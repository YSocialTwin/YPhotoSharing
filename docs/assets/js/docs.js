/* YCreator documentation behaviour. Taken from the YSocial site script (ysocial-v4.js), reduced to the features the docs use. No dependencies; every feature fails soft. */
(function () {
  'use strict';
  var doc = document, root = doc.documentElement;
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var $ = function (s, c) { return (c || doc).querySelector(s); };
  var $$ = function (s, c) { return Array.prototype.slice.call((c || doc).querySelectorAll(s)); };
  var isBlog = false;
  var IT = (root.getAttribute('lang') || 'en') === 'it';
  var T = IT ? { link: 'Link a questa sezione', copied: 'Copiato', copy: 'Copia', code: 'Copia il codice', cmd: 'Copia il comando' } : { link: 'Link to this section', copied: 'Copied', copy: 'Copy', code: 'Copy code', cmd: 'Copy command' };

  /* ---------- theme ---------- */
  function setTheme(t) {
    root.setAttribute('data-theme', t);
    try { localStorage.setItem('ys-theme', t); } catch (e) {}
    var m = $('meta[name="theme-color"]'); if (m) m.setAttribute('content', t === 'light' ? '#f3f8fb' : '#07131b');
  }
  function initTheme() {
    var b = $('#ys-theme'); if (!b) return;
    b.addEventListener('click', function () { setTheme(root.getAttribute('data-theme') === 'light' ? 'dark' : 'light'); });
  }

  /* ---------- navigation ---------- */
  function initNav() {
    var nav = $('#ys-nav'); if (!nav) return;
    var burger = $('#ys-burger');
    function closeDrops(except) { $$('.ys-drop.open', nav).forEach(function (d) { if (d !== except) { d.classList.remove('open'); $('.ys-drop-btn', d).setAttribute('aria-expanded', 'false'); } }); }
    $$('.ys-drop', nav).forEach(function (d) {
      var btn = $('.ys-drop-btn', d);
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        var open = !d.classList.contains('open'); closeDrops(d);
        d.classList.toggle('open', open); btn.setAttribute('aria-expanded', open ? 'true' : 'false');
      });
      if (window.matchMedia('(hover: hover) and (min-width: 992px)').matches) {
        var t; d.addEventListener('mouseenter', function () { clearTimeout(t); closeDrops(d); d.classList.add('open'); btn.setAttribute('aria-expanded', 'true'); });
        d.addEventListener('mouseleave', function () { t = setTimeout(function () { d.classList.remove('open'); btn.setAttribute('aria-expanded', 'false'); }, 160); });
      }
    });
    doc.addEventListener('click', function (e) { if (!nav.contains(e.target)) closeDrops(); });
    doc.addEventListener('keydown', function (e) { if (e.key === 'Escape') { var o = $('.ys-drop.open .ys-drop-btn', nav); closeDrops(); setMenu(false); if (o && nav.contains(doc.activeElement)) o.focus(); } });
    function setMenu(on) {
      nav.classList.toggle('menu-open', on); doc.body.classList.toggle('ys-lock', on);
      if (burger) { burger.setAttribute('aria-expanded', on ? 'true' : 'false');  }
    }
    if (burger) burger.addEventListener('click', function () { setMenu(!nav.classList.contains('menu-open')); });
    $$('.ys-menu a', nav).forEach(function (a) { a.addEventListener('click', function () { setMenu(false); }); });
    window.addEventListener('resize', function () { if (window.innerWidth > 1060) setMenu(false); });
    var bar = $('#ys-progress'), top = $('#ys-top'), ticking = false;
    function onScroll() {
      var y = window.pageYOffset || root.scrollTop, h = root.scrollHeight - root.clientHeight;
      nav.classList.toggle('is-scrolled', y > 8);
      if (bar) bar.style.transform = 'scaleX(' + (h > 0 ? Math.min(1, y / h) : 0) + ')';
      if (top) top.classList.toggle('on', y > 700);
      ticking = false;
    }
    window.addEventListener('scroll', function () { if (!ticking) { ticking = true; requestAnimationFrame(onScroll); } }, { passive: true });
    onScroll();
    if (top) top.addEventListener('click', function () { window.scrollTo({ top: 0, behavior: reduce ? 'auto' : 'smooth' }); });
  }

  /* ---------- aurora backdrop ---------- */
  function initAurora() {
    if ($('#ys-aurora')) return;
    var a = doc.createElement('div'); a.id = 'ys-aurora'; a.setAttribute('aria-hidden', 'true');
    a.innerHTML = '<i></i><i></i><i></i>'; doc.body.insertBefore(a, doc.body.firstChild);
  }

  function article() { return $('#maincontent'); }
  function slug(s) { return s.toLowerCase().replace(/[^\w\s-]/g, '').trim().replace(/\s+/g, '-'); }

  function initHeadings() {
    var a = article(); if (!a || isBlog) return;
    var seen = {};
    $$('h2, h3', a).forEach(function (h) {
      if (h.closest('details, .ys-card, .ys-footer')) return;
      if (!h.id) { var id = slug(h.textContent) || 'section', n = id, i = 2; while (seen[n] || doc.getElementById(n)) n = id + '-' + i++; h.id = n; }
      seen[h.id] = 1;
      if (!$('.ys-anchor', h)) { var l = doc.createElement('a'); l.className = 'ys-anchor'; l.href = '#' + h.id; l.setAttribute('aria-label', T.link); l.textContent = '#'; h.appendChild(l); }
    });
  }


  function initTables() {
    $$('#maincontent table').forEach(function (t) {
      if (t.parentNode.classList.contains('ys-table-wrap') || t.closest('.ys-no-wrap')) return;
      var w = doc.createElement('div'); w.className = 'ys-table-wrap'; t.parentNode.insertBefore(w, t); w.appendChild(t);
    });
  }

  function copyText(txt, btn) {
    function done() { var o = btn.textContent; btn.textContent = T.copied; btn.classList.add('ok'); setTimeout(function () { btn.textContent = o; btn.classList.remove('ok'); }, 1400); }
    if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(txt).then(done, fallback); else fallback();
    function fallback() { var t = doc.createElement('textarea'); t.value = txt; t.style.position = 'fixed'; t.style.opacity = '0'; doc.body.appendChild(t); t.select(); try { doc.execCommand('copy'); done(); } catch (e) {} doc.body.removeChild(t); }
  }
  function initCopy() {
    $$('div.highlighter-rouge, figure.highlight, #maincontent > pre, details pre').forEach(function (box) {
      var host = box.tagName === 'PRE' && box.parentNode.classList.contains('highlight') ? box.parentNode : box;
      if (host.querySelector('.ys-copy') || host.closest('.ys-cmd')) return;
      if (host.tagName === 'PRE' && !host.style.position) host.style.position = 'relative';
      var b = doc.createElement('button'); b.type = 'button'; b.className = 'ys-copy'; b.textContent = T.copy; b.setAttribute('aria-label', T.code);
      b.addEventListener('click', function () { var p = host.tagName === 'PRE' ? host : $('pre', host); copyText((p || host).innerText.replace(/\s+$/, ''), b); });
      host.appendChild(b);
    });
    $$('pre').forEach(function (p) { if (p.scrollWidth > p.clientWidth + 1) p.setAttribute('tabindex', '0'); });
    $$('.ys-cmd').forEach(function (c) {
      if ($('.ys-copy', c)) return;
      var b = doc.createElement('button'); b.type = 'button'; b.className = 'ys-copy'; b.textContent = T.copy; b.setAttribute('aria-label', T.cmd);
      b.addEventListener('click', function () { copyText($('code', c).innerText.trim(), b); }); c.appendChild(b);
    });
  }
  function initDetails() {
    var list = $$('#maincontent details'); if (!list.length) return;
    list.forEach(function (d) {
      var s = $('summary', d); if (!s || s.hasAttribute('data-excerpt')) return;
      var p = $('p', d); if (!p) return;
      var t = p.textContent.replace(/\s+/g, ' ').trim(); if (t.length > 96) t = t.slice(0, 93).replace(/\s+\S*$/, '') + '…';
      s.setAttribute('data-excerpt', t);
    });
    if (list.length >= 3 && !$('.ys-expand')) {
      var bar = doc.createElement('div'); bar.className = 'ys-expand';
      bar.innerHTML = '<button type="button" data-a="open">Expand all</button><button type="button" data-a="close">Collapse all</button>';
      list[0].parentNode.insertBefore(bar, list[0]);
      bar.addEventListener('click', function (e) { var b = e.target.closest('button'); if (!b) return; list.forEach(function (d) { if (d.parentNode === bar.parentNode) d.open = b.getAttribute('data-a') === 'open'; }); });
    }
    if (location.hash) { var t = doc.getElementById(location.hash.slice(1)); var d = t && t.closest('details'); if (d) d.open = true; }
  }

  /* ---------- docs: "on this page" column, sidebar on small screens ---------- */
  function initDocToc() {
    var host = $('#ys-doc-toc'), a = article(); if (!host || !a) return;
    var hs = $$('h2, h3', a).filter(function (h) { return h.id && !h.closest('details') && !h.classList.contains('ys-tldr-title'); });
    if (hs.length < 3) { host.hidden = true; return; }
    host.innerHTML = '<b>' + (a.getAttribute('data-on-this-page') || 'On this page') + '</b>' + hs.map(function (h) {
      var t = h.firstChild ? h.firstChild.textContent.trim() : h.textContent.trim();
      return '<a class="' + (h.tagName === 'H3' ? 'sub' : '') + '" href="#' + h.id + '">' + t + '</a>';
    }).join('');
    if ('IntersectionObserver' in window) {
      var links = $$('a', host), io = new IntersectionObserver(function (es) {
        es.forEach(function (e) { if (e.isIntersecting) { links.forEach(function (l) { l.classList.toggle('on', l.getAttribute('href') === '#' + e.target.id); }); } });
      }, { rootMargin: '-84px 0px -70% 0px' });
      hs.forEach(function (h) { io.observe(h); });
    }
  }


  /* ---------- "where to next": a strip of links after the content, never a tab ---------- */
  var NEXT_RE = /^(where to (go )?next|da dove continuare|dove andare dopo|per continuare)$/i;
  function initNext() {
    var a = article(); if (!a || isBlog) return;
    var kids = Array.prototype.slice.call(a.children);
    var i = kids.findIndex(function (k) { return k.tagName === 'H2' && NEXT_RE.test(hText(k)); });
    if (i < 0) return;
    var nodes = [kids[i]];
    for (var j = i + 1; j < kids.length && kids[j].tagName !== 'H2' && !kids[j].classList.contains('ys-pn'); j++) nodes.push(kids[j]);
    if (nodes.some(function (n) { return (n.matches && n.matches('.ys-steps')) || (n.querySelector && n.querySelector('.ys-steps')); })) return;
    var box = doc.createElement('aside'); box.className = 'ys-next';
    nodes[0].parentNode.insertBefore(box, nodes[0]);
    nodes.forEach(function (n) { box.appendChild(n); });
    var pn = $('.ys-pn', a); if (pn) a.insertBefore(box, pn); else a.appendChild(box);
  }

  /* ---------- one section at a time: H2 sections become tabs; poor sections are merged ---------- */
  function hText(h) { var c = h.cloneNode(true); var x = c.querySelector('.ys-anchor'); if (x) x.remove(); return c.textContent.trim().replace(/\s*\(.*$/, '') || c.textContent.trim(); }
  var RICH = '.ys-lab, .ys-shot, .ys-params, .ys-schema, .ys-grid, .ys-steps, .ys-sandbox';
  function secScore(nodes) {
    var s = 0, len = 0, rich = false;
    nodes.slice(1).forEach(function (n) {
      len += (n.textContent || '').length;
      var q = function (sel) { return (n.matches && n.matches(sel)) || (n.querySelector && n.querySelector(sel)); };
      if (q(RICH)) { s += 3; rich = true; }
      if (n.tagName === 'TABLE' || q('table')) { s += 2; rich = true; }
      if (n.tagName === 'PRE' || q('pre')) { s += 1; rich = true; }
    });
    return { score: s + len / 700, rich: rich };
  }
  function initTabs() {
    var a = article(); if (!a || isBlog || a.classList.contains('ys-notabs')) return;
    var kids = Array.prototype.slice.call(a.children);
    var first = kids.findIndex(function (k) { return k.tagName === 'H2' && !k.classList.contains('ys-tldr-title'); });
    if (first < 0) return;
    var end = kids.findIndex(function (k, i) { return i > first && k.classList && (k.classList.contains('ys-pn') || k.classList.contains('ys-next')); }); if (end < 0) end = kids.length;
    var secs = [], cur = null;
    kids.slice(first, end).forEach(function (k) {
      if (k.tagName === 'H2') { cur = { h: k, nodes: [k] }; secs.push(cur); } else cur.nodes.push(k);
    });
    if (secs.length < 2) return;
    /* group: a section with only text, or with very little, joins the previous tab (the first one joins the next) */
    var groups = [];
    secs.forEach(function (sc) {
      var sc_ = secScore(sc.nodes), poor = !sc_.rich || sc_.score < 2;
      if (poor && groups.length) groups[groups.length - 1].secs.push(sc);
      else groups.push({ secs: [sc], poorFirst: poor });
    });
    if (groups.length > 1 && groups[0].poorFirst) { var g0 = groups.shift(); groups[0].secs = g0.secs.concat(groups[0].secs); }
    if (groups.length < 2) return;
    var bar = doc.createElement('div'); bar.className = 'ys-tabbar'; bar.setAttribute('role', 'tablist');
    var panes = [];
    groups.forEach(function (g, i) {
      var pane = doc.createElement('section'); pane.className = 'ys-pane'; pane.id = 'pane-' + i; pane.setAttribute('role', 'tabpanel');
      var head = g.secs[0].nodes[0];
      head.parentNode.insertBefore(pane, head);
      g.secs.forEach(function (sc) {
        sc.nodes.forEach(function (n) { pane.appendChild(n); });
        var fig = sc.nodes.find(function (n) { return n.classList && n.classList.contains('ys-shot') && !n.classList.contains('wide'); });
        if (fig && fig.previousElementSibling !== sc.h) sc.h.parentNode.insertBefore(fig, sc.h.nextSibling);
      });
      var tl = g.secs.map(function (s) { return hText(s.h); });
      var label = tl[0] + (tl.length > 1 ? ' \u00b7 ' + tl[1] : '') + (tl.length > 2 ? ' +' + (tl.length - 2) : '');
      var b = doc.createElement('button'); b.type = 'button'; b.setAttribute('role', 'tab');
      b.innerHTML = '<i>' + (i + 1) + '</i><span></span>'; b.lastChild.textContent = label; bar.appendChild(b);
      panes.push({ pane: pane, btn: b, h: g.secs[0].h, label: label, hs: g.secs.map(function (s) { return s.h; }) });
    });
    panes.forEach(function (p, i) {
      var nav = doc.createElement('div'); nav.className = 'ys-stepnav';
      nav.innerHTML = '<button type="button" data-d="-1"' + (i ? '' : ' style="visibility:hidden"') + '>← ' + (i ? panes[i - 1].label : '') + '</button><button type="button" data-d="1"' + (i < panes.length - 1 ? '' : ' style="visibility:hidden"') + '>' + (i < panes.length - 1 ? panes[i + 1].label : '') + ' →</button>';
      p.pane.appendChild(nav);
    });
    var intro = doc.createElement('div'); intro.className = 'ys-intro-pane';
    var firstPane = panes[0].pane;
    kids.slice(0, first).forEach(function (k) { intro.appendChild(k); });
    a.insertBefore(intro, firstPane); a.insertBefore(bar, firstPane);
    function show(i, scroll, keep) {
      panes.forEach(function (p, j) { p.pane.classList.toggle('on', i === j); p.btn.setAttribute('aria-selected', i === j ? 'true' : 'false'); });
      if (scroll) { var y = bar.getBoundingClientRect().top + window.pageYOffset - 70; if (window.pageYOffset > y) window.scrollTo({ top: y, behavior: 'smooth' }); }
      if (!keep) { try { history.replaceState(null, '', '#' + panes[i].h.id); } catch (e) {} }
    }
    bar.addEventListener('click', function (e) { var b = e.target.closest('button'); if (b) show(Array.prototype.indexOf.call(bar.children, b), true); });
    a.addEventListener('click', function (e) {
      var b = e.target.closest('.ys-stepnav button'); if (!b) return;
      var i = panes.findIndex(function (p) { return p.pane.contains(b); }); show(i + parseInt(b.getAttribute('data-d'), 10), true);
      var bb = bar.children[i + parseInt(b.getAttribute('data-d'), 10)]; if (bb && bb.scrollIntoView) bb.scrollIntoView({ block: 'nearest', inline: 'center' });
    });
    function fromHash() {
      var id = location.hash.slice(1), t = id && doc.getElementById(id), idx = 0;
      if (t) { var p = t.closest('.ys-pane'); if (p) idx = panes.findIndex(function (x) { return x.pane === p; }); }
      show(idx < 0 ? 0 : idx, false, true); if (t && t.scrollIntoView) t.scrollIntoView();
    }
    window.addEventListener('hashchange', fromHash); fromHash();
  }

  /* ---------- cards: links move to a footer row ---------- */
  function initCards() {
    $$('#maincontent .ys-grid > .ys-card').forEach(function (c) {
      if (c.tagName === 'A' || $('.ys-card-go', c)) return;
      var p = $('p', c); if (!p) return;
      var links = $$('a', p); if (!links.length) return;
      var go = doc.createElement('div'); go.className = 'ys-card-go';
      links.forEach(function (l) { go.appendChild(l); });
      p.innerHTML = p.innerHTML.replace(/[\s·|]+$/, '');
      c.appendChild(go);
    });
  }

  /* ---------- click a screenshot to enlarge ---------- */
  function initLightbox() {
    var lb = null;
    doc.addEventListener('click', function (e) {
      var a = e.target.closest && e.target.closest('a.ys-zoom'); if (!a) { if (lb && lb.contains(e.target)) lb.classList.remove('on'); return; }
      e.preventDefault();
      if (!lb) { lb = doc.createElement('div'); lb.id = 'ys-lightbox'; lb.innerHTML = '<img alt=""><p></p>'; doc.body.appendChild(lb); }
      var im = lb.querySelector('img'); im.src = a.getAttribute('data-full'); im.alt = a.getAttribute('aria-label') || '';
      lb.querySelector('p').textContent = a.getAttribute('aria-label') || ''; lb.classList.add('on');
    });
    doc.addEventListener('keydown', function (e) { if (e.key === 'Escape' && lb) lb.classList.remove('on'); });
  }

  function initSidebar() {
    var btn = $('#ys-side-toggle'), side = $('#ys-side'); if (!btn || !side) return;
    btn.addEventListener('click', function () {
      var on = !side.classList.contains('open');
      side.classList.toggle('open', on); btn.setAttribute('aria-expanded', on ? 'true' : 'false');
    });
    var cur = $('a.active', side); if (cur && cur.scrollIntoView && window.innerWidth > 1060) { try { cur.scrollIntoView({ block: 'nearest' }); } catch (e) {} }
  }

  function ready(fn) { if (doc.readyState !== 'loading') fn(); else doc.addEventListener('DOMContentLoaded', fn); }
  ready(function () {
    root.classList.remove('no-js');
    [initTheme, initNav, initAurora, initHeadings, initNext, initTabs, initCards, initLightbox, initTables, initCopy, initDetails].forEach(function (f) {
      try { f(); } catch (e) { if (window.console) console.warn('docs:', f.name, e); }
    });
  });
})();
