from __future__ import annotations

from config_wma_pack import wma_name_from_len
from infra_futuros import wma

# Ladder restringida para trailing dinámico
TRAILING_WMA_LADDER = [144, 233, 377, 610, 987]


def _has_cross(short_prev: float, long_prev: float, short_cur: float, long_cur: float, is_long: bool) -> bool:
    if None in (short_prev, long_prev, short_cur, long_cur):
        return False
    prev_diff = short_prev - long_prev
    cur_diff = short_cur - long_cur
    return (prev_diff <= 0 < cur_diff) if is_long else (prev_diff >= 0 > cur_diff)


def get_trailing_reference(side: str, closes: list[float]) -> dict:
    """
    Devuelve la WMA de referencia a usar como trailing, basada en cruces Fibonacci.
    No envía órdenes ni mantiene estado.
    """
    side_norm = (side or "long").lower()
    is_long = side_norm != "short"

    if len(closes) < 3:
        return {"trailing_name": None, "trailing_len": None, "trailing_value": None}

    current_wmas = {length: wma(closes, length) for length in TRAILING_WMA_LADDER}
    prev_closes = closes[:-1]
    prev_wmas = {length: wma(prev_closes, length) for length in TRAILING_WMA_LADDER}

    candidates: list[tuple[int, int | None, float | None, str]] = []

    for idx in range(len(TRAILING_WMA_LADDER) - 1):
        a_len = TRAILING_WMA_LADDER[idx]
        b_len = TRAILING_WMA_LADDER[idx + 1]

        if _has_cross(prev_wmas[a_len], prev_wmas[b_len], current_wmas[a_len], current_wmas[b_len], is_long):
            trailing_idx = idx - 1
            trailing_len = TRAILING_WMA_LADDER[trailing_idx] if trailing_idx >= 0 else None
            trailing_value = wma(closes, trailing_len) if trailing_len else None
            reason = f"cruce_{a_len}_{b_len}"
            candidates.append((b_len, trailing_len, trailing_value, reason))

    if not candidates:
        return {"trailing_name": None, "trailing_len": None, "trailing_value": None}

    # Mayor escala = B más grande
    candidates.sort(key=lambda x: x[0], reverse=True)
    _, trailing_len, trailing_value, reason = candidates[0]
    trailing_name = wma_name_from_len(trailing_len) if trailing_len else None

    return {
        "trailing_name": trailing_name,
        "trailing_len": trailing_len,
        "trailing_value": trailing_value,
        "reason": reason,
    }
