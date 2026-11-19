/* Interactive parameter reference. Data: assets/data/parameters.json, written by scripts/make_parameters_data.py. */
(function () {
  'use strict';
  var host = document.querySelector('.ys-params'); if (!host) return;
  var IT = (document.documentElement.lang || 'en').slice(0, 2) === 'it';
  var T = IT ? {
    all: 'Tutti', server: 'Server', client: 'Client', adv: 'Mostra anche i parametri avanzati', search: 'Cerca parametri', of: 'di', params: 'parametri',
    param: 'Parametro', meaning: 'Significato ed effetto', values: 'Valori · predefinito', none: 'Nessun parametro corrisponde.', basic: 'Base', advanced: 'Avanzato',
    on: 'sì / no', def: 'predefinito', file_s: 'server_config.json', file_c: 'client_config.json', onoff: 'sì / no', jump: 'Vai a', empty: 'vuoto',
    bool: 'sì / no', int: 'intero', float: 'numero', str: 'testo', choice: 'scelta', list: 'elenco', table: 'tabella', kv: 'nome = valore', ranges: 'intervalli'
  } : {
    all: 'All', server: 'Server', client: 'Client', adv: 'Show advanced parameters', search: 'Search parameters', of: 'of', params: 'parameters',
    param: 'Parameter', meaning: 'Meaning and effect', values: 'Values · default', none: 'No parameter matches.', basic: 'Basic', advanced: 'Advanced',
    on: 'on / off', def: 'default', file_s: 'server_config.json', file_c: 'client_config.json', onoff: 'on / off', jump: 'Jump to', empty: 'empty',
    bool: 'on / off', int: 'integer', float: 'number', str: 'text', choice: 'choice', list: 'list', table: 'table', kv: 'name = value', ranges: 'ranges'
  };
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function el(tag, cls, html) { var e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; }
  function fmtDefault(f) {
    var d = f.default; if (d === null || d === undefined || d === '') return null;
    if (typeof d === 'boolean') return d ? (IT ? 'sì' : 'on') : (IT ? 'no' : 'off');
    if (typeof d === 'object') { var s = JSON.stringify(d); return s.length > 60 ? s.slice(0, 57) + '…' : s; }
    return String(d);
  }
  function fmtValues(f) {
    var parts = [];
    if (f.choices && f.choices.length) parts.push(f.choices.filter(function (c) { return c !== ''; }).map(function (c) { return '<code>' + esc(c) + '</code>'; }).join(' · '));
    else if (f.kind === 'bool') parts.push(T.onoff);
    else {
      var b = [];
      if (f.min != null) b.push('≥ ' + f.min); if (f.xmin != null) b.push('> ' + f.xmin); if (f.max != null) b.push('≤ ' + f.max);
      parts.push(esc(T[f.kind] || f.kind) + (b.length ? ' (' + b.join(', ') + ')' : ''));
    }
    var d = fmtDefault(f);
    return parts.join('') + (d !== null ? '<div class="ys-pd">' + T.def + ' <code>' + esc(d) + '</code></div>' : '');
  }

  fetch(host.getAttribute('data-src')).then(function (r) { return r.json(); }).then(init).catch(function (e) { host.textContent = 'Parameter data not available.'; if (window.console) console.warn(e); });

  function init(D) {
    var state = { kind: 'all', adv: false, q: '' };
    host.innerHTML = '';
    var bar = el('div', 'ys-pbar');
    var seg = el('div', 'ys-seg-p'); [['all', T.all], ['server', T.server], ['client', T.client]].forEach(function (k) { var b = el('button', k[0] === 'all' ? 'on' : '', k[1]); b.type = 'button'; b.setAttribute('data-k', k[0]); seg.appendChild(b); });
    var q = el('input'); q.type = 'search'; q.placeholder = T.search; q.setAttribute('aria-label', T.search);
    var lab = el('label', 'ys-padv'); var cb = el('input'); cb.type = 'checkbox'; lab.appendChild(cb); lab.appendChild(document.createTextNode(' ' + T.adv));
    var cnt = el('span', 'ys-sc-count');
    bar.appendChild(seg); bar.appendChild(q); bar.appendChild(lab); bar.appendChild(cnt);
    var nav = el('nav', 'ys-pnav'), body = el('div', 'ys-pbody');
    host.appendChild(bar); host.appendChild(nav); host.appendChild(body);
    var total = 0; ['server', 'client'].forEach(function (k) { D[k].forEach(function (s) { total += s.fields.length; }); });

    function match(f, kind) {
      if (!state.adv && !f.basic) return false;
      if (!state.q) return true; var s = state.q;
      return f.path.toLowerCase().indexOf(s) >= 0 || (IT ? f.label_it : f.label).toLowerCase().indexOf(s) >= 0 || (IT ? f.help_it : f.help).toLowerCase().indexOf(s) >= 0;
    }
    function render() {
      body.innerHTML = ''; nav.innerHTML = ''; var shown = 0;
      ['server', 'client'].forEach(function (kind) {
        if (state.kind !== 'all' && state.kind !== kind) return;
        var head = el('h2', 'ys-pk', (kind === 'server' ? T.server : T.client) + ' <small>' + (kind === 'server' ? T.file_s : T.file_c) + '</small>'); var any = false;
        var frag = document.createDocumentFragment();
        D[kind].forEach(function (s) {
          var fs = s.fields.filter(function (f) { return match(f, kind); }); if (!fs.length) return; any = true; shown += fs.length;
          var id = 'p-' + kind + '-' + s.id; var sec = el('section', 'ys-ps'); sec.id = id;
          sec.appendChild(el('h3', '', esc(IT ? s.title_it : s.title) + ' <span>' + fs.length + '</span>'));
          var rows = fs.map(function (f) {
            return '<tr><td><code>' + esc(f.path) + '</code><div class="ys-pl">' + esc(IT ? f.label_it : f.label) + (f.basic ? '' : ' <em>' + T.advanced + '</em>') + '</div></td><td>' + esc((IT ? f.help_it : f.help) || (IT ? f.label_it : f.label)) + '</td><td>' + fmtValues(f) + '</td></tr>';
          }).join('');
          sec.appendChild(el('div', 'ys-table-wrap ys-no-wrap', '<table class="ys-ptab"><thead><tr><th>' + T.param + '</th><th>' + T.meaning + '</th><th>' + T.values + '</th></tr></thead><tbody>' + rows + '</tbody></table>'));
          frag.appendChild(sec);
          var a = el('a', '', esc(IT ? s.title_it : s.title)); a.href = '#' + id; a.setAttribute('data-kind', kind); nav.appendChild(a);
        });
        if (any) { body.appendChild(head); body.appendChild(frag); }
      });
      if (!shown) body.appendChild(el('p', 'ys-sc-none', T.none));
      cnt.textContent = shown + ' ' + T.of + ' ' + total + ' ' + T.params;
    }
    seg.addEventListener('click', function (e) { var b = e.target.closest('button'); if (!b) return; state.kind = b.getAttribute('data-k'); Array.prototype.forEach.call(seg.children, function (x) { x.classList.toggle('on', x === b); }); render(); });
    q.addEventListener('input', function () { state.q = q.value.trim().toLowerCase(); render(); });
    cb.addEventListener('change', function () { state.adv = cb.checked; render(); });
    render();
    if (location.hash.indexOf('#p-') === 0) { var t = document.getElementById(location.hash.slice(1)); if (!t) { cb.checked = state.adv = true; render(); t = document.getElementById(location.hash.slice(1)); } if (t) t.scrollIntoView(); }
  }
})();
