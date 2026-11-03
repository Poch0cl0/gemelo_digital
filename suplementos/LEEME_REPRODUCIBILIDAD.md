# Entrega suplementaria preparada para revisión

No publicada por esta tarea. Las licencias propuestas siguen inactivas hasta confirmar titulares y cotitulares. No atribuir al commit de preparación una reproducción integral ni el cierre de la validación clínica.

## Campañas separadas

| Campaña | Ubicación tras preparar el espacio | Evidencia |
| --- | --- | --- |
| Original, 1500 ejecuciones reportadas | `gemelo_digital/resultados/` | 900 de ajuste resumidas en 9 filas; 450 evaluación; 150 sensibilidad. |
| Ampliación, 1550 | `gemelo_digital/resultados/revision_manuscrito/` | 270 factorial y 1280 Sobol. |
| Suplemento posterior sobre motor histórico | `correcciones_articulo/evidencia_adicional/` | 20480 Sobol y 750 políticas; 450 repeticiones de auditoría aparte. |
| V4 | `evidencia_v4/fase_3/` | 1120 principales + 120 incertidumbre + 3072 Sobol + 40 distribuciones = 4352. |

## Estructura necesaria

Los scripts existentes buscan `correcciones_articulo/` y `evidencia_v4/` como hermanas de `gemelo_digital/`. Las copias se almacenan dentro de `suplementos/` para versionarlas sin cambiar los scripts originales. En una ubicación nueva, utilizar esta estructura:

```text
espacio_reproduccion/
  gemelo_digital/                 # clon del repositorio fijado por commit
  correcciones_articulo/         # copia de suplementos/correcciones_articulo/
  evidencia_v4/                  # copia de suplementos/evidencia_v4/
```

En PowerShell, situado en un clon nuevo, copiar a una carpeta de preparación vacía elegida por el usuario. No sobrescribir la entrega de referencia. La ruta `suplementos/` es almacenamiento; ejecutar los scripts directamente allí alteraría las rutas relativas que esperan.

## Instalación y verificaciones

Desde `gemelo_digital`, con Python compatible con las versiones fijadas (la instalación limpia registrada usó Python 3.11):

```powershell
python -m venv .venv-repro
.\.venv-repro\Scripts\python.exe -m pip install -r requirements-v4-lock.txt
.\.venv-repro\Scripts\python.exe -B -m unittest motor.test_v4 motor.test_scenario_v4 -v
.\.venv-repro\Scripts\python.exe -B -m unittest motor.test_model.EngineTests.test_original_engine_regression
```

El último comando conserva tres fallos históricos de subcaso; no modificar sus hashes para obtener éxito. La batería completa tiene dependencias opcionales distintas. El núcleo histórico usa biblioteca estándar; factorial/Sobol requieren NumPy/SciPy; figuras requieren Matplotlib; el grafo V4 requiere LangGraph. NHAMCS, modelos ML y credenciales no son necesarios para estas campañas científicas.

Desde el repositorio, `python -B suplementos/verificar_integridad.py` comprueba todas las copias suplementarias inventariadas sin generar simulaciones ni reescribir resultados.

## Regeneración en una segunda copia

Los siguientes comandos escriben resultados. Ejecutarlos solo en un espacio independiente; conservar una copia de referencia y comparar salidas científicas, sin exigir identidad de tiempos de ejecución.

- Original: desde `gemelo_digital`, `python -m motor.experiment`.
- Ampliación: desde `gemelo_digital`, `python -m motor.revision_manuscrito`.
- Suplemento: desde `espacio_reproduccion`, usar el intérprete del venv con `correcciones_articulo/generar_evidencia.py`. La preparación de resúmenes y figuras se encuentra en `finalizar_evidencia.py`; ese script también contiene operaciones editoriales y no debe ejecutarse íntegramente sin sus documentos de entrada. Los CSV y figuras existentes se incluyen para su inspección; no se declara un generador autónomo completo de todas las figuras del artículo.
- V4: desde `gemelo_digital`, `python -B -m motor.v4_workflow pilot` y `python -B -m motor.v4_workflow experiment`, en ese orden. Las etapas rechazan resultados ya existentes: apuntar a un espacio nuevo sin salidas de campaña y conservar los protocolos de referencia para compararlos. La ampliación de distribuciones está en `motor/uncertainty_v4.py` y utiliza su protocolo independiente.

Los scripts de calibración y benchmark tienen sus etapas en `motor/V4_IMPLEMENTACION.md`. La repetición de campañas completas no se ejecutó como parte de esta preparación. No se afirma autosuficiencia de todos los generadores editoriales ni reconstrucción de la fuente histórica.

## Integridad y límites

`INVENTARIO_ENTREGA.json` identifica bytes y procedencia de las copias. Los manifiestos antiguos se conservan como registros, aunque apunten a archivos excluidos o ausentes. No son el inventario de esta entrega. Se excluyen el ZIP de línea base (contiene documentos de derechos no confirmados), logs extensos, entorno virtual y metadatos bibliográficos externos. Tres objetos JSON comprimidos de regresión contienen resultados sintéticos, no credenciales ni pacientes reales.

Los SHA-256 del árbol Windows pueden diferir del objeto Git por CRLF/LF. En `model.py`, el archivo local `fb160769…` normalizado a LF corresponde al objeto Git `61b4f5f3…`. Esta equivalencia entre copia actual y Git no recupera el hash histórico `34575aa3…` ni resuelve los fallos de regresión.

Sobol posterior histórico y Sobol V4 tienen dominios/modelos/diseños distintos. El primero cumplió criterios en N=128/256; V4 mantiene incumplimientos para beta en N=32/64. No se presentan como una sola prueba de convergencia. La recuperación sintética de parámetros tampoco es calibración hospitalaria.
