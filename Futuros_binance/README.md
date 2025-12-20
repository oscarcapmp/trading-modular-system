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
- Primer prompt: menú principal con 3 modos:
  - Nueva operación: pide modo simulación/real, timeframe, WMA de entrada o market, tipo de salida (stop WMA o trailing dinámico) y freno ATR local.
  - Posición ya abierta: valida que exista posición, muestra resumen real y permite solo gestionar con stop WMA o trailing dinámico + ATR.
  - Gestión manual: ver posición o cerrarla completa (MARKET) sin trailing ni ATR.

## 5. Modo simulación vs real
- Simulación: no envía órdenes a Binance; muestra lo que haría.
- Real: envía órdenes MARKET al detectar entrada/salida.
- Elige “s” en “¿Simular?” para modo seguro.

## Gestión de riesgo y stops
- El freno de emergencia es un STOP MARKET ejecutado por el bot (1.5×ATR sobre WMA de stop).
- No existe stop nativo en Binance en esta etapa; si el servidor cae, se acepta ese riesgo conscientemente.
- Se prioriza simplicidad y control del bot sobre la operativa.

## 6. Estructura mental (mini)
- Infraestructura: cliente Binance, WMA, helpers de cantidades y balance.
- Operación: abrir/cerrar posiciones y orquestar trailing.
- Tácticas de entrada: reglas de disparo (cruce WMA).
- Tácticas de salida: trailing WMA.
- Main: `bot_futuros_main.py` (entrypoint).

## 7. WMA Pack (Pollita…Camaleona)
- WMAs configurables: Pollita (34), Celeste (55), Dorada (89), Carmesí (233), Blanca (377), Camaleona (987).
- Alineadas si: Pollita < Celeste < Dorada < Carmesí < Blanca < Camaleona.
- Ejemplo de log: `WMAs alineadas ✅: Pollita < Celeste < Dorada < Carmesí < Blanca < Camaleona` o `WMAs NO alineadas ❌: faltan por alinear: Dorada, Blanca`.

## 8. Buenas prácticas personales
- Probar siempre en simulación antes de usar real.
- Usar símbolos líquidos y conocidos.
- No guardar claves en el repo ni compartirlas.
- Revisar lot sizes y notional mínimo antes de operar.
- Mantener WMAs y sleep en valores razonables para el timeframe.

## 9. Licencia / Aviso
Uso personal; no es asesoría financiera. Operar conlleva riesgo.  
Mini diagrama: `main -> operacion -> (tactica_entrada + tactica_salida) -> Binance`
