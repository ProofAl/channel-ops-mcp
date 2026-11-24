import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { DatabaseSync } from 'node:sqlite';
import test from 'node:test';
import worker from './worker.mjs';

const origin = 'https://channel-ops-lab.knowingfoxglove4.chatgpt.site';
const schema = readFileSync(new URL('./discovery.sql', import.meta.url), 'utf8');
const page = async (path, env = {}, headers = {}, method = 'GET') =>
  worker.fetch(new Request(origin + path, { headers, method }), env);

function database(t) {
  const conn = new DatabaseSync(':memory:');
  t.after(() => conn.close());
  conn.exec(schema);
  const env = { FEEDBACK: { prepare(sql) {
    const stmt = conn.prepare(sql);
    return {
      async all() { return { results: stmt.all(), success: true }; },
      bind(...args) { return {
        async run() { stmt.run(...args); return { success: true }; },
        async first() { return stmt.get(...args) || null; }
      }; }
    };
  } } };
  return { conn, env };
}

async function formToken(env) {
  const res = await page('/', env);
  return (await res.text()).match(/name="submission" value="([\w-]+)"/)[1];
}
function submit(env, fields, headers = {}, lang = 'en') {
  const body = fields instanceof URLSearchParams ? fields : new URLSearchParams(fields);
  return worker.fetch(new Request(origin + '/feedback?lang=' + lang, {
    method: 'POST', body,
    headers: { 'content-type': 'application/x-www-form-urlencoded', origin, 'sec-fetch-site': 'same-origin', ...headers }
  }), env);
}

test('English and Russian survey is standard HTML, opt-in and discoverable without tracking a visit', async () => {
  for (const lang of ['ru','en']) {
    const res = await page('/?lang=' + lang);
    const html = await res.text();
    assert.match(html, /href="#survey"/);
    assert.ok(html.includes('/releases/download/review-v0.1.0/channel-review.zip'));
    assert.match(html, /name="decision" value="attribution"/);
    assert.match(html, /name="decision" value="none"/);
    assert.match(html, /name="role"/);
    assert.match(html, /name="method"/);
    assert.match(html, new RegExp('action="/feedback\\?lang=' + lang + '"'));
    assert.match(html, /rel="canonical"/);
    assert.match(html, /hreflang="ru"/);
    assert.match(res.headers.get('content-security-policy'), /form-action 'self'/);
    assert.equal(res.headers.get('referrer-policy'), 'same-origin');
    assert.equal(res.headers.get('set-cookie'), null);
  }
  assert.match(await (await page('/robots.txt')).text(), /Sitemap: https:.*\/sitemap.xml/);
  assert.match(await (await page('/sitemap.xml')).text(), /<loc>https:.*\?lang=ru<\/loc>/);
});

test('submission persists only validated options, deduplicates retries and separates receipt from identity', async t => {
  const { conn, env } = database(t);
  const token = await formToken(env);
  const fields = { submission: token, decision: 'attribution', method: 'crm', role: 'agency' };
  const res = await submit(env, fields, { 'CF-Connecting-IP': '192.0.2.1' }, 'ru');
  assert.equal(res.status,303);
  assert.equal(res.headers.get('location'),'/feedback?lang=ru');
  const cookie = res.headers.get('set-cookie').split(';')[0];
  assert.match(res.headers.get('set-cookie'), /HttpOnly; Secure; SameSite=Strict/);
  assert.equal((await submit(env,fields)).status,303);
  assert.equal((await submit(env,{ ...fields, decision: 'topic', submission: await formToken(env) },{ cookie })).status,303);
  const rows = conn.prepare('SELECT * FROM discovery_answers').all();
  assert.equal(rows.length,1);
  assert.equal(rows[0].decision,'attribution');
  assert.equal(rows[0].role,'agency');
  assert.match(rows[0].received_day,/^\d{4}-\d{2}-\d{2}$/);
  assert.match(rows[0].submission_hash,/^[a-f\d]{64}$/);
  assert.deepEqual(Object.keys(rows[0]).sort(), ['decision','method','received_day','role','submission_hash']);
  assert.ok(!JSON.stringify(rows).includes(token));
  const thanks = await page('/feedback?lang=ru',env,{ cookie });
  assert.equal(thanks.status,200);
  assert.match(await thanks.text(), /Ответ сохранён/);
  assert.equal((await page('/feedback',env)).status,303);
  assert.equal((await submit(env,{ decision: 'none', submission: await formToken(env) })).status,303);
  assert.equal(conn.prepare('SELECT method FROM discovery_answers WHERE decision=?').get('none').method,null);
});

test('cross-origin, unknown options and oversized requests never create evidence', async t => {
  const { conn, env } = database(t);
  const base = { submission: await formToken(env), decision: 'topic' };
  for (const values of [{ decision: 'not-allowed' }, { role: 'a@sample.test' }, { extra: 'anything' }, { submission: 'x' }]) {
    assert.equal((await submit(env,{ ...base, ...values })).status,400);
  }
  const repeated = new URLSearchParams(base);
  repeated.append('decision','none');
  assert.equal((await submit(env,repeated)).status,400);
  for (const hs of [{ origin: 'null' }, { origin: 'https://other.example' }, { 'sec-fetch-site': 'cross-site' }]) {
    assert.equal((await submit(env,base,hs)).status,403);
  }
  assert.equal((await submit(env,base,{ 'content-type': 'application/json' })).status,415);
  assert.equal((await submit(env,{ ...base, role: 'x'.repeat(1000) })).status,413);
  assert.equal(conn.prepare('SELECT COUNT(*) AS n FROM discovery_answers').get().n,0);
});

test('readiness and failure paths distinguish inaccessible storage from a saved response', async t => {
  const { conn, env } = database(t);
  assert.equal((await page('/feedback',env,{},'HEAD')).status,200);
  assert.equal(conn.prepare('SELECT COUNT(*) AS n FROM discovery_answers').get().n,0);
  const values = { submission: await formToken({}), decision: 'contribution' };
  for (const unavailable of [{}, { FEEDBACK: { prepare: () => { throw Error('offline'); } } }]) {
    assert.equal((await page('/feedback',unavailable,{},'HEAD')).status,503);
    const res = await submit(unavailable,values,{},'ru');
    assert.equal(res.status,503);
    assert.equal(res.headers.get('set-cookie'),null);
    const html = await res.text();
    assert.match(html,/Сохранить ответ не удалось/);
    assert.match(html,/github.com\/ProofAl\/channel-ops-mcp\/issues\/new/);
  }
});
