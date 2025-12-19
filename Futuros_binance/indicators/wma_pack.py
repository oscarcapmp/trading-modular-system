from infra_futuros import wma
from config_wma_pack import WMA_PACK_ORDER, MAX_WMA_PACK_LEN


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


def check_wma_alignment(wma_values_dict, custom_order=None):
    """
    Revisa el orden: Pollita < Celeste < Dorada < Carmesí < Blanca < Camaleona.
    Retorna (aligned: bool, broken: list[str], human_message: str)
    """
    order = custom_order if custom_order is not None else WMA_PACK_ORDER
    broken = []

    # Si falta algún valor, se marca como roto.
    for name, _ in order:
        if wma_values_dict.get(name) is None:
            broken.append(name)

    for i in range(len(order) - 1):
        left_name, _ = order[i]
        right_name, _ = order[i + 1]
        left_val = wma_values_dict.get(left_name)
        right_val = wma_values_dict.get(right_name)

        if left_val is None or right_val is None:
            continue

        if not (left_val < right_val):
            broken.extend([left_name, right_name])

    # Dejar únicos en el mismo orden de aparición.
    seen = set()
    broken_unique = []
    for n in broken:
        if n not in seen:
            seen.add(n)
            broken_unique.append(n)

    aligned = len(broken_unique) == 0

    if aligned:
        names_str = " < ".join(name for name, _ in order)
        msg = f"WMAs alineadas ✅: {names_str}"
    else:
        msg = "WMAs NO alineadas ❌: faltan por alinear: " + ", ".join(broken_unique)

    return aligned, broken_unique, msg
