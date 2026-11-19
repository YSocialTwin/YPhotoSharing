/* Interactive database schema of YInstantMessaging. Data: assets/data/schema.json, written by scripts/make_schema_data.py. */
(function () {
  'use strict';
  var host = document.querySelector('.ys-schema'); if (!host) return;
  var IT = (document.documentElement.lang || 'en').slice(0, 2) === 'it';
  var T = IT ? {
    search: 'Cerca tabelle e colonne', none: 'Nessuna tabella corrisponde.', tables: 'tabelle', cols: 'colonne', refs: 'Fa riferimento a', by: 'Referenziata da',
    via: 'tramite', through: 'attraverso', col: 'Colonna', type: 'Tipo', desc: 'Descrizione', doc: 'Spiegata in', pk: 'Chiave primaria', nul: 'Può essere nulla', def: 'predefinito',
    pick: 'Scegli una tabella', link: 'Riferimento a', nofk: 'nessuno'
  } : {
    search: 'Search tables and columns', none: 'No table matches.', tables: 'tables', cols: 'columns', refs: 'References', by: 'Referenced by',
    via: 'via', through: 'through', col: 'Column', type: 'Type', desc: 'Description', doc: 'Explained in', pk: 'Primary key', nul: 'Can be null', def: 'default',
    pick: 'Pick a table', link: 'Link to', nofk: 'none'
  };
  var pre = host.getAttribute('data-pre') || '/';
  var DOCN = {};
  function el(tag, cls, html) { var e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }

  fetch(host.getAttribute('data-src')).then(function (r) { return r.json(); }).then(init).catch(function (e) { host.textContent = 'Schema data not available.'; if (window.console) console.warn(e); });

  function init(D) {
    var names = Object.keys(D.tables), back = {};
    Object.keys(D.docs || {}).forEach(function (k) { DOCN[k] = IT ? D.docs[k].it : D.docs[k].en; });
    names.forEach(function (n) { D.tables[n].columns.forEach(function (c) { if (c.fk) { var t = c.fk.split('.')[0]; (back[t] = back[t] || []).push({ table: n, col: c.name, to: c.fk.split('.')[1] }); } }); });
    var title = el('div', 'ys-sc-bar');
    var input = el('input'); input.type = 'search'; input.placeholder = T.search; input.setAttribute('aria-label', T.search);
    var count = el('span', 'ys-sc-count'); title.appendChild(input); title.appendChild(count);
    var wrap = el('div', 'ys-sc'), list = el('nav', 'ys-sl'), det = el('div', 'ys-sd');
    wrap.appendChild(list); wrap.appendChild(det); host.innerHTML = ''; host.appendChild(title); host.appendChild(wrap);
    var cur = null;

    function matches(n, q) {
      if (!q) return true; var t = D.tables[n];
      if (n.indexOf(q) >= 0 || (t.note || '').toLowerCase().indexOf(q) >= 0) return true;
      return t.columns.some(function (c) { return c.name.toLowerCase().indexOf(q) >= 0 || (c.desc || '').toLowerCase().indexOf(q) >= 0; });
    }
    function renderList() {
      var q = input.value.trim().toLowerCase(), shown = 0; list.innerHTML = '';
      D.groups.forEach(function (g) {
        var ts = g.tables.filter(function (n) { return matches(n, q); }); if (!ts.length) return; shown += ts.length;
        var s = el('section', 'ys-sg'); s.appendChild(el('h3', '', esc(IT && g.title_it ? g.title_it : g.title) + ' <span>' + ts.length + '</span>'));
        var ul = el('div', 'ys-chips');
        ts.forEach(function (n) { var b = el('button', cur === n ? 'on' : '', esc(n)); b.type = 'button'; b.setAttribute('data-t', n); ul.appendChild(b); });
        s.appendChild(ul); list.appendChild(s);
      });
      if (!shown) list.appendChild(el('p', 'ys-sc-none', T.none));
      count.textContent = shown + ' ' + T.tables;
    }
    function chip(n, sub) { return '<button type="button" class="ys-ref" data-t="' + esc(n) + '">' + esc(n) + '<small>' + esc(sub) + '</small></button>'; }
    function renderDetail(n, push) {
      var t = D.tables[n]; if (!t) { det.innerHTML = '<p class="ys-sc-none">' + T.pick + '</p>'; return; }
      cur = n; if (push !== false) { try { history.replaceState(null, '', '#t=' + n); } catch (e) {} }
      var out = '<h3 class="ys-sd-h"><code>' + esc(n) + '</code><span>' + t.columns.length + ' ' + T.cols + '</span></h3>';
      if (t.note) out += '<p class="ys-sd-note">' + esc(t.note) + '</p>';
      if (t.doc) out += '<p class="ys-sd-doc">' + T.doc + ' <a href="' + pre + t.doc + '/">' + esc(DOCN[t.doc] || t.doc) + '</a></p>';
      var refs = {}; t.columns.forEach(function (c) { if (c.fk) { var k = c.fk.split('.')[0]; refs[k] = (refs[k] ? refs[k] + ', ' : '') + c.name; } });
      var rk = Object.keys(refs), bk = {}; (back[n] || []).forEach(function (r) { if (r.table !== n) bk[r.table] = (bk[r.table] ? bk[r.table] + ', ' : '') + r.col; });
      var bks = Object.keys(bk);
      if (rk.length || bks.length) {
        out += '<div class="ys-rel">';
        if (rk.length) out += '<div><b>' + T.refs + '</b>' + rk.map(function (k) { return chip(k, T.via + ' ' + refs[k]); }).join('') + '</div>';
        if (bks.length) out += '<div><b>' + T.by + '</b>' + bks.map(function (k) { return chip(k, T.through + ' ' + bk[k]); }).join('') + '</div>';
        out += '</div>';
      }
      out += '<div class="ys-table-wrap ys-no-wrap"><table class="ys-cols"><thead><tr><th>' + T.col + '</th><th>' + T.type + '</th><th>' + T.desc + '</th></tr></thead><tbody>';
      t.columns.forEach(function (c) {
        var name = esc(c.name) + (c.pk ? ' <em class="pk" title="' + T.pk + '">PK</em>' : '') + (c.fk ? ' <a class="fk" href="#t=' + esc(c.fk.split('.')[0]) + '" data-t="' + esc(c.fk.split('.')[0]) + '" title="' + T.link + ' ' + esc(c.fk) + '">&rarr; ' + esc(c.fk.split('.')[0]) + '</a>' : '');
        var d = esc(c.desc) + (c['default'] != null ? ' <small>(' + T.def + ' <code>' + esc(c['default']) + '</code>)</small>' : '');
        out += '<tr><td>' + name + '</td><td>' + esc(c.type) + '</td><td>' + (d || '<span class="ys-dim">&mdash;</span>') + '</td></tr>';
      });
      out += '</tbody></table></div>';
      det.innerHTML = out; renderList();
    }
    function go(n, scroll) { renderDetail(n); if (scroll && window.innerWidth < 900) det.scrollIntoView({ behavior: 'smooth', block: 'start' }); }
    host.addEventListener('click', function (e) {
      var b = e.target.closest('[data-t]'); if (!b) return; e.preventDefault(); go(b.getAttribute('data-t'), true);
    });
    input.addEventListener('input', renderList);
    var m = /#t=([\w]+)/.exec(location.hash); renderList(); renderDetail(m && D.tables[m[1]] ? m[1] : names.indexOf('messages') >= 0 ? 'messages' : names[0], false);
  }
})();
