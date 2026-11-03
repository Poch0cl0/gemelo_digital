# Motor V4 optativo y evidencia sintética

El motor `model.py` y su interfaz existente se preservan. Las ampliaciones se ejecutan con `model_v4.simulate`; `mode='legacy'` delega al código V3 sin modificarlo. No cambia automáticamente el comportamiento de la interfaz hospitalaria anterior. El punto de entrada nuevo es Python o `python -B -m motor.scenario_graph_v4 '<JSON>'`, con solicitudes estructuradas; el asistente ML anterior permanece separado.

## Contratos y ecuaciones

`initial_state.InitialState/InitialPatient/Phase` describen capacidades completas, pacientes, fases, trabajo residual, asignaciones por identidad, tiempo transcurrido, carga, fuente y procedencia por campo. Se validan duplicados, disponibilidad, prioridades, fechas relativas al corte, trabajo y tipos. `from_operational` requiere enriquecimiento explícito: no infiere trabajo desde el estado SQL. `unknown` no es un valor utilizable de trabajo/carga. El origen observado no acredita validación externa.

Las fases son categorías abstractas, no protocolos clínicos. Una fase termina al agotar trabajo; libera recursos y vuelve a competir por la fase siguiente. Preempción `none` no interrumpe atención; `boundary` permite reasignación en esos límites; `immediate` puede pausar fases interrumpibles si una solicitud de mayor rango puede ser atendida liberando recursos. Se preserva trabajo. Una reducción de calendario pausa los episodios cuyas identidades dejan de estar disponibles, libera todo su conjunto y respeta la nueva capacidad, incluso si la fase estaba marcada no interrumpible: supuesto estructural explícito que no es recomendación clínica.

Se conserva la relajación Euler `F_next = F + h*(u-F)/tau` y velocidad `1-beta*F`. En V4, `u=max(fracción de médicos usados, fracción de enfermeros usados)` permite requerimientos distintos por fase; con fase única estándar reproduce `active/min(doctors,nurses)`. La alternativa `resource_peak` incluye los demás recursos y se etiqueta como incertidumbre estructural. El calendario introduce subpasos en sus discontinuidades. Ninguna fracción supera uno; `tau>=dt` conserva el intervalo [0,1].

Los riesgos opcionales tienen unidades por minuto. Se usa probabilidad de salida `1-exp(-h*sum(rates))` y elección de causa proporcional al riesgo; abandono solo desde espera, muerte/traslado desde espera/atención. Deterioro reduce el rango de prioridad experimental; no cambia automáticamente los recursos de la fase ni expresa fisiología. Sus números de ejemplo son sintéticos. Semillas derivadas por paciente/tiempo/evento evitan que el recorrido de la cola determine las realizaciones aleatorias. Mecanismos desactivados tienen tasa cero.

J usa clase original, espera hasta primer inicio o salida/censura, y penalización de no completado. Todas las salidas distintas de completado reciben esa penalización. Los pacientes iniciales aportan su historia relativa al corte. No comparar J de poblaciones iniciales distintas como si fuese un efecto causal puro de política; las ablaciones se describen con sus denominadores. Cobertura sigue siendo inicio, no supervivencia. Las métricas de ocupación se dividen por capacidad-tiempo realmente disponible. El checkpoint contiene el estado antes de procesar el siguiente instante; configuración, política, semilla y dinámica se comprueban por firma. Una instantánea permite continuar la misma ejecución, no demuestra que un hospital esté observado.

## Calibración

`calibration_v4.calibrate` estima tasas Poisson con exposición e IC exactos, distribución gamma por momentos por clase, beta por regresión de velocidad/carga y tau por relajación de carga observada. Máximos de disponibilidad son estadísticos descriptivos de capacidades, no una optimización de dotación. Se rechazan falta de identificabilidad y particiones con IDs compartidos. `calibrated_inputs` incorpora explícitamente esas tasas, cargas gamma, capacidades y parámetros mediante una cohorte; exige aceptar un ajuste sintético y declara que proporciones de prioridad y ventilación siguen siendo supuestos sintéticos. No sustituye silenciosamente la triangular V3. Se ejecutó recuperación sintética con holdout independiente y una demostración de simulación con cohorte calibrada, no calibración hospitalaria.

En cada intervalo los riesgos se aplican antes del procesamiento de finalización del siguiente instante; las salidas se registran al final del intervalo. Esta convención discreta puede importar cuando un episodio agotaría su trabajo en ese mismo intervalo. No se afirma que represente tiempos clínicos continuos ni que estos destinos estimen mortalidad real.

## Reproducción

Desde `gemelo_digital`:

```powershell
python -B -m unittest motor.test_v4 motor.test_scenario_v4 -v
python -B -m motor.scenario_graph_v4 '{"horizon":120,"variant":"full","policy":"priority","seeds":[41000]}'
```

El grafo real local no requiere ni usa LLM: JSON se normaliza, valida y ejecuta con herramientas deterministas; la respuesta enlaza cifras e IDs de evidencia. Texto ambiguo, unidades NHAMCS y afirmaciones observadas sin datos se rechazan. El benchmark local real no evalúa interpretación lingüística ni un modelo de proveedor. Reintentos/fallos se ensayan aparte con herramientas inyectadas. La caché verifica contenido y hashes de fuente, no ofrece autenticación criptográfica de datos externos.

Los comandos `python -B -m motor.v4_workflow diagnose|pilot|experiment|benchmark|tests` escriben en `../evidencia_v4/fase_X` y rechazan resultados de etapa ya existentes. Para una reproducción, usar copia completa en otra ubicación y conservar los protocolos originales; no borrar ni sobrescribir evidencia de referencia. La etapa `tests` genera nuevos logs por primera ejecución; no usarla para reescribir logs preservados. No ejecutar generadores V3 sobre la entrega histórica.

Entorno estadístico/grafo: `python -m pip install -r requirements-v4.txt`; consultar `evidencia_v4/fase_5` para el resultado real de instalación limpia, sin asumir que estas restricciones puedan resolverse en cualquier índice/Python. Licencia, publicación y validación hospitalaria permanecen sujetos a datos/autorizaciones externas.
