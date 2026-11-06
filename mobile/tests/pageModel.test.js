const test = require('node:test');
const assert = require('node:assert/strict');
const { parsePage, all, initialValues, entries, validate, siteAddress, text } = require('../src/pageModel');

test('extracts main content and labels without executing scripts', () => {
  const page = parsePage('<title>Family - Guardian</title><body><nav>menu</nav><main><h1>My family</h1><label for="name">Nickname &amp; age</label><input id="name"></main><script>throw new Error()</script></body>');
  assert.equal(page.title, 'Family');
  assert.equal(page.labels.name, 'Nickname & age');
  assert.equal(page.nodes.some((n) => n.name === 'nav'), false);
});
test('preserves consent, quiz answers and repeated child selections', () => {
  const page = parsePage('<form method="post"><input type="hidden" name="csrfmiddlewaretoken" value="token"><input type="hidden" name="action" value="send"><input type="checkbox" name="children" value="1" checked><input type="checkbox" name="children" value="2" checked><input type="checkbox" name="off"><input type="radio" name="q1" value="4" checked><input name="ignored" disabled value="no"><textarea name="summary">A &amp; B</textarea><select name="age"><option value="10-12" selected>10–12</option></select></form>');
  const form = page.nodes[0], values = initialValues(form);
  assert.deepEqual(values.children, ['1', '2']);
  assert.equal(values.q1, '4');
  assert.equal(values.summary, 'A & B');
  assert.equal(values.age, '10-12');
  assert.equal(values.ignored, undefined);
  assert.deepEqual(entries(values, { name: 'action', value: 'publish' }).filter(([k]) => k === 'children'), [['children', '1'], ['children', '2']]);
  assert.equal(entries(values).some(([k]) => k === 'off'), false);
});
test('required consent and quiz choices must be provided', () => {
  const form = parsePage('<form><input name="told_child" type="checkbox" required><input name="q1" type="radio" required value="1"></form>').nodes[0];
  assert.match(validate(form, {}), /told child/);
  assert.match(validate(form, { told_child: ['on'] }), /q1/);
  assert.equal(validate(form, { told_child: ['on'], q1: '1' }), null);
});
test('server settings accept phone-reachable origins and reject unsafe addresses', () => {
  assert.equal(siteAddress('https://guardian.example.org/'), 'https://guardian.example.org');
  assert.equal(siteAddress('http://192.168.1.20:8001'), 'http://192.168.1.20:8001');
  for (const url of ['http://localhost:8001', 'http://10.0.2.2:8001', 'javascript:alert(1)', 'https://user:secret@example.org', 'https://example.org/path']) assert.throws(() => siteAddress(url));
});
