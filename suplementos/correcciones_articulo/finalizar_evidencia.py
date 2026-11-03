from pathlib import Path
from docx import Document
import json, hashlib, zipfile, subprocess, sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT=Path(__file__).resolve().parent
EV=OUT/'evidencia_adicional'
ROOT=OUT.parent
r=json.loads((EV/'resultados.json').read_text(encoding='utf-8'))
def f(x): return f'{x:.3f}'.replace('.',',')
def ci(s):return f"{f(s['mean'])} [{f(s['ci95'][0])}; {f(s['ci95'][1])}]"
rows=r['sobol_stability']
status='se cumplió' if r['all_stability_criteria_met'] else 'no se cumplió para todos los índices'
text=f'''# Evidencia computacional suplementaria ejecutada

El 31 de octubre de 2026 se ejecutó un protocolo fijado antes de esta ampliación, después de conocer los resultados originales. No es un registro previo del estudio original ni validación hospitalaria. Código: generar_evidencia.py. No se alteraron el motor ni las salidas históricas.

Se ejecutaron {r['simulation_counts']['sobol']} simulaciones de sensibilidad, {r['simulation_counts']['new_policy']} de políticas nuevas y {r['simulation_counts']['reproduction']} repeticiones de auditoría. Las nuevas simulaciones analíticas suman 21230; con las 3050 históricas, 24280. Las 450 repeticiones no se cuentan como evidencia independiente. Los tamaños anidados N=64/128/256 reutilizan el mismo diseño y tampoco deben sumarse.

## Reproducción numérica

Las 450 filas originales se repitieron con el motor actual. Error máximo absoluto en J: {r['reproduction']['max_objective_error']:.3g}; máximo entre las métricas numéricas comparadas, excluido runtime_s: {r['reproduction']['max_metric_error']:.3g}. Tolerancia fijada: 1e-8. J cumple la tolerancia en todas las filas, pero no se reprodujeron idénticamente todas las métricas. La comparación por campo localizó cuatro diferencias en max_queue de un paciente: escenario demanda_200, semillas 1020 y 1025, políticas priority y tuned. No hay otras discrepancias por encima de la tolerancia entre las métricas comparadas. Véase discrepancias_reproduccion.json. Es una comprobación de métricas, no de igualdad bit a bit de pacientes y trayectorias; no elimina los fallos históricos de hashes serializados. No se reprodujo aquí el ajuste ni toda la ampliación factorial original.

## Sensibilidad con aleatorizaciones independientes

Entradas independientes: service_scale U(0,8;1,2), beta U(0;0,5). Cuatro secuencias Sobol aleatorizadas independientes de dimensión cuatro, semillas 2026103101–2026103104. Por secuencia: matrices A/B/AB0/AB1 con N=256, cinco semillas comunes 2000–2004 por configuración. Total 4×256×4×5=20480 simulaciones. Salida: media de J sobre cinco semillas. Saltelli primer orden, Jansen efecto total.

Los IC95% se calculan con t(3) entre los cuatro estimadores independientes de cada índice; caracterizan variación de la integración aleatorizada, condicionada a los parámetros, estructura y cinco semillas. No caracterizan heterogeneidad hospitalaria ni toda la incertidumbre del modelo. No se usa bootstrap ordinario de filas para estos nuevos IC.

Diagnóstico fijado antes de la ejecución: para los cuatro índices, cambio absoluto de la media entre N=128 y 256 ≤0,03 y semiancho del IC95% en N=256 ≤0,05. Resultado: {status}. Es evidencia numérica en los tamaños probados; no prueba matemática de convergencia general.

| Parámetro | Índice | N=64, media [IC95%] | N=128 | N=256 | Cambio 128→256 | Cumple ambos criterios |
|---|---|---|---|---|---|---|
'''
for row in rows:
    b=row['by_N'];text+=f"| {row['parameter']} | {row['index']} | {ci(b['64'])} | {ci(b['128'])} | {ci(b['256'])} | {f(row['change128_256'])} | {'Sí' if row['criterion_met'] else 'No'} |\n"
text+='''
## Políticas de envejecimiento en semillas nuevas

Cinco escenarios × cinco políticas (FIFO, prioridad estricta y envejecimiento cada 30/60/120 minutos) × 30 semillas 3000–3029 =750 simulaciones. No hubo selección de ganador ni ajuste a estas semillas. Es un análisis exploratorio añadido después de conocer la desventaja distributiva original. En envejecimiento baja la clase efectiva para ordenar la cola, pero la clase clínica experimental y sus recursos permanecen: un P2 no consume UCI por cambiar su orden. Los IC de comparaciones son marginales pareados; no se hacen afirmaciones confirmatorias de múltiples contrastes.

Referencia, medias por ejecución; cobertura significa inicio y no finalización o supervivencia:

| Política | J | Finalizaciones | Cobertura P0 % | Cobertura P1 % | Cobertura P2 % |
|---|---|---|---|---|---|
'''
for row in r['policy_summary']:
    if row['scenario']=='referencia':
        m=row['metrics'];text+=f"| {row['policy']} | {f(m['objective']['mean'])} | {f(m['completed']['mean'])} | {f(100*m['coverage_p0']['mean'])} | {f(100*m['coverage_p1']['mean'])} | {f(100*m['coverage_p2']['mean'])} |\n"
text+='\nComparaciones pareadas en referencia contra prioridad estricta:\n\n| Política | ΔJ [IC95%] | Δ cobertura P2, puntos porcentuales [IC95%] |\n|---|---|---|\n'
for row in r['paired_policy_contrasts']:
    if row['scenario']=='referencia':
        m=row['metrics'];z=m['coverage_p2'];z={**z,'mean':100*z['mean'],'ci95':[100*x for x in z['ci95']]}
        text+=f"| {row['policy']} | {ci(m['objective'])} | {ci(z)} |\n"
text+='''
Las cinco tablas de escenario completas, IC y contrastes están en resultados.json y todos los valores por ejecución en policy_ejecuciones.csv. Una mejora de P2 no garantiza que J o P0 mejoren: debe describirse el compromiso con sus cifras. No se define un umbral clínico de equidad con estos datos sintéticos.

## Límites y estado de las objeciones

Estos experimentos fortalecen reproducibilidad, sensibilidad y análisis distributivo. No aportan datos de pacientes, calibración real, validación externa, ocupación observada inicial, fases asistenciales ni evaluación del asistente LangGraph. El motor sigue comenzando vacío. La retención no interrumpible de recursos y el resto de supuestos siguen vigentes. No se declara una nota de 20/20 ni el cierre de todas las observaciones.

Los CSV son sintéticos. No se asigna aquí una licencia nueva ni se afirma haber depositado el material en GitHub. El manifiesto identifica exactamente la entrega local.
'''
(EV/'INFORME_EVIDENCIA.md').write_text(text,encoding='utf-8')
# Export figures from actual results.
fig,axes=plt.subplots(1,2,figsize=(10,4))
for ax,name in zip(axes,['service_scale','beta']):
    for metric in ['S1','ST']:
        row=next(x for x in rows if x['parameter']==name and x['index']==metric)
        n=[64,128,256];b=row['by_N'];means=[b[str(i)]['mean'] for i in n]
        err=[[b[str(i)]['mean']-b[str(i)]['ci95'][0] for i in n],[b[str(i)]['ci95'][1]-b[str(i)]['mean'] for i in n]]
        ax.errorbar(n,means,yerr=err,marker='o',capsize=3,label=metric)
    ax.set(title=name,xlabel='N por aleatorización',ylabel='Índice (IC95% entre 4 aleatorizaciones)');ax.legend();ax.grid(alpha=.2)
fig.tight_layout();fig.savefig(EV/'sobol_estabilidad.png',dpi=180);plt.close(fig)
fig,ax=plt.subplots(figsize=(7,4))
for row in r['policy_summary']:
    if row['scenario']=='referencia':
        m=row['metrics'];ax.scatter(m['objective']['mean'],100*m['coverage_p2']['mean']);ax.annotate(row['policy'],(m['objective']['mean'],100*m['coverage_p2']['mean']),xytext=(4,4),textcoords='offset points')
ax.set(xlabel='Pérdida ponderada J (minutos equivalentes)',ylabel='Cobertura de inicio P2 (%)',title='Referencia sintética · semillas nuevas 3000–3029');ax.grid(alpha=.2);fig.tight_layout();fig.savefig(EV/'compromiso_distributivo.png',dpi=180);plt.close(fig)
# Preserve first corrected document and create a new version with a genuine supplement.
d=Document(OUT/'Articulo_corregido_revision2.docx')
from docx.enum.style import WD_STYLE_TYPE
for name in ['Heading 1','Heading 2']:
    if name not in d.styles:
        style=d.styles.add_style(name,WD_STYLE_TYPE.PARAGRAPH);style.font.bold=True
if 'Table Grid' not in d.styles:
    d.styles.add_style('Table Grid',WD_STYLE_TYPE.TABLE)
for p in d.paragraphs:
    if p.text.startswith('Resumen:'):
        p.text=p.text.replace('El experimento original comprendió 1500 simulaciones; una ampliación exploratoria reportada añadió 1550.','El experimento original comprendió 1500 simulaciones y la ampliación previa añadió 1550. Un suplemento posterior añadió 21230 simulaciones analíticas: 20480 para sensibilidad y 750 para políticas de envejecimiento, además de 450 repeticiones de auditoría.')
    if p.text.startswith('El sistema evaluado es un simulador sintético'):
        p.text=p.text.replace('La sensibilidad global se limita a dos parámetros y no ha demostrado convergencia.','La sensibilidad global se limita a dos parámetros; el suplemento documenta el diagnóstico de estabilidad en tamaños anidados y cuatro aleatorizaciones independientes, sin demostrar convergencia general.')
d.add_page_break();d.add_heading('Suplemento computacional posterior a la segunda revisión',level=1)
table=None
for line in text.splitlines():
    if line.startswith('|'):
        cells=[v.strip() for v in line.strip('|').split('|')]
        if all(set(v)<=set('-: ') for v in cells):continue
        if table is None:
            table=d.add_table(rows=0,cols=len(cells));table.style='Table Grid'
        row=table.add_row()
        for cell,value in zip(row.cells,cells):cell.text=value
    else:
        table=None
        if line.startswith('## '):d.add_heading(line[3:],level=2)
        elif line.startswith('# '):d.add_heading(line[2:],level=2)
        elif line.strip():d.add_paragraph(line)
d.add_picture(str(EV/'sobol_estabilidad.png'),width=__import__('docx').shared.Inches(6))
d.add_paragraph('Figura S1. Índices de sensibilidad y variación entre cuatro aleatorizaciones independientes; cinco semillas comunes por configuración. Datos sintéticos.')
d.add_picture(str(EV/'compromiso_distributivo.png'),width=__import__('docx').shared.Inches(6))
d.add_paragraph('Figura S2. Compromiso descriptivo entre J y cobertura P2 en el escenario de referencia con semillas nuevas; no representa una frontera óptima demostrada.')
d.save(OUT/'Articulo_revision2_con_evidencia.docx')
# Authoritative prompt update first, followed by prior instructions as historical context.
base=(OUT/'PROMPT_CLAUDE_COMPLETO.md').read_text(encoding='utf-8')
new='''# ACTUALIZACIÓN PRIORITARIA: EVIDENCIA NUEVA REALMENTE EJECUTADA

Este encabezado actualiza las instrucciones históricas que siguen. Usa Articulo_revision2_con_evidencia.docx, evidencia_adicional/INFORME_EVIDENCIA.md, resultados.json y los CSV, además del artículo original y revisión. Integra el suplemento en el cuerpo del artículo y su respuesta al revisor; no lo dejes como un apéndice desconectado. El artículo con suplemento conserva el cuerpo previo para mantener trazabilidad: elimina contradicciones temporales al producir la versión final.

Debes añadir/cambiar:

1. Resumen y diseño experimental: distinguir 1500 originales, 1550 de ampliación previa, 20480 nuevas Sobol y 750 políticas, total analítico acumulado 24280. Hay 450 repeticiones adicionales de reproducción, que no aumentan evidencia independiente. N=64/128/256 son tamaños anidados reutilizados y no se suman.
2. Metodología de sensibilidad: cuatro aleatorizaciones independientes, N máximo 256, cinco semillas comunes y estimadores/criterios/IC exactos del protocolo. Separar CI aproximados bootstrap históricos de los nuevos IC t(3) entre aleatorizaciones. El protocolo fue fijado antes del suplemento pero después de los resultados previos; no llamarlo preregistro original.
3. Resultados: tabla completa de estabilidad y Figura S1, sin elegir solo índices favorables. Declara para cada índice si cumple el cambio <=0,03 y semiancho <=0,05. Si algún criterio falla, informa qué falta; no escribas «convergencia demostrada». Incluso si todos cumplen, escribe «estabilidad numérica en el diseño probado».
4. Políticas: explica envejecimiento cada 30/60/120 minutos, sin cambiar clase original ni recursos; cinco escenarios, 30 semillas nuevas 3000–3029, 750 ejecuciones. Integra medias, IC y diferencias pareadas en J, cobertura P0/P1/P2 y finalizaciones. Incluye Figura S2. No selecciones una política como clínicamente óptima ni omitas pérdidas de cobertura P0 o aumentos de J. Los análisis son exploratorios y los IC marginales.
5. Reproducibilidad: sustituye la afirmación de «solo 15 valores de J repetidos» por la reproducción adicional de 450 filas, con errores máximos realmente observados, tolerancia 1e-8 y exclusión de runtime_s. J coincide en todas; cuatro filas difieren en max_queue por un paciente, identificadas en discrepancias_reproduccion.json. No declares todas las métricas reproducidas. No se certificó igualdad de todos los pacientes/trazas. Los tres subcasos de regresión por hash y el timeout de exportación siguen pendientes; esta evidencia no los hace desaparecer.
6. Discusión y conclusiones: incorporar el compromiso de envejecimiento observado y el resultado real de estabilidad. Mantener como pendientes calibración hospitalaria, validación externa, inicio observado, fases y evaluación LangGraph. No inventar validación clínica ni cierres de FON-01/FON-02/FON-04. FON-03 se responde con evidencia específica y su alcance, FON reproducibilidad con scripts/CSV/hashes locales; publicación y licencia pendientes.
7. Entrega un manuscrito coherente de extensión acorde con revista: integra material central y coloca tablas largas por escenario, protocolo y métricas por ejecución en suplemento. Conserva resultados originales comparables y etiqueta todas las incorporaciones posteriores. Responde a cada criterio de la rúbrica con evidencia y pendientes. No prometas 20/20.

## RESULTADOS NUEVOS AUTORITATIVOS

'''+text+'\n\n## CONTEXTO HISTÓRICO (actualizar afirmaciones superadas con la evidencia anterior)\n\n'+base
(OUT/'PROMPT_CLAUDE_ACTUALIZADO.md').write_text(new,encoding='utf-8')
requirements=subprocess.check_output([sys.executable,'-m','pip','freeze'],text=True)
(EV/'entorno_ejecutado_freeze.txt').write_text(requirements,encoding='utf-8')
files=[p for p in EV.rglob('*') if p.is_file()]+[OUT/'generar_evidencia.py',OUT/'finalizar_evidencia.py',OUT/'PROMPT_CLAUDE_ACTUALIZADO.md',OUT/'Articulo_revision2_con_evidencia.docx']
manifest={str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
(EV/'manifiesto_sha256.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
with zipfile.ZipFile(OUT/'Paquete_Claude_con_evidencia.zip','w',zipfile.ZIP_DEFLATED) as z:
    # Include original package, and current files directly, for traceability and accessibility.
    with zipfile.ZipFile(OUT/'Paquete_Claude.zip') as old:
        for name in old.namelist():z.writestr(name,old.read(name))
    for p in files+[EV/'manifiesto_sha256.json']:z.write(p,str(p.relative_to(ROOT)))
print('Ready:',OUT/'Paquete_Claude_con_evidencia.zip')
