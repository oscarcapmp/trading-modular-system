try:
    from ui_consola import (
        ui_error,
        ui_info,
        ui_pedir_float,
        ui_pedir_int,
        ui_pedir_opcion,
        ui_pedir_si_no,
        ui_print_resumen_config,
        ui_print_resumen_posicion,
        ui_separador,
        ui_titulo,
        ui_warn,
    )
    from config_wma_pack import MAX_WMA_PACK_LEN
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
except ImportError:
    from Futuros_binance.ui_consola import (
        ui_error,
        ui_info,
        ui_pedir_float,
        ui_pedir_int,
        ui_pedir_opcion,
        ui_pedir_si_no,
        ui_print_resumen_config,
        ui_print_resumen_posicion,
        ui_separador,
        ui_titulo,
        ui_warn,
    )
    from Futuros_binance.config_wma_pack import MAX_WMA_PACK_LEN
    from Futuros_binance.indicators.wma_pack import calc_wma_pack, check_wma_alignment
    from Futuros_binance.infra_futuros import (
        format_quantity,
        get_closes_futures,
        get_futures_client,
        get_futures_usdt_balance,
        get_max_leverage_symbol,
    )
    from Futuros_binance.operacion import (
        cerrar_posicion_market,
        get_current_position,
        mostrar_posicion_actual,
        run_long_strategy,
        run_short_strategy,
    )
    from Futuros_binance.tacticas_salida import tactica_salida_trailing_stop_wma


def report_wma_pack_alignment(client, symbol: str, interval: str, side: str):
    try:
        closes = get_closes_futures(client, symbol, interval, limit=MAX_WMA_PACK_LEN + 2)
    except Exception as e:
        ui_warn(f"No se pudieron leer cierres para WMA Pack: {e}")
        return False

    wma_values = calc_wma_pack(closes)
    _, _, msg = check_wma_alignment(wma_values, side=side)
    ui_info(msg)
    return True


def menu_principal() -> str:
    ui_titulo("¿QUÉ QUIERES HACER?")
    ui_info("1) Iniciar una NUEVA operación")
    ui_info("2) Gestionar una posición YA ABIERTA")
    ui_info("3) Gestión manual (ver / cerrar posición)")
    ui_info("4) Salir")
    return ui_pedir_opcion("Elige una opción (1/2/3/4): ", opciones_validas=["1", "2", "3", "4"])


def flujo_nueva_operacion(client):
    symbol = input("Símbolo Futuros (ej: BTCUSDT): ").strip().upper() or "BTCUSDT"
    base_asset = symbol.replace("USDT", "")

    simular = ui_pedir_si_no("¿Simular sin enviar órdenes reales? (s/n) [s]: ", default="s")
    interval = input("Marco de tiempo (ej: 1m, 5m, 15m, 1h): ").strip() or "1m"
    sleep_seconds = ui_pedir_int("Segundos entre chequeos (ej: 15): ", default=15)

    wma_entry_len = ui_pedir_int(
        "WMA de ENTRADA (ej: 89, o 0 para entrar a MARKET inmediato): ",
        default=89,
    )
    ui_info("\nTipo de salida:")
    ui_info("1) Stop clásico por WMA")
    ui_info("2) Trailing dinámico 2 fases")
    salida_opcion = ui_pedir_opcion("Elige una opción (1/2): ", opciones_validas=["1", "2"])
    trailing_dinamico_on = salida_opcion == "2"

    if trailing_dinamico_on:
        wma_stop_len = 0
        pct_fase1 = ui_pedir_float("Porcentaje de cierre en Fase 1 (1-99) [50]: ", default=50.0)
        pct_fase1 = max(1, min(99, pct_fase1))
    else:
        wma_stop_len = ui_pedir_int("Longitud de WMA de STOP (ej: 34): ", default=34)
        if wma_stop_len <= 0:
            ui_error("WMA de STOP inválida. Cancelando nueva operación.")
            return
        pct_fase1 = 50.0

    emergency_atr_on = ui_pedir_si_no(
        "¿Activar freno de emergencia ATR (LOCAL, cierre MARKET)? (s/n) [s]: ",
        default="s",
    )
    atr_mult = ui_pedir_float("Multiplicador k del ATR (ej: 1.5) [1.5]: ", default=1.5)
    if atr_mult <= 0:
        atr_mult = 1.5

    wait_on_close = ui_pedir_si_no("¿Esperar cierre REAL de la vela para el STOP? (true/false) [true]: ", default="s")

    if wma_entry_len == 0:
        ui_info("Entrada MARKET inmediata (sin táctica de cruce).")

    balance_usdt = get_futures_usdt_balance(client)
    max_lev = get_max_leverage_symbol(client, symbol)
    trading_power = balance_usdt * max_lev

    side_input = input("¿Estrategia LONG o SHORT? (long/short): ").strip().lower() or "long"
    if side_input not in ["long", "short"]:
        ui_error("Opción de lado no válida. Usa 'long' o 'short'. Saliendo.")
        return

    report_wma_pack_alignment(client, symbol, interval, side_input)

    ui_print_resumen_config(
        {
            "symbol": symbol,
            "side": side_input,
            "simular": simular,
            "interval": interval,
            "wma_entry_len": wma_entry_len,
            "trailing_dinamico_on": trailing_dinamico_on,
            "pct_fase1": pct_fase1,
            "wma_stop_len": wma_stop_len,
            "emergency_atr_on": emergency_atr_on,
            "atr_mult": atr_mult,
            "sleep_seconds": sleep_seconds,
            "wait_on_close": wait_on_close,
            "max_lev": max_lev,
            "balance_usdt": balance_usdt,
            "trading_power": trading_power,
        }
    )

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
            wait_on_close=wait_on_close,
            emergency_atr_on=emergency_atr_on,
            atr_mult=atr_mult,
            balance_usdt=balance_usdt,
            trading_power=trading_power,
            max_lev=max_lev,
            trailing_dinamico_on=trailing_dinamico_on,
            pct_fase1=pct_fase1,
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
            wait_on_close=wait_on_close,
            emergency_atr_on=emergency_atr_on,
            atr_mult=atr_mult,
            balance_usdt=balance_usdt,
            trading_power=trading_power,
            max_lev=max_lev,
            trailing_dinamico_on=trailing_dinamico_on,
            pct_fase1=pct_fase1,
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
        ui_error(f"No se encontró una posición abierta en {symbol}. Volviendo al menú principal.")
        return

    ui_print_resumen_posicion({**pos_info, "symbol": symbol})

    simular = ui_pedir_si_no("¿Simular sin enviar órdenes reales? (s/n) [s]: ", default="s")
    interval = input("Marco de tiempo (ej: 1m, 5m, 15m, 1h): ").strip() or "1m"
    sleep_seconds = ui_pedir_int("Segundos entre chequeos (ej: 15): ", default=15)

    ui_info("\nTipo de gestión sobre la posición abierta:")
    ui_info("1) Stop clásico por WMA")
    ui_info("2) Trailing dinámico 2 fases")
    salida_opcion = ui_pedir_opcion("Elige una opción (1/2): ", opciones_validas=["1", "2"])
    trailing_dinamico_on = salida_opcion == "2"

    if trailing_dinamico_on:
        wma_stop_len = 0
        pct_fase1 = ui_pedir_float("Porcentaje de cierre en Fase 1 (1-99) [50]: ", default=50.0)
        pct_fase1 = max(1, min(99, pct_fase1))
    else:
        wma_stop_len = ui_pedir_int("Longitud de WMA de STOP (ej: 34): ", default=34)
        if wma_stop_len <= 0:
            ui_error("WMA de STOP inválida. No se ejecuta gestión sobre la posición.")
            return
        pct_fase1 = 50.0

    wait_on_close = ui_pedir_si_no("¿Esperar cierre REAL de la vela para el STOP? (true/false) [true]: ", default="s")
    emergency_atr_on = ui_pedir_si_no(
        "¿Activar freno de emergencia ATR (LOCAL, cierre MARKET)? (s/n) [s]: ",
        default="s",
    )
    atr_mult = ui_pedir_float("Multiplicador k del ATR (ej: 1.5) [1.5]: ", default=1.5)
    if atr_mult <= 0:
        atr_mult = 1.5

    ui_titulo("RESUMEN GESTIÓN SOBRE POSICIÓN EXISTENTE")
    ui_info(f"Símbolo:             {symbol}")
    ui_info(f"Lado detectado:      {pos_info['side'].upper()}")
    ui_info(f"Modo:                {'SIMULACIÓN' if simular else 'REAL'}")
    ui_info(f"Intervalo:           {interval}")
    if trailing_dinamico_on:
        ui_info("Salida:             Trailing dinámico 2 fases")
        ui_info(f"Fase 1 (%):         {pct_fase1}")
        ui_info("WMA de STOP:        (IGNORADA por trailing dinámico)")
    else:
        ui_info("Salida:             Stop clásico por WMA")
        ui_info(f"WMA de STOP:        {wma_stop_len}")
    ui_info(f"Freno ATR local:    {'Sí' if emergency_atr_on else 'No'} (k={atr_mult})")
    ui_info(f"Sleep (segundos):   {sleep_seconds}")
    ui_info(f"Esperar cierre STOP:{wait_on_close}\n")

    tactica_salida_trailing_stop_wma(
        client=client,
        symbol=symbol,
        base_asset=base_asset,
        interval=interval,
        sleep_seconds=sleep_seconds,
        wma_stop_len=wma_stop_len,
        wait_on_close=wait_on_close,
        emergency_atr_on=emergency_atr_on,
        atr_mult=atr_mult,
        qty_est=pos_info["qty_est"],
        qty_str=pos_info["qty_str"],
        entry_exec_price=pos_info["entry_exec_price"],
        entry_margin_usdt=pos_info["entry_margin_usdt"],
        simular=simular,
        side=pos_info["side"],
        entry_order_id=None,
        balance_inicial_futuros=None,
        trailing_dinamico_on=trailing_dinamico_on,
        pct_fase1=pct_fase1,
    )


def flujo_gestion_manual(client):
    symbol = input("Símbolo Futuros (ej: BTCUSDT): ").strip().upper() or "BTCUSDT"
    simular = ui_pedir_si_no("¿Simular sin enviar órdenes reales? (s/n) [s]: ", default="s")

    while True:
        ui_info("\nGestión manual:")
        ui_info("1) Ver posición actual")
        ui_info("2) Cerrar posición completa (MARKET)")
        ui_info("3) Volver al menú principal")
        opcion = ui_pedir_opcion("Elige una opción (1/2/3): ", opciones_validas=["1", "2", "3"])

        if opcion == "1":
            mostrar_posicion_actual(client, symbol)
        elif opcion == "2":
            cerrar_posicion_market(client, symbol, simular)
        elif opcion == "3":
            return
        else:
            ui_warn("Opción no válida.")


def main():
    ui_titulo("Bot Futuros USDT-M")
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
            ui_info("Saliendo del bot.")
            break
        else:
            ui_warn("Opción no válida. Intenta de nuevo.")


if __name__ == "__main__":
    main()
