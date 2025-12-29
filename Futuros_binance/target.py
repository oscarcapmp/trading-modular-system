from infra_futuros import format_quantity, floor_to_step


def should_trigger_touch_wma(side: str, price_now: float, wma_now: float) -> bool:
    """
    Regla de 'toque' simple:
    - LONG: dispara si price_now <= wma_now (tocó o cruzó hacia abajo)
    - SHORT: dispara si price_now >= wma_now (tocó o cruzó hacia arriba)
    """
    side_norm = (side or "").lower()
    if side_norm == "long":
        return price_now <= wma_now
    if side_norm == "short":
        return price_now >= wma_now
    return False


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

    try:
        exch = client.exchange_info()
        lot_filter = None
        for s in exch.get("symbols", []):
            if s.get("symbol") == symbol:
                for f in s.get("filters", []):
                    if f.get("filterType") == "LOT_SIZE":
                        lot_filter = f
                        break
                break
        if lot_filter:
            step_size = float(lot_filter.get("stepSize", "0"))
            min_qty = float(lot_filter.get("minQty", "0"))
        else:
            step_size = 0.0
            min_qty = 0.0
    except Exception:
        step_size = 0.0
        min_qty = 0.0

    qty_total = abs(amt)
    qty_close_raw = qty_total * pct
    if step_size > 0:
        qty_close = floor_to_step(qty_close_raw, step_size)
    else:
        qty_close = qty_close_raw

    if qty_close <= 0 or (min_qty and qty_close < min_qty):
        return {"skipped": True, "reason": "qty<minQty"}

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
        quantity=str(qty_close_str),
    )

    return {
        "orderId": order.get("orderId"),
        "qty_close": qty_close,
        "qty_close_str": qty_close_str,
        "pct": pct,
        "side_order": order_side,
    }
