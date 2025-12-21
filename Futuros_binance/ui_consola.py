try:
    from formatters import fmt_resumen_config, fmt_resumen_posicion
except ImportError:
    from Futuros_binance.formatters import fmt_resumen_config, fmt_resumen_posicion


def ui_titulo(texto: str):
    print(f"\n=== {texto} ===")


def ui_separador():
    print("-" * 50)


def ui_info(msg: str):
    print(msg)


def ui_warn(msg: str):
    print(f"⚠️ {msg}")


def ui_error(msg: str):
    print(f"❌ {msg}")


def ui_print_resumen_config(cfg: dict):
    print(fmt_resumen_config(cfg))


def ui_print_resumen_posicion(pos: dict | None):
    formatted = fmt_resumen_posicion(pos)
    if formatted:
        print(formatted)


def ui_pedir_opcion(prompt: str, opciones_validas: list[str] | None = None) -> str:
    val = input(prompt).strip()
    if opciones_validas and val not in opciones_validas:
        ui_warn(f"Opción no reconocida: {val}. Opciones válidas: {', '.join(opciones_validas)}")
    return val


def ui_pedir_si_no(prompt: str, default: str | None = None) -> bool:
    val = input(prompt).strip().lower()
    if val == "":
        if default is None:
            return False
        return default.lower() in ["s", "si", "sí", "y", "yes", "true", "t", "1"]
    return val in ["s", "si", "sí", "y", "yes", "true", "t", "1"]


def ui_pedir_int(prompt: str, default: int | None = None, min_value: int | None = None) -> int:
    val = input(prompt).strip()
    if val == "":
        return default if default is not None else 0
    try:
        parsed = int(val)
    except ValueError:
        return default if default is not None else 0
    if min_value is not None and parsed < min_value:
        return default if default is not None else parsed
    return parsed


def ui_pedir_float(prompt: str, default: float | None = None, min_value: float | None = None) -> float:
    val = input(prompt).strip()
    if val == "":
        return default if default is not None else 0.0
    try:
        parsed = float(val)
    except ValueError:
        return default if default is not None else 0.0
    if min_value is not None and parsed < min_value:
        return default if default is not None else parsed
    return parsed
