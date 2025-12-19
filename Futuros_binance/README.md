## 1. Qué es
Bot simple para Futuros USDT-M: entra por cruce de WMA (long/short), abre con orden MARKET y sale con trailing basado en otra WMA. Permite modo simulación para no enviar órdenes reales.
- Incluye freno de emergencia por ATR (1.5×ATR desde la WMA de stop) para cerrar si el precio se aleja demasiado.

## 2. Requisitos
- Python 3.10+ recomendado.
- Dependencia: `binance-futures-connector`.
- Probado en macOS (alarma usa `afplay`/`say`); en otros sistemas solo imprime beeps.

## 3. Configuración rápida
- Variables de entorno:
  - `BINANCE_API_KEY`
  - `BINANCE_API_SECRET`
- Ejemplo (mac):
  ```bash
  export BINANCE_API_KEY="..."
  export BINANCE_API_SECRET="..."
  ```

## 4. Cómo ejecutar
- Desde la carpeta `Futuros_binance`:
  ```bash
  python bot_futuros_main.py
  ```
- Inputs solicitados (en orden):
  - símbolo (ej. BTCUSDT)
  - simular (s/n)
  - intervalo (ej. 1m, 5m, 15m)
  - segundos de espera entre chequeos
  - WMA de entrada
  - WMA de stop (trailing)
  - esperar cierre real para stop (true/false)
  - lado (long/short)
  - poder a usar (USDT) cuando se pide
  - opción de menú: ver posición, cerrar, estrategia completa o solo trailing

## 5. Modo simulación vs real
- Simulación: no envía órdenes a Binance; muestra lo que haría.
- Real: envía órdenes MARKET al detectar entrada/salida.
- Elige “s” en “¿Simular?” para modo seguro.

## 6. Estructura mental (mini)
- Infraestructura: cliente Binance, WMA, helpers de cantidades y balance.
- Operación: abrir/cerrar posiciones y orquestar trailing.
- Tácticas de entrada: reglas de disparo (cruce WMA).
- Tácticas de salida: trailing WMA.
- Main: `bot_futuros_main.py` (entrypoint).

## 7. Buenas prácticas personales
- Probar siempre en simulación antes de usar real.
- Usar símbolos líquidos y conocidos.
- No guardar claves en el repo ni compartirlas.
- Revisar lot sizes y notional mínimo antes de operar.
- Mantener WMAs y sleep en valores razonables para el timeframe.

## 8. Licencia / Aviso
Uso personal; no es asesoría financiera. Operar conlleva riesgo.  
Mini diagrama: `main -> operacion -> (tactica_entrada + tactica_salida) -> Binance`
