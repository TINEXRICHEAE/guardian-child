const test = require('node:test');
const assert = require('node:assert/strict');
const { GuardianClient } = require('../src/client');
const { parsePage } = require('../src/pageModel');
const { DEFAULT_PREFIXES } = require('../src/routes');
const site = 'https://guardian.example.org';
const html = (body, url = site + '/family/') => ({ ok: true, status: 200, url, headers: new Headers({ 'content-type': 'text/html' }), text: async () => body });
const json = (data, status = 200) => ({ ok: status < 400, status, url: site + '/a4e2b1c9/login/', headers: new Headers({ 'content-type': 'application/json' }), text: async () => JSON.stringify(data) });

test('login submits CSRF and follows the backend role destination', async (t) => {
  const calls = [];
  t.mock.method(global, 'fetch', async (url, options) => {
    calls.push({ url, options });
    return calls.length === 1 ? json({ csrfToken: 'token' }) : calls.length === 2 ? json({ next: '/family/' }) : html('<main><h1>My family</h1></main>');
  });
  const client = new GuardianClient(site, DEFAULT_PREFIXES);
  const form = parsePage('<form method="post" action="/a4e2b1c9/login/"></form>').nodes[0];
  const result = await client.submit(form, { email: 'parent@example.org', password: 'test-password' }, {}, site + '/');
  assert.equal(calls[1].options.body.get('csrfmiddlewaretoken'), 'token');
  assert.equal(calls[1].options.headers['X-CSRFToken'], 'token');
  assert.equal(calls[1].options.credentials, 'include');
  assert.equal(calls[2].url, site + '/family/');
  assert.equal(result.nodes[0].name, 'h1');
});
test('backend validation errors are shown to the native form', async (t) => {
  t.mock.method(global, 'fetch', async () => json({ error: 'Invalid email or password' }, 401));
  const client = new GuardianClient(site, DEFAULT_PREFIXES);
  await assert.rejects(client.request('/a4e2b1c9/login/'), /Invalid email or password/);
});
test('form actions and account redirects cannot send credentials to another server', async (t) => {
  const client = new GuardianClient(site, DEFAULT_PREFIXES);
  assert.throws(() => client.url('https://evil.example.org/'), /outside/);
  t.mock.method(global, 'fetch', async () => json({ next: 'https://evil.example.org/' }));
  client.csrf = 'token';
  await assert.rejects(client.submit({ attribs: { method: 'post' } }, {}, {}, site + '/'), /outside/);
});
test('GET filters keep repeated parameters without submitting CSRF', async (t) => {
  let requested;
  t.mock.method(global, 'fetch', async (url) => { requested = new URL(url); return html('<main>Results</main>'); });
  const client = new GuardianClient(site, DEFAULT_PREFIXES);
  await client.submit({ attribs: { method: 'get', action: '/family/news/' } }, { q: 'safe links', child: ['1', '2'], csrfmiddlewaretoken: 'secret' }, {}, site + '/');
  assert.equal(requested.searchParams.get('q'), 'safe links');
  assert.deepEqual(requested.searchParams.getAll('child'), ['1', '2']);
  assert.equal(requested.searchParams.has('csrfmiddlewaretoken'), false);
});
