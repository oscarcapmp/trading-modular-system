## Qué es este repo
Bot CLI para Futuros USDT-M: entra por cruce de WMA (long/short), ejecuta MARKET y gestiona la salida con trailing WMA fijo o escalera dinámica. Incluye freno de emergencia ATR+WMA34 y modo simulación para operar sin enviar órdenes reales.

## Qué sí hace esta versión
- Detecta cruce de WMA en vela cerrada con buffer y latchea trigger hasta breakout.
- Abre posiciones MARKET (long/short) con sizing basado en balance y leverage configurado.
- Gestiona salidas con trailing WMA fijo o dinámico (144/233/377/610/987) y reglas de cruce o breakout.
- Aplica freno de emergencia (ATR14 + WMA34) y soporta targets parciales opcionales (Traguito 2×ATR o toque WMA233/377).
- Provee logs verbosos y alarma sonora para operar desde terminal.

## Qué no hace esta versión
- NO hay reporting de resultados ni reporte P&G.
- NO hay métricas históricas ni almacenamiento de performance.
- Sin dashboards ni UI; solo consola.

## Cómo ejecutar
Desde `Futuros_binance`:
```bash
python bot_futuros_main.py
```
Requiere Python 3.10+, `binance-futures-connector` instalado y variables `BINANCE_API_KEY`, `BINANCE_API_SECRET` exportadas. Primer menú: nueva operación, gestionar posición abierta o gestión manual (ver/cerrar).

## Cómo navegar el código (orden sugerido)
1) `bot_futuros_main.py` — menú y configuración de modos.
2) `operacion.py` — estrategias long/short, sizing y arranque de trailing.
3) `tacticas_entrada.py` / `tacticas_salida.py` — reglas de entrada y stop/trailing.
4) `Trailing_dinamico.py`, `stop_clasico.py`, `freno_emergencia.py`, `target.py` — piezas de gestión.
5) `config_wma_pack.py` y `indicators/wma_pack.py` — SSoT de WMAs y cálculos.
6) `infra_futuros.py` — cliente Binance, helpers de lotes/balance/ATR/WMA.
Más detalle en `ARCHITECTURE.md` (estructura) y `PLAYBOOK.md` (operación).

## Flujo de trabajo GitHub + VPS (fuente de verdad)
- GitHub (`origin/main`) es la única fuente de verdad. El VPS nunca genera cambios.
- Mac (desarrollo):
  ```bash
  cd "/Users/oscarquantico/Library/CloudStorage/OneDrive-Personal/OKA PROGRAMADOR/TradingSystem"
  git status
  git add .
  git commit -m "mensaje claro"
  git push origin main
  ```
- VPS (ejecución):
  ```bash
  cd ~/trading-modular-system
  git fetch origin
  git reset --hard origin/main
  cd ~/trading-modular-system/Futuros_binance
  ```
- Ejecutar el bot solo después de sincronizar contra `origin/main`.

## Roadmap (next version)
- Reporting de resultados.
- P&G consolidado.
- Métricas históricas y persistencia.

## Estado del proyecto
Versión cerrada/estable. Cambios futuros se agregan en la siguiente versión con reporting y P&G.
