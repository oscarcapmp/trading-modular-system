import time
from infra_futuros import get_hlc_futures, wma


ENTRY_BREAKOUT_BUFFER_PCT = 0.17


def tactica_entrada_cruce_wma(
    client,
    symbol: str,
    interval: str,
    wma_entry_len: int,
    sleep_seconds: int,
    side: str,
):
    if side == "long":
        print(f"\n=== [FUTUROS] Buscando ENTRADA LONG en {symbol} ===")
        print(f"Condición: vela cerrada cruza AL ALZA la WMA{wma_entry_len} en {interval}.\n")
    else:
        print(f"\n=== [FUTUROS] Buscando ENTRADA SHORT en {symbol} ===")
        print(f"Condición: vela cerrada cruza A LA BAJA la WMA{wma_entry_len} en {interval}.\n")

    last_closed_close = None
    pending_breakout = None

    while True:
        try:
            highs, lows, closes = get_hlc_futures(client, symbol, interval, limit=wma_entry_len + 5)
            if len(closes) < wma_entry_len + 3:
                print("Aún no hay suficientes velas para WMA de entrada. Esperando...")
                time.sleep(sleep_seconds)
                continue

            close_prev = closes[-2]
            close_prevprev = closes[-3]
            close_current = closes[-1]
            high_current = highs[-1]
            low_current = lows[-1]

            if last_closed_close is None:
                last_closed_close = close_prev

            new_closed = close_prev != last_closed_close

            # Evaluar breakout intravela y latcheado
            if pending_breakout:
                wma_current = wma(closes, wma_entry_len)
                current_state = "above" if close_current > wma_current else "below"

                if current_state == pending_breakout["reset_state"]:
                    pending_breakout = None
                else:
                    trigger = pending_breakout["trigger"]
                    trigger_side = pending_breakout["side"]
                    breakout = high_current >= trigger if trigger_side == "long" else low_current <= trigger
                    if breakout:
                        print(f"\n✅ [FUTUROS] Entrada {trigger_side.upper()} ejecutada por ruptura a {trigger:.4f}.")
                        return trigger

            if new_closed:
                if pending_breakout is None:
                    wma_prev = wma(closes[:-1], wma_entry_len)
                    wma_prevprev = wma(closes[:-2], wma_entry_len)

                    prev_state = "above" if close_prev > wma_prev else "below"
                    prevprev_state = "above" if close_prevprev > wma_prevprev else "below"

                    print(
                        f"[ENTRADA-FUT] Vela cerrada {interval} -> "
                        f"c_-3: {close_prevprev:.4f}, WMA_-3: {wma_prevprev:.4f}, "
                        f"c_-2: {close_prev:.4f}, WMA_-2: {wma_prev:.4f}, "
                        f"estados: {prevprev_state} -> {prev_state}"
                    )

                    if side == "long" and prevprev_state == "below" and prev_state == "above":
                        print("\n✅ [FUTUROS] Señal de ENTRADA LONG detectada (cruce alcista WMA de ENTRADA).")
                        high_cruce = highs[-2]
                        low_cruce = lows[-2]
                        rango_cruce = high_cruce - low_cruce
                        buffer = rango_cruce * ENTRY_BREAKOUT_BUFFER_PCT
                        trigger = high_cruce + buffer
                        print(
                            f"[ENTRADA-FUT] Detectado cruce WMA. Rango cruce: {rango_cruce:.4f}, "
                            f"buffer: {buffer:.4f}"
                        )
                        print(f"[ENTRADA-FUT] Trigger calculado: {trigger:.4f}")
                        pending_breakout = {
                            "side": side,
                            "trigger": trigger,
                            "reset_state": prevprev_state,
                        }

                    if side == "short" and prevprev_state == "above" and prev_state == "below":
                        print("\n✅ [FUTUROS] Señal de ENTRADA SHORT detectada (cruce bajista WMA de ENTRADA).")
                        high_cruce = highs[-2]
                        low_cruce = lows[-2]
                        rango_cruce = high_cruce - low_cruce
                        buffer = rango_cruce * ENTRY_BREAKOUT_BUFFER_PCT
                        trigger = low_cruce - buffer
                        print(
                            f"[ENTRADA-FUT] Detectado cruce WMA. Rango cruce: {rango_cruce:.4f}, "
                            f"buffer: {buffer:.4f}"
                        )
                        print(f"[ENTRADA-FUT] Trigger calculado: {trigger:.4f}")
                        pending_breakout = {
                            "side": side,
                            "trigger": trigger,
                            "reset_state": prevprev_state,
                        }

                last_closed_close = close_prev

            time.sleep(sleep_seconds)

        except KeyboardInterrupt:
            print("\nBot detenido manualmente durante la fase de entrada.")
            return None
        except Exception as e:
            print(f"Error durante la fase de entrada (Futuros): {e}")
            time.sleep(sleep_seconds)


def tactica_entrada_wma34_debajo_y_cruce_89(*args, **kwargs):
    """
    Validar que la WMA de 34 esté por debajo de la de 233 y 89
    y entrar cuando el precio cruce la WMA de 89.
    """
    pass
