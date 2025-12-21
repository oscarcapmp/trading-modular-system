import time

try:
    from infra_futuros import (
        atr,
        format_quantity,
        get_hlc_futures,
        get_futures_usdt_balance,
        get_max_leverage_symbol,
        get_lot_size_filter_futures,
        sonar_alarma,
        wma,
    )
    from config_wma_pack import MAX_WMA_PACK_LEN
except ImportError:
    from Futuros_binance.infra_futuros import (
        atr,
        format_quantity,
        get_hlc_futures,
        get_futures_usdt_balance,
        get_max_leverage_symbol,
        get_lot_size_filter_futures,
        sonar_alarma,
        wma,
    )
    from Futuros_binance.config_wma_pack import MAX_WMA_PACK_LEN


def tactica_salida_stop_clasico(
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
    trailing_state = None
    qty_remaining = qty_est
    notional_entry = (entry_exec_price or 0) * qty_est
    stop_mode_logged = False
    invalid_stop_reported = False
    base_wma_ref = None
    base_wma_len = None
    base_wma_name = None
    realized_pnl_total_usdt = 0.0
    partial_logged = False
    phase2_logged = False
    last_atr_level = None
    atr_stop_fijo = None
    atr_entry = None

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
    step_size = None
    tick_counter = 0
    try:
        _, _, step_size = get_lot_size_filter_futures(client, symbol)
    except Exception as e:
        print(f"⚠️ No se pudo leer LOT_SIZE para normalizar parciales: {e}")

    # Calcular WMA base y ATR de entrada para STOP fijo (fase 1+2)
    try:
        highs_init, lows_init, closes_init = get_hlc_futures(client, symbol, interval, limit=MAX_WMA_PACK_LEN + 2)
        wma_34 = wma(closes_init, 34)
        wma_55 = wma(closes_init, 55)
        if entry_exec_price is not None:
            dist_34 = abs(entry_exec_price - wma_34)
            dist_55 = abs(entry_exec_price - wma_55)
            if dist_34 >= dist_55:
                base_wma_ref = wma_34
                base_wma_len = 34
                base_wma_name = "Pollita"
            else:
                base_wma_ref = wma_55
                base_wma_len = 55
                base_wma_name = "Celeste"
        if emergency_atr_on:
            atr_entry = atr(highs_init, lows_init, closes_init, atr_len)
            base_for_atr = base_wma_ref if base_wma_ref is not None else entry_exec_price
            if base_for_atr is not None and atr_entry is not None:
                if side == "long":
                    atr_stop_fijo = base_for_atr - atr_mult * atr_entry
                else:
                    atr_stop_fijo = base_for_atr + atr_mult * atr_entry
                last_atr_level = atr_stop_fijo
                print(
                    f"[ATR_STOP_FIJO] base={base_for_atr:.4f} ({base_wma_name or 'entry'}) "
                    f"ATR{atr_len}_entry={atr_entry:.4f} k={atr_mult} stop={atr_stop_fijo:.4f}"
                )
    except Exception as e:
        print(f"⚠️ No se pudo calcular ATR_STOP_FIJO: {e}")
        base_wma_ref = entry_exec_price
        base_wma_len = None
        base_wma_name = None

    while True:
        try:
            state_for_signal = None
            limit_needed = max(
                (wma_stop_len + 3) if wma_stop_len else 0,
                MAX_WMA_PACK_LEN + 1,
                990,
            )
            highs, lows, closes = get_hlc_futures(client, symbol, interval, limit=limit_needed)
            tick_counter += 1

            if not stop_mode_logged:
                mode_txt = "DINAMICO" if trailing_dinamico_on else "CLASICO"
                print(f"[DEBUG] STOP_MODE={mode_txt}")
                stop_mode_logged = True

            wma_current = wma(closes, wma_stop_len) if (not trailing_dinamico_on and wma_stop_len > 0) else None
            wma_prev = wma(closes[:-1], wma_stop_len) if (not trailing_dinamico_on and wma_stop_len > 0) else None

            close_current = closes[-1]
            close_prev = closes[-2]

            atr_txt = f"{atr_entry:.4f}" if atr_entry is not None else "N/D"

            if side == "long":
                if close_current < min_price_during_trade:
                    min_price_during_trade = close_current
            else:
                if close_current > max_price_during_trade:
                    max_price_during_trade = close_current
            # Freno ATR local (fijo)
            if emergency_atr_on and atr_stop_fijo is not None and entry_exec_price is not None:
                atr_level = atr_stop_fijo
                atr_triggered = close_current <= atr_level if side == "long" else close_current >= atr_level
                last_atr_level = atr_level
                print(
                    f"[FRENO ATR LOCAL] price_now={close_current:.4f} stop_fijo={atr_level:.4f} "
                    f"cond={'<=' if side=='long' else '>='}"
                )
                if atr_triggered and qty_remaining > 0:
                    qty_close_str = format_quantity(abs(qty_remaining))
                    price_event = close_current
                    pnl_remain = (price_event - entry_exec_price) * qty_remaining if side == "long" else (entry_exec_price - price_event) * qty_remaining
                    realized_pnl_total_usdt += pnl_remain
                    pnl_pct_total = (pnl_remain / (entry_exec_price * qty_remaining) * 100) if entry_exec_price and qty_remaining else 0.0
                    print(
                        f"[EVENTO] Cierre total por ATR FIJO @ {atr_level:.4f} | price_now={price_event:.4f} "
                        f"PnL_realizado={pnl_remain:.4f} USDT ({pnl_pct_total:.2f}%) "
                        f"PnL_total={realized_pnl_total_usdt:.4f} USDT"
                    )
                    if simular:
                        print(f"[SIMULACIÓN] Cierre total por ATR fijo qty={qty_close_str}")
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
                            print(f"❌ Error cerrando por ATR fijo: {e}")
                    return

            trigger_exit = False
            motivo = ""
            exit_price = None

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

                pnl_exit = (
                    (exit_price_used - entry_exec_price) * qty_remaining
                    if side == "long"
                    else (entry_exec_price - exit_price_used) * qty_remaining
                )
                realized_pnl_total_usdt += pnl_exit
                pnl_total_pct = (realized_pnl_total_usdt / notional_entry * 100) if notional_entry else 0.0

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

                print(
                    f"[EVENTO] Salida final ({motivo}) | PnL_tramo={pnl_exit:.4f} USDT "
                    f"PnL_total={realized_pnl_total_usdt:.4f} USDT ({pnl_total_pct:.2f}%)"
                )

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

    pnl_bruto_usdt = realized_pnl_total_usdt

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

    pnl_bruto_pct = (pnl_bruto_usdt / notional_entry * 100) if notional_entry else 0.0

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

    pnl_neto_pct = (pnl_real_usdt / notional_entry) * 100 if notional_entry else 0.0

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
