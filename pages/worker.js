import {databricksApi} from './databricks_api.js';

// The same two portals as FastAPI, backed by Databricks when configured.
const jsonHeaders = {'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'private, no-store'};
const json = value => Response.json(value, {headers: jsonHeaders});
const jsonText = text => new Response(text, {headers: jsonHeaders});
const rows = async statement => (await statement.all()).results;
const fact = async (db, key) => JSON.parse(await db.prepare('SELECT value FROM facts WHERE key=?').bind(key).first('value'));

class RequestError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}
function valid(condition, message, status = 422) {
  if (!condition) throw new RequestError(status, message);
}
function numberIn(value, min, max) {
  return typeof value === 'number' && Number.isFinite(value) && value >= min && value <= max;
}
async function origin(db, crew) {
  const located = crew && await db.prepare('SELECT lat,lon,name FROM crews WHERE id=? AND lat IS NOT NULL').bind(crew).first();
  if (located) return {coords: [located.lat, located.lon], label: located.name};
  return {coords: await fact(db, 'origin'), label: 'fleet centre'};
}

async function listWells(db, q, pilotMode) {
  const sort = q.get('sort') || 'loss', limit = Number(q.get('limit') || 50);
  const min = Number(q.get('min_risk') || 0);
  valid(numberIn(min, 0, 1) && Number.isInteger(limit) && numberIn(limit, 1, 500), 'Invalid risk or limit');
  const order = {risk: "json_extract(listing,'$.p_repair') DESC", loss: "json_extract(listing,'$.expected_loss_mid') DESC",
    closest: 'distance IS NULL, distance ASC', furthest: 'distance IS NULL, distance DESC'};
  valid(Object.hasOwn(order, sort), 'Unknown priority');
  const from = await origin(db, q.get('crew_id'));
  // D1 evaluates distance and ordering before applying the requested limit.
  const sql = `WITH points AS (
    SELECT w.listing, json_extract(listing,'$.surface_latitude') AS lat, json_extract(listing,'$.surface_longitude') AS lon
    FROM wells w WHERE json_extract(listing,'$.p_repair') >= ? AND (? = 0 OR coalesce(arm,'') != 'control')
    AND NOT EXISTS (SELECT 1 FROM assignments a WHERE a.uwi=w.uwi AND (a.status='resolved' OR ?=0)))
    SELECT listing, 12742.0176 * asin(sqrt(min(1, pow(sin(radians(lat-?)/2),2)
      + cos(radians(lat))*cos(radians(?))*pow(sin(radians(lon-?)/2),2)))) AS distance
    FROM points ORDER BY ${order[sort]} LIMIT ?`;
  const [lat, lon] = from.coords;
  const result = await rows(db.prepare(sql).bind(min, Number(pilotMode), Number(q.get('include_assigned') === 'true'), lat, lat, lon, limit));
  return json({sort, distance_from: from.label, wells: result.map(r => ({...JSON.parse(r.listing), distance_km: r.distance}))});
}

function quantile(sorted, fraction) {
  if (!sorted.length) return null;
  const pos = (sorted.length - 1) * fraction, lo = Math.floor(pos);
  return sorted[lo] + (sorted[Math.ceil(pos)] - sorted[lo]) * (pos - lo);
}
function summarize(neighbors) {
  const values = key => neighbors.map(p => p[key]).filter(Number.isFinite).sort((a,b) => a-b);
  const life = values('life_days'), cost = quantile(values('cost'), .5), median = quantile(life, .5);
  return {n: neighbors.length, median_life_days: median, life_p25: quantile(life,.25), life_p75: quantile(life,.75),
    median_cost: cost, cost_per_day_of_life: median > 0 && cost != null ? cost / median : null};
}
async function embed(db, text) {
  const counts = new Map();
  for (const word of text.toLowerCase().match(/[\p{L}\p{N}_]{2,}/gu) || []) counts.set(word, (counts.get(word) || 0) + 1);
  const words = [...counts.keys()], result = [];
  for (let i = 0; i < words.length; i += 80) {
    const chunk = words.slice(i, i+80);
    const sql = 'SELECT word,projection FROM terms WHERE word IN (' + chunk.map(() => '?').join(',') + ')';
    for (const term of await rows(db.prepare(sql).bind(...chunk))) {
      const tf = 1 + Math.log(counts.get(term.word));
      JSON.parse(term.projection).forEach((v,j) => { result[j] = (result[j] || 0) + tf*v; });
    }
  }
  const norm = Math.hypot(...result);
  return norm ? result.map(v => v/norm) : result;
}
async function wellDetail(db, uwi, k) {
  valid(Number.isInteger(k) && numberIn(k,1,15), 'Invalid neighbor count');
  const raw = await db.prepare('SELECT detail FROM wells WHERE uwi=?').bind(uwi).first('detail');
  valid(raw, 'Unknown well', 404);
  const {vector, ...detail} = JSON.parse(raw);
  if (vector.length) {
    const added = await rows(db.prepare(`SELECT v.vector,a.crew_note,a.work_done,a.actual_cost,a.resolved_at
      FROM note_vectors v JOIN assignments a ON v.aid=a.id WHERE a.uwi!=?`).bind(uwi));
    for (const r of added) {
      const v = JSON.parse(r.vector), similarity = v.reduce((sum,x,j) => sum+x*vector[j], 0);
      detail.precedents.push({date: r.resolved_at.slice(0,10), text: [r.work_done,r.crew_note].filter(Boolean).join(' . ').slice(0,500),
        cost: r.actual_cost, life_days: null, similarity});
    }
    detail.precedents.sort((a,b) => b.similarity-a.similarity);
  }
  detail.summary = detail.query ? summarize(detail.precedents.slice(0,10)) : null;
  detail.precedents = detail.precedents.slice(0,k).map(p => ({...p, similarity: Number(p.similarity.toFixed(3))}));
  return json(detail);
}

async function writeApi(db, path, body) {
  valid(body && typeof body === 'object' && !Array.isArray(body), 'Expected a JSON object');
  const now = new Date().toISOString();
  if (path === '/api/assign') {
    const {uwi, crew_id: crew, note = ''} = body;
    valid(typeof uwi === 'string' && typeof crew === 'string' && typeof note === 'string' && note.length <= 1000, 'Invalid assignment');
    valid(await db.prepare('SELECT 1 FROM wells WHERE uwi=?').bind(uwi).first(), 'Unknown well',404);
    valid(await db.prepare('SELECT 1 FROM crews WHERE id=?').bind(crew).first(), 'Unknown crew',409);
    const r = await db.prepare(`INSERT OR IGNORE INTO assignments(uwi,crew_id,manager_note,assigned_at) VALUES (?,?,?,?)`).bind(uwi,crew,note,now).run();
    valid(r.meta.changes, 'Well already assigned',409);
    return json({id:r.meta.last_row_id});
  }
  const location = path.match(/^\/api\/crews\/([^/]+)\/location$/);
  if (location) {
    valid(numberIn(body.lat,-90,90) && numberIn(body.lon,-180,180), 'Invalid crew location');
    const r = await db.prepare('UPDATE crews SET lat=?,lon=?,updated=? WHERE id=?').bind(body.lat,body.lon,now,location[1]).run();
    valid(r.meta.changes,'Unknown crew',404);
    return json({ok:true});
  }
  const completion = path.match(/^\/api\/assignments\/(\d+)\/complete$/);
  valid(completion, 'Unknown route',404);
  const id = Number(completion[1]), {work_done: work = [], note = '', actual_cost: cost = null,
    hours = null, lat = null, lon = null} = body;
  valid(Array.isArray(work) && work.length <= 12 && work.every(w => typeof w === 'string' && w.length <= 250) &&
    typeof note === 'string' && note.length <= 3000, 'Invalid work description');
  const text = [work.join(' '), note].filter(Boolean).join(' . ').trim();
  valid(text.length >= 3, 'Describe the work done');
  valid((cost == null || numberIn(cost,0,5000000)) && (hours == null || numberIn(hours,0,500)) &&
    (lat == null || numberIn(lat,-90,90)) && (lon == null || numberIn(lon,-180,180)), 'Invalid job details');
  const assignment = await db.prepare('SELECT status FROM assignments WHERE id=?').bind(id).first();
  valid(assignment, 'Unknown assignment',404);
  valid(assignment.status === 'assigned','Already resolved',409);
  const vector = await embed(db,text);
  const [,update] = await db.batch([
    db.prepare("INSERT INTO note_vectors SELECT id,? FROM assignments WHERE id=? AND status='assigned'").bind(JSON.stringify(vector),id),
    db.prepare(`UPDATE assignments SET status='resolved',work_done=?,crew_note=?,actual_cost=?,hours=?,resolved_at=?,
      resolved_lat=?,resolved_lon=? WHERE id=? AND status='assigned'`).bind(work.join('; '),note,cost,hours,now,lat,lon,id)
  ]);
  valid(update.meta.changes,'Already resolved',409);
  return json(await db.prepare('SELECT * FROM assignments WHERE id=?').bind(id).first());
}

async function apiRequest(request, url, env) {
  const db = env.DB, path = url.pathname, q = url.searchParams, pilotMode = env.PILOT_MODE === '1';
  if (request.method === 'POST') {
    valid(!request.headers.get('Origin') || request.headers.get('Origin') === url.origin, 'Invalid origin',403);
    valid(request.headers.get('Content-Type')?.startsWith('application/json'), 'Expected JSON',415);
    const raw = await request.text();
    valid(raw.length <= 32000,'Request too large',413);
    let body;
    try { body = JSON.parse(raw); } catch { throw new RequestError(400,'Invalid JSON'); }
    return writeApi(db,path,body);
  }
  valid(request.method === 'GET','Unsupported method',405);
  if (path === '/api/overview') {
    const overview = await fact(db,'overview');
    const counts = await db.prepare("SELECT count(CASE WHEN status='assigned' THEN 1 END) AS open_assignments,count(CASE WHEN status='resolved' THEN 1 END) AS resolved_count FROM assignments").first();
    return json({...overview,...counts});
  }
  if (path === '/api/pilot') return json({...await fact(db,'pilot'),pilot_mode:pilotMode});
  if (path === '/api/crews') return json(await rows(db.prepare('SELECT * FROM crews ORDER BY id')));
  if (path === '/api/wells') return listWells(db,q,pilotMode);
  if (path.startsWith('/api/wells/')) return wellDetail(db,decodeURIComponent(path.slice(11)), Number(q.get('k') || 5));
  if (path === '/api/model') {
    const meta = await fact(db,'model');
    const trees = await rows(db.prepare("SELECT value FROM facts WHERE key GLOB 'tree-*' ORDER BY key"));
    valid(trees.length === meta.trees,'Incomplete model',503);
    return jsonText('{"base":'+meta.base+',"features":'+JSON.stringify(meta.features)+',"trees":['+trees.map(t=>t.value).join(',')+']}');
  }
  if (path === '/api/model/inputs') {
    const from = await origin(db,q.get('crew_id'));
    const records = await rows(db.prepare(`SELECT listing,inputs,
      ((?=0 OR coalesce(arm,'')!='control') AND NOT EXISTS(SELECT 1 FROM assignments WHERE assignments.uwi=wells.uwi)) AS visible FROM wells`).bind(Number(pilotMode)));
    return jsonText('{"origin":'+JSON.stringify(from.coords)+',"rows":['+records.map(r=>'['+r.listing+','+r.inputs+','+r.visible+']').join(',')+']}');
  }
  if (path === '/api/assignments') {
    const status = q.get('status'), crew = q.get('crew_id');
    valid(!status || ['assigned','resolved'].includes(status), 'Invalid status');
    const jobs = await rows(db.prepare(`SELECT a.*,w.listing FROM assignments a JOIN wells w ON w.uwi=a.uwi
      WHERE (? IS NULL OR a.status=?) AND (? IS NULL OR a.crew_id=?) ORDER BY id DESC`).bind(status,status,crew,crew));
    return json(jobs.map(({listing,...j}) => {
      const w = JSON.parse(listing);
      return {...w,...j,field:w.field_operating_area,lat:w.surface_latitude,lon:w.surface_longitude};
    }));
  }
  throw new RequestError(404,'Unknown route');
}

export default {
  async fetch(request, env) {
    if (!env.DEMO_PASSWORD) return new Response('Competition access is not configured.',{status:503,headers:{'Cache-Control':'no-store'}});
    const expected = 'Basic '+btoa('demo:'+env.DEMO_PASSWORD);
    const header = request.headers.get('Authorization') || '';
    const encoder = new TextEncoder();
    if (header.length !== expected.length ||
        !crypto.subtle.timingSafeEqual(encoder.encode(header),encoder.encode(expected))) {
      return new Response('Sign in with your competition demo credentials.', {status:401,headers:{
        'WWW-Authenticate':'Basic realm="WellSimple competition demo"', 'Cache-Control':'private, no-store'}});
    }
    const url = new URL(request.url);
    try {
      if (url.pathname.startsWith('/api/')) {
        if (env.DATABRICKS_CLIENT_SECRET) return await databricksApi(request,env);
        if (env.D1_TEST_ONLY) return await apiRequest(request,url,env);
        return Response.json({detail:'Databricks is not configured.'}, {status:503,headers:{'Cache-Control':'private, no-store'}});
      }
      // Keep credentials out of asset subrequests and authenticated responses out of shared caches.
      const asset = await env.ASSETS.fetch(new Request(request.url, {method:request.method}));
      const result = new Response(asset.body,asset);
      result.headers.set('Cache-Control','private, no-store');
      return result;
    } catch (e) {
      if (!(e instanceof RequestError)) console.error('WellSimple request failed', e.name);
      return Response.json({detail: e instanceof RequestError ? e.message : 'Could not load the competition application.'},
        {status:e.status || 500,headers:jsonHeaders});
    }
  }
};
