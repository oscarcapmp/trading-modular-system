# futures_wma_exit_bot.py
import os
import time
import math
import platform

try:
    from binance.um_futures import UMFutures
except ModuleNotFoundError:
    print("❌ No se encontró 'binance.um_futures'.")
    print("Instala la librería con:\n   pip install binance-futures-connector")
    raise


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
# CLIENTE FUTUROS Y UTILIDADES BÁSICAS
# ==========================================================
def get_futures_client():
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")
    if not api_key or not api_secret:
        raise RuntimeError("Faltan BINANCE_API_KEY o BINANCE_API_SECRET en variables de entorno.")
    return UMFutures(key=api_key, secret=api_secret)


def wma(values, length: int):
    if len(values) < length:
        return None
    weights = list(range(1, length + 1))
    sub = values[-length:]
    num = sum(v * w for v, w in zip(sub, weights))
    den = sum(weights)
    return num / den


def get_closes_futures(client: UMFutures, symbol: str, interval: str, limit: int):
    klines = client.klines(symbol=symbol, interval=interval, limit=limit)
    closes = [float(k[4]) for k in klines]
    return closes


def floor_to_step(qty: float, step: float) -> float:
    if step <= 0:
        return qty
    return math.floor(qty / step) * step


def format_quantity(qty: float) -> str:
    s = f"{qty:.10f}"
    s = s.rstrip("0").rstrip(".")
    return s


def get_lot_size_filter_futures(client: UMFutures, symbol: str):
    """LOT_SIZE para Futuros USDT-M."""
    info = client.exchange_info()
    for sym in info["symbols"]:
        if sym["symbol"] == symbol:
            for f in sym["filters"]:
                if f["filterType"] == "LOT_SIZE":
                    min_qty = float(f["minQty"])
                    max_qty = float(f["maxQty"])
                    step_size = float(f["stepSize"])
                    return min_qty, max_qty, step_size
    raise RuntimeError(f"No se encontró filtro LOT_SIZE para {symbol} en Futuros.")


def get_futures_usdt_balance(client: UMFutures) -> float:
    """Balance disponible USDT en Futuros USDT-M (wallet de Futuros, no Spot)."""
    try:
        balances = client.balance()
        for b in balances:
            if b.get("asset") == "USDT":
                return float(b.get("availableBalance", b.get("balance", "0")))
    except Exception as e:
        print(f"⚠️ No se pudo leer balance de Futuros: {e}")
    return 0.0


def get_max_leverage_symbol(client: UMFutures, symbol: str) -> int:
    """
    En tu versión de la librería no está disponible leverage_bracket.
    Usamos 20x como apalancamiento máximo por defecto (muy típico en BTCUSDT).
    """
    return 20


# ==========================================================
# COMISIONES: LECTURA DESDE TRADES DE FUTUROS (OPCIONAL)
# ==========================================================
def get_commission_for_order_usdt(
    client: UMFutures,
    symbol: str,
    base_asset: str,
    order_id: int,
    ref_price: float
) -> float:
    """
    Lee los trades de Futuros para el símbolo y suma la comisión
    asociada al orderId dado, convertida a USDT.
    Se mantiene como referencia, pero el cálculo "bueno" lo vamos a
    hacer comparando balance inicial vs balance final.
    """
    total = 0.0
    try:
        trades = client.user_trades(symbol=symbol, limit=1000)
        for t in trades:
            if t.get("orderId") != order_id:
                continue

            commission = float(t.get("commission", "0") or 0.0)
            asset = t.get("commissionAsset", "")
            price_fill = float(t.get("price", str(ref_price)) or ref_price)

            if commission == 0:
                continue

            if asset == "USDT":
                total += commission
            elif asset == base_asset:
                total += commission * price_fill
            else:
                total += commission * ref_price

    except Exception as e:
        print(f"⚠️ No se pudieron obtener comisiones para orderId {order_id}: {e}")

    return total


# ==========================================================
# PRECHECK ESTILO "QUANTFURY": PODER DE TRADING (NOTIONAL)
# ==========================================================
def precheck_poder_trading(client: UMFutures, symbol: str, poder_usdt: float) -> bool:
    """
    Recibe el PODER DE TRADING en USDT que el usuario quiere usar.
    Valida:
    - LOT_SIZE (minQty, stepSize)
    - NOTIONAL mínimo (100 USDT).
    """
    ticker = client.ticker_price(symbol=symbol)
    price = float(ticker["price"])

    min_qty, max_qty, step_size = get_lot_size_filter_futures(client, symbol)

    raw_qty_est = poder_usdt / price
    qty_est = min(raw_qty_est, max_qty)
    qty_est = floor_to_step(qty_est, step_size)

    # --- Validar minQty ---
    if qty_est < min_qty:
        notional_min_qty = min_qty * price
        print("\n❌ Con este poder de trading NO se alcanza el minQty del símbolo.")
        print(f"Símbolo:                 {symbol}")
        print(f"Precio ref:              {price:.4f} USDT")
        print(f"minQty (contratos):      {min_qty}")
        print(f"Cantidad calculada:      {qty_est}")
        print(f"Notional mínimo por minQty: {notional_min_qty:.4f} USDT")
        print("Aumenta el poder de trading o usa otro símbolo con notional más bajo.\n")
        return False

    # --- Validar NOTIONAL mínimo 100 USDT ---
    NOTIONAL_MIN = 100.0
    notional_est = qty_est * price

    if notional_est < NOTIONAL_MIN:
        qty_min_notional = NOTIONAL_MIN / price
        steps_needed = math.ceil(qty_min_notional / step_size)
        qty_needed = steps_needed * step_size
        notional_needed = qty_needed * price

        print("\n❌ Con este poder de trading la orden NO alcanza el notional mínimo de Binance Futuros.")
        print(f"Símbolo:                 {symbol}")
        print(f"Precio ref:              {price:.4f} USDT")
        print(f"Notional estimado:       {notional_est:.4f} USDT")
        print(f"Notional mínimo requerido: {NOTIONAL_MIN:.4f} USDT")
        print(f"Cantidad actual estimada: {qty_est}")
        print(f"Cantidad mínima para >= {NOTIONAL_MIN:.0f} USDT: {qty_needed}")
        print(f"Notional con esa cantidad: {notional_needed:.4f} USDT")
        print("Aumenta el poder de trading o usa otro símbolo.\n")
        return False

    print(
        f"\n✅ Precheck de poder OK. "
        f"Precio ref: {price:.4f} | minQty: {min_qty} | qty_estimada: {qty_est} | notional_est: {notional_est:.4f}"
    )
    return True


# ==========================================================
# FASE 1 – ESPERAR CRUCE (ENTRADA LONG o SHORT)
# ==========================================================
def esperar_entrada_cruce_fut(
    client: UMFutures,
    symbol: str,
    interval: str,
    wma_entry_len: int,
    sleep_seconds: int,
    side: str,  # "long" o "short"
):
    if side == "long":
        print(f"\n=== [FUTUROS] Buscando ENTRADA LONG en {symbol} ===")
        print(f"Condición: vela cerrada cruza AL ALZA la WMA{wma_entry_len} en {interval}.\n")
    else:
        print(f"\n=== [FUTUROS] Buscando ENTRADA SHORT en {symbol} ===")
        print(f"Condición: vela cerrada cruza A LA BAJA la WMA{wma_entry_len} en {interval}.\n")

    last_closed_close = None

    while True:
        try:
            closes = get_closes_futures(client, symbol, interval, limit=wma_entry_len + 5)
            if len(closes) < wma_entry_len + 3:
                print("Aún no hay suficientes velas para WMA de entrada. Esperando...")
                time.sleep(sleep_seconds)
                continue

            close_prev = closes[-2]
            close_prevprev = closes[-3]

            if last_closed_close is None:
                last_closed_close = close_prev

            if close_prev != last_closed_close:
                wma_prev = wma(closes[:-1], wma_entry_len)
                wma_prevprev = wma(closes[:-2], wma_entry_len)

                prev_state = "above" if close_prev > wma_prev else "below"
                prevprev_state = "above" if close_prevprev > wma_prevprev else "below"

                print(
                    f"[ENTRADA-FUT] Vela cerrada {interval} -> "
                    f"c_-3: {close_prevprev:.4f}, WMA_-3: {wma_prevprev:.4f}, "
                    f"c_-2: {close_prev:.4f}, WMA_-2: {wma_prev:.4f}, "
                    f"estados: {prevprev_state} -> {prev_state}"
                )

                # LONG: cruce alcista (below -> above)
                if side == "long" and prevprev_state == "below" and prev_state == "above":
                    print("\n✅ [FUTUROS] Señal de ENTRADA LONG detectada (cruce alcista WMA de ENTRADA).")
                    ticker = client.ticker_price(symbol=symbol)
                    current_price = float(ticker["price"])
                    return current_price

                # SHORT: cruce bajista (above -> below)
                if side == "short" and prevprev_state == "above" and prev_state == "below":
                    print("\n✅ [FUTUROS] Señal de ENTRADA SHORT detectada (cruce bajista WMA de ENTRADA).")
                    ticker = client.ticker_price(symbol=symbol)
                    current_price = float(ticker["price"])
                    return current_price

                last_closed_close = close_prev

            time.sleep(sleep_seconds)

        except KeyboardInterrupt:
            print("\nBot detenido manualmente durante la fase de entrada.")
            return None
        except Exception as e:
            print(f"Error durante la fase de entrada (Futuros): {e}")
            time.sleep(sleep_seconds)


# ==========================================================
# POSICIÓN ACTUAL / CIERRE MANUAL
# ==========================================================
def get_current_position(client: UMFutures, symbol: str):
    try:
        resp = client.get_position_risk(symbol=symbol)
        for p in resp:
            amt = float(p.get("positionAmt", "0"))
            if abs(amt) > 0:
                return p
        return None
    except Exception as e:
        print(f"Error obteniendo posición actual: {e}")
        return None


def mostrar_posicion_actual(client: UMFutures, symbol: str):
    pos = get_current_position(client, symbol)
    if not pos:
        print(f"\nℹ️ No hay posición abierta en {symbol}.")
        return

    amt = float(pos["positionAmt"])
    side = "LONG" if amt > 0 else "SHORT"
    entry = float(pos["entryPrice"])
    mark = float(pos["markPrice"])
    lev = float(pos["leverage"])
    upnl = float(pos["unRealizedProfit"])

    print("\n=== POSICIÓN ACTUAL ===")
    print(f"Símbolo:        {symbol}")
    print(f"Lado:           {side}")
    print(f"Cantidad:       {amt}")
    print(f"Precio entrada: {entry}")
    print(f"Precio mark:    {mark}")
    print(f"Leverage:       {lev}x")
    print(f"uPnL:           {upnl} USDT")
    print("========================\n")


def cerrar_posicion_market(client: UMFutures, symbol: str, simular: bool):
    pos = get_current_position(client, symbol)
    if not pos:
        print(f"\nℹ️ No hay posición abierta en {symbol} para cerrar.")
        return

    amt = float(pos["positionAmt"])
    if amt == 0:
        print(f"\nℹ️ No hay cantidad abierta en {symbol}.")
        return

    side = "SELL" if amt > 0 else "BUY"
    qty = abs(amt)
    qty_str = format_quantity(qty)

    print("\n=== CIERRE MANUAL DE POSICIÓN ===")
    print(f"Símbolo:  {symbol}")
    print(f"Lado:     {'LONG' if amt > 0 else 'SHORT'}")
    print(f"Orden:    {side} {qty_str} (MARKET)")
    print(f"Modo:     {'SIMULACIÓN' if simular else 'REAL'}\n")

    if simular:
        print("SIMULACIÓN: no se envió orden real de cierre.\n")
        return

    try:
        resp = client.new_order(symbol=symbol, side=side, type="MARKET", quantity=qty_str)
        print("✅ Orden de cierre enviada. Respuesta de Binance:")
        print(resp)
    except Exception as e:
        print(f"❌ Error al cerrar la posición: {e}")


# ==========================================================
# FASE 2 – TRAILING STOP FUTUROS (LONG o SHORT) + FRENO
# ==========================================================
def ejecutar_trailing_stop_futuros(
    client: UMFutures,
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
    entry_order_id: int | None = None,
):
    last_state = None
    last_closed_close = None

    # Para medir stop observado
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

    # === Balance inicial en FUTUROS (para comisiones y P&L real) ===
    if not simular:
        balance_inicial_futuros = get_futures_usdt_balance(client)
    else:
        balance_inicial_futuros = entry_margin_usdt

    # === FRENO DE EMERGENCIA (MVP: cálculo + log, sin orden real) ===
    emergency_stop_price = None
    emergency_mode = "none"

    try:
        closes_for_freno = get_closes_futures(client, symbol, interval, limit=max(250, wma_stop_len + 5))
        wma34 = wma(closes_for_freno, 34)
        wma89 = wma(closes_for_freno, 89)
        if wma34 is not None and wma89 is not None:
            diff = abs(wma89 - wma34)
            if side == "long":
                emergency_stop_price = entry_exec_price - diff
            else:
                emergency_stop_price = entry_exec_price + diff
            emergency_mode = "static"
            print(
                f"[FRENO EMERGENCIA] WMA89 - WMA34 = {diff:.2f}. "
                f"Stop estático calculado en: {emergency_stop_price:.2f}"
            )
        else:
            print("[FRENO EMERGENCIA] No hay suficientes velas para calcular WMA34/WMA89. Freno desactivado por ahora.")
    except Exception as e:
        print(f"[FRENO EMERGENCIA] Error calculando freno estático: {e}")

    # Para futura aceleración/dinámica con WMA233 (placeholder)
    last_89_vs_233_state = None

    while True:
        try:
            closes = get_closes_futures(client, symbol, interval, limit=max(wma_stop_len + 3, 240))
            if len(closes) < wma_stop_len + 2:
                print("Aún no hay suficientes velas para WMA de STOP. Esperando...")
                time.sleep(sleep_seconds)
                continue

            wma_current = wma(closes, wma_stop_len)
            wma_prev = wma(closes[:-1], wma_stop_len)

            close_current = closes[-1]
            close_prev = closes[-2]

            # WMA adicionales para lógica futura (aceleración con 89 / 233)
            wma89_curr = wma(closes, 89)
            wma233_curr = wma(closes, 233)

            # Actualizar precios extremos
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

            # Placeholder de cambio a dinámico con WMA233 (sin órdenes reales, solo log)
            if wma89_curr is not None and wma233_curr is not None:
                curr_89_vs_233 = "above" if wma89_curr > wma233_curr else "below"
                if last_89_vs_233_state is None:
                    last_89_vs_233_state = curr_89_vs_233
                else:
                    if emergency_mode == "static" and curr_89_vs_233 != last_89_vs_233_state:
                        emergency_mode = "dynamic233"
                        emergency_stop_price = wma233_curr
                        print(
                            f"[FRENO EMERGENCIA] WMA89 ha cruzado WMA233. "
                            f"Freno pasa a dinámico en WMA233: {emergency_stop_price:.2f}"
                        )
                    last_89_vs_233_state = curr_89_vs_233

            print(
                f"[STOP-PARCIAL FUT] {symbol} {interval} -> "
                f"Close parcial: {close_current:.4f} | "
                f"WMA_STOP{wma_stop_len}: {wma_current:.4f} | "
                f"Estado actual: {current_state} | "
                f"Estado señal: {state_for_signal} | "
                f"Freno: {emergency_mode}"
            )

            if close_prev != last_closed_close:
                print(f"[STOP-CERRADA FUT] Nueva vela {interval} cerrada -> Close definitivo: {close_prev:.4f}")
                last_closed_close = close_prev

            # Cruce de salida según el lado
            if side == "long":
                crossed = last_state == "above" and state_for_signal == "below"   # cruce bajista
            else:
                crossed = last_state == "below" and state_for_signal == "above"   # cruce alcista

            trigger_exit = False
            motivo = ""

            if crossed:
                trigger_exit = True
                if side == "long":
                    motivo = "Cruce bajista (precio cruza por debajo de la WMA de STOP)."
                else:
                    motivo = "Cruce alcista (precio cruza por encima de la WMA de STOP)."

            if trigger_exit:
                exit_price = close_prev if wait_on_close else close_current
                exit_price_used = exit_price
                trade_end_time = time.time()

                sonar_alarma()

                lado_txt = "LONG" if side == "long" else "SHORT"
                print(f"\n=== [FUTUROS] SEÑAL DE SALIDA {lado_txt} DETECTADA (WMA STOP) ===")
                print(f"Motivo:   {motivo}")
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

    # P&L según el lado (BRUTO, sin comisiones)
    if exit_price_used is not None and entry_exec_price is not None:
        if side == "long":
            pnl_bruto_usdt = (exit_price_used - entry_exec_price) * qty_est
        else:  # short
            pnl_bruto_usdt = (entry_exec_price - exit_price_used) * qty_est
    else:
        pnl_bruto_usdt = 0.0

    # Stop observado (retroceso máximo en contra)
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

    # ==== Comisiones ====
    # 1) Intentamos leer por trades (opcional, como referencia)
    total_commission_usdt_trades = 0.0
    if not simular:
        if entry_order_id is not None:
            total_commission_usdt_trades += get_commission_for_order_usdt(
                client=client,
                symbol=symbol,
                base_asset=base_asset,
                order_id=entry_order_id,
                ref_price=entry_exec_price,
            )
        if exit_order_id is not None and exit_price_used is not None:
            total_commission_usdt_trades += get_commission_for_order_usdt(
                client=client,
                symbol=symbol,
                base_asset=base_asset,
                order_id=exit_order_id,
                ref_price=exit_price_used,
            )

    # 2) Cálculo "bueno": comparando balance inicial vs final de FUTUROS
    if not simular:
        balance_final_futuros = get_futures_usdt_balance(client)
        delta_balance = balance_final_futuros - balance_inicial_futuros

        # Comisión ≈ PnL bruto teórico - PnL real
        estimated_commission = pnl_bruto_usdt - delta_balance

        # Limpieza de ruido numérico
        if abs(estimated_commission) < 1e-6:
            estimated_commission = 0.0

        if estimated_commission < 0:
            # Si da negativo por redondeos extraños, lo dejamos en 0
            estimated_commission = 0.0

        total_commission_usdt = estimated_commission
        pnl_neto_usdt = delta_balance
        balance_inicial = balance_inicial_futuros
        balance_final = balance_final_futuros
    else:
        total_commission_usdt = 0.0
        pnl_neto_usdt = pnl_bruto_usdt
        balance_inicial = balance_inicial_futuros
        balance_final = balance_inicial + pnl_neto_usdt

    # P&L porcentual vs margen asignado a la operación
    if entry_margin_usdt != 0:
        pnl_bruto_pct = (pnl_bruto_usdt / entry_margin_usdt) * 100
        pnl_neto_pct = (pnl_neto_usdt / entry_margin_usdt) * 100
    else:
        pnl_bruto_pct = 0.0
        pnl_neto_pct = 0.0

    if stop_pct > 0:
        rr = pnl_bruto_pct / stop_pct
    else:
        rr = None

    # Retorno de la inversión (movimiento del precio en %)
    if exit_price_used is not None and entry_exec_price is not None and entry_exec_price != 0:
        if side == "long":
            retorno_mov_pct = (exit_price_used - entry_exec_price) / entry_exec_price * 100
        else:
            retorno_mov_pct = (entry_exec_price - exit_price_used) / entry_exec_price * 100
    else:
        retorno_mov_pct = 0.0

    # % de aporte al balance (utilidad neta vs balance inicial de Futuros)
    if balance_inicial != 0:
        aporte_balance_pct = (pnl_neto_usdt / balance_inicial) * 100
    else:
        aporte_balance_pct = 0.0

    lado_txt = "LONG" if side == "long" else "SHORT"
    max_lev_disp = get_max_leverage_symbol(client, symbol)
    inversion_apalancada = qty_est * entry_exec_price if entry_exec_price is not None else 0.0

    print(f"========== RESUMEN DE LA OPERACIÓN FUTUROS ({lado_txt} TRAILING) ==========")
    print(f"Apalancamiento máximo disponible:\t{max_lev_disp:.0f}x")
    print(f"Inversión apalancada\t\t\t{inversion_apalancada:.4f}")
    print(f"Balance de cuenta inicial\t\t{balance_inicial:.4f}")
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
    print(f"Comisión\t\t\t\t{total_commission_usdt:.4f}")
    print(f"Utilidad\t\t\t\t{pnl_neto_usdt:.4f}")
    print(f"P&G neto final\t\t\t\t{pnl_neto_usdt:.4f}")
    print(f"Balance de cuenta final\t\t\t{balance_final:.4f}")
    print(f"% de aporte al balance\t\t\t{aporte_balance_pct:.4f}%")
    print(f"Duración operación (min)\t\t{duration_min:.2f}")
    print("==========================================================\n")


# ==========================================================
# ESTRATEGIA LONG (MODULAR)
# ==========================================================
def run_long_strategy(
    client: UMFutures,
    symbol: str,
    base_asset: str,
    simular: bool,
    interval: str,
    sleep_seconds: int,
    wma_entry_len: int,
    wma_stop_len: int,
    wait_on_close: bool,
    balance_usdt: float,
    trading_power: float,
    max_lev: int,
):
    if trading_power <= 0:
        print("❌ No tienes poder de trading disponible. Revisa tu balance de Futuros.")
        return

    poder_usar = float(
        input(
            f"Poder de trading (USDT) que deseas usar en esta entrada LONG (<= {trading_power:.4f}): "
        ).strip()
    )

    if poder_usar <= 0:
        print("❌ El poder de trading debe ser mayor que 0. Cancelando.")
        return

    if poder_usar > trading_power:
        print("❌ No puedes usar más poder de trading del que tienes disponible.")
        return

    continuar = input(
        f"\n¿Activar bot y esperar señal de ENTRADA LONG usando {poder_usar:.4f} USDT de poder? (s/n): "
    ).strip().lower()
    if continuar not in ["s", "si", "sí", "y", "yes"]:
        print("Bot cancelado por el usuario.")
        return

    try:
        ok_poder = precheck_poder_trading(client, symbol, poder_usar)
        if not ok_poder:
            return
    except Exception as e:
        print(f"⚠️ Error en precheck de poder: {e}")
        print("Continuando de todas formas (el lote se validará de nuevo en la entrada)...\n")

    if not simular:
        try:
            print(f"\nConfigurando leverage {max_lev}x para {symbol}...")
            client.change_leverage(symbol=symbol, leverage=max_lev)
        except Exception as e:
            print(f"⚠️ No se pudo cambiar leverage (usará el actual). Error: {e}")

    entry_price_ref = esperar_entrada_cruce_fut(
        client=client,
        symbol=symbol,
        interval=interval,
        wma_entry_len=wma_entry_len,
        sleep_seconds=sleep_seconds,
        side="long",
    )

    if entry_price_ref is None:
        print("No se ejecutó entrada. Saliendo.")
        return

    raw_qty_est = poder_usar / entry_price_ref
    entry_order_id = None

    try:
        min_qty, max_qty, step_size = get_lot_size_filter_futures(client, symbol)
        qty_est = min(raw_qty_est, max_qty)
        qty_est = floor_to_step(qty_est, step_size)

        NOTIONAL_MIN = 100.0
        if qty_est < min_qty:
            notional_min_qty = min_qty * entry_price_ref
            print("\n❌ Tras el cruce, la cantidad queda por debajo del minQty.")
            print(f"Precio entrada ref: {entry_price_ref:.4f}, minQty: {min_qty}, qty_est: {qty_est}")
            print(f"Notional mínimo por minQty: {notional_min_qty:.4f} USDT")
            print("No se abrirá la posición. Ajusta el poder de trading o usa otro símbolo.\n")
            return

        notional_est = qty_est * entry_price_ref
        if notional_est < NOTIONAL_MIN:
            print("\n❌ Tras el cruce, la orden NO alcanza el notional mínimo de Binance Futuros.")
            print(f"Notional estimado: {notional_est:.4f} USDT, mínimo requerido: {NOTIONAL_MIN:.4f} USDT")
            print("No se abrirá la posición. Ajusta el poder de trading o usa otro símbolo.\n")
            return

        qty_str = format_quantity(qty_est)

        print(f"Filtro LOT_SIZE Futuros {symbol} -> minQty={min_qty}, stepSize={step_size}, maxQty={max_qty}")
        print(
            f"[DEBUG] raw_qty_est: {raw_qty_est}, qty_est normalizada: {qty_est}, "
            f"qty_str: {qty_str}, notional_est: {notional_est:.4f}"
        )

    except Exception as e:
        print(f"⚠️ No se pudo obtener LOT_SIZE Futuros. Usando qty estimada sin normalizar: {e}")
        qty_est = raw_qty_est
        qty_str = format_quantity(qty_est)

    print(f"\n[FUTUROS LONG] Señal de entrada LONG activada.")
    print(f"Precio de referencia (ticker): {entry_price_ref:.4f} USDT")
    print(f"Cantidad estimada a abrir:     {qty_str} {base_asset}")
    print(f"Poder de trading usado:        {poder_usar:.4f} USDT")
    print(f"Leverage efectivo (aprox):     {max_lev}x")
    print("Ejecutando APERTURA LONG automáticamente...\n")

    entry_margin_usdt = poder_usar / max_lev if max_lev != 0 else poder_usar
    entry_exec_price = entry_price_ref

    if simular:
        print("SIMULACIÓN: No se envía orden de apertura real.\n")
    else:
        try:
            print("📥 ENVIANDO ORDEN MARKET BUY (LONG FUTUROS)...")
            entry_order = client.new_order(
                symbol=symbol,
                side="BUY",
                type="MARKET",
                quantity=qty_str
            )
            print("Orden de APERTURA LONG enviada. Respuesta de Binance:")
            print(entry_order)
            entry_order_id = entry_order.get("orderId")

            time.sleep(0.5)
            pos = get_current_position(client, symbol)
            if pos:
                amt_pos = float(pos.get("positionAmt", "0"))
                if amt_pos > 0:
                    entry_exec_price = float(pos.get("entryPrice", entry_price_ref))
                    lev_pos = float(pos.get("leverage", max_lev))
                    notional_pos = abs(amt_pos) * entry_exec_price
                    entry_margin_usdt = notional_pos / lev_pos if lev_pos != 0 else entry_margin_usdt
                    qty_est = abs(amt_pos)
                    qty_str = format_quantity(qty_est)
                    print("\n[INFO] Datos reales de la posición LONG tomados de get_position_risk():")
                    print(f"Cantidad real:   {qty_est}")
                    print(f"Precio entrada:  {entry_exec_price}")
                    print(f"Leverage real:   {lev_pos}x")
                    print(f"Margen aprox:    {entry_margin_usdt:.4f} USDT\n")
            else:
                print("\n⚠️ No se pudo leer la posición después de la orden. Se usa precio de referencia.\n")

        except Exception as e:
            print(f"❌ Error enviando orden de apertura LONG en Futuros: {e}")
            return

    print("\n=== Apertura LONG realizada (real o simulada). Iniciando TRAILING WMA STOP... ===\n")

    ejecutar_trailing_stop_futuros(
        client=client,
        symbol=symbol,
        base_asset=base_asset,
        interval=interval,
        sleep_seconds=sleep_seconds,
        wma_stop_len=wma_stop_len,
        wait_on_close=wait_on_close,
        qty_est=qty_est,
        qty_str=qty_str,
        entry_exec_price=entry_exec_price,
        entry_margin_usdt=entry_margin_usdt,
        simular=simular,
        side="long",
        entry_order_id=entry_order_id,
    )


# ==========================================================
# ESTRATEGIA SHORT (MODULAR)
# ==========================================================
def run_short_strategy(
    client: UMFutures,
    symbol: str,
    base_asset: str,
    simular: bool,
    interval: str,
    sleep_seconds: int,
    wma_entry_len: int,
    wma_stop_len: int,
    wait_on_close: bool,
    balance_usdt: float,
    trading_power: float,
    max_lev: int,
):
    if trading_power <= 0:
        print("❌ No tienes poder de trading disponible. Revisa tu balance de Futuros.")
        return

    poder_usar = float(
        input(
            f"Poder de trading (USDT) que deseas usar en esta entrada SHORT (<= {trading_power:.4f}): "
        ).strip()
    )

    if poder_usar <= 0:
        print("❌ El poder de trading debe ser mayor que 0. Cancelando.")
        return

    if poder_usar > trading_power:
        print("❌ No puedes usar más poder de trading del que tienes disponible.")
        return

    continuar = input(
        f"\n¿Activar bot y esperar señal de ENTRADA SHORT usando {poder_usar:.4f} USDT de poder? (s/n): "
    ).strip().lower()
    if continuar not in ["s", "si", "sí", "y", "yes"]:
        print("Bot cancelado por el usuario.")
        return

    try:
        ok_poder = precheck_poder_trading(client, symbol, poder_usar)
        if not ok_poder:
            return
    except Exception as e:
        print(f"⚠️ Error en precheck de poder: {e}")
        print("Continuando de todas formas (el lote se validará de nuevo en la entrada)...\n")

    if not simular:
        try:
            print(f"\nConfigurando leverage {max_lev}x para {symbol}...")
            client.change_leverage(symbol=symbol, leverage=max_lev)
        except Exception as e:
            print(f"⚠️ No se pudo cambiar leverage (usará el actual). Error: {e}")

    entry_price_ref = esperar_entrada_cruce_fut(
        client=client,
        symbol=symbol,
        interval=interval,
        wma_entry_len=wma_entry_len,
        sleep_seconds=sleep_seconds,
        side="short",
    )

    if entry_price_ref is None:
        print("No se ejecutó entrada. Saliendo.")
        return

    raw_qty_est = poder_usar / entry_price_ref
    entry_order_id = None

    try:
        min_qty, max_qty, step_size = get_lot_size_filter_futures(client, symbol)
        qty_est = min(raw_qty_est, max_qty)
        qty_est = floor_to_step(qty_est, step_size)

        NOTIONAL_MIN = 100.0
        if qty_est < min_qty:
            notional_min_qty = min_qty * entry_price_ref
            print("\n❌ Tras el cruce, la cantidad queda por debajo del minQty.")
            print(f"Precio entrada ref: {entry_price_ref:.4f}, minQty: {min_qty}, qty_est: {qty_est}")
            print(f"Notional mínimo por minQty: {notional_min_qty:.4f} USDT")
            print("No se abrirá la posición. Ajusta el poder de trading o usa otro símbolo.\n")
            return

        notional_est = qty_est * entry_price_ref
        if notional_est < NOTIONAL_MIN:
            print("\n❌ Tras el cruce, la orden NO alcanza el notional mínimo de Binance Futuros.")
            print(f"Notional estimado: {notional_est:.4f} USDT, mínimo requerido: {NOTIONAL_MIN:.4f} USDT")
            print("No se abrirá la posición. Ajusta el poder de trading o usa otro símbolo.\n")
            return

        qty_str = format_quantity(qty_est)

        print(f"Filtro LOT_SIZE Futuros {symbol} -> minQty={min_qty}, stepSize={step_size}, maxQty={max_qty}")
        print(
            f"[DEBUG] raw_qty_est: {raw_qty_est}, qty_est normalizada: {qty_est}, "
            f"qty_str: {qty_str}, notional_est: {notional_est:.4f}"
        )

    except Exception as e:
        print(f"⚠️ No se pudo obtener LOT_SIZE Futuros. Usando qty estimada sin normalizar: {e}")
        qty_est = raw_qty_est
        qty_str = format_quantity(qty_est)

    print(f"\n[FUTUROS SHORT] Señal de entrada SHORT activada.")
    print(f"Precio de referencia (ticker): {entry_price_ref:.4f} USDT")
    print(f"Cantidad estimada a abrir:     {qty_str} {base_asset}")
    print(f"Poder de trading usado:        {poder_usar:.4f} USDT")
    print(f"Leverage efectivo (aprox):     {max_lev}x")
    print("Ejecutando APERTURA SHORT automáticamente...\n")

    entry_margin_usdt = poder_usar / max_lev if max_lev != 0 else poder_usar
    entry_exec_price = entry_price_ref

    if simular:
        print("SIMULACIÓN: No se envía orden de apertura real.\n")
    else:
        try:
            print("📥 ENVIANDO ORDEN MARKET SELL (SHORT FUTUROS)...")
            entry_order = client.new_order(
                symbol=symbol,
                side="SELL",
                type="MARKET",
                quantity=qty_str
            )
            print("Orden de APERTURA SHORT enviada. Respuesta de Binance:")
            print(entry_order)
            entry_order_id = entry_order.get("orderId")

            time.sleep(0.5)
            pos = get_current_position(client, symbol)
            if pos:
                amt_pos = float(pos.get("positionAmt", "0"))
                if amt_pos < 0:
                    entry_exec_price = float(pos.get("entryPrice", entry_price_ref))
                    lev_pos = float(pos.get("leverage", max_lev))
                    notional_pos = abs(amt_pos) * entry_exec_price
                    entry_margin_usdt = notional_pos / lev_pos if lev_pos != 0 else entry_margin_usdt
                    qty_est = abs(amt_pos)
                    qty_str = format_quantity(qty_est)
                    print("\n[INFO] Datos reales de la posición SHORT tomados de get_position_risk():")
                    print(f"Cantidad real:   {qty_est}")
                    print(f"Precio entrada:  {entry_exec_price}")
                    print(f"Leverage real:   {lev_pos}x")
                    print(f"Margen aprox:    {entry_margin_usdt:.4f} USDT\n")
            else:
                print("\n⚠️ No se pudo leer la posición después de la orden. Se usa precio de referencia.\n")

        except Exception as e:
            print(f"❌ Error enviando orden de apertura SHORT en Futuros: {e}")
            return

    print("\n=== Apertura SHORT realizada (real o simulada). Iniciando TRAILING WMA STOP... ===\n")

    ejecutar_trailing_stop_futuros(
        client=client,
        symbol=symbol,
        base_asset=base_asset,
        interval=interval,
        sleep_seconds=sleep_seconds,
        wma_stop_len=wma_stop_len,
        wait_on_close=wait_on_close,
        qty_est=qty_est,
        qty_str=qty_str,
        entry_exec_price=entry_exec_price,
        entry_margin_usdt=entry_margin_usdt,
        simular=simular,
        side="short",
        entry_order_id=entry_order_id,
    )


# ==========================================================
# MAIN – ORQUESTADOR
# ==========================================================
def main():
    print("=== Bot Futuros USDT-M – ENTRADA por cruce + CIERRE por WMA STOP (LONG / SHORT) ===")

    client = get_futures_client()

    symbol = input("Símbolo Futuros (ej: BTCUSDT): ").strip().upper() or "BTCUSDT"
    base_asset = symbol.replace("USDT", "")

    sim_input = input("¿Simular sin enviar órdenes reales? (s/n): ").strip().lower() or "s"
    simular = sim_input in ["s", "si", "sí", "y", "yes"]

    interval = input("Marco de tiempo (ej: 1m, 5m, 15m, 1h): ").strip() or "1m"
    sleep_seconds = int(input("Segundos entre chequeos (ej: 15): ").strip() or "15")

    wma_entry_len = int(input("Longitud de WMA de ENTRADA (ej: 89): ").strip() or "89")
    wma_stop_len = int(input("Longitud de WMA de STOP (ej: 34): ").strip() or "34")

    wait_close_input = input("¿Esperar cierre REAL de la vela para el STOP? (true/false): ").strip().lower() or "true"
    wait_on_close = wait_close_input in ["true", "t", "1", "s", "si", "sí", "y", "yes"]

    balance_usdt = get_futures_usdt_balance(client)
    max_lev = get_max_leverage_symbol(client, symbol)
    trading_power = balance_usdt * max_lev

    print("\n=== INFORMACIÓN DE CUENTA (MODO QUANTFURY) ===")
    print(f"Balance disponible USDT (Futuros): {balance_usdt:.4f}")
    print(f"Apalancamiento MÁXIMO para {symbol}: {max_lev}x (fijo en esta versión)")
    print(f"Poder de trading (balance * maxLev): {trading_power:.4f} USDT")
    print("================================================\n")

    side_input = input("¿Estrategia LONG o SHORT? (long/short): ").strip().lower() or "long"
    if side_input not in ["long", "short"]:
        print("Opción de lado no válida. Usa 'long' o 'short'. Saliendo.")
        return

    print("=== MENÚ DE ACCIONES ===")
    print("1) Ver posición actual en este símbolo")
    print("2) Cerrar posición completa (MARKET)")
    print("3) Ejecutar estrategia completa: cruce WMA ENTRADA + apertura + trailing STOP (MODO QUANTFURY)")
    print("4) Asumir que ya hay posición abierta y SOLO ejecutar trailing STOP\n")

    opcion = input("Elige una opción (1/2/3/4): ").strip()

    if opcion == "1":
        mostrar_posicion_actual(client, symbol)
        return

    elif opcion == "2":
        cerrar_posicion_market(client, symbol, simular)
        return

    print("\n=== RESUMEN CONFIGURACIÓN FUTUROS ===")
    print(f"Símbolo:             {symbol}")
    print(f"Lado estrategia:     {side_input.upper()}")
    print(f"Modo:                {'SIMULACIÓN' if simular else 'REAL'}")
    print(f"Intervalo:           {interval}")
    print(f"WMA de ENTRADA:      {wma_entry_len}")
    print(f"WMA de STOP:         {wma_stop_len}")
    print(f"Sleep (segundos):    {sleep_seconds}")
    print(f"Esperar cierre STOP: {wait_on_close}")
    print(f"Apalancamiento usado: {max_lev}x")
    print(f"Balance USDT:        {balance_usdt:.4f}")
    print(f"Poder de trading:    {trading_power:.4f} USDT\n")

    if opcion == "3":
        if side_input == "long":
            run_long_strategy(
                client=client,
                symbol=symbol,
                base_asset=base_asset,
                simular=simular,
                interval=interval,
                sleep_seconds=sleep_seconds,
                wma_entry_len=wma_entry_len,
                wma_stop_len=wma_stop_len,
                wait_on_close=wait_on_close,
                balance_usdt=balance_usdt,
                trading_power=trading_power,
                max_lev=max_lev,
            )
        else:
            run_short_strategy(
                client=client,
                symbol=symbol,
                base_asset=base_asset,
                simular=simular,
                interval=interval,
                sleep_seconds=sleep_seconds,
                wma_entry_len=wma_entry_len,
                wma_stop_len=wma_stop_len,
                wait_on_close=wait_on_close,
                balance_usdt=balance_usdt,
                trading_power=trading_power,
                max_lev=max_lev,
            )

    elif opcion == "4":
        continuar = input("\n¿Iniciar SOLO el trailing STOP sobre una posición ya abierta? (s/n): ").strip().lower()
        if continuar not in ["s", "si", "sí", "y", "yes"]:
            print("Bot cancelado por el usuario.")
            return

        pos = get_current_position(client, symbol)
        if not pos:
            print(f"\n❌ No se encontró una posición abierta en {symbol}. No se puede iniciar trailing.")
            return

        amt = float(pos["positionAmt"])
        if side_input == "long" and amt <= 0:
            print(f"\n❌ La posición no es LONG (amt={amt}). Ajusta el lado o abre una LONG primero.")
            return
        if side_input == "short" and amt >= 0:
            print(f"\n❌ La posición no es SHORT (amt={amt}). Ajusta el lado o abre una SHORT primero.")
            return

        entry_exec_price = float(pos["entryPrice"])
        lev = float(pos["leverage"])
        notional = abs(amt) * entry_exec_price
        entry_margin_usdt = notional / lev if lev != 0 else notional

        qty_est = abs(amt)
        qty_str = format_quantity(qty_est)

        lado_txt = "LONG" if side_input == "long" else "SHORT"
        print("\n=== TRAILING SOLO SOBRE POSICIÓN EXISTENTE ===")
        print(f"Símbolo:        {symbol}")
        print(f"Cantidad {lado_txt}:  {qty_est}")
        print(f"Precio entrada: {entry_exec_price}")
        print(f"Leverage:       {lev}x")
        print(f"Margen aprox:   {entry_margin_usdt:.4f} USDT")
        print("Iniciando trailing WMA STOP solamente...\n")

        ejecutar_trailing_stop_futuros(
            client=client,
            symbol=symbol,
            base_asset=base_asset,
            interval=interval,
            sleep_seconds=sleep_seconds,
            wma_stop_len=wma_stop_len,
            wait_on_close=wait_on_close,
            qty_est=qty_est,
            qty_str=qty_str,
            entry_exec_price=entry_exec_price,
            entry_margin_usdt=entry_margin_usdt,
            simular=simular,
            side=side_input,
            entry_order_id=None,
        )

    else:
        print("Opción no válida. Saliendo.")


if __name__ == "__main__":
    main()