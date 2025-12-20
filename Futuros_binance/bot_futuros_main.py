from infra_futuros import (
    format_quantity,
    get_futures_client,
    get_futures_usdt_balance,
    get_max_leverage_symbol,
    get_closes_futures,
)
from config_wma_pack import MAX_WMA_PACK_LEN
from indicators.wma_pack import calc_wma_pack, check_wma_alignment
from operacion import (
    cerrar_posicion_market,
    get_current_position,
    mostrar_posicion_actual,
    run_long_strategy,
    run_short_strategy,
)
from tacticas_salida import tactica_salida_trailing_stop_wma


def report_wma_pack_alignment(client, symbol: str, interval: str, side: str):
    try:
        closes = get_closes_futures(client, symbol, interval, limit=MAX_WMA_PACK_LEN + 2)
    except Exception as e:
        print(f"⚠️ No se pudieron leer cierres para WMA Pack: {e}")
        return False

    wma_values = calc_wma_pack(closes)
    aligned, broken, msg = check_wma_alignment(wma_values, side=side)
    print(msg)
    return aligned


def main():
    print("=== Bot Futuros USDT-M – ENTRADA por cruce + CIERRE por WMA STOP (LONG / SHORT) ===")

    client = get_futures_client()

    symbol = input("Símbolo Futuros (ej: BTCUSDT): ").strip().upper() or "BTCUSDT"
    base_asset = symbol.replace("USDT", "")

    sim_input = input("¿Simular sin enviar órdenes reales? (s/n): ").strip().lower() or "s"
    simular = sim_input in ["s", "si", "sí", "y", "yes"]

    interval = input("Marco de tiempo (ej: 1m, 5m, 15m, 1h): ").strip() or "1m"
    sleep_seconds = int(input("Segundos entre chequeos (ej: 15): ").strip() or "15")

    wma_entry_len = int(
        input("WMA de ENTRADA (ej: 89, o 0 para entrar a MARKET inmediato): ").strip() or "89"
    )
    wma_stop_len = int(input("Longitud de WMA de STOP (ej: 34): ").strip() or "34")

    emergency_input = input("¿Activar freno de emergencia ATR NATIVO en Binance? (s/n) [default: s]: ").strip().lower() or "s"
    emergency_atr_on = emergency_input in ["s", "si", "sí", "y", "yes"]

    trailing_dyn_input = input("¿Activar trailing dinámico 2 fases? (s/n) [default: n]: ").strip().lower() or "n"
    trailing_dinamico_on = trailing_dyn_input in ["s", "si", "sí", "y", "yes"]
    pct_fase1_input = input("Porcentaje de cierre en Fase 1 (1-99) [default: 50]: ").strip() or "50"
    try:
        pct_fase1 = float(pct_fase1_input)
        if pct_fase1 < 1:
            pct_fase1 = 1
        if pct_fase1 > 99:
            pct_fase1 = 99
    except ValueError:
        pct_fase1 = 50

    if wma_entry_len == 0:
        print("Entrada MARKET inmediata (sin táctica de cruce).")

    wait_close_input = input("¿Esperar cierre REAL de la vela para el STOP? (true/false): ").strip().lower() or "true"
    wait_on_close = wait_close_input in ["true", "t", "1", "s", "si", "sí", "y", "yes"]

    balance_usdt = get_futures_usdt_balance(client)
    max_lev = get_max_leverage_symbol(client, symbol)
    trading_power = balance_usdt * max_lev

    print("\n=== INFORMACIÓN DE CUENTA (MODO QUANTFURY) ===")
    print(f"Balance disponible USDT (Futuros): {balance_usdt:.4f}")
    print(f"Apalancamiento MÁXIMO para {symbol}: {max_lev}x (fijo en esta versión)")
    print(f"Poder de trading (balance * maxLev): {trading_power:.4f} USDT")
    print("================================================\n")

    side_input = input("¿Estrategia LONG o SHORT? (long/short): ").strip().lower() or "long"
    if side_input not in ["long", "short"]:
        print("Opción de lado no válida. Usa 'long' o 'short'. Saliendo.")
        return

    report_wma_pack_alignment(client, symbol, interval, side_input)

    print("=== MENÚ DE ACCIONES ===")
    print("1) Ver posición actual en este símbolo")
    print("2) Cerrar posición completa (MARKET)")
    print("3) Ejecutar estrategia completa: cruce WMA ENTRADA + apertura + trailing STOP (MODO QUANTFURY)")
    print("4) Asumir que ya hay posición abierta y SOLO ejecutar trailing STOP\n")

    opcion = input("Elige una opción (1/2/3/4): ").strip()

    if opcion == "1":
        mostrar_posicion_actual(client, symbol)
        return

    elif opcion == "2":
        cerrar_posicion_market(client, symbol, simular)
        return

    print("\n=== RESUMEN CONFIGURACIÓN FUTUROS ===")
    print(f"Símbolo:             {symbol}")
    print(f"Lado estrategia:     {side_input.upper()}")
    print(f"Modo:                {'SIMULACIÓN' if simular else 'REAL'}")
    print(f"Intervalo:           {interval}")
    print(f"WMA de ENTRADA:      {wma_entry_len}")
    print(f"WMA de STOP:         {wma_stop_len}")
    print(f"Freno nativo:        {'Sí' if emergency_atr_on else 'No'}")
    print(f"Trailing dinámico:   {'Sí' if trailing_dinamico_on else 'No'} (Fase1: {pct_fase1}%)")
    print(f"Sleep (segundos):    {sleep_seconds}")
    print(f"Esperar cierre STOP: {wait_on_close}")
    print(f"Apalancamiento usado: {max_lev}x")
    print(f"Balance USDT:        {balance_usdt:.4f}")
    print(f"Poder de trading:    {trading_power:.4f} USDT\n")

    if opcion == "3":
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
                balance_usdt=balance_usdt,
                trading_power=trading_power,
                max_lev=max_lev,
                trailing_dinamico_on=trailing_dinamico_on,
                pct_fase1=pct_fase1,
            )

    elif opcion == "4":
        continuar = input("\n¿Iniciar SOLO el trailing STOP sobre una posición ya abierta? (s/n): ").strip().lower()
        if continuar not in ["s", "si", "sí", "y", "yes"]:
            print("Bot cancelado por el usuario.")
            return

        pos = get_current_position(client, symbol)
        if not pos:
            print(f"\n❌ No se encontró una posición abierta en {symbol}. No se puede iniciar trailing.")
            return

        amt = float(pos["positionAmt"])
        if side_input == "long" and amt <= 0:
            print(f"\n❌ La posición no es LONG (amt={amt}). Ajusta el lado o abre una LONG primero.")
            return
        if side_input == "short" and amt >= 0:
            print(f"\n❌ La posición no es SHORT (amt={amt}). Ajusta el lado o abre una SHORT primero.")
            return

        entry_exec_price = float(pos["entryPrice"])
        lev = float(pos["leverage"])
        notional = abs(amt) * entry_exec_price
        entry_margin_usdt = notional / lev if lev != 0 else notional

        qty_est = abs(amt)
        qty_str = format_quantity(qty_est)

        lado_txt = "LONG" if side_input == "long" else "SHORT"
        print("\n=== TRAILING SOLO SOBRE POSICIÓN EXISTENTE ===")
        print(f"Símbolo:        {symbol}")
        print(f"Cantidad {lado_txt}:  {qty_est}")
        print(f"Precio entrada: {entry_exec_price}")
        print(f"Leverage:       {lev}x")
        print(f"Margen aprox:   {entry_margin_usdt:.4f} USDT")
        print("Iniciando trailing WMA STOP solamente...\n")

        tactica_salida_trailing_stop_wma(
            client=client,
            symbol=symbol,
            base_asset=base_asset,
            interval=interval,
            sleep_seconds=sleep_seconds,
            wma_stop_len=wma_stop_len,
            wait_on_close=wait_on_close,
            emergency_atr_on=emergency_atr_on,
            qty_est=qty_est,
            qty_str=qty_str,
            entry_exec_price=entry_exec_price,
            entry_margin_usdt=entry_margin_usdt,
            simular=simular,
            side=side_input,
            entry_order_id=None,
            balance_inicial_futuros=balance_usdt,
            trailing_dinamico_on=trailing_dinamico_on,
            pct_fase1=pct_fase1,
        )

    else:
        print("Opción no válida. Saliendo.")


if __name__ == "__main__":
    main()
