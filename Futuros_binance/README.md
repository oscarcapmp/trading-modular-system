## 1. Qué es
Bot simple para Futuros USDT-M: entra por cruce de WMA (long/short), abre con orden MARKET y sale con trailing basado en otra WMA. Permite modo simulación para no enviar órdenes reales.
- Incluye freno de emergencia por ATR (1.5×ATR desde la WMA de stop) para cerrar si el precio se aleja demasiado.

### Notas rápidas
- Desde 2025-12-09 Binance mueve stops condicionales USDT-M a Algo Orders; el freno nativo ahora es un STOP_MARKET CONDITIONAL (Algo Order) server-side.
- Freno de emergencia nativo: se coloca como Algo Order al abrir; sobrevive si el servidor cae.
- Si el trailing cierra, el bot cancela el STOP nativo, valida que la posición quede en 0 y que no existan órdenes (openOrders/openAlgoOrders vacíos).
- Trailing dinámico 2 fases (opcional): Fase 1 cierra un porcentaje sobre WMA más lejana (34/55), Fase 2 cambia a WMA89 tras cruce 233/377 para cerrar el resto.

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
  - trailing dinámico 2 fases (s/n) y % de cierre Fase 1
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

## 7. WMA Pack (Pollita…Camaleona)
- WMAs configurables: Pollita (34), Celeste (55), Dorada (89), Carmesí (233), Blanca (377), Lima (610), Camaleona (987).
- Alineadas en LONG si: Pollita < Celeste < Dorada < Carmesí < Blanca < Lima < Camaleona (en SHORT se invierte el orden).
- Ejemplo de log: `WMAs alineadas ✅: Pollita < Celeste < Dorada < Carmesí < Blanca < Lima < Camaleona` o `WMAs NO alineadas ❌: rompen orden: Dorada, Blanca | datos insuficientes: Lima`.

## 8. Validación de freno nativo (Algo Orders)
- UI de Binance Futures USDT-M → pestaña Stop/Condicional.
- CLI/logs: se usa `get_open_algo_orders(symbol)` para listar y se cancelan con `cancel_all_open_algo_orders(symbol)` al cerrar.

## 8. Buenas prácticas personales
- Probar siempre en simulación antes de usar real.
- Usar símbolos líquidos y conocidos.
- No guardar claves en el repo ni compartirlas.
- Revisar lot sizes y notional mínimo antes de operar.
- Mantener WMAs y sleep en valores razonables para el timeframe.

## 9. Licencia / Aviso
Uso personal; no es asesoría financiera. Operar conlleva riesgo.  
Mini diagrama: `main -> operacion -> (tactica_entrada + tactica_salida) -> Binance`
