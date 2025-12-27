from infra_futuros import format_quantity


def close_market_reduceonly_pct(client, symbol: str, side: str, pct: float, simular: bool) -> dict:
    """
    Cierra a MARKET (reduceOnly) un porcentaje de la posición actual.
    side: long/short
    pct: 0.50 -> 50%
    """
    from operacion import get_current_position  # import local para evitar ciclos

    pos = get_current_position(client, symbol)
    if not pos:
        return {"error": "no_position"}

    try:
        amt = float(pos.get("positionAmt", "0"))
    except Exception:
        return {"error": "invalid_position"}

    qty_total = abs(amt)
    qty_close = qty_total * pct
    qty_close_str = format_quantity(qty_close)

    if simular:
        return {
            "simulated": True,
            "qty": qty_close,
            "qty_str": qty_close_str,
            "pct": pct,
        }

    side_norm = (side or "").lower()
    order_side = "SELL" if side_norm == "long" else "BUY"
    order = client.new_order(
        symbol=symbol,
        side=order_side,
        type="MARKET",
        reduceOnly=True,
        quantity=qty_close_str,
    )

    return {
        "orderId": order.get("orderId"),
        "qty_close": qty_close,
        "qty_close_str": qty_close_str,
        "pct": pct,
        "side_order": order_side,
    }
