from infra_futuros import wma

# Constantes de longitudes
WMA_POLLITA = 34
WMA_CELESTE = 55
WMA_DORADA = 89
WMA_CARMESI = 233
WMA_BLANCA = 377


def detectar_cruce_carmesi_blanca(prev_carmesi, prev_blanca, curr_carmesi, curr_blanca) -> bool:
    """Detecta cualquier cruce entre Carmesí (233) y Blanca (377)."""
    if prev_carmesi is None or prev_blanca is None or curr_carmesi is None or curr_blanca is None:
        return False
    return (prev_carmesi <= prev_blanca and curr_carmesi > curr_blanca) or (
        prev_carmesi >= prev_blanca and curr_carmesi < curr_blanca
    )


def wma_trailing_fase(price: float, wma_pollita: float, wma_celeste: float, wma_dorada: float, fase2: bool, side: str):
    """Devuelve la WMA que actúa como trailing en la fase actual."""
    if fase2:
        return wma_dorada

    # Fase 1: escoger la más lejana entre Pollita y Celeste
    dist_pollita = abs(price - wma_pollita) if wma_pollita is not None else -1
    dist_celeste = abs(price - wma_celeste) if wma_celeste is not None else -1

    if dist_pollita > dist_celeste:
        return wma_pollita
    if dist_celeste > dist_pollita:
        return wma_celeste

    # Empate: preferir conservadora
    if side == "long":
        # menor valor protege más
        candidates = [v for v in [wma_pollita, wma_celeste] if v is not None]
        return min(candidates) if candidates else None
    else:
        # mayor valor protege más
        candidates = [v for v in [wma_pollita, wma_celeste] if v is not None]
        return max(candidates) if candidates else None


def stop_roto(price: float, trailing_wma: float, side: str) -> bool:
    if trailing_wma is None or price is None:
        return False
    if side == "long":
        return price <= trailing_wma
    return price >= trailing_wma


def porcentaje_cierre(fase2: bool, pct_fase1: float) -> float:
    if fase2:
        return 1.0
    pct = pct_fase1 / 100.0
    if pct < 0:
        pct = 0
    if pct > 1:
        pct = 1
    return pct


def calcular_wmas_trailing(closes):
    """Devuelve dict con WMAs necesarios para el trailing dinámico."""
    return {
        "pollita": wma(closes, WMA_POLLITA),
        "celeste": wma(closes, WMA_CELESTE),
        "dorada": wma(closes, WMA_DORADA),
        "carmesi": wma(closes, WMA_CARMESI),
        "blanca": wma(closes, WMA_BLANCA),
    }


def calcular_wmas_trailing_prev(closes):
    prev = closes[:-1]
    return calcular_wmas_trailing(prev) if len(prev) else {
        "pollita": None,
        "celeste": None,
        "dorada": None,
        "carmesi": None,
        "blanca": None,
    }
