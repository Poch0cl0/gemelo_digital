# Informe fase 3

Fecha de corte: 31 de octubre de 2026 (America/Bogota). Evidencia nueva posterior a V3; datos sintéticos. No se editó el artículo V3 ni se redactó V4.

## Objetivo y estado

Estado: **RESUELTA**. Alcance y criterios de esta fase se evalúan computacionalmente, sin atribuir validez clínica.

## Tareas realizadas, implementación y resultados

Campaña completa: 4352 ejecuciones nuevas, protocolos y tamaños conservados. Resultados en RESUMEN_RESULTADOS_V4.md y CSV/JSON por ejecución. Piloto antes de campaña; ampliación de 40 distribuciones con protocolo separado antes de sus propias ejecuciones. Diseño exploratorio; no se atribuye full a un solo mecanismo. Criterios Sobol fallidos se conservan.

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

| Escenario | Motor/variante | J media [IC95%] | Inicio P0% | Inicio P1% | Inicio P2% | Completados | Salida dead sintética |
| --- | --- | --- | --- | --- | --- | --- | --- |
| reference | legacy | 79.9135 [76.6363; 83.1906] | 46.54 | 46.11 | 8.29 | 18.50 | 0.00 |
| reference | single | 79.9135 [76.6363; 83.1906] | 46.54 | 46.11 | 8.29 | 18.50 | 0.00 |
| reference | occupied | 81.8310 [78.6811; 84.9809] | 45.64 | 44.29 | 9.40 | 18.25 | 0.00 |
| reference | phases | 79.6989 [76.4150; 82.9829] | 47.17 | 45.80 | 8.29 | 17.40 | 0.00 |
| reference | interruptions | 78.6638 [75.3712; 81.9564] | 47.83 | 47.60 | 8.29 | 16.75 | 0.00 |
| reference | shifts | 83.6917 [80.6554; 86.7280] | 46.32 | 39.30 | 8.29 | 16.20 | 0.00 |
| reference | full | 81.9889 [79.3059; 84.6719] | 47.10 | 36.43 | 12.36 | 14.15 | 1.50 |
| demand_150 | legacy | 91.9355 [89.5190; 94.3519] | 32.36 | 30.53 | 4.74 | 18.45 | 0.00 |
| demand_150 | single | 91.9355 [89.5190; 94.3519] | 32.36 | 30.53 | 4.74 | 18.45 | 0.00 |
| demand_150 | occupied | 93.5108 [91.2069; 95.8147] | 31.97 | 28.60 | 5.86 | 18.05 | 0.00 |
| demand_150 | phases | 91.5622 [89.2413; 93.8830] | 32.88 | 30.69 | 4.74 | 16.85 | 0.00 |
| demand_150 | interruptions | 90.9941 [88.6327; 93.3556] | 33.03 | 31.40 | 4.74 | 16.55 | 0.00 |
| demand_150 | shifts | 94.3254 [92.0350; 96.6157] | 31.98 | 26.49 | 4.74 | 16.35 | 0.00 |
| demand_150 | full | 91.9499 [89.9619; 93.9379] | 33.52 | 25.33 | 7.80 | 14.00 | 1.90 |

| Parámetro | Índice | N64 [IC95% t(3)] | Cambio32→64 | Semiancho | Cumple .03/.05 |
| --- | --- | --- | --- | --- | --- |
| service_scale | S1 | 0.4555 [0.4247; 0.4863] | 0.010128 | 0.030799 | True |
| service_scale | ST | 0.4938 [0.4745; 0.5131] | 0.013420 | 0.019297 | True |
| beta | S1 | 0.4809 [0.4399; 0.5218] | 0.063739 | 0.040931 | False |
| beta | ST | 0.5121 [0.4596; 0.5647] | 0.042205 | 0.052589 | False |

## Conclusión

Campaña completa: 4352 ejecuciones nuevas, protocolos y tamaños conservados. Resultados en RESUMEN_RESULTADOS_V4.md y CSV/JSON por ejecución. Piloto antes de campaña; ampliación de 40 distribuciones con protocolo separado antes de sus propias ejecuciones. Diseño exploratorio; no se atribuye full a un solo mecanismo. Criterios Sobol fallidos se conservan.

Los números de pruebas compartidas no se suman entre fases. Véanse fases/suites originales y ESTADO_PRUEBAS_V4.md.
