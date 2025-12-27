from config_wma_pack import MAX_WMA_PACK_LEN, WMA_PACK_ORDER
from indicators.wma_pack import calc_wma_pack
from infra_futuros import get_closes_futures


def validar_orden_wmas(client, symbol: str, interval: str, side: str):
    """
    Valida e imprime el orden de las WMAs según el lado. Solo informa, no altera flujo.
    """
    try:
        closes = get_closes_futures(client, symbol, interval, limit=MAX_WMA_PACK_LEN + 2)
    except Exception as e:
        print(f"⚠️ No se pudieron leer cierres para validar WMAs: {e}")
        return

    wma_values = calc_wma_pack(closes)
    side_norm = (side or "long").lower()
    is_long = side_norm != "short"

    comparator = (lambda a, b: a < b) if is_long else (lambda a, b: a > b)

    pollita_name = WMA_PACK_ORDER[0][0]
    second_name = WMA_PACK_ORDER[1][0] if len(WMA_PACK_ORDER) > 1 else None

    pollita_val = wma_values.get(pollita_name)
    second_val = wma_values.get(second_name) if second_name else None

    if second_name is None or pollita_val is None or second_val is None or not comparator(pollita_val, second_val):
        print("Pollita en desorden.")
        return

    last_ordered = second_name

    for idx in range(1, len(WMA_PACK_ORDER) - 1):
        current_name = WMA_PACK_ORDER[idx][0]
        next_name = WMA_PACK_ORDER[idx + 1][0]

        current_val = wma_values.get(current_name)
        next_val = wma_values.get(next_name)

        if current_val is None or next_val is None or not comparator(current_val, next_val):
            print(f"Ordenada hasta {last_ordered.lower()}")
            return

        last_ordered = next_name

    print("Todas las WMAs ordenadas.")
