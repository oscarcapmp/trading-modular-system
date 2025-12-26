from __future__ import annotations

from infra_futuros import atr, get_hlc_futures, wma


def eval_freno_emergencia(
    client,
    symbol: str,
    interval: str,
    side: str,
    price_for_stop: float,
    atr_len: int = 14,
    atr_mult: float = 1.5,
) -> dict:
    """
    Devuelve un dict con la decisión del freno de emergencia basado en ATR + WMA34.
    No envía órdenes ni imprime logs verbosos.
    """
    try:
        highs, lows, closes = get_hlc_futures(client, symbol, interval, limit=max(atr_len + 40, 60))
        if len(closes) < atr_len + 1:
            return {"action": "none", "stop_level": None, "atr": None, "wma34": None}

        wma34 = wma(closes, 34)
        atr_val = atr(highs, lows, closes, atr_len)

        if wma34 is None or atr_val is None:
            return {"action": "none", "stop_level": None, "atr": atr_val, "wma34": wma34}

        if side == "long":
            stop_level = wma34 - atr_mult * atr_val
            triggered = price_for_stop <= stop_level
        else:
            stop_level = wma34 + atr_mult * atr_val
            triggered = price_for_stop >= stop_level

        if triggered:
            return {
                "action": "close_all",
                "reason": "emergency_atr_wma34",
                "stop_level": stop_level,
                "atr": atr_val,
                "wma34": wma34,
            }

        return {"action": "none", "stop_level": stop_level, "atr": atr_val, "wma34": wma34}
    except Exception:
        return {"action": "none", "stop_level": None, "atr": None, "wma34": None}
