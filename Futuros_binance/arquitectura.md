## 1. Objetivo
Bot para Futuros USDT-M que entra por cruce de WMA (long/short), abre posición (market), y sale con trailing basado en otra WMA. Soporta modo simulación vs real y reporta la operación al cierre.

## 2. Modelo mental del proyecto
- Infraestructura: cliente Binance, WMAs, helpers de lotes, balance, prechecks.
- Operación (Compra / Venta / Mantener): abrir/cerrar posiciones y orquestar trailing.
- Tácticas de entrada: reglas de cuándo disparar la entrada.
- Tácticas de salida: reglas de trailing/stop.
- Main / Orquestador: entrada de usuario y disparo de la estrategia.

## 3. Mapa de archivos
- infra_futuros.py: cliente UMFutures, WMA, helpers de cantidades, lot size, balance, precheck y alarma.
- tacticas_entrada.py: `tactica_entrada_cruce_wma` (cruce de vela cerrada vs WMA) y placeholder WMA34<89<233.
- tacticas_salida.py: `tactica_salida_trailing_stop_wma` (trailing por WMA) y placeholder de trailing en 3 fases.
- operacion.py: posición actual, cierre market, compra long/short por cruce WMA, placeholder de mantener.
- bot_futuros_main.py: pide inputs al usuario y ejecuta la estrategia completa o solo trailing.
- trabajar_futures_wma_exit_bot.py: referencia a la nueva modularización.

## 4. Flujo de ejecución
bot_futuros_main.py → pide inputs → llama Operación → usa Tácticas (entrada + trailing) → ejecuta órdenes (o simula) → imprime resumen.

## 5. Puntos de extensión
- Nueva táctica de entrada: crear función en tacticas_entrada.py y llamarla desde operacion.py.
- Nueva táctica de salida (3 fases, etc.): implementar en tacticas_salida.py y sustituir la llamada en operacion.py.
- Nuevo modo de compra (limit/market): añadir función en operacion.py usando los mismos helpers (lot size, formato) y ajustar el main a usarla.

## 6. Decisiones y límites
- Sin clases: todo en funciones para simplicidad.
- Solo Futuros USDT-M via UMFutures.
- Apalancamiento máximo fijo por función `get_max_leverage_symbol` (20x en esta versión).
- Comisiones: se infiere por diferencia de balance (la lectura de trades está disponible pero no se usa).
- Entradas y salidas actuales solo MARKET; no hay stop-limit ni órdenes limit.
- Trailing incluye freno de emergencia: si el precio se aleja 1.5×ATR (ATR 14) desde la WMA de stop, se cierra inmediato.

## 7. TODO
- Implementar `tactica_entrada_wma34_debajo_y_cruce_89`.
- Implementar `tactica_salida_trailing_3_fases`.
- Agregar modo de apertura LIMIT opcional.
- Añadir stop-limit de emergencia.
- Parametrizar apalancamiento máximo por símbolo cuando esté disponible.
