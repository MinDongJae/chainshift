/* 여러 담당자의 의견 모으기 — 화면 쪽.
   붙이는 법: 이 파일과 committee.css 를 화면에 싣기만 하면 된다. 화면의 다른 코드 · 꾸밈을 고치지 않는다.
   - 답 카드(#card) 바로 아래에 자리(#committee)를 스스로 만든다.
   - 답이 끝난 것은 답 카드에 「답 전체와 출처」 단추(#more)가 생기는 것으로 안다.
   - 방금 답의 질문 · 답 · 자료는 화면이 서버에서 받아 오는 응답을 옆에서 함께 읽어 얻는다(받아 둔 실제 답은 window.KIC.rec).
   글은 모두 words.json 에서 읽는다. */
(() => {
  'use strict';
  if (window.KICCommittee) return;                      // 두 번 실려도 한 번만 돈다
  window.KICCommittee = { version: 1 };
  const API = '/api/kic-agent/committee', $ = (s, el = document) => el.querySelector(s);
  const esc = t => String(t == null ? '' : t).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const fmt = (t, o) => String(t).replace(/\{(\w+)\}/g, (m, k) => (k in o ? o[k] : m));
  let W = null, box = null, live = null, run = null, seq = 0;
  const jobs = {}; // 역할 → { ctrl, runId, state }

  /* ── 방금 답의 기록 얻기 ─────────────────────────────── */
  const fromEvents = evs => {
    const g = t => evs.filter(e => e.type === t).pop() || {};
    const done = g('done'), ver = g('verify'), bad = (ver.sentences || []).filter(x => !x.ok).length;
    return { question: (g('received').text || '').trim(), answer: done.answer || '', evidence: g('evidence').items || [], category: g('classified').category,
      issues: (g('review').issues || []).map(i => i.label || i.kind || ''), verify: { bad }, scope: done.scope };
  };
  const _fetch = window.fetch;
  window.fetch = function (input, init) {             // 화면이 답을 받아 오는 응답을 그대로 돌려주면서 사본을 읽는다
    const p = _fetch.apply(this, arguments);
    try {
      const url = typeof input === 'string' ? input : (input && input.url) || '';
      if (/\/api\/kic-agent\/ask(\?|$)/.test(url)) {
        const mine = live = { evs: [], q: '' };
        try { mine.q = JSON.parse((init && init.body) || '{}').question || ''; } catch (e) { /* 본문 없음 */ }
        p.then(r => {
          if (!r.ok || !r.body) return;
          const rd = r.clone().body.getReader(), dec = new TextDecoder(); let buf = '';
          const pump = () => rd.read().then(({ value, done }) => {
            if (done) return; buf += dec.decode(value, { stream: true }); let i;
            while ((i = buf.indexOf('\n\n')) >= 0) { const line = buf.slice(0, i); buf = buf.slice(i + 2); if (line.startsWith('data:')) { try { mine.evs.push(JSON.parse(line.slice(5))); } catch (e) { /* 깨진 줄 */ } } }
            return pump();
          }).catch(() => {});
          pump();
        }).catch(() => {});
      }
    } catch (e) { /* 읽지 못해도 화면은 그대로 돈다 */ }
    return p;
  };
  const currentRun = () => {
    if (live && live.evs.some(e => e.type === 'done')) { const r = fromEvents(live.evs); if (!r.question) r.question = live.q; return r; }
    const rec = window.KIC && window.KIC.rec; return rec ? fromEvents(rec) : null;
  };

  /* ── 서버와 주고받기 ─────────────────────────────── */
  async function sha(t) { const b = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(t)); return [...new Uint8Array(b)].map(x => x.toString(16).padStart(2, '0')).join(''); }
  async function post(path, obj, signal) {
    const body = JSON.stringify(obj), h = { 'content-type': 'application/json' };
    try { h['x-amz-content-sha256'] = await sha(body); } catch (e) { /* 안전하지 않은 주소에서는 없음 */ }
    const tok = sessionStorage.getItem('kicAskToken'); if (tok) h['x-kic-token'] = tok;
    return _fetch(API + path, { method: 'POST', headers: h, body, signal });
  }

  /* ── 그리기 ─────────────────────────────── */
  const refs = r => (r && r.length ? ` <span class="cm-ref">${r.map(n => 'N' + n).join(' · ')}</span>` : '');
  const U = () => W.ui, R = k => W.roles[k];
  function ensureBox() {
    const card = $('#card'); if (!card) return null;
    if (!box || !box.isConnected) { box = document.createElement('section'); box.id = 'committee'; box.setAttribute('aria-live', 'polite'); card.insertAdjacentElement('afterend', box); }
    return box;
  }
  function clear() { Object.values(jobs).forEach(j => j.ctrl && j.ctrl.abort()); Object.keys(jobs).forEach(k => delete jobs[k]); if (box) { box.innerHTML = ''; box.hidden = true; } run = null; seq++; }

  function offerRow(o) {
    const opts = []; for (let n = o.n_min; n <= o.n_max; n++) opts.push(`<option value="${n}"${n === o.n ? ' selected' : ''}>${esc(fmt(W.ui.people, { n }))}</option>`);
    return `<article class="cm-role" data-role="${o.role}" data-state="ask">
      <header><b class="cm-k">${esc(o.role)}</b><h3>${esc(o.ask)}</h3></header>
      <p class="cm-why">${esc(o.why)}</p><p class="cm-note">${esc(o.note)}</p>
      <div class="cm-act"><label>${esc(U().count)} <select class="cm-n">${opts.join('')}</select></label>
        <button type="button" class="cm-go">${esc(U().approve)}</button><button type="button" class="cm-no">${esc(U().decline)}</button></div>
      <div class="cm-body" hidden></div></article>`;
  }
  async function showOffers() {
    const my = ++seq, r = currentRun(); if (!r || r.scope === 'out' || !r.answer || !ensureBox()) return;
    let j; try { j = await (await post('/offers', { run: r })).json(); } catch (e) { return; }
    if (my !== seq || !j.offers || !j.offers.length) return;
    run = r; box.hidden = false;
    box.innerHTML = `<h2 class="cm-title">${esc(U().title)}</h2>` + j.offers.map(offerRow).join('');
  }

  const stateWord = s => ({ adopted: U().agree, split: '', rejected: U().disagree }[s] || '');
  function itemLi(x, withVotes) {
    const said = withVotes && x.said ? `<ul class="cm-said">${x.said.map(s => `<li><b>${esc(s.by)}</b> <i class="cm-v cm-v-${s.vote === U().agree ? 'a' : s.vote === U().disagree ? 'd' : 'h'}">${esc(s.vote)}</i> ${esc(s.why)}</li>`).join('')}</ul>` : '';
    const cnt = 'agree' in x ? `<span class="cm-cnt">${esc(U().agree)} ${x.agree} · ${esc(U().disagree)} ${x.disagree} · ${esc(U().hold)} ${x.hold}</span>` : '';
    return `<li data-id="${esc(x.id)}"><span class="cm-by">${esc(x.by)}</span> ${esc(x.text)}${refs(x.refs)} ${cnt}${said}</li>`;
  }
  function render(role) {
    const j = jobs[role], el = $(`.cm-role[data-role="${role}"]`, box); if (!j || !el) return;
    const item = R(role).item, body = $('.cm-body', el); body.hidden = false; el.dataset.state = j.state;
    const mem = j.members.map(m => `<li class="${j.absent[m.id] ? 'off' : ''}"><b>${esc(m.id)}</b><span>${esc(m.lens)}</span><em>${esc(j.absent[m.id] || j.doing[m.id] || '')}</em></li>`).join('');
    let h = `<ul class="cm-mem">${mem}</ul>`, log = '';
    if (j.dropped) h += `<p class="cm-note">${esc(fmt(U().dropped, { n: j.dropped }))}</p>`;
    if (j.opinions.length) log += `<section class="cm-step"><h4>${esc(U().step1)}</h4>` + j.opinions.map(o => `<div class="cm-op"><h5>${esc(o.member)} · ${esc(o.lens)}</h5><ul>${o.items.map(x => itemLi(x)).join('')}</ul></div>`).join('') + '</section>';
    if (j.found) log += `<section class="cm-step"><h4>${esc(U().found)}</h4><ul>${j.found.items.map(x => `<li><span class="cm-ref">N${x.n}</span> ${esc(x.title)} <span class="cm-by">${esc(x.tag || '')}</span></li>`).join('')}</ul></section>`;
    const byId = {}; j.opinions.forEach(o => o.items.forEach(x => { byId[x.id] = x; })); (j.found ? j.found.items : []).forEach(x => { byId['new-' + x.n] = { by: W.found_by, text: x.title }; });
    const about = id => { const x = byId[id]; if (!x) return `<span class="cm-ref">${esc(id)}</span>`; const t = String(x.text); return `<span class="cm-about"><b>${esc(fmt(U().about, { by: x.by }))}</b> ${esc(t.length > 46 ? t.slice(0, 46) + '…' : t)}</span>`; };
    [1, 2].forEach(rd => {
      const ex = j.exchanges.filter(x => x.round === rd); if (!ex.length) return;
      log += `<section class="cm-step"><h4>${esc(rd === 1 ? U().step2 : U().step3)}</h4>` + ex.map(x => `<div class="cm-op"><h5>${esc(x.member)}</h5><ul>${x.votes.map(v => {
        const ch = x.changed.find(c => c.id === v.id);
        return `<li>${about(v.id)} <i class="cm-v cm-v-${v.vote === U().agree ? 'a' : v.vote === U().disagree ? 'd' : 'h'}">${esc(v.vote)}</i> ${esc(v.why)}${ch ? ` <span class="cm-ch">${esc(U().changed)} · ${esc(ch.from)} → ${esc(ch.to)}</span>` : ''}</li>`;
      }).join('')}</ul></div>`).join('') + '</section>';
    });
    const r = j.result, nOp = j.opinions.reduce((a, o) => a + o.items.length, 0), nRe = j.exchanges.reduce((a, x) => a + x.votes.length, 0);
    if (r) {
      h += `<section class="cm-step cm-result"><h4>${esc(U().step4)} · <span class="cm-state">${esc(r.state)}</span></h4>`;
      if (r.why) h += `<p>${esc(r.why)}</p>`;
      if (r.answer) h += `<div class="cm-answer"><h5>${esc(U().new_answer)}</h5><p>${esc(r.answer).replace(/\[N(\d+)\]/g, '<span class="cm-ref">N$1</span>')}</p>`
        + (r.check ? `<p class="cm-note">${r.check.failed ? esc(fmt(U().check_bad, { n: r.check.failed })) : esc(U().check_ok)}</p>` : '')
        + (r.unknown_refs && r.unknown_refs.length ? `<p class="cm-warn">${esc(U().unknown_refs)}</p>` : '') + `<p class="cm-note">${esc(U().original_kept)}</p></div>`;
      if (r.answer_error) h += `<p class="cm-warn">${esc(r.answer_error)}</p>`;
      if (role === 'K' && r.evidence) h += `<p>${esc(fmt(U().k_core, { n: r.evidence.length }))} ${r.evidence.map(n => `<span class="cm-ref">N${n}</span>`).join(' ')}</p>`;
      if (r.split && r.split.length) h += `<div class="cm-list cm-split"><h5>${esc(fmt(U().split, { item }))} ${r.split.length}</h5><ul>${r.split.map(x => itemLi(x, true)).join('')}</ul></div>`;
      [['adopted', U().adopted], ['rejected', U().rejected]].forEach(([k, t]) => {
        if (r[k] && r[k].length) h += `<details class="cm-fold cm-list cm-${k}"><summary>${esc(fmt(t, { item }))} ${r[k].length}</summary><ul>${r[k].map(x => itemLi(x, k !== 'adopted')).join('')}</ul></details>`;
      });
      h += '</section>';
    }
    if (log) h += j.state === 'running' ? log : `<details class="cm-fold cm-log"><summary>${esc(fmt(U().log, { op: nOp, re: nRe }))}</summary>${log}</details>`;
    if (j.state === 'stopped') h += `<p class="cm-warn">${esc(j.why === 'time' ? U().timeout : U().stopped)}</p>`;
    if (j.state === 'failed') h += `<p class="cm-warn">${esc(j.msg || U().failed)}</p>`;
    body.innerHTML = h;
    const busy = Object.values(jobs).some(x => x.state === 'running');
    box.querySelectorAll('.cm-go').forEach(b => { b.disabled = busy; b.title = busy ? U().one_at_a_time : ''; });
    $('.cm-act', el).innerHTML = j.state === 'running' ? `<button type="button" class="cm-stop">${esc(U().stop)}</button>` : `<button type="button" class="cm-again">${esc(U().reopen)}</button>`;
  }

  /* ── 승인 · 거절 · 중단 ─────────────────────────────── */
  async function approve(role, n) {
    const my = seq, j = jobs[role] = { ctrl: new AbortController(), state: 'running', members: [], doing: {}, absent: {}, opinions: [], exchanges: [], found: null, result: null, runId: '' };
    try {
      const r = await post('/run', { role, n, run }, j.ctrl.signal);
      if (!r.ok || !r.body) { try { j.msg = (await r.json()).message || ''; } catch (e) { /* 본문 없음 */ } throw new Error('no stream'); }
      j.runId = r.headers.get('x-run-id') || '';
      const rd = r.body.getReader(), dec = new TextDecoder(); let buf = '';
      for (;;) {
        const { value, done } = await rd.read(); if (done) break;
        buf += dec.decode(value, { stream: true }); let i;
        while ((i = buf.indexOf('\n\n')) >= 0) {
          const line = buf.slice(0, i); buf = buf.slice(i + 2); if (!line.startsWith('data:') || my !== seq) continue;
          const e = JSON.parse(line.slice(5));
          if (e.type === 'run') j.runId = e.run_id;
          else if (e.type === 'start') j.members = e.members;
          else if (e.type === 'dropped') j.dropped = e.count;
          else if (e.type === 'thinking') { j.doing = { [e.member]: e.step }; }
          else if (e.type === 'absent') j.absent[e.member] = U().absent;
          else if (e.type === 'opinion') { j.opinions.push(e); j.doing = {}; }
          else if (e.type === 'found') j.found = e;
          else if (e.type === 'exchange') { j.exchanges.push(e); j.doing = {}; }
          else if (e.type === 'result') { j.result = e; j.state = 'done'; j.doing = {}; }
          else if (e.type === 'stopped') { j.state = 'stopped'; j.why = e.why; j.doing = {}; }
          else if (e.type === 'error') { j.state = 'failed'; j.doing = {}; }
          render(role);
        }
      }
      if (j.state === 'running') { j.state = 'failed'; render(role); }
    } catch (err) { if (my !== seq) return; j.state = err.name === 'AbortError' ? 'stopped' : 'failed'; j.doing = {}; render(role); }
  }
  function stopJob(role) {
    const j = jobs[role]; if (!j || j.state !== 'running') return;
    post('/cancel', { role, run_id: j.runId, question: run && run.question }).catch(() => {});
    j.ctrl.abort(); j.state = 'stopped'; j.doing = {}; render(role);
  }
  function decline(role, el) {
    post('/decision', { role, decision: 'decline', question: run && run.question }).catch(() => {});
    el.dataset.state = 'declined';
    $('.cm-act', el).innerHTML = `<span class="cm-note">${esc(U().declined)}</span> <button type="button" class="cm-again">${esc(U().reopen)}</button>`;
  }
  document.addEventListener('click', e => {
    const el = e.target.closest && e.target.closest('#committee .cm-role'); if (!el) return;
    const role = el.dataset.role;
    if (e.target.matches('.cm-go')) { if (Object.values(jobs).some(x => x.state === 'running')) return; const n = +$('.cm-n', el).value; el.dataset.state = 'running'; $('.cm-act', el).innerHTML = `<button type="button" class="cm-stop">${esc(U().stop)}</button>`; box.querySelectorAll('.cm-go').forEach(b => { b.disabled = true; b.title = U().one_at_a_time; }); approve(role, n); }
    else if (e.target.matches('.cm-no')) decline(role, el);
    else if (e.target.matches('.cm-stop')) stopJob(role);
    else if (e.target.matches('.cm-again')) { if (jobs[role] && jobs[role].ctrl) jobs[role].ctrl.abort(); delete jobs[role]; showOffers(); }
  });

  /* ── 답이 끝났는지 지켜보기 ─────────────────────────────── */
  function watch() {
    const card = $('#card'); if (!card) return;
    let had = false;
    const see = () => { const has = !!$('#more', card); if (has && !had) showOffers(); else if (!has && had) clear(); had = has; };
    new MutationObserver(see).observe(card, { childList: true, subtree: true }); see();
  }
  const start = () => _fetch('/words.json').then(r => r.json()).then(j => { W = j; watch(); }).catch(() => {});
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
  Object.assign(window.KICCommittee, { refresh: showOffers, clear });
})();
