const S = { overview: null, crews: [], wells: [], map: null, markers: null, charts: [], pts: [] };
const scenario = () => document.getElementById('scenario').value;
const lossKey = () => 'expected_loss_' + scenario();

async function loadAll() {
  const [ov, crews] = await Promise.all([api('/api/overview'), api('/api/crews')]);
  S.overview = ov; S.crews = crews;
  document.getElementById('modelPanel').hidden = !ov.model;
  if (ov.model) {
    document.getElementById('modelSource').textContent = 'Gradient-boosted trees trained on ' +
      num(ov.model.training_snapshots) + ' weekly snapshots from ' + num(ov.model.daily_rows) +
      ' daily records and ' + num(ov.model.job_rows) + ' jobs. Each prediction uses ' + ov.model.features +
      ' sensor and repair-history features as of ' + ov.model.snapshot_date + '. The target includes scheduled repairs.';
  }
  document.getElementById('asof').textContent = 'Data as of ' + ov.as_of;
  const origin = document.getElementById('origin');
  origin.replaceChildren(el('option', { value: '', text: 'Fleet centre' }),
    ...crews.map(c => el('option', { value: c.id, text: c.name + (c.lat != null ? ' (located)' : ' (no location yet)') })));
  renderKpis(); renderOverviewCharts(); renderPotential(); renderReliability(); renderConcentration(); renderQuality(); loadTop10();
}

function renderKpis() {
  const o = S.overview, k = document.getElementById('kpis');
  const loss = o['expected_loss_' + scenario()];
  const card = (v, l, n) => el('div', { class: 'card kpi' }, el('div', { class: 'v', text: v }), el('div', { class: 'l', text: l }), n ? el('div', { class: 'n', text: n }) : null);
  k.replaceChildren(
    card(num(o.producing_wells), 'Producing wells scored', 'as of ' + o.as_of),
    card(num(o.high_risk_wells), 'High-risk wells', '30-day repair chance 40%+'),
    card(moneyM(loss), 'Expected 30-day loss', 'job cost + lost oil, ' + (scenario() === 'low' ? 'conservative' : 'mid') + ' price'),
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
      { type: 'line', label: 'Repair jobs performed (rod truck + workover)', data: m.map(r => r.repair_jobs), borderColor: '#0b6e4f', pointRadius: 0, yAxisID: 'y2' }] },
    options: { responsive: true, scales: { y: { title: { display: true, text: 'm³' } }, y2: { position: 'right', grid: { drawOnChartArea: false } },
      x: { ticks: { maxTicksLimit: 8 } } } } }));
  const codes = Object.entries(S.overview.lost_by_code);
  S.charts.push(new Chart(document.getElementById('chartCodes'), {
    type: 'bar', data: { labels: codes.map(c => c[0]), datasets: [{ data: codes.map(c => c[1]), backgroundColor: '#0b6e4f99' }] },
    options: { indexAxis: 'y', plugins: { legend: { display: false } } } }));
}

async function loadWells(rescore = false) {
  const q = new URLSearchParams({ sort: document.getElementById('sort').value, min_risk: document.getElementById('minrisk').value, limit: 30, scenario: scenario() });
  if (rescore === true) q.set('rescore', 'true');
  const crew = document.getElementById('origin').value; if (crew) q.set('crew_id', crew);
  const r = rescore === true && typeof scoreHostedWells === 'function'
    ? await scoreHostedWells(q) : await api('/api/wells?' + q);
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
  return r;
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
  await Promise.all([loadPilot(), loadWells(), loadAssignments('assigned', 'assignedTable', ASSIGNED_COLS), loadAssignments('resolved', 'resolvedTable', RESOLVED_COLS)]);
}

document.querySelectorAll('.tab').forEach(b => b.addEventListener('click', () => {
  document.querySelectorAll('.tab').forEach(x => x.setAttribute('aria-selected', x === b));
  ['overview', 'wells', 'assigned', 'resolved', 'pilot'].forEach(t => document.getElementById('tab-' + t).classList.toggle('hidden', t !== b.dataset.tab));
  if (b.dataset.tab === 'wells' && S.map) fitMap();
}));
['sort', 'origin', 'minrisk'].forEach(id => document.getElementById(id).addEventListener('change', loadWells));
document.getElementById('runModel').addEventListener('click', async () => {
  const button = document.getElementById('runModel'), status = document.getElementById('modelResult');
  button.disabled = true;
  status.textContent = 'Running inference on the fleet…';
  document.getElementById('sort').value = 'risk';
  document.getElementById('minrisk').value = '0.4';
  try {
    const r = await loadWells(true);
    status.textContent = num(r.scored_wells) + ' wells scored. ' + num(r.high_risk_wells) +
      ' reached 40% repair probability. Showing ' + r.wells.length + ' available wells in risk order.';
  } catch (e) { status.textContent = 'Scoring failed. ' + e.message; }
  finally { button.disabled = false; }
});
document.getElementById('scenario').addEventListener('change', () => { renderKpis(); loadWells(); loadTop10(); loadAssignments('assigned', 'assignedTable', ASSIGNED_COLS); });
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

async function loadPilot() {
  const box = document.getElementById('pilot');
  let p;
  try { p = await api('/api/pilot'); } catch (e) { box.replaceChildren(el('div', { class: 'empty', text: 'No pilot built yet. Run scripts/build_pilot.py.' })); return; }
  const th = (...t) => el('tr', {}, ...t.map(x => el('th', { text: x })));
  const row = (...c) => el('tr', {}, ...c.map(x => el('td', { text: x })));
  const smd = v => (v > 0 ? '+' : '') + v.toFixed(2);
  const pw = p.power.by_effect_percent;
  box.replaceChildren(
    el('h3', { style: 'margin-top:0', text: 'A/B pilot: how we will measure the saving' }),
    el('div', { class: 'banner', text: 'Status: ' + p.status + '. Enrolled on ' + p.enrolled_as_of + '; first read ' + p.earliest_read + '. ' + p.outcome_note }),
    pilotLine('Who', p.population),
    pilotLine('System arm (' + p.n_system + ' wells)', p.arms.system),
    pilotLine('Control arm (' + p.n_control + ' wells)', p.arms.control + (p.pilot_mode ? ' (hidden from this manager view while the pilot runs)' : '')),
    pilotLine('Assignment', 'random within field and baseline-repeat strata, seed ' + p.seed + ', fixed before any outcome'),
    pilotLine('Primary outcome', p.primary_outcome),
    pilotLine('Analysis', p.analysis),
    el('h4', { text: 'Are the arms comparable at the start? (standardized difference; within ±0.1 is balanced)' }),
    el('table', {}, th('Baseline measure', 'System mean', 'Control mean', 'Difference'),
      ...p.balance.map(b => row(b.measure.replaceAll('_', ' '), num(b.system, 2), num(b.control, 2), smd(b.smd)))),
    el('h4', { text: 'Does the test invent effects? A/A check on real history' }),
    el('p', { class: 'small', text: p.aa_check.wells + ' real repeat-prone wells were randomized ' + p.aa_check.trials + ' times with no intervention. The test wrongly reported a difference ' +
      pct(p.aa_check.false_positive_rate) + ' of the time (95% interval ' + pct(p.aa_check.ci_low) + ' to ' + pct(p.aa_check.ci_high) + '). About 5% is correct.' }),
    el('h4', { text: 'How big an effect can it detect? (' + p.power.wells_per_arm + ' wells per arm, 12 months)' }),
    el('table', {}, th('If the system cuts repeat repairs by', 'Chance the pilot detects it'),
      ...Object.entries(pw).map(([k, v]) => row(k + '%', pct(v)))),
    el('p', { class: 'small', text: 'Smallest effect detected with 80% power: ' + (p.power.min_detectable_effect_80pct == null ? 'none in the tested range' : Math.round(p.power.min_detectable_effect_80pct * 100) + '%') +
      '. Smaller effects need a longer pilot or more wells.' }),
    el('p', { class: 'small muted', text: p.effect_size_reference }),
    el('h4', { text: 'Potential result' }),
    pilotPotential(p));
}
function pilotPotential(p) {
  const d = potentialData();
  if (!d) return el('div', { class: 'muted small', text: 'Potential figures appear once the overview data is loaded.' });
  return el('div', {},
    el('p', { style: 'font-size:20px;font-weight:700;margin:4px 0', text: 'Could potentially save about ' + moneyM(d.at(0.30)) + ' a year, and up to ' + moneyM(d.at(0.55)) + ' a year' }),
    el('p', { class: 'small', text: 'That is a 30% cut in repeat repairs, up to the 55% a published root-cause program achieved. Range: ' + moneyM(d.at(0.10)) + ' a year at a 10% cut to ' + moneyM(d.at(0.55)) +
      ' at 55%. Based on the measured repeat-repair pool of ' + moneyM(d.repair) + ' a year of repair spend plus about ' + moneyM(d.oil) + ' of lost oil.' }),
    el('p', { class: 'small muted', text: 'The pilot is enrolled and randomized. Its measured result reads out at 12 months (first read ' + p.earliest_read + ') and will replace these potential figures with the measured saving.' }));
}
function pilotLine(label, text) { return el('p', { class: 'small', style: 'margin:4px 0' }, el('b', { text: label + ': ' }), text); }

// Potential saving: the measured repeat-repair pool times a range of possible reductions.
// Wording is deliberate: "could potentially save", never "will save". The A/B pilot measures the real figure.
function potentialData() {
  const o = S.overview, r = o.reliability && o.reliability.repeat_spend && o.reliability.repeat_spend[0];
  if (!r) return null;
  const jobsPerYear = r.jobs * r.cost_per_year / r.cost;
  const oil = jobsPerYear * o.lost_m3_per_event * 6.2898 * o.netback_scenarios.low;
  const pool = r.cost_per_year + oil, at = f => pool * f;
  return { repair: r.cost_per_year, oil, pool, at };
}
function renderPotential() {
  const box = document.getElementById('potential'), d = potentialData();
  if (!d) { box.replaceChildren(); return; }
  const rows = [[0.10, ''], [0.30, ''], [0.50, 'smallest effect the pilot can reliably detect'], [0.55, 'published before/after benchmark (Chad PCP program)']];
  box.replaceChildren(
    el('h3', { style: 'margin-top:0', text: 'Potential saving (not measured)' }),
    el('p', { text: 'About ' + moneyM(d.repair) + ' a year of repair spend, plus about ' + moneyM(d.oil) + ' of lost oil (conservative price), comes from repair jobs that start within 30 days of a previous repair on the same well. If better repairs cut those repeats, Strathcona could potentially save:' }),
    el('table', {}, el('tr', {}, ...['If repeat repairs fall by', 'Could potentially save per year', 'Basis'].map(t => el('th', { text: t }))),
      ...rows.map(([f, why]) => el('tr', {}, el('td', { text: Math.round(f * 100) + '%' }), el('td', { text: moneyM(d.at(f)) }), el('td', { class: 'muted', text: why })))),
    el('p', { class: 'small muted', text: 'Based on the measured repeat-repair spend (field cost estimates) and the stated scenarios. It is a ceiling-based potential, not a measured saving: some repeats are planned follow-ups, and the 55% figure comes from one uncontrolled published case. The A/B pilot is designed to measure the real number.' }));
}

// ---- "Act on these 10 first": highest expected loss, with likely component and precedent ----
async function loadTop10() {
  const box = document.getElementById('top10');
  const r = await api('/api/wells?sort=loss&limit=10&scenario=' + scenario());
  const comp = w => {
    const c = [['Pump', w.p_pump], ['Rods', w.p_rods], ['Tubing', w.p_tubing]].filter(x => x[1] != null).sort((a, b) => b[1] - a[1]);
    return c.length ? c[0][0] + ' ' + pct(c[0][1]) : '–';
  };
  box.replaceChildren(
    el('h3', { style: 'margin-top:0', text: 'Act on these 10 first' }),
    el('p', { class: 'small muted', text: 'Highest expected 30-day loss (' + (scenario() === 'low' ? 'conservative' : 'mid') + ' oil price). Likely component comes from sensors alone; the last column is how long similar past repairs lasted.' }),
    el('div', { style: 'overflow-x:auto' }, el('table', {},
      el('tr', {}, ...['#', 'Well', 'Field', 'Risk (30 d)', 'Expected loss', 'Likely component', 'Similar fixes lasted', 'Why flagged'].map(t => el('th', { text: t }))),
      ...r.wells.map((w, i) => el('tr', { class: 'clickable', onclick: () => { document.querySelector('[data-tab=wells]').click(); showDetail(w); } },
        el('td', { text: String(i + 1) }), el('td', { text: w.well_name || w.uwi }), el('td', { text: w.field_operating_area || '' }),
        el('td', {}, riskPill(w.p_repair)), el('td', { text: money(w[lossKey()]) }), el('td', { text: comp(w) }),
        el('td', { text: w.precedent_life_days == null ? '–' : num(w.precedent_life_days) + ' days' }),
        el('td', { class: 'small', text: w.reasons || 'general risk' }))))));
}

// ---- the killer chart: repair work is concentrated on a few wells ----
function renderConcentration() {
  const c = S.overview.concentration, box = document.getElementById('concentration');
  if (!c) { box.replaceChildren(); return; }
  const a = c.all_repairs, canvas = el('canvas');
  box.replaceChildren(
    el('h3', { style: 'margin-top:0', text: 'The worst 10% of wells take ' + pct(a.top10_share) + ' of all repair jobs' }),
    el('p', { class: 'small muted', text: 'Share of repair jobs (rod truck and workover, 2021 to 2026) taken by the worst wells. The dashed line is what an even spread would look like. Rod truck jobs alone: ' + pct(c.rod_truck.top10_share) + '.' }),
    el('div', { style: 'position:relative;height:240px' }, canvas));
  S.charts.push(new Chart(canvas, { type: 'line',
    data: { labels: a.points.map(p => p.wells_pct + '%'), datasets: [
      { label: 'Share of repair jobs', data: a.points.map(p => p.jobs_pct * 100), borderColor: '#c2410c', backgroundColor: '#c2410c22', fill: true, pointRadius: 0 },
      { label: 'Even spread', data: a.points.map(p => p.wells_pct), borderColor: '#94a3b8', borderDash: [6, 6], pointRadius: 0 }] },
    options: { maintainAspectRatio: false, scales: { x: { title: { display: true, text: 'Worst wells (share of wells with repairs)' }, ticks: { maxTicksLimit: 10 } },
      y: { title: { display: true, text: '% of repair jobs' }, max: 100 } } } }));
}

// ---- model quality: held-out accuracy, baselines, calibration, new field ----
function renderQuality() {
  const q = S.overview.model_quality, box = document.getElementById('quality');
  if (!q) { box.replaceChildren(); return; }
  const canvas = el('canvas'), f3 = v => v.toFixed(3);
  const row = (...c) => el('tr', {}, ...c.map(x => el('td', { text: x })));
  const few = q.cold_start['1 to 2 previous repairs'];
  box.replaceChildren(
    el('h3', { style: 'margin-top:0', text: 'Can you trust the risk score?' }),
    el('p', { class: 'small', text: 'Tested on ' + num(q.test_rows) + ' well-weeks from ' + q.cutoff + ' on, trained only on earlier data.' }),
    el('table', {}, el('tr', {}, ...['Method', 'Accuracy (AUC)', 'Top 5% that needed a repair'].map(t => el('th', { text: t }))),
      row('WellSimple model', f3(q.model.auc) + ' (' + f3(q.model.ci.auc[0]) + ' to ' + f3(q.model.ci.auc[1]) + ')', pct(q.model.precision_top5)),
      row('Each well’s own repair history', f3(q.baselines.well_history.auc), pct(q.baselines.well_history.precision_top5)),
      row('Field average', f3(q.baselines.field_average.auc), pct(q.baselines.field_average.precision_top5)),
      row('Picking wells at random', '0.500', pct(q.base_rate))),
    el('h4', { text: 'Calibration: when it says 40%, about 40% need a repair' }),
    el('div', { style: 'position:relative;height:200px' }, canvas),
    el('p', { class: 'small muted', text: 'New field (model trained without it), AUC unseen vs seen: ' +
      Object.entries(q.new_field).map(([k, v]) => k + ' ' + f3(v.auc_unseen_field) + ' vs ' + f3(v.auc_seen_field)).join(', ') +
      '. Wells with only 1 to 2 past repairs: AUC ' + (few ? f3(few.auc) : '–') + '.' }));
  const pts = q.calibration.map(b => ({ x: b.predicted * 100, y: b.observed * 100 }));
  S.charts.push(new Chart(canvas, { type: 'scatter',
    data: { datasets: [{ label: 'Observed vs predicted (tenths of wells)', data: pts, backgroundColor: '#0b6e4f' },
      { label: 'Perfect calibration', type: 'line', data: [{ x: 0, y: 0 }, { x: 50, y: 50 }], borderColor: '#94a3b8', borderDash: [6, 6], pointRadius: 0 }] },
    options: { maintainAspectRatio: false, scales: { x: { type: 'linear', title: { display: true, text: 'Predicted chance (%)' }, min: 0, max: 50 },
      y: { title: { display: true, text: 'Observed (%)' }, min: 0, max: 50 } } } }));
}
