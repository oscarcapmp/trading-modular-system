## Filosofía operativa
- Prioriza estructura de precio vía WMAs; disciplina de entrada/salida por encima de maximizar profit puntual.
- Simulación primero, real solo después de validar logs y parámetros.
- Menos superficie: órdenes MARKET para entrar/salir, sin TP/limit nativos; observabilidad por consola.

## Playbook de entrada
- Configuración: símbolo (Futuros USDT-M), lado, intervalo, `wma_entry_len` (0 = market inmediato), modo simulación/real.
- Validación previa: `validaciones.py` imprime orden de WMAs (`WMAs alineadas` o `Ordenada hasta ...`).
- Señal: `tactica_entrada_cruce_wma` detecta cruce de vela cerrada sobre la WMA de entrada, calcula buffer 17% del rango y guarda trigger.
- Estado “waiting for breakout”: trigger latcheado; si la vela actual regresa al estado previo se invalida y se reinicia la búsqueda.
- Confirmación: en breakout se ejecuta MARKET (o solo log en simulación), capturando qty, precio de entrada y apalancamiento.

## Playbook de gestión
- Referencia de trailing:
  - Fijo: WMA definida por usuario.
  - Dinámico: `Trailing_dinamico.get_trailing_reference` cambia la WMA de stop en la escalera 144/233/377/610/987 según cruces.
- Regla de stop (`stop_rule_mode`):
  - `breakout`: espejo de la entrada con buffer; latchea trigger y cierra al romperlo.
  - `cross`: cierra al cruce directo con la WMA de stop.
- Freno de emergencia: activo cuando el trailing es dinámico; ATR14 + WMA34 calcula un único nivel para cierre total reduceOnly.
- Storytelling/targets opcionales: “Traguito” 2×ATR desde entrada o toque WMA233/377 para cerrar un porcentaje (reduceOnly).

## Playbook de salida
- Stop clásico: `stop_clasico.py` decide cierre total por cruce o breakout+buffer según la regla.
- Freno de emergencia: `[FRENO]` muestra nivel ATR+WMA34; al tocarlo cierra toda la posición.
- Targets parciales: `🎯 [TARGET]` al disparar TRAGUITO o toque WMA; `✅ [TARGET]` si se ejecuta (solo log en simulación).
- Cierre manual: menú opción 3 permite ver/cerrar posición completa a MARKET sin trailing.

## Observabilidad (logs)
- Entrada: `[ENTRADA-FUT] Waiting for breakout @ ...` cuando hay trigger; `✅ [FUTUROS] Entrada ... ejecutada` al disparar.
- Trailing: `[STOP] trailing=... action=...` para cada ciclo; `[STOP] Trigger preparado: ...` cuando hay buffer armado.
- Freno: `[FRENO] nivel_fijo=...` en cada iteración; al disparar imprime motivo y cierra.
- Alineación: `WMAs alineadas ✅ ...` o `WMAs NO alineadas ❌ ...` al inicio de nueva operación.
- Alerta sonora: `infra_futuros.sonar_alarma` en stop/freno para no depender de UI externa.

## Fuera de alcance (scope out)
- NO hay reporting de resultados ni P&G.
- NO hay métricas históricas ni almacenamiento de performance.
- Sin dashboards ni persistencia; todo se observa por consola.
