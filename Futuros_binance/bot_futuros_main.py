# bot_futuros_main.py
from infra_futuros import get_futures_client, get_futuros_usdt_balance
from operacion import (
    mostrar_posicion_actual,
    venta_freno_emergencia,
    compra_por_cruce_wma,
)
# Si quieres luego: compra_limit_o_market, venta_stop_limit, mantener_posicion


def main():
    print("=== Bot Futuros USDT-M – Modular (Operación + Tácticas) ===")

    client = get_futures_client()

    symbol = input("Símbolo Futuros (ej: BTCUSDT): ").strip().upper() or "BTCUSDT"
    base_asset = symbol.replace("USDT", "")

    sim_input = input("¿Simular sin enviar órdenes reales? (s/n): ").strip().lower() or "s"
    simular = sim_input in ["s", "si", "sí", "y", "yes"]

    interval = input("Marco de tiempo (ej: 1m, 5m, 15m, 1h): ").strip() or "1m"
    sleep_seconds = int(input("Segundos entre chequeos (ej: 15): ").strip() or "15")

    wma_entry_len = int(input("Longitud de WMA de ENTRADA (ej: 89): ").strip() or "89")
    wma_stop_len = int(input("Longitud de WMA de STOP (ej: 34): ").strip() or "34")

    wait_close_input = input("¿Esperar cierre REAL de la vela para el STOP? (true/false): ").strip().lower() or "true"
    wait_on_close = wait_close_input in ["true", "t", "1", "s", "si", "sí", "y", "yes"]

    side_input = input("¿Estrategia LONG o SHORT? (long/short): ").strip().lower() or "long"
    if side_input not in ["long", "short"]:
        print("Opción de lado no válida. Usa 'long' o 'short'. Saliendo.")
        return

    balance_usdt = get_futuros_usdt_balance(client)
    print(f"\n=== INFORMACIÓN DE CUENTA ===")
    print(f"Balance disponible USDT (Futuros): {balance_usdt:.4f}")
    print("================================\n")

    print("=== MENÚ DE OPERACIÓN ===")
    print("1) Ver posición actual en este símbolo")
    print("2) Cerrar posición completa (FRENO DE EMERGENCIA)")
    print("3) Ejecutar COMPRA por cruce WMA + TRAILING STOP")
    print("4) (Reservado) Ejecutar sólo TRAILING STOP sobre posición ya abierta\n")

    opcion = input("Elige una opción (1/2/3): ").strip() or "3"

    if opcion == "1":
        mostrar_posicion_actual(client, symbol)
        return

    if opcion == "2":
        venta_freno_emergencia(client, symbol, simular)
        return

    if opcion == "3":
        poder_usar = float(
            input("Poder de trading (USDT) que deseas usar en esta operación: ").strip() or "0"
        )

        print("\n=== RESUMEN CONFIGURACIÓN OPERACIÓN ===")
        print(f"Símbolo:             {symbol}")
        print(f"Lado estrategia:     {side_input.upper()}")
        print(f"Modo:                {'SIMULACIÓN' if simular else 'REAL'}")
        print(f"Intervalo:           {interval}")
        print(f"WMA de ENTRADA:      {wma_entry_len}")
        print(f"WMA de STOP:         {wma_stop_len}")
        print(f"Sleep (segundos):    {sleep_seconds}")
        print(f"Esperar cierre STOP: {wait_on_close}")
        print(f"Balance USDT:        {balance_usdt:.4f}")
        print(f"Poder de trading:    {poder_usar:.4f} USDT\n")

        continuar = input("¿Ejecutar OPERACIÓN de compra por cruce WMA? (s/n): ").strip().lower()
        if continuar not in ["s", "si", "sí", "y", "yes"]:
            print("Operación cancelada por el usuario.")
            return

        compra_por_cruce_wma(
            client=client,
            symbol=symbol,
            base_asset=base_asset,
            side=side_input,
            simular=simular,
            interval=interval,
            sleep_seconds=sleep_seconds,
            wma_entry_len=wma_entry_len,
            wma_stop_len=wma_stop_len,
            wait_on_close=wait_on_close,
            poder_usar=poder_usar,
        )
        return

    print("Opción no válida. Saliendo.")


if __name__ == "__main__":
    main()
