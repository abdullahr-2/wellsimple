// Smoke-test the hosted handler against a disposable copy of the private export.
// Run with Node 22.13+ after export_pages_data.py.
import assert from 'node:assert/strict';
import {timingSafeEqual} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {DatabaseSync} from 'node:sqlite';
import vm from 'node:vm';
import worker from '../pages/worker.js';

const sqlite = new DatabaseSync(':memory:');
sqlite.exec(readFileSync(process.argv[2] || 'artifacts/competition-import.sql','utf8'));
class Statement {
  constructor(sql) { this.statement = sqlite.prepare(sql); this.args = []; }
  bind(...args) { this.args = args; return this; }
  first(col) { const row = this.statement.get(...this.args); return col ? row?.[col] : row; }
  all() { return {results:this.statement.all(...this.args)}; }
  run() {
    const {changes,lastInsertRowid} = this.statement.run(...this.args);
    return {meta:{changes,last_row_id:lastInsertRowid}};
  }
}
const db = {prepare: sql => new Statement(sql), batch: batch => batch.map(s=>s.run())};
if (!crypto.subtle.timingSafeEqual) crypto.subtle.timingSafeEqual = timingSafeEqual;
const env = {DB:db, DEMO_PASSWORD:'test-secret'};
const base = 'https://demo.invalid';
const request = (path, body) => worker.fetch(new Request(base+path,{
  method:body?'POST':'GET',headers:{Authorization:'Basic '+btoa('demo:test-secret'),'Content-Type':'application/json'},
  body: body && JSON.stringify(body)}),env);
async function api(path,body) {
  const res = await request(path,body);
  assert.equal(res.status,200,path);
  return res.json();
}
assert.equal((await worker.fetch(new Request(base+'/api/model'),env)).status,401);
const overview = await api('/api/overview'), pilot = await api('/api/pilot');
const model = await api('/api/model'), fleet = await api('/api/model/inputs');
assert.equal(fleet.rows.length, overview.producing_wells);
assert.equal(pilot.n_control + pilot.n_system, sqlite.prepare('SELECT count(*) AS n FROM wells WHERE arm IS NOT NULL').get().n);
const scripts = vm.createContext({api,URLSearchParams});
vm.runInContext(readFileSync(new URL('../pages/model.js',import.meta.url),'utf8'),scripts);
let maxError = 0;
for (const [well,inputs] of fleet.rows) maxError = Math.max(maxError, Math.abs(scripts.repairProbability(model,inputs)-well.p_repair));
assert.ok(maxError < 1e-12, 'Browser predictions differ from sklearn');
const params = new URLSearchParams({sort:'risk',min_risk:'0.4',limit:'30'});
const scored = await scripts.scoreHostedWells(params), ranked = await api('/api/wells?'+params);
assert.equal(scored.high_risk_wells, overview.high_risk_wells);
assert.equal(scored.wells.map(w=>w.uwi).join(','),ranked.wells.map(w=>w.uwi).join(','));
for (const sort of ['closest','furthest','loss']) assert.ok((await api('/api/wells?sort='+sort)).wells.length);
const well = ranked.wells[0], detail = await api('/api/wells/'+encodeURIComponent(well.uwi));
assert.ok(detail.autopsy.notes.length && detail.precedents.length);
assert.ok(overview.reliability.hazard.length && pilot.power && pilot.outcome === null);
const job = {uwi:well.uwi,crew_id:'crew-1'};
const {id} = await api('/api/assign',job);
assert.equal((await request('/api/assign',job)).status,409);
assert.equal((await api('/api/assignments?status=assigned&crew_id=crew-1'))[0].id,id);
await api('/api/crews/crew-1/location',{lat:53,lon:-110});
await api('/api/assignments/'+id+'/complete',{work_done:['Replaced pump rotor'],note:'Inspect rod string',actual_cost:100,hours:1});
assert.equal((await api('/api/assignments?status=resolved'))[0].id,id);
assert.equal((await request('/api/assignments/'+id+'/complete',{note:'Duplicate'})).status,409);
assert.ok(sqlite.prepare('SELECT vector FROM note_vectors WHERE aid=?').get(id).vector.length > 10);
console.log('Verified',fleet.rows.length,'predictions; max error',maxError,';',scored.high_risk_wells,'high risk;',
  pilot.n_system,'system /',pilot.n_control,'control. Pilot, retrieval, assignment, completion and access checks passed.');
