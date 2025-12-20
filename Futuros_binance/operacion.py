import time
from infra_futuros import (
    atr_sma,
    floor_to_step,
    format_quantity,
    get_hlc_futures,
    get_lot_size_filter_futures,
    precheck_poder_trading,
    wma,
)
from binance_algo_orders import place_conditional_stop_market
from tacticas_entrada import tactica_entrada_cruce_wma
from tacticas_salida import tactica_salida_trailing_stop_wma


def get_current_position(client, symbol: str):
    try:
        resp = client.get_position_risk(symbol=symbol)
        for p in resp:
            amt = float(p.get("positionAmt", "0"))
            if abs(amt) > 0:
                return p
        return None
    except Exception as e:
        print(f"Error obteniendo posición actual: {e}")
        return None


def mostrar_posicion_actual(client, symbol: str):
    pos = get_current_position(client, symbol)
    if not pos:
        print(f"\nℹ️ No hay posición abierta en {symbol}.")
        return

    amt = float(pos["positionAmt"])
    side = "LONG" if amt > 0 else "SHORT"
    entry = float(pos["entryPrice"])
    mark = float(pos["markPrice"])
    lev = float(pos["leverage"])
    upnl = float(pos["unRealizedProfit"])

    print("\n=== POSICIÓN ACTUAL ===")
    print(f"Símbolo:        {symbol}")
    print(f"Lado:           {side}")
    print(f"Cantidad:       {amt}")
    print(f"Precio entrada: {entry}")
    print(f"Precio mark:    {mark}")
    print(f"Leverage:       {lev}x")
    print(f"uPnL:           {upnl} USDT")
    print("========================\n")


def cerrar_posicion_market(client, symbol: str, simular: bool):
    pos = get_current_position(client, symbol)
    if not pos:
        print(f"\nℹ️ No hay posición abierta en {symbol} para cerrar.")
        return

    amt = float(pos["positionAmt"])
    if amt == 0:
        print(f"\nℹ️ No hay cantidad abierta en {symbol}.")
        return

    side = "SELL" if amt > 0 else "BUY"
    qty = abs(amt)
    qty_str = format_quantity(qty)

    print("\n=== CIERRE MANUAL DE POSICIÓN ===")
    print(f"Símbolo:  {symbol}")
    print(f"Lado:     {'LONG' if amt > 0 else 'SHORT'}")
    print(f"Orden:    {side} {qty_str} (MARKET)")
    print(f"Modo:     {'SIMULACIÓN' if simular else 'REAL'}\n")

    if simular:
        print("SIMULACIÓN: no se envió orden real de cierre.\n")
        return

    try:
        resp = client.new_order(symbol=symbol, side=side, type="MARKET", quantity=qty_str)
        print("✅ Orden de cierre enviada. Respuesta de Binance:")
        print(resp)
    except Exception as e:
        print(f"❌ Error al cerrar la posición: {e}")


def comprar_long_por_cruce_wma(
    client,
    symbol: str,
    base_asset: str,
    simular: bool,
    interval: str,
    sleep_seconds: int,
    wma_entry_len: int,
    wma_stop_len: int,
    wait_on_close: bool,
    emergency_atr_on: bool,
    balance_usdt: float,
    trading_power: float,
    max_lev: int,
    trailing_dinamico_on: bool = False,
    pct_fase1: float = 50,
):
    if trading_power <= 0:
        print("❌ No tienes poder de trading disponible. Revisa tu balance de Futuros.")
        return

    poder_usar = float(
        input(
            f"Poder de trading (USDT) que deseas usar en esta entrada LONG (<= {trading_power:.4f}): "
        ).strip()
    )

    if poder_usar <= 0:
        print("❌ El poder de trading debe ser mayor que 0. Cancelando.")
        return

    if poder_usar > trading_power:
        print("❌ No puedes usar más poder de trading del que tienes disponible.")
        return

    prompt_accion = (
        f"\n¿Activar bot y ENTRAR LONG MARKET inmediato usando {poder_usar:.4f} USDT? (s/n): "
        if wma_entry_len == 0
        else f"\n¿Activar bot y esperar señal de ENTRADA LONG usando {poder_usar:.4f} USDT de poder? (s/n): "
    )
    continuar = input(prompt_accion).strip().lower()
    if continuar not in ["s", "si", "sí", "y", "yes"]:
        print("Bot cancelado por el usuario.")
        return

    try:
        ok_poder = precheck_poder_trading(client, symbol, poder_usar)
        if not ok_poder:
            return
    except Exception as e:
        print(f"⚠️ Error en precheck de poder: {e}")
        print("Continuando de todas formas (el lote se validará de nuevo en la entrada)...\n")

    if not simular:
        try:
            print(f"\nConfigurando leverage {max_lev}x para {symbol}...")
            client.change_leverage(symbol=symbol, leverage=max_lev)
        except Exception as e:
            print(f"⚠️ No se pudo cambiar leverage (usará el actual). Error: {e}")

    if wma_entry_len == 0:
        ticker = client.ticker_price(symbol=symbol)
        entry_price_ref = float(ticker["price"])
        print("\n[ENTRADA] WMA de entrada = 0, ejecutando MARKET inmediato.")
    else:
        entry_price_ref = tactica_entrada_cruce_wma(
            client=client,
            symbol=symbol,
            interval=interval,
            wma_entry_len=wma_entry_len,
            sleep_seconds=sleep_seconds,
            side="long",
        )

    if entry_price_ref is None:
        print("No se ejecutó entrada. Saliendo.")
        return

    raw_qty_est = poder_usar / entry_price_ref
    entry_order_id = None

    try:
        min_qty, max_qty, step_size = get_lot_size_filter_futures(client, symbol)
        qty_est = min(raw_qty_est, max_qty)
        qty_est = floor_to_step(qty_est, step_size)

        NOTIONAL_MIN = 100.0
        if qty_est < min_qty:
            notional_min_qty = min_qty * entry_price_ref
            print("\n❌ Tras el cruce, la cantidad queda por debajo del minQty.")
            print(f"Precio entrada ref: {entry_price_ref:.4f}, minQty: {min_qty}, qty_est: {qty_est}")
            print(f"Notional mínimo por minQty: {notional_min_qty:.4f} USDT")
            print("No se abrirá la posición. Ajusta el poder de trading o usa otro símbolo.\n")
            return

        notional_est = qty_est * entry_price_ref
        if notional_est < NOTIONAL_MIN:
            print("\n❌ Tras el cruce, la orden NO alcanza el notional mínimo de Binance Futuros.")
            print(f"Notional estimado: {notional_est:.4f} USDT, mínimo requerido: {NOTIONAL_MIN:.4f} USDT")
            print("No se abrirá la posición. Ajusta el poder de trading o usa otro símbolo.\n")
            return

        qty_str = format_quantity(qty_est)

        print(f"Filtro LOT_SIZE Futuros {symbol} -> minQty={min_qty}, stepSize={step_size}, maxQty={max_qty}")
        print(
            f"[DEBUG] raw_qty_est: {raw_qty_est}, qty_est normalizada: {qty_est}, "
            f"qty_str: {qty_str}, notional_est: {notional_est:.4f}"
        )

    except Exception as e:
        print(f"⚠️ No se pudo obtener LOT_SIZE Futuros. Usando qty estimada sin normalizar: {e}")
        qty_est = raw_qty_est
        qty_str = format_quantity(qty_est)

    print(f"\n[FUTUROS LONG] Señal de entrada LONG activada.")
    print(f"Precio de referencia (ticker): {entry_price_ref:.4f} USDT")
    print(f"Cantidad estimada a abrir:     {qty_str} {base_asset}")
    print(f"Poder de trading usado:        {poder_usar:.4f} USDT")
    print(f"Leverage efectivo (aprox):     {max_lev}x")
    print("Ejecutando APERTURA LONG automáticamente...\n")

    entry_margin_usdt = poder_usar / max_lev if max_lev != 0 else poder_usar
    entry_exec_price = entry_price_ref

    if simular:
        print("SIMULACIÓN: No se envía orden de apertura real.\n")
    else:
        try:
            print("📥 ENVIANDO ORDEN MARKET BUY (LONG FUTUROS)...")
            entry_order = client.new_order(
                symbol=symbol,
                side="BUY",
                type="MARKET",
                quantity=qty_str
            )
            print("Orden de APERTURA LONG enviada. Respuesta de Binance:")
            print(entry_order)
            entry_order_id = entry_order.get("orderId")

            time.sleep(0.5)
            pos = get_current_position(client, symbol)
            if pos:
                amt_pos = float(pos.get("positionAmt", "0"))
                if amt_pos > 0:
                    entry_exec_price = float(pos.get("entryPrice", entry_price_ref))
                    lev_pos = float(pos.get("leverage", max_lev))
                    notional_pos = abs(amt_pos) * entry_exec_price
                    entry_margin_usdt = notional_pos / lev_pos if lev_pos != 0 else entry_margin_usdt
                    qty_est = abs(amt_pos)
                    qty_str = format_quantity(qty_est)
                    print("\n[INFO] Datos reales de la posición LONG tomados de get_position_risk():")
                    print(f"Cantidad real:   {qty_est}")
                    print(f"Precio entrada:  {entry_exec_price}")
                    print(f"Leverage real:   {lev_pos}x")
                    print(f"Margen aprox:    {entry_margin_usdt:.4f} USDT\n")
            else:
                print("\n⚠️ No se pudo leer la posición después de la orden. Se usa precio de referencia.\n")

        except Exception as e:
            print(f"❌ Error enviando orden de apertura LONG en Futuros: {e}")
            return

    print("\n=== Apertura LONG realizada (real o simulada). Iniciando TRAILING WMA STOP... ===\n")

    emergency_algo_id = None
    emergency_price = None
    try:
        atr_len = 14
        limit_needed = max(wma_stop_len + 3, atr_len + 2)
        highs, lows, closes = get_hlc_futures(client, symbol, interval, limit=limit_needed)
        wma_stop_ref = wma(closes, wma_stop_len)
        atr_ref = atr_sma(highs, lows, closes, atr_len)
        if wma_stop_ref is not None and atr_ref is not None and emergency_atr_on:
            emergency_price = wma_stop_ref - 1.5 * atr_ref
            exit_side = "SELL"
            order = place_conditional_stop_market(
                client=client,
                symbol=symbol,
                side=exit_side,
                stop_price=emergency_price,
                qty_str=qty_str,
                atr_ref=atr_ref,
            )
            emergency_algo_id = order.get("algoId")
        elif emergency_atr_on:
            print("⚠️ No se pudo calcular freno nativo (datos insuficientes para WMA/ATR).")
    except Exception as e:
        print(f"⚠️ Error preparando freno nativo: {e}")

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
        side="long",
        entry_order_id=entry_order_id,
        balance_inicial_futuros=balance_usdt,
        emergency_algo_id=emergency_algo_id,
        emergency_stop_active=emergency_atr_on,
        emergency_level_fixed=emergency_price if emergency_atr_on else None,
        emergency_side_close=exit_side,
        emergency_enabled=emergency_atr_on,
        trailing_dinamico_on=trailing_dinamico_on,
        pct_fase1=pct_fase1,
    )


def comprar_short_por_cruce_wma(
    client,
    symbol: str,
    base_asset: str,
    simular: bool,
    interval: str,
    sleep_seconds: int,
    wma_entry_len: int,
    wma_stop_len: int,
    wait_on_close: bool,
    emergency_atr_on: bool,
    balance_usdt: float,
    trading_power: float,
    max_lev: int,
    trailing_dinamico_on: bool = False,
    pct_fase1: float = 50,
):
    if trading_power <= 0:
        print("❌ No tienes poder de trading disponible. Revisa tu balance de Futuros.")
        return

    poder_usar = float(
        input(
            f"Poder de trading (USDT) que deseas usar en esta entrada SHORT (<= {trading_power:.4f}): "
        ).strip()
    )

    if poder_usar <= 0:
        print("❌ El poder de trading debe ser mayor que 0. Cancelando.")
        return

    if poder_usar > trading_power:
        print("❌ No puedes usar más poder de trading del que tienes disponible.")
        return

    prompt_accion = (
        f"\n¿Activar bot y ENTRAR SHORT MARKET inmediato usando {poder_usar:.4f} USDT? (s/n): "
        if wma_entry_len == 0
        else f"\n¿Activar bot y esperar señal de ENTRADA SHORT usando {poder_usar:.4f} USDT de poder? (s/n): "
    )
    continuar = input(prompt_accion).strip().lower()
    if continuar not in ["s", "si", "sí", "y", "yes"]:
        print("Bot cancelado por el usuario.")
        return

    try:
        ok_poder = precheck_poder_trading(client, symbol, poder_usar)
        if not ok_poder:
            return
    except Exception as e:
        print(f"⚠️ Error en precheck de poder: {e}")
        print("Continuando de todas formas (el lote se validará de nuevo en la entrada)...\n")

    if not simular:
        try:
            print(f"\nConfigurando leverage {max_lev}x para {symbol}...")
            client.change_leverage(symbol=symbol, leverage=max_lev)
        except Exception as e:
            print(f"⚠️ No se pudo cambiar leverage (usará el actual). Error: {e}")

    if wma_entry_len == 0:
        ticker = client.ticker_price(symbol=symbol)
        entry_price_ref = float(ticker["price"])
        print("\n[ENTRADA] WMA de entrada = 0, ejecutando MARKET inmediato.")
    else:
        entry_price_ref = tactica_entrada_cruce_wma(
            client=client,
            symbol=symbol,
            interval=interval,
            wma_entry_len=wma_entry_len,
            sleep_seconds=sleep_seconds,
            side="short",
        )

    if entry_price_ref is None:
        print("No se ejecutó entrada. Saliendo.")
        return

    raw_qty_est = poder_usar / entry_price_ref
    entry_order_id = None

    try:
        min_qty, max_qty, step_size = get_lot_size_filter_futures(client, symbol)
        qty_est = min(raw_qty_est, max_qty)
        qty_est = floor_to_step(qty_est, step_size)

        NOTIONAL_MIN = 100.0
        if qty_est < min_qty:
            notional_min_qty = min_qty * entry_price_ref
            print("\n❌ Tras el cruce, la cantidad queda por debajo del minQty.")
            print(f"Precio entrada ref: {entry_price_ref:.4f}, minQty: {min_qty}, qty_est: {qty_est}")
            print(f"Notional mínimo por minQty: {notional_min_qty:.4f} USDT")
            print("No se abrirá la posición. Ajusta el poder de trading o usa otro símbolo.\n")
            return

        notional_est = qty_est * entry_price_ref
        if notional_est < NOTIONAL_MIN:
            print("\n❌ Tras el cruce, la orden NO alcanza el notional mínimo de Binance Futuros.")
            print(f"Notional estimado: {notional_est:.4f} USDT, mínimo requerido: {NOTIONAL_MIN:.4f} USDT")
            print("No se abrirá la posición. Ajusta el poder de trading o usa otro símbolo.\n")
            return

        qty_str = format_quantity(qty_est)

        print(f"Filtro LOT_SIZE Futuros {symbol} -> minQty={min_qty}, stepSize={step_size}, maxQty={max_qty}")
        print(
            f"[DEBUG] raw_qty_est: {raw_qty_est}, qty_est normalizada: {qty_est}, "
            f"qty_str: {qty_str}, notional_est: {notional_est:.4f}"
        )

    except Exception as e:
        print(f"⚠️ No se pudo obtener LOT_SIZE Futuros. Usando qty estimada sin normalizar: {e}")
        qty_est = raw_qty_est
        qty_str = format_quantity(qty_est)

    print(f"\n[FUTUROS SHORT] Señal de entrada SHORT activada.")
    print(f"Precio de referencia (ticker): {entry_price_ref:.4f} USDT")
    print(f"Cantidad estimada a abrir:     {qty_str} {base_asset}")
    print(f"Poder de trading usado:        {poder_usar:.4f} USDT")
    print(f"Leverage efectivo (aprox):     {max_lev}x")
    print("Ejecutando APERTURA SHORT automáticamente...\n")

    entry_margin_usdt = poder_usar / max_lev if max_lev != 0 else poder_usar
    entry_exec_price = entry_price_ref

    if simular:
        print("SIMULACIÓN: No se envía orden de apertura real.\n")
    else:
        try:
            print("📥 ENVIANDO ORDEN MARKET SELL (SHORT FUTUROS)...")
            entry_order = client.new_order(
                symbol=symbol,
                side="SELL",
                type="MARKET",
                quantity=qty_str
            )
            print("Orden de APERTURA SHORT enviada. Respuesta de Binance:")
            print(entry_order)
            entry_order_id = entry_order.get("orderId")

            time.sleep(0.5)
            pos = get_current_position(client, symbol)
            if pos:
                amt_pos = float(pos.get("positionAmt", "0"))
                if amt_pos < 0:
                    entry_exec_price = float(pos.get("entryPrice", entry_price_ref))
                    lev_pos = float(pos.get("leverage", max_lev))
                    notional_pos = abs(amt_pos) * entry_exec_price
                    entry_margin_usdt = notional_pos / lev_pos if lev_pos != 0 else entry_margin_usdt
                    qty_est = abs(amt_pos)
                    qty_str = format_quantity(qty_est)
                    print("\n[INFO] Datos reales de la posición SHORT tomados de get_position_risk():")
                    print(f"Cantidad real:   {qty_est}")
                    print(f"Precio entrada:  {entry_exec_price}")
                    print(f"Leverage real:   {lev_pos}x")
                    print(f"Margen aprox:    {entry_margin_usdt:.4f} USDT\n")
            else:
                print("\n⚠️ No se pudo leer la posición después de la orden. Se usa precio de referencia.\n")

        except Exception as e:
            print(f"❌ Error enviando orden de apertura SHORT en Futuros: {e}")
            return

    print("\n=== Apertura SHORT realizada (real o simulada). Iniciando TRAILING WMA STOP... ===\n")

    emergency_algo_id = None
    emergency_price = None
    try:
        atr_len = 14
        limit_needed = max(wma_stop_len + 3, atr_len + 2)
        highs, lows, closes = get_hlc_futures(client, symbol, interval, limit=limit_needed)
        wma_stop_ref = wma(closes, wma_stop_len)
        atr_ref = atr_sma(highs, lows, closes, atr_len)
        if wma_stop_ref is not None and atr_ref is not None and emergency_atr_on:
            emergency_price = wma_stop_ref + 1.5 * atr_ref
            exit_side = "BUY"
            order = place_conditional_stop_market(
                client=client,
                symbol=symbol,
                side=exit_side,
                stop_price=emergency_price,
                qty_str=qty_str,
                atr_ref=atr_ref,
            )
            emergency_algo_id = order.get("algoId")
        elif emergency_atr_on:
            print("⚠️ No se pudo calcular freno nativo (datos insuficientes para WMA/ATR).")
    except Exception as e:
        print(f"⚠️ Error preparando freno nativo: {e}")

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
        side="short",
        entry_order_id=entry_order_id,
        balance_inicial_futuros=balance_usdt,
        emergency_algo_id=emergency_algo_id,
        emergency_stop_active=emergency_atr_on,
        emergency_level_fixed=emergency_price if emergency_atr_on else None,
        emergency_side_close=exit_side,
        emergency_enabled=emergency_atr_on,
        trailing_dinamico_on=trailing_dinamico_on,
        pct_fase1=pct_fase1,
    )


def mantener_posicion(*args, **kwargs):
    print("Manteniendo posición actual (placeholder).")


def run_long_strategy(*args, **kwargs):
    return comprar_long_por_cruce_wma(*args, **kwargs)


def run_short_strategy(*args, **kwargs):
    return comprar_short_por_cruce_wma(*args, **kwargs)
