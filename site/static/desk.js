/* The editors' desk: start a translation, watch it, resume an interrupted one.
   Runs go on in the background on the server; this page only asks how they're getting on, every
   five seconds, until each is done, has failed or was interrupted. A run's row is drawn the same
   way as in desk.html, so keep the wording in step. */
(function () {
  var form = document.getElementById('desk');
  if (!form) return;
  var base = '/desk/' + encodeURIComponent(form.dataset.token);
  var runs = document.getElementById('runs');
  var start = document.getElementById('start');
  var err = document.getElementById('err');
  var EVERY = 5000;
  var watching = {};

  function n(x) { return Number(x || 0).toLocaleString('en-GB'); }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function say(el, text) { el.textContent = text || ''; el.hidden = !text; }

  function status(r) {
    var s = esc(r.stage_label);
    return { queued: 'Queued.', running: 'In progress: ' + s + '.', done: 'Done: ' + s + '.',
             failed: 'Failed at ' + s + '.', interrupted: 'Interrupted at ' + s + '.' }[r.status] || esc(r.status) + '.';
  }

  function row(r) {
    var li = document.createElement('li');
    li.className = 'run st-' + r.status;
    li.dataset.run = r.id;
    li.dataset.status = r.status;
    var h = '<span class="rt"><i>' + esc(r.title_en) + '</i> <span class="sm">started ' + esc(r.started) + '</span></span>' +
      '<span class="rs" aria-live="polite">' + status(r) + ' <span class="sm">' + n(r.spent) + ' drops spent' +
      (r.reserved ? ', ' + n(r.reserved) + ' still held' : '') + '.</span></span>';
    if (r.status === 'done' && r.edition_url) h += '<a class="read" href="' + esc(r.edition_url) + '">Read it</a>';
    if (r.status === 'interrupted') h += '<span class="rr"><button type="button" class="btn resume">Resume</button>' +
      '<span class="sm">It carries on from the last finished stage; nothing is paid for twice.</span>' +
      '<span class="err" aria-live="polite" hidden></span></span>';
    li.innerHTML = h;
    return li;
  }

  function put(r) {
    var old = runs.querySelector('[data-run="' + r.id + '"]');
    var li = row(r);
    // Keep the old row's live region when the words haven't changed, so a screen reader isn't told twice.
    if (old && old.dataset.status === r.status && old.innerHTML === li.innerHTML) return;
    if (old) runs.replaceChild(li, old); else runs.insertBefore(li, runs.firstChild);
    document.getElementById('noruns').hidden = true;
  }

  function json(method, url, body) {
    return fetch(url, {
      method: method, credentials: 'same-origin',
      headers: body ? { 'Content-Type': 'application/json' } : {},
      body: body ? JSON.stringify(body) : undefined
    }).then(function (res) {
      return res.json().catch(function () { return {}; }).then(function (d) {
        if (!res.ok && !d.error) d.error = 'The server said no (' + res.status + ').';
        return d;
      });
    });
  }

  var ACTIVE = { queued: true, running: true };
  function watch(id) {
    if (watching[id]) return;
    watching[id] = true;
    (function tick() {
      json('GET', base + '/runs/' + id).then(function (r) {
        if (r.error || !r.id) { watching[id] = false; return; }
        put(r);
        if (ACTIVE[r.status]) setTimeout(tick, EVERY);
        else { watching[id] = false; finished(r); }
      }, function () { setTimeout(tick, EVERY); });  // offline for a moment: keep asking
    })();
  }

  // Once nothing of yours is running, another translation can be started, with a fresh allowance.
  function finished() {
    if (Object.keys(watching).some(function (k) { return watching[k]; })) return;
    if (form.dataset.started) say(err, '');
    var again = document.getElementById('again');
    if (form.dataset.started && !again) {
      again = document.createElement('p');
      again.id = 'again'; again.className = 'line';
      again.innerHTML = '<a href="">Reload the page</a> to start another.';
      err.parentNode.appendChild(again);
    }
  }

  function chosen() { return form.querySelector('input[name="work"]:checked'); }

  // What starting would hold, for the work picked.
  form.querySelectorAll('input[name="work"]').forEach(function (r) {
    r.addEventListener('change', function () {
      document.getElementById('holdn').textContent = n(r.dataset.estimate);
      say(err, '');
    });
  });
  var agree = document.getElementById('agree');
  agree.addEventListener('change', function () { if (agree.checked) say(err, ''); });

  function lock(on) {
    form.querySelectorAll('input[name="work"], input[name="credit"], #agree').forEach(function (i) {
      if (on) { i.dataset.was = i.disabled ? '1' : ''; i.disabled = true; }
      else i.disabled = i.dataset.was === '1';
    });
    start.disabled = on;
  }

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    if (start.disabled) return;
    var w = chosen();
    if (!w) { say(err, 'Pick a work first.'); return; }
    if (!agree.checked) { say(err, 'Tick Published? first: everything translated here is published.'); agree.focus(); return; }
    var credit = form.querySelector('input[name="credit"]:checked');
    say(err, '');
    lock(true);
    start.textContent = 'Starting…';
    json('POST', base + '/runs', { work: w.value, agree: true, credit: credit ? credit.value : '' }).then(function (d) {
      if (!d.run_id) {
        lock(false);
        start.textContent = 'Start';
        say(err, d.error || 'It didn\'t start. Try again.');
        return;
      }
      form.dataset.started = '1';
      start.textContent = 'Started';
      hold(Number(w.dataset.estimate));
      put({ id: d.run_id, title_en: w.dataset.title, status: 'queued', stage_label: '', reserved: Number(w.dataset.estimate), spent: 0,
            started: new Date().toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) });
      runs.firstChild.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      watch(d.run_id);
    }, function () {
      lock(false);
      start.textContent = 'Start';
      say(err, 'Couldn\'t reach Fortleben. Try again.');
    });
  });

  // The whole estimate comes off the allowance when a run starts.
  function hold(drops) {
    var d = form.dataset, granted = +d.granted, spent = +d.spent, reserved = +d.reserved + drops;
    document.getElementById('avail').textContent = n(Math.max(0, +d.available - drops));
    document.getElementById('altail').textContent = n(granted) + ' granted, ' + n(spent) + ' spent, ' + n(reserved) + ' held for a translation in progress.';
  }

  runs.addEventListener('click', function (e) {
    var b = e.target.closest('.resume');
    if (!b) return;
    var li = b.closest('.run'), id = li.dataset.run, msg = li.querySelector('.err');
    b.disabled = true;
    b.textContent = 'Resuming…';
    say(msg, '');
    json('POST', base + '/runs/' + id + '/resume').then(function (d) {
      if (d.error || !d.ok) {
        b.disabled = false; b.textContent = 'Resume';
        say(msg, d.error || 'It didn\'t resume. Try again.');
        return;
      }
      watch(id);
    }, function () {
      b.disabled = false; b.textContent = 'Resume';
      say(msg, 'Couldn\'t reach Fortleben. Try again.');
    });
  });

  // Runs already going when the page opened are watched too.
  runs.querySelectorAll('.run').forEach(function (li) { if (ACTIVE[li.dataset.status]) watch(li.dataset.run); });
})();
