from infra_futuros import format_quantity


def place_take_profit_market_50(client, symbol: str, side: str, target_price: float, simular: bool) -> dict:
    """
    Envía (o simula) un TAKE_PROFIT_MARKET para cerrar el 50% de la posición.
    """
    # Import interno para evitar ciclos
    from operacion import get_current_position

    pos = get_current_position(client, symbol)
    if not pos:
        return {"error": "no_position"}

    try:
        amt = float(pos.get("positionAmt", "0"))
    except Exception:
        return {"error": "invalid_position"}

    qty_total = abs(amt)
    qty_50 = qty_total * 0.5
    qty_50_str = format_quantity(qty_50)

    if simular:
        return {
            "simulated": True,
            "qty": qty_50,
            "qty_str": qty_50_str,
            "target_price": target_price,
        }

    side_order = "SELL" if side == "long" else "BUY"
    order = client.new_order(
        symbol=symbol,
        side=side_order,
        type="TAKE_PROFIT_MARKET",
        stopPrice=target_price,
        reduceOnly=True,
        quantity=qty_50_str,
    )

    return {
        "orderId": order.get("orderId"),
        "target_price": target_price,
        "qty_50": qty_50,
        "qty_50_str": qty_50_str,
        "side_order": side_order,
    }


def is_order_filled(client, symbol: str, order_id: int) -> tuple[bool, dict]:
    """
    Consulta el estado de la orden. Retorna (filled, order_data).
    """
    try:
        order = client.get_order(symbol=symbol, orderId=order_id)
    except Exception:
        order = client.query_order(symbol=symbol, orderId=order_id)

    status = order.get("status")
    filled = status in ("FILLED",)
    return filled, order
