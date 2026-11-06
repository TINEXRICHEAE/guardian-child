/** Translate the existing Django response into data for native controls. No scripts execute. */
const { parseDocument } = require('htmlparser2');
const children = (node) => node.children || [];
function all(node, predicate) {
  return children(node).flatMap((n) => [...(predicate(n) ? [n] : []), ...all(n, predicate)]);
}
function text(node) {
  if (node.type === 'text') return node.data;
  if (['script', 'style', 'svg'].includes(node.name)) return '';
  return children(node).map(text).join(' ').replace(/\s+/g, ' ').trim();
}
function parsePage(html) {
  const document = parseDocument(html, { decodeEntities: true });
  const body = all(document, (n) => n.name === 'main')[0]
    || all(document, (n) => n.name === 'body')[0] || document;
  const title = all(document, (n) => n.name === 'title')[0];
  const labels = {};
  for (const label of all(body, (n) => n.name === 'label' && n.attribs?.for)) labels[label.attribs.for] = text(label);
  return { title: title ? text(title).replace(/\s*[-|]\s*Guardian.*$/, '') : 'Guardian', nodes: children(body), labels };
}
function controls(form) {
  return all(form, (n) => ['input', 'textarea', 'select', 'button'].includes(n.name));
}
function initialValues(form) {
  const values = {};
  for (const node of controls(form)) {
    const a = node.attribs || {}, name = a.name;
    if (!name || 'disabled' in a || node.name === 'button' || ['submit', 'file', 'button'].includes(a.type)) continue;
    if (a.type === 'checkbox') {
      if (!values[name]) values[name] = [];
      if ('checked' in a) values[name].push(a.value || 'on');
    } else if (a.type === 'radio') {
      if ('checked' in a) values[name] = a.value || 'on';
    } else if (node.name === 'textarea') values[name] = children(node).map((c) => c.data || '').join('');
    else if (node.name === 'select') {
      const options = all(node, (n) => n.name === 'option');
      const selected = options.filter((o) => 'selected' in o.attribs);
      values[name] = 'multiple' in a ? selected.map((o) => o.attribs.value ?? text(o))
        : (selected[0] || options[0])?.attribs?.value ?? '';
    } else values[name] = a.value || '';
  }
  return values;
}
function entries(values, submitter) {
  const result = Object.entries(values).flatMap(([key, value]) =>
    (Array.isArray(value) ? value : [value]).filter((v) => v != null).map((v) => [key, v]));
  if (submitter?.name) result.push([submitter.name, submitter.value || '']);
  return result;
}
function validate(form, values) {
  for (const node of controls(form)) {
    const a = node.attribs || {};
    if (!a.name || 'disabled' in a || !('required' in a)) continue;
    const v = values[a.name];
    if (v == null || v === '' || (Array.isArray(v) && !v.length)) return `Please complete ${a.name.replace(/_/g, ' ')}.`;
    if (a.type === 'email' && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v)) return 'Enter a valid email address.';
  }
  return null;
}
function siteAddress(value) {
  const u = new URL(value.trim());
  if (!['https:', 'http:'].includes(u.protocol) || u.username || u.password || u.search || u.hash || u.pathname !== '/') {
    throw new Error('Enter the website base address, for example https://guardian.example.org');
  }
  if (['localhost', '127.0.0.1', '10.0.2.2'].includes(u.hostname)) {
    throw new Error('Use the live website or your computer’s Wi-Fi IP address. Localhost cannot reach your computer from a phone.');
  }
  return u.origin;
}
module.exports = { all, text, parsePage, controls, initialValues, entries, validate, siteAddress };
