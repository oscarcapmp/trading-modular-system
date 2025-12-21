try:
    from infra_futuros import wma
except ImportError:
    from Futuros_binance.infra_futuros import wma

WMA_POLLITA = 34
WMA_CELESTE = 55
WMA_DORADA = 89
WMA_CARMESI = 233
WMA_BLANCA = 377
WMA_LIMA = 610
WMA_CAMALEONA = 987


def init_trailing_state(pct_fase1: float) -> dict:
    pct = max(1.0, min(99.0, pct_fase1))
    return {"pct_fase1": pct, "phase": 1, "fase1_done": False, "latched_phase2": False}


def detectar_cruce(prev_carmesi, prev_blanca, curr_carmesi, curr_blanca) -> bool:
    if None in [prev_carmesi, prev_blanca, curr_carmesi, curr_blanca]:
        return False
    diff_prev = prev_carmesi - prev_blanca
    diff_curr = curr_carmesi - curr_blanca
    return (diff_prev == 0 and diff_curr != 0) or (diff_prev != 0 and diff_curr == 0) or (diff_prev * diff_curr < 0)


def elegir_trailing_fase1(price: float, wma_pollita: float, wma_celeste: float, side: str):
    dist_pollita = abs(price - wma_pollita) if wma_pollita is not None else -1
    dist_celeste = abs(price - wma_celeste) if wma_celeste is not None else -1

    if dist_pollita > dist_celeste:
        return "pollita", wma_pollita, dist_pollita, dist_celeste
    if dist_celeste > dist_pollita:
        return "celeste", wma_celeste, dist_pollita, dist_celeste

    candidates = []
    if wma_pollita is not None:
        candidates.append(("pollita", wma_pollita))
    if wma_celeste is not None:
        candidates.append(("celeste", wma_celeste))
    if not candidates:
        return None, None, dist_pollita, dist_celeste

    if side == "long":
        chosen = min(candidates, key=lambda x: x[1])
    else:
        chosen = max(candidates, key=lambda x: x[1])
    return chosen[0], chosen[1], dist_pollita, dist_celeste


def stop_hit(price: float, trailing_wma: float, side: str) -> bool:
    if trailing_wma is None or price is None:
        return False
    return price <= trailing_wma if side == "long" else price >= trailing_wma


def update_trailing(state: dict, side: str, price: float, wmas: dict, wmas_prev: dict):
    phase = state.get("phase", 1)
    fase1_done = state.get("fase1_done", False)
    pct_fase1 = state.get("pct_fase1", 50.0)
    latched_phase2 = state.get("latched_phase2", False)

    cross = detectar_cruce(
        wmas_prev.get("carmesi"),
        wmas_prev.get("blanca"),
        wmas.get("carmesi"),
        wmas.get("blanca"),
    )

    if cross or latched_phase2:
        phase = 2
        latched_phase2 = True

    if phase == 2:
        trailing_name = "dorada"
        trailing_val = wmas.get("dorada")
        trailing_len = WMA_DORADA
        action = "close_all" if stop_hit(price, trailing_val, side) else "none"
        decision = {
            "phase": 2,
            "trailing_name": trailing_name,
            "trailing_len": trailing_len,
            "trailing_value": trailing_val,
            "action": action,
            "pct": 1.0,
            "cross_233_377": cross,
            "dist_pollita": abs(price - wmas.get("pollita")) if wmas.get("pollita") is not None else -1,
            "dist_celeste": abs(price - wmas.get("celeste")) if wmas.get("celeste") is not None else -1,
        }
        return {"phase": phase, "fase1_done": fase1_done, "pct_fase1": pct_fase1, "latched_phase2": latched_phase2}, decision

    trailing_name, trailing_val, dist_pollita, dist_celeste = elegir_trailing_fase1(
        price, wmas.get("pollita"), wmas.get("celeste"), side
    )
    action = "none"
    pct = pct_fase1 / 100.0
    if stop_hit(price, trailing_val, side):
        if not fase1_done:
            action = "sell_partial"
            fase1_done = True
        else:
            action = "none"

    decision = {
        "phase": 1,
        "trailing_name": trailing_name,
        "trailing_len": WMA_POLLITA if trailing_name == "pollita" else WMA_CELESTE if trailing_name == "celeste" else None,
        "trailing_value": trailing_val,
        "action": action,
        "pct": pct,
        "cross_233_377": cross,
        "dist_pollita": dist_pollita,
        "dist_celeste": dist_celeste,
    }
    return {"phase": phase, "fase1_done": fase1_done, "pct_fase1": pct_fase1, "latched_phase2": latched_phase2}, decision


def calcular_wmas_trailing(closes):
    return {
        "pollita": wma(closes, WMA_POLLITA),
        "celeste": wma(closes, WMA_CELESTE),
        "dorada": wma(closes, WMA_DORADA),
        "carmesi": wma(closes, WMA_CARMESI),
        "blanca": wma(closes, WMA_BLANCA),
        "lima": wma(closes, WMA_LIMA),
        "camaleona": wma(closes, WMA_CAMALEONA),
    }


def calcular_wmas_trailing_prev(closes):
    prev = closes[:-1]
    return calcular_wmas_trailing(prev) if len(prev) else {
        "pollita": None,
        "celeste": None,
        "dorada": None,
        "carmesi": None,
        "blanca": None,
        "lima": None,
        "camaleona": None,
    }
