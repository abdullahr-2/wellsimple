import {query} from './databricks.js';

const schema = 'workspace.wellsimple.';
const json = value => Response.json(value, {headers: {'Cache-Control': 'private, no-store'}});
let cachedFacts, cachedWells;

class ApiError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}
function requireValue(condition, message, status = 422) {
  if (!condition) throw new ApiError(status, message);
}
function inRange(value, min, max) {
  return typeof value === 'number' && Number.isFinite(value) && value >= min && value <= max;
}
function parameter(name, value, type = 'STRING') {
  return {name, value: value == null ? null : String(value), type};
}
async function facts(secret) {
  if (!cachedFacts) {
    const result = await query(secret, 'SELECT key, value FROM ' + schema + 'facts');
    cachedFacts = Object.fromEntries(result.map(row => [row.key, JSON.parse(row.value)]));
  }
  return cachedFacts;
}
async function wells(secret) {
  if (!cachedWells) {
    const result = await query(secret, "SELECT uwi, listing, inputs, arm, get_json_object(detail, '$.well.p_pump') AS p_pump, get_json_object(detail, '$.well.p_rods') AS p_rods, get_json_object(detail, '$.well.p_tubing') AS p_tubing FROM " + schema + 'wells');
    cachedWells = result.map(row => ({uwi: row.uwi,
      listing: {...JSON.parse(row.listing), ...Object.fromEntries(['p_pump','p_rods','p_tubing'].map(k => [k, row[k] == null ? null : Number(row[k])]))},
      inputs: JSON.parse(row.inputs), arm: row.arm}));
  }
  return cachedWells;
}
async function state(secret) {
  const rows = await query(secret, 'SELECT revision, payload FROM ' + schema + 'app_state WHERE id=1');
  if (rows.length !== 1) throw new Error('Application state is unavailable');
  return {revision: rows[0].revision, value: JSON.parse(rows[0].payload)};
}
async function mutate(secret, action) {
  for (let attempt = 0; attempt < 5; attempt++) {
    const current = await state(secret);
    const outcome = await action(current.value);
    let result;
    try {
      result = await query(secret, 'UPDATE ' + schema + 'app_state SET payload=:payload, revision=revision+1 WHERE id=1 AND revision=:revision', [
        parameter('payload', JSON.stringify(current.value)),
        parameter('revision', current.revision, 'BIGINT')
      ]);
    } catch (error) {
      if (/DELTA_CONCURRENT|CONCURRENT_(APPEND|WRITE|MODIFICATION)/i.test(error.message)) continue;
      throw error;
    }
    const count = Number(result[0]?.num_affected_rows);
    if (count === 1) return outcome;
    if (count !== 0) throw new Error('Unexpected database update result');
  }
  throw new ApiError(409, 'Another update was made. Please retry.');
}
function origin(snapshot, facts, crewId) {
  const crew = snapshot.crews.find(c => c.id === crewId && c.lat != null);
  return crew ? {coords: [crew.lat, crew.lon], label: crew.name} : {coords: facts.origin, label: 'fleet centre'};
}
function distance(a, b, c, d) {
  if ([a,b,c,d].some(v => v == null)) return null;
  const rad = Math.PI / 180;
  const h = Math.sin((c-a)*rad/2)**2 + Math.cos(a*rad)*Math.cos(c*rad)*Math.sin((d-b)*rad/2)**2;
  return 12742.0176 * Math.asin(Math.sqrt(Math.min(1,h)));
}
function summarize(neighbors) {
  const sorted = key => neighbors.map(p => p[key]).filter(Number.isFinite).sort((a,b) => a-b);
  const quantile = (a,p) => {
    if (!a.length) return null;
    const x = (a.length-1)*p, n = Math.floor(x);
    return a[n] + (a[Math.ceil(x)]-a[n])*(x-n);
  };
  const life = sorted('life_days'), cost = quantile(sorted('cost'),.5), median = quantile(life,.5);
  return {n: neighbors.length, median_life_days: median, life_p25: quantile(life,.25), life_p75: quantile(life,.75),
    median_cost: cost, cost_per_day_of_life: median > 0 && cost != null ? cost/median : null};
}
async function embed(secret, text) {
  const counts = new Map();
  for (const word of text.toLowerCase().match(/[\p{L}\p{N}_]{2,}/gu) || []) counts.set(word,(counts.get(word)||0)+1);
  const words = [...counts.keys()], result = [];
  for (let i=0; i<words.length; i+=80) {
    const chunk = words.slice(i,i+80);
    const params = chunk.map((word,j) => parameter('p'+j,word));
    const matches = await query(secret, 'SELECT word, projection FROM ' + schema + 'terms WHERE word IN (' +
      params.map(p => ':'+p.name).join(',') + ')', params);
    for (const row of matches) {
      const tf = 1 + Math.log(counts.get(row.word));
      JSON.parse(row.projection).forEach((v,j) => { result[j] = (result[j]||0) + v*tf; });
    }
  }
  const norm = Math.hypot(...result);
  return norm ? result.map(v => v/norm) : result;
}
async function detail(secret, uwi, k, snapshot) {
  requireValue(Number.isInteger(k) && inRange(k,1,15),'Invalid neighbor count');
  const rows = await query(secret, 'SELECT detail FROM ' + schema + 'wells WHERE uwi=:uwi', [parameter('uwi',uwi)]);
  requireValue(rows.length === 1,'Unknown well',404);
  const {vector, ...result} = JSON.parse(rows[0].detail);
  if (vector.length) {
    for (const entry of snapshot.vectors || []) {
      const job = snapshot.assignments.find(a => a.id === entry.aid && a.uwi !== uwi);
      if (!job) continue;
      const similarity = JSON.parse(entry.vector).reduce((sum,x,j) => sum+x*vector[j],0);
      result.precedents.push({date:job.resolved_at.slice(0,10), text:[job.work_done,job.crew_note].filter(Boolean).join(' . ').slice(0,500),
        cost:job.actual_cost, life_days:null, similarity});
    }
    result.precedents.sort((a,b) => b.similarity-a.similarity);
  }
  result.summary = result.query ? summarize(result.precedents.slice(0,10)) : null;
  result.precedents = result.precedents.slice(0,k).map(p => ({...p, similarity:Number(p.similarity.toFixed(3))}));
  return result;
}
function decorate(job, fleet) {
  const entry = fleet.find(w => w.uwi === job.uwi);
  if (!entry) return job;
  const w = entry.listing;
  return {...w,...job,field:w.field_operating_area,lat:w.surface_latitude,lon:w.surface_longitude};
}

export async function databricksApi(request, env) {
  try {
    const secret = env.DATABRICKS_CLIENT_SECRET;
    if (!secret) throw new Error('Databricks credentials are unavailable');
    const url = new URL(request.url), path = url.pathname, q = url.searchParams;
    const pilotMode = env.PILOT_MODE === '1';
    if (request.method === 'POST') {
      requireValue(!request.headers.get('Origin') || request.headers.get('Origin') === url.origin,'Invalid origin',403);
      requireValue(request.headers.get('Content-Type')?.startsWith('application/json'),'Expected JSON',415);
      const raw = await request.text();
      requireValue(raw.length <= 32000,'Request too large',413);
      let body;
      try { body=JSON.parse(raw); } catch { throw new ApiError(400,'Invalid JSON'); }
      requireValue(body && typeof body === 'object' && !Array.isArray(body),'Expected a JSON object');
      const now = new Date().toISOString();
      if (path === '/api/assign') {
        const {uwi, crew_id: crew, note=''} = body;
        requireValue(typeof uwi === 'string' && typeof crew === 'string' && typeof note === 'string' && note.length <= 1000,'Invalid assignment');
        requireValue((await wells(secret)).some(w => w.uwi === uwi),'Unknown well',404);
        return json(await mutate(secret, snapshot => {
          requireValue(snapshot.crews.some(c => c.id === crew),'Unknown crew',409);
          requireValue(!snapshot.assignments.some(a => a.uwi === uwi && a.status === 'assigned'),'Well already assigned',409);
          const id = Math.max(0,...snapshot.assignments.map(a => a.id))+1;
          snapshot.assignments.push({id,uwi,crew_id:crew,manager_note:note,assigned_at:now,status:'assigned'});
          return {id};
        }));
      }
      const location = path.match(/^\/api\/crews\/([^/]+)\/location$/);
      if (location) {
        requireValue(inRange(body.lat,-90,90) && inRange(body.lon,-180,180),'Invalid crew location');
        return json(await mutate(secret, snapshot => {
          const crew = snapshot.crews.find(c => c.id === location[1]);
          requireValue(crew,'Unknown crew',404);
          Object.assign(crew,{lat:body.lat,lon:body.lon,updated:now});
          return {ok:true};
        }));
      }
      const complete = path.match(/^\/api\/assignments\/(\d+)\/complete$/);
      requireValue(complete,'Unknown route',404);
      const id=Number(complete[1]), {work_done:work=[],note='',actual_cost:cost=null,hours=null,lat=null,lon=null}=body;
      requireValue(Array.isArray(work) && work.length<=12 && work.every(w=>typeof w==='string' && w.length<=250) && typeof note==='string' && note.length<=3000,'Invalid work description');
      const text=[work.join(' '),note].filter(Boolean).join(' . ').trim();
      requireValue(text.length>=3,'Describe the work done');
      requireValue((cost==null||inRange(cost,0,5000000)) && (hours==null||inRange(hours,0,500)) &&
        (lat==null||inRange(lat,-90,90)) && (lon==null||inRange(lon,-180,180)),'Invalid job details');
      const vector = JSON.stringify(await embed(secret,text));
      const fleet = await wells(secret);
      return json(await mutate(secret, snapshot => {
        const job=snapshot.assignments.find(a=>a.id===id);
        requireValue(job,'Unknown assignment',404);
        requireValue(job.status==='assigned','Already resolved',409);
        Object.assign(job,{status:'resolved',work_done:work.join('; '),crew_note:note,actual_cost:cost,hours,
          resolved_at:now,resolved_lat:lat,resolved_lon:lon});
        snapshot.vectors ||= [];
        snapshot.vectors.push({aid:id,vector});
        return decorate(job,fleet);
      }));
    }
    requireValue(request.method === 'GET','Unsupported method',405);
    const [data, fleet, snapshot] = await Promise.all([facts(secret),wells(secret),state(secret).then(r=>r.value)]);
    if (path === '/api/overview') return json({...data.overview,open_assignments:snapshot.assignments.filter(a=>a.status==='assigned').length,
      resolved_count:snapshot.assignments.filter(a=>a.status==='resolved').length});
    if (path === '/api/pilot') return json({...data.pilot,pilot_mode:pilotMode});
    if (path === '/api/crews') return json(snapshot.crews);
    if (path === '/api/model') {
      const meta=data.model, trees=Object.keys(data).filter(k=>k.startsWith('tree-')).sort().map(k=>data[k]);
      requireValue(trees.length===meta.trees,'Incomplete model',503);
      return json({...meta,trees});
    }
    const from = origin(snapshot,data,q.get('crew_id'));
    const visible = w => !(pilotMode && w.arm==='control') &&
      !snapshot.assignments.some(a=>a.uwi===w.uwi && (a.status==='resolved' || q.get('include_assigned')!=='true'));
    if (path === '/api/model/inputs') return json({origin:from.coords,rows:fleet.map(w=>[w.listing,w.inputs,Number(visible(w))])});
    if (path === '/api/wells') {
      const sort=q.get('sort')||'loss', limit=Number(q.get('limit')||50), min=Number(q.get('min_risk')||0), scenario=q.get('scenario')||'mid';
      requireValue(['loss','risk','closest','furthest'].includes(sort) && ['low','mid'].includes(scenario) && Number.isInteger(limit) && inRange(limit,1,500) && inRange(min,0,1),'Invalid filter');
      const ranked=fleet.filter(w=>visible(w) && w.listing.p_repair>=min).map(w=>({...w.listing,
        distance_km:distance(...from.coords,w.listing.surface_latitude,w.listing.surface_longitude)}));
      ranked.sort((a,b) => {
        if (sort==='risk') return b.p_repair-a.p_repair;
        if (sort==='loss') return b['expected_loss_'+scenario]-a['expected_loss_'+scenario];
        if (a.distance_km==null) return 1;
        if (b.distance_km==null) return -1;
        return sort==='closest' ? a.distance_km-b.distance_km : b.distance_km-a.distance_km;
      });
      return json({sort,distance_from:from.label,wells:ranked.slice(0,limit)});
    }
    if (path.startsWith('/api/wells/')) return json(await detail(secret,decodeURIComponent(path.slice(11)),Number(q.get('k')||5),snapshot));
    if (path === '/api/assignments') {
      const status=q.get('status'), crew=q.get('crew_id');
      requireValue(!status || ['assigned','resolved'].includes(status),'Invalid status');
      return json(snapshot.assignments.filter(a=>(!status||a.status===status)&&(!crew||a.crew_id===crew))
        .sort((a,b)=>b.id-a.id).map(a=>decorate(a,fleet)));
    }
    throw new ApiError(404,'Unknown route');
  } catch (error) {
    if (!(error instanceof ApiError)) console.error('Databricks request failed',error.message);
    return Response.json({detail:error instanceof ApiError ? error.message : 'Could not load the competition application.'},
      {status:error.status||500,headers:{'Cache-Control':'private, no-store'}});
  }
}
