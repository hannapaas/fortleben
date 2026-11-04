/* The editors' desk, on its three pages: your desk (your translations, watched while they run), a new translation
   (pick a work and start it, then go to its page), and a translation's own page (how far it has got, and at the
   checkpoint the files, notes and approval).
   Runs go on in the background on the server; these pages only ask how they're getting on, every five seconds.
   A translation's page is drawn by the server, so when its run moves on a stage, reaches the checkpoint, or the
   house has answered a note, the page reloads. A run's row is drawn the same way as in desk_parts.html, so keep
   the wording in step. */
(function () {
  var page = document.querySelector('#home, #desk, #run');
  if (!page) return;
  var base = page.dataset.base;  // /desk when signed in, /desk/<token> from an invite link
  var runs = document.getElementById('runs');
  var onRun = page.id === 'run';
  var EVERY = 5000;
  var watching = {};
  var leaving = false;  // set when the page reloads itself, so nothing on it is saved twice

  function n(x) { return Number(x || 0).toLocaleString('en-GB'); }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function say(el, text) { el.textContent = text || ''; el.hidden = !text; }
  function reload() { leaving = true; location.reload(); }

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

  // ---------- A translation's row: on your desk, and at the top of its own page ----------
  function status(r) {
    var s = esc(r.stage_label);
    return { queued: 'Queued.', running: 'In progress: ' + s + '.', waiting: 'Waiting for you.', done: 'Done: ' + s + '.',
             failed: 'Failed at ' + s + '.', interrupted: 'Interrupted at ' + s + '.' }[r.status] || esc(r.status) + '.';
  }

  function row(r) {
    var li = document.createElement('li'), url = base + '/translations/' + esc(r.id);
    li.className = 'run st-' + r.status;
    li.dataset.run = r.id;
    li.dataset.status = r.status;
    li.dataset.stage = r.stage || '';
    var h = '<span class="rt"><a href="' + url + '"><i>' + esc(r.title_en) + '</i></a> <span class="sm">started ' + esc(r.started) + '</span></span>' +
      '<span class="rs" aria-live="polite">' + status(r) + ' <span class="sm">' + (r.spent_words ? esc(r.spent_words) : n(r.spent) + ' drops spent' +
      (r.held ? ', ' + n(r.held) + ' still held' : '') + '.') + '</span></span>';
    if (r.status === 'done' && r.edition_url) h += '<a class="read" href="' + esc(r.edition_url) + '">Read it</a>';
    if (r.status === 'done' && r.edit_url) h += '<a class="read" href="' + esc(r.edit_url) + '">Edit it</a>';
    if (r.status === 'waiting') h += '<a class="read" href="' + url + '">Review and approve</a>';
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
  }

  var ACTIVE = { queued: true, running: true };
  function watch(id) {
    if (watching[id]) return;
    watching[id] = true;
    (function tick() {
      json('GET', base + '/runs/' + id).then(function (r) {
        if (r.error || !r.id) { watching[id] = false; return; }
        var li = runs.querySelector('[data-run="' + r.id + '"]');
        // On its own page the stages are drawn by the server: a run that has moved on is drawn again.
        if (onRun && li && (li.dataset.status !== r.status || li.dataset.stage !== (r.stage || ''))) return reload();
        put(r);
        if (ACTIVE[r.status]) setTimeout(tick, EVERY);
        else watching[id] = false;
      }, function () { setTimeout(tick, EVERY); });  // offline for a moment: keep asking
    })();
  }

  if (runs) {
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
        if (onRun) return reload();
        watch(id);
      }, function () {
        b.disabled = false; b.textContent = 'Resume';
        say(msg, 'Couldn\'t reach Fortleben. Try again.');
      });
    });
    // Runs already going when the page opened are watched.
    runs.querySelectorAll('.run').forEach(function (li) { if (ACTIVE[li.dataset.status]) watch(li.dataset.run); });
  }

  // ---------- A new translation: pick a work, or add one from a link, and start it ----------
  var form = page.id === 'desk' ? page : null;
  if (form) (function () {
  var start = document.getElementById('start');
  var err = document.getElementById('err');
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
      var meta = esc(w.author_en || w.author) + (w.year ? ', ' + esc(w.year) : '') + ' · ' + esc(w.sheets) + ' sheets';
      meta += own ? '.' + (w.covered ? '' : ' Longer than one run here may spend.')
        : ' · ' + n(w.estimate) + ' drops. ' + (w.covered ? 'Your allowance covers it.' : 'That\'s ' + n(w.estimate - avail) + ' more than you have.');
      label.innerHTML = '<input type="radio" name="work" value="' + esc(w.id) + '" data-estimate="' + esc(w.estimate) +
        '" data-title="' + esc(w.title_en || w.title) + '"' + (w.covered ? '' : ' disabled') + '>' +
        '<span class="bx r" aria-hidden="true"></span><span class="wb">' +
        '<span class="wj" lang="ja">' + esc(w.title) + '</span>' + (w.title_en ? ' <span class="wt">' + esc(w.title_en) + '</span>' : '') +
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
      var credit = form.querySelector('input[name="credit"]');
      var accent = form.querySelector('input[name="accent"]:checked');
      say(err, '');
      lock(true);
      start.textContent = 'Starting…';
      json('POST', base + '/runs', { work: w.value, agree: true, credit: credit ? credit.value.trim() : '', accent: accent ? accent.value : '', estimate: Number(w.dataset.estimate) }).then(function (d) {
        if (!d.run_id) {
          lock(false);
          start.textContent = 'Start';
          say(err, d.error || 'It didn\'t start. Try again.');
          return;
        }
        form.dataset.started = '1';
        location.href = base + '/translations/' + d.run_id;  // its own page, where it can be watched
      }, function () {
        lock(false);
        start.textContent = 'Start';
        say(err, 'Couldn\'t reach Fortleben. Try again.');
      });
    });
  })();

  // ---------- The checkpoint, on a translation's page ----------
  // A file is saved with its Save button, with Ctrl or Cmd and S, before a note or the approval goes, and when
  // the page is left with it changed, so nothing typed is lost.
  document.querySelectorAll('.checkpoint').forEach(function (cp) {
    var id = cp.dataset.run, url = base + '/runs/' + id;
    var send = cp.querySelector('.send'), approve = cp.querySelector('.approve');
    var box = cp.querySelector('.note-box'), msg = cp.querySelector('.err'), reading = cp.querySelector('.reading-note');
    var full = !!cp.dataset.full;  // the house has no room, or runs can't start here
    var files = Array.prototype.slice.call(cp.querySelectorAll('.file'));
    function voice() { var v = cp.querySelector('input[type="radio"]:checked'); return v ? Number(v.value) : 0; }
    function busy(on) {
      send.disabled = on; approve.disabled = on || full; reading.hidden = !on;
      files.forEach(function (f) { f.querySelector('.file-box').readOnly = on; f.querySelector('.save').disabled = on || !f.querySelector('.file-box').dataset.dirty; });
      cp.querySelectorAll('.vname, .vtext').forEach(function (el) { el.readOnly = on; });
    }

    // Each file reads as part of the page: its box is as tall as its text, so the page is the only thing that scrolls.
    files.forEach(function (f) {
      var save = f.querySelector('.save'), fbox = f.querySelector('.file-box'), said = f.querySelector('.saved');
      var was = fbox.value;
      function fit() { fbox.style.height = 'auto'; fbox.style.height = (fbox.scrollHeight + fbox.offsetHeight - fbox.clientHeight) + 'px'; }
      function mark() {
        if (fbox.value === was) delete fbox.dataset.dirty; else fbox.dataset.dirty = '1';
        save.disabled = !fbox.dataset.dirty || fbox.readOnly;
      }
      f.saveNow = function () {  // resolves true once saved (or nothing to save), false if it couldn't be
        if (!fbox.dataset.dirty) return Promise.resolve(true);
        var text = fbox.value;
        save.disabled = true;
        say(said, 'Saving…');
        return json('POST', url + '/files/' + f.dataset.file, { text: text }).then(function (d) {
          if (d.error || !d.ok) { mark(); say(said, d.error || 'It didn\'t save. Try again.'); return false; }
          was = text; mark();
          say(said, fbox.dataset.dirty ? 'Not saved yet.' : 'Saved.');
          return true;
        }, function () { mark(); say(said, 'Couldn\'t reach Fortleben. Try again.'); return false; });
      };
      f.leave = function () {  // the page is going: send what's unsaved in a request that outlives it
        if (!fbox.dataset.dirty || leaving) return;
        fetch(url + '/files/' + f.dataset.file, { method: 'POST', keepalive: true, credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'fetch' }, body: JSON.stringify({ text: fbox.value }) });
      };
      fbox.addEventListener('input', function () { fit(); mark(); say(said, fbox.dataset.dirty ? 'Not saved yet.' : ''); });
      fbox.addEventListener('keydown', function (e) {
        if (e.key === 's' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); f.saveNow(); }
      });
      save.addEventListener('click', function () { f.saveNow(); });
      fit();
      addEventListener('resize', fit);
    });
    addEventListener('pagehide', function () { files.forEach(function (f) { f.leave(); }); });

    // The voice: the picked one shows its name and line as fields; what's in the fields is the voices file.
    var voices = cp.querySelector('.voices.file');
    if (voices) {
      var hidden = voices.querySelector('.file-box');
      var each = Array.prototype.slice.call(voices.querySelectorAll('.voice'));
      var written = function () {
        return each.map(function (v, i) {
          return '## Voice ' + i + ': ' + v.querySelector('.vname').value.trim() + '\n\n' + v.querySelector('.vtext').value.trim();
        }).join('\n\n');
      };
      each.forEach(function (v) {
        var t = v.querySelector('.vtext');
        function fitLine() { t.style.height = 'auto'; t.style.height = (t.scrollHeight + t.offsetHeight - t.clientHeight) + 'px'; }
        v.querySelectorAll('.vname, .vtext').forEach(function (el) {
          el.addEventListener('input', function () {
            if (el === t) fitLine();
            v.querySelector('.opt b').textContent = v.querySelector('.vname').value;  // as it reads once another is picked
            v.querySelector('.vline').textContent = t.value;
            hidden.value = written();  // the same text the server wrote, until a field changes it
            hidden.dispatchEvent(new Event('input'));
          });
          el.addEventListener('keydown', function (e) {
            if (e.key === 's' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); voices.saveNow(); }
          });
        });
        v.querySelector('input[type="radio"]').addEventListener('change', function () {
          each.forEach(function (w) { w.classList.toggle('picked', w === v); });
          fitLine();
        });
        fitLine();
      });
    }
    function saveAll() {
      return Promise.all(files.map(function (f) { return f.saveNow(); })).then(function (oks) { return oks.every(Boolean); });
    }

    // Ask until a new round is in, or the house has stopped reading (a failed note says so on reload).
    function wait(before) {
      json('GET', url).then(function (r) {
        if (r.error || !r.id) { busy(false); say(msg, r.error || 'Couldn\'t reach Fortleben. Reload the page.'); return; }
        if (r.rounds > before || !r.steering || r.status !== 'waiting') reload();
        else setTimeout(function () { wait(before); }, EVERY);
      }, function () { setTimeout(function () { wait(before); }, EVERY); });
    }

    send.addEventListener('click', function () {
      var note = box.value.trim();
      if (!note) { say(msg, 'Write a note first.'); box.focus(); return; }
      say(msg, '');
      saveAll().then(function (ok) {
        if (!ok) { say(msg, 'A file didn\'t save, so the note didn\'t go. See above.'); return; }
        busy(true);
        json('POST', url + '/steer', { note: note, voice: voice() }).then(function (d) {
          if (d.error || !d.ok) { busy(false); say(msg, d.error || 'The note didn\'t go. Try again.'); return; }
          wait(Number(cp.dataset.rounds));
        }, function () { busy(false); say(msg, 'Couldn\'t reach Fortleben. Try again.'); });
      });
    });

    approve.addEventListener('click', function () {
      say(msg, '');
      send.disabled = approve.disabled = true;
      approve.textContent = 'Approving…';
      function undo(text) { send.disabled = false; approve.disabled = full; approve.textContent = 'Approve and translate'; say(msg, text); }
      saveAll().then(function (ok) {
        if (!ok) return undo('A file didn\'t save, so it wasn\'t approved. See above.');
        json('POST', url + '/approve', { voice: voice() }).then(function (d) {
          if (d.error || !d.ok) return undo(d.error || 'It didn\'t go. Try again.');
          reload();
        }, function () { undo('Couldn\'t reach Fortleben. Try again.'); });
      });
    });

    // A note or the approval, never both: with something written the button sends it, and with nothing it approves.
    function either() { var note = !!box.value.trim(); send.hidden = !note; approve.hidden = note; }
    box.addEventListener('input', either);
    either();

    if (cp.dataset.steering) wait(Number(cp.dataset.rounds));
  });
})();
