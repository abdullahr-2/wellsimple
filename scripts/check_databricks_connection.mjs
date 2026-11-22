import assert from 'node:assert/strict';
import {databricksApi} from '../pages/databricks_api.js';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const secret = process.env.WELLSIMPLE_TEST_SECRET;
assert.ok(secret);
const env = {DATABRICKS_CLIENT_SECRET: secret};
async function get(path) {
  const response = await databricksApi(new Request('https://example.invalid' + path),env);
  assert.equal(response.status,200,path + ': ' + (response.status === 200 ? '' : await response.text()));
  return response.json();
}
const [overview, pilot, model, fleet, ranked, crews, assignments] = await Promise.all([
  get('/api/overview'), get('/api/pilot'), get('/api/model'), get('/api/model/inputs'),
  get('/api/wells?sort=risk&limit=30&min_risk=0.4'), get('/api/crews'), get('/api/assignments')
]);
assert.equal(fleet.rows.length,overview.producing_wells);
assert.equal(model.trees.length,model.trees.length && 250);
const inference = vm.createContext({});
vm.runInContext(readFileSync(new URL('../pages/model.js',import.meta.url),'utf8'),inference);
for (const [well,inputs] of fleet.rows) {
  assert.ok(Math.abs(inference.repairProbability(model,inputs)-well.p_repair)<1e-12);
}
assert.equal(pilot.n_system+pilot.n_control,369);
assert.equal(crews.length,4);
assert.ok(ranked.wells.length);
assert.ok(assignments.length >= 3);
const detail=await get('/api/wells/'+encodeURIComponent(ranked.wells[0].uwi));
assert.ok(detail.precedents.length && detail.autopsy.notes.length);
console.log('Databricks service identity verified:',fleet.rows.length,'wells,',model.trees.length,'trees,',
  assignments.length,'existing assignments. Detail and pilot checks passed.');
