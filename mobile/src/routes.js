/**
 * Pure routing helpers shared by the app and the tests (no React Native imports here).
 *
 * The Django site is the single source of truth: every tab is a site path, and the app only
 * decides which tabs a role sees and how each link should open.
 */

const DEFAULT_PREFIXES = { auth: 'a4e2b1c9', panel: 'b2a9e6f1', parent: 'family', child: 'me' };

/** Tabs for each role. `match` lists path prefixes that light the tab up. */
function tabsFor(role, prefixes = DEFAULT_PREFIXES) {
  const p = { ...DEFAULT_PREFIXES, ...(prefixes || {}) };
  if (role === 'child') {
    return [
      { key: 'home', label: 'My space', icon: 'home-outline', path: `/${p.child}/`, match: [`/${p.child}/family/`] },
      { key: 'check', label: 'Is this safe?', icon: 'shield-checkmark-outline', path: `/${p.child}/check/`, match: [`/${p.child}/check/`, `/${p.child}/history/`] },
      { key: 'lessons', label: 'Lessons', icon: 'book-outline', path: `/${p.child}/lessons/`, match: [`/${p.child}/lessons/`, '/learn/'] },
      { key: 'report', label: 'Report', icon: 'flag-outline', path: `/${p.child}/report/`, match: [`/${p.child}/report/`] },
      { key: 'help', label: 'Get help', icon: 'call-outline', path: '/help/', match: ['/help/', '/privacy/'] },
    ];
  }
  if (role === 'parent') {
    return [
      { key: 'family', label: 'Family', icon: 'people-outline', path: `/${p.parent}/`, match: [`/${p.parent}/children/`] },
      { key: 'news', label: 'News', icon: 'newspaper-outline', path: `/${p.parent}/news/`, match: [`/${p.parent}/news/`] },
      { key: 'check', label: 'Check', icon: 'shield-checkmark-outline', path: `/${p.parent}/check/`, match: [`/${p.parent}/check/`] },
      { key: 'alerts', label: 'Alerts', icon: 'notifications-outline', path: `/${p.parent}/alerts/`, match: [`/${p.parent}/alerts/`] },
      { key: 'settings', label: 'Settings', icon: 'settings-outline', path: `/${p.parent}/settings/`, match: [`/${p.parent}/settings/`, `/${p.auth}/security/`] },
    ];
  }
  if (role === 'analyst') {
    return [
      { key: 'dashboard', label: 'Dashboard', icon: 'grid-outline', path: `/${p.panel}/dashboard/`, match: [`/${p.panel}/dashboard/`] },
      { key: 'content', label: 'Content', icon: 'document-text-outline', path: `/${p.panel}/content/`, match: [`/${p.panel}/content/`, `/${p.panel}/sources/`, `/${p.panel}/raw/`] },
      { key: 'campaigns', label: 'Campaigns', icon: 'mail-outline', path: `/${p.panel}/campaigns/`, match: [`/${p.panel}/campaigns/`] },
      { key: 'analytics', label: 'Analytics', icon: 'stats-chart-outline', path: `/${p.panel}/analytics/`, match: [`/${p.panel}/analytics/`] },
      { key: 'evaluation', label: 'Models', icon: 'pulse-outline', path: `/${p.panel}/evaluation/`, match: [`/${p.panel}/evaluation/`] },
    ];
  }
  return [
    { key: 'home', label: 'Home', icon: 'home-outline', path: '/', match: [] },
    { key: 'signin', label: 'Sign in', icon: 'log-in-outline', path: `/${p.auth}/login/`, match: [`/${p.auth}/login/`, `/${p.auth}/password/`] },
    { key: 'join', label: 'Join', icon: 'person-add-outline', path: `/${p.auth}/register/`, match: [`/${p.auth}/register/`] },
    { key: 'code', label: 'Family code', icon: 'key-outline', path: '/pair/', match: ['/pair/'] },
    { key: 'help', label: 'Get help', icon: 'call-outline', path: '/help/', match: ['/help/', '/privacy/'] },
  ];
}

/** Which tab a site path belongs to: the longest matching prefix wins; exact tab roots count too. */
function activeTab(tabs, path) {
  let best = null;
  let bestLen = -1;
  for (const t of tabs) {
    for (const prefix of [t.path, ...(t.match || [])]) {
      const hit = prefix === '/' ? path === '/' : path.startsWith(prefix);
      if (hit && prefix.length > bestLen) {
        best = t.key;
        bestLen = prefix.length;
      }
    }
  }
  return best;
}

function origin(siteUrl) {
  const m = /^(https?:\/\/[^/]+)/i.exec(siteUrl || '');
  return m ? m[1].toLowerCase() : '';
}

/**
 * How a requested URL should open:
 *  'web'      load inside the app (the Guardian site, or about:/data: frames such as email previews)
 *  'dial'     phone, SMS or email apps (Call 116)
 *  'google'   Google sign-in, which Google blocks inside embedded web views
 *  'external' everything else: the phone's browser (Guardian never opens checked links for the user)
 */
function classify(url, siteUrl) {
  const u = String(url || '');
  if (/^(about:|data:|blob:|javascript:)/i.test(u)) return 'web';
  if (/^(tel:|sms:|mailto:|intent:)/i.test(u)) return 'dial';
  if (/^https?:\/\/accounts\.google\.com/i.test(u) || /\/accounts\/google\/login/i.test(u)) return 'google';
  const site = origin(siteUrl);
  if (site && u.toLowerCase().startsWith(site)) return 'web';
  return 'external';
}

/** A deep link (guardian://p/TOKEN or https://site/p/TOKEN) as a site path, or null. */
function deepLinkPath(link, siteUrl) {
  const s = String(link || '');
  const site = origin(siteUrl);
  if (site && s.toLowerCase().startsWith(site)) return s.slice(site.length) || '/';
  const m = /^guardian:\/\/+(.*)$/i.exec(s);
  if (m) return '/' + m[1].replace(/^\/+/, '');
  return null;
}

/** Path part of a full site URL (for tab highlighting). */
function pathOf(url, siteUrl) {
  const site = origin(siteUrl);
  const u = String(url || '');
  if (site && u.toLowerCase().startsWith(site)) {
    const rest = u.slice(site.length).split(/[?#]/)[0];
    return rest || '/';
  }
  return '/';
}

/** On the Android emulator, the computer's localhost is 10.0.2.2. Real phones need the LAN IP instead. */
function forEmulator(siteUrl, isAndroid) {
  if (!isAndroid) return siteUrl;
  return String(siteUrl).replace(/^(https?:\/\/)(localhost|127\.0\.0\.1)(?=[:/]|$)/i, '$110.0.2.2');
}

module.exports = { DEFAULT_PREFIXES, tabsFor, activeTab, classify, deepLinkPath, pathOf, forEmulator, origin };
