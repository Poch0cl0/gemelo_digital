/* Local, dependency-free publication exports. Data providers retain unrounded values. */
(() => {
  'use strict';
  const NS = 'http://www.w3.org/2000/svg';
  /** @typedef {{title?: string, headers?: string[], rows?: Array<Array<string|number|boolean|null>>, notes?: string[], source?: string, scenario?: string}} ExportData */
  /** @type {WeakMap<Element, () => ExportData>} */
  const providers = new WeakMap();
  const views = new WeakMap();
  const el = (tag, text) => Object.assign(document.createElement(tag), {textContent: text});
  const svgNode = (tag, attrs = {}, text) => {
    const n = document.createElementNS(NS, tag);
    Object.entries(attrs).forEach(([k, v]) => n.setAttribute(k, v));
    if (text != null) n.textContent = text;
    return n;
  };
  function csv(headers, rows) {
    const quote = v => {
      let s = v == null ? '' : String(v);
      // Prevent spreadsheet formulas in untrusted text, preserving numeric negatives.
      if (typeof v === 'string' && /^[\s]*[=+@-]/.test(s)) s = "'" + s;
      return '"' + s.replaceAll('"', '""') + '"';
    };
    return '\ufeff' + [headers, ...rows].map(r => r.map(quote).join(',')).join('\r\n');
  }
  function download(blob, name) {
    const url = URL.createObjectURL(blob), a = el('a', '');
    a.href = url; a.download = name; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 30000);
  }
  function context(target) {
    const panel = target.closest('.ml-panel, .panel, .data-panel, section') || target.parentElement;
    const heading = [...document.querySelectorAll('#ml-content h2')].filter(h => h.compareDocumentPosition(target) & Node.DOCUMENT_POSITION_FOLLOWING).at(-1);
    return {
      title: panel.querySelector('h3,h2')?.textContent || target.getAttribute('aria-label') || 'Resultados',
      scenario: [heading?.textContent, document.querySelector('#ml-trained')?.textContent].filter(Boolean).join(' · '),
      notes: [...panel.querySelectorAll('p, .ml-chart-meta, .ml-interpret, .ml-legend, .legend')]
        .filter(n => !n.closest('.export-tools') && !n.parentElement.closest('.ml-interpret'))
        .map(n => n.matches('.legend,.ml-legend') && n.children.length ? [...n.children].map(c => c.textContent.trim()).join(' · ') : n.textContent.trim()).filter(Boolean),
      source: location.pathname + location.hash,
    };
  }
  function data(target) {
    const supplied = providers.get(target)?.() || {};
    const meta = {...context(target), ...supplied};
    if (target.tagName === 'TABLE' && !meta.rows) {
      const heads = [...target.querySelectorAll('thead th')];
      const indices = heads.map((h, i) => /acciones/i.test(h.textContent) ? -1 : i).filter(i => i >= 0);
      meta.headers = indices.map(i => heads[i].textContent.trim());
      meta.rows = [...target.querySelectorAll('tbody tr')].filter(r => r.cells.length === heads.length)
        .map(r => indices.map(i => r.cells[i].dataset.value ?? r.cells[i].textContent.trim()));
      meta.notes.push('Valores según la precisión presentada en pantalla.');
    }
    const view = views.get(target);
    if (view && meta.rows) {
      meta.rows = meta.rows.filter(row => !view.query || row.some(v => String(v ?? '').toLocaleLowerCase('es').includes(view.query)));
      if (view.column >= 0) meta.rows = [...meta.rows].sort((a, b) => {
        const x = a[view.column], y = b[view.column];
        return view.direction * (typeof x === 'number' && typeof y === 'number' ? x - y : String(x ?? '').localeCompare(String(y ?? ''), 'es', {numeric:true}));
      });
      meta.notes = [...(meta.notes || []), `Filtro de tabla: ${view.query || 'todos'} · Orden: ${view.column < 0 ? 'original' : meta.headers[view.column] + (view.direction > 0 ? ' ascendente' : ' descendente')}`];
    }
    return meta;
  }
  function lines(text, size = 100) {
    const result = [];
    for (const paragraph of String(text).split('\n')) {
      let line = '';
      for (const word of paragraph.split(/\s+/)) {
        // Also wrap long hashes/identifiers without dropping characters.
        for (let i = 0; i < word.length; i += size) {
          const chunk = word.slice(i, i + size);
          if ((line + ' ' + chunk).length > size) { result.push(line); line = ''; }
          line += (line ? ' ' : '') + chunk;
        }
      }
      if (line) result.push(line);
    }
    return result;
  }
  function figure(target, meta, rows) {
    let content, width, height;
    if (target.tagName === 'TABLE') {
      const matrix = [meta.headers, ...rows];
      const widths = meta.headers.map((_, c) => Math.max(100, Math.min(150,
        Math.max(...matrix.map(r => String(r[c] ?? '—').length)) * 7 + 24)));
      width = widths.reduce((a, b) => a + b, 0) + 32;
      content = svgNode('g'); height = 0;
      matrix.forEach((row, index) => {
        const cells = row.map((v, c) => lines(v == null ? '—' : String(v), Math.floor((widths[c] - 20) / 7)));
        const h = Math.max(1, ...cells.map(c => c.length)) * 18 + 16;
        content.append(svgNode('rect', {x: 16, y: height, width: width - 32, height: h,
          fill: index === 0 ? '#e9eef2' : index % 2 ? '#ffffff' : '#f5f7f8'}));
        let x = 26;
        cells.forEach((cell, c) => {
          cell.forEach((line, j) => content.append(svgNode('text', {x, y: height + 22 + j * 18,
            'font-weight': index === 0 ? 'bold' : 'normal'}, line)));
          x += widths[c];
        });
        height += h;
      });
    } else {
      const box = target.viewBox.baseVal;
      const bbox = target.getBBox();
      const left = Math.min(0, box.x, bbox.x - 8), top = Math.min(0, box.y, bbox.y - 8);
      width = Math.max(box.width, bbox.x + bbox.width + 8) - left;
      height = Math.max(box.height, bbox.y + bbox.height + 8) - top;
      content = svgNode('g', {transform: `translate(${-left},${-top})`});
      const clone = target.cloneNode(true);
      const originals = [target, ...target.querySelectorAll('*')];
      [clone, ...clone.querySelectorAll('*')].forEach((n, i) => {
        const style = getComputedStyle(originals[i]);
        for (const prop of ['fill','stroke','stroke-width','stroke-dasharray','opacity','fill-opacity','font-size','font-family','font-weight','text-anchor']) {
          n.setAttribute(prop, style.getPropertyValue(prop));
        }
        n.removeAttribute('class'); n.removeAttribute('style'); n.removeAttribute('id');
      });
      content.append(...clone.childNodes);
    }
    width = Math.max(width, 600);
    const maxChars = Math.floor((width - 40) / 7.5);
    const heading = lines(meta.title, maxChars);
    const legend = [...(target.closest('.ml-figure')?.querySelectorAll('.ml-legend > span') || [])].flatMap(span => {
      const sample = span.querySelector('line');
      if (!sample) return [];
      return lines(span.textContent.trim(), maxChars - 8).map(text => ({text,
        color: sample.getAttribute('stroke'), dash: sample.getAttribute('stroke-dasharray') || 'none'}));
    });
    const notes = [meta.scenario, ...(meta.notes || []), `Origen: ${meta.source} · Exportado: ${new Date().toISOString()}`]
      .filter(Boolean).flatMap(s => lines(s, maxChars));
    const offset = 24 + heading.length * 22;
    const root = svgNode('svg', {xmlns: NS, viewBox: `0 0 ${width} ${height + offset + (notes.length + legend.length) * 18 + 32}`,
      width, height: height + offset + (notes.length + legend.length) * 18 + 32, 'font-family': 'Arial, sans-serif', 'font-size': 13, fill: '#162530'});
    root.append(svgNode('rect', {width: '100%', height: '100%', fill: 'white'}));
    heading.forEach((s, i) => root.append(svgNode('text', {x: 20, y: 24 + i * 22, 'font-size': 18, 'font-weight': 'bold'}, s)));
    const translated = svgNode('g', {transform: `translate(0,${offset})`}); translated.append(content); root.append(translated);
    legend.forEach((item, i) => {
      const y = offset + height + 18 + i * 18;
      root.append(svgNode('line', {x1:20,x2:48,y1:y-4,y2:y-4,stroke:item.color,'stroke-width':3,'stroke-dasharray':item.dash}));
      root.append(svgNode('text', {x:56,y}, item.text));
    });
    notes.forEach((s, i) => root.append(svgNode('text', {x: 20, y: offset + height + 22 + (i + legend.length) * 18}, s)));
    root.append(svgNode('metadata', {}, JSON.stringify({...meta, rows: rows || meta.rows})));
    return root;
  }
  // PNG pHYs explicitly records 300 DPI in addition to sufficient pixel dimensions.
  function crc32(bytes) {
    let c = 0xffffffff;
    for (const byte of bytes) { c ^= byte; for (let k = 0; k < 8; k++) c = (c >>> 1) ^ ((c & 1) ? 0xedb88320 : 0); }
    return (c ^ 0xffffffff) >>> 0;
  }
  async function png(svg, mm) {
    const serialized = new XMLSerializer().serializeToString(svg);
    const url = URL.createObjectURL(new Blob([serialized], {type: 'image/svg+xml'}));
    try {
      const img = new Image(); img.src = url; await img.decode();
      const vb = svg.viewBox.baseVal;
      const scale = Math.max(300 * mm / 25.4 / vb.width, 300 / 96);
      const canvas = document.createElement('canvas');
      canvas.width = Math.ceil(vb.width * scale); canvas.height = Math.ceil(vb.height * scale);
      if (canvas.width > 16000 || canvas.height > 16000 || canvas.width * canvas.height > 64000000)
        throw new Error('La figura supera el tamaño seguro de PNG. Usa SVG o PDF.');
      canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height);
      const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
      if (!blob) throw new Error('El navegador no pudo generar el PNG.');
      const bytes = new Uint8Array(await blob.arrayBuffer());
      const chunk = new Uint8Array(21), view = new DataView(chunk.buffer);
      view.setUint32(0, 9); chunk.set([112,72,89,115], 4);
      view.setUint32(8, 11811); view.setUint32(12, 11811); chunk[16] = 1;
      view.setUint32(17, crc32(chunk.slice(4, 17)));
      const chunks = [bytes.slice(0, 33), chunk];
      for (let offset = 33; offset < bytes.length;) {
        const length = new DataView(bytes.buffer, bytes.byteOffset + offset, 4).getUint32(0);
        if (String.fromCharCode(...bytes.slice(offset + 4, offset + 8)) !== 'pHYs') chunks.push(bytes.slice(offset, offset + length + 12));
        offset += length + 12;
      }
      return new Blob(chunks, {type: 'image/png'});
    } finally { URL.revokeObjectURL(url); }
  }
  async function exportTarget(target, format, mm = 180) {
    const meta = data(target);
    const name = meta.title.normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9]+/gi, '-').slice(0, 70);
    if (format === 'csv') return download(new Blob([csv([...meta.headers, 'Escenario', 'Origen', 'Notas'],
      meta.rows.map(row => [...row, meta.scenario || meta.title, meta.source, (meta.notes || []).join(' | ')]))], {type: 'text/csv;charset=utf-8'}), name + '.csv');
    if (format === 'json') return download(new Blob([JSON.stringify(meta, null, 2)], {type: 'application/json'}), name + '.json');
    const pages = [];
    if (target.tagName === 'TABLE') {
      let page = [], height = 0;
      for (const row of meta.rows) {
        const rowHeight = Math.max(1, ...row.map(v => lines(v ?? '—', 11).length)) * 18 + 16;
        if (page.length && (page.length >= 25 || height + rowHeight > 650)) {pages.push(page); page = []; height = 0;}
        page.push(row); height += rowHeight;
      }
      if (page.length || !pages.length) pages.push(page);
    } else pages.push(undefined);
    if (format === 'pdf') {
      // A same-origin page avoids inline scripts/styles and respects the server CSP.
      const win = window.open('/export-preview', '_blank');
      if (!win) throw new Error('Permite abrir la vista PDF en una pestaña nueva.');
      const onMessage = event => {
        if (event.origin !== location.origin || event.source !== win || event.data !== 'export-ready') return;
        window.removeEventListener('message', onMessage);
        win.postMessage({type: 'export-figures', mm, figures: pages.map((r, i) => new XMLSerializer().serializeToString(figure(target, {...meta, title: `${meta.title} (${i + 1}/${pages.length})`}, r)))}, location.origin);
      };
      window.addEventListener('message', onMessage);
      setTimeout(() => window.removeEventListener('message', onMessage), 60000);
      return;
    }
    for (const [i, rows] of pages.entries()) {
      const svg = figure(target, {...meta, title: pages.length > 1 ? `${meta.title} (${i + 1}/${pages.length})` : meta.title}, rows);
      const blob = format === 'png' ? await png(svg, mm) : new Blob([new XMLSerializer().serializeToString(svg)], {type: 'image/svg+xml'});
      download(blob, `${name}${pages.length > 1 ? '-'+(i + 1) : ''}.${format}`);
    }
  }
  function attach(target) {
    if (target.dataset.exportAttached) return;
    target.dataset.exportAttached = 'true';
    const bar = el('div', ''); bar.className = 'export-tools';
    const label = el('label', 'Formato científico · ancho mínimo '), size = el('select', '');
    for (const mm of [180, 90]) { const option = el('option', `${mm} mm`); option.value = mm; size.append(option); }
    label.append(size); bar.append(label);
    if (target.tagName === 'TABLE' && !target.querySelector('#record-body')) {
      const view = {query: '', column: -1, direction: 1}; views.set(target, view);
      const search = el('input', ''); search.type = 'search'; search.placeholder = 'Filtrar tabla'; search.setAttribute('aria-label', 'Filtrar tabla');
      const sort = el('select', ''); sort.setAttribute('aria-label', 'Ordenar tabla');
      const original = el('option', 'Orden original'); original.value = '-1'; sort.append(original);
      [...target.querySelectorAll('thead th')].forEach((th, i) => {
        for (const direction of [1, -1]) {const opt = el('option', th.textContent + (direction > 0 ? ' ↑' : ' ↓')); opt.value = `${i}:${direction}`; sort.append(opt);}
      });
      // Snapshot fallback tables before replacing their DOM; registered providers remain authoritative.
      if (!providers.has(target)) { const snapshot = data(target); providers.set(target, () => snapshot); }
      const update = () => {
        view.query = search.value.trim().toLocaleLowerCase('es');
        [view.column, view.direction = 1] = sort.value.split(':').map(Number);
        const meta = data(target), body = target.tBodies[0] || target.createTBody(); body.replaceChildren();
        for (const row of meta.rows) {const tr = body.insertRow(); row.forEach(v => tr.insertCell().textContent = v == null ? '—' : String(v));}
      };
      search.addEventListener('input', update); sort.addEventListener('change', update);
      target.refreshExportView = () => { if (view.query || view.column >= 0) update(); };
      bar.append(search, sort);
    }
    const status = el('span', ''); status.setAttribute('role', 'status');
    for (const format of target.tagName === 'TABLE' ? ['csv','png','pdf','json'] : ['svg','png','pdf','json']) {
      const button = el('button', format === 'pdf' ? 'PDF / imprimir' : format.toUpperCase());
      button.type = 'button'; button.className = 'secondary'; button.setAttribute('aria-label', `Descargar ${format.toUpperCase()}`);
      button.addEventListener('click', async () => {
        button.disabled = true; status.textContent = 'Preparando…';
        try { await exportTarget(target, format, Number(size.value)); status.textContent = 'Exportación preparada.'; }
        catch (error) { status.textContent = error.message; }
        finally { button.disabled = false; }
      });
      bar.append(button);
    }
    bar.append(status); target.before(bar);
  }
  function scan() {
    document.querySelectorAll('table, #chart > svg, svg.ml-chart').forEach(attach);
  }
  window.ScientificExport = {register: (target, provider) => providers.set(target, provider), csv, figure, png, data, exportTarget};
  scan();
  let scheduled = false;
  new MutationObserver(records => {
    if (scheduled || !records.some(r => [...r.addedNodes].some(n => n.nodeType === 1 && (n.matches('table,svg') || n.querySelector('table,svg'))))) return;
    scheduled = true; requestAnimationFrame(() => { scheduled = false; scan(); });
  }).observe(document.body, {childList: true, subtree: true});
})();
