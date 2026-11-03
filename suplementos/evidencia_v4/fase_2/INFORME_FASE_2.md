# Informe fase 2

Fecha de corte: 31 de octubre de 2026 (America/Bogota). Evidencia nueva posterior a V3; datos sintéticos. No se editó el artículo V3 ni se redactó V4.

## Objetivo y estado

Estado: **RESUELTA**. Alcance y criterios de esta fase se evalúan computacionalmente, sin atribuir validez clínica.

## Tareas realizadas, implementación y resultados

Motor ampliado optativo con fases y requisitos, preempción inmediata o en límites, reducción de capacidad que pausa y libera, riesgos competidores y deterioro experimental de rango. F original mantiene relajación/velocidad; utilización por staff real o alternativa resource_peak. J penaliza todos los destinos no completados; llegada inicial se incluye en denominador. Reinicio exacto probado. No modifica automáticamente UI anterior.

## Archivos y funciones

| Archivo (dentro de gemelo_digital salvo ../) | Función/clase | Cambio | Motivo | Prueba | Impacto experimental |
| --- | --- | --- | --- | --- | --- |
| motor/initial_state.py | Phase,InitialPatient,InitialState,from_operational | Contratos/ocupación/procedencia | Inicio ocupado y rechazo de datos faltantes | test_initial_*,test_operational_* | Solo ruta V4 |
| motor/model_v4.py | Dynamics,simulate | Fases, interrupciones, turnos, destinos, checkpoint | Ampliación optativa sin editar V3 | 25 tests y campaña | Cambia dinámica en extended; legacy delega intacto |
| motor/calibration_v4.py | calibrate,validate_holdout,calibrated_inputs | Estimación y cohortes calibradas explícitas | Procedimiento probado con datos sintéticos | recuperación/leakage/inputs | Cambios solo si se opta por ajuste |
| motor/scenario_graph_v4.py | ScenarioRequest,execute,build_graph,answer_scenario | Flujo separado StateGraph y contratos | Escenarios verificables sin inventar cifras | 5 tests/20 tareas | No cambia asistente ML |
| motor/v4_workflow.py | diagnose,pilot,experiment,benchmark,figures | Ejecución, protocolos y análisis | Evidencia posterior aV3 sin sobrescritura | CSV/JSON/logs/figuras | Resultados nuevos en evidencia_v4 |
| motor/uncertainty_v4.py | CLI | Experimento adicional de distribución | Sensibilidad de forma de entrada | 40 ejecuciones | Exploratorio con protocolo propio |
| motor/references_v4.py | verify | Metadatos externos acotados | Auditoría bibliográfica | 25/30 metadatos | No modifica bibliografía |
| motor/verification_v4.py | verify | Verificación independiente de CSV/estadísticos y baseline | Contrastar la evidencia sin simular | 4352 filas, índices/medias/IC y95 hashes | Solo posprocesamiento; cero cambios de resultados |
| motor/test_v4.py, test_scenario_v4.py | V4Tests,ScenarioTests | 30 tests nuevos | Verificación funcional | 30/30 limpios | No borra tests antiguos |
| requirements-v4.txt, requirements-v4-lock.txt | Dependencias | Versiones directas/transitivas | Instalación independiente | clean_install/clean_tests | No sustituye requisitos ML |
| motor/V4_IMPLEMENTACION.md | Documentación | Ecuaciones, uso y límites | Reproducción | Comandos probados | Sin cambio de modelo |
| ../correcciones_articulo/generar_informes_implementacion_v4.py | main | Informes desde resultados ejecutados | Evitar cifras manuales | Lectura de evidencia y manifiestos | No ejecuta simulaciones |

## Pruebas ejecutadas

# Estado de pruebas V4

Fecha de corte: 31 de octubre de 2026 (America/Bogota). Evidencia nueva posterior a V3; datos sintéticos. No se editó el artículo V3 ni se redactó V4.

Batería actual del entorno de trabajo: **91 métodos; 90 superados; 1 método fallido; 3 registros de subcasos fallidos; 0 errores; 0 omitidos**. No se midió cobertura. No se eliminó ni se cambió ningún hash esperado.

Fallido: `motor.test_model.EngineTests.test_original_engine_regression` en tres subcasos. Los otros métodos antiguos y los 30 nuevos pasan. La batería incluye núcleo, cohortes, base, UI, asistente ML, cinco exportaciones y módulos V4. No incluye toda la suite ML/EDA/TypeScript.

**Incidente de transporte fuera del resultado unittest:** en la consola de un hilo HTTP se observó al menos un ConnectionAbortedError WinError10053 al escribir una respuesta. Cero errores de unittest no significa ausencia de esa excepción. Se registró en `evidencia_v4/fase_0/observacion_transporte_tests.md`; no se demostró vínculo con el timeout histórico ni se modificó el servidor preexistente.

Comando ejecutado desde `gemelo_digital`: `python -B -m motor.v4_workflow tests` (primera selección 88 métodos) y runner equivalente tras añadir tres casos, registro actual `evidencia_v4/fase_0/tests_current.log/json`. Los registros anteriores no se suman como pruebas distintas.

Entorno virtual limpio: instalación de `requirements-v4.txt` exitosa y **30 métodos nuevos superados** (`returncode=0`), sin heredar site-packages. Log `fase_5/clean_tests.log`, `clean_install.log`; lock transitive `gemelo_digital/requirements-v4-lock.txt`. No se reinstaló en ese venv todo el sistema ML/navegador.

## Regresiones e incidencias

Tres casos serializados completos nuevos están en `fase_0/case_0_current.json.gz` a `case_2_current.json.gz`. Se comparó repetición actual, default/compact JSON y conversión de floats enteros. Ninguna representación probada recuperó hashes históricos. No hay objetos/fuente original para atribuir la diferencia a regresión funcional o representación. `diagnostics.json` contiene configuraciones, semillas y hashes.

Las cuatro diferencias max_queue se focalizaron de nuevo: escenario demanda200, priority/tuned, semillas 1020/1025. Excluir H de las trazas actuales recupera254/221, mientras incluirlo produce255/222. Se demuestra el contrafactual métrico para estos casos, no la fuente histórica. Un test nuevo verifica el extremo H.

Timeout: las cinco exportaciones vuelven a pasar. Clasificación: **histórico no reproducido**, no causa reparada. Se conservan los registros negativos V3.

## Pruebas nuevas

25 métodos en `test_v4.py`: identidad legada, métricas fase única, vacío/ocupado/residual, recursos insuficientes, datos inválidos, adaptador enriquecido, reinicio exacto y configuración incompatible, fases, interrupción inmediata/no interrumpible/límites, turnos fraccionarios, destinos/conservación/determinismo, desactivación, recuperación/identificabilidad/leakage y entradas calibradas. Cinco métodos de `test_scenario_v4.py`: grafo real vs directo, rechazo, caché/tamper, fallo y reintento con herramienta inyectada. No se presenta la inyección de errores como ejecución de un proveedor real.

## Evidencia y limitaciones

| Fase | Estado | Funcionalidades implementadas | Pruebas | Evidencias | Pendientes |
| --- | --- | --- | --- | --- | --- |
| 0 | PARCIAL | Línea base ZIP+SHA; rama codex/implementacion-v4; tres objetos de regresión y diagnóstico de cola | Pruebas antiguas y nuevas; fallos históricos conservados | evidencia_v4/fase_0/ | Fuente original/hash no recuperados; timeout histórico no reproducido |
| 1 | PARCIAL | Estado ocupado, contratos/procedencia, calibración ejecutable y holdout sintético | 25 métodos V4 compartidos con fase 2; recuperación sintética | evidencia_v4/fase_1/ | Calibración y validación hospitalarias externas |
| 2 | RESUELTA | Fases, preempción, calendarios, salidas opcionales y checkpoint, alcance sintético | 25 métodos V4; compatibilidad legada y conservación | evidencia_v4/fase_2/ | Parámetros/transiciones clínicos no validados; interfaz antigua no activada automáticamente |
| 3 | RESUELTA | 4352 simulaciones nuevas; políticas, ablaciones, incertidumbre y Sobol | Protocolo antes de campaña; tamaños completos; IC y Holm | evidencia_v4/fase_3/ | Estabilidad limitada; resultados negativos se conservan; no confirmación clínica |
| 4 | PARCIAL | StateGraph real local con contratos, ejecución/caché/evidencia, abstención y reintento | 20 tareas, 20/20 estados correctos; 20/20 equivalencias; cinco tests de grafo | evidencia_v4/fase_4/ | No LLM/proveedor ni comprensión libre evaluados; no ventaja operacional demostrada |
| 5 | PARCIAL | Instalación limpia y lock, metadatos externos, manifiestos y guía | 30 métodos nuevos en entorno limpio; returncode=0 | evidencia_v4/fase_5/ | Licencia/autorización de publicación, [2], lectura íntegra y verificación editorial |

## Conclusión

Motor ampliado optativo con fases y requisitos, preempción inmediata o en límites, reducción de capacidad que pausa y libera, riesgos competidores y deterioro experimental de rango. F original mantiene relajación/velocidad; utilización por staff real o alternativa resource_peak. J penaliza todos los destinos no completados; llegada inicial se incluye en denominador. Reinicio exacto probado. No modifica automáticamente UI anterior.

Los números de pruebas compartidas no se suman entre fases. Véanse fases/suites originales y ESTADO_PRUEBAS_V4.md.
