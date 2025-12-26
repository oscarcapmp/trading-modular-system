from __future__ import annotations


def init_stop_state() -> dict:
    return {"last_state": None, "last_closed_close": None}


def eval_stop_clasico_by_wma(
    *,
    side: str,
    close_current: float,
    close_prev: float,
    trailing_value_current: float | None,
    trailing_value_prev: float | None,
    wait_on_close: bool,
    state: dict,
) -> tuple[dict, dict]:
    """
    Retorna (new_state, decision)

    decision:
      {"action": "none"} o
      {"action": "close_all", "reason": "...", "exit_price": ...}
    """
    if trailing_value_current is None or trailing_value_prev is None:
        return state, {"action": "none"}

    current_state = "above" if close_current > trailing_value_current else "below"
    prev_state = "above" if close_prev > trailing_value_prev else "below"
    state_for_signal = prev_state if wait_on_close else current_state

    if state["last_state"] is None:
        state["last_state"] = state_for_signal
        state["last_closed_close"] = close_prev
        return state, {"action": "none"}

    crossed = (
        state["last_state"] == "above" and state_for_signal == "below"
        if side == "long"
        else state["last_state"] == "below" and state_for_signal == "above"
    )

    exit_price = close_prev if wait_on_close else close_current

    state["last_state"] = state_for_signal
    state["last_closed_close"] = close_prev

    if crossed:
        reason = (
            "Cruce bajista (precio cruza por debajo de la WMA de STOP)."
            if side == "long"
            else "Cruce alcista (precio cruza por encima de la WMA de STOP)."
        )
        return state, {"action": "close_all", "reason": reason, "exit_price": exit_price}

    return state, {"action": "none"}
