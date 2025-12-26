from infra_futuros import wma

WMA_POLLITA = 34
WMA_CELESTE = 55
WMA_DORADA = 89


def _pick_nearest_wma(price: float, wmas: list[tuple[str, int, float]]):
    candidates = []
    for name, length, value in wmas:
        if value is None:
            continue
        dist = abs(price - value)
        candidates.append((dist, length, name, value))

    if not candidates:
        return None, None, None

    candidates.sort(key=lambda x: (x[0], x[1]))
    _, length, name, value = candidates[0]
    return name, length, value


def get_trailing_reference(side: str, price: float, closes: list[float]) -> dict:
    """
    Devuelve la WMA de referencia a usar como trailing.
    No envía órdenes ni mantiene estado.
    """
    wma_pollita = wma(closes, WMA_POLLITA)
    wma_celeste = wma(closes, WMA_CELESTE)
    wma_dorada = wma(closes, WMA_DORADA)

    name, length, value = _pick_nearest_wma(
        price,
        [
            ("pollita", WMA_POLLITA, wma_pollita),
            ("celeste", WMA_CELESTE, wma_celeste),
            ("dorada", WMA_DORADA, wma_dorada),
        ],
    )

    return {
        "trailing_name": name,
        "trailing_len": length,
        "trailing_value": value,
    }
