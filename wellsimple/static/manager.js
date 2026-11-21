const S = { overview: null, crews: [], wells: [], map: null, markers: null, charts: [], pts: [] };
const scenario = () => document.getElementById('scenario').value;
const lossKey = () => 'expected_loss_' + scenario();

async function loadAll() {
  const [ov, crews] = await Promise.all([api('/api/overview'), api('/api/crews')]);
  S.overview = ov; S.crews = crews;
  document.getElementById('asof').textContent = 'Data as of ' + ov.as_of;
  const origin = document.getElementById('origin');
  origin.replaceChildren(el('option', { value: '', text: 'Fleet centre' }),
    ...crews.map(c => el('option', { value: c.id, text: c.name + (c.lat != null ? ' (located)' : ' (no location yet)') })));
  renderKpis(); renderOverviewCharts(); renderReliability();
}

function renderKpis() {
  const o = S.overview, k = document.getElementById('kpis');
  const loss = o['expected_loss_' + scenario()];
  const card = (v, l, n) => el('div', { class: 'card kpi' }, el('div', { class: 'v', text: v }), el('div', { class: 'l', text: l }), n ? el('div', { class: 'n', text: n }) : null);
  k.replaceChildren(
    card(num(o.producing_wells), 'Producing wells scored', 'as of ' + o.as_of),
    card(num(o.high_risk_wells), 'High-risk wells', '30-day repair chance 40%+'),
    card(money(loss), 'Expected 30-day loss', 'job cost + lost oil, ' + (scenario() === 'low' ? 'conservative' : 'mid') + ' price'),
    card(pct(o.repair_repeat_90d_share), 'Repairs repeating within 90 days', 'share of repair jobs on the same well'),
    card(num(o.open_assignments), 'Open assignments'),
    card(num(o.resolved_count), 'Resolved jobs'));
}

function renderOverviewCharts() {
  S.charts.forEach(c => c.destroy()); S.charts = [];
  const m = S.overview.monthly.filter(r => r.month >= '2021-01');
  S.charts.push(new Chart(document.getElementById('chartMonthly'), {
    data: { labels: m.map(r => r.month), datasets: [
      { type: 'bar', label: 'Lost oil (m³)', data: m.map(r => r.lost_oil_m3), backgroundColor: '#c2410c99', yAxisID: 'y' },
      { type: 'line', label: 'Repair jobs', data: m.map(r => r.repair_jobs), borderColor: '#0b6e4f', pointRadius: 0, yAxisID: 'y2' }] },
    options: { responsive: true, scales: { y: { title: { display: true, text: 'm³' } }, y2: { position: 'right', grid: { drawOnChartArea: false } },
      x: { ticks: { maxTicksLimit: 8 } } } } }));
  const codes = Object.entries(S.overview.lost_by_code);
  S.charts.push(new Chart(document.getElementById('chartCodes'), {
    type: 'bar', data: { labels: codes.map(c => c[0]), datasets: [{ data: codes.map(c => c[1]), backgroundColor: '#0b6e4f99' }] },
    options: { indexAxis: 'y', plugins: { legend: { display: false } } } }));
}

async function loadWells() {
  const q = new URLSearchParams({ sort: document.getElementById('sort').value, min_risk: document.getElementById('minrisk').value, limit: 30 });
  const crew = document.getElementById('origin').value; if (crew) q.set('crew_id', crew);
  const r = await api('/api/wells?' + q);
  S.wells = r.wells;
  const t = document.getElementById('wellsTable');
  const head = el('tr', {}, ...['Well', 'Risk', 'Expected loss', 'Why flagged', 'km', 'Assign'].map(h => el('th', { text: h })));
  const rows = r.wells.map(w => {
    const sel = el('select', { 'aria-label': 'Assign crew', style: 'width:92px;padding:6px' }, ...S.crews.map(c => el('option', { value: c.id, text: c.name })));
    sel.addEventListener('click', e => e.stopPropagation());
    const btn = el('button', { class: 'ghost', text: 'Assign', onclick: async (e) => {
      e.stopPropagation(); btn.disabled = true;
      try { await api('/api/assign', { method: 'POST', body: { uwi: w.uwi, crew_id: sel.value } }); await refresh(); }
      catch (err) { alert('Could not assign: ' + err.message); btn.disabled = false; } } });
    return el('tr', { class: 'clickable', onclick: () => showDetail(w) },
      el('td', {}, el('div', { text: w.well_name || w.uwi }), el('div', { class: 'muted small', text: w.field_operating_area || '' })),
      el('td', {}, riskPill(w.p_repair)),
      el('td', { text: money(w[lossKey()]) }),
      el('td', {}, ...(w.reasons ? w.reasons.split('; ').map(x => el('span', { class: 'tag', text: x })) : [el('span', { class: 'muted small', text: 'general risk' })])),
      el('td', { text: num(w.distance_km) }),
      el('td', { style: 'white-space:nowrap' }, sel, ' ', btn));
  });
  t.replaceChildren(head, ...rows);
  if (!rows.length) t.replaceChildren(el('tr', {}, el('td', { class: 'empty', text: 'No wells match.' })));
  drawMap();
}

function drawMap() {
  if (!S.map) { S.map = osmMap('map', [53.3, -110.3], 7); S.markers = L.layerGroup().addTo(S.map); }
  S.markers.clearLayers();
  const pts = [];
  S.wells.forEach(w => {
    if (w.surface_latitude == null) return;
    const c = w.p_repair >= 0.4 ? '#b91c1c' : w.p_repair >= 0.2 ? '#c2410c' : '#15803d';
    const m = L.circleMarker([w.surface_latitude, w.surface_longitude], { radius: 8, color: c, fillColor: c, fillOpacity: .6 })
      .bindTooltip((w.well_name || w.uwi) + ' · ' + pct(w.p_repair)).on('click', () => showDetail(w));
    m.addTo(S.markers); pts.push([w.surface_latitude, w.surface_longitude]);
  });
  S.pts = pts; fitMap();
}
function fitMap() {
  // the map may have been created while its tab was hidden, so re-measure before fitting
  setTimeout(() => { S.map.invalidateSize(); if (S.pts.length) S.map.fitBounds(S.pts, { padding: [30, 30], maxZoom: 11 }); }, 60);
}

async function showDetail(w) {
  const box = document.getElementById('detail');
  box.replaceChildren(el('div', { class: 'muted', text: 'Loading…' }));
  try {
    const d = await api('/api/wells/' + encodeURIComponent(w.uwi) + '?k=4');
    const s = d.summary;
    box.replaceChildren(
      el('h3', { style: 'margin:0 0 4px', text: w.well_name || w.uwi }),
      el('div', { class: 'small muted', text: 'Risk ' + pct(w.p_repair) + ' · expected loss ' + money(w[lossKey()]) }),
      s && s.median_life_days != null ? el('p', { class: 'small', text: 'Similar past repairs lasted a median of ' + num(s.median_life_days) +
        ' days (middle half: ' + num(s.life_p25) + '–' + num(s.life_p75) + '), at about ' + money(s.cost_per_day_of_life) + ' per day of well life.' }) : null,
      autopsyBlock(d.autopsy),
      el('div', { class: 'small', text: 'Closest past jobs' }),
      ...(d.precedents.length ? d.precedents.map(p => el('div', { class: 'note' },
        el('div', { class: 'small muted', text: (p.date || '') + ' · similarity ' + p.similarity + ' · lasted ' + (p.life_days == null ? 'unknown' : num(p.life_days) + ' days') + ' · cost ' + money(p.cost) }),
        el('div', { text: p.text }))) : [el('div', { class: 'muted small', text: 'No similar notes found.' })]));
  } catch (e) { box.replaceChildren(el('div', { class: 'muted', text: 'Could not load: ' + e.message })); }
}

async function loadAssignments(status, tableId, cols) {
  const rows = await api('/api/assignments?status=' + status);
  const crewName = id => (S.crews.find(c => c.id === id) || {}).name || id;
  const t = document.getElementById(tableId);
  const head = el('tr', {}, ...cols.map(c => el('th', { text: c[0] })));
  const body = rows.map(r => el('tr', {}, ...cols.map(c => el('td', { text: c[1](r, crewName) }))));
  t.replaceChildren(head, ...(body.length ? body : [el('tr', {}, el('td', { class: 'empty', colspan: cols.length, text: 'Nothing here yet.' }))]));
}
const ASSIGNED_COLS = [['Well', r => r.well_name || r.uwi], ['Crew', (r, n) => n(r.crew_id)], ['Risk', r => pct(r.p_repair)],
  ['Expected loss', r => money(r['expected_loss_' + scenario()] ?? r.expected_loss_mid)], ['Note to crew', r => r.manager_note || ''], ['Assigned', r => (r.assigned_at || '').replace('T', ' ').slice(0, 16)]];
const RESOLVED_COLS = [['Well', r => r.well_name || r.uwi], ['Crew', (r, n) => n(r.crew_id)], ['Work done', r => r.work_done || ''],
  ['Crew note', r => r.crew_note || ''], ['Cost', r => money(r.actual_cost)], ['Hours', r => num(r.hours, 1)], ['Resolved', r => (r.resolved_at || '').replace('T', ' ').slice(0, 16)]];

async function refresh() {
  await loadAll();
  await Promise.all([loadWells(), loadAssignments('assigned', 'assignedTable', ASSIGNED_COLS), loadAssignments('resolved', 'resolvedTable', RESOLVED_COLS)]);
}

document.querySelectorAll('.tab').forEach(b => b.addEventListener('click', () => {
  document.querySelectorAll('.tab').forEach(x => x.setAttribute('aria-selected', x === b));
  ['overview', 'wells', 'assigned', 'resolved'].forEach(t => document.getElementById('tab-' + t).classList.toggle('hidden', t !== b.dataset.tab));
  if (b.dataset.tab === 'wells' && S.map) fitMap();
}));
['sort', 'origin', 'minrisk'].forEach(id => document.getElementById(id).addEventListener('change', loadWells));
document.getElementById('scenario').addEventListener('change', () => { renderKpis(); loadWells(); loadAssignments('assigned', 'assignedTable', ASSIGNED_COLS); });
refresh().catch(e => { document.querySelector('main').prepend(el('div', { class: 'banner', text: 'Could not load data: ' + e.message })); });

function renderReliability() {
  const r = S.overview.reliability, box = document.getElementById('reliability');
  if (!r) { box.replaceChildren(); return; }
  const h = r.hazard;
  const early = h[0].hazard_per_day, late = h[6].hazard_per_day;
  const canvas = el('canvas');
  const chartBox = el('div', { style: 'position:relative;height:260px' }, canvas);
  const table = el('table', {}, el('tr', {}, ...['Job type', 'Jobs', 'Share of repair cost', 'Median cost', 'Median days it lasts', 'Repeat within 30 days'].map(t => el('th', { text: t }))),
    ...r.pareto.map(p => el('tr', {}, el('td', { text: p.job_type }), el('td', { text: num(p.jobs) }), el('td', { text: pct(p.share_of_cost) }),
      el('td', { text: money(p.median_cost) }), el('td', { text: num(p.median_life_days) }), el('td', { text: pct(p.repeat_30d_share) }))));
  box.replaceChildren(
    el('h3', { style: 'margin-top:0', text: 'Do fixes last? Risk is highest right after a repair' }),
    el('p', { class: 'small', text: 'Fitted Weibull shape k = ' + r.shape.toFixed(2) + ' (95% CI ' + r.shape_ci[0].toFixed(2) + ' to ' + r.shape_ci[1].toFixed(2) +
      '). Below 1 means risk falls with time since the fix: rod-truck jobs are about ' + Math.round(early / late) + '× likelier to need another visit in the first week than 6 to 12 months out. ' +
      r.age_replacement.reason + ' The money is in doing each repair right the first time.' }),
    chartBox,
    el('p', { class: 'small muted', text: 'Caveat: the next job on a well can be a planned follow-up visit, not a failed fix, so some early risk is return trips.' }),
    el('h4', { text: 'Where the repair money goes, by crew job type' }),
    el('div', { style: 'overflow-x:auto' }, table));
  S.charts.push(new Chart(canvas, { type: 'bar',
    data: { labels: h.map(x => x.from + '–' + (x.to >= 5000 ? '+' : x.to) + ' d'), datasets: [{ label: 'Chance per day of another repair (rod-truck jobs)', data: h.map(x => x.hazard_per_day * 100), backgroundColor: '#c2410c99' }] },
    options: { maintainAspectRatio: false, plugins: { legend: { display: true } }, scales: { y: { title: { display: true, text: '% per day' } }, x: { title: { display: true, text: 'Days since the last repair' } } } } }));
}
