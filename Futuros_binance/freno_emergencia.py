from __future__ import annotations

from infra_futuros import atr, get_hlc_futures, wma


def compute_freno_emergencia_stop_level(
    client,
    symbol: str,
    interval: str,
    side: str,
    atr_len: int = 14,
    atr_mult: float = 1.5,
) -> dict:
    """
    Calcula una sola vez el nivel del freno de emergencia basado en ATR + WMA34.
    No envía órdenes ni imprime logs verbosos.
    """
    try:
        highs, lows, closes = get_hlc_futures(client, symbol, interval, limit=max(atr_len + 40, 60))
        if len(closes) < atr_len + 1:
            return {"stop_level": None, "atr": None, "wma34": None}

        wma34 = wma(closes, 34)
        atr_val = atr(highs, lows, closes, atr_len)

        if wma34 is None or atr_val is None:
            return {"stop_level": None, "atr": atr_val, "wma34": wma34}

        if side == "long":
            stop_level = wma34 - atr_mult * atr_val
        else:
            stop_level = wma34 + atr_mult * atr_val

        return {"stop_level": stop_level, "atr": atr_val, "wma34": wma34}
    except Exception:
        return {"stop_level": None, "atr": None, "wma34": None}
