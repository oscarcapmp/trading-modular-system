from __future__ import annotations


def init_stop_state() -> dict:
    return {
        "last_state": None,
        "last_closed_close": None,
        "pending_breakout": None,
    }


def eval_stop_clasico_by_wma(
    *,
    side: str,
    close_current: float,
    close_prev: float,
    close_prevprev: float,
    high_current: float,
    low_current: float,
    high_prev: float,
    low_prev: float,
    trailing_value_current: float | None,
    trailing_value_prev: float | None,
    trailing_value_prevprev: float | None,
    wait_on_close: bool,
    stop_rule_mode: str,
    state: dict,
    buffer_ratio: float = 0.10,
) -> tuple[dict, dict]:
    """
    Retorna (new_state, decision)

    decision:
      {"action": "none"} o
      {"action": "close_all", "reason": "...", "exit_price": ...}
    """
    if trailing_value_current is None or trailing_value_prev is None or trailing_value_prevprev is None:
        return state, {"action": "none"}

    stop_mode = (stop_rule_mode or "breakout").lower()
    new_closed = state["last_closed_close"] is None or close_prev != state["last_closed_close"]
    if not new_closed:
        return state, {"action": "none"}

    # Evaluar pending breakout si existe (solo modo breakout)
    if stop_mode == "breakout":
        pending = state.get("pending_breakout")
        if pending:
            candles_checked = pending["candles_checked"] + 1
            trigger = pending["trigger"]
            breakout = low_prev <= trigger if pending["side"] == "long" else high_prev >= trigger

            if breakout:
                exit_price = close_prev if wait_on_close else close_current
                state["pending_breakout"] = None
                state["last_closed_close"] = close_prev
                return state, {
                    "action": "close_all",
                    "reason": "Breakout confirmado con buffer",
                    "exit_price": exit_price,
                    "trigger": trigger,
                }

            if candles_checked >= 2:
                state["pending_breakout"] = None
            else:
                pending["candles_checked"] = candles_checked
                state["pending_breakout"] = pending
    else:
        state["pending_breakout"] = None

    prev_state = "above" if close_prev > trailing_value_prev else "below"
    prevprev_state = "above" if close_prevprev > trailing_value_prevprev else "below"

    state["last_state"] = prev_state
    state["last_closed_close"] = close_prev

    crossed = (
        prevprev_state == "above" and prev_state == "below"
        if side == "long"
        else prevprev_state == "below" and prev_state == "above"
    )

    if stop_mode == "cross":
        if crossed:
            exit_price = close_prev if wait_on_close else close_current
            return state, {
                "action": "close_all",
                "reason": "Cruce directo con WMA",
                "exit_price": exit_price,
            }
        return state, {"action": "none"}

    if crossed:
        rango_cruce = high_prev - low_prev
        buffer = rango_cruce * buffer_ratio
        if side == "long":
            trigger = low_prev - buffer
        else:
            trigger = high_prev + buffer

        state["pending_breakout"] = {
            "side": side,
            "trigger": trigger,
            "candles_checked": 0,
            "buffer": buffer,
        }
        return state, {
            "action": "none",
            "pending_trigger": trigger,
            "pending_buffer": buffer,
        }

    return state, {"action": "none"}
