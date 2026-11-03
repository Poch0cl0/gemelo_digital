> ARCHIVO HISTÓRICO DE PREPARACIÓN: los borradores de esta carpeta no son los avisos vigentes. Tras la confirmación del solicitante, rigen LICENSE, LICENSE-DATA y LICENSE-SCOPE.md en la raíz. Las dudas de conformidad descritas abajo corresponden al estado anterior.

# Licencias preparadas, sin entrada en vigor

Estado al 3 de noviembre de 2026: el autor que solicita la tarea autoriza MIT para código propio y CC BY 4.0 para datos sintéticos, resultados y figuras propios. No se ha confirmado la identidad de todos los titulares ni la conformidad de posibles cotitulares. Los archivos de esta carpeta son borradores; no se instala una licencia definitiva en la raíz del proyecto.

El historial Git atribuye commits a Jefferson Peña Serrano/Poch0cl0; el PDF declara autoría académica de Jefferson Miguel Peña Serrano, Martin Aryan Robles Perez y Juan Pedro Santos Fernandez. Ninguna de estas observaciones acredita por sí sola la titularidad exclusiva del software o los resultados, ni descarta derechos institucionales. El espacio de titular del modelo MIT se conserva sin completar: no se inventan titulares ni fechas de adquisición de derechos.

| Material | Licencia propuesta, condicionada a conformidad | Alcance/exclusión |
| --- | --- | --- |
| Código fuente propio `motor/*.py`, `motor/web/*`, migraciones SQL, pruebas y scripts propios de reproducción | MIT | Confirmar procedencia de cada componente. No incluye bibliotecas o recursos de terceros. |
| Scripts propios copiados en `suplementos/correcciones_articulo/*.py` | MIT | La copia conserva bytes del original. |
| Resultados sintéticos `resultados/*.csv`, configuraciones y resúmenes propios JSON; factorial/Sobol de `resultados/revision_manuscrito/`, salvo metadatos de terceros | CC BY 4.0 | No se cambia la evidencia ni se afirma identidad con la fuente histórica. |
| CSV, protocolos, resultados JSON y figuras propias inventariadas en `suplementos/INVENTARIO_ENTREGA.json` | CC BY 4.0 | Conceder únicamente derechos propios; separar atribución de datos y del código. |
| Informes, manifiestos y registros de entorno | Confirmación de titularidad y clasificación antes del depósito | No extender automáticamente la licencia a citas, metadatos o contenidos incrustados de terceros. |

**Exclusiones expresas:** `datos/nhamcs/`, `resultados_ml/`, bibliotecas, ejecutables, entornos virtuales, cachés, `tmp/`, secretos y bases operativas; manuscritos y plantillas editoriales; metadatos Crossref y cualquier contenido externo no autorizado. La autoría del artículo no es una cesión de derechos sobre estos materiales.

NHAMCS ya figura en el historial público anterior a esta preparación. No se añade ni se vuelve a distribuir dentro del suplemento, y no se relicencia. Tampoco se reescribe el historial para eliminarlo. Revisar sus condiciones originales y avisos de atribución es una tarea diferenciada si se pretende seguir redistribuyéndolo.

Las dependencias conservan sus licencias; se distribuyen instrucciones de instalación, no sus paquetes binarios. La revisión de metadatos instalados se conserva en `cierre_articulo/dependencias_licencias.json` fuera de esta carpeta. NumPy/SciPy/pandas/scikit-learn/joblib usan avisos BSD y otros componentes; LangGraph y SHAP indican MIT; Matplotlib tiene su propio acuerdo; python-dotenv indica BSD. Estos avisos no se sustituyen por MIT del proyecto. El inventario directo no certifica todas las dependencias transitivas/opcionales.

Fuentes oficiales de los borradores: [MIT, Open Source Initiative](https://opensource.org/license/mit) y [CC BY 4.0, texto legal](https://creativecommons.org/licenses/by/4.0/legalcode). El resumen CC no sustituye el texto legal.

Para activar las licencias: identificar titulares por material, registrar su conformidad, completar año/titulares MIT y atribución CC, aprobar el inventario exacto y colocar los avisos definitivos en la raíz. Hasta entonces, no publicar estos borradores como una concesión efectiva.
