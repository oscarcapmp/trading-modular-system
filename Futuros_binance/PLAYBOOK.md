## Deploy en VPS
- Instalar Python 3.10+ y `binance-futures-connector`.
- Exportar `BINANCE_API_KEY` y `BINANCE_API_SECRET`.
- Clonar o pull del repo en la VPS.

## Ejecutar bot
- Desde `Futuros_binance`: `python bot_futuros_main.py`.
- Usar modo simulación primero para validar.

## Revert en GitHub
- Hacer revert desde GitHub UI sobre el commit problemático.
- Pull en la VPS para sincronizar.

## Sincronizar VPS
- `git pull origin main` en la VPS.
- Verificar que no haya cambios locales inesperados.

## Checklist antes de operar en REAL
- Claves cargadas y símbolo correcto.
- Modo simulación probado.
- Intervalo, WMAs y % trailing configurados.
- Balance y lot sizes revisados.
- Conexión estable y logs visibles.
