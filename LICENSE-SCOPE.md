# Alcance de las licencias

El solicitante confirmó que Jefferson Miguel Peña Serrano, Martin Aryan Robles Perez y Juan Pedro Santos Fernandez son los titulares del código y de los materiales científicos propios de esta entrega, y que todos consienten MIT para el código y CC BY 4.0 para datos sintéticos, resultados y figuras propios. Esta declaración es la base de los avisos; no se presenta como una investigación registral independiente de titularidad.

## Código propio: MIT

`LICENSE` se aplica al código fuente propio de `motor/` (Python, JavaScript, HTML, CSS, SQL y pruebas CJS), los scripts propios de `suplementos/correcciones_articulo/` y `suplementos/verificar_integridad.py`. Se excluyen bytecode, binarios, bibliotecas externas, recursos de terceros y archivos con aviso de otra procedencia. Los requisitos de instalación no relicencian los paquetes que enumeran.

## Material científico propio: CC BY 4.0

`LICENSE-DATA` se aplica a:

- CSV sintéticos de `resultados/`, configuraciones y resúmenes propios `politica_ajustada.json`, `resumen.json`, `auditoria_final.json` y `manifest_final.json`.
- `resultados/revision_manuscrito/{analisis.json,interacciones.csv,sobol_ejecuciones.csv}`.
- Los 58 archivos científicos y de documentación propios distintos de scripts enumerados individualmente en `suplementos/INVENTARIO_ENTREGA.json`, incluidos datos, protocolos, resultados, figuras, manifiestos y registros sintéticos. Las citas y avisos de terceros que aparezcan en ellos conservan sus condiciones originales.
- La prosa propia de la guía, del inventario y de los avisos de alcance de esta entrega. Los textos legales de las licencias conservan su procedencia oficial.

La atribución debe identificar los titulares, proyecto, campaña y versión, mantener el enlace de licencia e indicar modificaciones. Los CSV son resultados de simulación y no observaciones de pacientes reales. Las licencias no convierten las campañas en validación clínica ni acreditan igualdad con la versión histórica exacta.

## Exclusiones

No se conceden derechos sobre `datos/nhamcs/`, `resultados_ml/`, paquetes y dependencias, cachés, ejecutables, entornos virtuales, bases operativas, credenciales, `tmp/`, metadatos Crossref (`referencias_crossref.json` y equivalentes), manuscritos, plantillas o materiales editoriales. El ZIP de línea base con documentos no se incluye en el suplemento. Los materiales externos no se transforman en MIT o CC BY por estar presentes en el repositorio.

Los archivos NHAMCS ya presentes en la historia pública conservan su procedencia y condiciones originales; no se relicencian ni se añaden a esta entrega. No se reescribe el historial. Las dependencias se obtienen de sus distribuidores y conservan sus propios avisos.

`preparacion_licencias/` conserva los borradores anteriores para trazabilidad y no determina el alcance vigente. Para identificar bytes del suplemento, utilizar su inventario SHA-256; los manifiestos históricos pueden incluir rutas excluidas o ausentes y no sustituyen ese inventario.

Fuentes oficiales: [MIT, Open Source Initiative](https://opensource.org/license/mit) y [CC BY 4.0, texto legal](https://creativecommons.org/licenses/by/4.0/legalcode).
