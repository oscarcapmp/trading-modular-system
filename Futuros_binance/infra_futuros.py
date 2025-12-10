# infra_futuros.py
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
    """Reproduce un sonido y una voz diciendo 'Stop activado' (en macOS)."""
    if platform.system() == "Darwin":
        os.system('afplay "/System/Library/Sounds/Glass.aiff"')
        time.sleep(3)
        os.system('say -v Victoria "Stop activado"')
    else:
        # En otros sistemas, solo hace beep varias veces.
        for _ in range(5):
            print("\a")
            time.sleep(0.3)


# ==========================================================
# CLIENTE FUTUROS
# ==========================================================
def get_futures_client():
    """Crea el cliente de Binance Futuros USDT-M usando variables de entorno."""
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")
    if not api_key or not api_secret:
        raise RuntimeError("Faltan BINANCE_API_KEY o BINANCE_API_SECRET en variables de entorno.")
    return UMFutures(key=api_key, secret=api_secret)


# ==========================================================
# INDICADORES Y VELAS
# ==========================================================
def wma(values, length: int):
    """Weighted Moving Average simple, con pesos 1..length."""
    if len(values) < length:
        return None
    weights = list(range(1, length + 1))
    sub = values[-length:]
    num = sum(v * w for v, w in zip(sub, weights))
    den = sum(weights)
    return num / den


def get_closes_futuros(client, symbol: str, interval: str, limit: int):
    """Devuelve una lista de precios de cierre para Futuros."""
    klines = client.klines(symbol=symbol, interval=interval, limit=limit)
    closes = [float(k[4]) for k in klines]
    return closes


# ==========================================================
# UTILIDADES DE CANTIDADES / FORMATO / LOT_SIZE
# ==========================================================
def floor_to_step(qty: float, step: float) -> float:
    """Redondea hacia abajo la cantidad al múltiplo más cercano del step."""
    if step <= 0:
        return qty
    return math.floor(qty / step) * step


def format_quantity(qty: float) -> str:
    """Formatea la cantidad quitando ceros y punto sobrante."""
    s = f"{qty:.10f}"
    s = s.rstrip("0").rstrip(".")
    return s


def get_lot_size_filter_futuros(client, symbol: str):
    """Devuelve (min_qty, max_qty, step_size) para Futuros USDT-M."""
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


# ==========================================================
# BALANCE Y APALANCAMIENTO
# ==========================================================
def get_futuros_usdt_balance(client) -> float:
    """Balance disponible USDT en Futuros USDT-M."""
    try:
        balances = client.balance()
        for b in balances:
            if b.get("asset") == "USDT":
                return float(b.get("availableBalance", b.get("balance", "0")))
    except Exception as e:
        print(f"⚠️ No se pudo leer balance de Futuros: {e}")
    return 0.0


def get_max_leverage_symbol(client, symbol: str) -> int:
    """
    En esta versión simple, devolvemos un apalancamiento máximo fijo (20x).
    Más adelante puedes hacerlo dinámico según el símbolo.
    """
    return 20


def precheck_poder_trading(client, symbol: str, poder_usdt: float) -> bool:
    """
    Precheck estilo 'Quantfury':
    - Recibe un poder de trading en USDT
    - Calcula la cantidad estimada
    - Valida minQty y notional mínimo (100 USDT)
    """
    ticker = client.ticker_price(symbol=symbol)
    price = float(ticker["price"])

    min_qty, max_qty, step_size = get_lot_size_filter_futuros(client, symbol)

    raw_qty_est = poder_usdt / price
    qty_est = min(raw_qty_est, max_qty)
    qty_est = floor_to_step(qty_est, step_size)

    # Validar minQty
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

    # Validar NOTIONAL mínimo 100 USDT
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

