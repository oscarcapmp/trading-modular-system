# tacticas_entrada.py
import time
from infra_futuros import wma, get_closes_futuros


def tactica_entrada_cruce_wma(
    client,
    symbol: str,
    interval: str,
    wma_entry_len: int,
    sleep_seconds: int,
    side: str,  # "long" o "short"
):
    """
    TÁCTICA DE ENTRADA: por cruce de WMA.

    - LONG: vela cerrada pasa de estar debajo de la WMA a estar encima.
    - SHORT: vela cerrada pasa de encima a debajo.
    """
    if side == "long":
        print(f"\n=== [TÁCTICA ENTRADA] Buscando ENTRADA LONG en {symbol} por cruce WMA{wma_entry_len} ===")
    else:
        print(f"\n=== [TÁCTICA ENTRADA] Buscando ENTRADA SHORT en {symbol} por cruce WMA{wma_entry_len} ===")

    last_closed_close = None

    while True:
        try:
            closes = get_closes_futuros(client, symbol, interval, limit=wma_entry_len + 5)
            if len(closes) < wma_entry_len + 3:
                print("Aún no hay suficientes velas para WMA de entrada. Esperando...")
                time.sleep(sleep_seconds)
                continue

            close_prev = closes[-2]      # cierre de la última vela cerrada
            close_prevprev = closes[-3]  # cierre de la vela anterior a esa

            if last_closed_close is None:
                last_closed_close = close_prev

            if close_prev != last_closed_close:
                # WMA calculada sin incluir la vela actual en formación
                wma_prev = wma(closes[:-1], wma_entry_len)
                wma_prevprev = wma(closes[:-2], wma_entry_len)

                prev_state = "above" if close_prev > wma_prev else "below"
                prevprev_state = "above" if close_prevprev > wma_prevprev else "below"

                print(
                    f"[ENTRADA] {symbol} {interval} -> "
                    f"c_-3: {close_prevprev:.4f}, WMA_-3: {wma_prevprev:.4f}, "
                    f"c_-2: {close_prev:.4f}, WMA_-2: {wma_prev:.4f}, "
                    f"estados: {prevprev_state} -> {prev_state}"
                )

                # LONG: cruce alcista (below -> above)
                if side == "long" and prevprev_state == "below" and prev_state == "above":
                    print("\n✅ Señal de ENTRADA LONG detectada (cruce alcista WMA).")
                    ticker = client.ticker_price(symbol=symbol)
                    current_price = float(ticker["price"])
                    return current_price

                # SHORT: cruce bajista (above -> below)
                if side == "short" and prevprev_state == "above" and prev_state == "below":
                    print("\n✅ Señal de ENTRADA SHORT detectada (cruce bajista WMA).")
                    ticker = client.ticker_price(symbol=symbol)
                    current_price = float(ticker["price"])
                    return current_price

                last_closed_close = close_prev

            time.sleep(sleep_seconds)

        except KeyboardInterrupt:
            print("\nBot detenido manualmente durante la táctica de entrada.")
            return None
        except Exception as e:
            print(f"Error durante la táctica de entrada: {e}")
            time.sleep(sleep_seconds)


def tactica_entrada_wma34_debajo_y_cruce_89(
    client,
    symbol: str,
    interval: str,
    sleep_seconds: int,
    side: str,
):
    """
    TÁCTICA ESPECIAL (tu regla mental):

    De entrada:
    a. Validar que la WMA de 34 esté por debajo de la de 233 y 89
    b. Entrar cuando cruce la de 89

    Implementación:
    - Primero revisa WMA34, WMA89, WMA233.
    - Si se cumple W34 < W89 y W34 < W233, entonces llama a la táctica de
      cruce simple usando WMA89.
    """
    len_34 = 34
    len_89 = 89
    len_233 = 233

    print("\n=== [TÁCTICA ENTRADA] WMA34 < WMA89 y WMA233 + cruce WMA89 ===")

    while True:
        try:
            limit = max(len_34, len_89, len_233) + 3
            closes = get_closes_futuros(client, symbol, interval, limit=limit)

            if len(closes) < limit:
                print("Aún no hay suficientes velas para WMA34/89/233. Esperando...")
                time.sleep(sleep_seconds)
                continue

            w34 = wma(closes, len_34)
            w89 = wma(closes, len_89)
            w233 = wma(closes, len_233)

            print(
                f"[CHECK WMA] {symbol} {interval} -> "
                f"W34: {w34:.4f}, W89: {w89:.4f}, W233: {w233:.4f}"
            )

            # Condición previa: WMA34 debajo de ambas
            if w34 < w89 and w34 < w233:
                print("✅ Condición previa cumplida (WMA34 < WMA89 y WMA233). Ahora esperamos cruce en WMA89.")
                # Reutilizamos la táctica de cruce simple sobre WMA89
                return tactica_entrada_cruce_wma(
                    client=client,
                    symbol=symbol,
                    interval=interval,
                    wma_entry_len=len_89,
                    sleep_seconds=sleep_seconds,
                    side=side,
                )

            time.sleep(sleep_seconds)

        except KeyboardInterrupt:
            print("\nBot detenido manualmente durante la táctica WMA34<89,233.")
            return None
        except Exception as e:
            print(f"Error en táctica WMA34<89,233: {e}")
            time.sleep(sleep_seconds)
