// Public portfolio fixture. All wells, scores, coordinates and job notes are invented.
// The production portals call the same interface over HTTP in the field application.
const demoWells = [
  ['Alder 01', 'Alder Flats', 53.23, -110.31, .68, 37000, 'Rod torque rising', 'Rods', 'Polished rod clamp showed wear. Replaced the clamp and checked alignment.', 42],
  ['Ember 02', 'Ember Valley', 53.32, -110.42, .46, 62000, 'Pump efficiency falling', 'Pump', 'Changed the pump rotor after inspecting the stator. Flow recovered during the test.', 104],
  ['Alder 03', 'Alder Flats', 53.26, -110.36, .35, 26000, 'Recent repeat repair', 'Rods', 'Checked rod guides and replaced a worn coupling. Recorded the starting load.', 58],
  ['Larch 04', 'Larch Creek', 53.44, -110.25, .29, 44000, 'Tubing pressure falling', 'Tubing', 'A pressure test identified a leaking tubing joint. Changed the joint and retested.', 89],
  ['Ember 05', 'Ember Valley', 53.36, -110.48, .18, 30000, 'Flow below recent average', 'Pump', 'Sand was present at the intake. Cleaned the intake and checked pump rotation.', 116],
  ['Larch 06', 'Larch Creek', 53.48, -110.27, .12, 28000, 'Variable casing pressure', 'Tubing', 'Inspected tubing connections and replaced a damaged seal.', 77]
].map(([well_name, field_operating_area, surface_latitude, surface_longitude, p_repair, cost, reasons, component, note, days], i) => ({
  uwi: 'DEMO-' + (i + 1), well_name, field_operating_area, surface_latitude, surface_longitude,
  p_repair, reasons, component, note, days, event_cost_mid: cost,
  expected_loss_mid: Math.round(cost * p_repair), expected_loss_low: Math.round(cost * p_repair * .86)
}));
const demoKey = 'wellsimple.public.v1';
const demoCrewIds = ['crew-1', 'crew-2', 'crew-3', 'crew-4'];
function initialDemoState() {
  return { assignments: [{ id: 1, uwi: 'DEMO-6', crew_id: 'crew-1', status: 'assigned',
    assigned_at: '2026-10-31T08:00:00Z', manager_note: 'Review the tubing history before the visit.' }], locations: {} };
}
function demoDistance(a, b, c, d) {
  const rad = Math.PI / 180;
  const h = Math.sin((c-a)*rad/2)**2 + Math.cos(a*rad)*Math.cos(c*rad)*Math.sin((d-b)*rad/2)**2;
  return 12742 * Math.asin(Math.min(1, Math.sqrt(h)));
}
async function demoApi(path, options = {}) {
  const url = new URL(path, 'https://demo.invalid'), q = url.searchParams;
  const state = JSON.parse(localStorage.getItem(demoKey) || 'null') || initialDemoState();
  const jobs = state.assignments, body = options.body || {};
  const save = () => localStorage.setItem(demoKey, JSON.stringify(state));
  const getWell = uwi => demoWells.find(w => w.uwi === uwi);
  const [, , resource, id, action] = url.pathname.split('/');
  if (resource === 'overview') {
    const total = key => demoWells.reduce((sum, w) => sum + w[key], 0);
    return { as_of: '2026-10-31', producing_wells: demoWells.length, high_risk_wells: 2,
      expected_loss_low: total('expected_loss_low'), expected_loss_mid: total('expected_loss_mid'),
      repair_repeat_90d_share: .33, open_assignments: jobs.filter(j => j.status === 'assigned').length,
      resolved_count: jobs.filter(j => j.status === 'resolved').length,
      monthly: [82, 65, 110, 74, 68, 92].map((loss,i) => ({month: '2026-' + String(i+5).padStart(2,'0'), lost_oil_m3: loss, repair_jobs: [2,1,3,2,1,2][i]})),
      lost_by_code: { Pump: 230, Rods: 171, Tubing: 90 } };
  }
  if (resource === 'crews' && !id) return demoCrewIds.map((id,i) => ({id, name: 'Crew ' + (i+1), ...state.locations[id]}));
  if (resource === 'crews' && action === 'location') { state.locations[id] = body; save(); return {ok:true}; }
  if (resource === 'wells' && !id) {
    const origin = state.locations[q.get('crew_id')] || {lat: 53.35, lon: -110.35};
    const sort = q.get('sort');
    const wells = demoWells.filter(w => w.p_repair >= Number(q.get('min_risk')) && !jobs.some(j => j.uwi === w.uwi))
      .map(w => ({...w, distance_km: demoDistance(origin.lat, origin.lon, w.surface_latitude, w.surface_longitude)}));
    const by = {risk: (a,b) => b.p_repair-a.p_repair, closest: (a,b) => a.distance_km-b.distance_km,
      furthest: (a,b) => b.distance_km-a.distance_km, loss: (a,b) => b.expected_loss_mid-a.expected_loss_mid};
    return {wells: wells.sort(by[sort] || by.loss)};
  }
  if (resource === 'wells' && id) {
    const well = getWell(id), similar = demoWells.filter(w => w.uwi !== id && w.component === well.component);
    const precedents = similar.map(w => ({date: '2026-05-18', text: w.note, life_days: w.days, cost: w.event_cost_mid, similarity: 'illustrative match'}));
    for (const job of jobs.filter(j => j.status === 'resolved' && j.uwi !== id && getWell(j.uwi).component === well.component)) {
      precedents.unshift({date: job.resolved_at.slice(0,10), text: job.crew_note || job.work_done, cost: job.actual_cost, life_days: null, similarity: 'demo submission'});
    }
    const ref = similar[0];
    return {well, precedents: precedents.slice(0, Number(q.get('k')) || 5),
      summary: {median_life_days: ref.days, life_p25: ref.days, life_p75: ref.days, cost_per_day_of_life: ref.event_cost_mid/ref.days},
      autopsy: {p: Object.fromEntries(['Pump','Rods','Tubing'].map(c => [c, c === well.component ? .7 : .15])),
        notes: [{component: ref.component, text: ref.note}]}};
  }
  if (resource === 'assign') {
    if (jobs.some(j => j.uwi === body.uwi)) throw Error('This well already has a job.');
    const job = {id: Math.max(0, ...jobs.map(j => j.id)) + 1, uwi: body.uwi, crew_id: body.crew_id,
      assigned_at: new Date().toISOString(), status: 'assigned', manager_note: body.note || ''};
    jobs.push(job); save(); return job;
  }
  if (resource === 'assignments' && action === 'complete') {
    const job = jobs.find(j => j.id === Number(id));
    if (!job || job.status !== 'assigned') throw Error('This assignment is no longer open.');
    Object.assign(job, {status:'resolved', resolved_at:new Date().toISOString(), work_done:body.work_done.join(', '),
      crew_note:body.note, actual_cost:body.actual_cost, hours:body.hours}); save(); return job;
  }
  if (resource === 'assignments') return jobs.filter(j => (!q.get('status') || j.status === q.get('status')) &&
    (!q.get('crew_id') || j.crew_id === q.get('crew_id'))).map(j => {
      const w = getWell(j.uwi);
      return {...w, ...j, field:w.field_operating_area, lat:w.surface_latitude, lon:w.surface_longitude};
    }).reverse();
  throw Error('Unavailable in the fictional demo');
}
