from config_wma_pack import MAX_WMA_PACK_LEN, wma_name_from_len
from indicators.wma_pack import calc_wma_pack, check_wma_alignment
from infra_futuros import (
    format_quantity,
    get_closes_futures,
    get_futures_client,
    get_futures_usdt_balance,
    get_max_leverage_symbol,
)
from operacion import (
    cerrar_posicion_market,
    get_current_position,
    mostrar_posicion_actual,
    run_long_strategy,
    run_short_strategy,
)
from tacticas_salida import tactica_salida_trailing_stop_wma


def _leer_bool(prompt: str, default: bool = False) -> bool:
    val = input(prompt).strip().lower()
    if val == "":
        return default
    return val in ["s", "si", "sí", "y", "yes", "true", "t", "1"]


def _leer_int(prompt: str, default: int) -> int:
    val = input(prompt).strip()
    if val == "":
        return default
    try:
        return int(val)
    except ValueError:
        return default


def _leer_float(prompt: str, default: float) -> float:
    val = input(prompt).strip()
    if val == "":
        return default
    try:
        return float(val)
    except ValueError:
        return default


def report_wma_pack_alignment(client, symbol: str, interval: str, side: str):
    try:
        closes = get_closes_futures(client, symbol, interval, limit=MAX_WMA_PACK_LEN + 2)
    except Exception as e:
        print(f"⚠️ No se pudieron leer cierres para WMA Pack: {e}")
        return False

    wma_values = calc_wma_pack(closes)
    _, _, msg = check_wma_alignment(wma_values, side=side)
    print(msg)
    return True


def menu_principal() -> str:
    print("\n¿QUÉ QUIERES HACER?")
    print("1) Iniciar una NUEVA operación")
    print("2) Gestionar una posición YA ABIERTA")
    print("3) Gestión manual (ver / cerrar posición)")
    print("4) Salir")
    return input("Elige una opción (1/2/3/4): ").strip()


def flujo_nueva_operacion(client):
    symbol = input("Símbolo Futuros (ej: BTCUSDT): ").strip().upper() or "BTCUSDT"
    side_input = input("¿Estrategia LONG o SHORT? (long/short): ").strip().lower() or "long"
    if side_input not in ["long", "short"]:
        print("Opción de lado no válida. Usa 'long' o 'short'. Saliendo.")
        return
    base_asset = symbol.replace("USDT", "")

    simular = _leer_bool("¿Simular sin enviar órdenes reales? (s/n) [s]: ", default=True)
    interval = input("Marco de tiempo (ej: 1m, 5m, 15m, 1h): ").strip() or "1m"
    sleep_seconds = _leer_int("Segundos entre chequeos (ej: 15): ", default=15)

    wma_entry_len = _leer_int(
        "WMA de ENTRADA (ej: 89, o 0 para entrar a MARKET inmediato): ",
        default=89,
    )
    print("\nReferencia de STOP:")
    print("1) WMA fija")
    print("2) Trailing dinámico (escalera Fibonacci)")
    salida_opcion = input("Elige una opción (1/2): ").strip()
    trailing_ref_mode = "dynamic" if salida_opcion == "2" else "fixed"

    if trailing_ref_mode == "fixed":
        wma_stop_len = _leer_int("Longitud de WMA de STOP (ej: 144): ", default=144)
        if wma_stop_len <= 0:
            print("WMA de STOP inválida. Cancelando nueva operación.")
            return
    else:
        wma_stop_len = None

    print("\nRegla del STOP:")
    print("1) Espejo entrada (buffer+breakout 2 velas) [defecto]")
    print("2) Cruce inmediato (clásico)")
    stop_rule_opcion = input("Elige una opción (1/2): ").strip()
    stop_rule_mode = "cross" if stop_rule_opcion == "2" else "breakout"

    wait_on_close = _leer_bool("¿Esperar cierre REAL de la vela para el STOP? (true/false) [true]: ", default=True)

    if wma_entry_len == 0:
        print("Entrada MARKET inmediata (sin táctica de cruce).")

    balance_usdt = get_futures_usdt_balance(client)
    max_lev = get_max_leverage_symbol(client, symbol)
    trading_power = balance_usdt * max_lev

    report_wma_pack_alignment(client, symbol, interval, side_input)

    print("\n=== RESUMEN CONFIGURACIÓN FUTUROS ===")
    print(f"Símbolo:             {symbol}")
    print(f"Lado estrategia:     {side_input.upper()}")
    print(f"Modo:                {'SIMULACIÓN' if simular else 'REAL'}")
    print(f"Intervalo:           {interval}")
    print(f"WMA de ENTRADA:      {wma_entry_len}")
    if trailing_ref_mode == "dynamic":
        print("Referencia STOP:     Trailing dinámico (escalera Fibonacci)")
        print("WMA de STOP:        Automática")
    else:
        nombre_wma_stop = wma_name_from_len(wma_stop_len)
        print("Referencia STOP:     WMA fija")
        print(f"WMA de STOP:        {wma_stop_len} ({nombre_wma_stop})")
    print(f"Regla STOP:          {'Cruce inmediato (clásico)' if stop_rule_mode == 'cross' else 'Espejo entrada (buffer+breakout 2 velas)'}")
    print("Freno emergencia:    SIEMPRE ACTIVO (ATR+WMA34, cierre MARKET)")
    print(f"Sleep (segundos):   {sleep_seconds}")
    print(f"Esperar cierre STOP:{wait_on_close}")
    print(f"Apalancamiento max: {max_lev}x")
    print(f"Balance USDT:       {balance_usdt:.4f}")
    print(f"Poder de trading:   {trading_power:.4f} USDT\n")

    if side_input == "long":
        run_long_strategy(
            client=client,
            symbol=symbol,
            base_asset=base_asset,
            simular=simular,
            interval=interval,
            sleep_seconds=sleep_seconds,
            wma_entry_len=wma_entry_len,
            wma_stop_len=wma_stop_len,
            trailing_ref_mode=trailing_ref_mode,
            stop_rule_mode=stop_rule_mode,
            wait_on_close=wait_on_close,
            balance_usdt=balance_usdt,
            trading_power=trading_power,
            max_lev=max_lev,
        )
    else:
        run_short_strategy(
            client=client,
            symbol=symbol,
            base_asset=base_asset,
            simular=simular,
            interval=interval,
            sleep_seconds=sleep_seconds,
            wma_entry_len=wma_entry_len,
            wma_stop_len=wma_stop_len,
            trailing_ref_mode=trailing_ref_mode,
            stop_rule_mode=stop_rule_mode,
            wait_on_close=wait_on_close,
            balance_usdt=balance_usdt,
            trading_power=trading_power,
            max_lev=max_lev,
        )


def _leer_posicion_abierta(client, symbol: str):
    pos = get_current_position(client, symbol)
    if not pos:
        return None

    try:
        amt = float(pos.get("positionAmt", "0"))
        if amt == 0:
            return None
    except Exception:
        return None

    entry_exec_price = float(pos.get("entryPrice", "0") or 0)
    lev = float(pos.get("leverage", "0") or 0)
    notional = abs(amt) * entry_exec_price
    entry_margin_usdt = notional / lev if lev != 0 else notional

    side = "long" if amt > 0 else "short"
    qty_est = abs(amt)
    qty_str = format_quantity(qty_est)

    return {
        "side": side,
        "qty_est": qty_est,
        "qty_str": qty_str,
        "entry_exec_price": entry_exec_price,
        "entry_margin_usdt": entry_margin_usdt,
        "leverage": lev,
    }


def flujo_posicion_abierta(client):
    symbol = input("Símbolo Futuros (ej: BTCUSDT): ").strip().upper() or "BTCUSDT"
    base_asset = symbol.replace("USDT", "")

    pos_info = _leer_posicion_abierta(client, symbol)
    if not pos_info:
        print(f"\n❌ No se encontró una posición abierta en {symbol}. Volviendo al menú principal.")
        return

    print("\n=== POSICIÓN DETECTADA ===")
    print(f"Símbolo:        {symbol}")
    print(f"Lado:           {pos_info['side'].upper()}")
    print(f"Cantidad:       {pos_info['qty_est']}")
    print(f"Precio entrada: {pos_info['entry_exec_price']}")
    print(f"Leverage:       {pos_info['leverage']}x")
    print(f"Margen aprox:   {pos_info['entry_margin_usdt']:.4f} USDT\n")

    simular = _leer_bool("¿Simular sin enviar órdenes reales? (s/n) [s]: ", default=True)
    interval = input("Marco de tiempo (ej: 1m, 5m, 15m, 1h): ").strip() or "1m"
    sleep_seconds = _leer_int("Segundos entre chequeos (ej: 15): ", default=15)

    print("\nReferencia de STOP:")
    print("1) WMA fija")
    print("2) Trailing dinámico (escalera Fibonacci)")
    salida_opcion = input("Elige una opción (1/2): ").strip()
    trailing_ref_mode = "dynamic" if salida_opcion == "2" else "fixed"

    if trailing_ref_mode == "fixed":
        wma_stop_len = _leer_int("Longitud de WMA de STOP (ej: 144): ", default=144)
        if wma_stop_len <= 0:
            print("WMA de STOP inválida. No se ejecuta gestión sobre la posición.")
            return
    else:
        wma_stop_len = None

    print("\nRegla del STOP:")
    print("1) Espejo entrada (buffer+breakout 2 velas) [defecto]")
    print("2) Cruce inmediato (clásico)")
    stop_rule_opcion = input("Elige una opción (1/2): ").strip()
    stop_rule_mode = "cross" if stop_rule_opcion == "2" else "breakout"

    wait_on_close = _leer_bool("¿Esperar cierre REAL de la vela para el STOP? (true/false) [true]: ", default=True)

    print("\n=== RESUMEN GESTIÓN SOBRE POSICIÓN EXISTENTE ===")
    print(f"Símbolo:             {symbol}")
    print(f"Lado detectado:      {pos_info['side'].upper()}")
    print(f"Modo:                {'SIMULACIÓN' if simular else 'REAL'}")
    print(f"Intervalo:           {interval}")
    if trailing_ref_mode == "dynamic":
        print("Referencia STOP:     Trailing dinámico (escalera Fibonacci)")
        print("WMA de STOP:        Automática")
    else:
        nombre_wma_stop = wma_name_from_len(wma_stop_len)
        print("Referencia STOP:     WMA fija")
        print(f"WMA de STOP:        {wma_stop_len} ({nombre_wma_stop})")
    print(f"Regla STOP:          {'Cruce inmediato (clásico)' if stop_rule_mode == 'cross' else 'Espejo entrada (buffer+breakout 2 velas)'}")
    print("Freno emergencia:    SIEMPRE ACTIVO (ATR+WMA34, cierre MARKET)")
    print(f"Sleep (segundos):   {sleep_seconds}")
    print(f"Esperar cierre STOP:{wait_on_close}\n")

    tactica_salida_trailing_stop_wma(
        client=client,
        symbol=symbol,
        base_asset=base_asset,
        interval=interval,
        sleep_seconds=sleep_seconds,
        trailing_ref_mode=trailing_ref_mode,
        wma_stop_len=wma_stop_len,
        wait_on_close=wait_on_close,
        stop_rule_mode=stop_rule_mode,
        qty_est=pos_info["qty_est"],
        qty_str=pos_info["qty_str"],
        entry_exec_price=pos_info["entry_exec_price"],
        entry_margin_usdt=pos_info["entry_margin_usdt"],
        simular=simular,
        side=pos_info["side"],
        entry_order_id=None,
        balance_inicial_futuros=None,
    )


def flujo_gestion_manual(client):
    symbol = input("Símbolo Futuros (ej: BTCUSDT): ").strip().upper() or "BTCUSDT"
    simular = _leer_bool("¿Simular sin enviar órdenes reales? (s/n) [s]: ", default=True)

    while True:
        print("\nGestión manual:")
        print("1) Ver posición actual")
        print("2) Cerrar posición completa (MARKET)")
        print("3) Volver al menú principal")
        opcion = input("Elige una opción (1/2/3): ").strip()

        if opcion == "1":
            mostrar_posicion_actual(client, symbol)
        elif opcion == "2":
            cerrar_posicion_market(client, symbol, simular)
        elif opcion == "3":
            return
        else:
            print("Opción no válida.")


def main():
    print("=== Bot Futuros USDT-M ===")
    client = get_futures_client()

    while True:
        opcion = menu_principal()

        if opcion == "1":
            flujo_nueva_operacion(client)
        elif opcion == "2":
            flujo_posicion_abierta(client)
        elif opcion == "3":
            flujo_gestion_manual(client)
        elif opcion == "4":
            print("Saliendo del bot.")
            break
        else:
            print("Opción no válida. Intenta de nuevo.")


if __name__ == "__main__":
    main()
