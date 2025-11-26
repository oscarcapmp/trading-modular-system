# mvp3_trailing_sim.py
import time
import os
import platform
from mvp_lib import get_client, get_closes, wma
from sim_entry import prompt_simulated_entry


# ==========================================================
# ALARMA SONORA – Glass + Voz femenina "Stop activado"
# ==========================================================
def sonar_alarma():
    """Alarma sonora en macOS: sonido Glass + voz femenina."""
    if platform.system() == "Darwin":
        # 1) Sonido Glass
        sound_path = "/System/Library/Sounds/Glass.aiff"
        if os.path.exists(sound_path):
            os.system(f'afplay "{sound_path}"')

        # 2) Esperar 3 segundos
        time.sleep(3)

        # 3) Voz femenina – macOS usa Victoria o Samantha según disponibilidad
        #   Puedes cambiar "Victoria" por "Samantha" si la prefieres
        os.system('say -v Victoria "Stop activado"')

    else:
        # Fallback: beep estándar
        for _ in range(5):
            print("\a")
            time.sleep(0.3)


# ==========================================================
# BOT PRINCIPAL – PILOTO SIMULADO
# ==========================================================
def main():
    client = get_client()

    # 1) Definir posición simulada (sin tocar Binance)
    pos = prompt_simulated_entry()
    symbol = pos["symbol"]
    market_type = pos["market_type"]  # spot / futuros
    side = pos["side"]                # long / short
    amount_usd = pos["amount_usd"]
    entry_price = pos["entry_price"]
    initial_stop = pos["initial_stop"]

    print(f"Mercado simulado: {market_type.upper()}")

    # 2) Si el precio de entrada es 0, usar último precio real Spot
    if entry_price == 0:
        ticker = client.ticker_price(symbol)
        entry_price = float(ticker["price"])
        pos["entry_price"] = entry_price
        print(f"Usando último precio de mercado como entrada: {entry_price:.4f}")

    # 3) Calcular cantidad simulada
    qty = amount_usd / entry_price
    pos["qty"] = qty
    print(f"Cantidad simulada: {qty:.6f} {symbol.replace('USDT','')} aprox.\n")

    # 4) Parámetros del trailing WMA
    interval = input("Marco de tiempo (ej: 1m, 5m, 15m, 1h): ").strip() or "15m"
    wma_length = int(input("Longitud de WMA (ej: 34): ").strip() or "34")
    sleep_seconds = int(input("Segundos entre chequeos (ej: 15): ").strip() or "15")

    # 🔹 Opción: esperar cierre real de la vela
    wait_close_input = input("Esperar cierre real de la vela? (true/false): ").strip().lower() or "false"
    wait_on_close = wait_close_input in ["true", "t", "1", "s", "si", "sí", "y", "yes"]

    iniciar = input("¿Iniciar el trailing ahora? (s/n): ").strip().lower()
    if iniciar not in ["s", "si", "sí"]:
        print("Trailing no iniciado. Saliendo.")
        return

    print(f"\nMonitoreando {symbol} en {interval} con WMA{wma_length} (SIMULADO, sin órdenes reales)...")
    if wait_on_close:
        print("Modo: señales SOLO al cierre REAL de la vela.\n")
    else:
        print("Modo: señales en tiempo real (vela en formación).\n")

    print("Ctrl+C para detener.\n")

    last_state = None
    last_closed_close = None  # para detectar cuándo cambia la vela cerrada

    while True:
        try:
            closes = get_closes(client, symbol, interval, limit=wma_length + 3)
            if len(closes) < wma_length + 2:
                print("Aún no hay suficientes velas. Esperando...")
                time.sleep(sleep_seconds)
                continue

            wma_current = wma(closes, wma_length)
            wma_prev = wma(closes[:-1], wma_length)

            close_current = closes[-1]  # cierre PARCIAL de la vela actual (timeframe elegido)
            close_prev = closes[-2]     # cierre DEFINITIVO de la vela anterior (cerrada)

            current_state = "above" if close_current > wma_current else "below"
            prev_state = "above" if close_prev > wma_prev else "below"

            # Estado que usaremos para detectar el cruce:
            # - Si esperamos cierre real, usamos la vela previa (ya cerrada)
            # - Si no, usamos la vela actual (en formación)
            state_for_signal = prev_state if wait_on_close else current_state

            if last_state is None:
                # Primer ciclo: inicializamos last_state y last_closed_close
                last_state = state_for_signal
                last_closed_close = close_prev

            # 👀 Mostrar cierres parciales y cierre definitivo
            # Parcial = vela actual en formación
            print(f"[PARCIAL] Vela actual {interval} -> Close parcial: {close_current:.4f} | WMA{wma_length}: {wma_current:.4f} | Estado actual: {current_state} | Estado señal: {state_for_signal}")

            # Detectar si cambió la vela cerrada (cuando empieza una nueva vela)
            if close_prev != last_closed_close:
                print(f"[CERRADA] Nueva vela {interval} cerrada -> Close definitivo: {close_prev:.4f}")
                last_closed_close = close_prev

            # Cruces según el estado que define la señal
            crossed_down = last_state == "above" and state_for_signal == "below"
            crossed_up = last_state == "below" and state_for_signal == "above"

            trigger_exit = False
            motivo = ""

            if side == "long" and crossed_down:
                trigger_exit = True
                motivo = "Cruce bajista (precio cruza por debajo de la WMA)."
            
            elif side == "short" and crossed_up:
                trigger_exit = True
                motivo = "Cruce alcista (precio cruza por encima de la WMA)."

            if trigger_exit:
                # Precio de salida:
                # - Si esperamos cierre real -> vela previa (cerrada)
                # - Si no -> vela actual (precio en tiempo real)
                exit_price = close_prev if wait_on_close else close_current

                if side == "long":
                    pnl_usd = (exit_price - entry_price) * qty
                else:
                    pnl_usd = (entry_price - exit_price) * qty

                # 🔔 SONAR ALARMA AQUÍ
                sonar_alarma()

                print("\n=== SALIDA SIMULADA POR CRUCE WMA ===")
                print(f"Mercado: {market_type.upper()}")
                print(f"Motivo: {motivo}")
                print(f"Entrada: {entry_price:.4f}")
                print(f"Salida:  {exit_price:.4f}")
                print(f"Cantidad: {qty:.6f}")
                print(f"P&L estimado: {pnl_usd:.2f} USD\n")
                print("Fin del piloto simulado.\n")
                break

            # Actualizamos last_state al estado que usamos como señal
            last_state = state_for_signal
            time.sleep(sleep_seconds)

        except KeyboardInterrupt:
            print("\nBot detenido por el usuario.")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(sleep_seconds)


if __name__ == "__main__":
    main()
