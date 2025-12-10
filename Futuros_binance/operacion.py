# operacion.py
from infra_futuros import (
    precheck_poder_trading,
    get_lot_size_filter_futuros,
    floor_to_step,
    format_quantity,
    get_max_leverage_symbol,
    get_futuros_usdt_balance,
)
from tacticas_entrada import tactica_entrada_cruce_wma, tactica_entrada_wma34_debajo_y_cruce_89
from tacticas_salida import tactica_salida_trailing_stop_wma
import time


# ==========================================================
# POSICIÓN ACTUAL (para mantener / vender / freno de emergencia)
# ==========================================================
def get_posicion_actual(client, symbol: str):
    """Devuelve el diccionario de posición actual en ese símbolo, o None si no hay."""
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
    """Imprime en pantalla la posición actual."""
    pos = get_posicion_actual(client, symbol)
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


def cerrar_posicion_completa_market(client, symbol: str, simular: bool):
    """Cierra la posición completa a mercado (se usa como 'freno de emergencia')."""
    pos = get_posicion_actual(client, symbol)
    if not pos:
        print(f"\nℹ️ No hay posición abierta en {symbol} para cerrar.")
        return

    amt = float(pos["positionAmt"])
    if amt == 0:
        print(f"\nℹ️ No hay cantidad abierta en {symbol}.")
        return

    side_actual = "long" if amt > 0 else "short"
    side_order = "SELL" if amt > 0 else "BUY"
    qty = abs(amt)
    qty_str = format_quantity(qty)

    print("\n=== CIERRE COMPLETO (FRENO DE EMERGENCIA) ===")
    print(f"Símbolo:  {symbol}")
    print(f"Lado:     {side_actual.upper()}")
    print(f"Orden:    {side_order} {qty_str} (MARKET)")
    print(f"Modo:     {'SIMULACIÓN' if simular else 'REAL'}\n")

    if simular:
        print("SIMULACIÓN: no se envió orden real de cierre.\n")
        return

    try:
        resp = client.new_order(symbol=symbol, side=side_order, type="MARKET", quantity=qty_str)
        print("✅ Orden de cierre enviada. Respuesta de Binance:")
        print(resp)
    except Exception as e:
        print(f"❌ Error al cerrar la posición: {e}")


# ==========================================================
# OPERACIÓN: COMPRA por cruce de WMA (LONG o SHORT)
# ==========================================================
def compra_por_cruce_wma(
    client,
    symbol: str,
    base_asset: str,
    side: str,          # "long" o "short"
    simular: bool,
    interval: str,
    sleep_seconds: int,
    wma_entry_len: int,
    wma_stop_len: int,
    wait_on_close: bool,
    poder_usar: float,
):
    """
    Operación: COMPRA (apertura de posición) por cruce de WMA.
    - Usa tactica_entrada_cruce_wma.
    - Luego usa tactica_salida_trailing_stop_wma para cerrar.
    """
    balance_usdt = get_futuros_usdt_balance(client)
    max_lev = get_max_leverage_symbol(client, symbol)
    trading_power = balance_usdt * max_lev

    if poder_usar <= 0:
        print("❌ El poder de trading debe ser mayor que 0. Cancelando.")
        return

    if trading_power <= 0:
        print("❌ No tienes poder de trading disponible. Revisa tu balance de Futuros.")
        return

    if poder_usar > trading_power:
        print("❌ No puedes usar más poder de trading del que tienes disponible.")
        return

    # Precheck rápido de poder
    try:
        ok_poder = precheck_poder_trading(client, symbol, poder_usar)
        if not ok_poder:
            return
    except Exception as e:
        print(f"⚠️ Error en precheck de poder: {e}")
        print("Continuando de todas formas...\n")

    # Configurar apalancamiento
    if not simular:
        try:
            print(f"\nConfigurando leverage {max_lev}x para {symbol}...")
            client.change_leverage(symbol=symbol, leverage=max_lev)
        except Exception as e:
            print(f"⚠️ No se pudo cambiar leverage (usará el actual). Error: {e}")

    # === TÁCTICA DE ENTRADA ===
    entry_price_ref = tactica_entrada_cruce_wma(
        client=client,
        symbol=symbol,
        interval=interval,
        wma_entry_len=wma_entry_len,
        sleep_seconds=sleep_seconds,
        side=side,
    )

    if entry_price_ref is None:
        print("No se ejecutó entrada. Saliendo.")
        return

    # Calcular cantidad estimada
    raw_qty_est = poder_usar / entry_price_ref

    try:
        min_qty, max_qty, step_size = get_lot_size_filter_futuros(client, symbol)
        qty_est = min(raw_qty_est, max_qty)
        qty_est = floor_to_step(qty_est, step_size)

        NOTIONAL_MIN = 100.0
        if qty_est < min_qty:
            notional_min_qty = min_qty * entry_price_ref
            print("\n❌ Tras el cruce, la cantidad queda por debajo del minQty.")
            print(f"Precio entrada ref: {entry_price_ref:.4f}, minQty: {min_qty}, qty_est: {qty_est}")
            print(f"Notional mínimo por minQty: {notional_min_qty:.4f} USDT")
            print("No se abrirá la posición.\n")
            return

        notional_est = qty_est * entry_price_ref
        if notional_est < NOTIONAL_MIN:
            print("\n❌ Tras el cruce, la orden NO alcanza el notional mínimo de Binance Futuros.")
            print(f"Notional estimado: {notional_est:.4f} USDT, mínimo requerido: {NOTIONAL_MIN:.4f} USDT")
            print("No se abrirá la posición.\n")
            return

        qty_str = format_quantity(qty_est)

    except Exception as e:
        print(f"⚠️ No se pudo obtener LOT_SIZE Futuros. Usando qty estimada sin normalizar: {e}")
        qty_est = raw_qty_est
        qty_str = format_quantity(qty_est)

    print(f"\n[OPERACIÓN COMPRA] Señal de entrada {side.upper()} activada.")
    print(f"Precio de referencia (ticker): {entry_price_ref:.4f} USDT")
    print(f"Cantidad estimada a abrir:     {qty_str} {base_asset}")
    print(f"Poder de trading usado:        {poder_usar:.4f} USDT")
    print(f"Leverage efectivo (aprox):     {max_lev}x\n")

    entry_margin_usdt = poder_usar / max_lev if max_lev != 0 else poder_usar
    entry_exec_price = entry_price_ref

    # Enviar orden de apertura
    if simular:
        print("SIMULACIÓN: No se envía orden de apertura real.\n")
    else:
        try:
            if side == "long":
                binance_side = "BUY"
            else:
                binance_side = "SELL"

            print(f"📥 ENVIANDO ORDEN MARKET {binance_side} ({side.upper()} FUTUROS)...")
            entry_order = client.new_order(
                symbol=symbol,
                side=binance_side,
                type="MARKET",
                quantity=qty_str
            )
            print("Orden de APERTURA enviada. Respuesta de Binance:")
            print(entry_order)

            # Pequeña pausa por seguridad
            time.sleep(0.5)

        except Exception as e:
            print(f"❌ Error enviando orden de apertura en Futuros: {e}")
            return

    print("\n=== Apertura realizada (real o simulada). Iniciando TÁCTICA DE SALIDA (TRAILING WMA)... ===\n")

    tactica_salida_trailing_stop_wma(
        client=client,
        symbol=symbol,
        base_asset=base_asset,
        interval=interval,
        sleep_seconds=sleep_seconds,
        wma_stop_len=wma_stop_len,
        wait_on_close=wait_on_close,
        qty_est=qty_est,
        qty_str=qty_str,
        entry_exec_price=entry_exec_price,
        entry_margin_usdt=entry_margin_usdt,
        simular=simular,
        side=side,
        balance_inicial_futuros=balance_usdt,
    )


# ==========================================================
# OPERACIÓN: COMPRA límite o a mercado (stub)
# ==========================================================
def compra_limit_o_market(*args, **kwargs):
    """
    Stub para compra por orden límite o a mercado.

    Aquí, más adelante, puedes implementar:
    - Preguntar precio límite o usar precio actual.
    - Enviar una orden LIMIT o MARKET directa sin táctica de entrada.

    Lo dejo así para mantener el sistema simple por ahora.
    """
    print("⚠️ compra_limit_o_market aún no implementada. Usa compra por cruce de WMA.")


# ==========================================================
# OPERACIÓN: VENTA por freno de emergencia
# ==========================================================
def venta_freno_emergencia(client, symbol: str, simular: bool):
    """
    Venta por freno de emergencia:
    - Cierra la posición completa a mercado usando cerrar_posicion_completa_market.
    """
    cerrar_posicion_completa_market(client, symbol, simular)


# ==========================================================
# OPERACIÓN: VENTA por stop limit (stub)
# ==========================================================
def venta_stop_limit(*args, **kwargs):
    """
    Stub para venta por stop limit.
    Más adelante puedes:
    - Calcular el precio de stop
    - Calcular el precio límite
    - Enviar una orden STOP_LIMIT en Binance.
    """
    print("⚠️ venta_stop_limit aún no implementada. Usa trailing o freno de emergencia.")


# ==========================================================
# OPERACIÓN: MANTENER
# ==========================================================
def mantener_posicion():
    """Mantener = no hacer nada; sirve solo para tu estructura mental."""
    print("Mantener posición: no se ejecuta compra ni venta en este ciclo.")
