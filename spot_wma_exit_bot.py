# spot_wma_exit_bot.py

import os
import time
import math
import platform
from binance.spot import Spot


# ==========================================================
# ALARMA SONORA – Glass + Voz femenina "Stop activado"
# ==========================================================
def sonar_alarma():
    if platform.system() == "Darwin":
        os.system('afplay "/System/Library/Sounds/Glass.aiff"')
        time.sleep(3)
        os.system('say -v Victoria "Stop activado"')
    else:
        for _ in range(5):
            print("\a")
            time.sleep(0.3)


# ==========================================================
# FUNCIONES AUXILIARES
# ==========================================================
def get_client():
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")
    if not api_key or not api_secret:
        raise RuntimeError("Faltan BINANCE_API_KEY o BINANCE_API_SECRET en variables de entorno.")
    return Spot(api_key=api_key, api_secret=api_secret)


def wma(values, length: int):
    if len(values) < length:
        return None
    weights = list(range(1, length + 1))
    sub = values[-length:]
    num = sum(v * w for v, w in zip(sub, weights))
    den = sum(weights)
    return num / den


def get_closes(client: Spot, symbol: str, interval: str, limit: int):
    klines = client.klines(symbol, interval, limit=limit)
    closes = [float(k[4]) for k in klines]
    return closes


def get_free_asset_balance(client: Spot, asset: str) -> float:
    info = client.account()
    for b in info.get("balances", []):
        if b["asset"] == asset:
            return float(b["free"])
    return 0.0


def get_lot_size_filter(client: Spot, symbol: str):
    """Obtiene minQty, maxQty y stepSize del símbolo."""
    info = client.exchange_info(symbol=symbol)
    sym = info["symbols"][0]
    for f in sym["filters"]:
        if f["filterType"] == "LOT_SIZE":
            min_qty = float(f["minQty"])
            max_qty = float(f["maxQty"])
            step_size = float(f["stepSize"])
            return min_qty, max_qty, step_size
    raise RuntimeError(f"No se encontró filtro LOT_SIZE para {symbol}")


def floor_to_step(qty: float, step: float) -> float:
    """Redondea hacia abajo a múltiplos del step."""
    if step <= 0:
        return qty
    return math.floor(qty / step) * step


def format_quantity(qty: float) -> str:
    """Convierte float a string decimal sin notación científica ni ceros sobrantes."""
    s = f"{qty:.10f}"
    s = s.rstrip("0").rstrip(".")
    return s


# ==========================================================
# FASE 1: ESPERAR ENTRADA POR CRUCE ALCISTA (WMA ENTRADA)
# ==========================================================
def esperar_entrada_cruce_alcista(client: Spot, symbol: str, interval: str, wma_entry_len: int, sleep_seconds: int):
    """
    Espera a que una vela COMPLETA cruce al alza la WMA de entrada.
    Condición: vela cerrada pasa de estado "below" a "above" respecto a WMA de entrada.
    """
    print(f"\n=== Buscando ENTRADA LONG en {symbol} ===")
    print(f"Condición: vela cerrada cruza AL ALZA la WMA{wma_entry_len} en {interval}.\n")

    last_closed_close = None

    while True:
        try:
            closes = get_closes(client, symbol, interval, limit=wma_entry_len + 5)
            if len(closes) < wma_entry_len + 3:
                print("Aún no hay suficientes velas para WMA de entrada. Esperando...")
                time.sleep(sleep_seconds)
                continue

            # [..., c_{-3}, c_{-2}, c_{-1}]
            close_prev = closes[-2]      # última vela cerrada
            close_prevprev = closes[-3]  # vela cerrada anterior

            if last_closed_close is None:
                last_closed_close = close_prev

            # Solo evaluar cuando haya una nueva vela cerrada
            if close_prev != last_closed_close:
                wma_prev = wma(closes[:-1], wma_entry_len)    # WMA en c_{-2}
                wma_prevprev = wma(closes[:-2], wma_entry_len)  # WMA en c_{-3}

                prev_state = "above" if close_prev > wma_prev else "below"
                prevprev_state = "above" if close_prevprev > wma_prevprev else "below"

                print(
                    f"[ENTRADA] Vela cerrada {interval} -> "
                    f"c_-3: {close_prevprev:.4f}, WMA_-3: {wma_prevprev:.4f}, "
                    f"c_-2: {close_prev:.4f}, WMA_-2: {wma_prev:.4f}, "
                    f"estados: {prevprev_state} -> {prev_state}"
                )

                # Cruce alcista confirmado al cierre
                if prevprev_state == "below" and prev_state == "above":
                    print("\n✅ Señal de ENTRADA LONG detectada (cruce alcista WMA de ENTRADA).")
                    current_price = float(client.ticker_price(symbol)["price"])
                    return current_price

                last_closed_close = close_prev

            time.sleep(sleep_seconds)

        except KeyboardInterrupt:
            print("\nBot detenido manualmente durante la fase de entrada.")
            return None
        except Exception as e:
            print(f"Error durante la fase de entrada: {e}")
            time.sleep(sleep_seconds)


# ==========================================================
# BOT SPOT – ENTRADA por CRUCE + CIERRE por WMA STOP
# ==========================================================
def main():
    print("=== Bot Spot – ENTRADA por cruce + CIERRE por WMA STOP ===")

    client = get_client()

    symbol = input("Símbolo Spot (ej: BTCUSDT): ").strip().upper() or "BTCUSDT"
    base_asset = symbol.replace("USDT", "")

    # Modo simulación
    sim_input = input("¿Simular sin enviar órdenes reales? (s/n): ").strip().lower() or "s"
    simular = sim_input in ["s", "si", "sí", "y", "yes"]

    interval = input("Marco de tiempo (ej: 1m, 5m, 15m, 1h): ").strip() or "15m"
    sleep_seconds = int(input("Segundos entre chequeos (ej: 15): ").strip() or "15")

    # WMA de entrada y WMA de stop
    wma_entry_len = int(input("Longitud de WMA de ENTRADA (ej: 89): ").strip() or "89")
    wma_stop_len = int(input("Longitud de WMA de STOP (ej: 34): ").strip() or "34")

    wait_close_input = input("¿Esperar cierre REAL de la vela para el STOP? (true/false): ").strip().lower() or "true"
    wait_on_close = wait_close_input in ["true", "t", "1", "s", "si", "sí", "y", "yes"]

    # Monto para la compra en USDT
    amount_usdt = float(input("Monto en USDT a usar en la entrada LONG: ").strip())

    print("\n=== RESUMEN CONFIGURACIÓN ===")
    print(f"Símbolo:             {symbol}")
    print(f"Modo:                {'SIMULACIÓN' if simular else 'REAL'}")
    print(f"Intervalo:           {interval}")
    print(f"WMA de ENTRADA:      {wma_entry_len}")
    print(f"WMA de STOP:         {wma_stop_len}")
    print(f"Sleep (segundos):    {sleep_seconds}")
    print(f"Esperar cierre STOP: {wait_on_close}")
    print(f"Monto de entrada:    {amount_usdt} USDT")
    continuar = input("\n¿Activar bot y esperar señal de ENTRADA? (s/n): ").strip().lower()
    if continuar not in ["s", "si", "sí", "y", "yes"]:
        print("Bot cancelado por el usuario.")
        return

    # Para el resumen
    entry_exec_price = None
    entry_usdt_real = None
    entry_order = None
    trade_start_time = None
    min_price_during_trade = None
    exit_order = None
    exit_price_used = None

    # === FASE 1: ESPERAR CRUCE ALCISTA WMA DE ENTRADA ===
    entry_price_ref = esperar_entrada_cruce_alcista(
        client=client,
        symbol=symbol,
        interval=interval,
        wma_entry_len=wma_entry_len,
        sleep_seconds=sleep_seconds,
    )

    if entry_price_ref is None:
        print("No se ejecutó entrada. Saliendo.")
        return

    qty_est = amount_usdt / entry_price_ref
    print(f"\nSeñal de entrada activada.")
    print(f"Precio de referencia (ticker): {entry_price_ref:.4f} USDT")
    print(f"Cantidad estimada a comprar:   {qty_est:.8f} {base_asset}")
    print("Ejecutando COMPRA automáticamente...\n")

    # === COMPRA AUTOMÁTICA ===
    if simular:
        print("SIMULACIÓN: No se envía orden de compra real.\n")
        entry_exec_price = entry_price_ref
        entry_usdt_real = amount_usdt
        trade_start_time = time.time()
    else:
        try:
            print("📥 ENVIANDO ORDEN MARKET BUY...")
            entry_order = client.new_order(
                symbol=symbol,
                side="BUY",
                type="MARKET",
                quoteOrderQty=amount_usdt
            )
            print("Orden de COMPRA enviada. Respuesta de Binance:")
            print(entry_order)

            # Tomamos datos para el resumen
            entry_usdt_real = float(entry_order.get("cummulativeQuoteQty", amount_usdt))
            # Precio medio ejecución:
            exec_qty = float(entry_order.get("executedQty", "0") or 0.0)
            if exec_qty > 0:
                entry_exec_price = entry_usdt_real / exec_qty
            else:
                entry_exec_price = entry_price_ref
            trade_start_time = time.time()
        except Exception as e:
            print(f"❌ Error enviando orden de compra: {e}")
            return

    if entry_exec_price is None:
        entry_exec_price = entry_price_ref
    if entry_usdt_real is None:
        entry_usdt_real = amount_usdt

    print("\n=== Compra realizada (real o simulada). Iniciando TRAILING WMA STOP... ===\n")

    # === FASE 2: TRAILING STOP POR CRUCE BAJISTA DE WMA STOP ===
    last_state = None
    last_closed_close = None

    # Filtros LOT_SIZE
    try:
        min_qty, max_qty, step_size = get_lot_size_filter(client, symbol)
        print(f"Filtro LOT_SIZE {symbol} -> minQty={min_qty}, stepSize={step_size}, maxQty={max_qty}")
    except Exception as e:
        print(f"⚠️ No se pudo obtener LOT_SIZE. Continuando sin normalizar: {e}")
        min_qty = None
        max_qty = None
        step_size = None

    # Para medir el "stop" observado: mínimo precio durante la operación
    min_price_during_trade = entry_exec_price

    trade_end_time = None
    exit_usdt_real = None
    total_commission_usdt = 0.0

    while True:
        try:
            closes = get_closes(client, symbol, interval, limit=wma_stop_len + 3)
            if len(closes) < wma_stop_len + 2:
                print("Aún no hay suficientes velas para WMA de STOP. Esperando...")
                time.sleep(sleep_seconds)
                continue

            wma_current = wma(closes, wma_stop_len)
            wma_prev = wma(closes[:-1], wma_stop_len)

            close_current = closes[-1]
            close_prev = closes[-2]

            # actualizar mínimo durante la operación
            if close_current < min_price_during_trade:
                min_price_during_trade = close_current

            current_state = "above" if close_current > wma_current else "below"
            prev_state = "above" if close_prev > wma_prev else "below"

            state_for_signal = prev_state if wait_on_close else current_state

            if last_state is None:
                last_state = state_for_signal
                last_closed_close = close_prev

            print(
                f"[STOP-PARCIAL] {symbol} {interval} -> "
                f"Close parcial: {close_current:.4f} | "
                f"WMA_STOP{wma_stop_len}: {wma_current:.4f} | "
                f"Estado actual: {current_state} | Estado señal: {state_for_signal}"
            )

            if close_prev != last_closed_close:
                print(f"[STOP-CERRADA] Nueva vela {interval} cerrada -> Close definitivo: {close_prev:.4f}")
                last_closed_close = close_prev

            crossed_down = last_state == "above" and state_for_signal == "below"
            trigger_exit = False
            motivo = ""

            if crossed_down:
                trigger_exit = True
                motivo = "Cruce bajista (precio cruza por debajo de la WMA de STOP)."

            if trigger_exit:
                exit_price = close_prev if wait_on_close else close_current
                exit_price_used = exit_price
                trade_end_time = time.time()

                # 🔔 Alarma
                sonar_alarma()

                print("\n=== SEÑAL DE SALIDA DETECTADA (WMA STOP) ===")
                print(f"Motivo:   {motivo}")
                print(f"Salida a: {exit_price:.4f}")

                # BALANCE TOTAL A VENDER
                raw_balance = get_free_asset_balance(client, base_asset)
                print(f"Balance detectado bruto: {raw_balance} {base_asset}")

                if raw_balance <= 0:
                    print("❌ No hay balance para vender.")
                    break

                balance = raw_balance

                # Normalizar según LOT_SIZE
                if step_size is not None:
                    balance = min(balance, max_qty) if max_qty is not None else balance
                    balance = floor_to_step(balance, step_size)

                if min_qty is not None and balance < min_qty:
                    print(f"❌ Cantidad {balance} es menor que minQty ({min_qty}). No se puede vender.")
                    break

                qty_str = format_quantity(balance)
                print(f"Cantidad a vender normalizada: {qty_str} {base_asset}")
                print(f"Modo: {'SIMULACIÓN' if simular else 'REAL'}\n")

                if not simular:
                    try:
                        print("📤 Enviando orden MARKET SELL...")
                        exit_order = client.new_order(
                            symbol=symbol,
                            side="SELL",
                            type="MARKET",
                            quantity=qty_str
                        )
                        print("Orden de VENTA enviada. Respuesta de Binance:")
                        print(exit_order)

                        # Monto de salida en USDT
                        exit_usdt_real = float(exit_order.get("cummulativeQuoteQty", "0") or 0.0)

                        # Comisiones en USDT (aprox)
                        def extraer_comision_usdt(order, ref_price):
                            total = 0.0
                            fills = order.get("fills", [])
                            for f in fills:
                                c = float(f.get("commission", "0") or 0.0)
                                asset = f.get("commissionAsset", "")
                                price_f = float(f.get("price", str(ref_price)) or ref_price)
                                if asset == "USDT":
                                    total += c
                                elif asset == base_asset:
                                    total += c * price_f
                            return total

                        if entry_order is not None:
                            total_commission_usdt += extraer_comision_usdt(entry_order, entry_exec_price)
                        if exit_order is not None:
                            total_commission_usdt += extraer_comision_usdt(exit_order, exit_price_used)

                    except Exception as e:
                        print(f"❌ Error al enviar la orden de venta: {e}")
                else:
                    print("SIMULACIÓN: No se envió orden real.")
                    # En simulación estimamos el monto de salida
                    exit_usdt_real = entry_usdt_real * (exit_price_used / entry_exec_price)

                print("\nBot finalizado tras ejecutar la salida.\n")
                break

            last_state = state_for_signal
            time.sleep(sleep_seconds)

        except KeyboardInterrupt:
            print("\nBot detenido manualmente durante la fase de STOP.")
            break
        except Exception as e:
            print(f"Error en fase de STOP: {e}")
            time.sleep(sleep_seconds)

    # ======================================================
    # RESUMEN FINAL DE LA OPERACIÓN
    # ======================================================
    if trade_start_time is not None and trade_end_time is not None and exit_price_used is not None:
        duration_sec = trade_end_time - trade_start_time
        duration_min = duration_sec / 60.0

        # Si por alguna razón no tenemos salida real, estimamos
        if exit_usdt_real is None:
            exit_usdt_real = entry_usdt_real * (exit_price_used / entry_exec_price)

        pnl_bruto_usdt = exit_usdt_real - entry_usdt_real
        pnl_bruto_pct = (pnl_bruto_usdt / entry_usdt_real) * 100 if entry_usdt_real != 0 else 0.0

        # "Stop" observado = máximo retroceso desde la entrada
        if min_price_during_trade is not None and min_price_during_trade < entry_exec_price:
            stop_pct = (entry_exec_price - min_price_during_trade) / entry_exec_price * 100
        else:
            stop_pct = 0.0

        # P&G neto tras comisiones
        pnl_neto_usdt = pnl_bruto_usdt - total_commission_usdt
        pnl_neto_pct = (pnl_neto_usdt / entry_usdt_real) * 100 if entry_usdt_real != 0 else 0.0

        # Riesgo/beneficio = utilidad% / stop%
        if stop_pct > 0:
            rr = pnl_bruto_pct / stop_pct
        else:
            rr = None

        print("========== RESUMEN DE LA OPERACIÓN ==========")
        print(f"Activo operado:           {symbol}")
        print(f"Monto de entrada (USDT):  {entry_usdt_real:.4f}")
        print(f"Precio entrada aprox:     {entry_exec_price:.4f} USDT")
        print(f"Monto de salida (USDT):   {exit_usdt_real:.4f}")
        print(f"Precio salida aprox:      {exit_price_used:.4f} USDT")
        print(f"% stop observado*:        {stop_pct:.4f} %")
        print(f"% utilidad/pérdida bruta: {pnl_bruto_pct:.4f} % ({pnl_bruto_usdt:.4f} USDT)")
        print(f"Comisión total aprox:     {total_commission_usdt:.4f} USDT")
        print(f"P&G neto final:           {pnl_neto_usdt:.4f} USDT ({pnl_neto_pct:.4f} %)")
        print(f"Duración operación:       {duration_min:.2f} minutos")
        if rr is not None:
            print(f"Riesgo/beneficio (utilidad% / stop%): {rr:.4f}")
        else:
            print("Riesgo/beneficio:         N/A (no hubo retroceso significativo)")
        print("* stop observado = máximo retroceso desde la entrada hasta el mínimo precio durante la operación.")
        print("=============================================\n")


if __name__ == "__main__":
    main()
