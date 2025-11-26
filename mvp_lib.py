# mvp_lib.py
import os
from binance.spot import Spot

def get_client():
    """Crea el cliente Spot de Binance leyendo las variables de entorno."""
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")

    if not api_key or not api_secret:
        raise RuntimeError("Faltan BINANCE_API_KEY o BINANCE_API_SECRET en variables de entorno.")

    client = Spot(api_key=api_key, api_secret=api_secret)
    return client

def get_closes(client: Spot, symbol: str, interval: str, limit: int):
    """Devuelve una lista de cierres de las últimas velas Spot."""
    klines = client.klines(symbol, interval, limit=limit)
    closes = [float(k[4]) for k in klines]  # índice 4 = close
    return closes

def wma(values, length: int):
    """Calcula la WMA (Weighted Moving Average) de 'length' periodos."""
    if len(values) < length:
        return None
    weights = list(range(1, length + 1))
    sub = values[-length:]
    num = sum(v * w for v, w in zip(sub, weights))
    den = sum(weights)
    return num / den
