try:
    from salida_stop_clasico import tactica_salida_stop_clasico
    from salida_trailing_fases import tactica_salida_trailing_fases
except ImportError:
    from Futuros_binance.salida_stop_clasico import tactica_salida_stop_clasico
    from Futuros_binance.salida_trailing_fases import tactica_salida_trailing_fases


def tactica_salida_trailing_stop_wma(
    client,
    symbol: str,
    base_asset: str,
    interval: str,
    sleep_seconds: int,
    wma_stop_len: int,
    wait_on_close: bool,
    qty_est: float,
    qty_str: str,
    entry_exec_price: float,
    entry_margin_usdt: float,
    simular: bool,
    side: str,
    trailing_dinamico_on: bool,
    entry_order_id: int | None = None,
    balance_inicial_futuros: float | None = None,
    emergency_atr_on: bool = True,
    atr_len: int = 14,
    atr_mult: float = 1.5,
    pct_fase1: float = 50.0,
):
    if trailing_dinamico_on:
        return tactica_salida_trailing_fases(
            client=client,
            symbol=symbol,
            base_asset=base_asset,
            interval=interval,
            sleep_seconds=sleep_seconds,
            wma_stop_len=wma_stop_len,
            wait_on_close=wait_on_close,
            qty_est=qty_est,
            qty_str=qty_str,
            entry_exec_price=entry_exec_price,
            entry_margin_usdt=entry_margin_usdt,
            simular=simular,
            side=side,
            trailing_dinamico_on=trailing_dinamico_on,
            entry_order_id=entry_order_id,
            balance_inicial_futuros=balance_inicial_futuros,
            emergency_atr_on=emergency_atr_on,
            atr_len=atr_len,
            atr_mult=atr_mult,
            pct_fase1=pct_fase1,
        )
    return tactica_salida_stop_clasico(
        client=client,
        symbol=symbol,
        base_asset=base_asset,
        interval=interval,
        sleep_seconds=sleep_seconds,
        wma_stop_len=wma_stop_len,
        wait_on_close=wait_on_close,
        qty_est=qty_est,
        qty_str=qty_str,
        entry_exec_price=entry_exec_price,
        entry_margin_usdt=entry_margin_usdt,
        simular=simular,
        side=side,
        trailing_dinamico_on=trailing_dinamico_on,
        entry_order_id=entry_order_id,
        balance_inicial_futuros=balance_inicial_futuros,
        emergency_atr_on=emergency_atr_on,
        atr_len=atr_len,
        atr_mult=atr_mult,
        pct_fase1=pct_fase1,
    )


def tactica_salida_trailing_3_fases(*args, **kwargs):
    """
    Trailing stop en 3 fases:
    - Un porcentaje en WMA 34
    - Otro en WMA 89
    - Otro en WMA 233
    """
    pass
