const test = require('node:test');
const assert = require('node:assert');
const { activeTab, classify, deepLinkPath, forEmulator, pathOf, tabsFor } = require('../src/routes');

const SITE = 'http://192.168.1.20:8001';

test('lookalike domains cannot become internal links or practice links', () => {
  const site = 'https://guardian.example.org';
  assert.equal(classify(site + '.evil.test/p/token', site), 'external');
  assert.equal(deepLinkPath(site + '.evil.test/p/token', site), null);
  assert.equal(pathOf(site + '.evil.test/me/', site), '/');
});

test('each role gets its own five tabs', () => {
  assert.deepStrictEqual(tabsFor('child').map((t) => t.key), ['home', 'check', 'lessons', 'report', 'help']);
  assert.deepStrictEqual(tabsFor('parent').map((t) => t.key), ['family', 'news', 'check', 'alerts', 'settings']);
  assert.deepStrictEqual(tabsFor('analyst').map((t) => t.key), ['dashboard', 'content', 'campaigns', 'analytics', 'evaluation']);
  assert.deepStrictEqual(tabsFor(null).map((t) => t.key), ['home', 'signin', 'join', 'code', 'help']);
});

test('tab paths follow the Django prefixes', () => {
  const tabs = tabsFor('analyst', { panel: 'xyz' });
  assert.strictEqual(tabs[0].path, '/xyz/dashboard/');
  assert.strictEqual(tabsFor('parent', { parent: 'home' })[1].path, '/home/news/');
});

test('the deepest matching tab lights up', () => {
  const child = tabsFor('child');
  assert.strictEqual(activeTab(child, '/me/'), 'home');
  assert.strictEqual(activeTab(child, '/me/check/12/'), 'check');
  assert.strictEqual(activeTab(child, '/learn/3/'), 'lessons');
  const parent = tabsFor('parent');
  assert.strictEqual(activeTab(parent, '/family/news/2/'), 'news');
  assert.strictEqual(activeTab(parent, '/family/'), 'family');
  assert.strictEqual(activeTab(tabsFor(null), '/'), 'home');
  assert.strictEqual(activeTab(tabsFor(null), '/something-else/'), null);
});

test('links open in the right place', () => {
  assert.strictEqual(classify(SITE + '/family/news/', SITE), 'web');
  assert.strictEqual(classify('about:srcdoc', SITE), 'web');
  assert.strictEqual(classify('tel:116', SITE), 'dial');
  assert.strictEqual(classify('mailto:help@x.ug', SITE), 'dial');
  assert.strictEqual(classify('https://accounts.google.com/o/oauth2/auth', SITE), 'google');
  assert.strictEqual(classify(SITE + '/accounts/google/login/?process=connect', SITE), 'google');
  assert.strictEqual(classify('https://www.ucc.co.ug/', SITE), 'external');
  assert.strictEqual(classify('http://192.168.1.21:8001/', SITE), 'external');   // another host is not Guardian
});

test('deep links become site paths', () => {
  assert.strictEqual(deepLinkPath(SITE + '/p/abc123/', SITE), '/p/abc123/');
  assert.strictEqual(deepLinkPath('guardian://p/abc123/', SITE), '/p/abc123/');
  assert.strictEqual(deepLinkPath('https://elsewhere.ug/p/abc/', SITE), null);
  assert.strictEqual(deepLinkPath(null, SITE), null);
});

test('paths and the Android emulator address', () => {
  assert.strictEqual(pathOf(SITE + '/me/lessons/?d=4#quiz', SITE), '/me/lessons/');
  assert.strictEqual(pathOf(SITE, SITE), '/');
  assert.strictEqual(forEmulator('http://localhost:8001', true), 'http://10.0.2.2:8001');
  assert.strictEqual(forEmulator('http://127.0.0.1:8001', true), 'http://10.0.2.2:8001');
  assert.strictEqual(forEmulator('http://localhost:8001', false), 'http://localhost:8001');
  assert.strictEqual(forEmulator('https://guardian.ug', true), 'https://guardian.ug');
});
