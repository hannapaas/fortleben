/* The editors' desk: start a translation, watch it, resume an interrupted one, and at the checkpoint
   send the house notes and approve the draft.
   Runs go on in the background on the server; this page only asks how they're getting on, every
   five seconds, until each is done, has failed, was interrupted or is waiting at the checkpoint.
   The checkpoint is drawn by the server, so when a run reaches it, or the house has answered a
   note, the page reloads. A run's row is drawn the same way as in desk.html, so keep the wording in step. */
(function () {
  var form = document.getElementById('desk');
  if (!form) return;
  var base = form.dataset.base;  // /desk when signed in, /desk/<token> from an invite link
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
    return { queued: 'Queued.', running: 'In progress: ' + s + '.', waiting: 'Waiting for you.', done: 'Done: ' + s + '.',
             failed: 'Failed at ' + s + '.', interrupted: 'Interrupted at ' + s + '.' }[r.status] || esc(r.status) + '.';
  }

  function row(r) {
    var li = document.createElement('li');
    li.className = 'run st-' + r.status;
    li.dataset.run = r.id;
    li.dataset.status = r.status;
    var h = '<span class="rt"><i>' + esc(r.title_en) + '</i> <span class="sm">started ' + esc(r.started) + '</span></span>' +
      '<span class="rs" aria-live="polite">' + status(r) + ' <span class="sm">' + (r.spent_words ? esc(r.spent_words) : n(r.spent) + ' drops spent' +
      (r.held ? ', ' + n(r.held) + ' still held' : '') + '.') + '</span></span>';
    if (r.status === 'done' && r.edition_url) h += '<a class="read" href="' + esc(r.edition_url) + '">Read it</a>';
    if (r.status === 'waiting') h += '<a class="read" href="#checkpoint-' + esc(r.id) + '">Read the analysis</a>';
    if (r.status === 'interrupted' || r.status === 'failed') h += '<span class="rr">' +
      (r.resumable === false ? '' : '<button type="button" class="btn resume">Resume</button>') +
      '<span class="sm">' + (r.status === 'failed' && r.failure ? esc(r.failure) :
        'It carries on from the last finished stage; nothing is paid for twice.') + '</span>' +
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
      // The header a form on another site can't send: the server refuses desk changes without it.
      headers: body ? { 'Content-Type': 'application/json', 'X-Requested-With': 'fetch' } : { 'X-Requested-With': 'fetch' },
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
        else if (r.status === 'waiting' && !document.getElementById('checkpoint-' + r.id)) location.reload();
        else { watching[id] = false; finished(r); }
      }, function () { setTimeout(tick, EVERY); });  // offline for a moment: keep asking
    })();
  }

  // Once nothing of yours is running, another translation can be started, with a fresh allowance.
  function finished() {
    if (Object.keys(watching).some(function (k) { return watching[k]; })) return;
    // Opened while a run was going: the page says so and Start is off, so draw it afresh.
    if (!form.dataset.started && document.querySelector('#busy[data-going]')) { location.reload(); return; }
    if (form.dataset.started) say(err, '');
    var again = document.getElementById('again');
    if (form.dataset.started && !again) {
      again = document.createElement('p');
      again.id = 'again'; again.className = 'line';
      again.innerHTML = '<a href="">Start another translation</a>';
      err.parentNode.appendChild(again);
    }
  }

  function chosen() { return form.querySelector('input[name="work"]:checked'); }

  // What starting would hold, for the work picked.
  function picked(r) {
    var holdn = document.getElementById('holdn'), hold = document.getElementById('hold');
    if (holdn) holdn.textContent = n(r.dataset.estimate);
    if (hold && !form.dataset.own) hold.hidden = false;
    say(err, '');
  }
  form.querySelectorAll('input[name="work"]').forEach(function (r) {
    r.addEventListener('change', function () { picked(r); });
  });

  // A work added from a link to Aozora Bunko: the server reads its card and checks the rights,
  // and the work joins the list, picked. Its row is drawn as desk.html draws one, so keep them in step.
  var addform = document.getElementById('addwork');
  var works = document.getElementById('works');
  function workRow(w) {
    var own = !!form.dataset.own, avail = Number(form.dataset.available);
    var label = document.createElement('label');
    label.className = 'work' + (w.covered ? '' : ' short');
    var meta = esc(w.author_en) + (w.year ? ', ' + esc(w.year) : '') + ' · ' + esc(w.sheets) + ' sheets';
    meta += own ? '.' + (w.covered ? '' : ' Longer than one run here may spend.')
      : ' · ' + n(w.estimate) + ' drops. ' + (w.covered ? 'Your allowance covers it.' : 'That\'s ' + n(w.estimate - avail) + ' more than you have.');
    label.innerHTML = '<input type="radio" name="work" value="' + esc(w.id) + '" data-estimate="' + esc(w.estimate) +
      '" data-title="' + esc(w.title_en) + '"' + (w.covered ? '' : ' disabled') + '>' +
      '<span class="bx r" aria-hidden="true"></span><span class="wb">' +
      '<span class="wj" lang="ja">' + esc(w.title) + '</span> <span class="wt">' + esc(w.title_en) + '</span>' +
      '<span class="meta">' + meta + '</span>' +
      (w.blurb ? '<span class="meta blurb">' + esc(w.blurb) + '</span>' : '') +
      (w.has_edition ? '<span class="meta">Already on the shelf. Yours would be a separate edition, under your credit.</span>' : '') +
      (w.added ? '<span class="meta added">Added from Aozora</span>' : '') + '</span>';
    var input = label.querySelector('input');
    input.addEventListener('change', function () { picked(input); });
    return label;
  }
  if (addform) addform.addEventListener('submit', function (e) {
    e.preventDefault();
    var box = document.getElementById('aozora-url'), add = document.getElementById('add'), msg = document.getElementById('adderr');
    var url = box.value.trim();
    if (!url) { say(msg, 'Paste a link first.'); box.focus(); return; }
    say(msg, '');
    add.disabled = true;
    add.textContent = 'Reading the card…';
    json('POST', base + '/works', { url: url }).then(function (w) {
      add.disabled = false;
      add.textContent = 'Add';
      if (w.error || !w.id) { say(msg, w.error || 'It wasn\'t added. Try again.'); return; }
      var input = works.querySelector('input[name="work"][value="' + w.id.replace(/["\\]/g, '') + '"]');
      var label = input ? input.closest('.work') : workRow(w);
      if (!input) {
        works.insertBefore(label, works.firstChild);
        input = label.querySelector('input');
      }
      works.hidden = false;
      ['noworks', 'noneopen'].forEach(function (id) { var el = document.getElementById(id); if (el && w.covered) el.hidden = true; });
      box.value = '';
      if (!input.disabled && !form.dataset.started) {
        input.checked = true;
        picked(input);
        if (!form.dataset.unstartable) start.disabled = false;
      }
      label.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }, function () {
      add.disabled = false;
      add.textContent = 'Add';
      say(msg, 'Couldn\'t reach Fortleben. Try again.');
    });
  });

  function lock(on) {
    form.querySelectorAll('input[name="work"], input[name="credit"]').forEach(function (i) {
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
    var credit = form.querySelector('input[name="credit"]:checked');
    say(err, '');
    lock(true);
    start.textContent = 'Starting…';
    json('POST', base + '/runs', { work: w.value, agree: true, credit: credit ? credit.value : '', estimate: Number(w.dataset.estimate) }).then(function (d) {
      if (!d.run_id) {
        lock(false);
        start.textContent = 'Start';
        say(err, d.error || 'It didn\'t start. Try again.');
        return;
      }
      form.dataset.started = '1';
      start.textContent = 'Started';
      hold(Number(w.dataset.estimate));
      var own = !document.getElementById('avail');  // a desk with its own key holds no drops
      put({ id: d.run_id, title_en: w.dataset.title, status: 'queued', stage_label: '', spent: 0,
            held: own ? 0 : Number(w.dataset.estimate), spent_words: own ? 'Nothing spent from your key.' : null,
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
    if (!document.getElementById('avail')) return;
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

  // The checkpoint: a note is read in the background, and the page reloads with the house's reply.
  document.querySelectorAll('.checkpoint').forEach(function (cp) {
    var id = cp.dataset.run, url = base + '/runs/' + id;
    var send = cp.querySelector('.send'), approve = cp.querySelector('.approve');
    var box = cp.querySelector('.note-box'), msg = cp.querySelector('.err'), reading = cp.querySelector('.reading-note');
    var full = !!cp.dataset.full;  // the house has no room, or runs can't start here
    function voice() { var v = cp.querySelector('input[type="radio"]:checked'); return v ? Number(v.value) : 0; }
    function busy(on) { send.disabled = on; approve.disabled = on || full; reading.hidden = !on; }

    // Ask until a new round is in, or the house has stopped reading (a failed note says so on reload).
    function wait(before) {
      json('GET', url).then(function (r) {
        if (r.error || !r.id) { busy(false); say(msg, r.error || 'Couldn\'t reach Fortleben. Reload the page.'); return; }
        if (r.rounds > before || !r.steering || r.status !== 'waiting') location.reload();
        else setTimeout(function () { wait(before); }, EVERY);
      }, function () { setTimeout(function () { wait(before); }, EVERY); });
    }

    send.addEventListener('click', function () {
      var note = box.value.trim();
      if (!note) { say(msg, 'Write a note first.'); box.focus(); return; }
      say(msg, '');
      busy(true);
      json('POST', url + '/steer', { note: note, voice: voice() }).then(function (d) {
        if (d.error || !d.ok) { busy(false); say(msg, d.error || 'The note didn\'t go. Try again.'); return; }
        wait(Number(cp.dataset.rounds));
      }, function () { busy(false); say(msg, 'Couldn\'t reach Fortleben. Try again.'); });
    });

    approve.addEventListener('click', function () {
      say(msg, '');
      send.disabled = approve.disabled = true;
      approve.textContent = 'Approving…';
      json('POST', url + '/approve', { voice: voice() }).then(function (d) {
        if (d.error || !d.ok) {
          send.disabled = false; approve.disabled = full; approve.textContent = 'Approve and draft';
          say(msg, d.error || 'It didn\'t go. Try again.');
          return;
        }
        location.reload();
      }, function () {
        send.disabled = false; approve.disabled = full; approve.textContent = 'Approve and draft';
        say(msg, 'Couldn\'t reach Fortleben. Try again.');
      });
    });

    if (cp.dataset.steering) wait(Number(cp.dataset.rounds));
  });
})();
