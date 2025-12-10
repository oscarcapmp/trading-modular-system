# tacticas_salida.py
import time
from infra_futuros import (
    sonar_alarma,
    wma,
    get_closes_futuros,
    get_futuros_usdt_balance,
    get_max_leverage_symbol,
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
    side: str,  # "long" o "short"
    balance_inicial_futuros: float | None = None,
):
    """
    TÁCTICA DE SALIDA: Trailing stop con WMA.

    - Para LONG: sale cuando el precio cruza de arriba hacia abajo la WMA STOP.
    - Para SHORT: sale cuando el precio cruza de abajo hacia arriba la WMA STOP.

    Mantengo el cálculo de P&L simple pero útil.
    """

    last_state = None
    last_closed_close = None

    # Para medir el peor movimiento en contra (stop observado)
    if side == "long":
        min_price_during_trade = entry_exec_price
        max_price_during_trade = entry_exec_price
    else:
        min_price_during_trade = entry_exec_price
        max_price_during_trade = entry_exec_price

    trade_start_time = time.time()
    trade_end_time = None
    exit_price_used = None

    while True:
        try:
            closes = get_closes_futuros(client, symbol, interval, limit=wma_stop_len + 3)
            if len(closes) < wma_stop_len + 2:
                print("Aún no hay suficientes velas para WMA de STOP. Esperando...")
                time.sleep(sleep_seconds)
                continue

            wma_current = wma(closes, wma_stop_len)
            wma_prev = wma(closes[:-1], wma_stop_len)

            close_current = closes[-1]
            close_prev = closes[-2]

            # Actualizar extremos (máximo/mínimo durante la operación)
            if side == "long":
                if close_current < min_price_during_trade:
                    min_price_during_trade = close_current
                if close_current > max_price_during_trade:
                    max_price_during_trade = close_current
            else:
                if close_current > max_price_during_trade:
                    max_price_during_trade = close_current
                if close_current < min_price_during_trade:
                    min_price_during_trade = close_current

            current_state = "above" if close_current > wma_current else "below"
            prev_state = "above" if close_prev > wma_prev else "below"

            state_for_signal = prev_state if wait_on_close else current_state

            if last_state is None:
                last_state = state_for_signal
                last_closed_close = close_prev

            print(
                f"[TRAILING] {symbol} {interval} -> "
                f"Close: {close_current:.4f} | WMA_STOP{wma_stop_len}: {wma_current:.4f} | "
                f"Estado actual: {current_state} | Estado señal: {state_for_signal}"
            )

            if close_prev != last_closed_close:
                print(f"[TRAILING] Nueva vela {interval} cerrada a {close_prev:.4f}")
                last_closed_close = close_prev

            # Detectar cruce de salida
            if side == "long":
                crossed = last_state == "above" and state_for_signal == "below"
            else:
                crossed = last_state == "below" and state_for_signal == "above"

            if crossed:
                exit_price = close_prev if wait_on_close else close_current
                exit_price_used = exit_price
                trade_end_time = time.time()

                sonar_alarma()

                lado_txt = "LONG" if side == "long" else "SHORT"
                print(f"\n=== [TÁCTICA SALIDA] SEÑAL DE SALIDA {lado_txt} DETECTADA (TRAILING WMA) ===")
                print(f"Salida a: {exit_price:.4f}")
                print(f"Cantidad a cerrar: {qty_str} {base_asset}")
                print(f"Modo: {'SIMULACIÓN' if simular else 'REAL'}\n")

                if not simular:
                    binance_side = "SELL" if side == "long" else "BUY"
                    try:
                        print(f"📤 Enviando orden MARKET {binance_side} para cerrar {lado_txt}...")
                        exit_order = client.new_order(
                            symbol=symbol,
                            side=binance_side,
                            type="MARKET",
                            quantity=qty_str
                        )
                        print("Orden de CIERRE enviada. Respuesta de Binance:")
                        print(exit_order)
                    except Exception as e:
                        print(f"❌ Error al enviar la orden de cierre en Futuros: {e}")
                else:
                    print("SIMULACIÓN: No se envió orden real de cierre.")

                print("\nTáctica de salida por trailing completada.\n")
                break

            last_state = state_for_signal
            time.sleep(sleep_seconds)

        except KeyboardInterrupt:
            print("\nBot detenido manualmente durante la táctica de salida.")
            trade_end_time = time.time()
            break
        except Exception as e:
            print(f"Error en táctica de salida (Trailing): {e}")
            time.sleep(sleep_seconds)

    # ===== Resumen simple =====
    if trade_end_time is None:
        trade_end_time = time.time()

    duration_min = (trade_end_time - trade_start_time) / 60.0

    if exit_price_used is not None:
        if side == "long":
            pnl_bruto_usdt = (exit_price_used - entry_exec_price) * qty_est
        else:
            pnl_bruto_usdt = (entry_exec_price - exit_price_used) * qty_est
    else:
        pnl_bruto_usdt = 0.0

    # Stop observado como % movimiento máximo en contra
    if side == "long":
        worst_move_pct = (entry_exec_price - min_price_during_trade) / entry_exec_price * 100
    else:
        worst_move_pct = (max_price_during_trade - entry_exec_price) / entry_exec_price * 100

    # Balance antes/después si se proporcionó
    bal_ini = balance_inicial_futuros if balance_inicial_futuros is not None else 0.0
    if bal_ini > 0:
        if not simular:
            try:
                bal_fin = get_futuros_usdt_balance(client)
            except Exception as e:
                print(f"⚠️ No se pudo leer balance final de Futuros: {e}")
                bal_fin = bal_ini
        else:
            bal_fin = bal_ini + pnl_bruto_usdt
        pnl_real_usdt = bal_fin - bal_ini
    else:
        bal_fin = bal_ini + pnl_bruto_usdt
        pnl_real_usdt = pnl_bruto_usdt

    lado_txt = "LONG" if side == "long" else "SHORT"
    max_lev_disp = get_max_leverage_symbol(client, symbol)
    inversion_apalancada = qty_est * entry_exec_price if entry_exec_price else 0.0

    print("========== RESUMEN OPERACIÓN FUTUROS (TRAILING WMA) ==========")
    print(f"Símbolo:\t\t\t{symbol}")
    print(f"Lado:\t\t\t\t{lado_txt}")
    print(f"Apalancamiento máx. ref.:\t{max_lev_disp}x")
    print(f"Precio entrada:\t\t\t{entry_exec_price:.4f}")
    if exit_price_used is not None:
        print(f"Precio salida:\t\t\t{exit_price_used:.4f}")
    else:
        print("Precio salida:\t\t\tN/D")
    print(f"Cantidad:\t\t\t{qty_est} {base_asset}")
    print(f"Inversión apalancada aprox.:\t{inversion_apalancada:.4f} USDT")
    print(f"P&G bruto estimado:\t\t{pnl_bruto_usdt:.4f} USDT")
    print(f"P&G real (si hay balance_ini):\t{pnl_real_usdt:.4f} USDT")
    print(f"Peor movimiento en contra:\t{worst_move_pct:.4f}%")
    print(f"Balance inicial:\t\t{bal_ini:.4f} USDT")
    print(f"Balance final:\t\t\t{bal_fin:.4f} USDT")
    print(f"Duración operación (min):\t{duration_min:.2f}")
    print("==============================================================\n")


def tactica_salida_trailing_stop_3_fases(*args, **kwargs):
    """
    TÁCTICA DE SALIDA EN 3 FASES (WMA34, WMA89, WMA233).

    De salida:
    a. Trailing stop en 3 fases, sale un porcentaje en WMA de 34,
       otro en WMA de 89 y otro en WMA de 233.

    👉 Para mantener el sistema MUY SIMPLE, esta función la dejamos como
       'stub' (pendiente de implementar). Más adelante la puedes construir
       usando la misma idea de tactica_salida_trailing_stop_wma pero
       aplicando 3 cierres parciales.
    """
    print("⚠️ Táctica de salida en 3 fases aún no implementada. Usa trailing simple por ahora.")
