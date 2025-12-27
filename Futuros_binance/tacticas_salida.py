from __future__ import annotations

import time
from config_wma_pack import WMA_FIB_LENGTHS, wma_name_from_len
from infra_futuros import format_quantity, get_hlc_futures, sonar_alarma, wma
from Trailing_dinamico import get_trailing_reference
from stop_clasico import init_stop_state, eval_stop_clasico_by_wma
from freno_emergencia import eval_freno_emergencia


STOP_BREAKOUT_BUFFER_PCT = 0.10
ATR_LEN_DEFAULT = 14
ATR_MULT_DEFAULT = 1.5


def tactica_salida_trailing_stop_wma(
    client,
    symbol: str,
    base_asset: str,
    interval: str,
    sleep_seconds: int,
    trailing_ref_mode: str,
    wma_stop_len: int | None,
    wait_on_close: bool,
    stop_rule_mode: str,
    qty_est: float,
    qty_str: str,
    entry_exec_price: float,
    entry_margin_usdt: float,
    simular: bool,
    side: str,
    entry_order_id: int | None = None,
    balance_inicial_futuros: float | None = None,
):
    stop_state = init_stop_state()
    qty_close_str = qty_str or format_quantity(abs(qty_est))
    stop_mode_norm = (stop_rule_mode or "breakout").lower()
    ref_mode_norm = (trailing_ref_mode or "fixed").lower()

    while True:
        try:
            max_wma_len = max(([wma_stop_len] if wma_stop_len else []) + WMA_FIB_LENGTHS)
            limit_needed = max(max_wma_len + 5, 120)
            highs, lows, closes = get_hlc_futures(client, symbol, interval, limit=limit_needed)
            close_current = closes[-1]
            close_prev = closes[-2]
            close_prevprev = closes[-3]
            high_current = highs[-1]
            low_current = lows[-1]
            high_prev = highs[-2]
            low_prev = lows[-2]
            price_for_stop = close_prev if wait_on_close else close_current

            freno = eval_freno_emergencia(
                client=client,
                symbol=symbol,
                interval=interval,
                side=side,
                price_for_stop=price_for_stop,
                atr_len=ATR_LEN_DEFAULT,
                atr_mult=ATR_MULT_DEFAULT,
            )
            if freno.get("action") == "close_all":
                sonar_alarma()
                stop_level = freno.get("stop_level")
                stop_txt = f"{stop_level:.4f}" if stop_level is not None else "N/D"
                print(
                    f"[FRENO] Cierre total por emergencia ATR+WMA34 @ {stop_txt} "
                    f"(atr={freno.get('atr')}, wma34={freno.get('wma34')})"
                )
                if simular:
                    print(f"[SIMULACIÓN] Cierre total qty={qty_close_str}")
                else:
                    exit_side = "SELL" if side == "long" else "BUY"
                    try:
                        client.new_order(
                            symbol=symbol,
                            side=exit_side,
                            type="MARKET",
                            quantity=qty_close_str,
                            reduceOnly=True,
                        )
                    except Exception as e:
                        print(f"❌ Error cerrando por freno emergencia: {e}")
                return

            trailing_len = None
            trailing_name = None
            if ref_mode_norm == "dynamic":
                trailing_ref = get_trailing_reference(side, closes)
                trailing_len = trailing_ref.get("trailing_len")
                trailing_name = trailing_ref.get("trailing_name")
            else:
                trailing_len = wma_stop_len if wma_stop_len and wma_stop_len > 0 else None
                trailing_name = wma_name_from_len(trailing_len) if trailing_len else None

            if trailing_len and not trailing_name:
                trailing_name = wma_name_from_len(trailing_len)

            trailing_value_current = wma(closes, trailing_len) if trailing_len else None
            trailing_value_prev = wma(closes[:-1], trailing_len) if trailing_len else None
            trailing_value_prevprev = wma(closes[:-2], trailing_len) if trailing_len else None

            stop_state, stop_decision = eval_stop_clasico_by_wma(
                side=side,
                close_current=close_current,
                close_prev=close_prev,
                close_prevprev=close_prevprev,
                high_current=high_current,
                low_current=low_current,
                high_prev=high_prev,
                low_prev=low_prev,
                trailing_value_current=trailing_value_current,
                trailing_value_prev=trailing_value_prev,
                trailing_value_prevprev=trailing_value_prevprev,
                wait_on_close=wait_on_close,
                stop_rule_mode=stop_mode_norm,
                state=stop_state,
                buffer_ratio=STOP_BREAKOUT_BUFFER_PCT,
            )

            trailing_name_txt = trailing_name or "-"
            trailing_val_txt = f"{trailing_value_current:.4f}" if trailing_value_current is not None else "N/D"
            print(
                f"[STOP] trailing={trailing_name_txt}({trailing_len})@{trailing_val_txt} action={stop_decision.get('action')}"
            )

            if stop_decision.get("pending_trigger") is not None:
                print(
                    f"[STOP] Trigger preparado: {stop_decision.get('pending_trigger'):.4f} "
                    f"(buffer={stop_decision.get('pending_buffer'):.4f})"
                )

            if stop_decision.get("action") == "close_all":
                exit_price = stop_decision.get("exit_price", price_for_stop)
                sonar_alarma()
                lado_txt = "LONG" if side == "long" else "SHORT"
                print(f"\n=== [FUTUROS] SEÑAL DE SALIDA {lado_txt} DETECTADA (STOP CLÁSICO) ===")
                print(f"Motivo:   {stop_decision.get('reason')}")
                print(f"Salida a: {exit_price:.4f}")
                print(f"Cantidad a cerrar: {qty_close_str} {base_asset}")
                print(f"Modo: {'SIMULACIÓN' if simular else 'REAL'}\n")

                if not simular:
                    exit_side = "SELL" if side == "long" else "BUY"
                    try:
                        client.new_order(
                            symbol=symbol,
                            side=exit_side,
                            type="MARKET",
                            quantity=qty_close_str,
                            reduceOnly=True,
                        )
                    except Exception as e:
                        print(f"❌ Error al enviar la orden de cierre en Futuros: {e}")
                else:
                    print("SIMULACIÓN: No se envió orden real de cierre.")

                print("\nBot Futuros finalizado tras ejecutar la salida.\n")
                return

            time.sleep(sleep_seconds)

        except KeyboardInterrupt:
            print("\nBot detenido manualmente durante la fase de STOP en Futuros.")
            return
        except Exception as e:
            print(f"Error en fase de STOP (Futuros): {e}")
            time.sleep(sleep_seconds)


def tactica_salida_trailing_3_fases(*args, **kwargs):
    """
    Trailing stop en 3 fases:
    - Un porcentaje en WMA 34
    - Otro en WMA 89
    - Otro en WMA 233
    """
    pass
