const { parsePage, all, entries } = require('./pageModel');

class GuardianClient {
  constructor(site, prefixes) { this.site = site; this.prefixes = prefixes; this.csrf = null; }
  url(path, base = this.site) {
    const u = new URL(path, base);
    if (u.origin !== this.site) throw new Error('This action points outside your Guardian server.');
    return u.href;
  }
  async request(path, options = {}) {
    const url = this.url(path);
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 180000);
    try {
      const response = await fetch(url, { ...options, credentials: 'include', signal: controller.signal,
        headers: { Accept: 'text/html, application/json', Referer: this.site + '/', ...options.headers } });
      if (new URL(response.url || url).origin !== this.site) throw new Error('Guardian redirected to another server. Check the server address.');
      const raw = await response.text();
      if ((response.headers.get('content-type') || '').includes('application/json')) {
        const json = JSON.parse(raw);
        if (!response.ok || json.status === 'error' || json.error) throw new Error(json.error || json.message || `Request failed (${response.status})`);
        return { json, url: response.url || url };
      }
      const page = parsePage(raw);
      const token = page.nodes.flatMap((n) => [n, ...all(n, () => true)])
        .find((n) => n.attribs?.name === 'csrfmiddlewaretoken')?.attribs?.value;
      if (token) this.csrf = token;
      if (response.status >= 500) throw new Error(`The Guardian server returned ${response.status}. Try again shortly.`);
      return { ...page, status: response.status, url: response.url || url };
    } catch (e) {
      if (e.name === 'AbortError') throw new Error('Guardian took too long to respond. Try again.');
      throw e;
    } finally { clearTimeout(timer); }
  }
  async submit(form, values, submitter, pageUrl) {
    const attrs = form.attribs || {};
    const action = this.url(submitter?.formaction || attrs.action || pageUrl, pageUrl);
    const pairs = entries(values, submitter).filter(([name]) => name !== 'csrfmiddlewaretoken');
    if ((attrs.method || 'get').toLowerCase() === 'get') {
      const u = new URL(action);
      u.search = new URLSearchParams(pairs).toString();
      return this.request(u.href);
    }
    if (!this.csrf) {
      const token = await this.request(`/${this.prefixes.auth}/api/csrf/`);
      this.csrf = token.json?.csrfToken;
    }
    const data = new FormData();
    data.append('csrfmiddlewaretoken', this.csrf || '');
    for (const [key, value] of pairs) data.append(key, value);
    const result = await this.request(action, { method: 'POST', body: data,
      headers: { 'X-CSRFToken': this.csrf || '' } });
    if (result.json?.next) return this.request(this.url(result.json.next));
    return result;
  }
  async profile() {
    const result = await this.request(`/${this.prefixes.auth}/profile/`);
    return result.json?.status === 'success' ? result.json : null;
  }
  async account(action, body, multipart = false) {
    const token = await this.request(`/${this.prefixes.auth}/api/csrf/`);
    this.csrf = token.json?.csrfToken;
    return this.request(`/${this.prefixes.auth}/${action}/`, {
      method: 'POST', body: multipart ? body : JSON.stringify(body),
      headers: { 'X-CSRFToken': this.csrf || '', ...(multipart ? {} : { 'Content-Type': 'application/json' }) },
    });
  }
}
module.exports = { GuardianClient };
