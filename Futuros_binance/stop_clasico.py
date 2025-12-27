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
    buffer_ratio: float = 0.17,
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
    price_for_stop = close_prev if wait_on_close else close_current

    # Evaluar pending breakout intravela y latcheado
    if stop_mode == "breakout":
        pending = state.get("pending_breakout")
        if pending:
            current_state = "above" if close_current > trailing_value_current else "below"
            if current_state == pending["reset_state"]:
                state["pending_breakout"] = None
            else:
                trigger = pending["trigger"]
                breakout = low_current <= trigger if pending["side"] == "long" else high_current >= trigger
                if breakout:
                    state["pending_breakout"] = None
                    if new_closed:
                        state["last_closed_close"] = close_prev
                    return state, {
                        "action": "close_all",
                        "reason": "Breakout confirmado con buffer",
                        "exit_price": price_for_stop,
                        "trigger": trigger,
                    }
    else:
        state["pending_breakout"] = None

    if not new_closed:
        return state, {"action": "none"}

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
            "buffer": buffer,
            "reset_state": prevprev_state,
        }
        return state, {
            "action": "none",
            "pending_trigger": trigger,
            "pending_buffer": buffer,
        }

    return state, {"action": "none"}
