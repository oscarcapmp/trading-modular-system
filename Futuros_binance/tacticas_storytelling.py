from infra_futuros import atr, get_hlc_futures
from target import place_take_profit_market_50


def storytelling_traguito_pa_las_almas(
    client,
    symbol: str,
    side: str,
    entry_exec_price: float,
    interval: str,
    simular: bool,
) -> dict | None:
    try:
        highs, lows, closes = get_hlc_futures(client, symbol, interval, limit=120)
    except Exception as e:
        print(f"[WARN] No se pudo leer HLC para storytelling: {e}")
        return None

    if len(closes) < 15:
        print("[WARN] Datos insuficientes para ATR storytelling.")
        return None

    atr_val = atr(highs, lows, closes, 14)
    if atr_val is None:
        print("[WARN] ATR storytelling no disponible.")
        return None

    if side == "long":
        target_price = entry_exec_price + 2 * atr_val
    else:
        target_price = entry_exec_price - 2 * atr_val

    print("# traguito pa las almas")
    print(
        f"[STORY] symbol={symbol} side={side.upper()} entry_real={entry_exec_price:.4f} "
        f"ATR14={atr_val:.4f} target={target_price:.4f} pct=50%"
    )

    try:
        res = place_take_profit_market_50(
            client=client,
            symbol=symbol,
            side=side,
            target_price=target_price,
            simular=simular,
        )
    except Exception as e:
        print(f"[WARN] No se pudo colocar el TARGET storytelling: {e}")
        return None

    if res.get("error"):
        print(f"[WARN] Target storytelling no colocado: {res.get('error')}")
        return None

    return {
        "enabled": True,
        "order_id": res.get("orderId"),
        "target_price": target_price,
        "printed_fill": False,
    }
