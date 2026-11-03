(() => {
  const C = window.MLCharts;
  const {fmt} = C;
  const pct = v => v == null ? '—' : C.value(v * 100, fmt(v * 100, 1) + ' %');
  const pv = p => p == null ? '—' : C.value(p, p < 0.001 ? '< 0,001' : String(fmt(p, 3)));
  const $ = id => document.getElementById(id);
  const make = (tag, props = {}, children = []) => {
    const n = Object.assign(document.createElement(tag), props);
    [].concat(children).forEach(c => n.append(c));
    return n;
  };

  const TABS = [['business', 'Negocio'], ['eda', 'EDA'], ['preparation', 'Preparación'], ['cv', 'Entrenamiento y validación cruzada'],
    ['tuning', 'Hiperparámetros'], ['selection', 'Selección del modelo'], ['test', 'Prueba y estadística'],
    ['explain', 'Explicabilidad'], ['predict', 'Predicción individual']];
  const TARGETS = {visit_minutes: 'Estancia total (LOV)', wait_minutes: 'Espera hasta atención (WAITTIME)', hospitalization: 'Ingreso hospitalario (ADMITHOS)'};
  const MODELS = {baseline: 'Referencia constante', linear: 'Lineal regularizado', decision_tree: 'Árbol de decisión',
    random_forest: 'Random Forest', hist_gradient_boosting: 'Gradient boosting'};
  const NAMES = {age: 'Edad', sex: 'Sexo', triage: 'Triaje', temperature_c: 'Temperatura', pulse: 'Pulso', respiration: 'Respiración',
    systolic: 'PA sistólica', diastolic: 'PA diastólica', pain: 'Dolor', ambulance: 'Ambulancia', arrival_hour: 'Hora de llegada',
    visit_minutes: 'Estancia LOV', wait_minutes: 'Espera', hospitalization: 'Ingreso'};
  const UNITS = {age: 'años', temperature_c: '°C', pulse: 'lat/min', respiration: 'resp/min', systolic: 'mmHg', diastolic: 'mmHg',
    pain: '0–10', arrival_hour: 'hora', triage: 'nivel 1–5', sex: '1 = F, 2 = M', ambulance: '0/1'};
  const BASE = {
    informe: 'NHAMCS 2022 (16.025 visitas) · pesos PATWT · artefacto resultados_ml/informe.json',
    eda: 'Fase EDA (report.eda) · cohorte completa NHAMCS 2022',
    prep: 'Fase preparación (report.preparation) · variables de llegada limpiadas',
    cv: 'Validación cruzada anidada · GroupKFold externo por hospital · RandomizedSearchCV interno (3 pliegues)',
    test: 'Hospitales de prueba (~20 %) nunca usados en entrenamiento ni selección',
    explain: 'Conjunto de prueba · mismo split que la evaluación final',
    predict: 'Modelos entrenados en trainval · predicción en tiempo real vía /api/ml/predict',
  };
  const isCls = t => t === 'hospitalization';
  const metricKey = t => isCls(t) ? 'brier' : 'mae_minutes';
  const metricName = t => isCls(t) ? 'Brier' : 'MAE (min)';
  const modelName = k => MODELS[k] || (k?.startsWith('baseline') ? MODELS.baseline : k);
  let report = null;

  function heading(text, sub) {
    const box = make('div', {className: 'ml-section-heading'});
    box.append(make('h2', {textContent: text}));
    if (sub) box.append(make('p', {textContent: sub}));
    return box;
  }

  function grid(...panels) { return make('div', {className: 'ml-grid'}, panels); }

  // ---------------------------------------------------------------- Negocio
  function renderBusiness(root) {
    const r = report, b = r.business || {};
    const tv = r.split?.trainval, te = r.split?.test;
    const card = make('div', {className: 'ml-kpis'});
    for (const [label, value, sub] of [
      ['Registros', fmt(r.source?.records, 0), r.source?.name],
      ['Hospitales de entrenamiento', fmt(tv?.hospitals?.length, 0), `${fmt(tv?.records, 0)} visitas`],
      ['Hospitales de prueba', fmt(te?.hospitals?.length, 0), `${fmt(te?.records, 0)} visitas`],
      ['Modo de entrenamiento', r.quick_mode ? 'Rápido' : 'Completo', r.quick_mode ? '3 pliegues, B = 200' : '5 pliegues, B = 2000']]) {
      card.append(make('div', {className: 'metric'}, [make('div', {className: 'label', textContent: label}),
        make('strong', {textContent: value}), make('small', {textContent: sub || ''})]));
    }
    root.append(card);
    const t = r.targets || {};
    const phases = [
      ['1. Comprensión del negocio', !!r.business, 'Objetivo, alcance y limitaciones declaradas'],
      ['2. Comprensión de los datos (EDA)', !!r.eda?.descriptives, 'Descriptivos, distribuciones, correlación, pruebas de particiones'],
      ['3. Preparación de los datos', !!r.preparation, 'Limpieza de códigos especiales, rangos válidos, imputación'],
      ['4. Modelado / entrenamiento', Object.values(t).every(x => x.cv), '5 algoritmos candidatos por objetivo'],
      ['   Validación cruzada', Object.values(t).every(x => x.cv), 'Anidada, agrupada por hospital'],
      ['   Hiperparámetros', Object.values(t).every(x => x.tuning?.search_space), 'RandomizedSearchCV en la validación interna'],
      ['   Selección del mejor modelo', Object.values(t).every(x => x.selection?.comparisons), 'Bootstrap fuera de pliegue por hospital + Holm + parsimonia'],
      ['5. Evaluación con pruebas robustas', Object.values(t).every(x => x.statistics?.metric_ci), 'Bootstrap por hospital, Wilcoxon/DeLong, Friedman–Nemenyi, calibración'],
      ['   Explicabilidad', Object.values(t).every(x => x.explainability), 'Permutación, SHAP global y local, dependencia parcial'],
      ['6. Despliegue', true, 'API local y esta interfaz']];
    const rows = phases.map(([fase, ok, detalle]) => ({fase, estado: ok ? 'Cumplido' : 'Pendiente', detalle}));
    root.append(C.panel('Cumplimiento de la metodología CRISP-DM', C.table(rows, [['fase', 'Fase'], ['estado', 'Estado'], ['detalle', 'Evidencia en el informe']],
      {highlight: r => r.estado !== 'Cumplido'}), {
      prueba: 'Checklist CRISP-DM (sin prueba inferencial)',
      base: `${BASE.informe} · metadatos report.business, report.eda, report.targets`,
      comoLeer: 'Cada fila es una fase de CRISP-DM; "Cumplido" significa que el informe de entrenamiento contiene los resultados de esa fase y que se muestran en su pestaña.',
      interpretacion: `${rows.filter(x => x.estado === 'Cumplido').length} de ${rows.length} elementos presentes. ${b.objective || ''}`,
    }));
    const summary = Object.entries(t).map(([k, v]) => {
      const mk = metricKey(k);
      const imp = v.test_baseline?.[mk] ? (1 - v.test_selected[mk] / v.test_baseline[mk]) : null;
      return {objetivo: TARGETS[k], modelo: modelName(v.selected_key || v.selected), metrica: metricName(k),
        prueba: fmt(v.test_selected?.[mk], 3), referencia: fmt(v.test_baseline?.[mk], 3), mejora: imp == null ? '—' : pct(imp),
        p: pv(v.statistics?.comparison_p)};
    });
    root.append(C.panel('Resultado final por objetivo', C.table(summary, [['objetivo', 'Objetivo'], ['modelo', 'Modelo elegido'],
      ['metrica', 'Métrica'], ['prueba', 'Prueba'], ['referencia', 'Referencia'], ['mejora', 'Mejora'], ['p', 'p (modelo vs referencia)']]), {
      prueba: 'Wilcoxon (regresión) o DeLong (clasificación) · p en statistics.comparison_p',
      base: `${BASE.test} · métricas report.targets[*].test_selected y test_baseline`,
      comoLeer: 'Métrica en los hospitales de prueba, que nunca se usaron para entrenar ni para elegir. Menor es mejor en MAE y Brier. "Mejora" es la reducción relativa frente a predecir una constante.',
      interpretacion: summary.map(s => `${s.objetivo}: ${s.modelo}, mejora ${s.mejora} (p ${s.p})`).join('. ') + '.',
    }));
    const lim = make('ul', {className: 'ml-list'}, (r.limits || []).map(l => make('li', {textContent: l})));
    root.append(C.panel('Limitaciones declaradas', lim, {
      prueba: 'Declaración cualitativa (sin prueba estadística)',
      base: 'report.limits · contexto report.business',
      comoLeer: 'Condiciones bajo las cuales los resultados son válidos.',
      interpretacion: b.interpretacion,
    }));
  }

  // ---------------------------------------------------------------- EDA
  function renderEDA(root) {
    const eda = report.eda || {};
    const desc = eda.descriptives?.data || {};
    const rows = Object.entries(desc).map(([k, v]) => ({variable: NAMES[k] || k, unidad: UNITS[k] || '', n: fmt(v.weighted.n, 0),
      falt: pct(v.weighted.missing), media: fmt(v.weighted.mean), mediana: fmt(v.weighted.median),
      ric: `${fmt(v.weighted.q1)} – ${fmt(v.weighted.q3)}`, rango: `${fmt(v.weighted.min)} – ${fmt(v.weighted.max)}`, atip: fmt(v.weighted.outliers_iqr, 0)}));
    const worst = Object.entries(desc).sort((a, b) => b[1].weighted.missing - a[1].weighted.missing)[0];
    const skewed = Object.entries(desc).filter(([, v]) => v.weighted.outliers_iqr > 0.02 * v.weighted.n).map(([k]) => NAMES[k]);
    root.append(C.panel('Estadística descriptiva de las variables de llegada', C.table(rows, [['variable', 'Variable'], ['unidad', 'Unidad'],
      ['n', 'n válidos'], ['falt', 'Faltantes'], ['media', 'Media ponderada'], ['mediana', 'Mediana'], ['ric', 'RIC (Q1–Q3)'], ['rango', 'Mín – máx'], ['atip', 'Atípicos (1,5·RIC)']]), {
      prueba: 'Descriptiva ponderada (media, mediana, RIC, atípicos 1,5·RIC) — sin prueba inferencial',
      base: `${BASE.eda} · report.eda.descriptives · 11 variables de llegada`,
      comoLeer: 'La media está ponderada con PATWT para representar las visitas nacionales. El RIC contiene el 50 % central de los datos; los atípicos quedan fuera de 1,5 RIC.',
      interpretacion: worst ? `${NAMES[worst[0]]} es la variable con más faltantes (${pct(worst[1].weighted.missing)}); los modelos de árboles la tratan como ausencia y el lineal la imputa con la mediana más un indicador de faltante. ` +
        (skewed.length ? `Tienen más de 2 % de atípicos: ${skewed.join(', ')}. Por eso se usan medianas y la pérdida absoluta.` : 'No hay variables con muchos atípicos.') : '',
    }));

    const select = make('select', {className: 'ml-select', ariaLabel: 'Variable del histograma'});
    Object.keys(desc).forEach(k => select.add(new Option(NAMES[k] || k, k)));
    const holder = make('div');
    const histPanel = C.panel('Histograma de variables de llegada', [make('label', {className: 'ml-inline', textContent: 'Variable: '}, select), holder], {
      prueba: 'Histograma ponderado (descriptiva)',
      base: `${BASE.eda} · report.eda.descriptives[*].histogram · pesos PATWT`,
      comoLeer: 'Cada barra es la proporción ponderada de visitas en ese intervalo. Las líneas marcan mediana y media.',
    });
    const drawHist = () => {
      const k = select.value, v = desc[k];
      holder.replaceChildren(C.histogram(v.histogram, {xLabel: `${NAMES[k]} (${UNITS[k] || ''})`,
        markers: [[v.weighted.median, 'ref', 'mediana'], [v.weighted.mean, 'ref2', 'media']], aria: `Histograma ${NAMES[k]}`}));
      const box = histPanel.querySelector('.ml-interpret');
      box.replaceChildren(
        make('p', {}, [make('strong', {textContent: 'Cómo leerlo: '}), `Cada barra es la proporción ponderada de visitas en ese intervalo de ${NAMES[k]}. Las líneas marcan la mediana y la media.`]),
        make('p', {}, [make('strong', {textContent: 'Interpretación: '}),
          `Mediana ${fmt(v.weighted.median)} y media ${fmt(v.weighted.mean)}; ${Math.abs(v.weighted.mean - v.weighted.median) > 0.1 * Math.abs(v.weighted.median || 1) ?
            (v.weighted.mean > v.weighted.median ? 'la media supera a la mediana: distribución asimétrica a la derecha.' : 'la media es menor que la mediana: asimetría a la izquierda.') :
            'media y mediana similares: distribución aproximadamente simétrica.'} Faltan ${pct(v.weighted.missing)} de los valores.`]));
    };
    select.addEventListener('change', drawHist);
    root.append(histPanel); drawHist();

    const tg = eda.targets?.data || {};
    const logFmt = v => fmt(Math.expm1(v), 0);
    const panels = [];
    for (const k of ['visit_minutes', 'wait_minutes']) {
      const d = tg[k]; if (!d) continue;
      panels.push(C.panel(`Distribución de ${TARGETS[k]}`, C.histogram(d.log_histogram, {xLabel: 'Minutos (escala logarítmica)', xFormat: logFmt,
        markers: [[Math.log1p(d.median), 'ref', 'mediana']], color: k === 'wait_minutes' ? C.COLORS[1] : C.COLORS[0]}), {
        prueba: 'Histograma log(1+x) y descriptivos ponderados',
        base: `${BASE.eda} · report.eda.targets.data.${k} · columna NHAMCS ${k === 'visit_minutes' ? 'LOV' : 'WAITTIME'}`,
        comoLeer: 'El eje horizontal está en escala logarítmica (log(1 + minutos)) porque hay visitas extremadamente largas; las etiquetas muestran minutos reales.',
        interpretacion: `Mediana ${fmt(d.median, 0)} min, RIC ${fmt(d.q1, 0)}–${fmt(d.q3, 0)} min, media ${fmt(d.mean, 0)} min y máximo ${fmt(d.max, 0)} min. ` +
          `La media ${d.mean > d.median * 1.2 ? 'es mucho mayor que' : 'se parece a'} la mediana: ${d.mean > d.median * 1.2 ? 'cola larga a la derecha, por lo que el MAE es más adecuado que el error cuadrático.' : 'distribución poco asimétrica.'}`,
      }));
    }
    const hosp = tg.hospitalization;
    if (hosp) panels.push(C.panel('Prevalencia de ingreso hospitalario (ADMITHOS)', C.barChart([
      {label: 'No ingresa', value: 1 - hosp.prevalence, color: C.COLORS[0]}, {label: 'Ingresa', value: hosp.prevalence, color: C.COLORS[4]}],
      {xLabel: 'Proporción ponderada', digits: 3}), {
      prueba: 'Prevalencia ponderada (descriptiva)',
      base: `${BASE.eda} · report.eda.targets.data.hospitalization · columna ADMITHOS`,
      comoLeer: 'Proporción ponderada de visitas con y sin ingreso en el mismo hospital.',
      interpretacion: `Solo el ${pct(hosp.prevalence)} de las visitas termina en ingreso: las clases están desbalanceadas. Por eso se evalúa con Brier, AUC y precisión media además de la exactitud, y la referencia es predecir siempre ${pct(hosp.prevalence)}.`,
    }));
    root.append(grid(...panels));

    const bt = eda.by_triage || {};
    const tp = [];
    for (const k of ['visit_minutes', 'wait_minutes']) {
      const d = bt.data?.[k]; if (!d) continue;
      const items = Object.entries(d).map(([lvl, v]) => ({label: `Triaje ${lvl}`, median: v.median, q1: v.q1, q3: v.q3, n: v.n}));
      const hi = items.reduce((a, b) => a.median > b.median ? a : b), lo = items.reduce((a, b) => a.median < b.median ? a : b);
      tp.push(C.panel(`${TARGETS[k]} según triaje (Kruskal–Wallis)`, C.rangeChart(items, {yLabel: 'Minutos', zero: true, color: k === 'wait_minutes' ? C.COLORS[1] : C.COLORS[0]}), {
        prueba: `Kruskal–Wallis (scipy.stats.kruskal) · p = ${pv(bt.kruskal_p?.[k])} · report.eda.by_triage.kruskal_p.${k}`,
        base: `${BASE.eda} · medianas y RIC por IMMEDR (triaje 1–5) · ${Object.values(d).reduce((a, v) => a + v.n, 0)} visitas`,
        comoLeer: 'La línea gruesa es la mediana y la caja el rango intercuartílico en cada nivel de triaje (1 = inmediato, 5 = no urgente). Kruskal–Wallis contrasta si las medianas difieren entre niveles.',
        interpretacion: `La mediana va de ${fmt(lo.median, 0)} min (${lo.label}) a ${fmt(hi.median, 0)} min (${hi.label}). Kruskal–Wallis p = ${pv(bt.kruskal_p?.[k])}: ` +
          (bt.kruskal_p?.[k] < 0.05 ? 'el triaje se asocia significativamente con el objetivo, así que es una variable predictiva relevante.' : 'no hay evidencia de diferencias entre niveles.'),
      }));
    }
    root.append(grid(...tp));

    const corr = eda.correlation?.data || {};
    const labels = Object.keys(corr);
    const pairs = [];
    labels.forEach((a, i) => labels.slice(i + 1).forEach(b => { if (corr[a][b] != null) pairs.push([a, b, corr[a][b]]); }));
    pairs.sort((p, q) => Math.abs(q[2]) - Math.abs(p[2]));
    const top = pairs.slice(0, 3).map(([a, b, v]) => `${NAMES[a]}–${NAMES[b]} (ρ = ${fmt(v, 2)})`).join(', ');
    const withTarget = ['visit_minutes', 'hospitalization'].map(t => {
      const best = labels.filter(l => !TARGETS[l]).map(l => [l, corr[l][t]]).filter(x => x[1] != null).sort((p, q) => Math.abs(q[1]) - Math.abs(p[1]))[0];
      return best ? `${NAMES[t]}: ${NAMES[best[0]]} (ρ = ${fmt(best[1], 2)})` : '';
    }).filter(Boolean).join('; ');
    root.append(C.panel('Correlación de Spearman (ρ) entre variables y objetivos', C.heatmap(corr, labels, {names: NAMES}), {
      prueba: 'Correlación de Spearman (pandas.corr method=spearman) — asociación monótona, sin p-valores por celda',
      base: `${BASE.eda} · report.eda.correlation.data · 11 features + 3 objetivos`,
      comoLeer: 'Azul = asociación positiva, rojo = negativa, blanco = ninguna. Spearman mide relaciones monótonas y es robusto a atípicos. Pasa el cursor sobre una celda para ver el valor.',
      interpretacion: `Asociaciones más fuertes: ${top}. Variable más asociada con cada objetivo — ${withTarget}. Correlaciones bajas con los objetivos anticipan un poder predictivo moderado.`,
    }));

    const parts = eda.partitions?.data || [];
    const sig = parts.filter(p => p.holm_p < 0.05);
    root.append(C.panel('Comparación de particiones (Kolmogorov–Smirnov + Holm)', C.table(parts.map(p => ({v: p.variable.replaceAll('_', ' '),
      p: pv(p.ks_p), h: pv(p.holm_p), s: p.holm_p < 0.05 ? 'Sí' : 'No'})), [['v', 'Variable y particiones'], ['p', 'p KS'], ['h', 'p Holm'], ['s', 'Diferencia significativa']],
      {highlight: r => r.s === 'Sí'}), {
      prueba: 'Kolmogorov–Smirnov (scipy.stats.ks_2samp) + corrección Holm–Bonferroni (motor/ml_stats.holm_correction)',
      base: `${BASE.eda} · report.eda.partitions · train vs validation vs test (4 primeras variables)`,
      comoLeer: 'KS compara la distribución de una variable entre dos particiones de hospitales; Holm corrige por comparaciones múltiples. p > 0,05 indica distribuciones compatibles.',
      interpretacion: sig.length ? `${sig.length} de ${parts.length} comparaciones difieren: los hospitales no son intercambiables en esas variables, lo que refuerza separar por hospital para no sobreestimar el rendimiento.`
        : `Ninguna de las ${parts.length} comparaciones es significativa tras Holm: las particiones son comparables y la evaluación en prueba es representativa.`,
    }));
  }

  // ---------------------------------------------------------------- Preparación
  function renderPreparation(root) {
    const p = report.preparation || {};
    const miss = Object.entries(p.feature_missing_fraction || {}).sort((a, b) => b[1] - a[1]);
    root.append(C.panel('Datos faltantes tras la limpieza', C.barChart(miss.map(([k, v]) => ({label: NAMES[k] || k, value: v, color: v > 0.2 ? C.COLORS[4] : C.COLORS[0]})),
      {xLabel: 'Proporción de valores faltantes', digits: 3}), {
      prueba: 'Proporción de missing (descriptiva)',
      base: `${BASE.prep} · report.preparation.feature_missing_fraction`,
      comoLeer: 'Proporción de visitas sin dato válido tras convertir códigos especiales NHAMCS (negativos, 998, Doppler) y valores fuera de rango. Rojo = más de 20 %.',
      interpretacion: `${miss.filter(([, v]) => v > 0.2).map(([k]) => NAMES[k]).join(', ') || 'Ninguna variable'} supera el 20 % de faltantes. ${p.cleaning || ''} Los árboles tratan la ausencia como información propia.`,
    }));
    const rules = [['Edad', 'AGE; 0 = menor de un año, 94 = 94 o más'], ['Temperatura', 'TEMPF en décimas de °F → °C; rango 15–45 °C'],
      ['Signos vitales', 'Pulso 0–350, respiración 0–150, PA sistólica 0–350, diastólica 0–250'], ['Triaje', 'IMMEDR 1–5; otros códigos → ausente'],
      ['Dolor', 'PAINSCALE 0–10'], ['Ambulancia', 'ARREMS 1 = sí, 2 = no'], ['Hora de llegada', 'ARRTIME hhmm → hora decimal'],
      ['Etiquetas', 'Se excluyen visitas sin objetivo válido o con peso PATWT no positivo'], ['Fugas de información', 'No se usan disposición, tratamientos ni duración como entradas']];
    root.append(C.panel('Reglas de preparación', C.table(rules.map(([a, b]) => ({a, b})), [['a', 'Elemento'], ['b', 'Regla aplicada']]), {
      prueba: 'Reglas de limpieza (motor/ml.py clean_features) — sin prueba inferencial',
      base: `${BASE.prep} · report.preparation.cleaning`,
      comoLeer: 'Transformaciones aplicadas antes de entrenar, idénticas en entrenamiento, prueba y predicción.',
      interpretacion: p.interpretacion,
    }));
    const counts = Object.entries(report.targets || {}).map(([k, t]) => ({o: TARGETS[k], tv: fmt(t.counts?.trainval, 0), te: fmt(t.counts?.test, 0), el: fmt(t.eligible, 0)}));
    root.append(C.panel('Registros utilizables por objetivo', C.table(counts, [['o', 'Objetivo'], ['el', 'Con etiqueta válida'], ['tv', 'Entrenamiento + validación'], ['te', 'Prueba']]), {
      prueba: 'Conteos por partición (descriptiva)',
      base: `${BASE.informe} · report.split + report.targets[*].counts · GroupShuffleSplit por HOSPCODE (80/20)`,
      comoLeer: 'La partición es por hospital (80 % / 20 %): ningún hospital aparece en entrenamiento y prueba a la vez.',
      interpretacion: 'Cada objetivo tiene distinto número de visitas porque se excluyen las que no tienen ese dato; la partición de hospitales es la misma para los tres.',
    }));
  }

  // ---------------------------------------------------------------- CV
  function cvChart(t, k) {
    const entries = Object.entries(t.cv).filter(([, v]) => v && v.fold_scores);
    const sel = t.selected_key;
    return C.barChart(entries.map(([m, v]) => ({label: MODELS[m] || m, value: v.mean, error: v.std, points: v.fold_scores,
      color: m === sel ? C.COLORS[2] : m === 'baseline' ? '#9aa6ae' : C.COLORS[0]})),
      {xLabel: `${metricName(k)} en validación (menor es mejor)`, reference: t.cv.baseline?.mean, digits: 3, min: 0,
        legend: [{label: 'Modelo elegido', color: C.COLORS[2]}, {label: 'Referencia constante (línea)', color: '#8a97a0', dashed: true}]});
  }

  function renderCV(root) {
    for (const [k, t] of Object.entries(report.targets || {})) {
      root.append(heading(TARGETS[k]));
      const entries = Object.entries(t.cv).filter(([, v]) => v && v.fold_scores);
      const best = entries.reduce((a, b) => a[1].mean < b[1].mean ? a : b);
      const base = t.cv.baseline;
      const gain = base ? 1 - best[1].mean / base.mean : null;
      const cvStable = entries.map(([m, v]) => [m, v.std / v.mean]).sort((a, b) => a[1] - b[1])[0];
      root.append(C.panel('Validación cruzada anidada por hospital', cvChart(t, k), {
        prueba: `Media ± desv. estándar de ${metricName(k)} por pliegue externo (comparación emparejada)`,
        base: `${BASE.cv} · report.targets.${k}.cv · ${best[1].fold_scores.length} pliegues GroupKFold`,
        comoLeer: `Cada barra es la media del ${metricName(k)} en los pliegues externos; la barra de error es ± 1 desviación estándar y los puntos son los pliegues individuales. Los hiperparámetros se eligen solo con hospitales de entrenamiento (validación interna).`,
        interpretacion: `Mejor media: ${MODELS[best[0]]} (${fmt(best[1].mean, 3)} ± ${fmt(best[1].std, 3)}), ${gain == null ? '' : gain > 0 ? `${pct(gain)} mejor que la referencia constante` : 'sin mejorar a la referencia constante'}. ` +
          `El modelo más estable entre hospitales es ${MODELS[cvStable[0]]} (coeficiente de variación ${pct(cvStable[1])}). La dispersión entre pliegues muestra cuánto cambia el rendimiento de un grupo de hospitales a otro.`,
      }));
      const folds = best[1].fold_scores.map((_, i) => i);
      const rows = entries.map(([m, v]) => Object.assign({m: MODELS[m]}, ...folds.map(i => ({[`f${i}`]: fmt(v.fold_scores[i], 3)})), {mean: fmt(v.mean, 3), sd: fmt(v.std, 3)}));
      root.append(C.panel('Métrica por pliegue (tabla)', C.table(rows, [['m', 'Modelo'], ...folds.map(i => [`f${i}`, `Pliegue ${i + 1}`]), ['mean', 'Media'], ['sd', 'Desv.']],
        {highlight: r => r.m === MODELS[t.selected_key]}), {
        prueba: 'Puntuaciones emparejadas por pliegue (insumo para Friedman y Nadeau–Bengio)',
        base: `${BASE.cv} · report.targets.${k}.cv[*].fold_scores`,
        comoLeer: 'Mismos pliegues para todos los modelos (comparación emparejada), lo que permite las pruebas de Friedman y Nadeau–Bengio de la pestaña Selección.',
        interpretacion: `Fila resaltada: modelo elegido (${MODELS[t.selected_key]}).`,
      }));
    }
  }

  // ---------------------------------------------------------------- Hiperparámetros
  function renderTuning(root) {
    for (const [k, t] of Object.entries(report.targets || {})) {
      root.append(heading(TARGETS[k]));
      const tu = t.tuning || {};
      const space = [];
      for (const [m, s] of Object.entries(tu.search_space || {}))
        for (const [p, d] of Object.entries(s.params || {})) space.push({m: MODELS[m], p: p.replace('model__', ''), d, n: s.n_iter});
      root.append(C.panel('Espacio de búsqueda de hiperparámetros', C.table(space, [['m', 'Modelo'], ['p', 'Hiperparámetro'], ['d', 'Distribución muestreada'], ['n', 'Combinaciones probadas']]), {
        prueba: 'RandomizedSearchCV (sklearn) · CV interna 3 pliegues por hospital',
        base: `${BASE.cv} · report.targets.${k}.tuning.search_space`,
        comoLeer: `RandomizedSearchCV prueba combinaciones aleatorias y elige la de menor ${metricName(k)} en validación cruzada interna ponderada con PATWT.`,
        interpretacion: `Se exploran ${space.length} hiperparámetros en ${Object.keys(tu.search_space || {}).length - 1} algoritmos; la referencia constante no tiene hiperparámetros.`,
      }));
      const best = Object.entries(tu.best_params || {});
      const foldP = tu.fold_params?.[t.selected_key] || [];
      const rows = best.map(([p, v]) => {
        const vals = foldP.map(f => f[p]).filter(x => typeof x === 'number');
        const cv = vals.length > 1 ? Math.sqrt(vals.reduce((a, b) => a + (b - vals.reduce((x, y) => x + y) / vals.length) ** 2, 0) / vals.length) / Math.abs(vals.reduce((x, y) => x + y) / vals.length) : null;
        return {p: p.replace('model__', ''), v: fmt(v, 4), f: vals.map(x => fmt(x, 3)).join(' · '), s: cv == null ? '—' : cv < 0.3 ? 'Estable' : 'Variable'};
      });
      const unstable = rows.filter(r => r.s === 'Variable').map(r => r.p);
      root.append(C.panel(`Hiperparámetros del modelo final (${MODELS[t.selected_key]})`, rows.length ? C.table(rows, [['p', 'Hiperparámetro'], ['v', 'Valor final'], ['f', 'Valor elegido en cada pliegue externo'], ['s', 'Estabilidad']])
        : make('p', {className: 'ml-empty', textContent: 'El modelo elegido es la referencia constante: no tiene hiperparámetros.'}), {
        prueba: 'Estabilidad entre pliegues (descriptiva: coeficiente de variación)',
        base: `${BASE.cv} · report.targets.${k}.tuning.best_params y fold_params`,
        comoLeer: 'El valor final se obtiene repitiendo la búsqueda con todos los hospitales de entrenamiento. La columna de pliegues muestra qué se eligió en cada repetición de la validación anidada.',
        interpretacion: rows.length ? (unstable.length ? `${unstable.join(', ')} cambian bastante entre pliegues: el rendimiento es poco sensible a ellos dentro del rango explorado.` : 'Los valores elegidos son parecidos en todos los pliegues: la búsqueda es estable.') : 'Seleccionar la constante indica que ningún algoritmo supera significativamente a predecir la mediana.',
      }));
    }
  }

  // ---------------------------------------------------------------- Selección
  function renderSelection(root) {
    for (const [k, t] of Object.entries(report.targets || {})) {
      root.append(heading(TARGETS[k]));
      const s = t.selection || {};
      const rank = (s.ranking || []).map((r, i) => ({i: i + 1, m: MODELS[r.name], oof: fmt(r.oof, 4), mean: fmt(r.mean, 4), sd: fmt(r.std, 4), key: r.name}));
      root.append(C.panel('Ranking en validación cruzada', C.table(rank, [['i', '#'], ['m', 'Modelo'], ['oof', `${metricName(k)} fuera de pliegue`], ['mean', 'Media por pliegue'], ['sd', 'Desv.']],
        {highlight: r => r.key === t.selected_key}), {
        prueba: 'Orden por métrica fuera de pliegue (OOF) — descriptiva',
        base: `${BASE.cv} · report.targets.${k}.selection.ranking`,
        comoLeer: `Modelos ordenados por ${metricName(k)} de predicciones fuera de pliegue (cada visita se predice con un modelo que no la vio; menor es mejor). Fila resaltada: modelo elegido.`,
        interpretacion: s.justification,
      }));
      const comps = s.comparisons || [];
      root.append(C.panel(`Comparación con el mejor modelo (${MODELS[s.best_cv] || ''})`, [
        C.forestPlot(comps.map(c => ({label: MODELS[c.model], point: c.mean_diff, lo: c.ci_low, hi: c.ci_high,
          color: c.equivalent ? C.COLORS[2] : C.COLORS[4]})), {reference: 0, xLabel: `Diferencia de ${metricName(k)} frente al mejor (positivo = peor)`, digits: 4,
          legend: [{label: 'Equivalente al mejor', color: C.COLORS[2]}, {label: 'Significativamente peor', color: C.COLORS[4]}]}),
        C.table(comps.map(c => ({m: MODELS[c.model], d: fmt(c.mean_diff, 4), ci: `${fmt(c.ci_low, 4)} a ${fmt(c.ci_high, 4)}`, p: pv(c.p_value), h: pv(c.p_holm),
          nb: `t = ${fmt(c.nb_t, 2)}, p = ${pv(c.nb_p)}`, e: c.equivalent ? 'Sí' : 'No'})),
          [['m', 'Modelo'], ['d', 'Diferencia'], ['ci', 'IC 95 % (bootstrap por hospital)'], ['p', 'p'], ['h', 'p Holm'], ['nb', 'Nadeau–Bengio (pliegues)'], ['e', 'Equivalente']])], {
        prueba: 'Bootstrap por hospital de OOF (cluster_bootstrap_diff, B=2000) + Holm + Nadeau–Bengio t corregida',
        base: `${BASE.cv} · report.targets.${k}.selection.comparisons · predicciones fuera de pliegue emparejadas`,
        comoLeer: 'Se remuestrean hospitales y se compara el error de cada modelo con el del mejor sobre las mismas visitas fuera de pliegue; Holm corrige por comparar varios modelos. Nadeau–Bengio es complementaria sobre métricas por pliegue.',
        interpretacion: `Regla de parsimonia: entre modelos equivalentes se elige el más simple. ${comps.filter(c => !c.equivalent).length} de ${comps.length} modelos son significativamente peores que ${MODELS[s.best_cv]}. Elegido: ${MODELS[t.selected_key]}.`,
      }));
      const ranks = s.nemenyi?.mean_ranks || {};
      const cd = s.nemenyi?.critical_difference;
      const bestRank = Math.min(...Object.values(ranks));
      root.append(C.panel('Friedman y Nemenyi: rango medio de cada modelo', C.barChart(Object.entries(ranks).sort((a, b) => a[1] - b[1]).map(([m, v]) => ({label: MODELS[m], value: v,
        color: v - bestRank > cd ? '#9aa6ae' : C.COLORS[2]})), {xLabel: 'Rango medio en los pliegues (1 = mejor)', reference: cd == null ? null : bestRank + cd, digits: 2, min: 0,
        legend: [{label: 'Dentro de la diferencia crítica del mejor', color: C.COLORS[2]}, {label: 'Límite de la diferencia crítica', color: '#8a97a0', dashed: true}]}), {
        prueba: `Friedman (scipy.stats.friedmanchisquare) · p = ${pv(s.friedman?.p_value)} · Nemenyi post-hoc (DC = ${fmt(cd, 2)})`,
        base: `${BASE.cv} · report.targets.${k}.selection.friedman y nemenyi · rangos medios por pliegue`,
        comoLeer: 'Friedman contrasta si todos los modelos rinden igual ordenándolos en cada pliegue. Nemenyi da la diferencia crítica (DC): dos modelos cuyo rango medio difiere menos que la DC no se distinguen estadísticamente.',
        interpretacion: `Friedman χ² = ${fmt(s.friedman?.statistic, 2)}, p = ${pv(s.friedman?.p_value)}: ${s.friedman?.p_value < 0.05 ? 'hay diferencias globales entre modelos.' : 'no hay evidencia de diferencias globales; con pocos pliegues la prueba tiene poca potencia.'} DC = ${fmt(cd, 2)} rangos.`,
      }));
    }
  }

  // ---------------------------------------------------------------- Prueba
  function renderTest(root) {
    for (const [k, t] of Object.entries(report.targets || {})) {
      root.append(heading(TARGETS[k], `Modelo evaluado: ${MODELS[t.selected_key]} · ${fmt(t.counts?.test, 0)} visitas de hospitales nunca vistos`));
      const st = t.statistics || {}, mk = metricKey(k), ci = st.metric_ci || {}, diff = st.diff_vs_baseline || {};
      const constant = t.selected_key === 'baseline';
      const better = diff.ci_high < 0, worse = diff.ci_low > 0;
      root.append(grid(
        C.panel('Intervalos de confianza por bootstrap de hospitales', C.forestPlot([
          {label: `${metricName(k)} modelo`, point: ci.point, lo: ci.ci_low, hi: ci.ci_high, color: C.COLORS[2]},
          {label: 'Diferencia vs referencia', point: diff.diff, lo: diff.ci_low, hi: diff.ci_high, color: C.COLORS[1]}], {reference: 0, xLabel: metricName(k)}), {
          prueba: `Bootstrap por cluster hospitalario (cluster_bootstrap_ci / cluster_bootstrap_diff, B=${fmt(ci.n_boot, 0)}) · IC 95 % percentil`,
          base: `${BASE.test} · report.targets.${k}.statistics · ${fmt(ci.clusters, 0)} hospitales de prueba`,
          comoLeer: `Se remuestrean hospitales completos con reemplazo (${fmt(ci.n_boot, 0)} veces, ${fmt(ci.clusters, 0)} hospitales), porque los pacientes de un mismo hospital no son independientes. Los extremos son el IC 95 % percentil; la línea vertical es cero.`,
          interpretacion: constant ? 'El modelo elegido es la propia referencia, así que la diferencia es exactamente cero.' :
            `${metricName(k)} = ${fmt(ci.point, 3)} (IC 95 % ${fmt(ci.ci_low, 3)}–${fmt(ci.ci_high, 3)}). Diferencia con la referencia ${fmt(diff.diff, 3)} (IC ${fmt(diff.ci_low, 3)} a ${fmt(diff.ci_high, 3)}, p bootstrap ${pv(diff.p_value)}): ` +
            (better ? 'el intervalo queda completamente bajo cero, el modelo mejora de forma robusta.' : worse ? 'el intervalo queda sobre cero, el modelo es peor que la referencia.' : 'el intervalo incluye el cero, la mejora no es concluyente entre hospitales.'),
        }),
        isCls(k) ? testClassification(t, st) : testRegression(t, st)));
      const tri = Object.entries(t.test_by_triage || {});
      if (tri.length) {
        const sigL = tri.filter(([, v]) => v.diff_vs_baseline?.p_holm < 0.05 && v.diff_vs_baseline.diff < 0).map(([l]) => l);
        const worseL = tri.filter(([, v]) => v.diff_vs_baseline?.ci_low > 0).map(([l]) => l);
        root.append(C.panel('Rendimiento por nivel de triaje (subgrupos)', C.forestPlot(tri.map(([l, v]) => ({label: `Triaje ${l} (n=${v.n})`,
          point: v.diff_vs_baseline?.diff, lo: v.diff_vs_baseline?.ci_low, hi: v.diff_vs_baseline?.ci_high,
          color: v.diff_vs_baseline?.ci_high < 0 ? C.COLORS[2] : v.diff_vs_baseline?.ci_low > 0 ? C.COLORS[4] : C.COLORS[0]})),
          {reference: 0, xLabel: `Diferencia de ${metricName(k)}: modelo − referencia (negativo = mejor)`}), {
          prueba: 'Bootstrap por hospital en subgrupos + corrección Holm (5 niveles de triaje IMMEDR)',
          base: `${BASE.test} · report.targets.${k}.test_by_triage · visitas estratificadas por triaje`,
          comoLeer: 'Cada fila compara el modelo con la referencia solo dentro de un nivel de triaje, con IC por bootstrap de hospitales. Verde = mejora robusta, rojo = empeora, azul = no concluyente.',
          interpretacion: constant ? 'Modelo constante: sin diferencias por construcción.' :
            `${sigL.length ? `Mejora significativa (Holm) en triaje ${sigL.join(', ')}.` : 'Ningún subgrupo muestra una mejora significativa tras Holm.'} ${worseL.length ? `Empeora en triaje ${worseL.join(', ')}: el modelo no debe usarse igual para todos los niveles.` : ''} Los niveles 1 y 5 tienen pocas visitas, por eso sus intervalos son más anchos.`,
        }));
      }
    }
  }

  function testRegression(t, st) {
    const w = st.wilcoxon || {};
    const pts = (t.explainability?.diagnostics?.scatter || []).map(p => ({x: p.observed, y: p.predicted}));
    const sorted = pts.map(p => p.x).sort((a, b) => a - b);
    const cap = sorted[Math.floor(sorted.length * 0.95)] || 1;
    return C.panel('Observado frente a predicho (Wilcoxon)', C.scatter(pts, {cap, xLabel: 'Minutos observados', yLabel: 'Minutos predichos'}), {
      prueba: `Wilcoxon de rangos con signo unilateral (wilcoxon_signed_errors) · p = ${pv(w.p_value)} · mediana diff errores = ${fmt(w.median_diff, 1)} min`,
      base: `${BASE.test} · report.targets.*.explainability.diagnostics.scatter (muestra ≤500 visitas, percentil 95 en eje)`,
      comoLeer: 'Cada punto es una visita de prueba. Cuanto más cerca de la diagonal, mejor. Wilcoxon contrasta si los errores absolutos del modelo son menores que los de la referencia en las mismas visitas.',
      interpretacion: t.selected_key === 'baseline' ? 'La referencia predice la misma cifra para todos: los puntos forman una línea horizontal.' :
        `${w.p_value < 0.05 ? 'El modelo reduce el error de forma significativa visita a visita.' : 'No hay evidencia de que reduzca el error visita a visita.'} ` +
        'La nube se aplana hacia la media: el modelo subestima las estancias muy largas, típico cuando las variables de llegada explican poco de la duración.',
    });
  }

  function testClassification(t, st) {
    const d = st.delong || {}, hl = st.hosmer_lemeshow || {}, cf = st.calibration_fit || {};
    const cal = st.calibration || [];
    const maxP = Math.max(0.05, ...cal.map(c => Math.max(c.predicted, c.observed))) * 1.05;
    const chart = C.lineChart([
      {label: 'Calibración perfecta', x: [0, maxP], y: [0, maxP], color: '#8a97a0', dashed: true},
      {label: 'Modelo (deciles de riesgo)', x: cal.map(c => c.predicted), y: cal.map(c => c.observed), color: C.COLORS[2], markers: true}],
      {xDomain: [0, maxP], yDomain: [0, maxP], xLabel: 'Riesgo predicho', yLabel: 'Tasa observada de ingreso', xFormat: v => fmt(v * 100, 0) + '%', yFormat: v => fmt(v * 100, 0) + '%'});
    const calOk = cf.slope != null && Math.abs(cf.slope - 1) < 0.2 && Math.abs(cf.intercept) < 0.2;
    return C.panel('Calibración y discriminación (DeLong + Hosmer–Lemeshow)', chart, {
      prueba: `DeLong AUC (delong_auc) · p = ${pv(d.p_value)} · Hosmer–Lemeshow χ² = ${fmt(hl.chi2, 1)} (gl ${hl.df}), p = ${pv(hl.p_value)} · recalibración logística (pendiente ${fmt(cf.slope, 2)}, intercepto ${fmt(cf.intercept, 2)})`,
      base: `${BASE.test} · report.targets.hospitalization.statistics · deciles de riesgo (calibration_curve)`,
      comoLeer: 'Las visitas se agrupan en deciles de riesgo predicho; si el modelo está bien calibrado los puntos caen sobre la diagonal. Hosmer–Lemeshow contrasta calibración; DeLong compara AUC con la referencia.',
      interpretacion: `AUC ${fmt(d.auc_a, 3)} (IC 95 % ${fmt(d.auc_a_ci?.[0], 3)}–${fmt(d.auc_a_ci?.[1], 3)}) frente a ${fmt(d.auc_b, 3)}; DeLong p = ${pv(d.p_value)}. ` +
        (calOk ? 'Las probabilidades son fiables en promedio.' : cf.slope > 1 ? 'Las predicciones son demasiado conservadoras (poco extremas).' : 'Las predicciones son demasiado extremas; convendría recalibrar.') +
        (hl.p_value < 0.05 ? ' Con miles de visitas, Hosmer–Lemeshow detecta desviaciones pequeñas; la curva indica su tamaño real.' : ''),
    });
  }

  // ---------------------------------------------------------------- Explicabilidad
  function renderExplain(root) {
    for (const [k, t] of Object.entries(report.targets || {})) {
      root.append(heading(TARGETS[k], `Modelo explicado: ${MODELS[t.selected_key]}`));
      const ex = t.explainability || {};
      if (t.selected_key === 'baseline') {
        root.append(C.panel('Sin variables que explicar', make('p', {className: 'ml-empty', textContent: ex.shap?.message || 'El modelo elegido es constante.'}), {
          prueba: 'Modelo constante (sin explicabilidad multivariante)',
          base: `${BASE.explain} · selección report.targets.${k}.selected_key = baseline`,
          comoLeer: 'La selección eligió la referencia constante porque ningún algoritmo la supera de forma significativa.',
          interpretacion: 'Con las variables de llegada no se puede predecir mejor este objetivo que usando su mediana. Los gráficos de CV muestran lo que lograron los demás modelos.',
        }));
        continue;
      }
      const perm = Object.entries(ex.permutation || {}).sort((a, b) => b[1].mean - a[1].mean);
      const topPerm = perm.slice(0, 3).map(([f, v]) => `${NAMES[f]} (+${fmt(v.mean, isCls(k) ? 4 : 1)})`).join(', ');
      const useless = perm.filter(([, v]) => v.mean <= v.std).map(([f]) => NAMES[f]);
      const panels = [C.panel('Importancia por permutación (sklearn)', C.barChart(perm.map(([f, v]) => ({label: NAMES[f], value: v.mean, error: v.std})),
        {xLabel: `Aumento del ${metricName(k)} al desordenar la variable`, digits: isCls(k) ? 4 : 1}), {
        prueba: 'Permutation importance (5 repeticiones; error = desviación estándar)',
        base: `${BASE.explain} · report.targets.${k}.explainability.permutation · motor/ml_explain.py`,
        comoLeer: 'Se desordena al azar una variable en los datos de prueba y se mide cuánto empeora el error. Cuanto más empeora, más depende el modelo de esa variable.',
        interpretacion: `Las variables más importantes son ${topPerm}. ${useless.length ? `${useless.join(', ')} no aportan más que el ruido de la permutación.` : ''}`,
      })];
      const sh = ex.shap || {};
      if (sh.available) {
        const ranked = Object.entries(sh.mean_abs_shap).sort((a, b) => b[1] - a[1]);
        panels.push(C.panel('SHAP: contribución media absoluta', C.barChart(ranked.map(([f, v]) => ({label: NAMES[f], value: v, color: C.COLORS[3]})),
          {xLabel: `|SHAP| medio (${sh.scale})`, digits: 3}), {
          prueba: 'SHAP TreeExplainer / LinearExplainer (valores globales mean |SHAP|)',
          base: `${BASE.explain} · report.targets.${k}.explainability.shap · fondo = muestra trainval`,
          comoLeer: `SHAP reparte cada predicción entre las variables: el valor medio absoluto indica cuánto mueve cada una la predicción respecto al promedio, en ${sh.scale}.`,
          interpretacion: `${NAMES[ranked[0][0]]} es la variable que más mueve las predicciones (${fmt(ranked[0][1], 3)} ${sh.scale} de media), seguida de ${NAMES[ranked[1][0]]} y ${NAMES[ranked[2][0]]}. ` +
            (ranked[0][0] === perm[0]?.[0] ? 'Coincide con la permutación, lo que da solidez a la conclusión.' : 'El orden difiere algo del de permutación porque SHAP mide magnitud de efecto y la permutación mide pérdida de precisión.'),
        }));
        root.append(grid(...panels));
        const feats = ranked.slice(0, 8).map(([f]) => f);
        const dir = feats.slice(0, 3).map(f => {
          const pts = sh.beeswarm.filter(p => p.feature === f && p.scaled != null);
          const hi = pts.filter(p => p.scaled > 0.5), lo = pts.filter(p => p.scaled <= 0.5);
          const m = a => a.reduce((s, p) => s + p.shap, 0) / (a.length || 1);
          return `${NAMES[f]}: valores altos ${m(hi) > m(lo) ? 'aumentan' : 'reducen'} la predicción`;
        }).join('; ');
        root.append(C.panel('SHAP beeswarm: dirección del efecto', C.beeswarm(sh.beeswarm, feats, {names: NAMES, xLabel: `Valor SHAP (${sh.scale}); positivo = aumenta la predicción`}), {
          prueba: 'SHAP por visita (sin prueba inferencial; visualización de dirección)',
          base: `${BASE.explain} · report.targets.${k}.explainability.shap.beeswarm · top 8 variables`,
          comoLeer: 'Cada punto es una visita. Su posición horizontal es cuánto esa variable subió (derecha) o bajó (izquierda) la predicción; el color es el valor de la variable (rojo = alto, azul = bajo).',
          interpretacion: `${dir}. Si los colores se separan a cada lado del cero, el efecto es monótono; si se mezclan, depende de otras variables (interacciones).`,
        }));
      } else {
        panels.push(C.panel('SHAP', make('p', {className: 'ml-empty', textContent: sh.message || 'No disponible'}), {
          prueba: 'SHAP no disponible para este modelo',
          base: `${BASE.explain} · report.targets.${k}.explainability.shap`,
        }));
        root.append(grid(...panels));
      }
      const pdp = Object.entries(ex.pdp || {});
      if (pdp.length) {
        const figs = pdp.map(([f, raw]) => {
          const ok = raw.grid.map((g, j) => Number.isFinite(g) && Number.isFinite(raw.average[j]));
          const c = {grid: raw.grid.filter((_, j) => ok[j]), average: raw.average.filter((_, j) => ok[j])};
          const range = Math.max(...c.average) - Math.min(...c.average);
          const trend = c.average.at(-1) > c.average[0] ? 'aumenta' : 'disminuye';
          const y = isCls(k) ? c.average.map(v => v) : c.average;
          return C.panel(`Dependencia parcial (PDP): ${NAMES[f]}`, C.lineChart([{x: c.grid, y, color: C.COLORS[1], markers: c.grid.length <= 6}],
            {width: 380, height: 240, xLabel: `${NAMES[f]} (${UNITS[f] || ''})`, yLabel: isCls(k) ? 'Prob. media de ingreso' : 'Minutos predichos',
              yFormat: isCls(k) ? v => fmt(v * 100, 1) + '%' : undefined}), {
            prueba: 'Partial Dependence Plot (sklearn.inspection) — efecto marginal promedio',
            base: `${BASE.explain} · report.targets.${k}.explainability.pdp.${f} · conjunto de prueba`,
            comoLeer: 'Predicción media cuando todas las visitas toman ese valor de la variable y el resto se mantiene igual.',
            interpretacion: `Al pasar de ${fmt(c.grid[0])} a ${fmt(c.grid.at(-1))}, la predicción ${trend} ${isCls(k) ? pct(Math.abs(c.average.at(-1) - c.average[0])) : fmt(Math.abs(c.average.at(-1) - c.average[0]), 0) + ' min'}; el recorrido total es ${isCls(k) ? pct(range) : fmt(range, 0) + ' min'}.`,
          });
        });
        root.append(make('div', {className: 'ml-grid ml-grid-3'}, figs));
      }
    }
  }

  // ---------------------------------------------------------------- Predicción
  function renderPredict(root) {
    const fields = [['age', 'Edad (años)', 40, 0, 94], ['sex', 'Sexo (1 = F, 2 = M)', 1, 1, 2], ['triage', 'Triaje NHAMCS (1–5)', 3, 1, 5],
      ['temperature_c', 'Temperatura (°C)', 37, 15, 45], ['pulse', 'Pulso (lat/min)', 80, 0, 350], ['respiration', 'Respiración (resp/min)', 18, 0, 150],
      ['systolic', 'PA sistólica (mmHg)', 120, 0, 350], ['diastolic', 'PA diastólica (mmHg)', 80, 0, 250], ['pain', 'Dolor (0–10)', 4, 0, 10],
      ['ambulance', 'Ambulancia (0 = no, 1 = sí)', 0, 0, 1], ['arrival_hour', 'Hora de llegada (14,5 = 14:30)', 14, 0, 23.99]];
    const form = make('form', {className: 'ml-form'});
    fields.forEach(([k, label, v, min, max]) => form.append(make('label', {textContent: label},
      make('input', {name: k, type: 'number', value: v, min, max, step: k === 'triage' || k === 'sex' || k === 'ambulance' ? 1 : 'any'}))));
    form.append(make('button', {type: 'submit', textContent: 'Calcular y explicar'}));
    const out = make('div');
    root.append(C.panel('Perfil de llegada', form, {
      prueba: 'Predicción puntual + SHAP local (sin prueba inferencial)',
      base: BASE.predict,
      comoLeer: 'Deja un campo vacío para indicar dato ausente. Valores ficticios; no introduzcas datos de pacientes reales.',
      interpretacion: 'Las predicciones son exploratorias (NHAMCS 2022, EE. UU.) y no sustituyen el criterio clínico.',
    }), out);
    form.addEventListener('submit', async e => {
      e.preventDefault();
      out.replaceChildren(make('p', {textContent: 'Calculando…'}));
      const profile = Object.fromEntries([...new FormData(form)].map(([k, v]) => [k, v === '' ? null : Number(v)]));
      try {
        const res = await fetch('/api/ml/predict', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(profile)});
        const data = await res.json();
        if (!res.ok) throw new Error(data.error);
        out.replaceChildren();
        for (const [k, p] of Object.entries(data.predictions)) {
          const value = isCls(k) ? pct(p.value) : `${fmt(p.value, 0)} min`;
          const content = [make('p', {className: 'ml-big', textContent: value})];
          const scale = isCls(k) ? (p.method?.includes('linear') || p.method?.includes('hist') ? 'log-odds' : 'probabilidad') : 'minutos';
          if (Object.keys(p.contributions || {}).length) content.push(C.contributions(p.contributions, {names: NAMES, xLabel: `Contribución SHAP (${scale})`}));
          out.append(C.panel(`${TARGETS[k]} · ${modelName(p.method)}`, content, {
            prueba: 'SHAP local (TreeExplainer/LinearExplainer) sobre el perfil ingresado',
            base: `Modelo ${p.method} · modelos.joblib · mismas reglas de limpieza que el entrenamiento`,
            comoLeer: 'Barras rojas empujan la predicción hacia arriba y azules hacia abajo, respecto a la predicción media del conjunto de fondo.',
            interpretacion: p.explanation || 'Modelo constante: la predicción es igual para cualquier perfil.',
          }));
        }
        if (data.missing_features?.length) out.append(make('p', {className: 'hint', textContent: `Variables ausentes: ${data.missing_features.map(f => NAMES[f]).join(', ')}.`}));
      } catch (err) { out.replaceChildren(make('p', {className: 'error-box', textContent: err.message})); }
    });
    form.requestSubmit();
  }

  const RENDER = {business: renderBusiness, eda: renderEDA, preparation: renderPreparation, cv: renderCV, tuning: renderTuning,
    selection: renderSelection, test: renderTest, explain: renderExplain, predict: renderPredict};

  function show(id) {
    const root = $('ml-content');
    root.replaceChildren();
    $('ml-tabs').querySelectorAll('button').forEach(b => b.classList.toggle('selected', b.dataset.tab === id));
    try { RENDER[id](root); } catch (err) { root.append(make('p', {className: 'error-box', textContent: `Error al dibujar esta sección: ${err.message}`})); console.error(err); }
    history.replaceState(null, '', '#' + id);
  }

  TABS.forEach(([id, label]) => {
    const b = make('button', {type: 'button', className: 'ml-tab', textContent: label});
    b.dataset.tab = id;
    b.addEventListener('click', () => show(id));
    $('ml-tabs').append(b);
  });

  fetch('/api/ml/report').then(r => r.json().then(d => { if (!r.ok) throw new Error(d.error || 'Informe no disponible'); return d; }))
    .then(data => {
      report = data;
      const original = make('a', {href:'/api/ml/report',download:'informe-ml-original.json',textContent:'Descargar datos originales ML (JSON)'});
      $('ml-tabs').before(original);
      $('ml-trained').textContent = `● Entrenado ${new Date(data.trained_utc).toLocaleString('es-PE')}${data.quick_mode ? ' · modo rápido' : ''}`;
      const start = location.hash.slice(1);
      show(RENDER[start] ? start : 'business');
    })
    .catch(err => {
      $('ml-error').hidden = false;
      $('ml-error').textContent = `${err.message}. Ejecuta "python -m motor.train_ml" y reinicia "python -m motor.ui".`;
      $('ml-content').replaceChildren();
    });
})();
