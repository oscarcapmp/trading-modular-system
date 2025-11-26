# sim_entry.py
from typing import Dict

def prompt_simulated_entry() -> Dict:
    """
    Pide datos para simular una entrada.
    No toca Binance, solo calcula tamaño y guarda parámetros.
    """
    print("=== Simulación de entrada (no se envían órdenes reales) ===")

    symbol = input("Símbolo (ej: BTCUSDT): ").strip().upper() or "BTCUSDT"

    # Tipo de mercado: spot o futuros (solo informativo en este MVP)
    while True:
        market_type = input("¿Mercado SPOT o FUTUROS? (spot/futuros): ").strip().lower()
        if market_type in ["spot", "futuros", "futures"]:
            if market_type == "futures":
                market_type = "futuros"
            break
        print("Por favor escribe 'spot' o 'futuros'.")

    # Posición LONG / SHORT
    while True:
        side = input("¿Posición LONG o SHORT? (long/short): ").strip().lower()
        if side in ["long", "short"]:
            break
        print("Por favor escribe 'long' o 'short'.")

    # Monto en USD
    while True:
        try:
            amount_usd = float(input("Monto en USD para la posición (ej: 100): ").strip())
            if amount_usd > 0:
                break
        except ValueError:
            pass
        print("Monto inválido, intenta de nuevo.")

    # Precio de entrada
    print("Precio de entrada (simulado).")
    print("Puedes poner 0 para usar el último precio del mercado (lo calculará el script principal).")
    while True:
        try:
            entry_price = float(input("Precio de entrada (ej: 93000, o 0 para usar precio actual): ").strip())
            if entry_price >= 0:
                break
        except ValueError:
            pass
        print("Precio inválido, intenta de nuevo.")

    # Stop inicial (precio, no % en este MVP)
    while True:
        try:
            initial_stop = float(input("Stop inicial (precio, ej: 91000): ").strip())
            if initial_stop > 0:
                break
        except ValueError:
            pass
        print("Stop inválido, intenta de nuevo.")

    pos = {
        "symbol": symbol,
        "market_type": market_type,  # "spot" o "futuros"
        "side": side,                # "long" o "short"
        "amount_usd": amount_usd,
        "entry_price": entry_price,  # si es 0, se completa luego
        "initial_stop": initial_stop,
    }

    print("\nResumen posición simulada:")
    print(pos)
    print()
    return pos

if __name__ == "__main__":
    p = prompt_simulated_entry()
    print("Posición simulada:", p)
