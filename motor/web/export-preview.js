'use strict';
document.getElementById('print').addEventListener('click', () => window.print());
window.addEventListener('message', event => {
  if (event.origin !== location.origin || event.source !== window.opener || event.data?.type !== 'export-figures') return;
  const root = document.getElementById('figures'); root.replaceChildren();
  root.className = event.data.mm === 90 ? 'single-column' : 'double-column';
  for (const serialized of event.data.figures) {
    const svg = new DOMParser().parseFromString(serialized, 'image/svg+xml').documentElement;
    root.append(document.importNode(svg, true));
  }
});
window.opener?.postMessage('export-ready', location.origin);
