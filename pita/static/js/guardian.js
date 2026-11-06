// Guardian UI utilities, loaded after navbar.js
// Overrides: showToast, handleLogout, handleDeleteAccount
// Adds: showConfirm, data-confirm auto-wiring, button loading, client-side filter, page loader

var _SPINNER = '<svg class="animate-spin h-4 w-4 shrink-0" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>';

// Inline SVG used for link spinners, uses inline style so no Tailwind class dependency
var _LINK_SPINNER = '<span data-g-spin style="display:inline-flex;align-items:center;margin-left:5px;vertical-align:middle;pointer-events:none;">' +
    '<svg style="animation:spin 1s linear infinite;height:0.8em;width:0.8em;flex-shrink:0;" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">' +
    '<circle style="opacity:.25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>' +
    '<path style="opacity:.75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>' +
    '</svg></span>';

// ── Page transition loader ────────────────────────────────────────────
// Only used for fetch-based flows where no button/link remains visible
// after the action is initiated (logout / delete-account after confirm modal closes).
function _gShowPageLoader() {
    var el = document.getElementById('gPageLoader');
    if (el) { el.classList.remove('hidden'); el.classList.add('flex'); }
}
function _gHidePageLoader() {
    var el = document.getElementById('gPageLoader');
    if (el) { el.classList.add('hidden'); el.classList.remove('flex'); }
}

// ── Link spinner (local loading state for <a href> navigation) ────────
function _gSpinLink(el) {
    if (el.hasAttribute('data-g-spinning')) return;
    el.setAttribute('data-g-spinning', '1');
    el.style.pointerEvents = 'none';
    el.style.opacity = '0.7';
    el.insertAdjacentHTML('beforeend', _LINK_SPINNER);
}

// ── Restore state on bfcache (browser back/forward) ───────────────────
window.addEventListener('pageshow', function(e) {
    if (!e.persisted) return;
    _gHidePageLoader();
    document.querySelectorAll('[data-g-spinning]').forEach(function(el) {
        el.removeAttribute('data-g-spinning');
        el.style.pointerEvents = '';
        el.style.opacity = '';
        var s = el.querySelector('[data-g-spin]');
        if (s) s.remove();
    });
});

// ── Spin link on navigation click ────────────────────────────────────
document.addEventListener('click', function(e) {
    if (e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
    var el = e.target.closest('a[href]');
    if (!el || e.defaultPrevented) return;
    var href = el.getAttribute('href') || '';
    if (!href || href === '#' || href.charAt(0) === '#' ||
        href.startsWith('javascript') || href.startsWith('mailto') || href.startsWith('tel:') ||
        el.target === '_blank' || el.hasAttribute('data-no-loader')) return;
    _gSpinLink(el);
}, true);

// ── Toast (animated, overrides navbar.js version) ─────────────────────
function showToast(message, type) {
    type = type || 'success';
    var el = document.getElementById('toast');
    if (!el) return;
    el.textContent = message;
    el.className = 'toast ' + type;
    void el.offsetHeight;
    el.classList.add('show');
    clearTimeout(el._timer);
    el._timer = setTimeout(function() { el.classList.remove('show'); }, 3500);
}

// ── Confirm Modal ─────────────────────────────────────────────────────
function showConfirm(message, onConfirm, btnLabel) {
    btnLabel = btnLabel || 'Confirm';
    var overlay = document.getElementById('gConfirmOverlay');
    var msgEl = document.getElementById('gConfirmMsg');
    var btn = document.getElementById('gConfirmBtn');
    if (!overlay) {
        if (window.confirm(message) && onConfirm) { onConfirm(); }
        return;
    }
    msgEl.textContent = message;
    var fresh = btn.cloneNode(true);
    fresh.textContent = btnLabel;
    btn.parentNode.replaceChild(fresh, btn);
    fresh.addEventListener('click', function() {
        _gHideConfirm();
        if (onConfirm) onConfirm();
    });
    overlay.classList.remove('hidden');
    overlay.classList.add('flex');
    document.body.style.overflow = 'hidden';
}

function _gHideConfirm() {
    var o = document.getElementById('gConfirmOverlay');
    if (o) { o.classList.add('hidden'); o.classList.remove('flex'); }
    document.body.style.overflow = '';
}

// ── Logout override ───────────────────────────────────────────────────
// Confirm modal closes before the fetch fires, no link or button is
// visible at that point, so global page loader is the only option.
function handleLogout() {
    showConfirm('Are you sure you want to log out?', function() {
        _gShowPageLoader();
        fetch(window.GUARDIAN_URLS.logout, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken }
        }).then(function(r) {
            if (r.ok) { window.location.href = window.GUARDIAN_URLS.login; }
            else { _gHidePageLoader(); showToast('Logout failed', 'error'); }
        }).catch(function() { _gHidePageLoader(); showToast('Logout failed', 'error'); });
    }, 'Logout');
}

// ── Delete / deactivate account override ─────────────────────────────
function handleDeleteAccount() {
    showConfirm(
        'Permanently deactivate your account? Your organisational records will be retained. This cannot be undone.',
        function() {
            _gShowPageLoader();
            fetch(window.GUARDIAN_URLS.deleteAccount, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken }
            }).then(function(r) {
                return r.json().then(function(d) { return { ok: r.ok, d: d }; });
            }).then(function(res) {
                if (res.ok && res.d.status === 'success') {
                    showToast('Account deactivated. Goodbye!', 'success');
                    setTimeout(function() { window.location.href = '/'; }, 2000);
                } else {
                    _gHidePageLoader();
                    showToast((res.d && res.d.message) || 'Failed to deactivate', 'error');
                }
            }).catch(function() { _gHidePageLoader(); showToast('Failed to deactivate', 'error'); });
        },
        'Deactivate'
    );
}

// ── Button spinner (local loading state for form submit buttons) ──────
function _gApplyLoading(form) {
    // <button> with no type attribute is also a submit button
    var btn = form.querySelector('button[type="submit"]:not([data-no-loading]), button:not([type]):not([data-no-loading])');
    if (!btn || btn.disabled) return;
    btn.disabled = true;
    btn.style.minWidth = btn.offsetWidth + 'px';
    btn.innerHTML = '<span class="inline-flex items-center justify-center gap-1.5">' + btn.innerHTML + _SPINNER + '</span>';
}

document.addEventListener('DOMContentLoaded', function() {

    // ── Sync dark mode icons ──────────────────────────────────
    var _isDark = document.documentElement.classList.contains('dark');
    if (typeof _NAV_MOON !== 'undefined') {
        document.querySelectorAll('.dark-toggle-icon').forEach(function(el) {
            el.innerHTML = _isDark ? _NAV_SUN : _NAV_MOON;
        });
    }

    // ── Confirm overlay wiring ────────────────────────────────
    var cancelBtn = document.getElementById('gConfirmCancel');
    if (cancelBtn) cancelBtn.addEventListener('click', _gHideConfirm);
    var overlay = document.getElementById('gConfirmOverlay');
    if (overlay) overlay.addEventListener('click', function(e) {
        if (e.target === overlay) _gHideConfirm();
    });

    // ── data-confirm forms: button spinner only ───────────────
    document.querySelectorAll('form[data-confirm]').forEach(function(form) {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            var msg = form.dataset.confirm;
            var label = form.dataset.confirmBtn || 'Confirm';
            showConfirm(msg, function() {
                _gApplyLoading(form);
                if (form.hasAttribute('data-page-loader')) _gShowPageLoader();
                form.removeAttribute('data-confirm');
                form.submit();
            }, label);
        });
    });

    // ── Regular form submit: button spinner; slow AI/email actions also get the page loader ──
    document.querySelectorAll('form:not([data-confirm])').forEach(function(form) {
        form.addEventListener('submit', function() {
            _gApplyLoading(form);
            if (form.hasAttribute('data-page-loader')) _gShowPageLoader();
        });
    });

    // ── Django messages → toasts ──────────────────────────────
    (window._djangoMessages || []).forEach(function(m, i) {
        setTimeout(function() {
            showToast(m.message, m.tags === 'error' ? 'error' : 'success');
        }, i * 500 + 150);
    });

    // ── Library client-side filter ────────────────────────────
    var libSearch = document.getElementById('librarySearch');
    var libThreat = document.getElementById('libraryThreat');
    var libGrid   = document.getElementById('libraryGrid');
    var libEmpty  = document.getElementById('libraryEmpty');

    function _filterLib() {
        if (!libGrid) return;
        var q = (libSearch ? libSearch.value.toLowerCase().trim() : '');
        var t = (libThreat ? libThreat.value : '');
        var n = 0;
        libGrid.querySelectorAll('[data-title]').forEach(function(card) {
            var ok = (!q || card.dataset.title.includes(q) || (card.dataset.risk || '').includes(q))
                  && (!t || card.dataset.threat === t);
            card.classList.toggle('hidden', !ok);
            if (ok) n++;
        });
        if (libEmpty) libEmpty.classList.toggle('hidden', n > 0);
    }

    function _clearLib() {
        if (libSearch) libSearch.value = '';
        if (libThreat) libThreat.value = '';
        _filterLib();
    }

    if (libSearch) libSearch.addEventListener('input', _filterLib);
    if (libThreat) libThreat.addEventListener('change', _filterLib);
    document.querySelectorAll('[data-clear-library]').forEach(function(el) {
        el.addEventListener('click', _clearLib);
    });

    // ── Quizzes client-side search ────────────────────────────
    var quizSearch = document.getElementById('quizSearch');
    var quizGrid   = document.getElementById('quizzesGrid');
    var quizEmpty  = document.getElementById('quizzesEmpty');

    function _filterQuizzes() {
        if (!quizGrid) return;
        var q = (quizSearch ? quizSearch.value.toLowerCase().trim() : '');
        var n = 0;
        quizGrid.querySelectorAll('[data-title]').forEach(function(card) {
            var ok = !q || card.dataset.title.includes(q);
            card.classList.toggle('hidden', !ok);
            if (ok) n++;
        });
        if (quizEmpty) quizEmpty.classList.toggle('hidden', n > 0);
    }

    if (quizSearch) quizSearch.addEventListener('input', _filterQuizzes);
});
