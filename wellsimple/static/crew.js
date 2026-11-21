const WORK = ['Rod string replaced', 'Polish rod replaced', 'Pump / rotor replaced', 'Tubing repaired or replaced',
  'Sand cleaned out', 'Wellhead / surface repair', 'Adjusted RPM', 'Inspected, no fault found'];
const C = { crewId: localStorage.getItem('crewId'), pos: null, job: null, map: null, layers: null, watch: null, lastSent: 0 };
const $ = (id) => document.getElementById(id);

function km(a, b, c, d) {
  const r = 6371.0088, rad = x => x * Math.PI / 180, dp = rad(c - a), dl = rad(d - b);
  const h = Math.sin(dp / 2) ** 2 + Math.cos(rad(a)) * Math.cos(rad(c)) * Math.sin(dl / 2) ** 2;
  return 2 * r * Math.asin(Math.sqrt(h));
}

// ---- offline queue: submissions made without signal are kept and retried ----
const queue = () => { try { return JSON.parse(localStorage.getItem('queue') || '[]'); } catch (_) { return []; } };
const saveQueue = (q) => localStorage.setItem('queue', JSON.stringify(q));
function showQueue() { const n = queue().length; $('queueStatus').textContent = n ? n + ' waiting to send' : ''; }
async function flushQueue() {
  const rest = [];
  for (const item of queue()) {
    try { await api('/api/assignments/' + item.aid + '/complete', { method: 'POST', body: item.body }); }
    catch (e) { if (!(e instanceof TypeError)) continue; rest.push(item); }  // keep only network failures
  }
  saveQueue(rest); showQueue(); if (!C.job) loadJobs();
}
window.addEventListener('online', flushQueue);

// ---- crew + location ----
async function init() {
  const crews = await api('/api/crews');
  const sel = $('crew');
  sel.replaceChildren(...crews.map(c => el('option', { value: c.id, text: c.name })));
  if (!crews.some(c => c.id === C.crewId)) C.crewId = crews[0].id;
  sel.value = C.crewId;
  sel.addEventListener('change', () => { C.crewId = sel.value; localStorage.setItem('crewId', C.crewId); closeJob(); loadJobs(); });
  $('loc').addEventListener('click', startLocation);
  $('back').addEventListener('click', closeJob);
  $('submit').addEventListener('click', submit);
  setupChips(); setupDictation(); showQueue();
  await flushQueue(); await loadJobs();
}
function startLocation() {
  if (!navigator.geolocation) { $('locStatus').textContent = 'Location not supported'; return; }
  if (C.watch != null) return;
  $('locStatus').textContent = 'Locating…';
  C.watch = navigator.geolocation.watchPosition(p => {
    C.pos = { lat: p.coords.latitude, lon: p.coords.longitude };
    $('locStatus').textContent = 'Location on';
    if (Date.now() - C.lastSent > 30000) {
      C.lastSent = Date.now();
      api('/api/crews/' + C.crewId + '/location', { method: 'POST', body: C.pos }).catch(() => {});
    }
    if (C.job) updateJobMap();
  }, e => { $('locStatus').textContent = 'Location unavailable (' + e.message + ')'; C.watch = null; },
  { enableHighAccuracy: true, maximumAge: 15000, timeout: 20000 });
}

// ---- list ----
async function loadJobs() {
  const rows = await api('/api/assignments?status=assigned&crew_id=' + encodeURIComponent(C.crewId));
  $('jobs').replaceChildren(...(rows.length ? rows.map(r => {
    const d = (C.pos && r.lat != null) ? km(C.pos.lat, C.pos.lon, r.lat, r.lon) : null;
    return el('button', { class: 'card job', onclick: () => openJob(r) },
      el('h3', {}, r.well_name || r.uwi, ' ', riskPill(r.p_repair)),
      el('div', { class: 'small muted', text: (r.field || '') + (d != null ? ' · ' + num(d, 1) + ' km away' : '') }),
      r.manager_note ? el('div', { class: 'small', text: 'Manager: ' + r.manager_note }) : null);
  }) : [el('div', { class: 'empty', text: 'No wells assigned to this crew right now.' })]));
}

// ---- job ----
async function openJob(r) {
  C.job = r; $('listView').classList.add('hidden'); $('jobView').classList.remove('hidden'); $('msg').textContent = '';
  $('jTitle').textContent = r.well_name || r.uwi;
  $('jRisk').replaceChildren(riskPill(r.p_repair));
  $('jMeta').textContent = (r.field || '') + ' · ' + r.uwi;
  $('jManager').replaceChildren(...(r.manager_note ? [el('div', { class: 'note', text: 'Manager: ' + r.manager_note })] : []));
  $('jReasons').replaceChildren(...(r.reasons ? r.reasons.split('; ').map(x => el('span', { class: 'tag', text: x })) : []));
  $('jSummary').textContent = ''; $('jAutopsy').replaceChildren(); $('jPrec').replaceChildren(el('div', { class: 'muted small', text: 'Loading similar past jobs…' }));
  $('navLink').href = 'https://www.google.com/maps/dir/?api=1&destination=' + r.lat + ',' + r.lon;
  if (!C.map) { C.map = osmMap('jmap', [r.lat, r.lon], 12); C.layers = L.layerGroup().addTo(C.map); }
  updateJobMap(true); setTimeout(() => C.map.invalidateSize(), 50);
  try {
    const d = await api('/api/wells/' + encodeURIComponent(r.uwi) + '?k=3'), s = d.summary;
    $('jAutopsy').replaceChildren(autopsyBlock(d.autopsy));
    if (s && s.median_life_days != null)
      $('jSummary').textContent = 'Similar past repairs lasted a median of ' + num(s.median_life_days) + ' days at about ' + money(s.cost_per_day_of_life) + ' per day of well life.';
    $('jPrec').replaceChildren(...(d.precedents.length ? d.precedents.map(p => el('div', { class: 'note' },
      el('div', { class: 'small muted', text: (p.date || '') + ' · lasted ' + (p.life_days == null ? 'unknown' : num(p.life_days) + ' days') + ' · ' + money(p.cost) }),
      el('div', { text: p.text }))) : [el('div', { class: 'muted small', text: 'No similar past jobs found.' })]));
  } catch (e) { $('jPrec').replaceChildren(el('div', { class: 'muted small', text: 'Could not load past jobs (offline?).' })); }
}
function updateJobMap(fit) {
  const r = C.job; C.layers.clearLayers();
  const pts = [[r.lat, r.lon]];
  L.circleMarker([r.lat, r.lon], { radius: 10, color: '#b91c1c', fillColor: '#b91c1c', fillOpacity: .7 }).bindTooltip('Well').addTo(C.layers);
  if (C.pos) {
    pts.push([C.pos.lat, C.pos.lon]);
    L.circleMarker([C.pos.lat, C.pos.lon], { radius: 8, color: '#1d4ed8', fillColor: '#3b82f6', fillOpacity: .9 }).bindTooltip('You').addTo(C.layers);
    L.polyline(pts, { color: '#64748b', dashArray: '6 6' }).addTo(C.layers);
    $('jDist').textContent = num(km(C.pos.lat, C.pos.lon, r.lat, r.lon), 1) + ' km from you';
  } else $('jDist').textContent = 'Share your location to see the distance';
  if (fit || C.pos) C.map.fitBounds(pts, { padding: [40, 40], maxZoom: 14 });
}
function closeJob() { C.job = null; $('jobView').classList.add('hidden'); $('listView').classList.remove('hidden'); loadJobs(); }

// ---- completion ----
function setupChips() {
  $('chips').replaceChildren(...WORK.map(w => el('label', {}, el('input', { type: 'checkbox', value: w }), el('span', { text: w }))));
}
async function submit() {
  const work = [...document.querySelectorAll('#chips input:checked')].map(i => i.value);
  const note = $('cNote').value.trim();
  if (!work.length && note.length < 3) { $('msg').textContent = 'Pick what you did or write a short note.'; return; }
  const body = { work_done: work, note,
    actual_cost: $('cCost').value === '' ? null : Number($('cCost').value),
    hours: $('cHours').value === '' ? null : Number($('cHours').value),
    lat: C.pos ? C.pos.lat : null, lon: C.pos ? C.pos.lon : null };
  $('submit').disabled = true;
  try {
    await api('/api/assignments/' + C.job.id + '/complete', { method: 'POST', body });
    $('msg').textContent = 'Sent. Well marked resolved.';
  } catch (e) {
    if (e instanceof TypeError) {  // no network: keep it and send later
      saveQueue([...queue(), { aid: C.job.id, body }]); showQueue();
      $('msg').textContent = 'No signal. Saved on this phone and will send when you are back online.';
    } else { $('msg').textContent = 'Could not send: ' + e.message; $('submit').disabled = false; return; }
  }
  $('cNote').value = ''; $('cCost').value = ''; $('cHours').value = '';
  document.querySelectorAll('#chips input').forEach(i => i.checked = false);
  setTimeout(() => { $('submit').disabled = false; closeJob(); }, 1200);
}

// ---- dictation (browser speech recognition) ----
// Chrome and Edge use an online speech service. Other browsers (Brave, Firefox, plain Chromium) may expose the
// API but never start, so every failure path says what is wrong instead of failing silently.
const DICT_ERRORS = {
  'not-allowed': "Microphone is blocked. Click the lock icon in the address bar, allow the microphone, then try again.",
  'service-not-allowed': "This browser blocks its speech service. Use Chrome or Edge, or your keyboard's microphone key.",
  'audio-capture': "No microphone found. Plug one in or check your system sound settings.",
  'network': "The speech service could not be reached. Dictation needs an internet connection in Chrome and Edge.",
  'no-speech': "Did not hear anything. Try again closer to the microphone.",
  'language-not-supported': "This browser does not support dictation in English (Canada).",
};
function setupDictation() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  const btn = $('dictate'), hint = $('dictHint'), note = $('cNote');
  const IDLE = "Uses your browser's speech recognition. Your keyboard's microphone key also works.";
  hint.textContent = IDLE;
  if (!SR) {
    btn.disabled = true;
    hint.textContent = "Dictation is not available in this browser. Use Chrome or Edge, or your keyboard's microphone key.";
    return;
  }
  let rec = null, watchdog = null, failed = false;
  const reset = () => { clearTimeout(watchdog); rec = null; btn.textContent = 'Dictate'; };
  btn.addEventListener('click', () => {
    if (rec) { rec.stop(); return; }
    if (!window.isSecureContext) { hint.textContent = 'Dictation needs https or localhost. Open this page as http://127.0.0.1:8000/crew.'; return; }
    let r;
    try { r = new SR(); } catch (e) { hint.textContent = 'Could not start dictation: ' + e.message; return; }
    r.lang = 'en-CA'; r.continuous = true; r.interimResults = true;
    const base = note.value; let finalText = ''; failed = false;
    r.onstart = () => { clearTimeout(watchdog); hint.textContent = 'Listening… speak now. Tap Stop dictating when finished.'; };
    r.onresult = ev => {
      let interim = '';
      for (let i = ev.resultIndex; i < ev.results.length; i++) {
        const t = ev.results[i][0].transcript;
        if (ev.results[i].isFinal) finalText += (finalText ? ' ' : '') + t.trim(); else interim += t;
      }
      const spoken = (finalText + (interim ? (finalText ? ' ' : '') + interim : '')).trim();
      note.value = (base + (base && spoken ? ' ' : '') + spoken).trim();
    };
    r.onerror = e => {
      if (e.error === 'aborted') return;
      failed = true; hint.textContent = DICT_ERRORS[e.error] || ('Dictation error: ' + e.error);
    };
    r.onend = () => { if (!failed && hint.textContent.startsWith('Listening')) hint.textContent = IDLE; reset(); };
    rec = r; btn.textContent = 'Stop dictating'; hint.textContent = 'Starting the microphone…';
    // some browsers expose the API but never start it: say so instead of hanging
    watchdog = setTimeout(() => {
      if (rec === r) {
        try { r.abort(); } catch (_) {}
        failed = true; reset();
        hint.textContent = "Your browser did not start dictation (Brave, Firefox and plain Chromium often cannot). Use Chrome or Edge, or your keyboard's microphone key.";
      }
    }, 5000);
    try { r.start(); } catch (e) { failed = true; reset(); hint.textContent = 'Could not start dictation: ' + e.message; }
  });
}
init().catch(e => document.querySelector('main').prepend(el('div', { class: 'banner', text: 'Could not load: ' + e.message })));
