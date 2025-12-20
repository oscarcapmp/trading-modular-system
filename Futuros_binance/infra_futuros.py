import math
import os
import platform
import time

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


def get_hlc_futures(client: UMFutures, symbol: str, interval: str, limit: int):
    """Obtiene High, Low y Close de velas de Futuros."""
    klines = client.klines(symbol=symbol, interval=interval, limit=limit)
    highs = [float(k[2]) for k in klines]
    lows = [float(k[3]) for k in klines]
    closes = [float(k[4]) for k in klines]
    return highs, lows, closes


def atr_sma(highs, lows, closes, length: int = 14):
    """
    ATR simple (SMA) usando True Range clásico.
    Devuelve None si no hay suficientes datos.
    """
    if length <= 0:
        return None

    if len(highs) < length + 1 or len(lows) < length + 1 or len(closes) < length + 1:
        return None

    trs = []
    start = len(highs) - length
    for i in range(start, len(highs)):
        high = highs[i]
        low = lows[i]
        prev_close = closes[i - 1]
        tr = max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close),
        )
        trs.append(tr)

    if not trs:
        return None

    return sum(trs) / len(trs)


def atr(highs, lows, closes, length: int):
    """
    ATR simple (SMA) usando True Range clásico.
    Devuelve None si no hay suficientes datos.
    """
    if length <= 0:
        return None

    if len(highs) < length + 1 or len(lows) < length + 1 or len(closes) < length + 1:
        return None

    trs = []
    start = len(highs) - length
    for i in range(start, len(highs)):
        high = highs[i]
        low = lows[i]
        prev_close = closes[i - 1]
        tr = max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close),
        )
        trs.append(tr)

    if not trs:
        return None

    return sum(trs) / len(trs)


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
    """Balance disponible USDT en Futuros USDT-M."""
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
    Usamos 20x como apalancamiento máximo por defecto.
    """
    return 20


def place_emergency_stop_order(client, symbol: str, side: str, qty_str: str, stop_price: float, is_simulation: bool):
    """
    Coloca una orden STOP_MARKET reduceOnly en Binance como freno nativo.
    Devuelve dict con orderId (None en simulación).
    """
    stop_price_fmt = f"{stop_price:.2f}"
    if is_simulation:
        print(f"[FRENO NATIVO] Simulación: stopPrice calculado {stop_price_fmt}. No se envía orden.")
        return {"orderId": None}

    exit_side = "SELL" if side == "long" else "BUY"
    print("[FRENO NATIVO] Intentando STOP_MARKET", exit_side, "stopPrice", stop_price_fmt, "qty", qty_str)
    try:
        resp = client.new_order(
            symbol=symbol,
            side=exit_side,
            type="STOP_MARKET",
            stopPrice=stop_price_fmt,
            quantity=qty_str,
            reduceOnly=True,
        )
        print("[FRENO NATIVO] OK Binance:", resp)
        try:
            orders = client.get_open_orders(symbol=symbol)
            print("[FRENO NATIVO] Open orders:", orders)
            if not orders:
                print("⚠️ [FRENO NATIVO] WARNING: STOP_MARKET no aparece en órdenes abiertas.")
        except Exception as e:
            print(f"⚠️ [FRENO NATIVO] No se pudieron leer open_orders: {e}")
        return resp
    except Exception as e:
        print("[FRENO NATIVO] ERROR Binance:", e)
        return {"orderId": None}


def cancel_order_safe(client, symbol: str, order_id):
    if order_id is None:
        return
    try:
        client.cancel_order(symbol=symbol, orderId=order_id)
        print(f"[FRENO NATIVO] Orden {order_id} cancelada.")
    except Exception as e:
        print(f"⚠️ No se pudo cancelar orden {order_id}: {e}")


def cancel_all_open_orders_symbol(client, symbol: str):
    try:
        open_orders = client.get_open_orders(symbol=symbol)
    except Exception as e:
        print(f"⚠️ No se pudieron leer órdenes abiertas para {symbol}: {e}")
        return

    if not open_orders:
        return

    for o in open_orders:
        oid = o.get("orderId")
        try:
            client.cancel_order(symbol=symbol, orderId=oid)
            print(f"[CANCEL ALL] Orden {oid} cancelada.")
        except Exception as e:
            print(f"⚠️ No se pudo cancelar orden {oid}: {e}")


def wait_until_flat_and_no_orders(client, symbol: str, timeout_sec: float = 10, poll: float = 0.25) -> bool:
    """
    Espera a que no haya posición abierta ni órdenes pendientes para el símbolo.
    """
    end_time = time.time() + timeout_sec
    while time.time() < end_time:
        try:
            pos_list = client.get_position_risk(symbol=symbol)
            position_amt = 0.0
            for p in pos_list:
                position_amt = float(p.get("positionAmt", "0") or 0.0)
                break
            has_pos = abs(position_amt) > 0

            open_orders = client.get_open_orders(symbol=symbol)
            has_orders = len(open_orders) > 0

            if not has_pos and not has_orders:
                print("[CHECK] Sin posición y sin órdenes abiertas.")
                return True
        except Exception as e:
            print(f"⚠️ Error revisando estado plano: {e}")
            break

        time.sleep(poll)

    print("⚠️ Timeout esperando quedar plano y sin órdenes abiertas.")
    return False


# ==========================================================
# COMISIONES: LECTURA DESDE TRADES (NO USADA AHORA, PERO DISPONIBLE)
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
    (Actualmente NO se usa, dejamos la función por si la quieres en otra versión.)
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
