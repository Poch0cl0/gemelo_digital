# Evidencia computacional suplementaria ejecutada

El 31 de octubre de 2026 se ejecutó un protocolo fijado antes de esta ampliación, después de conocer los resultados originales. No es un registro previo del estudio original ni validación hospitalaria. Código: generar_evidencia.py. No se alteraron el motor ni las salidas históricas.

Se ejecutaron 20480 simulaciones de sensibilidad, 750 de políticas nuevas y 450 repeticiones de auditoría. Las nuevas simulaciones analíticas suman 21230; con las 3050 históricas, 24280. Las 450 repeticiones no se cuentan como evidencia independiente. Los tamaños anidados N=64/128/256 reutilizan el mismo diseño y tampoco deben sumarse.

## Reproducción numérica

Las 450 filas originales se repitieron con el motor actual. Error máximo absoluto en J: 2.84e-13; máximo entre las métricas numéricas comparadas, excluido runtime_s: 1. Tolerancia fijada: 1e-8. J cumple la tolerancia en todas las filas, pero no se reprodujeron idénticamente todas las métricas. La comparación por campo localizó cuatro diferencias en max_queue de un paciente: escenario demanda_200, semillas 1020 y 1025, políticas priority y tuned. No hay otras discrepancias por encima de la tolerancia entre las métricas comparadas. Véase discrepancias_reproduccion.json. Es una comprobación de métricas, no de igualdad bit a bit de pacientes y trayectorias; no elimina los fallos históricos de hashes serializados. No se reprodujo aquí el ajuste ni toda la ampliación factorial original.

## Sensibilidad con aleatorizaciones independientes

Entradas independientes: service_scale U(0,8;1,2), beta U(0;0,5). Cuatro secuencias Sobol aleatorizadas independientes de dimensión cuatro, semillas 2026103101–2026103104. Por secuencia: matrices A/B/AB0/AB1 con N=256, cinco semillas comunes 2000–2004 por configuración. Total 4×256×4×5=20480 simulaciones. Salida: media de J sobre cinco semillas. Saltelli primer orden, Jansen efecto total.

Los IC95% se calculan con t(3) entre los cuatro estimadores independientes de cada índice; caracterizan variación de la integración aleatorizada, condicionada a los parámetros, estructura y cinco semillas. No caracterizan heterogeneidad hospitalaria ni toda la incertidumbre del modelo. No se usa bootstrap ordinario de filas para estos nuevos IC.

Diagnóstico fijado antes de la ejecución: para los cuatro índices, cambio absoluto de la media entre N=128 y 256 ≤0,03 y semiancho del IC95% en N=256 ≤0,05. Resultado: se cumplió. Es evidencia numérica en los tamaños probados; no prueba matemática de convergencia general.

| Parámetro | Índice | N=64, media [IC95%] | N=128 | N=256 | Cambio 128→256 | Cumple ambos criterios |
|---|---|---|---|---|---|---|
| service_scale | S1 | 0,383 [0,363; 0,403] | 0,390 [0,384; 0,395] | 0,389 [0,386; 0,392] | 0,001 | Sí |
| service_scale | ST | 0,395 [0,391; 0,398] | 0,394 [0,390; 0,397] | 0,392 [0,390; 0,393] | 0,002 | Sí |
| beta | S1 | 0,612 [0,596; 0,627] | 0,614 [0,600; 0,627] | 0,610 [0,608; 0,613] | 0,003 | Sí |
| beta | ST | 0,615 [0,607; 0,623] | 0,613 [0,598; 0,628] | 0,610 [0,610; 0,611] | 0,003 | Sí |

## Políticas de envejecimiento en semillas nuevas

Cinco escenarios × cinco políticas (FIFO, prioridad estricta y envejecimiento cada 30/60/120 minutos) × 30 semillas 3000–3029 =750 simulaciones. No hubo selección de ganador ni ajuste a estas semillas. Es un análisis exploratorio añadido después de conocer la desventaja distributiva original. En envejecimiento baja la clase efectiva para ordenar la cola, pero la clase clínica experimental y sus recursos permanecen: un P2 no consume UCI por cambiar su orden. Los IC de comparaciones son marginales pareados; no se hacen afirmaciones confirmatorias de múltiples contrastes.

Referencia, medias por ejecución; cobertura significa inicio y no finalización o supervivencia:

| Política | J | Finalizaciones | Cobertura P0 % | Cobertura P1 % | Cobertura P2 % |
|---|---|---|---|---|---|
| fifo | 192,667 | 97,900 | 67,527 | 70,474 | 68,283 |
| priority | 175,193 | 73,267 | 84,043 | 90,382 | 9,098 |
| aging_30 | 192,393 | 97,733 | 67,527 | 70,340 | 68,292 |
| aging_60 | 191,625 | 97,767 | 67,408 | 70,403 | 68,222 |
| aging_120 | 188,870 | 97,200 | 67,704 | 69,936 | 67,668 |

Comparaciones pareadas en referencia contra prioridad estricta:

| Política | ΔJ [IC95%] | Δ cobertura P2, puntos porcentuales [IC95%] |
|---|---|---|
| fifo | 17,474 [15,681; 19,268] | 59,184 [55,685; 62,684] |
| aging_30 | 17,200 [15,469; 18,931] | 59,193 [55,737; 62,649] |
| aging_60 | 16,433 [14,741; 18,124] | 59,124 [55,533; 62,714] |
| aging_120 | 13,677 [12,377; 14,978] | 58,569 [55,111; 62,028] |

Las cinco tablas de escenario completas, IC y contrastes están en resultados.json y todos los valores por ejecución en policy_ejecuciones.csv. Una mejora de P2 no garantiza que J o P0 mejoren: debe describirse el compromiso con sus cifras. No se define un umbral clínico de equidad con estos datos sintéticos.

## Límites y estado de las objeciones

Estos experimentos fortalecen reproducibilidad, sensibilidad y análisis distributivo. No aportan datos de pacientes, calibración real, validación externa, ocupación observada inicial, fases asistenciales ni evaluación del asistente LangGraph. El motor sigue comenzando vacío. La retención no interrumpible de recursos y el resto de supuestos siguen vigentes. No se declara una nota de 20/20 ni el cierre de todas las observaciones.

Los CSV son sintéticos. No se asigna aquí una licencia nueva ni se afirma haber depositado el material en GitHub. El manifiesto identifica exactamente la entrega local.
