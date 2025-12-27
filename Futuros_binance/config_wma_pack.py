WMA_POLLITA_LEN = 34
WMA_CELESTE_LEN = 55
WMA_DORADA_LEN = 89
WMA_ROSADA_LEN = 144
WMA_CARMESI_LEN = 233
WMA_BLANCA_LEN = 377
WMA_LIMA_LEN = 610
WMA_CAMALEONA_LEN = 987
WMA_MORADA_LEN = 1597

WMA_PACK_ORDER = [
    ("Pollita", WMA_POLLITA_LEN),
    ("Celeste", WMA_CELESTE_LEN),
    ("Dorada", WMA_DORADA_LEN),
    ("Rosada", WMA_ROSADA_LEN),
    ("Carmesí", WMA_CARMESI_LEN),
    ("Blanca", WMA_BLANCA_LEN),
    ("Lima", WMA_LIMA_LEN),
    ("Camaleona", WMA_CAMALEONA_LEN),
    ("Morada", WMA_MORADA_LEN),
]

MAX_WMA_PACK_LEN = max(length for _, length in WMA_PACK_ORDER)

WMA_FIB_LENGTHS = [length for _, length in WMA_PACK_ORDER]

WMA_COLORS = {length: name for name, length in WMA_PACK_ORDER}


def wma_name_from_len(length: int) -> str:
    for name, len_val in WMA_PACK_ORDER:
        if len_val == length:
            return name
    return f"WMA {length}"
