/**
 * Runs inside every Guardian page after it loads. It:
 *  - hides the website's own bottom tab bar and footer (the app has native tabs instead);
 *  - tells the app who is signed in (child, parent, analyst or nobody) so it can show the right tabs;
 *  - tells the app whether the page is in dark mode, so the native bars match.
 * Nothing about the page content is sent to the app.
 */
export const BRIDGE_JS = `
(function () {
  try {
    var root = document.documentElement;
    root.classList.add('guardian-app');
    if (!document.getElementById('guardian-app-style')) {
      var st = document.createElement('style');
      st.id = 'guardian-app-style';
      st.textContent = '.app-tabbar, body > footer, footer.bg-on-surface { display: none !important; }'
        + ' body { padding-bottom: 0 !important; }';
      document.head.appendChild(st);
    }
    var send = function (role) {
      window.ReactNativeWebView.postMessage(JSON.stringify({
        type: 'page', role: role || null, dark: root.classList.contains('dark')
      }));
    };
    var url = (window.GUARDIAN_URLS || {}).userProfile;
    if (!url) { send(null); return; }
    fetch(url, { credentials: 'same-origin', headers: { 'Accept': 'application/json' } })
      .then(function (r) {
        var json = (r.headers.get('content-type') || '').indexOf('application/json') > -1;
        return r.ok && json ? r.json() : null;
      })
      .then(function (d) { send(d && d.status === 'success' ? d.role : null); })
      .catch(function () { send(null); });
    new MutationObserver(function () {      // the page's own light/dark toggle
      window.ReactNativeWebView.postMessage(JSON.stringify({ type: 'theme', dark: root.classList.contains('dark') }));
    }).observe(root, { attributes: true, attributeFilter: ['class'] });
  } catch (e) {}
})();
true;
`;
