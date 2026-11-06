const test = require('node:test');
const assert = require('node:assert/strict');
const server = require('../guardian.server.json');
const { siteAddress } = require('../src/pageModel');
const { DEFAULT_PREFIXES } = require('../src/routes');

test('the built-in server address is a valid public https base address', () => {
  assert.equal(siteAddress(server.siteUrl), server.siteUrl.replace(/\/+$/, ''));
  assert.match(server.siteUrl, /^https:\/\//);
});

test('built-in route prefixes match the Django defaults', () => {
  assert.deepEqual(server.prefixes, DEFAULT_PREFIXES);
});

test('the app has no server address input', () => {
  const app = require('fs').readFileSync(require('path').join(__dirname, '..', 'App.js'), 'utf8');
  assert.doesNotMatch(app, /TextInput/);
  assert.doesNotMatch(app, /title="Connect to Guardian"|Connection settings|Guardian server URL|route prefix/);
});
