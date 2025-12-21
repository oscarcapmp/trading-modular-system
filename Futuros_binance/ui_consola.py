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
    ui_titulo("RESUMEN CONFIGURACIÓN FUTUROS")
    print(f"Símbolo:             {cfg.get('symbol')}")
    print(f"Lado estrategia:     {str(cfg.get('side')).upper()}")
    print(f"Modo:                {'SIMULACIÓN' if cfg.get('simular') else 'REAL'}")
    print(f"Intervalo:           {cfg.get('interval')}")
    print(f"WMA de ENTRADA:      {cfg.get('wma_entry_len')}")
    if cfg.get("trailing_dinamico_on"):
        print("Salida:             Trailing dinámico 2 fases")
        print(f"Fase 1 (%):         {cfg.get('pct_fase1')}")
        print("WMA de STOP:        (IGNORADA por trailing dinámico)")
    else:
        print("Salida:             Stop clásico por WMA")
        print(f"WMA de STOP:        {cfg.get('wma_stop_len')}")
    print(f"Freno ATR local:    {'Sí' if cfg.get('emergency_atr_on') else 'No'} (k={cfg.get('atr_mult')})")
    print(f"Sleep (segundos):   {cfg.get('sleep_seconds')}")
    print(f"Esperar cierre STOP:{cfg.get('wait_on_close')}")
    print(f"Apalancamiento max: {cfg.get('max_lev')}x")
    print(f"Balance USDT:       {cfg.get('balance_usdt'):.4f}")
    print(f"Poder de trading:   {cfg.get('trading_power'):.4f} USDT\n")


def ui_print_resumen_posicion(pos: dict | None):
    if not pos:
        return
    ui_titulo("POSICIÓN DETECTADA")
    print(f"Símbolo:        {pos.get('symbol')}")
    print(f"Lado:           {str(pos.get('side')).upper()}")
    print(f"Cantidad:       {pos.get('qty_est')}")
    print(f"Precio entrada: {pos.get('entry_exec_price')}")
    print(f"Leverage:       {pos.get('leverage')}x")
    print(f"Margen aprox:   {pos.get('entry_margin_usdt'):.4f} USDT\n")


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
