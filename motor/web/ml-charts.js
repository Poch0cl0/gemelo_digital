(() => {
  const NS = 'http://www.w3.org/2000/svg';
  const COLORS = ['#1f77b4', '#e8743b', '#19a979', '#945ecf', '#d64550', '#13a4b4', '#8c6d31'];
  // Retain the original number when a formatted value is passed to a table.
  const value = (raw, text) => Object.assign(new String(text), {raw});
  const fmt = (v, d = 2) => v == null || !isFinite(v) ? '—' : value(v, Number(v).toLocaleString('es-PE', {maximumFractionDigits: d}));

  function node(tag, attrs = {}, text) {
    const n = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) if (v != null) n.setAttribute(k, v);
    if (text != null) n.textContent = text;
    return n;
  }

  function niceTicks(min, max, count = 5) {
    if (!isFinite(min) || !isFinite(max)) return [0];
    if (min === max) { min -= 1; max += 1; }
    const range = max - min;
    let step = Math.pow(10, Math.floor(Math.log10(range / count)));
    const err = count / range * step;
    if (err <= 0.15) step *= 10; else if (err <= 0.35) step *= 5; else if (err <= 0.75) step *= 2;
    const ticks = [];
    for (let v = Math.ceil(min / step) * step; v <= max + step * 1e-9; v += step) ticks.push(+v.toFixed(10));
    return ticks;
  }

  function scale(d0, d1, r0, r1) {
    const m = (r1 - r0) / ((d1 - d0) || 1);
    return v => r0 + (v - d0) * m;
  }

  function frame(opts) {
    const w = opts.width || 560, h = opts.height || 300;
    const m = Object.assign({t: 16, r: 18, b: 46, l: 62}, opts.margin || {});
    const svg = node('svg', {viewBox: `0 0 ${w} ${h}`, class: 'ml-chart', role: 'img', 'aria-label': opts.aria || ''});
    const [x0, x1] = opts.x, [y0, y1] = opts.y;
    const sx = scale(x0, x1, m.l, w - m.r), sy = scale(y0, y1, h - m.b, m.t);
    const g = node('g', {class: 'axis'});
    if (opts.xTicks !== false) {
      for (const t of opts.xTickValues || niceTicks(x0, x1, opts.xCount || 6)) {
        if (t < x0 - 1e-9 || t > x1 + 1e-9) continue;
        g.append(node('line', {x1: sx(t), x2: sx(t), y1: m.t, y2: h - m.b, class: 'grid'}));
        g.append(node('text', {x: sx(t), y: h - m.b + 15, 'text-anchor': 'middle'}, (opts.xFormat || fmt)(t)));
      }
    }
    if (opts.yTicks !== false) {
      for (const t of niceTicks(y0, y1, opts.yCount || 5)) {
        if (t < y0 - 1e-9 || t > y1 + 1e-9) continue;
        g.append(node('line', {x1: m.l, x2: w - m.r, y1: sy(t), y2: sy(t), class: 'grid'}));
        g.append(node('text', {x: m.l - 7, y: sy(t) + 3, 'text-anchor': 'end'}, (opts.yFormat || fmt)(t)));
      }
    }
    g.append(node('line', {x1: m.l, x2: w - m.r, y1: h - m.b, y2: h - m.b, class: 'domain'}));
    g.append(node('line', {x1: m.l, x2: m.l, y1: m.t, y2: h - m.b, class: 'domain'}));
    if (opts.xLabel) g.append(node('text', {x: (m.l + w - m.r) / 2, y: h - 8, 'text-anchor': 'middle', class: 'label'}, opts.xLabel));
    if (opts.yLabel) g.append(node('text', {x: -(m.t + h - m.b) / 2, y: 14, transform: 'rotate(-90)', 'text-anchor': 'middle', class: 'label'}, opts.yLabel));
    svg.append(g);
    return {svg, sx, sy, w, h, m};
  }

  function tooltip(el, text) { el.append(node('title', {}, text)); return el; }

  function legend(items) {
    const div = document.createElement('div');
    div.className = 'ml-legend';
    items.forEach(({label, color, dashed}) => {
      const s = document.createElement('span');
      const sw = node('svg', {viewBox: '0 0 18 10', width: 18, height: 10});
      sw.append(node('line', {x1: 0, x2: 18, y1: 5, y2: 5, stroke: color, 'stroke-width': 3, 'stroke-dasharray': dashed ? '4 3' : null}));
      s.append(sw, document.createTextNode(label));
      div.append(s);
    });
    return div;
  }

  function wrap(svg, legendItems, sourceData) {
    const d = document.createElement('div');
    d.className = 'ml-figure';
    d.append(svg);
    ScientificExport.register(svg,()=>({source:'/api/ml/report',sourceData}));
    if (legendItems) d.append(legend(legendItems));
    return d;
  }

  /** Horizontal bars. items: {label, value, error?, color?, points?} */
  function barChart(items, opts = {}) {
    const rowH = opts.rowHeight || 26;
    const labelW = opts.labelWidth || 150;
    const h = Math.max(120, items.length * rowH + 62);
    const vals = items.flatMap(i => [i.value - (i.error || 0), i.value + (i.error || 0), ...(i.points || [])]);
    let lo = Math.min(0, ...vals), hi = Math.max(0, ...vals, opts.reference ?? -Infinity);
    if (opts.min != null) lo = opts.min;
    const pad = (hi - lo) * 0.08 || 1;
    const f = frame({width: opts.width || 620, height: h, x: [lo, hi + pad], y: [0, items.length],
      yTicks: false, margin: {l: labelW, t: 12, b: 44}, xLabel: opts.xLabel, aria: opts.aria});
    const band = (f.h - f.m.b - f.m.t) / items.length;
    items.forEach((it, i) => {
      const y = f.m.t + i * band + band * 0.18, bh = band * 0.64;
      const x0 = f.sx(Math.min(0, it.value)), x1 = f.sx(Math.max(0, it.value));
      f.svg.append(tooltip(node('rect', {x: x0, y, width: Math.max(1, x1 - x0), height: bh, fill: it.color || COLORS[0], rx: 3}),
        `${it.label}: ${fmt(it.value, 4)}${it.error ? ' ± ' + fmt(it.error, 4) : ''}`));
      if (it.error) {
        const cy = y + bh / 2;
        f.svg.append(node('line', {x1: f.sx(it.value - it.error), x2: f.sx(it.value + it.error), y1: cy, y2: cy, class: 'err'}));
        for (const v of [it.value - it.error, it.value + it.error])
          f.svg.append(node('line', {x1: f.sx(v), x2: f.sx(v), y1: cy - 5, y2: cy + 5, class: 'err'}));
      }
      (it.points || []).forEach(p => f.svg.append(tooltip(node('circle', {cx: f.sx(p), cy: y + bh / 2, r: 3.2, class: 'fold'}), `Pliegue: ${fmt(p, 4)}`)));
      f.svg.append(node('text', {x: labelW - 8, y: y + bh / 2 + 4, 'text-anchor': 'end', class: 'cat'}, it.label));
      if (opts.showValues !== false)
        f.svg.append(node('text', {x: f.sx(it.value + (it.error || 0)) + 6, y: y + bh / 2 + 4, class: 'val'}, fmt(it.value, opts.digits ?? 2)));
    });
    if (opts.reference != null) {
      f.svg.append(node('line', {x1: f.sx(opts.reference), x2: f.sx(opts.reference), y1: f.m.t, y2: f.h - f.m.b, class: 'ref'}));
    }
    return wrap(f.svg, opts.legend, {items, opts});
  }

  /** Vertical histogram from {bins, counts}. */
  function histogram(data, opts = {}) {
    const bins = data.bins || [], counts = data.counts || [];
    const total = counts.reduce((a, b) => a + b, 0) || 1;
    const share = counts.map(c => c / total);
    const f = frame({width: opts.width || 560, height: opts.height || 260, x: [bins[0], bins.at(-1)],
      y: [0, Math.max(...share) * 1.1], xLabel: opts.xLabel, yLabel: 'Proporción ponderada',
      yFormat: v => fmt(v * 100, 0) + '%', xFormat: opts.xFormat, aria: opts.aria});
    share.forEach((s, i) => {
      const x = f.sx(bins[i]), x2 = f.sx(bins[i + 1]);
      f.svg.append(tooltip(node('rect', {x: x + 0.5, y: f.sy(s), width: Math.max(0.5, x2 - x - 1), height: f.sy(0) - f.sy(s),
        fill: opts.color || COLORS[0], opacity: 0.85}),
        `${fmt((opts.xFormat ? null : bins[i]) ?? bins[i])}–${fmt(bins[i + 1])}: ${fmt(s * 100, 1)}%`));
    });
    (opts.markers || []).forEach(([v, cls, label], k) => {
      if (v < bins[0] || v > bins.at(-1)) return;
      f.svg.append(node('line', {x1: f.sx(v), x2: f.sx(v), y1: f.m.t, y2: f.h - f.m.b, class: cls}));
      f.svg.append(node('text', {x: f.sx(v) + 4, y: f.m.t + 10 + k * 13, class: 'val'}, label));
    });
    return wrap(f.svg, opts.legend, {data, opts});
  }

  /** Median + IQR per category. items: {label, median, q1, q3, n} */
  function rangeChart(items, opts = {}) {
    const vals = items.flatMap(i => [i.q1, i.q3, i.median]);
    const lo = Math.min(opts.zero ? 0 : Infinity, ...vals), hi = Math.max(...vals);
    const pad = (hi - lo) * 0.08 || 1;
    const f = frame({width: opts.width || 560, height: opts.height || 260, x: [0, items.length], xTicks: false,
      y: [lo - (opts.zero ? 0 : pad), hi + pad], yLabel: opts.yLabel, xLabel: opts.xLabel, aria: opts.aria});
    const band = (f.w - f.m.l - f.m.r) / items.length;
    items.forEach((it, i) => {
      const cx = f.m.l + band * (i + 0.5), bw = Math.min(46, band * 0.5);
      f.svg.append(tooltip(node('rect', {x: cx - bw / 2, y: f.sy(it.q3), width: bw, height: Math.max(1, f.sy(it.q1) - f.sy(it.q3)),
        fill: opts.color || COLORS[0], opacity: 0.3, stroke: opts.color || COLORS[0]}),
        `${it.label}: mediana ${fmt(it.median)}, RIC [${fmt(it.q1)}, ${fmt(it.q3)}], n=${it.n}`));
      f.svg.append(node('line', {x1: cx - bw / 2, x2: cx + bw / 2, y1: f.sy(it.median), y2: f.sy(it.median), stroke: opts.color || COLORS[0], 'stroke-width': 3}));
      f.svg.append(node('text', {x: cx, y: f.h - f.m.b + 15, 'text-anchor': 'middle', class: 'cat'}, it.label));
      if (it.n != null) f.svg.append(node('text', {x: cx, y: f.h - f.m.b + 28, 'text-anchor': 'middle', class: 'sub'}, `n=${it.n}`));
    });
    if (opts.reference != null)
      f.svg.append(node('line', {x1: f.m.l, x2: f.w - f.m.r, y1: f.sy(opts.reference), y2: f.sy(opts.reference), class: 'ref'}));
    return wrap(f.svg, opts.legend, {items, opts});
  }

  /** Lines. series: [{label, x:[], y:[], color?, dashed?}] */
  function lineChart(series, opts = {}) {
    series = series.map(s => {
      const keep = s.x.map((v, j) => Number.isFinite(v) && Number.isFinite(s.y[j]));
      return Object.assign({}, s, {x: s.x.filter((_, j) => keep[j]), y: s.y.filter((_, j) => keep[j])});
    });
    const xs = series.flatMap(s => s.x), ys = series.flatMap(s => s.y);
    const x = opts.xDomain || [Math.min(...xs), Math.max(...xs)];
    const yr = opts.yDomain || [Math.min(...ys), Math.max(...ys)];
    const pad = opts.yDomain ? 0 : (yr[1] - yr[0]) * 0.1 || 1;
    const f = frame({width: opts.width || 480, height: opts.height || 300, x, y: [yr[0] - pad, yr[1] + pad],
      xLabel: opts.xLabel, yLabel: opts.yLabel, xFormat: opts.xFormat, yFormat: opts.yFormat, aria: opts.aria});
    series.forEach((s, i) => {
      const color = s.color || COLORS[i % COLORS.length];
      const pts = s.x.map((v, j) => `${f.sx(v)},${f.sy(s.y[j])}`).join(' ');
      f.svg.append(node('polyline', {points: pts, fill: 'none', stroke: color, 'stroke-width': s.width || 2.2,
        'stroke-dasharray': s.dashed ? '5 4' : null}));
      if (s.markers) s.x.forEach((v, j) => f.svg.append(tooltip(node('circle', {cx: f.sx(v), cy: f.sy(s.y[j]), r: 3.5, fill: color}),
        `${s.label}: (${fmt(v, 3)}, ${fmt(s.y[j], 3)})`)));
    });
    return wrap(f.svg, series.filter(s => s.label).map((s, i) => ({label: s.label, color: s.color || COLORS[i % COLORS.length], dashed: s.dashed})), {series, opts});
  }

  /** Scatter observed vs predicted with identity line. */
  function scatter(points, opts = {}) {
    const all = points.flatMap(p => [p.x, p.y]);
    const cap = opts.cap || Math.max(...all);
    const f = frame({width: opts.width || 480, height: opts.height || 320, x: [0, cap], y: [0, cap],
      xLabel: opts.xLabel, yLabel: opts.yLabel, aria: opts.aria});
    f.svg.append(node('line', {x1: f.sx(0), y1: f.sy(0), x2: f.sx(cap), y2: f.sy(cap), class: 'ref'}));
    points.forEach(p => {
      if (p.x > cap || p.y > cap) return;
      f.svg.append(node('circle', {cx: f.sx(p.x), cy: f.sy(p.y), r: 2.6, fill: COLORS[0], opacity: 0.45}));
    });
    return wrap(f.svg, [{label: 'Predicción perfecta (y = x)', color: '#8a97a0', dashed: true}], {points, opts});
  }

  /** Forest plot. rows: {label, point, lo, hi} */
  function forestPlot(rows, opts = {}) {
    const vals = rows.flatMap(r => [r.lo, r.hi, r.point]).concat(opts.reference ?? []);
    const lo = Math.min(...vals), hi = Math.max(...vals), pad = (hi - lo) * 0.12 || 1;
    const h = Math.max(120, rows.length * 34 + 60);
    const f = frame({width: opts.width || 620, height: h, x: [lo - pad, hi + pad], y: [0, rows.length], yTicks: false,
      margin: {l: opts.labelWidth || 170, b: 44}, xLabel: opts.xLabel, aria: opts.aria});
    const band = (f.h - f.m.b - f.m.t) / rows.length;
    if (opts.reference != null)
      f.svg.append(node('line', {x1: f.sx(opts.reference), x2: f.sx(opts.reference), y1: f.m.t, y2: f.h - f.m.b, class: 'ref'}));
    rows.forEach((r, i) => {
      const cy = f.m.t + band * (i + 0.5);
      const color = r.color || COLORS[0];
      f.svg.append(node('line', {x1: f.sx(r.lo), x2: f.sx(r.hi), y1: cy, y2: cy, stroke: color, 'stroke-width': 2.5}));
      for (const v of [r.lo, r.hi]) f.svg.append(node('line', {x1: f.sx(v), x2: f.sx(v), y1: cy - 6, y2: cy + 6, stroke: color, 'stroke-width': 2}));
      f.svg.append(tooltip(node('rect', {x: f.sx(r.point) - 5, y: cy - 5, width: 10, height: 10, fill: color}),
        `${r.label}: ${fmt(r.point, 4)} [${fmt(r.lo, 4)}, ${fmt(r.hi, 4)}]`));
      f.svg.append(node('text', {x: f.m.l - 8, y: cy + 4, 'text-anchor': 'end', class: 'cat'}, r.label));
      f.svg.append(node('text', {x: f.sx(r.point), y: cy - 9, 'text-anchor': 'middle', class: 'val'}, `${fmt(r.point, opts.digits ?? 3)} [${fmt(r.lo, opts.digits ?? 3)}; ${fmt(r.hi, opts.digits ?? 3)}]`));
    });
    return wrap(f.svg, opts.legend, {rows, opts});
  }

  /** Correlation heatmap with diverging colours. */
  function heatmap(matrix, labels, opts = {}) {
    const cell = opts.cell || 34, left = 118, top = 12, bottom = 96;
    const w = left + labels.length * cell + 90, h = top + labels.length * cell + bottom;
    const svg = node('svg', {viewBox: `0 0 ${w} ${h}`, class: 'ml-chart', role: 'img', 'aria-label': opts.aria || ''});
    const color = v => {
      if (v == null) return '#f1f3f5';
      const t = Math.max(-1, Math.min(1, v));
      const a = Math.abs(t);
      return t >= 0 ? `rgb(${Math.round(255 - a * 200)},${Math.round(255 - a * 130)},${Math.round(255 - a * 30)})`
                    : `rgb(${Math.round(255 - a * 20)},${Math.round(255 - a * 160)},${Math.round(255 - a * 170)})`;
    };
    labels.forEach((row, i) => {
      svg.append(node('text', {x: left - 6, y: top + i * cell + cell / 2 + 4, 'text-anchor': 'end', class: 'cat'}, opts.names?.[row] || row));
      labels.forEach((col, j) => {
        const v = matrix[row]?.[col];
        svg.append(tooltip(node('rect', {x: left + j * cell, y: top + i * cell, width: cell - 2, height: cell - 2, fill: color(v), rx: 2}),
          `${opts.names?.[row] || row} × ${opts.names?.[col] || col}: ρ = ${fmt(v, 3)}`));
        if (v != null && Math.abs(v) >= 0.1)
          svg.append(node('text', {x: left + j * cell + cell / 2 - 1, y: top + i * cell + cell / 2 + 3, 'text-anchor': 'middle', class: 'cell'}, fmt(v, 2)));
      });
      svg.append(node('text', {x: left + i * cell + cell / 2, y: top + labels.length * cell + 8,
        transform: `rotate(55 ${left + i * cell + cell / 2} ${top + labels.length * cell + 8})`, class: 'cat'}, opts.names?.[row] || row));
    });
    const lx = left + labels.length * cell + 24;
    for (let k = 0; k <= 20; k++) {
      const v = 1 - k / 10;
      svg.append(node('rect', {x: lx, y: top + k * 10, width: 14, height: 10, fill: color(v)}));
    }
    svg.append(node('text', {x: lx + 20, y: top + 8, class: 'sub'}, '+1'));
    svg.append(node('text', {x: lx + 20, y: top + 104, class: 'sub'}, '0'));
    svg.append(node('text', {x: lx + 20, y: top + 210, class: 'sub'}, '−1'));
    return wrap(svg, null, {matrix, labels, opts});
  }

  /** SHAP beeswarm: one row per feature, x = SHAP, colour = feature value (blue low, red high). */
  function beeswarm(points, features, opts = {}) {
    const rowH = 30, labelW = 130;
    const vals = points.map(p => p.shap);
    const lim = Math.max(...vals.map(Math.abs), 1e-9);
    const f = frame({width: opts.width || 640, height: features.length * rowH + 64, x: [-lim * 1.05, lim * 1.05],
      y: [0, features.length], yTicks: false, margin: {l: labelW, b: 46}, xLabel: opts.xLabel, aria: opts.aria});
    f.svg.append(node('line', {x1: f.sx(0), x2: f.sx(0), y1: f.m.t, y2: f.h - f.m.b, class: 'ref'}));
    const band = (f.h - f.m.b - f.m.t) / features.length;
    features.forEach((feat, i) => {
      const cy = f.m.t + band * (i + 0.5);
      f.svg.append(node('text', {x: labelW - 8, y: cy + 4, 'text-anchor': 'end', class: 'cat'}, opts.names?.[feat] || feat));
      const pts = points.filter(p => p.feature === feat);
      const bins = new Map();
      pts.forEach(p => {
        const key = Math.round(f.sx(p.shap) / 4);
        const k = bins.get(key) || 0; bins.set(key, k + 1);
        const offset = (k % 2 ? 1 : -1) * Math.ceil(k / 2) * 2.4;
        if (Math.abs(offset) > band * 0.45) return;
        const t = p.scaled;
        const fill = t == null ? '#b8c2c9' : `rgb(${Math.round(40 + 200 * t)},${Math.round(90 + 20 * (1 - Math.abs(t - 0.5) * 2))},${Math.round(230 - 190 * t)})`;
        f.svg.append(node('circle', {cx: f.sx(p.shap), cy: cy + offset, r: 2.3, fill, opacity: 0.8}));
      });
    });
    const d = wrap(f.svg, null, {points, features, opts});
    const key = document.createElement('div');
    key.className = 'ml-legend';
    key.textContent = 'Color del punto: azul = valor bajo de la variable · rojo = valor alto · gris = dato ausente';
    d.append(key);
    return d;
  }

  /** Diverging contributions (local SHAP). */
  function contributions(contrib, opts = {}) {
    const items = Object.entries(contrib).sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
      .map(([k, v]) => ({label: opts.names?.[k] || k, value: v, color: v >= 0 ? '#d64550' : '#1f77b4'}));
    return barChart(items, {xLabel: opts.xLabel, digits: 3, legend: [{label: 'Aumenta la predicción', color: '#d64550'},
      {label: 'Disminuye la predicción', color: '#1f77b4'}]});
  }

  function table(rows, columns, opts = {}) {
    const wrapEl = document.createElement('div');
    wrapEl.className = 'table-wrap ml-table';
    const t = document.createElement('table');
    const thead = t.createTHead().insertRow();
    columns.forEach(([, label]) => { const th = document.createElement('th'); th.textContent = label; thead.append(th); });
    const body = t.createTBody();
    rows.forEach(r => {
      const tr = body.insertRow();
      if (opts.highlight && opts.highlight(r)) tr.className = 'highlight';
      columns.forEach(([key]) => { tr.insertCell().textContent = r[key] ?? '—'; });
    });
    wrapEl.append(t);
    ScientificExport.register(t, () => ({headers: columns.map(([, label]) => label),
      rows: rows.map(r => columns.map(([key]) => r[key]?.raw ?? r[key] ?? null)),
      notes: [...(t.closest('.ml-panel')?.querySelectorAll('.ml-chart-meta, .ml-interpret') || [])].map(n => n.textContent),
      source: '/api/ml/report · resultados_ml/informe.json',
      precision: 'Los números formateados conservan su valor original. Los intervalos compuestos mantienen su representación textual; consulta el informe JSON para sus extremos originales.'}));
    return wrapEl;
  }

  function panel(title, content, comoLeerOrMeta, interpretacion) {
    const meta = (comoLeerOrMeta && typeof comoLeerOrMeta === 'object' && !Array.isArray(comoLeerOrMeta))
      ? comoLeerOrMeta
      : {comoLeer: comoLeerOrMeta, interpretacion};
    const sec = document.createElement('section');
    sec.className = 'ml-panel';
    const h = document.createElement('h3');
    h.textContent = title;
    sec.append(h);
    if (meta.prueba || meta.base) {
      const facts = document.createElement('dl');
      facts.className = 'ml-chart-meta';
      if (meta.prueba) {
        const dt = document.createElement('dt');
        dt.textContent = 'Prueba / método';
        const dd = document.createElement('dd');
        dd.textContent = meta.prueba;
        facts.append(dt, dd);
      }
      if (meta.base) {
        const dt = document.createElement('dt');
        dt.textContent = 'Base del gráfico';
        const dd = document.createElement('dd');
        dd.textContent = meta.base;
        facts.append(dt, dd);
      }
      sec.append(facts);
    }
    [].concat(content).filter(Boolean).forEach(c => sec.append(c));
    const box = document.createElement('div');
    box.className = 'ml-interpret';
    for (const [label, text, cls] of [['Cómo leerlo', meta.comoLeer, 'read'], ['Interpretación', meta.interpretacion, 'interp']]) {
      if (!text) continue;
      const p = document.createElement('p');
      p.className = cls;
      const s = document.createElement('strong');
      s.textContent = label + ': ';
      p.append(s, document.createTextNode(text));
      box.append(p);
    }
    if (box.childElementCount) sec.append(box);
    return sec;
  }

  window.MLCharts = {barChart, histogram, rangeChart, lineChart, scatter, forestPlot, heatmap, beeswarm,
    contributions, table, panel, fmt, value, COLORS};
})();
