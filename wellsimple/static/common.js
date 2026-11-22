// Shared helpers. Everything user- or data-derived is inserted with textContent
// (never innerHTML), because crew notes are free text.
function el(tag, props, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (k === 'class') e.className = v;
    else if (k === 'text') e.textContent = v;
    else if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
    else if (v !== undefined && v !== null) e.setAttribute(k, v);
  }
  for (const kid of kids.flat()) if (kid != null) e.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  return e;
}
const money = (v) => v == null ? '–' : '$' + Math.round(v).toLocaleString('en-CA');
const moneyM = (v) => v == null ? '–' : '$' + (v / 1e6).toFixed(1) + 'M';  // rounded: inputs are field estimates
const pct = (v) => v == null ? '–' : Math.round(v * 100) + '%';
const num = (v, d = 0) => v == null ? '–' : Number(v).toLocaleString('en-CA', { maximumFractionDigits: d });
async function api(path, opts) {
  const r = await fetch(path, opts && opts.body ? { ...opts, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(opts.body) } : opts);
  if (!r.ok) {
    let msg = r.statusText;
    try { const j = await r.json(); msg = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail); } catch (_) {}
    throw new Error(msg);
  }
  return r.json();
}
function riskPill(p) {
  const c = p >= 0.4 ? 'hi' : p >= 0.2 ? 'mid' : 'lo';
  return el('span', { class: 'pill ' + c, text: pct(p) });
}
function osmMap(id, center, zoom) {
  const m = L.map(id).setView(center, zoom);
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    { maxZoom: 18, attribution: '&copy; OpenStreetMap contributors' }).addTo(m);
  return m;
}

// "Likely finding": what wells with similar sensor behavior turned out to have. Shown as an
// estimate with the real past notes it is based on; it is not a diagnosis.
function autopsyBlock(a) {
  if (!a) return el('div', { class: 'muted small', text: 'No sensor-based estimate for this well.' });
  const parts = Object.entries(a.p).sort((x, y) => y[1] - x[1]);
  return el('div', {},
    el('div', { class: 'small', text: 'Likely finding, from sensors alone' }),
    el('div', {}, ...parts.map(([k, v]) => el('span', { class: 'tag', text: k + ' ' + pct(v) }))),
    ...a.notes.map(n => el('div', { class: 'note' }, el('div', { class: 'small muted', text: 'Past note from a well that behaved similarly (' + n.component + ')' }), el('div', { text: n.text }))),
    el('div', { class: 'small muted', text: 'Estimate, not a diagnosis. In a 2026 hold-out test the model ranked pump, rod and tubing failures with AUC 0.69 to 0.76 (0.5 is chance).' }));
}
