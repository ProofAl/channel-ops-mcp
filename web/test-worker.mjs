import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import worker from './worker.mjs';

const host = 'https://channel-ops.example';
const path = '/demo/mcp';
const revision = '2026-07-28';
const sample = { collected_usd: 200, refunds_usd: 0, delivery_fees_usd: 50, campaign_cost_usd: 125 };
function send(body, headers = {}, route = path) {
  return worker.fetch(new Request(host + route, { method: 'POST', headers: {
    'Content-Type': 'application/json', Accept: 'application/json, text/event-stream', ...headers
  }, body: typeof body === 'string' ? body : JSON.stringify(body) }));
}
function rpc(method, params = {}, id = 1) { return { jsonrpc: '2.0', id, method, params }; }
function runTool(name, args, route) { return send(rpc('tools/call', { name, arguments: args }), {}, route); }

test('public landing and the source and pilot routes are available in both languages', async () => {
  for (const lang of ['en', 'ru']) {
    const res = await worker.fetch(new Request(host + '/?lang=' + lang));
    assert.equal(res.status, 200);
    assert.equal(res.headers.get('content-language'), lang);
    const body = await res.text();
    assert.match(body, new RegExp('<html lang="' + lang + '">'));
    assert.match(body, /github\.com\/ProofAl\/channel-ops-mcp\/issues\/new\?template=pilot.yml/);
    assert.match(body, /\$29/); assert.match(body, /id="result"/);
    assert.doesNotMatch(body, /<(iframe|img)\b|script src="https:/i);
  }
});

test('browser calculator updates locally, including a loss and malformed inputs', async () => {
  const js = await worker.fetch(new Request(host + '/demo.js'));
  const fields = Object.entries(sample).map(([name, valueAsNumber]) => ({ name, valueAsNumber }));
  const handlers = {};
  const form = { querySelectorAll: () => fields, addEventListener: (name, fn) => { handlers[name] = fn; } };
  const nodes = { result: {}, error: { dataset: { message: 'bad amounts' } },
    endpoint: {}, copy: { addEventListener() {} } };
  vm.runInNewContext(await js.text(), { URL, Intl, location: { href: host }, document: {
    documentElement: { lang: 'en' }, querySelector: () => form, getElementById: id => nodes[id] } });
  assert.equal(nodes.result.textContent, '$25.00');
  assert.equal(nodes.endpoint.value, host + '/demo/mcp');
  fields[0].valueAsNumber = 0; handlers.input(); assert.equal(nodes.result.textContent, '-$175.00');
  fields[0].valueAsNumber = NaN; handlers.input(); assert.equal(nodes.error.textContent, 'bad amounts');
});

test('legacy handshake, notifications, and listing on both paths', async () => {
  for (const route of [path, '/mcp']) {
    const request = rpc('initialize', { protocolVersion: '2025-11-25', capabilities: {}, clientInfo: { name: 'test', version: '1' } }, 'a');
    const res = await send(request, {}, route);
    assert.equal(res.status, 200);
    assert.match(res.headers.get('content-type'), /application\/json/);
    assert.equal(res.headers.get('mcp-session-id'), null);
    const data = await res.json();
    assert.equal(data.id, 'a'); assert.equal(data.result.protocolVersion, '2025-11-25');
    assert.equal(data.result.serverInfo.name, 'channel-ops-demo');
    const notice = await send({ jsonrpc: '2.0', method: 'notifications/initialized' }, {}, route);
    assert.equal(notice.status, 202); assert.equal(await notice.text(), '');
    const list = await (await send(rpc('tools/list'), {}, route)).json();
    assert.deepEqual(list.result.tools.map(t => t.name), ['demo_contribution', 'draft_campaign_link']);
    assert.ok(list.result.tools.every(t => t.annotations.readOnlyHint && !t.annotations.openWorldHint));
  }
});
test('modern discovery, mirrored headers and tagged tool results', async () => {
  const meta = { 'io.modelcontextprotocol/protocolVersion': revision, 'io.modelcontextprotocol/clientCapabilities': {} };
  const discover = await send(rpc('server/discover', { _meta: meta }), { 'mcp-protocol-version': revision, 'mcp-method': 'server/discover' });
  const result = (await discover.json()).result;
  assert.equal(result.resultType, 'complete');
  assert.equal(result._meta['io.modelcontextprotocol/serverInfo'].name, 'channel-ops-demo');
  assert.ok(result.supportedVersions.includes(revision)); assert.deepEqual(result.capabilities.tools, {});
  const call = rpc('tools/call', { name: 'demo_contribution', arguments: sample, _meta: meta }, 0);
  const hs = { 'mcp-protocol-version': revision, 'mcp-method': 'tools/call', 'mcp-name': 'demo_contribution' };
  const ans = await (await send(call, hs)).json();
  assert.equal(ans.id, 0); assert.equal(ans.result.resultType, 'complete');
  assert.equal(ans.result.structuredContent.campaign_contribution_usd, 25);
  const conflict = await send(call, { ...hs, 'mcp-name': 'other' });
  assert.equal(conflict.status, 400); assert.equal((await conflict.json()).error.code, -32020);
  const unsupported = await send(rpc('ping'), { 'mcp-protocol-version': '1900-01-01' });
  assert.equal(unsupported.status, 400); assert.equal((await unsupported.json()).error.code, -32022);
});
test('calculator handles cents, losses, zero and invalid or additional inputs', async () => {
  for (const [data, value] of [[sample, 25], [{ ...sample, collected_usd: 0.1, campaign_cost_usd: 0.04, delivery_fees_usd: 0.03 }, 0.03],
    [{ ...sample, refunds_usd: 220 }, -195]]) {
    const r = await (await runTool('demo_contribution', data)).json();
    assert.equal(r.result.structuredContent.campaign_contribution_usd, value);
  }
  for (const bad of [{}, { ...sample, refunds_usd: -1 }, { ...sample, collected_usd: '20' },
    { ...sample, campaign_cost_usd: 0.001 }, { ...sample, collected_usd: null }, { ...sample, user_id: 'x' }]) {
    const r = await (await runTool('demo_contribution', bad)).json();
    assert.equal(r.result.isError, true); assert.equal(r.result.structuredContent, undefined);
  }
});
test('campaign drafts create standard links and reject credentials or non-HTTPS URLs', async () => {
  const base = { landing_url: 'https://example.com/pilot', campaign: 'winter-demo' };
  const draft = (await (await runTool('draft_campaign_link', base)).json()).result.structuredContent;
  assert.equal(draft.action, 'draft_only');
  assert.equal(draft.url, 'https://example.com/pilot?utm_source=youtube&utm_medium=organic_social&utm_campaign=winter-demo');
  assert.equal(new URL(draft.url).searchParams.has('utm_content'), false);
  const placed = await (await runTool('draft_campaign_link', { ...base, content_id: 'release-03-description' })).json();
  assert.equal(new URL(placed.result.structuredContent.url).searchParams.get('utm_content'), 'release-03-description');
  for (const bad of [{ ...base, content_id: 'arbitrary&x=1' }, { ...base, content_id: '' }, { ...base, video_id: 'unknown' },
    { ...base, landing_url: 'javascript:void(0)' }, { ...base, landing_url: 'https://user:pw@example.com/a' },
    { ...base, landing_url: 'https://example.com/?secret=X' }, { ...base, campaign: 'x&campaign=bad' }]) {
    const r = await (await runTool('draft_campaign_link', bad)).json(); assert.equal(r.result.isError, true);
  }
});
test('transport rejects cross-origin browser requests, batches and oversized bodies', async () => {
  assert.equal((await worker.fetch(new Request(host + path))).status, 405);
  assert.equal((await send(rpc('ping'), { Origin: 'https://another.example' })).status, 403);
  assert.equal((await send(rpc('ping'), { Origin: host })).status, 200);
  assert.equal((await send(rpc('ping'), { 'Content-Type': 'text/plain' })).status, 415);
  assert.equal((await send(rpc('ping'), { Accept: 'text/event-stream' })).status, 406);
  for (const message of ['bad-json', [rpc('ping')], rpc('ping', {}, null)]) assert.equal((await send(message)).status, 400);
  assert.equal((await send('x'.repeat(16385))).status, 413);
  assert.equal((await send(rpc('ping'), { 'content-length': '18000' })).status, 413);
  const unknown = await (await send(rpc('missing'))).json();
  assert.equal(unknown.error.code, -32601);
});
