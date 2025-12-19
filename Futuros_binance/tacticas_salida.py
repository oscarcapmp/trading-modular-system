import time
from infra_futuros import (
    atr,
    get_hlc_futures,
    get_futures_usdt_balance,
    get_max_leverage_symbol,
    sonar_alarma,
    wma,
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
    entry_order_id: int | None = None,
    balance_inicial_futuros: float | None = None,
    emergency_atr_on: bool = True,
    atr_len: int = 14,
    emergency_mult: float = 1.5,
):
    last_state = None
    last_closed_close = None
    emergency_level = None
    emergency_atr_ref = None
    emergency_wma_ref = None
    emergency_announced = False

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
            limit_needed = max(wma_stop_len + 3, atr_len + 2)
            highs, lows, closes = get_hlc_futures(client, symbol, interval, limit=limit_needed)

            if len(closes) < wma_stop_len + 2:
                print("Aún no hay suficientes velas para WMA de STOP. Esperando...")
                time.sleep(sleep_seconds)
                continue

            wma_current = wma(closes, wma_stop_len)
            wma_prev = wma(closes[:-1], wma_stop_len)

            close_current = closes[-1]
            close_prev = closes[-2]

            if emergency_atr_on and emergency_level is None:
                atr_val = atr(highs, lows, closes, atr_len)
                if atr_val is not None and wma_current is not None:
                    emergency_atr_ref = atr_val
                    emergency_wma_ref = wma_current
                    if side == "long":
                        emergency_level = emergency_wma_ref - emergency_mult * emergency_atr_ref
                    else:
                        emergency_level = emergency_wma_ref + emergency_mult * emergency_atr_ref
                    print(
                        f"[EMERGENCIA ATR] Nivel fijado -> WMA_STOP ref: {emergency_wma_ref:.4f}, "
                        f"ATR{atr_len} ref: {emergency_atr_ref:.4f}, "
                        f"Nivel emergencia: {emergency_level:.4f}"
                    )
                    emergency_announced = True

            atr_txt = f"{emergency_atr_ref:.4f}" if emergency_atr_ref is not None else "N/D"
            emergency_txt = f"{emergency_level:.4f}" if emergency_level is not None else "N/D"

            if side == "long":
                if close_current < min_price_during_trade:
                    min_price_during_trade = close_current
            else:
                if close_current > max_price_during_trade:
                    max_price_during_trade = close_current

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
                f"Nivel emergencia (fijo): {emergency_txt} | "
                f"Estado actual: {current_state} | Estado señal: {state_for_signal}"
            )

            if close_prev != last_closed_close:
                print(f"[STOP-CERRADA FUT] Nueva vela {interval} cerrada -> Close definitivo: {close_prev:.4f}")
                last_closed_close = close_prev

            if side == "long":
                crossed = last_state == "above" and state_for_signal == "below"
            else:
                crossed = last_state == "below" and state_for_signal == "above"

            trigger_exit = False
            motivo = ""
            emergency_triggered = False
            exit_price = None

            if crossed:
                trigger_exit = True
                if side == "long":
                    motivo = "Cruce bajista (precio cruza por debajo de la WMA de STOP)."
                else:
                    motivo = "Cruce alcista (precio cruza por encima de la WMA de STOP)."
                exit_price = close_prev if wait_on_close else close_current

            if emergency_atr_on and emergency_level is not None:
                if side == "long":
                    emergency_triggered = close_current <= emergency_level
                else:
                    emergency_triggered = close_current >= emergency_level

                if emergency_triggered:
                    trigger_exit = True
                    exit_price = close_current
                    motivo = (
                        "Freno de emergencia: precio cruzó umbral ATR "
                        f"(nivel {emergency_level:.4f}, ATR{atr_len}={atr_txt})."
                    )

            if trigger_exit:
                exit_price_used = exit_price if exit_price is not None else close_current
                exit_price = exit_price_used
                trade_end_time = time.time()

                sonar_alarma()

                lado_txt = "LONG" if side == "long" else "SHORT"
                print(f"\n=== [FUTUROS] SEÑAL DE SALIDA {lado_txt} DETECTADA (WMA STOP) ===")
                print(f"Motivo:   {motivo}")
                if emergency_triggered and emergency_level is not None and emergency_atr_ref is not None:
                    print(
                        f"[EMERGENCIA ATR] Precio {close_current:.4f} rompió nivel "
                        f"{emergency_level:.4f} (ATR{atr_len}={emergency_atr_ref:.4f})"
                    )
                print(f"Salida a: {exit_price:.4f}")
                print(f"Cantidad a cerrar: {qty_str} {base_asset}")
                print(f"Modo: {'SIMULACIÓN' if simular else 'REAL'}\n")

                if not simular:
                    exit_side = "SELL" if side == "long" else "BUY"
                    try:
                        print(f"📤 Enviando orden MARKET {exit_side} para cerrar {lado_txt}...")
                        exit_order = client.new_order(
                            symbol=symbol,
                            side=exit_side,
                            type="MARKET",
                            quantity=qty_str
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

            last_state = state_for_signal
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
