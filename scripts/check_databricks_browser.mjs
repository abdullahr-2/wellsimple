import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {readFile} from 'node:fs/promises';
import {timingSafeEqual} from 'node:crypto';
import {createRequire} from 'node:module';
import worker from '../pages/worker.js';

const require = createRequire(import.meta.url);
const {chromium} = require('../artifacts/browser-qa/node_modules/playwright-core');
if (!crypto.subtle.timingSafeEqual) crypto.subtle.timingSafeEqual = timingSafeEqual;
const env = {DEMO_PASSWORD:'local-check', DATABRICKS_CLIENT_SECRET:process.env.WELLSIMPLE_TEST_SECRET,
  ASSETS:{async fetch(request) {
    const path = new URL(request.url).pathname;
    const name = path === '/' ? 'index.html' : path === '/crew' ? 'crew/index.html' : path.slice(1);
    if (!/^(index\.html|crew\/index\.html|static\/[\w.-]+)$/.test(name)) return new Response('Not found',{status:404});
    const bytes = await readFile(new URL('../dist-pages/site/'+name,import.meta.url)).catch(() => null);
    if (!bytes) return new Response('Not found',{status:404});
    const type = name.endsWith('.html') ? 'text/html' : name.endsWith('.js') ? 'text/javascript' :
      name.endsWith('.css') ? 'text/css' : 'image/png';
    return new Response(bytes,{headers:{'Content-Type':type}});
  }}};
const server = createServer(async (req,res) => {
  try {
    const chunks=[];
    for await (const chunk of req) chunks.push(chunk);
    const request = new Request('http://127.0.0.1:18766'+req.url,{
      method:req.method,headers:req.headers,body:chunks.length ? Buffer.concat(chunks) : undefined});
    const response=await worker.fetch(request,env);
    res.writeHead(response.status,Object.fromEntries(response.headers));
    res.end(Buffer.from(await response.arrayBuffer()));
  } catch { res.writeHead(500); res.end('Failed'); }
});
await new Promise(resolve=>server.listen(18766,'127.0.0.1',resolve));
const browser=await chromium.launch({channel:'msedge',headless:true});
try {
  const context=await browser.newContext({httpCredentials:{username:'demo',password:'local-check'}});
  const page=await context.newPage();
  const errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:18766/',{waitUntil:'domcontentloaded'});
  await page.waitForSelector('#kpis .kpi',{timeout:60000});
  await page.getByRole('tab',{name:'At-risk wells'}).click();
  await page.getByRole('button',{name:'Score producing wells'}).click();
  await page.waitForFunction(()=>document.querySelector('#modelResult').textContent.includes('wells scored'),null,{timeout:60000});
  assert.match(await page.locator('#modelResult').innerText(),/1,336 wells scored/);
  await page.locator('#wellsTable tr.clickable').first().click();
  await page.waitForSelector('#detail .note',{timeout:30000});
  await page.getByRole('tab',{name:'A/B pilot'}).click();
  assert.match(await page.locator('#pilot').innerText(),/System arm \(186 wells\)/);
  await page.getByRole('link',{name:'Crew portal'}).click();
  await page.waitForSelector('#crew option',{state:'attached',timeout:30000});
  assert.deepEqual(errors,[]);
  console.log('Browser verified dashboard, real scoring, well details, pilot and crew portal against Databricks.');
} finally {
  await browser.close();
  await new Promise(resolve=>server.close(resolve));
}
