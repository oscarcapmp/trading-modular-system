try:
    from infra_futuros import wma
    from config_wma_pack import WMA_PACK_ORDER
except ImportError:
    from Futuros_binance.infra_futuros import wma
    from Futuros_binance.config_wma_pack import WMA_PACK_ORDER


def calc_wma_pack(closes, custom_order=None):
    """
    Calcula las WMAs nombradas sobre la serie de cierres.
    Devuelve dict nombre -> valor (None si no hay datos suficientes).
    """
    order = custom_order if custom_order is not None else WMA_PACK_ORDER
    values = {}
    for name, length in order:
        values[name] = wma(closes, length)
    return values


def check_wma_alignment(wma_values_dict, side: str = "long", custom_order=None):
    """
    Valida alineación dependiente del lado:
    LONG  -> Pollita < Celeste < Dorada < Carmesí < Blanca < Lima < Camaleona
    SHORT -> Pollita > Celeste > Dorada > Carmesí > Blanca > Lima > Camaleona
    Retorna (aligned: bool, issues: list[str], human_message: str)
    issues incluye tanto WMAs que rompen el orden como las que no tienen datos suficientes.
    """
    order = custom_order if custom_order is not None else WMA_PACK_ORDER
    side_norm = (side or "long").lower()
    is_long = side_norm != "short"

    insufficient = []
    broken = []

    for name, _ in order:
        if wma_values_dict.get(name) is None:
            insufficient.append(name)

    comparator = (lambda a, b: a < b) if is_long else (lambda a, b: a > b)

    for i in range(len(order) - 1):
        left_name, _ = order[i]
        right_name, _ = order[i + 1]
        left_val = wma_values_dict.get(left_name)
        right_val = wma_values_dict.get(right_name)

        if left_val is None or right_val is None:
            continue

        if not comparator(left_val, right_val):
            broken.extend([left_name, right_name])

    def _unique(seq):
        seen = set()
        res = []
        for n in seq:
            if n not in seen:
                seen.add(n)
                res.append(n)
        return res

    broken_unique = _unique(broken)
    insufficient_unique = _unique(insufficient)
    issues_unique = _unique(broken_unique + insufficient_unique)

    aligned = len(issues_unique) == 0

    direction = "<" if is_long else ">"
    expected_chain = f" {direction} ".join(name for name, _ in order)
    status_txt = "alineadas ✅" if aligned else "NO alineadas ❌"

    details_parts = []
    if broken_unique:
        details_parts.append("rompen orden: " + ", ".join(broken_unique))
    if insufficient_unique:
        details_parts.append("datos insuficientes: " + ", ".join(insufficient_unique))

    msg = f"WMAs {status_txt} ({side_norm.upper()}) -> esperado: {expected_chain}"
    if details_parts:
        msg += " | " + " | ".join(details_parts)

    return aligned, issues_unique, msg
