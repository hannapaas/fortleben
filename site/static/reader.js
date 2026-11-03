/* The reader's settings and margin. Three presets (clean, curious, annotated) set the options under
   "More settings"; changing any of those by hand makes your own mix. Settings live in localStorage,
   and the preset in the hash so a link opens the same view. Every change keeps your place. */
(function () {
  var body = document.body;
  var PRESETS = window.FL_PRESETS;  // set in read.html, so the saved view applies before the page paints
  var s = Object.assign({ preset: 'clean', size: 18, leading: false, font: 'standard' }, PRESETS.clean);
  try {
    var saved = JSON.parse(localStorage.getItem('fl-reader') || '{}');
    // Settings saved before an option existed take that option from the saved preset.
    Object.assign(s, PRESETS[saved.preset] || {}, saved);
  } catch (e) {}
  location.hash.slice(1).split('/').forEach(function (t) { if (PRESETS[t]) Object.assign(s, PRESETS[t], { preset: t }); });

  // The paragraph being read, and how far down the screen it sits, so it can be put back.
  function anchor() {
    var units = document.querySelectorAll('.unit');
    for (var i = 0; i < units.length; i++) {
      var r = units[i].getBoundingClientRect();
      if (r.bottom > 40) return { el: units[i], top: r.top };
    }
  }

  function apply(keep) {
    var a = keep && anchor();
    body.className = body.className.replace(/\b(layout|marks)-\w+|\b(no-furigana|hide-status|inline|no-tools|quiet-comments)\b/g, '').trim();
    body.classList.add('layout-' + s.layout, 'marks-' + s.marks);
    if (!s.furigana) body.classList.add('no-furigana');
    if (!s.status) body.classList.add('hide-status');
    if (s.inline) body.classList.add('inline');
    if (!s.tools) body.classList.add('no-tools');
    if (!s.comments) body.classList.add('quiet-comments');
    document.documentElement.style.setProperty('--size', s.size + 'px');
    document.documentElement.style.setProperty('--leading', s.leading ? '1.85' : '1.6');
    document.querySelectorAll('[data-group]').forEach(function (g) {
      g.querySelectorAll('[data-val]').forEach(function (b) { b.setAttribute('aria-pressed', s[g.dataset.group] === b.dataset.val); });
    });
    document.querySelectorAll('[data-toggle]').forEach(function (b) { b.setAttribute('aria-pressed', !!s[b.dataset.toggle]); });
    document.querySelector('[data-leading]').setAttribute('aria-pressed', s.leading);
    if (s.font === 'dyslexic') loadDyslexic();
    body.classList.toggle('font-dyslexic', s.font === 'dyslexic');
    document.getElementById('custom').hidden = s.preset !== 'custom';
    try { localStorage.setItem('fl-reader', JSON.stringify(s)); } catch (e) {}
    layout();
    if (a) window.scrollBy(0, a.el.getBoundingClientRect().top - a.top);
  }

  // OpenDyslexic (SIL OFL) is fetched only when a reader asks for it.
  function loadDyslexic() {
    if (document.getElementById('od-font')) return;
    var l = document.createElement('link');
    l.id = 'od-font'; l.rel = 'stylesheet';
    l.href = 'https://cdn.jsdelivr.net/npm/@fontsource/opendyslexic@5.0.0/index.css';
    document.head.appendChild(l);
  }

  function custom() { s.preset = 'custom'; history.replaceState(null, '', location.pathname + location.search); }
  document.querySelectorAll('[data-group] [data-val]').forEach(function (b) {
    b.onclick = function () {
      var g = b.closest('[data-group]').dataset.group;
      if (g === 'font') {
        s.font = b.dataset.val;
      } else if (g === 'preset') {
        Object.assign(s, PRESETS[b.dataset.val], { preset: b.dataset.val });
        history.replaceState(null, '', '#' + b.dataset.val);
      } else {
        s[g] = b.dataset.val;
        custom();
      }
      apply(true);
    };
  });
  document.querySelectorAll('[data-toggle]').forEach(function (b) {
    b.onclick = function () { s[b.dataset.toggle] = !s[b.dataset.toggle]; custom(); apply(true); };
  });
  // Size and spacing aren't part of a preset, so they don't make your own mix.
  document.querySelectorAll('[data-size]').forEach(function (b) {
    b.onclick = function () { s.size = Math.max(14, Math.min(26, s.size + 2 * +b.dataset.size)); apply(true); };
  });
  document.querySelector('[data-leading]').onclick = function () { s.leading = !s.leading; apply(true); };

  // The margin: one slip per paragraph, opened by tapping the paragraph or "What happened here?".
  function toggleSlip(unit, open, noteIndex) {
    var slip = unit.querySelector('.slip');
    if (open === undefined) open = slip.hidden;
    slip.hidden = !open;
    var btn = unit.querySelector('.open');
    if (btn) btn.setAttribute('aria-expanded', open);
    slip.querySelectorAll('.nl li.on').forEach(function (li) { li.classList.remove('on'); });
    if (open && noteIndex !== undefined) {
      var li = slip.querySelector('.nl li[data-note="' + noteIndex + '"]');
      if (li) li.classList.add('on');
    }
    layout();
    if (open) slip.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }
  document.querySelectorAll('.unit').forEach(function (unit) {
    var en = unit.querySelector('.en');
    function activate(e) {
      if (e.target.closest('a')) return;  // a link goes where it goes
      if (window.getSelection && String(window.getSelection()).length) return;  // the end of a selection drag
      var t = e.target.closest('.t');
      toggleSlip(unit, t ? true : undefined, t ? t.dataset.note : undefined);
      // On a phone the margin sits under the paragraph, folded away; it opens and closes with the notes,
      // so a paragraph nobody has commented on can be commented on. With comments off (as in Clean) it stays shut.
      if (phone.matches && s.comments) margin(unit, !unit.querySelector('.slip').hidden);
    }
    en.addEventListener('click', activate);
    en.addEventListener('keydown', function (e) {
      if ((e.key === 'Enter' || e.key === ' ') && !e.target.closest('a')) { e.preventDefault(); activate(e); }
    });
    var open = unit.querySelector('.open');
    if (open) open.onclick = function () { toggleSlip(unit); };
    unit.querySelector('.jabtn').onclick = function (e) {
      e.currentTarget.setAttribute('aria-pressed', unit.classList.toggle('ja-on'));
    };
  });

  // Settings behind the round "Aa" button: a card on wide screens, a sheet on phones.
  var sheet = document.getElementById('settings'), aa = document.getElementById('aa');
  function showSettings(on) { sheet.classList.toggle('open', on); aa.setAttribute('aria-expanded', on); }
  aa.onclick = function () { showSettings(!sheet.classList.contains('open')); };
  document.getElementById('closeSettings').onclick = function () { showSettings(false); };
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') showSettings(false); });
  document.addEventListener('click', function (e) {
    if (sheet.classList.contains('open') && !sheet.contains(e.target) && e.target !== aa) showSettings(false);
  });

  // ---------- Comments in the margin ----------
  var PENCIL = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 20l1-4L16.5 4.5a2.1 2.1 0 013 3L8 19l-4 1z"/><path d="M14.5 6.5l3 3"/></svg>';
  var phone = matchMedia('(max-width: 860px)');
  document.querySelectorAll('.pc').forEach(function (b) { b.insertAdjacentHTML('afterbegin', PENCIL); });

  // Margin notes sit level with their paragraph; a crowded one moves down below the one above it.
  function layout() {
    var floor = -1e9;
    document.querySelectorAll('.mar .in').forEach(function (m) {
      m.style.transform = '';
      if (phone.matches || !m.offsetHeight) return;
      var r = m.getBoundingClientRect(), top = r.top + scrollY, shift = Math.max(0, floor - top);
      if (shift) m.style.transform = 'translateY(' + shift + 'px)';
      floor = top + shift + r.height + 16;
    });
  }
  addEventListener('resize', layout);
  if (document.fonts) document.fonts.ready.then(layout);

  function openComposer(mar, quiet) {
    mar.classList.add('writing'); layout();
    if (!quiet) mar.querySelector('textarea').focus();
  }
  // A phone's margin, opened from the paragraph: the composer shows, but the keyboard waits for a tap in it.
  function margin(unit, open) {
    var mar = unit.querySelector('.mar'), box = mar.querySelector('textarea');
    unit.classList.toggle('show', open);
    if (open && box) openComposer(mar, true);
    else if (!open && box && !box.value) mar.classList.remove('writing');
    layout();
  }
  document.querySelectorAll('.unit').forEach(function (unit) {
    var mar = unit.querySelector('.mar');
    var ph = mar.querySelector('.ph'), add = mar.querySelector('.add');
    if (ph) ph.onclick = function () {
      unit.classList.toggle('show');
      if (ph.dataset.n === '0' && add) openComposer(mar);
      layout();
    };
    if (add) add.onclick = function () { openComposer(mar); };
  });

  function by(name, note) {
    var span = document.createElement('span'); span.className = 'by';
    span.textContent = '— ' + (name ? name + ', ' : '') + 'just now. ';
    var b = document.createElement('b'); b.textContent = note; span.appendChild(b);
    return span;
  }
  // A new comment shows only to its writer until the screen has read it; check back for a minute or two.
  function watch(el, id, tries) {
    if (tries > 40) return;
    setTimeout(function () {
      fetch('/comments/' + id).then(function (r) { return r.ok ? r.json() : null; }).then(function (st) {
        if (!st || st.status === 'pending') return watch(el, id, tries + 1);
        var b = el.querySelector('.by b');
        if (st.status === 'published') { el.classList.remove('mine'); b.remove(); }
        else { el.classList.add('failed'); b.textContent = 'Not posted: ' + st.reason; }
        layout();
      });
    }, 3000);
  }
  document.querySelectorAll('.cmp').forEach(function (f) {
    var work = location.pathname.split('/')[2];
    f.addEventListener('submit', function (e) {
      e.preventDefault();
      var t = f.querySelector('textarea'), n = f.querySelector('input'), err = f.querySelector('.err');
      var text = t.value.trim(), name = n.value.trim();
      if (!text) return;
      err.hidden = true;
      var unit = f.closest('.unit');
      fetch('/read/' + work + '/comments', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ segment: unit.id, body: text, name: name }) })
        .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
        .then(function (res) {
          if (!res.ok) { err.textContent = res.j.error || res.j.detail || 'That didn’t post.'; err.hidden = false; layout(); return; }
          var c = document.createElement('div'); c.className = 'cm mine';
          var p = document.createElement('p'); p.textContent = text; c.appendChild(p);
          c.appendChild(by(name, 'Only you can see this until it’s checked.'));
          var mar = f.closest('.mar'); mar.querySelector('.list').appendChild(c); mar.classList.remove('empty');
          t.value = ''; mar.classList.remove('writing'); layout();
          watch(c, res.j.id, 0);
        })
        .catch(function () { err.textContent = 'That didn’t post. Check your connection and try again.'; err.hidden = false; });
    });
  });
  document.querySelectorAll('.cm.mine[data-status="pending"]').forEach(function (c) { watch(c, c.dataset.id, 0); });
  document.querySelectorAll('.rp').forEach(function (b) {
    b.onclick = function () {
      b.disabled = true;
      fetch('/comments/' + b.closest('.cm').dataset.id + '/report', { method: 'POST' })
        .then(function (r) { b.textContent = r.status === 429 ? 'too many reports; try later' : 'reported, thanks'; })
        .catch(function () { b.textContent = 'that didn’t send'; b.disabled = false; });
    };
  });
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    document.querySelectorAll('.mar.writing').forEach(function (m) { if (!m.querySelector('textarea').value) m.classList.remove('writing'); });
    layout();
  });

  apply(false);
  var m = location.hash.match(/#(p\d+)$/);
  if (m && document.getElementById(m[1])) document.getElementById(m[1]).scrollIntoView();
})();
