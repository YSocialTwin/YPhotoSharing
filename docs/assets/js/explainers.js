/* Interactive explainers of the YPhotoSharing documentation. Vanilla JavaScript, no dependencies, nothing is sent anywhere.
   Usage: <div class="ys-lab" data-lab="pricing"></div>. The language is the one of <html lang>.
   The formulas are the ones of the runtime (YPhotoSharing/YClient: round planner, agent loop, opinions, stress_reward; YServer: recsys, moderation, trend service);
   the pages say where a widget simplifies. */
(function () {
  'use strict';
  var doc = document;
  var IT = (doc.documentElement.getAttribute('lang') || 'en') === 'it';

  /* ---------- tiny helpers ---------- */
  function h(tag, attrs, kids) {
    var e = doc.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === 'class') e.className = attrs[k];
      else if (k === 'text') e.textContent = attrs[k];
      else e.setAttribute(k, attrs[k]);
    });
    (kids || []).forEach(function (c) { if (c != null) e.appendChild(typeof c === 'string' ? doc.createTextNode(c) : c); });
    return e;
  }
  function t(en, it) { return IT ? it : en; }
  function clamp(x, a, b) { return Math.max(a, Math.min(b, x)); }
  function pyRound(x) { var f = Math.floor(x), d = x - f; if (d > 0.5) return f + 1; if (d < 0.5) return f; return f % 2 === 0 ? f : f + 1; }
  function halfUp(x) { return Math.floor(x + 0.5); }
  function pct(x) { return Math.round(x * 1000) / 10 + '%'; }
  function num(x) { return String(Math.round(x * 100) / 100); }
  function rng(seed) { var a = seed >>> 0; return function () { a += 0x6D2B79F5; var r = Math.imul(a ^ a >>> 15, 1 | a); r ^= r + Math.imul(r ^ r >>> 7, 61 | r); return ((r ^ r >>> 14) >>> 0) / 4294967296; }; }
  function normal(r) { var u = 0, v = 0; while (u === 0) u = r(); while (v === 0) v = r(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); }

  function slider(label, min, max, step, val, fmt, on) {
    var out = h('output', { text: fmt ? fmt(val) : String(val) });
    var inp = h('input', { type: 'range', min: min, max: max, step: step, value: val });
    inp.addEventListener('input', function () { var v = parseFloat(inp.value); out.textContent = fmt ? fmt(v) : String(v); on(v); });
    var el = h('label', {}, [h('b', {}, [h('span', { text: label }), out]), inp]);
    el.set = function (v) { inp.value = v; out.textContent = fmt ? fmt(v) : String(v); };
    return el;
  }
  function select(label, options, val, on) {
    var s = h('select');
    options.forEach(function (o) { var op = h('option', { value: o[0], text: o[1] }); if (o[0] === val) op.selected = true; s.appendChild(op); });
    s.addEventListener('change', function () { on(s.value); });
    return h('label', {}, [h('b', {}, [h('span', { text: label })]), s]);
  }
  function seg(label, options, val, on) {
    var box = h('div', { class: 'ys-seg', role: 'group', 'aria-label': label }), btns = [];
    options.forEach(function (o) {
      var b = h('button', { type: 'button', text: o[1], 'aria-pressed': o[0] === val ? 'true' : 'false' });
      b.addEventListener('click', function () { btns.forEach(function (x) { x.setAttribute('aria-pressed', 'false'); }); b.setAttribute('aria-pressed', 'true'); on(o[0]); });
      btns.push(b); box.appendChild(b);
    });
    return h('label', {}, [h('b', {}, [h('span', { text: label })]), box]);
  }
  function check(label, val, on) {
    var c = h('input', { type: 'checkbox' }); c.checked = !!val;
    c.addEventListener('change', function () { on(c.checked); });
    return h('label', { class: 'ys-chk' }, [c, h('span', { text: label })]);
  }
  function kpi(label, value, cls) { return h('div', { class: 'ys-kpi' + (cls ? ' ' + cls : '') }, [h('small', { text: label }), h('b', { text: String(value) })]); }
  function msg(text, cls) { return h('div', { class: 'ys-msg' + (cls ? ' is-' + cls : ''), text: text }); }
  function bars(rows, max) {
    var m = max || Math.max.apply(null, rows.map(function (r) { return r[1]; }).concat([1e-9]));
    return h('div', { class: 'ys-bars' }, rows.map(function (r) {
      var i = h('i'); i.style.width = clamp(r[1] / m * 100, 0, 100) + '%';
      return h('div', { class: 'ys-bar' }, [h('span', { text: r[0] }), h('div', {}, [i]), h('em', { text: r[2] != null ? r[2] : num(r[1]) })]);
    }));
  }
  function table(head, rows) {
    return h('table', { class: 'ys-table-mini' }, [
      h('thead', {}, [h('tr', {}, head.map(function (x) { return h('th', { text: x }); }))]),
      h('tbody', {}, rows.map(function (r) { return h('tr', {}, r.map(function (x) { return h('td', { text: String(x) }); })); }))
    ]);
  }
  function svg(w, hgt) { var s = doc.createElementNS('http://www.w3.org/2000/svg', 'svg'); s.setAttribute('viewBox', '0 0 ' + w + ' ' + hgt); s.setAttribute('class', 'ys-plot'); s.setAttribute('role', 'img'); return s; }
  function sv(s, tag, attrs, text) { var e = doc.createElementNS('http://www.w3.org/2000/svg', tag); Object.keys(attrs || {}).forEach(function (k) { e.setAttribute(k, attrs[k]); }); if (text != null) e.textContent = text; s.appendChild(e); return e; }
  function shell(host, title, controls, out) {
    host.textContent = '';
    host.appendChild(h('div', { class: 'ys-lab-head' }, [h('p', { class: 'ys-lab-title', text: title }), h('span', { class: 'ys-lab-hint', text: t('Move the controls; everything is computed in your browser.', 'Muovi i controlli; tutto è calcolato nel tuo browser.') })]));
    host.appendChild(h('div', { class: 'ys-lab-body' }, [h('div', { class: 'ys-ctl' }, controls), out]));
  }

  var LABS = {};

  /* ---------- activity: who is selected in a slot ---------- */
  LABS.activity = function (host) {
    var H = [0.2, 0.1, 0.05, 0.05, 0.1, 0.2, 0.4, 0.6, 0.8, 0.9, 0.8, 0.8, 0.9, 0.9, 0.8, 0.8, 0.8, 0.9, 1.0, 1.0, 1.0, 0.9, 0.6, 0.4];
    var PROF = { high: [0, 23], medium: [8, 9, 12, 13, 18, 19, 20, 21], low: [19, 20, 21] };
    var S = { prof: 'none', level: 3 }, out = h('div', { class: 'ys-out' });
    function inProf(hr) { var p = PROF[S.prof]; if (S.prof === 'high') return true; return p.indexOf(hr) >= 0; }
    function draw() {
      out.textContent = '';
      var f = clamp(S.level / 5, 0, 1), s = svg(480, 150), exp = 0;
      for (var hr = 0; hr < 24; hr++) {
        var p = S.prof === 'none' ? clamp(H[hr] * f, 0, 1) : (inProf(hr) ? 1 : 0); exp += p;
        sv(s, 'rect', { x: 14 + hr * 19, y: 120 - p * 100, width: 16, height: Math.max(p * 100, 1), rx: 3, fill: 'var(--accent)', opacity: 0.55 + 0.4 * p });
        if (hr % 3 === 0) sv(s, 'text', { x: 22 + hr * 19, y: 138, 'text-anchor': 'middle', 'font-size': 9, fill: 'var(--muted)' }, String(hr));
      }
      out.appendChild(s);
      out.appendChild(h('div', { class: 'ys-kpis' }, [kpi(t('Slots per day the agent acts (expected)', 'Slot al giorno in cui l’agente agisce (atteso)'), num(exp)), kpi(t('Mode', 'Modalità'), S.prof === 'none' ? t('probability per hour', 'probabilità oraria') : t('fixed hours', 'ore fisse'))]));
      out.appendChild(h('p', { class: 'ys-lab-hint', text: t('If the agent has an activity_profile that exists in simulation.activity_profiles, it acts in exactly the hours of that profile (probability 1, 0 outside) and daily_activity_level is not used. Without a profile, the probability in each hour is hourly_activity[hour] × daily_activity_level / 5 (capped at 1). A level of 0 or less means the agent never acts; churned agents are skipped.', 'Se l’agente ha un activity_profile presente in simulation.activity_profiles, agisce esattamente nelle ore di quel profilo (probabilità 1, 0 fuori) e daily_activity_level non è usato. Senza profilo, la probabilità in ogni ora è hourly_activity[ora] × daily_activity_level / 5 (limitata a 1). Un livello pari o inferiore a 0 significa che l’agente non agisce mai; gli agenti che hanno abbandonato sono saltati.') }));
    }
    shell(host, t('Who acts in a slot', 'Chi agisce in uno slot'), [
      select(t('activity_profile', 'activity_profile'), [['none', t('(none)', '(nessuno)')], ['high', 'high'], ['medium', 'medium'], ['low', 'low']], 'none', function (v) { S.prof = v; draw(); }),
      slider('daily_activity_level', 1, 5, 1, 3, null, function (v) { S.level = v; draw(); })
    ], out);
    draw();
  };

  /* ---------- session: action weights, attention budget ---------- */
  LABS.session = function (host) {
    var W = { post_photo: 0.15, react: 0.20, comment: 0.15, follow: 0.10, share: 0.05, report: 0.05, save: 0.10, reply_comment: 0.10, unfollow: 0.05, send_dm: 0.05, post_story: 0.05, watch_story: 0.05 };
    var COST = { post_photo: 40, comment: 20, reply_comment: 20, send_dm: 25, react: 5, save: 5, follow: 10, share: 15, report: 10, unfollow: 5 };
    var S = { arch: 'none', ra: 4, bud: 100, seed: 3, page: false }, out = h('div', { class: 'ys-out' });
    function weights() {
      var w = {}; Object.keys(W).forEach(function (k) { w[k] = W[k]; });
      if (S.arch === 'broadcaster') { w.post_photo *= 2; w.post_story *= 2; } else if (S.arch === 'explorer') { w.watch_story *= 2; w.react *= 2; } else if (S.arch === 'validator') { w.comment *= 2; w.react *= 1.5; }
      return w;
    }
    function draw() {
      out.textContent = '';
      var w = weights(), keys = Object.keys(w), tot = keys.reduce(function (a, k) { return a + w[k]; }, 0), r = rng(S.seed);
      var n = S.page ? 1 : (function () { var hi = Math.max(1, S.ra), lo = Math.max(hi - 2, 1); return lo + Math.floor(r() * (hi - lo + 1)); })();
      var bud = S.bud, rows = [], stop = '';
      for (var i = 0; i < n; i++) {
        if (bud <= 0) { stop = t('budget exhausted', 'budget esaurito'); break; }
        var v = r() * tot, c = 0, act = keys[keys.length - 1];
        for (var j = 0; j < keys.length; j++) { c += w[keys[j]]; if (v < c) { act = keys[j]; break; } }
        var cost = COST[act] != null ? COST[act] : 10;
        if (bud < cost) { rows.push([i + 1, act, cost, bud, t('not enough: the session ends', 'non basta: la sessione finisce')]); stop = t('session ended', 'sessione conclusa'); break; }
        bud -= cost; rows.push([i + 1, act, cost, bud, 'ok']);
      }
      out.appendChild(bars(keys.map(function (k) { return [k, w[k] / tot, pct(w[k] / tot)]; }), Math.max.apply(null, keys.map(function (k) { return w[k] / tot; }))));
      out.appendChild(h('div', { class: 'ys-kpis' }, [kpi(t('Attempts drawn', 'Tentativi estratti'), n), kpi(t('Actions done', 'Azioni fatte'), rows.filter(function (x) { return x[4] === 'ok'; }).length), kpi(t('Budget left', 'Budget residuo'), bud), kpi(t('Why it stopped', 'Perché si è fermata'), stop || t('all attempts used', 'tentativi finiti'))]));
      out.appendChild(table([t('#', '#'), t('Action', 'Azione'), t('Cost', 'Costo'), t('Budget after', 'Budget dopo'), ''], rows));
      out.appendChild(h('p', { class: 'ys-lab-hint', text: t('Each selected agent attempts a random number of actions between max(round_actions − 2, 1) and round_actions (a page, is_page = 1, attempts exactly one). Each attempt draws an action with random.choices weighted by actions_likelihood, shaped by the archetype (broadcaster ×2 posts and stories; explorer ×2 watch_story and react; validator ×2 comments, ×1.5 react). The action costs attention (post 40, comment and reply 20, DM 25, share 15, follow and report 10, react, save, unfollow 5; others 10); if the budget cannot pay it the session ends.', 'Ogni agente selezionato tenta un numero casuale di azioni tra max(round_actions − 2, 1) e round_actions (una pagina, is_page = 1, ne tenta una sola). Ogni tentativo estrae un’azione con random.choices pesata da actions_likelihood, modificata dall’archetipo (broadcaster ×2 post e storie; explorer ×2 watch_story e react; validator ×2 commenti, ×1,5 react). L’azione costa attenzione (post 40, commento e risposta 20, DM 25, condivisione 15, follow e segnalazione 10, react, salvataggio e unfollow 5; altre 10); se il budget non la copre la sessione finisce.') }));
    }
    var again = h('button', { type: 'button', class: 'ys-btn ghost', text: t('Another session', 'Un’altra sessione') });
    again.addEventListener('click', function () { S.seed = (S.seed * 7919 + 11) % 100003; draw(); });
    shell(host, t('One session of an agent', 'Una sessione di un agente'), [
      select(t('archetype', 'archetype'), [['none', t('(none)', '(nessuno)')], ['broadcaster', 'broadcaster'], ['explorer', 'explorer'], ['validator', 'validator']], 'none', function (v) { S.arch = v; draw(); }),
      slider('round_actions', 1, 12, 1, 4, null, function (v) { S.ra = v; draw(); }),
      slider('attention_budget', 10, 200, 5, 100, null, function (v) { S.bud = v; draw(); }),
      check(t('The account is a page (is_page)', 'L’account è una pagina (is_page)'), false, function (v) { S.page = v; draw(); }),
      h('div', { class: 'ys-btnrow' }, [again])
    ], out);
    draw();
  };

  /* ---------- followgraph: follow, request, follow-back, secondary follow ---------- */
  LABS.followgraph = function (host) {
    var S = { fb: 0.1, sec: 0.1, priv: 0.2, n: 200, seed: 5 }, out = h('div', { class: 'ys-out' });
    function draw() {
      out.textContent = '';
      var r = rng(S.seed), req = 0, fol = 0, back = 0, sec = 0, secReq = 0;
      for (var i = 0; i < S.n; i++) {
        var priv = r() < S.priv;
        if (priv) req++; else { fol++; if (r() < S.fb) back++; }
        if (r() < S.sec) { if (r() < S.priv) secReq++; else sec++; }
      }
      out.appendChild(bars([[t('Direct follows', 'Follow diretti'), fol, String(fol)], [t('Follow requests (private target)', 'Richieste di follow (bersaglio privato)'), req, String(req)], [t('Follow-backs', 'Follow di ritorno'), back, String(back)], [t('Secondary follows', 'Follow secondari'), sec, String(sec)], [t('Secondary requests', 'Richieste secondarie'), secReq, String(secReq)]], S.n));
      out.appendChild(h('p', { class: 'ys-lab-hint', text: t('A follow action on a public account creates the edge at once, and with probability probability_of_follow_back the target follows back. On a private account (is_private) it creates a follow request instead, answered at slot 0 by the target with the model. After its actions, an agent also tries to follow each account it interacted with, each with probability probability_of_secondary_follow, by the same rules. Here every follow attempt has the same chance of hitting a private account and each attempt one secondary try (a simplification).', 'Un’azione di follow su un account pubblico crea subito l’arco e, con probabilità probability_of_follow_back, il bersaglio ricambia. Su un account privato (is_private) crea invece una richiesta di follow, a cui il bersaglio risponde allo slot 0 con il modello. Dopo le sue azioni, un agente prova anche a seguire ogni account con cui ha interagito, ciascuno con probabilità probability_of_secondary_follow, con le stesse regole. Qui ogni tentativo ha la stessa probabilità di colpire un account privato e ogni tentativo una prova secondaria (una semplificazione).') }));
    }
    var again = h('button', { type: 'button', class: 'ys-btn ghost', text: t('Another draw', 'Un’altra estrazione') });
    again.addEventListener('click', function () { S.seed = (S.seed * 7919 + 3) % 100003; draw(); });
    shell(host, t('Follows, requests and follow-backs', 'Follow, richieste e follow di ritorno'), [
      slider('probability_of_follow_back', 0, 1, 0.05, 0.1, num, function (v) { S.fb = v; draw(); }),
      slider('probability_of_secondary_follow', 0, 1, 0.05, 0.1, num, function (v) { S.sec = v; draw(); }),
      slider(t('Share of private accounts', 'Quota di account privati'), 0, 1, 0.05, 0.2, pct, function (v) { S.priv = v; draw(); }),
      slider(t('Follow attempts', 'Tentativi di follow'), 50, 1000, 50, 200, null, function (v) { S.n = v; draw(); }),
      h('div', { class: 'ys-btnrow' }, [again])
    ], out);
    draw();
  };

  /* ---------- homefeed: the ranking surrogate ---------- */
  LABS.homefeed = function (host) {
    var P = [
      { n: t('Photo A: close friend, small', 'Foto A: amico stretto, piccola'), inter: 12, likes: 3, comments: 1, shares: 0, viral: 1, topic: 0.5, aes: 0.5, age: 3 },
      { n: t('Photo B: stranger, popular', 'Foto B: sconosciuto, popolare'), inter: 0, likes: 60, comments: 12, shares: 8, viral: 4, topic: 1, aes: 0.8, age: 3 },
      { n: t('Photo C: friend, fresh, joyful', 'Foto C: amico, recente, gioiosa'), inter: 4, likes: 2, comments: 0, shares: 0, viral: 1, topic: 0, aes: 0.6, age: 0, joy: true },
      { n: t('Photo D: friend, old', 'Foto D: amico, vecchia'), inter: 8, likes: 20, comments: 5, shares: 2, viral: 2, topic: 0.5, aes: 0.7, age: 30 }
    ];
    var S = { decay: 0.1 }, out = h('div', { class: 'ys-out' });
    function score(p) {
      var ew = Math.log(1 + p.inter), eng = 2 * ew + Math.log(1 + p.viral), pop = Math.log(1 + p.likes + 2 * p.comments + 1.5 * p.shares);
      return (1.6 * eng + 1.2 * pop + 0.8 * p.topic + 0.4 * p.aes + (p.joy ? 0.15 : 0)) / (1 + S.decay * p.age);
    }
    function draw() {
      out.textContent = '';
      var rows = P.map(function (p) { return { p: p, s: score(p) }; }).sort(function (a, b) { return b.s - a.s; });
      out.appendChild(bars(rows.map(function (x) { return [x.p.n, x.s, num(x.s)]; })));
      out.appendChild(table([t('Photo', 'Foto'), t('Interactions with author', 'Interazioni con l’autore'), 'likes/comm./shares', t('Hours old', 'Ore di età'), 'score'], rows.map(function (x) { return [x.p.n, x.p.inter, x.p.likes + '/' + x.p.comments + '/' + x.p.shares, x.p.age, num(x.s)]; })));
      out.appendChild(h('p', { class: 'ys-lab-hint', text: t('score = (1.6 × (2 × ln(1+affinity) + ln(1+viral)) + 1.2 × ln(1 + likes + 2 × comments + 1.5 × shares) + 0.8 × topic overlap + 0.4 × aesthetic score + 0.15 if the photo has a joyful emotion + a small sentiment term) ÷ (1 + 0.1 × hours old). Affinity counts the reader’s reactions, 2 × comments and 2 × saves on the author’s photos. Age is in simulated hours, not wall clock. The example values are invented.', 'punteggio = (1,6 × (2 × ln(1+affinità) + ln(1+virale)) + 1,2 × ln(1 + like + 2 × commenti + 1,5 × condivisioni) + 0,8 × sovrapposizione di argomenti + 0,4 × punteggio estetico + 0,15 se la foto ha un’emozione gioiosa + un piccolo termine di sentiment) ÷ (1 + 0,1 × ore di età). L’affinità conta le reazioni del lettore, 2 × commenti e 2 × salvataggi sulle foto dell’autore. L’età è in ore simulate, non di orologio. I valori d’esempio sono inventati.') }));
    }
    var ctl = [slider(t('Decay per hour (fixed 0.1 in the runtime)', 'Decadimento orario (0,1 fisso nel runtime)'), 0, 0.3, 0.01, 0.1, num, function (v) { S.decay = v; draw(); })];
    P.forEach(function (p, i) { ctl.push(slider(t('Hours old: ', 'Ore di età: ') + 'ABCD'[i], 0, 48, 1, p.age, null, function (v) { p.age = v; draw(); })); });
    shell(host, t('Ranking four photos in the home feed', 'Ordinare quattro foto nel feed principale'), ctl, out);
    draw();
  };

  /* ---------- trend: hashtag momentum ---------- */
  LABS.trend = function (host) {
    var S = { recent: 12, older: 6, base: 5 }, out = h('div', { class: 'ys-out' });
    function draw() {
      out.textContent = '';
      var vel = S.older === 0 ? (S.recent > 0 ? 2 : 0) : (S.recent - S.older) / S.older, m = clamp(1 + vel, 0.5, 2);
      out.appendChild(h('div', { class: 'ys-kpis' }, [kpi(t('Velocity', 'Velocità'), num(vel)), kpi(t('Momentum multiplier', 'Moltiplicatore di momento'), '×' + num(m), m > 1 ? 'ok' : ''), kpi(t('Explore score', 'Punteggio explore'), num(S.base) + ' → ' + num(S.base * m))]));
      out.appendChild(bars([[t('Last 24 hours', 'Ultime 24 ore'), S.recent, String(S.recent)], [t('The 24 hours before', 'Le 24 ore prima'), S.older, String(S.older)]]));
      out.appendChild(h('p', { class: 'ys-lab-hint', text: t('For every hashtag of a photo the service counts the photos carrying it in the last 24 simulated hours and in the 24 before. Velocity = (recent − older) ÷ older; with no older photos a new trend gets 2.0. The momentum is 1 + velocity limited to [0.5, 2] and the multipliers of the photo’s hashtags are averaged. The explore score of the photo is multiplied by it.', 'Per ogni hashtag di una foto il servizio conta le foto che lo portano nelle ultime 24 ore simulate e nelle 24 prima. Velocità = (recenti − precedenti) ÷ precedenti; senza foto precedenti una tendenza nuova riceve 2,0. Il momento è 1 + velocità limitato a [0,5, 2] e i moltiplicatori degli hashtag della foto sono mediati. Il punteggio explore della foto è moltiplicato per esso.') }));
    }
    shell(host, t('Hashtag momentum in Explore', 'Il momento degli hashtag in Explore'), [
      slider(t('Photos with the hashtag, last 24 h', 'Foto con l’hashtag, ultime 24 h'), 0, 40, 1, 12, null, function (v) { S.recent = v; draw(); }),
      slider(t('Photos with the hashtag, the 24 h before', 'Foto con l’hashtag, le 24 h prima'), 0, 40, 1, 6, null, function (v) { S.older = v; draw(); }),
      slider(t('Explore score before the multiplier', 'Punteggio explore prima del moltiplicatore'), 1, 10, 0.5, 5, num, function (v) { S.base = v; draw(); })
    ], out);
    draw();
  };

  /* ---------- moderation: toxicity stub ---------- */
  LABS.moderation = function (host) {
    var KW = ['hate', 'kill', 'die', 'stupid', 'idiot', 'spam'];
    var S = { text: 'This is stupid spam, I hate it', reported: false, kind: 'photo' }, out = h('div', { class: 'ys-out' });
    function draw() {
      out.textContent = '';
      var low = S.text.toLowerCase(), hit = KW.filter(function (k) { return low.indexOf(k) >= 0; }), tox = Math.min(1, 0.3 * hit.length), res, pen = '';
      if (S.reported) { res = tox > 0.3 ? 'remove' : 'keep'; if (res === 'remove') pen = 'warn'; }
      else if (tox > 0.5) { res = 'remove'; pen = (S.kind === 'photo' && tox >= 0.8) ? 'shadow-ban' : 'warn'; } else res = 'keep';
      out.appendChild(h('div', { class: 'ys-kpis' }, [kpi(t('Keywords found', 'Parole chiave trovate'), hit.length ? hit.join(', ') : t('none', 'nessuna')), kpi(t('Toxicity score', 'Punteggio di tossicità'), num(tox)), kpi(t('Decision', 'Decisione'), res === 'remove' ? t('removed', 'rimosso') : t('kept', 'tenuto'), res === 'remove' ? '' : 'ok'), kpi(t('Penalty to the author', 'Sanzione all’autore'), pen === 'warn' ? t('warn: stress +0.2', 'avviso: stress +0,2') : pen === 'shadow-ban' ? t('shadow-ban: stress +0.5', 'shadow-ban: stress +0,5') : t('none', 'nessuna'))]));
      out.appendChild(h('p', { class: 'ys-lab-hint', text: t('A stub, not a model: each banned keyword (hate, kill, die, stupid, idiot, spam) adds 0.3 up to 1. Proactive scan of the round’s content: above 0.5 the content is removed; for photos a score of 0.8 or more also shadow-bans the author, otherwise the author is warned; a removed comment only warns. A reported item is checked with a lower bar: removed above 0.3 (or when the reason says spam) and the author is warned. Every decision is a row of moderation_events. Stress is capped at 1.', 'Un sostituto, non un modello: ogni parola vietata (hate, kill, die, stupid, idiot, spam) aggiunge 0,3 fino a 1. Scansione proattiva dei contenuti del turno: sopra 0,5 il contenuto è rimosso; per le foto un punteggio di 0,8 o più mette anche l’autore in shadow-ban, altrimenti l’autore riceve un avviso; un commento rimosso avvisa soltanto. Un contenuto segnalato è controllato con una soglia più bassa: rimosso sopra 0,3 (o quando il motivo dice spam) e l’autore è avvisato. Ogni decisione è una riga di moderation_events. Lo stress è limitato a 1.') }));
    }
    var ta = h('textarea', { rows: '3', 'aria-label': 'caption' }); ta.value = S.text; ta.addEventListener('input', function () { S.text = ta.value; draw(); });
    shell(host, t('How content is moderated', 'Come si modera un contenuto'), [
      h('label', {}, [h('b', {}, [h('span', { text: t('Caption or comment', 'Didascalia o commento') })]), ta]),
      select(t('Content', 'Contenuto'), [['photo', t('Photo caption', 'Didascalia di foto')], ['comment', t('Comment', 'Commento')]], 'photo', function (v) { S.kind = v; draw(); }),
      check(t('Someone reported it', 'Qualcuno l’ha segnalato'), false, function (v) { S.reported = v; draw(); })
    ], out);
    draw();
  };

  /* ---------- stress: events, coupling ---------- */
  LABS.stress = function (host) {
    var EV = { like: [t('Reaction: like', 'Reazione: like'), -0.005, 0.03, 'reaction'], dislike: [t('Reaction: dislike', 'Reazione: dislike'), 0.03, -0.02, 'reaction'],
      positive: [t('Comment: positive', 'Commento: positivo'), -0.02, 0.07], neutral: [t('Comment: neutral', 'Commento: neutro'), 0, 0.01], critical: [t('Comment: critical', 'Commento: critico'), 0.03, -0.01],
      hostile: [t('Comment: hostile', 'Commento: ostile'), 0.1, -0.05], supportive: [t('Comment: supportive', 'Commento: di supporto'), -0.05, 0.08],
      shpos: [t('Share: positive', 'Condivisione: positiva'), -0.01, 0.08], shhos: [t('Share: hostile', 'Condivisione: ostile'), 0.12, -0.06], report: [t('Reports: mass report', 'Segnalazioni: segnalazione di massa'), 0.06, -0.03] };
    var S = { log: [], alpha: 0.3, beta: 0.2, bias: -1.8 }, out = h('div', { class: 'ys-out' }), btns = h('div', { class: 'ys-btnrow ys-evbtns' });
    function c01(x) { return Math.max(0, Math.min(1, x)); }
    function run() {
      var st = 0.2, rw = 0.4, hist = [[st, rw]];
      S.log.forEach(function (k) {
        var ds = EV[k][1], dr = EV[k][2];
        if (EV[k][3] === 'reaction') { ds *= Math.log(2); dr *= Math.log(2); }
        if (ds > 0) ds *= Math.max(0, 1 - S.alpha * rw); if (dr > 0) dr *= Math.max(0, 1 - S.beta * st);
        st = c01(st + ds); rw = c01(rw + dr); hist.push([st, rw]);
      });
      return { st: st, rw: rw, hist: hist };
    }
    function draw() {
      out.textContent = '';
      var r = run(), lg = (2 * r.st - 1 * r.rw + S.bias) / 0.3, ch = Math.min(0.95, Math.max(0, 1 / (1 + Math.exp(-lg))));
      out.appendChild(h('div', { class: 'ys-kpis' }, [kpi('Stress', num(r.st)), kpi(t('Reward', 'Ricompensa'), num(r.rw)), kpi(t('Churn formula', 'Formula di abbandono'), pct(ch))]));
      var s = svg(480, 150), n = Math.max(r.hist.length - 1, 10), xs = 456 / n, ps = '', pr = '';
      r.hist.forEach(function (v, k) { ps += (k ? 'L' : 'M') + (12 + k * xs) + ' ' + (136 - v[0] * 120) + ' '; pr += (k ? 'L' : 'M') + (12 + k * xs) + ' ' + (136 - v[1] * 120) + ' '; });
      sv(s, 'path', { d: pr, fill: 'none', stroke: 'var(--accent-2)', 'stroke-width': 2.5 }); sv(s, 'path', { d: ps, fill: 'none', stroke: 'var(--accent)', 'stroke-width': 2.5, 'stroke-dasharray': '5 4' });
      out.appendChild(s);
      out.appendChild(h('p', { class: 'ys-lab-hint', text: t('Solid: reward. Dashed: stress. Each click is one event received by a creator: the deltas come from the event table (reactions are multiplied by ln 2 for one reaction), a rise of stress is damped by 1 − alpha × reward and a rise of reward by 1 − beta × stress. The state starts from the defaults the module uses when it knows nothing (stress 0.2, reward 0.4). The churn formula, sigmoid((2 × stress − reward + bias) ÷ 0.3) within [0, 0.95], is provided by the module; the live churn of the platform is driven by satisfaction and inactivity (see the page on lifecycle).', 'Linea piena: ricompensa. Tratteggiata: stress. Ogni clic è un evento ricevuto da un creatore: i delta vengono dalla tabella degli eventi (una reazione è moltiplicata per ln 2), un aumento di stress è smorzato da 1 − alpha × ricompensa e un aumento di ricompensa da 1 − beta × stress. Lo stato parte dai valori che il modulo usa quando non sa nulla (stress 0,2, ricompensa 0,4). La formula di abbandono, sigmoide((2 × stress − ricompensa + bias) ÷ 0,3) in [0, 0,95], è fornita dal modulo; l’abbandono effettivo della piattaforma è guidato da soddisfazione e inattività (vedi la pagina sul ciclo di vita).') }));
    }
    Object.keys(EV).forEach(function (k) { var b = h('button', { type: 'button', class: 'ys-btn ghost', text: '+ ' + EV[k][0] }); b.addEventListener('click', function () { S.log.push(k); draw(); }); btns.appendChild(b); });
    var clr = h('button', { type: 'button', class: 'ys-btn', text: t('Clear', 'Azzera') }); clr.addEventListener('click', function () { S.log = []; draw(); });
    shell(host, t('Events, stress and reward of a creator', 'Eventi, stress e ricompensa di un creatore'), [
      btns, h('div', { class: 'ys-btnrow' }, [clr]),
      slider('reward_buffers_stress_alpha', 0, 1, 0.05, 0.3, num, function (v) { S.alpha = v; draw(); }),
      slider('stress_reduces_reward_beta', 0, 1, 0.05, 0.2, num, function (v) { S.beta = v; draw(); }),
      slider('churn.bias', -4, 1, 0.1, -1.8, num, function (v) { S.bias = v; draw(); })
    ], out);
    draw();
  };

  /* ---------- satisfaction: churn from low engagement ---------- */
  LABS.satisfaction = function (host) {
    var S = { gain: 0, every: 3, days: 100 }, out = h('div', { class: 'ys-out' });
    function draw() {
      out.textContent = '';
      var sat = 100, pts = [100], left = null, i;
      for (i = 1; i <= S.days * 1; i++) {
        var gained = S.gain > 0 && i % S.every === 0 ? S.gain : 0;
        sat = clamp(sat + (gained > 0 ? 5 * gained : -1), 0, 100); pts.push(sat);
        if (sat <= 10 && left == null) { left = i; break; }
      }
      var s = svg(480, 150), n = Math.max(pts.length - 1, 10);
      sv(s, 'line', { x1: 12, x2: 468, y1: 136 - 10 * 1.2, y2: 136 - 10 * 1.2, stroke: 'var(--muted)', 'stroke-dasharray': '4 4' });
      sv(s, 'text', { x: 468, y: 136 - 10 * 1.2 - 4, 'text-anchor': 'end', 'font-size': 9, fill: 'var(--muted)' }, t('churn at 10', 'abbandono a 10'));
      var d = ''; pts.forEach(function (v, k) { d += (k ? 'L' : 'M') + (12 + k * 456 / n) + ' ' + (136 - v * 1.2) + ' '; });
      sv(s, 'path', { d: d, fill: 'none', stroke: 'var(--accent)', 'stroke-width': 2.5 });
      out.appendChild(s);
      out.appendChild(h('div', { class: 'ys-kpis' }, [kpi(t('Satisfaction at the end', 'Soddisfazione alla fine'), num(sat)), kpi(t('Churn', 'Abbandono'), left ? t('after ', 'dopo ') + left + t(' active turns', ' turni attivi') : t('does not leave', 'non se ne va'), left ? '' : 'ok')]));
      out.appendChild(h('p', { class: 'ys-lab-hint', text: t('Every turn an agent acts, its satisfaction (0–100, starts at 100) changes: +5 for every follower gained since the last turn, otherwise −1. At 10 or less the account is marked as churned and stops acting. Here a fixed number of followers is gained every few turns.', 'A ogni turno in cui agisce, la soddisfazione di un agente (0–100, parte da 100) cambia: +5 per ogni follower guadagnato dall’ultimo turno, altrimenti −1. A 10 o meno l’account è segnato come uscito e smette di agire. Qui un numero fisso di follower è guadagnato ogni tot turni.') }));
    }
    shell(host, t('Satisfaction and churn', 'Soddisfazione e abbandono'), [
      slider(t('Followers gained each time', 'Follower guadagnati ogni volta'), 0, 5, 1, 0, null, function (v) { S.gain = v; draw(); }),
      slider(t('...every N active turns', '...ogni N turni attivi'), 1, 20, 1, 3, null, function (v) { S.every = v; draw(); }),
      slider(t('Active turns shown', 'Turni attivi mostrati'), 20, 200, 10, 100, null, function (v) { S.days = v; draw(); })
    ], out);
    draw();
  };
/* ---------- opinions: bounded confidence ---------- */
  LABS.opinions = function (host) {
    var S = { eps: 0.25, mu: 0.5, theta: 0, n: 60, step: 0, timer: null, ops: [], seed: 4 }, out = h('div', { class: 'ys-out' }), rnd;
    function reset() { stop(); rnd = rng(S.seed); S.ops = []; for (var i = 0; i < S.n; i++) S.ops.push(rnd()); S.step = 0; draw(); }
    function stop() { if (S.timer) { clearInterval(S.timer); S.timer = null; } }
    function bc(x, y) { if (Math.abs(y - x) > S.eps) { if (S.theta) return x > y ? Math.min(x + S.theta, 1) : Math.max(x - S.theta, 0); return x; } return x + S.mu * (y - x); }
    function tick(k) { for (var q = 0; q < k; q++) { var i = Math.floor(rnd() * S.n), j = Math.floor(rnd() * S.n); if (i === j) continue; S.ops[i] = bc(S.ops[i], S.ops[j]); S.step++; } }
    function draw() {
      out.textContent = '';
      var B = 20, h2 = []; for (var b = 0; b < B; b++) h2.push(0);
      S.ops.forEach(function (v) { h2[Math.min(B - 1, Math.floor(v * B))]++; });
      var s = svg(480, 140), m = Math.max.apply(null, h2.concat([1]));
      h2.forEach(function (c, k) { sv(s, 'rect', { x: 12 + k * 22.8, y: 118 - c / m * 100, width: 20, height: c / m * 100, rx: 3, fill: 'var(--accent)', opacity: 0.85 }); });
      [0, 0.5, 1].forEach(function (v) { sv(s, 'text', { x: 12 + v * 456, y: 134, 'text-anchor': v === 0 ? 'start' : v === 1 ? 'end' : 'middle', 'font-size': 9, fill: 'var(--muted)' }, String(v)); });
      out.appendChild(s);
      var sorted = S.ops.slice().sort(function (a, b) { return a - b; }), clusters = 1; for (var i = 1; i < sorted.length; i++) if (sorted[i] - sorted[i - 1] > 0.05) clusters++;
      var mean = S.ops.reduce(function (a, b) { return a + b; }, 0) / S.n, sd = Math.sqrt(S.ops.reduce(function (a, b) { return a + (b - mean) * (b - mean); }, 0) / S.n);
      out.appendChild(h('div', { class: 'ys-kpis' }, [kpi(t('Interactions', 'Interazioni'), S.step), kpi(t('Clusters (gap > 0.05)', 'Gruppi (distanza > 0,05)'), clusters), kpi(t('Spread (std)', 'Dispersione (dev. std)'), num(sd))]));
      out.appendChild(h('p', { class: 'ys-lab-hint', text: t('Each interaction is one agent (reader) reading another (author) on a topic. If their opinions are within epsilon the reader moves a fraction mu towards the author; otherwise it stays, or, if theta is not 0, steps away from the author by theta (clamped to [0, 1]). Same rule as the bounded_confidence model; in a run the topic of a message decides who interacts.', 'Ogni interazione è un agente (lettore) che legge un altro (autore) su un argomento. Se le loro opinioni distano meno di epsilon il lettore si sposta di una frazione mu verso l’autore; altrimenti resta fermo oppure, se theta non è 0, si allontana dall’autore di theta (limitato a [0, 1]). Stessa regola del modello bounded_confidence; in una run è l’argomento del messaggio a decidere chi interagisce.') }));
    }
    var play = h('button', { type: 'button', class: 'ys-btn', text: t('▶ Play', '▶ Avvia') });
    play.addEventListener('click', function () { if (S.timer) { stop(); return; } S.timer = setInterval(function () { tick(30); draw(); if (S.step > 6000) stop(); }, 80); });
    var one = h('button', { type: 'button', class: 'ys-btn ghost', text: t('+100 interactions', '+100 interazioni') });
    one.addEventListener('click', function () { stop(); tick(100); draw(); });
    var rs = h('button', { type: 'button', class: 'ys-btn ghost', text: t('Reset', 'Azzera') });
    rs.addEventListener('click', reset);
    shell(host, t('Opinions that attract (and repel)', 'Opinioni che si attraggono (e si respingono)'), [
      slider('epsilon', 0.05, 0.6, 0.01, 0.25, num, function (v) { S.eps = v; }),
      slider('mu', 0.05, 0.5, 0.01, 0.5, num, function (v) { S.mu = v; }),
      slider('theta', 0, 0.1, 0.005, 0, num, function (v) { S.theta = v; }),
      h('div', { class: 'ys-btnrow' }, [play, one, rs])
    ], out);
    reset();
  };

  
  /* ---------- boot ---------- */
  function boot() {
    Array.prototype.forEach.call(doc.querySelectorAll('.ys-lab[data-lab]'), function (el) {
      var f = LABS[el.getAttribute('data-lab')];
      if (!f) return;
      try { f(el); } catch (e) { el.textContent = 'Interactive explainer unavailable.'; if (window.console) console.error(e); }
    });
  }
  if (doc.readyState === 'loading') doc.addEventListener('DOMContentLoaded', boot); else boot();
})();
