/** Stateless public MCP tools and an opt-in first-party discovery survey. */
const repo = 'https://github.com/ProofAl/channel-ops-mcp';
const pilot = repo + '/issues/new?template=pilot.yml';
const modern = '2026-07-28';
const legacy = ['2025-11-25', '2025-06-18', '2025-03-26'];
const versions = [modern, ...legacy];
const info = { name: 'channel-ops-demo', title: 'Channel Ops public demo', version: '0.1.0' };
const caps = { tools: {} };
const scope = 'Public examples only. Use fictional numbers and public URLs. No channel access, publishing or persistence.';
const versionKey = 'io.modelcontextprotocol/protocolVersion';
const infoKey = 'io.modelcontextprotocol/serverInfo';
const limit = 16384;
const isObject = v => v !== null && typeof v === 'object' && !Array.isArray(v);

const amounts = ['collected_usd', 'refunds_usd', 'delivery_fees_usd', 'campaign_cost_usd'];
const schema = (properties, required = Object.keys(properties)) => ({ type: 'object', properties, required, additionalProperties: false });
const properties = Object.fromEntries(amounts.map(name =>
  [name, { type: 'number', minimum: 0, maximum: 1000000000, multipleOf: 0.01 }]));
properties.campaign_cost_usd.description = 'Production, promotion, tools and loaded team time in USD.';
const annotations = { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false };
const tools = [
  { name: 'demo_contribution', title: 'Calculate example campaign contribution',
    description: 'Subtract refunds, fulfillment, fees and campaign costs from example cash receipts. Use illustrative USD values only.',
    inputSchema: schema(properties), annotations },
  { name: 'draft_campaign_link', title: 'Draft a campaign link',
    description: 'Format a public HTTPS landing page with YouTube organic UTM tags. The URL is returned as text and is never visited.',
    inputSchema: schema({ landing_url: { type: 'string', maxLength: 1024, format: 'uri' },
      campaign: { type: 'string', pattern: '^[a-z0-9][a-z0-9_-]{0,63}$' },
      content_id: { type: 'string', pattern: '^[a-z0-9][a-z0-9_-]{0,63}$', description: 'Optional known placement slug. Omit for shared profile links.' }
    }, ['landing_url', 'campaign']), annotations }
];

// This pure function is also served to the calculator, so the demo runs inside the browser.
function calculateContribution(input) {
  const fields = ['collected_usd', 'refunds_usd', 'delivery_fees_usd', 'campaign_cost_usd'];
  const cents = fields.map(field => {
    const amount = input[field];
    const rounded = Math.round(amount * 100);
    if (typeof amount !== 'number' || !Number.isFinite(amount) || amount < 0 ||
        amount > 1000000000 || rounded / 100 !== amount) {
      throw new Error('Use nonnegative USD amounts up to one billion, with at most two decimal places.');
    }
    return rounded;
  });
  const [collected, refunds, delivery, campaign] = cents;
  return { currency: 'USD', basis: 'illustrative', net_receipts_usd: (collected - refunds) / 100,
    campaign_contribution_usd: (collected - refunds - delivery - campaign) / 100 };
}

function draftLink(input) {
  if (typeof input.landing_url !== 'string' || input.landing_url.length > 1024)
    throw new Error('Enter a public HTTPS page URL (up to 1024 characters).');
  if (typeof input.campaign !== 'string' || !/^[a-z0-9][a-z0-9_-]{0,63}$/.test(input.campaign))
    throw new Error('Use a campaign slug with 1–64 lowercase letters, digits, underscores or hyphens.');
  if ('content_id' in input && (typeof input.content_id !== 'string' || !/^[a-z0-9][a-z0-9_-]{0,63}$/.test(input.content_id)))
    throw new Error('Use a placement slug with 1–64 lowercase letters, digits, underscores or hyphens, or omit content_id.');
  let url;
  try { url = new URL(input.landing_url); } catch { throw new Error('Enter an absolute HTTPS page URL.'); }
  if (url.protocol !== 'https:' || !url.hostname.includes('.') || url.username || url.password ||
      url.search || url.hash || url.port || !/^https:\/\//i.test(input.landing_url))
    throw new Error('Use a clean HTTPS page URL with no query, fragment, port or credentials.');
  const tags = new URLSearchParams({ utm_source: 'youtube', utm_medium: 'organic_social', utm_campaign: input.campaign });
  if (input.content_id) tags.set('utm_content', input.content_id);
  url.search = tags;
  return { url: url.href, action: 'draft_only' };
}

function response(body, status, type, extra = {}) {
  return new Response(body, { status, headers: { 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
    'Referrer-Policy': 'no-referrer', ...(type && { 'Content-Type': type }), ...extra } });
}
const json = (data, status = 200) => response(JSON.stringify(data), status, 'application/json; charset=utf-8');
const rpcError = (id, code, message, status = 200, data) =>
  json({ jsonrpc: '2.0', id, error: { code, message, ...(data && { data }) } }, status);

async function readText(req, max) {
  if (Number(req.headers.get('content-length')) > max) throw new RangeError();
  if (!req.body) throw new SyntaxError();
  const reader = req.body.getReader();
  const buffer = new Uint8Array(max);
  let length = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      if (length + value.length > max) { await reader.cancel(); throw new RangeError(); }
      buffer.set(value, length);
      length += value.length;
    }
  } finally { reader.releaseLock(); }
  return new TextDecoder('utf-8', { fatal: true }).decode(buffer.subarray(0, length));
}
function unpackName(header) {
  if (!header?.startsWith('=?base64?') || !header.endsWith('?=')) return header;
  try { return atob(header.slice(9, -2)); } catch { return null; }
}

async function handleMcp(req) {
  const origin = req.headers.get('origin');
  if (origin && ![new URL(req.url).origin, 'https://chatgpt.com', 'https://claude.ai'].includes(origin))
    return rpcError(null, -32600, 'Origin is not permitted.', 403);
  if (req.method !== 'POST') return response(null, 405, null, { Allow: 'POST' });
  if (req.headers.get('content-type')?.split(';')[0].trim().toLowerCase() !== 'application/json')
    return rpcError(null, -32600, 'Send application/json.', 415);
  const accept = (req.headers.get('accept') || '*/*').toLowerCase();
  if (!accept.includes('*/*') && !accept.includes('application/json'))
    return rpcError(null, -32600, 'The server returns application/json.', 406);
  let msg;
  try { msg = JSON.parse(await readText(req, limit)); } catch (error) {
    return error instanceof RangeError ? rpcError(null, -32600, 'Request exceeds 16 KiB.', 413)
      : rpcError(null, -32700, 'Expected a single UTF-8 JSON message.', 400);
  }
  if (!isObject(msg) || msg.jsonrpc !== '2.0' || typeof msg.method !== 'string' ||
      ('id' in msg && typeof msg.id !== 'string' && !Number.isSafeInteger(msg.id)) ||
      ('params' in msg && !isObject(msg.params))) return rpcError(null, -32600, 'Invalid JSON-RPC message.', 400);
  const { id, method, params = {} } = msg;
  const headerVersion = req.headers.get('mcp-protocol-version');
  const bodyVersion = params._meta?.[versionKey];
  const isModern = bodyVersion === modern || headerVersion === modern;
  if ((headerVersion && !versions.includes(headerVersion)) || (bodyVersion && !versions.includes(bodyVersion)))
    return rpcError(id ?? null, -32022, 'Unsupported protocol version.', 400, { supported: versions, requested: bodyVersion || headerVersion });
  if (isModern && (headerVersion !== bodyVersion || req.headers.get('mcp-method') !== method ||
      (method === 'tools/call' && unpackName(req.headers.get('mcp-name')) !== params.name)))
    return rpcError(id ?? null, -32020, 'MCP headers and body metadata must match.', 400);
  if (id === undefined) {
    if (method.startsWith('notifications/')) return response(null, 202);
    return rpcError(null, -32600, 'Requests require an ID.', 400);
  }
  const success = result => json({ jsonrpc: '2.0', id, result:
    (isModern || method === 'server/discover') ? { resultType: 'complete', _meta: { [infoKey]: info }, ...result } : result });
  switch (method) {
    case 'server/discover': return success({ supportedVersions: versions, capabilities: caps, instructions: scope });
    case 'initialize':
      if (typeof params.protocolVersion !== 'string' || !isObject(params.capabilities) ||
          !isObject(params.clientInfo) || typeof params.clientInfo.name !== 'string' || typeof params.clientInfo.version !== 'string')
        return rpcError(id, -32602, 'Supply protocolVersion, capabilities and clientInfo.');
      return success({ protocolVersion: legacy.includes(params.protocolVersion) ? params.protocolVersion : legacy[0],
        capabilities: caps, serverInfo: info, instructions: scope });
    case 'ping': return success({});
    case 'tools/list': return success({ tools });
    case 'tools/call': {
      const tool = tools.find(t => t.name === params.name);
      if (!tool) return rpcError(id, -32602, 'Unknown tool. Use tools/list.');
      const args = params.arguments;
      try {
        if (!isObject(args) || !Object.keys(args).every(key => Object.hasOwn(tool.inputSchema.properties, key)) ||
            !tool.inputSchema.required.every(key => Object.hasOwn(args, key))) throw new Error('Supply exactly the fields in the tool schema.');
        const output = tool.name === 'demo_contribution' ? calculateContribution(args) : draftLink(args);
        return success({ content: [{ type: 'text', text: JSON.stringify(output) }], structuredContent: output, isError: false });
      } catch (error) { return success({ content: [{ type: 'text', text: error.message }], isError: true }); }
    }
    default: return rpcError(id, -32601, 'Method not found.', isModern ? 404 : 200);
  }
}

const copy = {
  en: {
    lang: 'en', other: 'Русский', href: '/?lang=ru', nav: 'Pilot program', title: 'Did this video pay for itself?',
    lead: 'Channel Ops connects a YouTube release to a campaign, then subtracts production, promotion and delivery costs from the cash that came in.',
    heading: 'Try a campaign', hint: 'Change the fictional figures below. The calculator runs in your browser.',
    inputs: ['Cash collected', 'Refunds', 'Delivery and payment fees', 'Campaign spend, including labor'],
    unit: 'USD', output: 'Campaign contribution', sample: 'Illustrative figures in USD',
    calcError: 'Enter valid USD amounts with up to two decimal places.', script: 'Enable JavaScript to change the example.',
    ai: 'Try it in your assistant', endpoint: 'Public MCP endpoint', how: 'Use this URL as a remote MCP server in ChatGPT or Claude. The demo accepts example numbers and drafts a campaign link. Use fictional data here. For channel access, install your own copy from GitHub.',
    prompt: 'Calculate contribution on $200 received, $0 refunds, $50 delivery and fees, and $125 campaign spend.',
    pilot: 'Run a one-channel pilot', offer: 'We are testing $29 per channel per month. The pilot follows one release from a campaign link to confirmed sales and production costs.',
    evidence: 'A public GitHub issue records interest. Only a settled payment counts toward the paid-pilot test. Share a short use case and keep customer details and receipts private.',
    cta: 'Request a pilot', source: 'Get the source', copy: 'Copy URL', copied: 'Copied', ask: 'Example prompt', shorts: 'For Shorts, direct viewers to a channel profile link. A shared link identifies the channel only.'
  },
  ru: {
    lang: 'ru', other: 'English', href: '/?lang=en', nav: 'Пилот', title: 'Окупился ли этот ролик?',
    lead: 'Channel Ops связывает выпуск на YouTube с кампанией и считает, сколько денег осталось после расходов на производство, продвижение и выполнение заказов.',
    heading: 'Посчитайте результат', hint: 'Измените цифры в примере. Расчёт выполняется в вашем браузере.',
    inputs: ['Получено от клиентов', 'Возвраты', 'Выполнение заказов и комиссии', 'Расходы на кампанию с учётом труда'],
    unit: 'USD', output: 'Вклад кампании', sample: 'Пример расчёта в долларах США',
    calcError: 'Введите суммы в долларах с точностью до цента.', script: 'Чтобы менять суммы, включите JavaScript.',
    ai: 'Попробуйте в своём ассистенте', endpoint: 'Публичный адрес MCP', how: 'Добавьте этот адрес как удалённый MCP-сервер в ChatGPT или Claude. В демо можно посчитать результат и составить ссылку для кампании. Используйте вымышленные данные. Доступ к своему каналу настраивается в отдельной установке из GitHub.',
    prompt: 'Посчитай вклад кампании. Поступления $200, возвраты $0, выполнение заказов и комиссии $50, расходы на кампанию $125.',
    pilot: 'Пилот для одного канала', offer: 'Проверяем цену $29 в месяц за канал. В пилоте отслеживаем один выпуск от ссылки кампании до подтверждённых продаж и расходов на производство.',
    evidence: 'Заявка в GitHub публична и фиксирует интерес. Оплату пилота учитываем после поступления денег. В заявке достаточно описать задачу. Данные клиентов и платёжные документы оставьте у себя.',
    cta: 'Подать заявку', source: 'Исходный код', copy: 'Скопировать URL', copied: 'Скопировано', ask: 'Пример запроса', shorts: 'В Shorts направляйте зрителей по ссылке в профиле. Общая ссылка позволяет определить только канал.'
  }
};

const canonical = 'https://channel-ops-lab.knowingfoxglove4.chatgpt.site';
const feedbackCookie = '__Host-channel-ops-feedback';
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const text = {
  en: {
    title: 'YouTube campaign costs and sales | Channel Ops',
    workflow: 'Download the review for your assistant', guide: 'Use it in a conversation', nav: 'Creator survey', heading: 'What would help with your next release?',
    intro: 'Think of the last video your team published. Which decision was hardest?',
    decisions: { attribution: 'Trace a lead who watched, then called or searched for us', topic: 'Choose the next topic worth producing', contribution: 'Check whether sales covered the cost of a video', none: 'Another decision, or none of these' },
    methods: { spreadsheet: 'Spreadsheet', analytics: 'YouTube or web analytics', crm: 'CRM or sales reports', manual: 'Ask customers directly', no_process: 'No regular process' },
    roles: { creator: 'Creator or educator', marketing: 'In-house marketing team', agency: 'Agency', other: 'Other' },
    method: 'How do you handle this today?', role: 'Who do you work with?', optional: 'Optional',
    send: 'Send my answer', privacy: 'No login. The survey stores your choices, the UTC day and a random receipt hash. A receipt cookie helps avoid repeat answers in this browser. Our survey does not store names, contact details or IP addresses.',
    saved: 'Your answer has been recorded', savedBody: 'Thank you. Your response helps us decide which workflow to build next.',
    unavailable: 'The survey could not save a response', unavailableBody: 'Please try again later, or describe your workflow using the public GitHub pilot form.',
    invalid: 'Check the survey choices', invalidBody: 'Return to the survey and select one of the available decisions.',
    home: 'Back to Channel Ops', retry: 'Open the survey', pilot: 'Open the public pilot form'
  },
  ru: {
    title: 'Расходы и продажи YouTube-канала | Channel Ops',
    workflow: 'Скачать разбор для чата', guide: 'Как использовать в обычном чате', nav: 'Опрос для авторов', heading: 'Что помогло бы подготовить следующий выпуск?',
    intro: 'Вспомните последний ролик вашей команды. Что было труднее всего решить?',
    decisions: { attribution: 'Понять, какой ролик привёл клиента, который потом позвонил или нашёл нас через поиск', topic: 'Выбрать тему, на которую стоит потратить время съёмки', contribution: 'Посчитать, покрыли ли продажи затраты на выпуск', none: 'Другая задача или ничего из перечисленного' },
    methods: { spreadsheet: 'Таблица', analytics: 'YouTube или веб-аналитика', crm: 'CRM или отчёты по продажам', manual: 'Спрашиваем клиентов', no_process: 'Пока делаем от случая к случаю' },
    roles: { creator: 'Автор канала или преподаватель', marketing: 'Отдел маркетинга', agency: 'Агентство', other: 'Другое' },
    method: 'Как решаете это сейчас?', role: 'В какой команде вы работаете?', optional: 'Необязательно',
    send: 'Отправить ответ', privacy: 'Можно ответить без регистрации. Сохраним выбранные варианты, день по UTC и хеш случайной квитанции. Файл cookie с квитанцией помогает учесть ответ из этого браузера один раз. В базе опроса нет имён, контактов и IP-адресов.',
    saved: 'Ответ сохранён', savedBody: 'Спасибо. Ваш ответ поможет выбрать задачу для следующей версии.',
    unavailable: 'Сохранить ответ не удалось', unavailableBody: 'Попробуйте позже или опишите задачу в публичной форме пилота на GitHub.',
    invalid: 'Проверьте выбранные варианты', invalidBody: 'Вернитесь к опросу и выберите задачу из списка.',
    home: 'На главную Channel Ops', retry: 'Перейти к опросу', pilot: 'Открыть публичную форму пилота'
  }
};

function survey(lang) {
  const t = text[lang];
  function optional(name, title, choices) {
    return `<label class="select-label">${title}<select name="${name}"><option value="">${t.optional}</option>${Object.entries(choices).map(([k,v]) => `<option value="${k}">${v}</option>`).join('')}</select></label>`;
  }
  // A new form token is included in the HTML only. Nothing is persisted until submission.
  const submission = crypto.randomUUID();
  return `<section id="survey" class="lower"><div><h2>${t.heading}</h2><p>${t.privacy}</p></div>
<form class="survey" method="post" action="/feedback?lang=${lang}"><input type="hidden" name="submission" value="${submission}">
<fieldset><legend>${t.intro}</legend>${Object.entries(t.decisions).map(([k,v]) => `<label class="choice"><input type="radio" name="decision" value="${k}" required><span>${v}</span></label>`).join('')}</fieldset>
${optional('method',t.method,t.methods)}${optional('role',t.role,t.roles)}
<button type="submit">${t.send}</button></form></section>`;
}

function receipt(req) {
  const value = (req.headers.get('Cookie') || '').split(';').map(s => s.trim())
    .find(s => s.startsWith(feedbackCookie + '='))?.slice(feedbackCookie.length + 1);
  return uuid.test(value || '') ? value : null;
}

async function receiptHash(token) {
  const bytes = await crypto.subtle.digest('SHA-256', new TextEncoder().encode('creator-survey-v1:' + token));
  return Array.from(new Uint8Array(bytes), b => b.toString(16).padStart(2,'0')).join('');
}

function notice(lang, status, kind) {
  const t = text[lang];
  return response(`<!DOCTYPE html><html lang="${lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex"><title>${t[kind]} | Channel Ops</title><style>${style}</style></head><body><main class="notice"><h1>${t[kind]}</h1><p>${t[kind+'Body']}</p><p><a href="/?lang=${lang}#survey">${kind === 'saved' ? t.home : t.retry}</a> · <a href="${pilot}">${t.pilot}</a></p></main></body></html>`, status, 'text/html; charset=utf-8', { 'Content-Language': lang, 'X-Robots-Tag': 'noindex', 'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'" });
}

function redirect(path, extra = {}) { return response(null, 303, null, { Location: path, ...extra }); }

async function handleFeedback(req, db, lang) {
  const location = new URL(req.url);
  if (!['GET','HEAD','POST'].includes(req.method)) return response(null,405,null,{ Allow: 'GET, HEAD, POST' });
  // No DB writes or votes are created by a status check.
  if (req.method === 'HEAD') {
    try {
      if (!db) throw new Error();
      await db.prepare('SELECT 1 FROM discovery_answers LIMIT 0').all();
      return response(null,200,null,{ 'X-Robots-Tag': 'noindex' });
    } catch { return response(null,503,null); }
  }
  const existing = receipt(req);
  if (req.method === 'GET') {
    if (!existing) return redirect('/?lang=' + lang + '#survey');
    try {
      if (!db) throw new Error();
      const found = await db.prepare('SELECT 1 AS saved FROM discovery_answers WHERE submission_hash = ?')
        .bind(await receiptHash(existing)).first();
      return found ? notice(lang,200,'saved') : redirect('/?lang=' + lang + '#survey');
    } catch { return notice(lang,503,'unavailable'); }
  }
  const site = req.headers.get('sec-fetch-site');
  if (req.headers.get('origin') !== location.origin || (site && site !== 'same-origin'))
    return notice(lang,403,'invalid');
  if (req.headers.get('content-type')?.split(';')[0].trim() !== 'application/x-www-form-urlencoded')
    return notice(lang,415,'invalid');
  let form;
  try { form = new URLSearchParams(await readText(req, 768)); } catch (error) {
    return notice(lang, error instanceof RangeError ? 413 : 400, 'invalid');
  }
  const t = text.en;
  if ([...form.keys()].some(k => !['submission','decision','method','role'].includes(k) || form.getAll(k).length !== 1) ||
      !uuid.test(form.get('submission') || '') || !Object.hasOwn(t.decisions,form.get('decision')) ||
      (form.get('role') && !Object.hasOwn(t.roles,form.get('role'))) ||
      (form.get('method') && !Object.hasOwn(t.methods,form.get('method')))) return notice(lang,400,'invalid');
  const token = existing || form.get('submission');
  try {
    if (!db) throw new Error();
    const saved = await db.prepare('INSERT INTO discovery_answers (submission_hash, decision, method, role) VALUES (?, ?, ?, ?) ON CONFLICT(submission_hash) DO NOTHING')
      .bind(await receiptHash(token), form.get('decision'), form.get('method') || null, form.get('role') || null).run();
    if (!saved.success) throw new Error();
  } catch { return notice(lang,503,'unavailable'); }
  return redirect('/feedback?lang=' + lang, { 'Set-Cookie': `${feedbackCookie}=${token}; Path=/; Max-Age=2592000; HttpOnly; Secure; SameSite=Strict` });
}

const style = `
:root{color-scheme:light;--ink:#172922;--muted:#415c50;--green:#145c42;--line:#b8cbbf;--paper:#f9faf5;--mint:#d9edc9}
*{box-sizing:border-box}html{font-family:Inter,"Segoe UI",Arial,sans-serif;color:var(--ink);background:var(--paper);scroll-behavior:smooth}
body{max-width:1232px;margin:auto;padding:0 clamp(18px,5vw,68px)}a{color:var(--green);text-underline-offset:4px}a:hover{text-decoration-thickness:2px}
nav,footer{display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--line);padding:24px 0;gap:12px}
.brand{font-size:1.14rem;font-weight:760;letter-spacing:-.05em;color:var(--ink);text-decoration:none;white-space:nowrap}
nav div{display:flex;gap:clamp(12px,3vw,32px)}nav a,footer a{font-size:.92rem}
header{display:grid;grid-template-columns:1.06fr .94fr;align-items:center;gap:clamp(24px,5vw,80px);padding:clamp(36px,7vw,88px) 0}
h1,h2,p{margin:0}h1{font-family:"Instrument Serif",Georgia,serif;font-weight:400;font-size:clamp(3.2rem,6.5vw,5.9rem);line-height:.99;letter-spacing:-.058em;max-width:11ch}
.intro p{font-size:clamp(1rem,1.7vw,1.19rem);line-height:1.6;margin-top:25px;max-width:42ch;color:var(--muted)}
form{background:var(--mint);padding:clamp(19px,3vw,34px);border:1px solid #a7bd9d;border-radius:18px}
h2{font-size:clamp(1.38rem,2.6vw,2rem);line-height:1.13;letter-spacing:-.044em}p{line-height:1.55}
.note{font-size:.88rem;color:var(--muted);margin:10px 0 15px}.fields{display:grid;gap:8px}label{display:grid;grid-template-columns:1fr 100px;align-items:center;gap:10px;font-size:.91rem}
input{font:inherit;color:var(--ink);border:1px solid #8faa91;border-radius:5px;background:#fffffa;padding:7px 8px;text-align:right;min-width:0;font-variant-numeric:tabular-nums}
.result{border-top:1px solid #9ab49c;margin-top:17px;padding-top:13px;display:flex;align-items:center;justify-content:space-between;gap:12px}
.result strong{font-size:clamp(1.8rem,3.5vw,2.5rem);font-variant-numeric:tabular-nums;overflow-wrap:anywhere;letter-spacing:-.055em}
.lower{border-top:1px solid var(--line);display:grid;grid-template-columns:1fr 1fr;gap:clamp(24px,6vw,80px);padding:clamp(26px,4vw,52px) 0}
.lower p{color:var(--muted);margin-top:14px}.row{display:flex;gap:7px;align-items:stretch}.row input{width:100%;text-align:left;font: .87rem ui-monospace,monospace}
button,.action{border:1px solid var(--green);border-radius:5px;padding:8px 12px;background:var(--green);color:white;font:600 .9rem inherit;cursor:pointer;white-space:nowrap}
.action{display:inline-block;text-decoration:none;margin-top:16px;font-size:.94rem;font-weight:650}.action:hover,button:hover{background:#0d4431}
.lower h3{font-size:.85rem;margin:19px 0 7px}.lower blockquote{margin:0;padding-left:12px;border-left:3px solid var(--line);line-height:1.48;color:var(--muted)}
footer{border-bottom:0;border-top:1px solid var(--line)}.error{color:#763814;font-size:.85rem;line-height:1.3}.error:not(:empty){margin-top:8px}
:focus-visible{outline:3px solid #204c98;outline-offset:3px}
@media(max-width:760px){header,.lower{grid-template-columns:1fr}h1{max-width:13ch}header{padding:34px 0}nav,footer{padding:16px 0}.lower{gap:32px}}
@media(max-width:360px){body{padding:0 12px}label{grid-template-columns:1fr 73px}.row{flex-wrap:wrap}}
nav div{flex-wrap:wrap;justify-content:flex-end}.survey{background:white;border-color:var(--line)}
.survey fieldset{border:0;margin:0 0 16px;padding:0}.survey legend{font-size:1.13rem;font-weight:650;margin-bottom:10px}
.survey .choice{display:flex;justify-content:flex-start;gap:9px;margin:9px 0;cursor:pointer;align-items:baseline}.choice input{accent-color:var(--green);flex:none}
.survey .select-label{display:grid;grid-template-columns:1fr;gap:4px;margin:12px 0}.survey select{background:#fff;color:var(--ink);padding:8px;max-width:100%;font:inherit}.survey button{margin-top:8px}.notice{padding:clamp(28px,8vw,110px) 0}.notice p{margin:15px 0}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}`;

function browserDemo(calculate) {
  const form = document.querySelector('form[aria-labelledby="calc"]');
  const out = document.getElementById('result');
  const error = document.getElementById('error');
  const format = new Intl.NumberFormat(document.documentElement.lang, { style: 'currency', currency: 'USD' });
  function update() {
    try {
      const data = Object.fromEntries(Array.from(form.querySelectorAll('input'), el => [el.name, el.valueAsNumber]));
      out.textContent = format.format(calculate(data).campaign_contribution_usd);
      error.textContent = '';
    } catch {
      out.textContent = '—';
      error.textContent = error.dataset.message;
    }
  }
  form.addEventListener('submit', e => e.preventDefault());
  form.addEventListener('input', update);
  update();
  const address = document.getElementById('endpoint');
  address.value = new URL('/demo/mcp', location.href).href;
  const copy = document.getElementById('copy');
  copy.addEventListener('click', async () => {
    try { await navigator.clipboard.writeText(address.value); copy.textContent = copy.dataset.done; }
    catch { address.focus(); address.select(); }
  });
}

function landing(lang) {
  const t = copy[lang];
  const inputs = amounts.map((name, i) => `<label>${t.inputs[i]}<input type="number" name="${name}" min="0" max="1000000000" step=".01" required value="${[200, 0, 50, 125][i]}" aria-label="${t.inputs[i]}, USD"></label>`).join('');
  return `<!doctype html><html lang="${lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>${text[lang].title}</title><link rel="canonical" href="${canonical}/${lang === 'ru' ? '?lang=ru' : ''}">
<link rel="alternate" hreflang="en" href="${canonical}/"><link rel="alternate" hreflang="ru" href="${canonical}/?lang=ru"><link rel="alternate" hreflang="x-default" href="${canonical}/"><meta name="description" content="${t.lead}"><style>${style}</style><script src="/demo.js" defer></script></head>
<body><nav><a class="brand" href="/?lang=${lang}">Channel Ops</a><div><a href="#survey">${text[lang].nav}</a><a href="#pilot">${t.nav}</a><a href="${t.href}" hreflang="${lang === 'en' ? 'ru' : 'en'}">${t.other}</a></div></nav>
<main><header><div class="intro"><h1>${t.title}</h1><p>${t.lead}</p></div>
<form aria-labelledby="calc"><h2 id="calc">${t.heading}</h2><p class="note">${t.hint}</p><div class="fields">${inputs}</div><div class="result"><div>${t.output}<br><small>${t.sample}</small></div>
<strong id="result" aria-live="polite">$25.00</strong></div><p id="error" role="status" class="error" data-message="${t.calcError}"></p><noscript><small>${t.script}</small></noscript></form></header>
<div class="lower"><section><h2>${t.ai}</h2><p>${t.how}</p><h3><label for="endpoint">${t.endpoint}</label></h3><div class="row"><input id="endpoint" readonly value="/demo/mcp"><button type="button" id="copy" data-done="${t.copied}">${t.copy}</button></div>
<h3>${t.ask}</h3><blockquote>${t.prompt}</blockquote><p class="note">${t.shorts}</p><p><a href="${repo}/releases/download/review-v0.1.0/channel-review.zip">${text[lang].workflow}</a> · <a href="${repo}/tree/main/plugins/channel-review">${text[lang].guide}</a></p></section>
<section id="pilot"><h2>${t.pilot}</h2><p>${t.offer}</p><p>${t.evidence}</p><a class="action" href="${pilot}">${t.cta}</a></section></div>
${survey(lang)}</main><footer><span class="brand">Channel Ops</span><a href="${repo}">${t.source} ↗</a></footer></body></html>`;
}

export default {
  async fetch(req, env = {}) {
    const url = new URL(req.url);
    const lang = url.searchParams.get('lang') === 'ru' ? 'ru' : 'en';
    if (url.pathname === '/feedback') return handleFeedback(req,env.FEEDBACK,lang);
    if (['/mcp', '/demo/mcp'].includes(url.pathname)) return handleMcp(req);
    if (!['/', '/demo.js', '/robots.txt', '/sitemap.xml'].includes(url.pathname)) return response('Not found', 404, 'text/plain');
    if (req.method !== 'GET' && req.method !== 'HEAD') return response(null, 405, null, { Allow: 'GET, HEAD' });
    if (url.pathname === '/robots.txt')
      return response(req.method === 'HEAD' ? null : `User-agent: *\nAllow: /\nDisallow: /mcp\nDisallow: /demo/mcp\nDisallow: /feedback\nSitemap: ${canonical}/sitemap.xml\n`, 200,'text/plain; charset=utf-8');
    if (url.pathname === '/sitemap.xml')
      return response(req.method === 'HEAD' ? null : `<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>${canonical}/</loc></url><url><loc>${canonical}/?lang=ru</loc></url></urlset>`,200,'application/xml; charset=utf-8');
    if (url.pathname === '/demo.js')
      return response(req.method === 'HEAD' ? null : `(${browserDemo.toString()})(${calculateContribution.toString()});`, 200, 'text/javascript; charset=utf-8');
    return response(req.method === 'HEAD' ? null : landing(lang), 200, 'text/html; charset=utf-8', {
      'Content-Security-Policy': "default-src 'none'; script-src 'self'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'self'; frame-ancestors https://chatgpt.com https://*.chatgpt.com 'self'",
      'Referrer-Policy': 'same-origin', 'Content-Language': lang });
  }
};
