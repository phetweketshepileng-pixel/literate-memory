(function () {
  'use strict';
  var API = (window.ASCEND_API || '').replace(/\/$/, '') + '/api/v1';

  // ---------------- helpers ----------------
  var $ = function (id) { return document.getElementById(id); };
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function store(k, v) { try { if (v === undefined) return localStorage.getItem(k); if (v === null) localStorage.removeItem(k); else localStorage.setItem(k, v); } catch (e) { return null; } }
  function storeJSON(k, v) { if (v === undefined) { try { return JSON.parse(store(k) || 'null'); } catch (e) { return null; } } store(k, v === null ? null : JSON.stringify(v)); }
  var toastTimer;
  function toast(msg, isErr) {
    var t = $('toast'); t.textContent = msg; t.className = isErr ? 'err' : ''; t.style.display = 'block';
    clearTimeout(toastTimer); toastTimer = setTimeout(function () { t.style.display = 'none'; }, isErr ? 6000 : 3000);
  }
  function label(domain) { return String(domain || '').replace(/_/g, ' ').replace(/\b\w/g, function (c) { return c.toUpperCase(); }); }
  function money(n) { return n == null ? '' : 'R' + Math.round(n / 1000) + 'k'; }
  function pct(v) { return v == null ? '—' : (v <= 1 ? Math.round(v * 100) : Math.round(v)) + '%'; }
  function errMsg(body, status) {
    if (body && body.detail) {
      if (typeof body.detail === 'string') return body.detail;
      if (body.detail.message) return body.detail.message;
      if (Array.isArray(body.detail)) return body.detail.map(function (d) { return (d.loc ? d.loc[d.loc.length - 1] + ': ' : '') + d.msg; }).join('; ');
    }
    return 'Request failed (' + status + ')';
  }
  function formData(form) {
    var o = {};
    Array.prototype.forEach.call(form.elements, function (el) { if (el.name) o[el.name] = el.value.trim(); });
    return o;
  }
  function loadingInto(id) { $(id).innerHTML = '<div class="small muted"><span class="spinner"></span> Loading…</div>'; }
  function empty(html) { return '<div class="empty">' + html + '</div>'; }

  // ---------------- auth + API ----------------
  var session = storeJSON('ascend_session') || null; // {access, refresh, email}
  var refreshing = null;

  function saveSession(tok, email) {
    session = { access: tok.access_token, refresh: tok.refresh_token, email: email || (session && session.email) };
    storeJSON('ascend_session', session);
  }
  function ukey(k) { return k + ':' + ((session && session.email) || ''); }
  function clearSession() { session = null; storeJSON('ascend_session', null); }

  function doRefresh() {
    if (!session || !session.refresh) return Promise.reject(new Error('no session'));
    if (!refreshing) {
      refreshing = fetch(API + '/auth/refresh', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ refresh_token: session.refresh }) })
        .then(function (r) { if (!r.ok) throw new Error('refresh failed'); return r.json(); })
        .then(function (tok) { saveSession(tok); })
        .finally(function () { refreshing = null; });
    }
    return refreshing;
  }

  function api(method, path, body, opts) {
    opts = opts || {};
    var headers = {};
    if (session) headers['Authorization'] = 'Bearer ' + session.access;
    var payload;
    if (body instanceof FormData) payload = body;
    else if (body !== undefined) { headers['Content-Type'] = 'application/json'; payload = JSON.stringify(body); }
    return fetch(API + path, { method: method, headers: headers, body: payload }).then(function (r) {
      if (r.status === 401 && session && !opts.retried && path.indexOf('/auth/') !== 0) {
        return doRefresh().then(function () { return api(method, path, body, { retried: true }); }, function () {
          clearSession(); showAuth(); throw new Error('Your session expired — please sign in again.');
        });
      }
      if (r.status === 204) return null;
      return r.text().then(function (t) {
        var j = null; try { j = t ? JSON.parse(t) : null; } catch (e) { j = null; }
        if (!r.ok) { var e = new Error(j ? errMsg(j, r.status) : (r.status >= 500 ? 'The server hit an error (' + r.status + ')' : 'Request failed (' + r.status + ')')); e.status = r.status; throw e; }
        return j;
      });
    }, function () { throw new Error('Could not reach the server. Check your connection.'); });
  }
  function unwrap(j) { return j && Object.prototype.hasOwnProperty.call(j, 'data') && Object.prototype.hasOwnProperty.call(j, 'error') ? j.data : j; }
  function get(path) { return api('GET', path).then(unwrap); }
  function fail(e) { toast(e.message || String(e), true); }

  // ---------------- auth view ----------------
  var authMode = 'login';
  function setAuthMode(mode) {
    authMode = mode;
    $('tabLogin').classList.toggle('active', mode === 'login');
    $('tabRegister').classList.toggle('active', mode === 'register');
    $('authTitle').textContent = mode === 'login' ? 'Welcome back' : 'Create your account';
    $('authSub').textContent = mode === 'login' ? 'Sign in to continue.' : 'It takes ten seconds.';
    $('authSubmit').textContent = mode === 'login' ? 'Sign in' : 'Create account';
    $('pwHint').style.display = mode === 'register' ? 'block' : 'none';
    $('authPassword').autocomplete = mode === 'login' ? 'current-password' : 'new-password';
    $('authError').style.display = 'none';
  }
  function showReset(on) {
    $('authForm').style.display = on ? 'none' : '';
    $('resetForm').style.display = on ? '' : 'none';
    $('forgotLink').style.display = on ? 'none' : '';
    $('authError').style.display = 'none'; $('resetError').style.display = 'none';
    $('authTitle').textContent = on ? 'Reset your password' : (authMode === 'login' ? 'Welcome back' : 'Create your account');
    document.querySelector('.auth-tabs').style.display = on ? 'none' : '';
    $('authSub').style.display = on ? 'none' : '';
    if (on) { $('resetEmail').value = $('authEmail').value; $('resetEmail').focus(); }
  }
  $('forgotLink').onclick = function () { showReset(true); };
  $('resetBack').onclick = function () { showReset(false); };
  $('resetForm').addEventListener('submit', function (e) {
    e.preventDefault();
    var err = $('resetError'), pw = $('resetPw').value;
    if (pw !== $('resetPw2').value) { err.textContent = 'The two new passwords are different.'; err.style.display = 'block'; return; }
    var btn = $('resetSubmit'); btn.disabled = true; err.style.display = 'none';
    api('POST', '/auth/reset-password', { email: $('resetEmail').value.trim(), reset_code: $('resetCode').value, new_password: pw }).then(function () {
      $('authEmail').value = $('resetEmail').value.trim();
      $('resetCode').value = $('resetPw').value = $('resetPw2').value = '';
      setAuthMode('login'); showReset(false);
      toast('Password changed. Sign in with your new password.');
      $('authPassword').focus();
    }).catch(function (e2) { err.textContent = e2.message; err.style.display = 'block'; })
      .finally(function () { btn.disabled = false; });
  });
  $('tabLogin').onclick = function () { setAuthMode('login'); showReset(false); };
  $('tabRegister').onclick = function () { setAuthMode('register'); showReset(false); };
  $('authForm').addEventListener('submit', function (e) {
    e.preventDefault();
    var email = $('authEmail').value.trim(), pw = $('authPassword').value;
    var btn = $('authSubmit'); btn.disabled = true;
    api('POST', '/auth/' + authMode, { email: email, password: pw }).then(function (tok) {
      saveSession(tok, email); $('authPassword').value = ''; showApp(authMode === 'register');
    }).catch(function (err) {
      var m = err.message;
      if (err.status === 409) m = 'That email already has an account — sign in instead.';
      $('authError').textContent = m; $('authError').style.display = 'block';
    }).finally(function () { btn.disabled = false; });
  });

  function showAuth() { $('appView').style.display = 'none'; $('authView').style.display = 'flex'; }
  function showApp(isNew) {
    $('authView').style.display = 'none'; $('appView').style.display = 'flex';
    $('settingsEmail').textContent = 'Signed in as ' + (session.email || '');
    loadMeta().then(function () { showScreen(isNew ? 'profile' : (store('ascend_screen') || 'dashboard')); });
    if (isNew) toast('Account created — start by filling in your profile.');
  }
  $('logoutBtn').onclick = function () {
    var r = session && session.refresh;
    (r ? api('POST', '/auth/logout', { refresh_token: r }).catch(function () {}) : Promise.resolve()).then(function () { clearSession(); showAuth(); setAuthMode('login'); });
  };

  // ---------------- theme ----------------
  (function () { var t = store('ascend_theme'); if (t) document.documentElement.setAttribute('data-theme', t); })();
  $('themeBtn').onclick = function () {
    var cur = document.documentElement.getAttribute('data-theme');
    if (!cur) cur = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    var next = cur === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next); store('ascend_theme', next);
  };

  // ---------------- navigation ----------------
  var titles = { dashboard: 'Dashboard', profile: 'My Profile', jobs: 'Job Search', applications: 'Applications', analytics: 'Analytics',
    transition: 'Career Transition', interview: 'Interview Preparation', branding: 'Professional Brand', intelligence: 'Recruiter Intelligence', settings: 'Settings' };
  var loaders = {};
  function showScreen(name) {
    if (!titles[name]) name = 'dashboard';
    document.querySelectorAll('.screen').forEach(function (s) { s.classList.remove('active'); });
    $('screen-' + name).classList.add('active');
    document.querySelectorAll('.nav-item').forEach(function (n) { n.classList.toggle('active', n.dataset.screen === name); });
    $('screenTitle').textContent = titles[name];
    $('sidebar').classList.remove('open');
    store('ascend_screen', name);
    window.scrollTo(0, 0);
    if (loaders[name]) loaders[name]();
  }
  document.querySelectorAll('[data-screen]').forEach(function (b) { b.addEventListener('click', function () { showScreen(b.dataset.screen); }); });
  document.addEventListener('click', function (e) { var n = e.target.closest && e.target.closest('[data-nav]'); if (n) showScreen(n.dataset.nav); });
  $('menuToggle').onclick = function () { $('sidebar').classList.toggle('open'); };
  $('identityChip').onclick = function () { showScreen('profile'); };

  // modals
  function openModal(id) { $(id).classList.add('open'); }
  function closeModal(id) { $(id).classList.remove('open'); }
  document.addEventListener('click', function (e) {
    var c = e.target.closest && e.target.closest('[data-close]'); if (c) closeModal(c.dataset.close);
    if (e.target.classList && e.target.classList.contains('overlay')) e.target.classList.remove('open');
  });

  // ---------------- shared metadata ----------------
  var domains = { source_domains: [], target_domains: [] };
  var profile = null;
  function fillSelect(sel, items, selected) {
    sel.innerHTML = items.map(function (d) { return '<option value="' + esc(d) + '"' + (d === selected ? ' selected' : '') + '>' + esc(label(d)) + '</option>'; }).join('');
  }
  function preferredSource() { return store('ascend_source') || domains.source_domains[0]; }
  function setPreferredSource(v) { store('ascend_source', v); ['sourceDomainSel', 'ivSource', 'intelSource'].forEach(function (id) { if ($(id)) $(id).value = v; }); }
  function preferredTarget() { return (profile && profile.career_transition_target) || domains.target_domains[0]; }

  function loadMeta() {
    return Promise.all([get('/career-transition/domains').catch(function () { return domains; }), loadProfileHeader()]).then(function (r) {
      domains = r[0] || domains;
      var src = preferredSource();
      fillSelect($('sourceDomainSel'), domains.source_domains, src);
      fillSelect($('ivSource'), domains.source_domains, src);
      fillSelect($('intelSource'), domains.source_domains, src);
      fillSelect($('reframeTarget'), domains.target_domains, preferredTarget());
      fillSelect($('ivTarget'), domains.target_domains, preferredTarget());
      fillSelect($('brandTarget'), domains.target_domains, preferredTarget());
      $('profileTarget').innerHTML = '<option value="">—</option>' + domains.target_domains.map(function (d) { return '<option value="' + esc(d) + '">' + esc(label(d)) + '</option>'; }).join('');
      $('profileTarget').value = (profile && profile.career_transition_target) || '';
    });
  }
  ['sourceDomainSel', 'ivSource', 'intelSource'].forEach(function (id) {
    $(id).addEventListener('change', function () { setPreferredSource(this.value); if (id === 'sourceDomainSel') loaders.transition(); if (id === 'intelSource') loaders.intelligence(); });
  });

  function loadProfileHeader() {
    return get('/profile').then(function (p) {
      profile = p;
      var name = (p.full_name || '').trim();
      $('sidebarName').textContent = name || 'Set your name';
      $('sidebarRole').textContent = p.current_role || (session && session.email) || '';
      var parts = name.split(/\s+/).filter(Boolean);
      $('avatarInitials').textContent = parts.length ? (parts[0][0] + (parts.length > 1 ? parts[parts.length - 1][0] : '')).toUpperCase() : '?';
      return p;
    }).catch(function (e) { fail(e); });
  }

  // job cache (applications/matches only carry job ids)
  var jobCache = {};
  function getJob(id) {
    if (jobCache[id]) return Promise.resolve(jobCache[id]);
    return get('/jobs/' + id).then(function (j) { jobCache[id] = j; return j; }).catch(function () { return { id: id, title: 'Job no longer available', company: '' }; });
  }

  // ---------------- DASHBOARD ----------------
  var MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  function shortDate(iso) { var p = String(iso).split('-'); return Number(p[2]) + ' ' + MONTHS[Number(p[1]) - 1]; }
  function fmtN(n) { return Number(n || 0).toLocaleString('en-ZA'); }
  var ADZUNA_LINK = '<a href="https://www.adzuna.co.za" target="_blank" rel="noopener noreferrer">Jobs by Adzuna</a>';
  function alsoIn(j) {
    var a = j && j.also_in; if (!a || !a.length) return '';
    return '<div class="also-in">Also advertised in ' + a.slice(0, 3).map(esc).join('; ') + (a.length > 3 ? ' and ' + (a.length - 3) + ' more' : '') + '</div>';
  }
  function viaLine(j) { return j && j.via === 'adzuna' ? '<div class="via">' + ADZUNA_LINK + '</div>' : ''; }

  // Shared tooltip for every chart: positioned near the pointer or the focused bar.
  var tip = $('chartTip');
  function showTip(el, evt) {
    tip.textContent = '';
    var b = document.createElement('b'); b.textContent = el.getAttribute('data-tip-v'); tip.appendChild(b);
    var k = document.createElement('span'); k.className = 'k'; tip.appendChild(k);
    tip.appendChild(document.createTextNode(el.getAttribute('data-tip-l')));
    tip.hidden = false;
    var r = el.getBoundingClientRect(), x = evt && evt.clientX != null ? evt.clientX : r.left + r.width / 2, y = evt && evt.clientY != null ? evt.clientY : r.top;
    var w = tip.offsetWidth, h = tip.offsetHeight;
    tip.style.left = Math.max(8, Math.min(window.innerWidth - w - 8, x - w / 2)) + 'px';
    tip.style.top = Math.max(8, y - h - 12) + 'px';
  }
  function hideTip() { tip.hidden = true; }
  function bindTips(container) {
    Array.prototype.forEach.call(container.querySelectorAll('.hit'), function (el) {
      el.addEventListener('mousemove', function (e) { showTip(el, e); });
      el.addEventListener('mouseleave', hideTip);
      el.addEventListener('focus', function () { showTip(el); });
      el.addEventListener('blur', hideTip);
    });
  }
  function tableHtml(head, rows) {
    return '<table><tbody><tr><td class="muted">' + esc(head[0]) + '</td><td class="muted">' + esc(head[1]) + '</td></tr>' +
      rows.map(function (r) { return '<tr><td>' + esc(r[0]) + '</td><td>' + esc(fmtN(r[1])) + '</td></tr>'; }).join('') + '</tbody></table>';
  }
  function niceMax(v) { if (v <= 4) return 4; var p = Math.pow(10, Math.floor(Math.log10(v))), n = v / p; return (n <= 2 ? 2 : n <= 5 ? 5 : 10) * p; }
  // top-rounded bar path (4px radius on the data end only)
  function colPath(x, y, w, h) { var r = Math.min(4, w / 2, h); return 'M' + x + ',' + (y + h) + 'V' + (y + r) + 'Q' + x + ',' + y + ' ' + (x + r) + ',' + y + 'H' + (x + w - r) + 'Q' + (x + w) + ',' + y + ' ' + (x + w) + ',' + (y + r) + 'V' + (y + h) + 'Z'; }
  function rowPath(x, y, w, h) { var r = Math.min(4, h / 2, w); return 'M' + x + ',' + y + 'H' + (x + w - r) + 'Q' + (x + w) + ',' + y + ' ' + (x + w) + ',' + (y + r) + 'V' + (y + h - r) + 'Q' + (x + w) + ',' + (y + h) + ' ' + (x + w - r) + ',' + (y + h) + 'H' + x + 'Z'; }

  // Vertical columns. items: [{label, tick, value, tip}]
  function columnChart(id, items, unit, emptyMsg) {
    var el = $(id);
    var total = items.reduce(function (s, i) { return s + i.value; }, 0);
    if (!total) { el.innerHTML = '<div class="chart-empty">' + esc(emptyMsg) + '</div>'; return; }
    var W = 460, H = 190, padL = 30, padB = 22, padT = 16, plotW = W - padL, plotH = H - padB - padT;
    var max = niceMax(Math.max.apply(null, items.map(function (i) { return i.value; })));
    var slot = plotW / items.length, bw = Math.min(24, slot - 2);
    var maxIdx = 0; items.forEach(function (it, i) { if (it.value > items[maxIdx].value) maxIdx = i; });
    var s = '<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' + esc(el.getAttribute('data-label') || '') + '">';
    [0, 0.5, 1].forEach(function (f) {
      var y = padT + plotH * (1 - f);
      s += '<line class="grid" x1="' + padL + '" x2="' + W + '" y1="' + y + '" y2="' + y + '"/><text class="axis-t" x="' + (padL - 6) + '" y="' + (y + 4) + '" text-anchor="end">' + fmtN(max * f) + '</text>';
    });
    items.forEach(function (it, i) {
      var h = it.value ? Math.max(2, plotH * it.value / max) : 0, x = padL + slot * i + (slot - bw) / 2, y = padT + plotH - h;
      s += '<rect class="hit" tabindex="0" x="' + (padL + slot * i) + '" y="' + padT + '" width="' + slot + '" height="' + plotH + '" data-tip-v="' + esc(fmtN(it.value) + ' ' + unit) + '" data-tip-l="' + esc(it.tip) + '" aria-label="' + esc(it.tip + ': ' + it.value + ' ' + unit) + '"/>';
      if (h) s += '<path class="bar" d="' + colPath(x, y, bw, h) + '"/>';
      if (it.tick) s += '<text class="axis-t" x="' + (x + bw / 2) + '" y="' + (H - 6) + '" text-anchor="middle">' + esc(it.tick) + '</text>';
      if ((i === maxIdx || i === items.length - 1) && it.value) s += '<text class="val-t" x="' + (x + bw / 2) + '" y="' + (y - 4) + '" text-anchor="middle">' + fmtN(it.value) + '</text>';
    });
    el.innerHTML = s + '</svg>';
    bindTips(el);
  }

  // Horizontal bars, labels on the left, values at bar end.
  function barList(id, items, unit) {
    var el = $(id);
    if (!items.length) { el.innerHTML = '<div class="chart-empty">No jobs yet.</div>'; return; }
    var longest = Math.max.apply(null, items.map(function (i) { return String(i.label).length; }));
    var W = 460, rowH = 22, gap = 6, padL = Math.min(190, Math.max(90, Math.round(longest * 6.4) + 12)), padR = 48, H = items.length * (rowH + gap);
    var max = Math.max.apply(null, items.map(function (i) { return i.value; }));
    var s = '<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' + esc(el.parentNode.querySelector('.section-title').textContent) + '">';
    items.forEach(function (it, i) {
      var y = i * (rowH + gap), bh = 16, by = y + (rowH - bh) / 2, w = Math.max(2, (W - padL - padR) * it.value / max);
      s += '<rect class="hit" tabindex="0" x="0" y="' + y + '" width="' + W + '" height="' + rowH + '" data-tip-v="' + esc(fmtN(it.value) + ' ' + unit) + '" data-tip-l="' + esc(it.label) + '" aria-label="' + esc(it.label + ': ' + it.value + ' ' + unit) + '"/>';
      s += '<path class="bar" d="' + rowPath(padL, by, w, bh) + '"/>';
      s += '<text class="axis-t" x="' + (padL - 8) + '" y="' + (y + rowH / 2 + 4) + '" text-anchor="end">' + esc(it.label) + '</text>';
      s += '<text class="val-t" x="' + (padL + w + 6) + '" y="' + (y + rowH / 2 + 4) + '">' + fmtN(it.value) + '</text>';
    });
    el.innerHTML = s + '</svg>';
    bindTips(el);
  }

  function recCard(j) {
    var meta = [j.company, j.location, j.is_remote && !/remote/i.test(j.location || '') ? 'Remote' : '', j.date_posted ? 'Posted ' + shortDate(j.date_posted) : '', j.industry && j.industry !== 'Other' ? j.industry : ''].filter(Boolean).map(esc).join(' · ');
    return '<div class="rec"><div class="rec-score" title="Quick-fit score out of 100"><div class="n">' + esc(j.fit_score) + '</div><div class="bar"><i style="width:' + Math.max(0, Math.min(100, j.fit_score)) + '%"></i></div></div>' +
      '<div class="rec-body"><button class="rec-title" data-job="' + esc(j.id) + '">' + esc(j.title) + '</button><div class="rec-meta">' + meta + '</div>' +
      alsoIn(j) + (j.fit_reasons && j.fit_reasons.length ? '<div class="rec-why">' + j.fit_reasons.map(function (r) { return '<span>' + esc(r) + '</span>'; }).join('') + '</div>' : '') + viaLine(j) + '</div>' +
      '<div class="rec-actions"><button class="btn btn-ghost btn-sm" data-job="' + esc(j.id) + '">View</button><button class="btn btn-moss btn-sm" data-save-job="' + esc(j.id) + '">Save</button></div></div>';
  }
  $('dashRecommended').addEventListener('click', function (e) {
    var b = e.target.closest && e.target.closest('[data-save-job]'); if (!b) return;
    e.stopPropagation(); b.disabled = true;
    api('POST', '/applications', { job_id: b.getAttribute('data-save-job') }).then(function () {
      toast('Saved to your pipeline'); b.textContent = 'Saved ✓';
      get('/applications/dashboard').then(renderPipeline).catch(function () {});
    }).catch(function (err) { b.disabled = false; fail(err); });
  });

  var FUNNEL = ['saved', 'applying', 'submitted', 'screening', 'interview', 'assessment', 'offer'];
  function renderPipeline(d) {
    if (!d.total) { $('dashPipeline').innerHTML = '<div class="small muted">Nothing tracked yet. Press <b>Save</b> on a job to start your pipeline.</div>'; return; }
    var max = Math.max.apply(null, FUNNEL.map(function (k) { return d[k] || 0; })) || 1;
    $('dashPipeline').innerHTML = FUNNEL.map(function (k) {
      var v = d[k] || 0;
      return '<div class="pipe-row"><span class="lbl">' + label(k) + '</span><span class="trk">' + (v ? '<i style="width:' + (100 * v / max) + '%"></i>' : '') + '</span><span class="val">' + v + '</span></div>';
    }).join('') + '<div class="small muted" style="margin-top:6px;">' + d.total + ' tracked in total</div>';
  }

  loaders.dashboard = function () {
    get('/profile/completion-score').then(function (c) {
      $('dashCompletionPct').textContent = c.score + '%';
      $('dashCompletionBar').style.width = c.score + '%';
      $('dashMeter').setAttribute('aria-valuenow', c.score);
      $('dashMissing').innerHTML = c.missing_fields && c.missing_fields.length ? 'Missing: ' + c.missing_fields.slice(0, 3).map(esc).join(', ') + (c.missing_fields.length > 3 ? '…' : '') + ' · <a href="#" data-nav="profile">finish</a>' : 'Complete. Nice work.';
    }).catch(fail);

    api('GET', '/jobs/stats').then(function (j) {
      var s = j.data, days = s.added_per_day;
      $('kpiToday').textContent = fmtN(s.new_today);
      var yday = days.length > 1 ? days[days.length - 2].count : 0;
      $('kpiTodaySub').textContent = fmtN(yday) + ' yesterday';
      var smax = Math.max.apply(null, days.map(function (d) { return d.count; })) || 1;
      $('kpiSpark').innerHTML = days.map(function (d, i) { return '<span class="' + (i === days.length - 1 ? 'now' : '') + '" style="height:' + Math.max(8, 100 * d.count / smax) + '%"></span>'; }).join('');
      $('kpiTotal').textContent = fmtN(s.total_active);
      $('kpiTotalSub').textContent = fmtN(s.new_this_week) + ' added in the last 7 days';

      columnChart('chartDaily', days.map(function (d, i) {
        return { value: d.count, tip: shortDate(d.date), tick: (i % 3 === 1 || i === days.length - 1) ? shortDate(d.date) : '' };
      }), 'jobs', 'No new jobs in the last 14 days.');
      $('chartDailyTable').innerHTML = tableHtml(['Day', 'Jobs added'], days.map(function (d) { return [shortDate(d.date), d.count]; }).reverse());

      var regions = s.by_region.slice(0, 7), rest = s.by_region.slice(7).reduce(function (a, r) { return a + r.count; }, 0);
      if (rest) regions.push({ label: 'Everything else', count: rest });
      barList('chartRegions', regions.map(function (r) { return { label: r.label, value: r.count }; }), 'jobs');
      $('chartRegionsTable').innerHTML = tableHtml(['Region', 'Jobs'], s.by_region.map(function (r) { return [r.label, r.count]; }));

      var inds = (s.by_industry || []).filter(function (r) { return r.label !== 'Other'; }).slice(0, 8);
      var otherInd = (s.by_industry || []).reduce(function (a, r) { return a + r.count; }, 0) - inds.reduce(function (a, r) { return a + r.count; }, 0);
      if (otherInd) inds.push({ label: 'Other', count: otherInd });
      barList('chartIndustry', inds.map(function (r) { return { label: r.label, value: r.count }; }), 'jobs');
      $('chartIndustryTable').innerHTML = tableHtml(['Industry', 'Jobs'], (s.by_industry || []).map(function (r) { return [r.label, r.count]; }));
      var src = s.by_source.map(function (r) { return esc(r.label) + ' ' + fmtN(r.count); }).join(' · ');
      $('dashSources').innerHTML = 'Where your feed comes from: ' + src + '. Refreshed every 6 hours. South African listings: ' + ADZUNA_LINK + '.';
    }).catch(function (e) { $('chartDaily').innerHTML = '<div class="chart-empty">' + esc(e.message) + '</div>'; });

    loadingInto('dashRecommended');
    api('GET', '/jobs/recommended?limit=5').then(function (j) {
      jobsFromList(j.data);
      if (j.meta && j.meta.reason === 'no_preferences') {
        $('kpiFits').textContent = '—';
        $('dashRecommended').innerHTML = empty('<b>Tell us what you are looking for.</b><br>Add your target roles and a few skills on <a href="#" data-nav="profile">My Profile</a> and your best matches will show up here.');
        return;
      }
      $('kpiFits').textContent = fmtN(j.meta ? j.meta.candidates : j.data.length);
      $('dashRecommended').innerHTML = j.data.length ? j.data.map(recCard).join('') :
        empty('<b>No strong matches right now.</b><br>Try adding more target roles or skills on your profile. New jobs arrive every 6 hours.');
    }).catch(function (e) { $('dashRecommended').innerHTML = empty(esc(e.message)); });

    get('/applications/dashboard').then(renderPipeline).catch(fail);

    get('/applications/activity?weeks=8').then(function (weeks) {
      columnChart('chartWeekly', weeks.map(function (w, i) {
        return { value: w.submitted, tip: 'Week of ' + shortDate(w.week_start) + ' · ' + w.interviews + ' interview' + (w.interviews === 1 ? '' : 's'), tick: (i % 2 === 1) ? shortDate(w.week_start) : '' };
      }), 'submitted', 'No applications submitted in the last 8 weeks yet. Move a saved job to “Submitted” when you apply.');
      $('chartWeeklyTable').innerHTML = '<table><tbody><tr><td class="muted">Week of</td><td class="muted">Saved</td><td class="muted">Submitted</td><td class="muted">Interviews</td></tr>' +
        weeks.slice().reverse().map(function (w) { return '<tr><td>' + esc(shortDate(w.week_start)) + '</td><td>' + w.saved + '</td><td>' + w.submitted + '</td><td>' + w.interviews + '</td></tr>'; }).join('') + '</tbody></table>';
    }).catch(function (e) { $('chartWeekly').innerHTML = '<div class="chart-empty">' + esc(e.message) + '</div>'; });

    get('/jobs/hidden-gems').then(function (gems) {
      if (!gems.length) {
        $('dashGem').innerHTML = '<div class="panel"><div class="section-title" style="margin:0 0 6px;">💎 Hidden gem of the day</div><div class="small muted">None today. Hidden gems are jobs posted only on a company\'s own careers page, with few applicants. They appear here as soon as the feed finds one.</div></div>';
        return;
      }
      var g = gems[0]; // best fit for this profile, newest first
      $('dashGem').innerHTML = '<div class="hidden-gem-strip"><span class="pill pill-moss">💎 Hidden gem of the day</span>' +
        '<div style="font-weight:600; margin-top:8px;">' + esc(g.title) + (g.company ? ' — ' + esc(g.company) : '') + '</div><div class="small muted">' + esc(g.location || '') + (g.competition_score ? ' · ' + esc(label(g.competition_score)) + ' competition' : '') + '</div>' +
        (g.also_in && g.also_in.length ? '<div class="small muted">Also in ' + g.also_in.slice(0, 2).map(esc).join('; ') + '</div>' : '') +
        '<div class="small muted" style="margin-top:6px;">Posted only on the employer\'s own careers page' + (gems.length > 1 ? ' · <a href="#" data-nav="jobs">' + (gems.length - 1) + ' more</a>' : '') + '</div>' +
        '<button class="btn btn-moss btn-sm" style="margin-top:10px;" data-job="' + esc(g.id) + '">View job</button></div>';
    }).catch(function () { $('dashGem').innerHTML = ''; });
  };
  function jobsFromList(list) { (list || []).forEach(function (x) { jobCache[x.id] = Object.assign(jobCache[x.id] || {}, x); }); }

  // ---------------- PROFILE ----------------
  var LIST_FIELDS = ['desired_roles', 'location_preferences'];
  var NUM_FIELDS = ['years_experience', 'salary_expectation_min', 'salary_expectation_max'];
  loaders.profile = function () {
    loadProfileHeader().then(function () {
      var f = $('profileForm');
      Array.prototype.forEach.call(f.elements, function (el) {
        if (!el.name) return; var v = profile ? profile[el.name] : null;
        el.value = Array.isArray(v) ? v.join(', ') : (v == null ? '' : v);
      });
    });
    renderSkills(); renderEdu(); renderCerts(); renderDocs();
  };
  $('profileForm').addEventListener('submit', function (e) {
    e.preventDefault();
    var d = formData(this), body = {};
    Object.keys(d).forEach(function (k) {
      var v = d[k];
      if (LIST_FIELDS.indexOf(k) >= 0) body[k] = v ? v.split(',').map(function (s) { return s.trim(); }).filter(Boolean) : null;
      else if (NUM_FIELDS.indexOf(k) >= 0) body[k] = v === '' ? null : Number(v);
      else body[k] = v === '' ? null : v;
    });
    if (body.salary_currency) body.salary_currency = body.salary_currency.toUpperCase();
    if (body.salary_expectation_min != null && body.salary_expectation_max != null && body.salary_expectation_max < body.salary_expectation_min) { toast('Max salary must be at least the min salary.', true); return; }
    api('PUT', '/profile', body).then(function () { toast('Profile saved'); return loadMeta(); }).catch(fail);
  });

  // CV + documents
  function renderDocs() {
    get('/profile/documents').then(function (docs) {
      var cv = docs.filter(function (d) { return d.document_type === 'master_cv'; })[0];
      $('cvCurrent').innerHTML = !cv ? '' : '<div class="list-row"><span><span class="pill pill-moss">✓ Current CV</span> ' + esc(cv.file_name) +
        '</span><button class="btn btn-ghost btn-sm" data-download="' + esc(cv.id) + '" data-name="' + esc(cv.file_name) + '">Download</button></div>' +
        (cv.text_extracted ? '' : '<div class="note warn">We couldn\'t read text from this file, so skills weren\'t extracted.</div>');
    }).catch(function () {});
  }
  $('cvFileInput').addEventListener('change', function () {
    var file = this.files[0]; if (!file) return;
    if (file.size > 10 * 1024 * 1024) { toast('File is larger than 10MB.', true); return; }
    var fd = new FormData(); fd.append('file', file);
    $('cvUploadStatus').innerHTML = '<span class="spinner"></span> Uploading and reading ' + esc(file.name) + '…';
    api('POST', '/profile/documents?document_type=master_cv', fd).then(function (doc) {
      var added = doc.skills_added || [];
      toast(added.length ? 'CV uploaded — ' + added.length + ' skill(s) found and added' : 'CV uploaded');
      $('cvUploadStatus').innerHTML = added.length ? '<div class="note">Found in your CV and added to your skills: ' + added.map(esc).join(', ') + '</div>' : '';
      renderDocs(); renderSkills();
    }).catch(function (e) { $('cvUploadStatus').innerHTML = '<div class="note warn">' + esc(e.message) + '</div>'; renderDocs(); });
    this.value = '';
  });
  $('cvCurrent').addEventListener('click', function (e) {
    var b = e.target.closest('[data-download]'); if (!b) return;
    var url = API + '/profile/documents/' + b.dataset.download + '/download';
    var getFile = function () { return fetch(url, { headers: { Authorization: 'Bearer ' + session.access } }); };
    // the sign-in pass expires every 15 minutes: renew it once and retry, like api() does
    getFile()
      .then(function (r) { return r.status === 401 ? doRefresh().then(getFile, function () { return r; }) : r; })
      .then(function (r) {
        if (r.status === 401) { clearSession(); showAuth(); throw new Error('Your session expired — please sign in again.'); }
        if (!r.ok) throw new Error('Download failed (' + r.status + ')');
        return r.blob();
      })
      .then(function (blob) {
        var a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = b.dataset.name || 'cv';
        document.body.appendChild(a); a.click(); setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
      }).catch(fail);
  });

  // skills
  function renderSkills() {
    get('/profile/skills').then(function (skills) {
      $('skillsList').innerHTML = skills.length ? skills.map(function (s) {
        return '<span class="competency-chip" title="' + (s.source === 'cv_extracted' ? 'Found in your CV' : 'Added by you') + '">' + esc(s.name) +
          (s.proficiency ? ' · ' + esc(s.proficiency) : '') + (s.source === 'cv_extracted' ? ' <span class="muted">(CV)</span>' : '') +
          '<button class="chip-x" data-del-skill="' + esc(s.id) + '" title="Remove">×</button></span>';
      }).join('') : '<span class="small muted">No skills yet — add them here, or upload your CV to extract them.</span>';
    }).catch(fail);
  }
  $('skillForm').addEventListener('submit', function (e) {
    e.preventDefault(); var d = formData(this), form = this;
    api('POST', '/profile/skills', { name: d.name, proficiency: d.proficiency || null }).then(function () {
      form.reset(); renderSkills(); toast('Skill added');
    }).catch(fail);
  });
  $('skillsList').addEventListener('click', function (e) {
    var id = e.target.dataset && e.target.dataset.delSkill; if (!id) return;
    api('DELETE', '/profile/skills/' + id).then(renderSkills).catch(fail);
  });

  // education + certifications
  function renderList(elId, path, main, side, delAttr) {
    get(path).then(function (items) {
      $(elId).innerHTML = items.map(function (x) {
        return '<div class="list-row"><span>' + main(x) + '</span><span class="muted">' + side(x) +
          ' <button class="chip-x" ' + delAttr + '="' + esc(x.id) + '" title="Remove">×</button></span></div>';
      }).join('');
    }).catch(fail);
  }
  function renderEdu() { renderList('eduList', '/profile/education', function (x) { return esc(x.qualification) + (x.institution ? ' — ' + esc(x.institution) : ''); }, function (x) { return label(x.status); }, 'data-del-edu'); }
  function renderCerts() { renderList('certList', '/profile/certifications', function (x) { return esc(x.name); }, function (x) { return esc(x.issuer || ''); }, 'data-del-cert'); }
  $('eduList').addEventListener('click', function (e) { var id = e.target.dataset && e.target.dataset.delEdu; if (id) api('DELETE', '/profile/education/' + id).then(renderEdu).catch(fail); });
  $('certList').addEventListener('click', function (e) { var id = e.target.dataset && e.target.dataset.delCert; if (id) api('DELETE', '/profile/certifications/' + id).then(renderCerts).catch(fail); });
  $('eduForm').addEventListener('submit', function (e) {
    e.preventDefault(); var d = formData(this), form = this;
    api('POST', '/profile/education', { qualification: d.qualification, institution: d.institution || null, status: d.status }).then(function () {
      form.reset(); renderEdu(); toast('Education added');
    }).catch(fail);
  });
  $('certForm').addEventListener('submit', function (e) {
    e.preventDefault(); var d = formData(this), form = this;
    api('POST', '/profile/certifications', { name: d.name, issuer: d.issuer || null }).then(function () {
      form.reset(); renderCerts(); toast('Certification added');
    }).catch(fail);
  });

  // ---------------- JOBS ----------------
  var jobPage = 1;
  function jobCard(j) {
    var cls = j.is_hidden_gem ? 'gem' : (j.match_score >= 80 ? 'high-match' : '');
    var sal = j.salary_min || j.salary_max ? money(j.salary_min) + (j.salary_max ? '–' + money(j.salary_max) : '') : '';
    var meta = [j.location, j.is_remote && !/remote/i.test(j.location || '') ? 'Remote' : '', sal, j.date_posted ? 'Posted ' + shortDate(j.date_posted) : ''].filter(Boolean).map(esc).join(' · ');
    var score = j.match_score ? '<div class="match-score ' + (j.match_score >= 80 ? 'high' : j.match_score >= 60 ? 'mid' : 'low') + '">' + esc(j.match_score) + '%</div>' : '';
    return '<div class="job-card ' + cls + '"><div><div class="job-title">' + esc(j.title) + (j.company ? ' — ' + esc(j.company) : '') +
      (j.is_hidden_gem ? ' <span class="pill pill-moss">💎 Hidden Gem</span>' : '') + (j.industry && j.industry !== 'Other' ? '<span class="ind-tag">' + esc(j.industry) + '</span>' : '') + '</div><div class="job-meta">' + meta + '</div>' +
      alsoIn(j) + viaLine(j) + '<div style="margin-top:8px;"><button class="btn btn-ghost btn-sm" data-job="' + esc(j.id) + '">View details</button></div></div>' + score + '</div>';
  }
  function searchParams() {
    var f = $('jobSearchForm'), q = [];
    ['q', 'location', 'industry', 'salary_min', 'remote', 'posted_within_days'].forEach(function (n) {
      var v = (f.elements[n].value || '').trim(); if (v) q.push(n + '=' + encodeURIComponent(v));
    });
    if (f.elements.salary_min.value && !f.elements.include_no_salary.checked) q.push('include_no_salary=false');
    return q;
  }
  function searchJobs(page) {
    jobPage = page || 1;
    var q = searchParams();
    q.push('page=' + jobPage, 'page_size=20');
    loadingInto('jobList'); $('jobCount').textContent = '';
    api('GET', '/jobs/search?' + q.join('&')).then(function (j) {
      j.data.forEach(function (x) { jobCache[x.id] = Object.assign(jobCache[x.id] || {}, x); });
      var total = j.meta.total || 0, pages = Math.ceil(total / 20), filtered = searchParams().length > 0;
      $('jobCount').textContent = total ? total.toLocaleString('en-ZA') + ' job' + (total === 1 ? '' : 's') + (j.meta.postings > total ? ' (' + j.meta.postings.toLocaleString('en-ZA') + ' ads, repeats of the same job grouped)' : '') : '';
      $('jobList').innerHTML = j.data.length ? j.data.map(jobCard).join('') :
        empty(filtered ? '<b>No jobs match those filters.</b><br>Try fewer keywords, a wider area (a province instead of a suburb), or tick “Include jobs that don\'t show a salary”.'
                       : '<b>No jobs yet.</b><br>The feed adds new listings every 6 hours.');
      $('jobPager').innerHTML = pages > 1 ? '<button class="btn btn-ghost btn-sm" ' + (jobPage <= 1 ? 'disabled' : '') + ' data-page="' + (jobPage - 1) + '">‹ Prev</button><span class="small muted">Page ' + jobPage + ' of ' + pages + '</span><button class="btn btn-ghost btn-sm" ' + (jobPage >= pages ? 'disabled' : '') + ' data-page="' + (jobPage + 1) + '">Next ›</button>' : '';
    }).catch(function (e) { $('jobList').innerHTML = empty(esc(e.message)); });
  }
  ['industry', 'salary_min', 'remote', 'posted_within_days', 'include_no_salary'].forEach(function (n) {
    $('jobSearchForm').elements[n].addEventListener('change', function () { searchJobs(1); });
  });
  $('jobClear').onclick = function () {
    var f = $('jobSearchForm'); f.reset(); f.elements.include_no_salary.checked = true; searchJobs(1);
  };

  // Type-ahead: after 2 letters, offer real options from the feed, each with a job count.
  function attachSuggest(input, list, kind) {
    var timer = null, items = [], active = -1, lastQ = null, seq = 0;
    function close() { list.hidden = true; input.setAttribute('aria-expanded', 'false'); active = -1; }
    function paint() {
      list.innerHTML = items.length ? items.map(function (it, i) {
        return '<li role="option" id="' + list.id + '-' + i + '" data-i="' + i + '" aria-selected="' + (i === active) + '"><span>' + esc(it.value) +
          '</span><span class="s-kind">' + esc(it.kind + (it.hint ? ' · ' + it.hint : '')) + ' · <span class="s-n">' + esc(it.count.toLocaleString('en-ZA')) + '</span></span></li>';
      }).join('') : '<li class="s-empty">No matches in the current feed. Press Search to look anyway.</li>';
      list.hidden = false; input.setAttribute('aria-expanded', 'true');
      if (active >= 0) input.setAttribute('aria-activedescendant', list.id + '-' + active); else input.removeAttribute('aria-activedescendant');
    }
    function pick(i) { if (!items[i]) return; input.value = items[i].value; close(); searchJobs(1); }
    input.addEventListener('input', function () {
      clearTimeout(timer);
      var q = input.value.trim();
      if (q.length < 2) { close(); return; }
      timer = setTimeout(function () {
        if (q === lastQ && items.length) { paint(); return; }
        var my = ++seq; lastQ = q;
        get('/jobs/suggest?kind=' + kind + '&q=' + encodeURIComponent(q)).then(function (d) {
          if (my !== seq || document.activeElement !== input) return;
          items = d; active = -1; paint();
        }).catch(function () {});
      }, 180);
    });
    input.addEventListener('keydown', function (e) {
      if (list.hidden) return;
      if (e.key === 'ArrowDown') { e.preventDefault(); active = Math.min(items.length - 1, active + 1); paint(); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); active = Math.max(-1, active - 1); paint(); }
      else if (e.key === 'Enter' && active >= 0) { e.preventDefault(); pick(active); }
      else if (e.key === 'Escape') { close(); }
    });
    list.addEventListener('mousedown', function (e) {
      var li = e.target.closest('li[data-i]'); if (!li) return;
      e.preventDefault(); pick(Number(li.getAttribute('data-i')));
    });
    input.addEventListener('blur', function () { setTimeout(close, 120); });
    $('jobSearchForm').addEventListener('submit', close);
  }
  attachSuggest($('jobQ'), $('jobQList'), 'keyword');
  attachSuggest($('jobLoc'), $('jobLocList'), 'location');
  $('jobPager').addEventListener('click', function (e) { var p = e.target.dataset && e.target.dataset.page; if (p) searchJobs(Number(p)); });
  $('jobSearchForm').addEventListener('submit', function (e) { e.preventDefault(); searchJobs(1); });
  function loadIndustries() {
    get('/jobs/industries').then(function (list) {
      var sel = $('jobIndustry'), cur = sel.value;
      sel.innerHTML = '<option value="">All industries</option>' + list.map(function (i) {
        return '<option value="' + esc(i.label) + '">' + esc(i.label) + ' (' + i.count.toLocaleString('en-ZA') + ')</option>';
      }).join('');
      sel.value = cur;
    }).catch(function () {});
  }
  loaders.jobs = function () {
    loadIndustries();
    searchJobs(jobPage);
    get('/jobs/hidden-gems').then(function (g) {
      $('gemList').innerHTML = g.length ? '<div class="section-title">💎 Hidden gems — posted directly, low competition</div>' + g.slice(0, 3).map(jobCard).join('') + '<div class="section-title" style="margin-top:18px;">All results</div>' : '';
    }).catch(function () {});
  };

  // job detail modal
  document.addEventListener('click', function (e) {
    var b = e.target.closest && e.target.closest('[data-job]'); if (!b) return;
    e.preventDefault(); openJob(b.dataset.job);
  });
  function openJob(id) {
    $('jobModalBody').innerHTML = '<span class="spinner"></span>'; openModal('jobModal');
    get('/jobs/' + id).then(function (j) {
      jobCache[id] = j;
      var sal = j.salary_min || j.salary_max ? money(j.salary_min) + (j.salary_max ? '–' + money(j.salary_max) : '') : '';
      $('jobModalBody').innerHTML = '<h2 style="margin-top:4px;">' + esc(j.title) + (j.company ? ' — ' + esc(j.company) : '') + '</h2>' +
        '<div class="small muted" style="margin-bottom:14px;">' + [j.location, j.is_remote && !/remote/i.test(j.location || '') ? 'Remote' : '', sal, j.date_posted ? 'Posted ' + shortDate(j.date_posted) : '', j.is_hidden_gem ? '💎 Hidden Gem' : ''].filter(Boolean).map(esc).join(' · ') + '</div>' +
        viaLine(j) + '<div id="matchBox"></div>' +
        (j.description ? '<div class="field-label">Description</div><div class="small" style="white-space:pre-wrap; max-height:220px; overflow:auto;">' + esc(j.description) + '</div>' : '') +
        '<div class="row" style="margin-top:18px;">' +
          '<button class="btn btn-primary btn-sm" id="saveJobBtn">Save to pipeline</button>' +
          '<button class="btn btn-ghost btn-sm" id="scoreBtn">Score my match</button>' +
          '<select id="cvVariant" style="width:auto;"><option value="ats">ATS-optimised</option><option value="recruiter_friendly">Recruiter-friendly</option></select>' +
          '<button class="btn btn-ghost btn-sm" id="tailorBtn">Tailor my CV</button>' +
          (j.apply_url ? '<a class="btn btn-ghost btn-sm" href="' + esc(j.apply_url) + '" target="_blank" rel="noopener noreferrer">Apply on site ↗</a>' : '') +
        '</div><div id="aiStatus" class="small" style="margin-top:12px;"></div>';
      showMatch(id);
      $('saveJobBtn').onclick = function () {
        this.disabled = true;
        api('POST', '/applications', { job_id: id }).then(function () { toast('Saved to your pipeline'); }).catch(function (e) { $('saveJobBtn').disabled = false; fail(e); });
      };
      $('scoreBtn').onclick = function () { runScore(id); };
      $('tailorBtn').onclick = function () { runTailor(id, $('cvVariant').value); };
    }).catch(function (e) { $('jobModalBody').innerHTML = empty(esc(e.message)); });
  }
  function showMatch(id) {
    return get('/matches/' + id).then(function (m) {
      var chips = function (a) { return (a || []).map(function (x) { return '<span class="competency-chip">' + esc(typeof x === 'string' ? x : (x.name || x.skill || JSON.stringify(x))) + '</span>'; }).join('') || '<span class="small muted">—</span>'; };
      $('matchBox').innerHTML = '<div class="match-score ' + (m.match_score >= 80 ? 'high' : m.match_score >= 60 ? 'mid' : 'low') + '" style="margin-bottom:10px;">' + esc(m.match_score) + '% match</div>' +
        '<div class="grid-3" style="gap:10px;"><div><div class="field-label" style="margin-top:0;">Strengths</div>' + chips(m.strengths) + '</div><div><div class="field-label" style="margin-top:0;">Missing</div>' + chips(m.missing_skills) + '</div><div><div class="field-label" style="margin-top:0;">Recommended</div>' + chips(m.recommendations) + '</div></div>';
      return true;
    }).catch(function () { $('matchBox').innerHTML = '<div class="small muted">No match score yet for this job.</div>'; return false; });
  }
  function poll(fn, tries, delay) {
    return new Promise(function (resolve, reject) {
      (function tick(n) { fn().then(function (done) { if (done) resolve(done); else if (n <= 0) reject(new Error('timeout')); else setTimeout(function () { tick(n - 1); }, delay); }, reject); })(tries);
    });
  }
  function runScore(id) {
    var st = $('aiStatus'); st.innerHTML = '<span class="spinner"></span> Scoring your fit for this job…'; $('scoreBtn').disabled = true;
    api('POST', '/matches/score?job_id=' + id).then(function () {
      return poll(function () { return showMatch(id); }, 15, 3000);
    }).then(function () { st.textContent = ''; }).catch(function (e) {
      st.innerHTML = '<div class="note warn">' + (e.message === 'timeout' ? 'The match score didn\'t come back. AI scoring needs an OpenAI API key on the server — if one isn\'t set yet, this feature can\'t run.' : esc(e.message)) + '</div>';
    }).finally(function () { var b = $('scoreBtn'); if (b) b.disabled = false; });
  }
  function runTailor(id, variant) {
    var st = $('aiStatus'); st.innerHTML = '<span class="spinner"></span> Tailoring your CV… this can take up to a minute.'; $('tailorBtn').disabled = true;
    api('POST', '/cv/tailor?job_id=' + id + '&variant=' + variant).then(function (j) {
      var task = unwrap(j).task_id;
      return poll(function () {
        return get('/cv/tailor/' + task + '/status').then(function (s) {
          if (s.status === 'SUCCESS') return s; if (s.status === 'FAILURE') throw new Error('failed'); return false;
        });
      }, 30, 3000);
    }).then(function (s) {
      var r = s.result || {};
      st.innerHTML = '<div class="note">Tailored CV ready' + (r.ats_score != null ? ' · ATS score ' + esc(r.ats_score) : '') + '. Find it under Applications once you save this job.</div>';
    }).catch(function (e) {
      st.innerHTML = '<div class="note warn">' + (e.message === 'timeout' || e.message === 'failed' ? 'CV tailoring didn\'t complete. It needs an uploaded CV and an OpenAI API key on the server — if the key isn\'t set yet, this feature can\'t run.' : esc(e.message)) + '</div>';
    }).finally(function () { var b = $('tailorBtn'); if (b) b.disabled = false; });
  }

  // ---------------- APPLICATIONS ----------------
  var STAGES = ['saved', 'applying', 'submitted', 'screening', 'interview', 'assessment', 'offer', 'rejected', 'closed'];
  var ORDER = { saved: 0, applying: 1, submitted: 2, screening: 3, interview: 4, assessment: 5, offer: 6 };
  var TERMINAL = { offer: 1, rejected: 1, closed: 1 };
  function validMove(from, to) { // mirrors backend is_valid_transition
    if (from === to || TERMINAL[from]) return false;
    if (to === 'rejected' || to === 'closed') return true;
    if (to === 'offer' && (ORDER[from] == null ? -1 : ORDER[from]) < ORDER.interview) return false;
    return true;
  }
  loaders.applications = function () {
    $('kanban').innerHTML = '<span class="spinner"></span>';
    get('/applications').then(function (apps) {
      if (!apps.length) { $('kanban').innerHTML = empty('<b>Your pipeline is empty.</b><br>Open any job in Job Search and click <b>Save to pipeline</b>.'); return; }
      return Promise.all(apps.map(function (a) { return getJob(a.job_id).then(function (j) { a.job = j; return a; }); })).then(function () {
        $('kanban').innerHTML = STAGES.map(function (stage) {
          var items = apps.filter(function (a) { return a.stage === stage; });
          if (!items.length && (stage === 'assessment' || stage === 'closed')) return '';
          return '<div class="kanban-col"><div class="kanban-col-head"><span>' + label(stage) + '</span><span>' + items.length + '</span></div>' +
            items.map(function (a) {
              var opts = '<option selected>' + label(a.stage) + '</option>' + STAGES.filter(function (s) { return validMove(a.stage, s); }).map(function (s) { return '<option value="' + s + '">→ ' + label(s) + '</option>'; }).join('');
              return '<div class="kanban-card"><div class="co">' + esc(a.job.company || '—') + '</div><button class="job-link" data-job="' + esc(a.job_id) + '">' + esc(a.job.title) + '</button>' +
                (TERMINAL[a.stage] ? '<div class="small muted" style="margin-top:8px;">Final stage</div>' : '<select data-app="' + esc(a.id) + '">' + opts + '</select>') + '</div>';
            }).join('') + '</div>';
        }).join('');
      });
    }).catch(function (e) { $('kanban').innerHTML = empty(esc(e.message)); });
  };
  $('kanban').addEventListener('change', function (e) {
    var id = e.target.dataset.app, to = e.target.value; if (!id || !to) return;
    api('PUT', '/applications/' + id + '/stage', { stage: to }).then(function () { toast('Moved to ' + label(to)); loaders.applications(); }).catch(function (err) { fail(err); loaders.applications(); });
  });

  // ---------------- ANALYTICS ----------------
  function bars(obj, valueKey) {
    var entries = Object.keys(obj || {}).map(function (k) { var v = obj[k]; return [k, typeof v === 'object' && v ? (v[valueKey] != null ? v[valueKey] : v.applications || v.count || 0) : v]; });
    if (!entries.length) return '<div class="small muted">No data yet.</div>';
    var max = Math.max.apply(null, entries.map(function (e) { return Number(e[1]) || 0; })) || 1;
    return entries.map(function (e) { return '<div class="bar-row"><div class="bar-label">' + esc(label(e[0])) + '</div><div class="bar-track"><div class="bar-fill" style="width:' + ((Number(e[1]) || 0) / max * 100) + '%;"></div></div><div class="bar-value">' + esc(e[1]) + '</div></div>'; }).join('');
  }
  loaders.analytics = function () {
    var p = $('periodSel').value;
    api('GET', '/analytics/summary?period=' + p).then(function (j) {
      var s = j.data;
      $('analyticsNote').innerHTML = j.meta && j.meta.note ? '<div class="note">' + esc(j.meta.note) + '</div>' : '';
      $('analyticsStats').innerHTML = [[s.applications_submitted, 'Applications'], [pct(s.interview_rate), 'Interview rate'], [pct(s.response_rate), 'Response rate'], [s.interviews, 'Interviews'], [s.offers, 'Offers'], [s.avg_time_to_response_days == null ? '—' : s.avg_time_to_response_days + 'd', 'Avg. time to response']]
        .map(function (x) { return '<div class="panel stat"><div class="stat-num">' + esc(x[0]) + '</div><div class="stat-label">' + x[1] + '</div></div>'; }).join('');
    }).catch(fail);
    get('/analytics/by-source?period=' + p).then(function (d) { $('bySource').innerHTML = bars(d, 'applications'); }).catch(fail);
    get('/analytics/by-role?period=' + p).then(function (d) { $('byRole').innerHTML = bars(d, 'applications'); }).catch(fail);
    get('/analytics/trends?period=' + p).then(function (d) {
      $('trends').innerHTML = d && d.length ? d.map(function (r) { return '<div class="list-row"><span>' + esc(r.period_start || r.date || r.week || '') + '</span><span>' + esc(r.applications_submitted != null ? r.applications_submitted + ' applications' : JSON.stringify(r)) + '</span></div>'; }).join('') : '<div class="small muted">No data yet.</div>';
    }).catch(fail);
  };
  $('periodSel').onchange = function () { loaders.analytics(); };

  // ---------------- TRANSITION ----------------
  loaders.transition = function () {
    var src = $('sourceDomainSel').value;
    loadingInto('domainReadiness');
    get('/career-transition/readiness/ranked?source_domain=' + src).then(function (rows) {
      $('domainReadiness').innerHTML = rows.map(function (d) {
        var color = d.readiness_score >= 65 ? 'var(--leaf-deep)' : (d.readiness_score >= 45 ? 'var(--moss-deep)' : 'var(--text-mid)');
        return '<div class="domain-row"><div class="domain-name">' + esc(label(d.target_domain)) + '</div><div class="bar-track" style="flex:1;"><div class="bar-fill" style="width:' + d.readiness_score + '%; background:' + color + ';"></div></div><div class="domain-score" style="color:' + color + ';">' + d.readiness_score + '</div></div>';
      }).join('') + '<div class="small muted" style="margin-top:8px;">Scores rise as you add skills, education and certifications to your profile.</div>';
    }).catch(function (e) { $('domainReadiness').innerHTML = empty(esc(e.message)); });
    get('/career-transition/pathway?source_domain=' + src).then(function (p) {
      $('pathway').innerHTML = '<p style="margin-top:0;">Primary target: <b>' + esc(label(p.primary_target_domain)) + '</b> (readiness ' + esc(p.primary_readiness_score) + ')</p>' +
        (p.secondary_target_domain ? '<p>Secondary: <b>' + esc(label(p.secondary_target_domain)) + '</b></p>' : '') +
        (p.highest_leverage_gap ? '<div class="field-label">Highest-leverage gap to close</div><span class="competency-chip">' + esc(p.highest_leverage_gap) + '</span>' : '') +
        ((p.recommended_certifications || []).length ? '<div class="field-label">Recommended certifications</div>' + p.recommended_certifications.map(function (c) { return '<span class="competency-chip">' + esc(c) + '</span>'; }).join('') : '');
    }).catch(function (e) { $('pathway').innerHTML = empty(esc(e.message)); });
  };
  $('reframeForm').addEventListener('submit', function (e) {
    e.preventDefault(); var d = formData(this);
    api('POST', '/career-transition/reframe?source_domain=' + $('sourceDomainSel').value, d).then(function (j) {
      var f = unwrap(j).reframed_facts || [];
      $('reframeOut').innerHTML = f.length ? f.map(function (x) { return '<p class="small" style="padding:10px; background:var(--paper); border-radius:4px; border-left:3px solid var(--moss); margin:0 0 8px;">' + esc(x) + '</p>'; }).join('')
        : '<div class="note">No reframings matched. Name the specific skills you used — e.g. <i>escalation handling</i>, <i>dispute resolution</i>, <i>KPI management</i>, <i>reporting</i>.</div>';
    }).catch(fail);
  });

  // ---------------- INTERVIEW ----------------
  loaders.interview = function () {
    get('/interview-prep/sessions').then(function (s) {
      $('ivHistory').innerHTML = s.length ? s.map(function (x) { return '<div class="list-row"><span>' + esc(label(x.source_domain)) + ' → ' + esc(label(x.target_domain)) + ' <span class="muted small">' + esc((x.created_at || '').slice(0, 10)) + '</span></span><span>' + (x.readiness_score == null ? '<span class="muted">not finished</span>' : '<b>' + esc(x.readiness_score) + '</b> readiness') + '</span></div>'; }).join('') : '<div class="small muted">No sessions yet.</div>';
    }).catch(fail);
  };
  $('ivStartForm').addEventListener('submit', function (e) {
    e.preventDefault(); var d = formData(this);
    d.behavioral_count = Number(d.behavioral_count); d.technical_count = Number(d.technical_count);
    $('ivSession').innerHTML = '<span class="spinner"></span>';
    api('POST', '/interview-prep/sessions', d).then(function (j) { renderSession(unwrap(j)); loaders.interview(); }).catch(function (err) { $('ivSession').innerHTML = ''; fail(err); });
  });
  function renderSession(s) {
    $('ivSession').innerHTML = '<div class="panel"><div class="section-title">Your questions</div>' + s.questions.map(function (q, i) {
      var tech = q.question_type === 'technical';
      return '<div class="q-card" data-answer="' + esc(q.answer_id) + '"><div class="small muted">' + (i + 1) + ' · ' + (tech ? 'Technical' : 'Behavioural') + (q.target_competency ? ' · ' + esc(q.target_competency) : '') + '</div>' +
        '<p style="font-weight:600; margin:4px 0 8px;">' + esc(q.question) + '</p>' +
        (tech ? '<div class="small muted" style="margin-bottom:6px;">Answer out loud or on paper, then mark yourself honestly.</div><div class="row"><button class="btn btn-ghost btn-sm" data-tech="true">I got it right</button><button class="btn btn-ghost btn-sm" data-tech="false">I struggled</button></div>'
          : '<textarea rows="4" placeholder="Situation → Task → Action → Result"></textarea><button class="btn btn-primary btn-sm" data-score style="margin-top:8px;">Score my answer</button>') +
        '<div class="fb small" style="margin-top:8px;"></div></div>';
    }).join('') + '<button class="btn btn-moss btn-sm" id="ivComplete" style="margin-top:14px;">Finish session</button><div id="ivResult" style="margin-top:12px;"></div></div>';
    var box = $('ivSession');
    box.onclick = function (e) {
      var card = e.target.closest('.q-card');
      if (e.target.id === 'ivComplete') {
        api('POST', '/interview-prep/sessions/' + s.session_id + '/complete').then(function (j) {
          var r = unwrap(j);
          $('ivResult').innerHTML = '<div class="note">Readiness score <b>' + esc(r.readiness_score) + '</b> from ' + esc(r.questions_answered) + ' answered question(s).' + ((r.weak_competencies || []).length ? ' Work on: ' + r.weak_competencies.map(esc).join(', ') + '.' : '') + '</div>';
          loaders.interview();
        }).catch(fail);
        return;
      }
      if (!card) return;
      var fb = card.querySelector('.fb'), body = { answer_id: card.dataset.answer };
      if (e.target.dataset.tech) body.technical_correct = e.target.dataset.tech === 'true';
      else if (e.target.hasAttribute('data-score')) { body.answer_text = card.querySelector('textarea').value.trim(); if (!body.answer_text) { toast('Write your answer first.', true); return; } }
      else return;
      api('POST', '/interview-prep/sessions/' + s.session_id + '/answers', body).then(function (j) {
        var r = unwrap(j);
        if (r.star_score != null) fb.innerHTML = '<span class="pill ' + (r.star_score >= 75 ? 'pill-moss' : 'pill-brick') + '">STAR ' + esc(r.star_score) + '/100</span> ' + ((r.missing_components || []).length ? 'Missing: ' + r.missing_components.map(esc).join(', ') : 'All four STAR parts present.');
        else fb.innerHTML = '<span class="pill pill-leaf">Recorded</span>';
      }).catch(fail);
    };
  }

  // ---------------- BRANDING ----------------
  function brandCheck() {
    loadingInto('brandCheck');
    get('/branding/consistency-check').then(function (c) {
      $('brandCheck').innerHTML = '<div style="display:flex; align-items:center; gap:10px; margin-bottom:12px;"><div class="stat-num" style="font-size:26px;">' + esc(c.consistency_score) + '%</div>' +
        '<span class="pill ' + (c.consistency_score >= 75 ? 'pill-moss' : 'pill-brick') + '">' + (c.consistency_score >= 75 ? 'Looking consistent' : 'Needs attention') + '</span></div>' +
        (c.checks || []).map(function (k) { return '<div class="small" style="padding:7px 0; border-bottom:1px solid var(--paper-line);">' + (k.is_consistent ? '✓' : '✕') + ' &nbsp;' + esc(label(k.field)) + (k.note ? ' — ' + esc(k.note) : '') + '</div>'; }).join('') +
        ((c.generic_language_flags || []).length ? '<div class="field-label">Generic phrases to replace</div>' + c.generic_language_flags.map(function (g) { return '<span class="competency-chip">' + esc(g) + '</span>'; }).join('') : '');
    }).catch(function (e) { $('brandCheck').innerHTML = '<div class="small muted">' + (e.status === 404 ? 'Save your LinkedIn headline first to run the check.' : esc(e.message)) + '</div>'; });
  }
  loaders.branding = function () {
    var b = storeJSON(ukey('ascend_brand')) || {};
    $('brandForm').elements.linkedin_headline.value = b.linkedin_headline || '';
    $('brandForm').elements.linkedin_summary.value = b.linkedin_summary || '';
    brandCheck();
  };
  $('brandForm').addEventListener('submit', function (e) {
    e.preventDefault(); var d = formData(this); storeJSON(ukey('ascend_brand'), d);
    api('PUT', '/branding', { linkedin_headline: d.linkedin_headline || null, linkedin_summary: d.linkedin_summary || null }).then(function () { toast('Saved'); brandCheck(); }).catch(fail);
  });
  $('brandSuggestBtn').onclick = function () {
    get('/branding/headline-suggestion?target_domain_label=' + encodeURIComponent(label($('brandTarget').value))).then(function (s) {
      $('brandSuggestion').innerHTML = '<p class="small" style="padding:10px; background:var(--paper); border-radius:4px; border-left:3px solid var(--moss); margin:0 0 8px;">' + esc(s.suggested_headline) + '</p><button class="btn btn-ghost btn-sm" id="useHeadline">Use this headline</button>';
      $('useHeadline').onclick = function () { $('brandForm').elements.linkedin_headline.value = s.suggested_headline; toast('Copied into your headline — click Save & check.'); };
    }).catch(fail);
  };

  // ---------------- INTELLIGENCE ----------------
  loaders.intelligence = function () {
    loadingInto('intelCompanies'); loadingInto('intelRecruiters');
    var noData = 'Not enough data yet. Recruiter intelligence is pooled from users who share outcomes, and only shown once 5+ people contribute — it fills in as the platform gets used.';
    get('/recruiter-intelligence/companies?source_domain=' + $('intelSource').value).then(function (rows) {
      $('intelCompanies').innerHTML = rows.length ? rows.map(function (c) { return '<div class="list-row"><span><b>' + esc(c.company_name) + '</b> <span class="muted small">' + esc(c.contributing_user_count) + ' contributors</span></span><span>' + (c.insufficient_data ? '<span class="muted">insufficient data</span>' : 'Interview rate ' + pct(c.interview_rate_overall) + (c.avg_turnaround_days != null ? ' · ' + esc(c.avg_turnaround_days) + 'd turnaround' : '')) + '</span></div>'; }).join('') : '<div class="small muted">' + noData + '</div>';
    }).catch(function (e) { $('intelCompanies').innerHTML = '<div class="small muted">' + esc(e.message) + '</div>'; });
    get('/recruiter-intelligence/recruiters').then(function (rows) {
      $('intelRecruiters').innerHTML = rows.length ? rows.map(function (r) { return '<div class="list-row"><span><b>' + esc(r.recruiter_name) + '</b> <span class="muted small">' + esc(r.company || '') + '</span></span><span>' + (r.insufficient_data ? '<span class="muted">insufficient data</span>' : 'Response rate ' + pct(r.response_rate)) + '</span></div>'; }).join('') : '<div class="small muted">' + noData + '</div>';
    }).catch(function (e) { $('intelRecruiters').innerHTML = '<div class="small muted">' + esc(e.message) + '</div>'; });
  };

  // ---------------- SETTINGS ----------------
  loaders.settings = function () { $('consentToggle').checked = store(ukey('ascend_consent')) === '1'; };
  $('consentToggle').onchange = function () {
    var on = this.checked, box = this;
    api('PUT', '/recruiter-intelligence/settings/pooled-analytics-consent', { contributes_to_pooled_analytics: on }).then(function () {
      store(ukey('ascend_consent'), on ? '1' : '0'); toast(on ? 'Thanks — you\'re contributing anonymised outcomes.' : 'You\'ve stopped contributing.');
    }).catch(function (e) { box.checked = !on; fail(e); });
  };

  // ---------------- boot ----------------
  if (session && session.access) showApp(false); else { setAuthMode('login'); showAuth(); }
})();
