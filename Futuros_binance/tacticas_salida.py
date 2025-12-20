import time
from infra_futuros import (
    atr,
    format_quantity,
    get_hlc_futures,
    get_futures_usdt_balance,
    get_max_leverage_symbol,
    sonar_alarma,
    wma,
)
from config_wma_pack import MAX_WMA_PACK_LEN
from Trailing_dinamico import (
    calcular_wmas_trailing,
    calcular_wmas_trailing_prev,
    init_trailing_state,
    update_trailing,
)


def tactica_salida_trailing_stop_wma(
    client,
    symbol: str,
    base_asset: str,
    interval: str,
    sleep_seconds: int,
    wma_stop_len: int,
    wait_on_close: bool,
    qty_est: float,
    qty_str: str,
    entry_exec_price: float,
    entry_margin_usdt: float,
    simular: bool,
    side: str,
    trailing_dinamico_on: bool,
    entry_order_id: int | None = None,
    balance_inicial_futuros: float | None = None,
    emergency_atr_on: bool = True,
    atr_len: int = 14,
    atr_mult: float = 1.5,
    pct_fase1: float = 50.0,
):
    last_state = None
    last_closed_close = None
    trailing_state = init_trailing_state(pct_fase1) if trailing_dinamico_on else None
    qty_remaining = qty_est
    stop_mode_logged = False
    invalid_stop_reported = False

    if side == "long":
        min_price_during_trade = entry_exec_price
        max_price_during_trade = None
    else:
        min_price_during_trade = None
        max_price_during_trade = entry_exec_price

    trade_start_time = time.time()
    trade_end_time = None
    exit_price_used = None
    exit_order_id = None

    while True:
        try:
            state_for_signal = None
            limit_needed = max(
                (wma_stop_len + 3) if wma_stop_len else 0,
                atr_len + 2,
                MAX_WMA_PACK_LEN + 1,
                990,
            )
            highs, lows, closes = get_hlc_futures(client, symbol, interval, limit=limit_needed)

            if not stop_mode_logged:
                mode_txt = "DINAMICO" if trailing_dinamico_on else "CLASICO"
                print(f"[DEBUG] STOP_MODE={mode_txt}")
                stop_mode_logged = True

            wma_current = wma(closes, wma_stop_len) if (not trailing_dinamico_on and wma_stop_len > 0) else None
            wma_prev = wma(closes[:-1], wma_stop_len) if (not trailing_dinamico_on and wma_stop_len > 0) else None

            close_current = closes[-1]
            close_prev = closes[-2]

            atr_val = atr(highs, lows, closes, atr_len) if emergency_atr_on else None
            atr_txt = f"{atr_val:.4f}" if atr_val is not None else "N/D"

            if side == "long":
                if close_current < min_price_during_trade:
                    min_price_during_trade = close_current
            else:
                if close_current > max_price_during_trade:
                    max_price_during_trade = close_current
            # Freno ATR local
            if emergency_atr_on and atr_val is not None and entry_exec_price is not None:
                if side == "long":
                    atr_level = entry_exec_price - atr_mult * atr_val
                    atr_triggered = close_current <= atr_level
                else:
                    atr_level = entry_exec_price + atr_mult * atr_val
                    atr_triggered = close_current >= atr_level
                if atr_triggered and qty_remaining > 0:
                    qty_close_str = format_quantity(abs(qty_remaining))
                    print(
                        f"[FRENO ATR LOCAL] k={atr_mult} ATR{atr_len}={atr_val:.4f} "
                        f"umbral={atr_level:.4f} -> cerrando MARKET (reduce-only)"
                    )
                    if simular:
                        print(f"[SIMULACIÓN] Cierre total por ATR local qty={qty_close_str}")
                    else:
                        exit_side = "SELL" if side == "long" else "BUY"
                        try:
                            client.new_order(
                                symbol=symbol,
                                side=exit_side,
                                type="MARKET",
                                quantity=qty_close_str,
                                reduceOnly=True,
                            )
                        except Exception as e:
                            print(f"❌ Error cerrando por ATR local: {e}")
                    return

            trigger_exit = False
            motivo = ""
            exit_price = None

            if trailing_dinamico_on:
                price_for_stop = close_prev if wait_on_close else close_current
                wmas_dyn = calcular_wmas_trailing(closes)
                wmas_dyn_prev = calcular_wmas_trailing_prev(closes)
                trailing_state, decision = update_trailing(
                    trailing_state,
                    side=side,
                    price=price_for_stop,
                    wmas=wmas_dyn,
                    wmas_prev=wmas_dyn_prev,
                )
                trailing_val_txt = f"{decision.get('trailing_value'):.4f}" if decision.get("trailing_value") is not None else "N/D"
                trailing_len_txt = decision.get("trailing_len")
                print(
                    f"[TRAILING DIN] fase={decision.get('phase')} "
                    f"trailing={decision.get('trailing_name')}({trailing_len_txt})@{trailing_val_txt} "
                    f"dist34={decision.get('dist_pollita')} dist55={decision.get('dist_celeste')} "
                    f"cruce233_377={decision.get('cross_233_377')} action={decision.get('action')}"
                )

                if decision.get("action") == "sell_partial" and qty_remaining > 0:
                    pct = decision.get("pct", 0)
                    qty_partial = abs(qty_remaining) * pct
                    if qty_partial > 0:
                        qty_partial_str = format_quantity(qty_partial)
                        if simular:
                            print(f"[SIMULACIÓN] Parcial Fase 1: {qty_partial_str}")
                        else:
                            exit_side_partial = "SELL" if side == "long" else "BUY"
                            try:
                                client.new_order(
                                    symbol=symbol,
                                    side=exit_side_partial,
                                    type="MARKET",
                                    quantity=qty_partial_str,
                                    reduceOnly=True,
                                )
                                print(f"[TRAILING DIN] Parcial enviada {exit_side_partial} {qty_partial_str}")
                            except Exception as e:
                                print(f"⚠️ Parcial Fase 1 falló: {e}")
                        qty_remaining -= qty_partial
                    time.sleep(sleep_seconds)
                    continue

                if decision.get("action") == "close_all":
                    trigger_exit = True
                    motivo = "Trailing dinámico fase 2"
                    exit_price = price_for_stop

            else:
                if wma_stop_len <= 0:
                    if not invalid_stop_reported:
                        print("WMA_STOP inválida (<=0). Ajusta la longitud o usa trailing dinámico.")
                        invalid_stop_reported = True
                    return
                current_state = "above" if close_current > wma_current else "below"
                prev_state = "above" if close_prev > wma_prev else "below"
                state_for_signal = prev_state if wait_on_close else current_state

                if last_state is None:
                    last_state = state_for_signal
                    last_closed_close = close_prev

                print(
                    f"[STOP-PARCIAL FUT] {symbol} {interval} -> "
                    f"Close parcial: {close_current:.4f} | "
                    f"WMA_STOP{wma_stop_len}: {wma_current:.4f} | ATR{atr_len} ref: {atr_txt} | "
                    f"Estado actual: {current_state} | Estado señal: {state_for_signal}"
                )

                if close_prev != last_closed_close:
                    print(f"[STOP-CERRADA FUT] Nueva vela {interval} cerrada -> Close definitivo: {close_prev:.4f}")
                    last_closed_close = close_prev

                if side == "long":
                    crossed = last_state == "above" and state_for_signal == "below"
                else:
                    crossed = last_state == "below" and state_for_signal == "above"

                if crossed:
                    trigger_exit = True
                    if side == "long":
                        motivo = "Cruce bajista (precio cruza por debajo de la WMA de STOP)."
                    else:
                        motivo = "Cruce alcista (precio cruza por encima de la WMA de STOP)."
                    exit_price = close_prev if wait_on_close else close_current

            if trigger_exit:
                exit_price_used = exit_price if exit_price is not None else close_current
                exit_price = exit_price_used
                trade_end_time = time.time()

                sonar_alarma()

                lado_txt = "LONG" if side == "long" else "SHORT"
                print(f"\n=== [FUTUROS] SEÑAL DE SALIDA {lado_txt} DETECTADA (WMA STOP) ===")
                print(f"Motivo:   {motivo}")
                print(f"Salida a: {exit_price:.4f}")
                qty_close_str = format_quantity(abs(qty_remaining))
                print(f"Cantidad a cerrar: {qty_close_str} {base_asset}")
                print(f"Modo: {'SIMULACIÓN' if simular else 'REAL'}\n")

                if not simular:
                    exit_side = "SELL" if side == "long" else "BUY"
                    try:
                        print(f"📤 Enviando orden MARKET {exit_side} para cerrar {lado_txt}...")
                        exit_order = client.new_order(
                            symbol=symbol,
                            side=exit_side,
                            type="MARKET",
                            quantity=qty_close_str,
                            reduceOnly=True,
                        )
                        print("Orden de CIERRE enviada. Respuesta de Binance:")
                        print(exit_order)
                        exit_order_id = exit_order.get("orderId")

                    except Exception as e:
                        print(f"❌ Error al enviar la orden de cierre en Futuros: {e}")
                else:
                    print("SIMULACIÓN: No se envió orden real de cierre.")

                print("\nBot Futuros finalizado tras ejecutar la salida.\n")
                break

            last_state = state_for_signal if not trailing_dinamico_on else last_state
            time.sleep(sleep_seconds)

        except KeyboardInterrupt:
            print("\nBot detenido manualmente durante la fase de STOP en Futuros.")
            trade_end_time = time.time()
            break
        except Exception as e:
            print(f"Error en fase de STOP (Futuros): {e}")
            time.sleep(sleep_seconds)

    if trade_end_time is None:
        trade_end_time = time.time()

    duration_sec = trade_end_time - trade_start_time
    duration_min = duration_sec / 60.0

    if exit_price_used is not None and entry_exec_price is not None:
        if side == "long":
            pnl_bruto_usdt = (exit_price_used - entry_exec_price) * qty_est
        else:
            pnl_bruto_usdt = (entry_exec_price - exit_price_used) * qty_est
    else:
        pnl_bruto_usdt = 0.0

    if side == "long":
        if min_price_during_trade is not None and min_price_during_trade < entry_exec_price:
            stop_pct = (entry_exec_price - min_price_during_trade) / entry_exec_price * 100
        else:
            stop_pct = 0.0
    else:
        if max_price_during_trade is not None and max_price_during_trade > entry_exec_price:
            stop_pct = (max_price_during_trade - entry_exec_price) / entry_exec_price * 100
        else:
            stop_pct = 0.0

    if entry_margin_usdt != 0:
        pnl_bruto_pct = (pnl_bruto_usdt / entry_margin_usdt) * 100
    else:
        pnl_bruto_pct = 0.0

    if stop_pct > 0:
        rr = pnl_bruto_pct / stop_pct
    else:
        rr = None

    bal_ini = balance_inicial_futuros if balance_inicial_futuros is not None else 0.0

    if not simular and balance_inicial_futuros is not None:
        try:
            bal_fin = get_futures_usdt_balance(client)
        except Exception as e:
            print(f"⚠️ No se pudo leer balance final de Futuros: {e}")
            bal_fin = bal_ini
    else:
        bal_fin = bal_ini + pnl_bruto_usdt

    pnl_real_usdt = bal_fin - bal_ini

    commission_usdt = pnl_bruto_usdt - pnl_real_usdt

    if entry_margin_usdt != 0:
        pnl_neto_pct = (pnl_real_usdt / entry_margin_usdt) * 100
    else:
        pnl_neto_pct = 0.0

    if bal_ini != 0:
        aporte_balance_pct = (pnl_real_usdt / bal_ini) * 100
    else:
        aporte_balance_pct = 0.0

    lado_txt = "LONG" if side == "long" else "SHORT"

    max_lev_disp = get_max_leverage_symbol(client, symbol)

    inversion_apalancada = qty_est * entry_exec_price if entry_exec_price is not None else 0.0

    if exit_price_used is not None and entry_exec_price is not None and entry_exec_price != 0:
        if side == "long":
            retorno_mov_pct = (exit_price_used - entry_exec_price) / entry_exec_price * 100
        else:
            retorno_mov_pct = (entry_exec_price - exit_price_used) / entry_exec_price * 100
    else:
        retorno_mov_pct = 0.0

    print(f"========== RESUMEN DE LA OPERACIÓN FUTUROS ({lado_txt} TRAILING) ==========")
    print(f"Apalancamiento máximo disponible:\t{max_lev_disp:.0f}x")
    print(f"Inversión apalancada\t\t\t{inversion_apalancada:.4f}")
    print(f"Balance de cuenta inicial\t\t{bal_ini:.4f}")
    print(f"Precio de entrada\t\t\t{entry_exec_price:.4f}")
    if exit_price_used is not None:
        print(f"Precio de salida\t\t\t{exit_price_used:.4f}")
    else:
        print("Precio de salida\t\t\tN/D")

    print(f"Retorno de la inversión (movimiento)\t{retorno_mov_pct:.4f}%")
    print(f"Stop calculado\t\t\t\t{stop_pct:.4f}%")

    if rr is not None:
        print(f"Riesgo/Beneficio\t\t\t{rr:.4f}")
    else:
        print("Riesgo/Beneficio\t\t\tN/A")

    print(f"Ganancia/pérdida antes de comisiones\t{pnl_bruto_usdt:.4f}")
    print(f"Comisión\t\t\t\t{commission_usdt:.4f}")
    print(f"Utilidad\t\t\t\t{pnl_real_usdt:.4f}")
    print(f"P&G neto final\t\t\t\t{pnl_real_usdt:.4f}")
    print(f"Balance de cuenta final\t\t\t{bal_fin:.4f}")
    print(f"% de aporte al balance\t\t\t{aporte_balance_pct:.4f}%")
    print(f"Duración operación (min)\t\t{duration_min:.2f}")
    print("==========================================================\n")


def tactica_salida_trailing_3_fases(*args, **kwargs):
    """
    Trailing stop en 3 fases:
    - Un porcentaje en WMA 34
    - Otro en WMA 89
    - Otro en WMA 233
    """
    pass
