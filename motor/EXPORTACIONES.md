# Visualización y exportaciones

## Diagnóstico y alcance

La interfaz usa HTML, CSS y JavaScript nativos; `ui.py` sirve archivos y API con
`ThreadingHTTPServer`. La persistencia operativa usa SQLite. No hay framework web
ni biblioteca gráfica externa: `app.js` dibuja SVG de simulación, `ml-charts.js`
construye las figuras y tablas ML, y `hospital3d.js` dibuja la escena en canvas.
La escena espacial interactiva no es una figura científica exportable.

`POST /api/simulate` devuelve configuración, política, semilla, procedencia de la
población, pacientes, trazas temporales, métricas y comparaciones. El motor calcula
esperas censuradas, cobertura por prioridad, finalizados, cola máxima, utilización
integrada, saturación UCI, carga y pérdida ponderada. La comparación existente usa
una réplica por política; no ofrece intervalos entre réplicas ni una optimización
automática. La población puede ser sintética o una cohorte declarada por el usuario.

`GET /api/ml/report` suministra el artefacto ML existente, incluidas estadísticas,
validación y explicabilidad. `/api/ops/*` entrega los registros operativos y
`/api/twin/status` el estado de snapshots recibidos. No hay conexión HIS real ni
validación contra mediciones físicas continuas. No se añadieron tales métricas.

Antes solo existían descarga JSON global y CSV de pacientes; este último ignoraba
el filtro de prioridad. La gestión pagina en el navegador y ML ya tenía títulos,
unidades y notas, pero ninguna descarga individual.

## Implementación

Se mantiene la arquitectura y se añade `web/scientific-export.js`, compartido por
simulación, gestión y ML. Cada visualización registra un proveedor de datos;
los archivos se generan al pulsar el botón con los filtros actuales. La vista PDF
usa `export-preview.html/js` y la impresión nativa del navegador. `ui.py` registra
estos recursos y permite imágenes blob locales en CSP para rasterizar SVG.
No se agregaron dependencias de producción, servicios externos ni cambios al motor.

Las tablas de recursos y prioridad permiten descargar indicadores ya calculados.
El gráfico temporal añade eje de personas, trazos diferenciados y consulta de
valores por minuto. Las tablas ofrecen búsqueda y ordenamiento; la gestión conserva
su búsqueda y paginación y añade orden por ID.

## Uso

Ejecutar `python -m motor.ui` y abrir **Simulación y gemelo 3D** o **Aprendizaje
automático**. Cada SVG y tabla tiene una barra **Formato científico**:

| Elemento | Formatos |
| --- | --- |
| Evolución temporal y figuras ML | SVG, PNG, PDF mediante impresión, JSON |
| Pacientes, políticas, recursos, prioridades | CSV, PNG, PDF mediante impresión, JSON |
| Tablas ML y registros operativos | CSV, PNG, PDF mediante impresión, JSON |

PNG usa fondo blanco, conserva la proporción, genera al menos los píxeles necesarios
para 300 DPI al ancho mínimo seleccionado (90 o 180 mm) e incorpora pHYs de 300 DPI.
SVG incluye atributos gráficos resueltos, títulos, notas y metadatos y no depende
del CSS del dashboard. Las figuras conservan los ejes y datos del gráfico actual.
La impresión usa exclusivamente las figuras; desactivar encabezados y pies del
navegador y seleccionar **Guardar como PDF**.

Las tablas largas se separan en bloques, con encabezados y notas repetidos. PNG
descarga un archivo por bloque; el navegador puede pedir habilitar descargas
múltiples. PDF reúne los bloques en la vista imprimible. Se rechazan PNG que
superen límites conservadores de memoria; para esos casos utilizar SVG o PDF.
En tablas con muchas columnas conviene elegir 180 mm y comprobar la legibilidad
en el tamaño final de publicación.

CSV contiene todos los registros filtrados, no solo la página visible. Conserva
valores numéricos sin el redondeo de pantalla y añade escenario, origen y notas.
Los valores ausentes son celdas vacías; no se convierten en cero. CSV usa UTF-8 con
BOM, comillas y escape de fórmulas en texto para hojas de cálculo. El JSON conserva
los datos originales sin ese escape. En gestión, estados y referencias usan las
etiquetas legibles de la interfaz; las fechas mantienen su representación original.

Las tablas ML conservan los números originales al formatearlos para pantalla.
Algunos intervalos y resúmenes compuestos siguen siendo textos con la precisión
de presentación; **Descargar datos originales ML (JSON)** permite recuperar sus
extremos y estadísticas originales desde el artefacto existente. Los JSON de las
figuras ML incluyen sus entradas y opciones. XLSX no se genera: no existe una
dependencia Excel en la aplicación y se mantiene la instalación básica sin paquetes.

No se exportan controles de interfaz, no se alteran datos originales y no se
generan documentos académicos. Los artefactos incluyen procedencia y fecha UTC;
simulación añade configuración, política, semilla y metadatos de la cohorte en JSON
y en los metadatos SVG.

## Validación

```powershell
python -m unittest discover -s motor -t .
python -m unittest motor.test_exports -v
node motor/test_hospital3d.cjs
git diff --check
```

`test_exports.py` usa Playwright/Chromium si están disponibles (son herramientas
de prueba opcionales). Comprueba descargas reales, CSV filtrado y precisión,
tablas vacías y de 10.000 filas, protección CSV, dimensiones y pHYs de PNG,
envoltura de texto, SVG sin controles, impresión PDF, pestañas ML, ordenamiento
y exportación operativa de más registros que una página.

La prueba existente `test_original_engine_regression` presenta tres discrepancias
de hashes en este entorno. Se reprodujeron cargando directamente `HEAD:motor/model.py`
en una carpeta temporal; no se modificaron el motor ni los hashes esperados.
