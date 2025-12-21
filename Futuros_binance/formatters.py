def fmt_resumen_config(cfg: dict) -> str:
    lines = [
        "=== RESUMEN CONFIGURACIÓN FUTUROS ===",
        f"Símbolo:             {cfg.get('symbol')}",
        f"Lado estrategia:     {str(cfg.get('side')).upper()}",
        f"Modo:                {'SIMULACIÓN' if cfg.get('simular') else 'REAL'}",
        f"Intervalo:           {cfg.get('interval')}",
        f"WMA de ENTRADA:      {cfg.get('wma_entry_len')}",
    ]
    if cfg.get("trailing_dinamico_on"):
        lines.append("Salida:             Trailing dinámico 2 fases")
        lines.append(f"Fase 1 (%):         {cfg.get('pct_fase1')}")
        lines.append("WMA de STOP:        (IGNORADA por trailing dinámico)")
    else:
        lines.append("Salida:             Stop clásico por WMA")
        lines.append(f"WMA de STOP:        {cfg.get('wma_stop_len')}")
    lines.extend(
        [
            f"Freno ATR local:    {'Sí' if cfg.get('emergency_atr_on') else 'No'} (k={cfg.get('atr_mult')})",
            f"Sleep (segundos):   {cfg.get('sleep_seconds')}",
            f"Esperar cierre STOP:{cfg.get('wait_on_close')}",
            f"Apalancamiento max: {cfg.get('max_lev')}x",
            f"Balance USDT:       {cfg.get('balance_usdt'):.4f}",
            f"Poder de trading:   {cfg.get('trading_power'):.4f} USDT",
            "",
        ]
    )
    return "\n".join(lines)


def fmt_resumen_posicion(pos: dict | None) -> str:
    if not pos:
        return ""
    lines = [
        "=== POSICIÓN DETECTADA ===",
        f"Símbolo:        {pos.get('symbol')}",
        f"Lado:           {str(pos.get('side')).upper()}",
        f"Cantidad:       {pos.get('qty_est')}",
        f"Precio entrada: {pos.get('entry_exec_price')}",
        f"Leverage:       {pos.get('leverage')}x",
        f"Margen aprox:   {pos.get('entry_margin_usdt'):.4f} USDT",
        "",
    ]
    return "\n".join(lines)


def fmt_bloque(titulo: str, cuerpo: str) -> str:
    return f"=== {titulo} ===\n{cuerpo}"
