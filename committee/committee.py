# -*- coding: utf-8 -*-
"""여러 담당자의 의견 모으기 — K · I · C 역할마다, 필요할 때 같은 역할의 담당을 여럿 두고
① 각자 의견 → ② 서로의 의견을 읽고 동의 · 반대 · 보류와 까닭을 주고받음 → ③ 갈린 것만 한 번 더 → ④ 모인 뜻과 갈린 뜻을 가른다.

이 파일은 차례와 셈만 맡는다. 역할 · 관점 · 화면 글은 words.json 에서 읽는다.
실제로 묻는 일은 밖에서 넣어 주는 ask(member, system, prompt, tier) 가 한다(tier: "fast" | "write").
먼저 사용자에게 물을지(offers)는 앞서 끝난 답의 기록만 보고 코드로 정한다 — 모델을 부르지 않는다.
사용자가 승인한 역할만 run() 으로 돈다. 중단은 should_stop() 이 참을 돌려주면 다음 물음 앞에서 멈춘다."""
import json, re, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

W = json.loads((Path(__file__).resolve().parent / "words.json").read_text(encoding="utf-8"))
ROLES, P, ST, STEP = W["roles"], W["prompt"], W["states"], W["steps"]
AGREE, DISAGREE, HOLD = W["ui"]["agree"], W["ui"]["disagree"], W["ui"]["hold"]   # closed-class: 표는 이 셋뿐
ADOPT, REJECT, SPLIT = "adopted", "rejected", "split"
MAX_ITEMS, EV_CHARS = 5, 420          # 한 담당이 내는 의견 수 · 담당에게 보여 주는 자료 한 건의 글자 수


# ---------------------------------------------------------------- 먼저 물을지 정하기
def offers(run):
    """끝난 답의 기록을 보고 어느 역할에 의견 모으기를 권할지 정한다. 돌려주는 글은 사용자에게 그대로 보인다."""
    O = W["offer"]; ev = run.get("evidence") or []; ans = run.get("answer") or ""; issues = run.get("issues") or []
    cited = {int(n) for n in re.findall(r"\[N(\d+)\]", ans)}; v = run.get("verify") or {}; out = []
    if ev and (len(ev) < 6 or len(cited) * 3 <= len(ev)):
        why = O["K_few"].format(found=len(ev)) if len(ev) < 6 else O["K_unused"].format(found=len(ev), cited=len(cited))
        out.append({"role": "K", "why": why + O["K_tail"]})
    causal = bool(re.search(O["causal_pattern"], (run.get("question") or "") + " " + ans))
    strong = [x for x in issues if re.search(O["strong_pattern"], x)]
    if ans and (causal or strong):
        out.append({"role": "I", "why": (O["I_causal"] if causal else O["I_strong"]) + O["I_tail"]})
    if ans and (v.get("bad", 0) > 0 or len(issues) >= 3):
        why = O["C_bad"].format(bad=v.get("bad")) if v.get("bad", 0) > 0 else O["C_many"].format(issues=len(issues))
        out.append({"role": "C", "why": why + O["C_tail"]})
    for o in out:
        r = ROLES[o["role"]]
        o.update({"name": r["name"], "n": 3, "n_min": 2, "n_max": 5, "ask": O["ask"].format(name=r["name"]), "note": O["note"]})
    return out


# ---------------------------------------------------------------- 셈
def tally(items, votes, members):
    """의견마다 동의 · 반대 · 보류를 세어 가른다. 낸 사람은 자기 의견에 동의한 것으로 센다.
    받아들임: 동의가 과반이고 반대보다 많다 / 받아들이지 않음: 반대가 과반 / 그 밖은 갈림."""
    n = len(members); need = n // 2 + 1; out = []
    for it in items:
        cnt = {AGREE: 0, DISAGREE: 0, HOLD: 0}; said = []
        for m in members:
            if m == it["by"]: cnt[AGREE] += 1; continue
            v = votes.get((m, it["id"]))
            if v is None: cnt[HOLD] += 1; said.append({"by": m, "vote": HOLD, "why": P["no_vote"]}); continue
            cnt[v["vote"]] += 1; said.append({"by": m, "vote": v["vote"], "why": v.get("why", "")})
        state = ADOPT if cnt[AGREE] >= need and cnt[AGREE] > cnt[DISAGREE] else REJECT if cnt[DISAGREE] >= need else SPLIT
        out.append({**it, "agree": cnt[AGREE], "disagree": cnt[DISAGREE], "hold": cnt[HOLD], "state": state, "said": said})
    return out


def outcome(rows):
    a = sum(r["state"] == ADOPT for r in rows); s = sum(r["state"] == SPLIT for r in rows)
    return ST["all"] if a and not s else ST["some"] if a else ST["none"]


# ---------------------------------------------------------------- 담당에게 보내는 글
def _ev_block(ev):
    return "\n".join(f"[N{e['n']}] ({e.get('tag') or ''}{' · ' + e['published_at'] if e.get('published_at') else ''}) {e.get('title', '')}\n{(e.get('text') or '')[:EV_CHARS]}" for e in ev)


def _system(role, lens):
    r = ROLES[role]
    return W["system"].format(name=r["name"], lens=lens[0], lens_desc=lens[1], task=r["task"])


def _head(role, run):
    L = [f"{P['q']}: {run['question']}", "", f"{P['ev']}:", _ev_block(run["evidence"]), ""]
    if role != "K": L += [f"{P['answer']}:", run.get("answer", ""), ""]
    return L


def _first(role, run):
    r = ROLES[role]
    return "\n".join(_head(role, run) + [P["count"].format(item=r["item"], n=MAX_ITEMS), f"{P['format']}: {r['first_format']}"])


def _refs(i):
    return f" [{P['refs']} {', '.join('N' + str(n) for n in i['refs'])}]" if i.get("refs") else ""


def _exchange(role, run, mine, others, prior):
    r = ROLES[role]; L = _head(role, run)
    L += [P["mine"].format(item=r["item"]) + ":"] + [f"- {i['id']}: {i['text']}" for i in mine] + ["", P["others"].format(item=r["item"]) + ":"]
    L += [f"- {i['id']} ({i['by']}): {i['text']}{_refs(i)}" for i in others]
    if prior:
        L += ["", P["prior"]]
        for p in prior:
            L.append(f"- {p['id']}: {p['text']}")
            L += [f"    · {s['by']} {s['vote']} — {s['why']}" for s in p["said"]]
        L += ["", P["prior_tail"]]
    L += ["", P["vote"].format(item=r["item"]), f"{P['format']}: {P['vote_format']}"]
    return "\n".join(L)


def _compose(role, run, adopted):
    r = ROLES[role]
    L = _head(role, run) + [P["adopted_claims"].format(item=r["item"])] + [f"- {i['text']}{_refs(i)}" for i in adopted]
    return "\n".join(L + ["", r["compose"], f"{P['format']}: {P['compose_format']}"])


# ---------------------------------------------------------------- 받은 답 다듬기
def _items(raw, by, known):
    out = []
    for it in (raw or {}).get("items") or []:
        if not isinstance(it, dict) or not str(it.get("text", "")).strip(): continue
        refs = []
        for n in it.get("refs") or []:
            s = str(n).lstrip("N")
            if s.isdigit() and int(s) in known: refs.append(int(s))
        out.append({"id": f"{by.split()[-1]}-{len(out) + 1}", "by": by, "text": str(it["text"]).strip()[:400], "refs": refs})
        if len(out) >= MAX_ITEMS: break
    return out


def _votes(raw, ids):
    out = {}
    for v in (raw or {}).get("votes") or []:
        if isinstance(v, dict) and v.get("id") in ids and v.get("vote") in (AGREE, DISAGREE, HOLD):
            out[v["id"]] = {"vote": v["vote"], "why": str(v.get("why", "")).strip()[:300]}
    return out


# ---------------------------------------------------------------- 돌리기
def _batch(jobs, parallel):
    """jobs: [(이름, 함수)] → {이름: 결과 | 예외}. parallel 이면 한꺼번에 묻는다(한 차례에 걸리는 시간이 가장 느린 한 사람 몫으로 준다)."""
    def one(f):
        try: return f()
        except Exception as e: return e
    if not parallel or len(jobs) < 2: return None
    with ThreadPoolExecutor(len(jobs)) as ex: return dict(zip([k for k, _ in jobs], ex.map(one, [f for _, f in jobs])))


def run(role, run_, ask, n=3, should_stop=lambda: False, search=None, check=None, max_rounds=2, deadline=240, parallel=False):
    """승인받은 역할 하나의 의견 모으기. 사건(dict)을 차례로 낸다.
    ask(member, system, prompt, tier) -> dict | 예외.  search(낱말) -> 자료 목록(K 가 빠진 자료를 찾을 때).  check(답, 자료) -> 숫자 대조 결과."""
    assert role in ROLES
    r = ROLES[role]; n = max(2, min(5, int(n))); t0 = time.time(); calls = 0
    members = [{"id": f"{W['member']} {k + 1}", "lens": r["lenses"][k][0]} for k in range(n)]
    yield {"type": "start", "role": role, "name": r["name"], "members": members, "item": r["item"]}
    user_stop = should_stop; late = lambda: time.time() - t0 > deadline        # 정한 시간을 넘기면 다음 물음 앞에서 멈춘다
    should_stop = lambda: user_stop() or late()
    stopped = lambda: {"type": "stopped", "role": role, "why": "time" if late() and not user_stop() else "user", "seconds": round(time.time() - t0, 1), "calls": calls}
    known = {e["n"] for e in run_["evidence"]}

    # ① 각자 의견
    items, alive, words = [], [], []
    first = lambda k, m: (lambda: ask(m["id"], _system(role, r["lenses"][k]), _first(role, run_), r["tier"]))
    if parallel and not should_stop():
        for m in members: yield {"type": "thinking", "member": m["id"], "step": STEP["write"]}
    pre = _batch([(m["id"], first(k, m)) for k, m in enumerate(members)], parallel and not should_stop())
    for k, m in enumerate(members):
        if pre is None:
            if should_stop(): yield stopped(); return
            yield {"type": "thinking", "member": m["id"], "step": STEP["write"]}
        try:
            raw = first(k, m)() if pre is None else pre[m["id"]]
            if isinstance(raw, Exception): raise raw
            calls += 1
            mine = _items(raw, m["id"], known)
            if not mine: raise ValueError("empty")
        except Exception:
            yield {"type": "absent", "member": m["id"], "why": STEP["absent_first"]}; continue
        alive.append(m["id"]); items += mine
        if role == "K": words += [str(s).strip()[:40] for s in (raw.get("search") or []) if str(s).strip()][:2]
        yield {"type": "opinion", "member": m["id"], "lens": m["lens"], "items": mine}
    if pre is not None and should_stop(): yield stopped(); return
    if len(alive) < 2:
        yield {"type": "result", "role": role, "state": ST["short"], "why": ST["short_why"], "adopted": [], "split": [], "rejected": [],
               "seconds": round(time.time() - t0, 1), "calls": calls}
        return

    # K: 빠진 자료 찾기 — 담당이 낸 낱말로 실제로 찾아 후보에 더한다
    added = []
    if role == "K" and search and words:
        seen = {(e.get("title"), (e.get("text") or "")[:60]) for e in run_["evidence"]}; nn = max(known) + 1
        for w in dict.fromkeys(words):
            if should_stop(): yield stopped(); return
            for e in (search(w) or [])[:2]:
                key = (e.get("title"), (e.get("text") or "")[:60])
                if key in seen: continue
                seen.add(key); added.append({**e, "n": nn, "found_by": w}); nn += 1
        if added:
            run_ = {**run_, "evidence": run_["evidence"] + added}; known |= {e["n"] for e in added}
            items += [{"id": f"new-{e['n']}", "by": W["found_by"], "text": P["new_item"].format(word=e["found_by"], title=e.get("title", "")), "refs": [e["n"]]} for e in added]
            yield {"type": "found", "words": list(dict.fromkeys(words)),
                   "items": [{"n": e["n"], "title": e.get("title"), "tag": e.get("tag"), "text": (e.get("text") or "")[:200]} for e in added]}

    # ② · ③ 서로의 의견을 읽고 주고받기
    votes, rows, prior, rd = {}, [], [], 0
    for rd in range(1, max_rounds + 1):
        target = items if rd == 1 else [i for i in items if i["id"] in {p["id"] for p in prior}]
        step = STEP["read"] if rd == 1 else STEP["reread"]
        oth = {m: [i for i in target if i["by"] != m] for m in alive}
        kof = {x["id"]: j for j, x in enumerate(members)}
        reply = lambda m: (lambda: ask(m, _system(role, r["lenses"][kof[m]]), _exchange(role, run_, [i for i in items if i["by"] == m], oth[m], prior), r["tier"]))
        if should_stop(): yield stopped(); return
        if parallel:
            for m in alive:
                if oth[m]: yield {"type": "thinking", "member": m, "step": step}
        pre = _batch([(m, reply(m)) for m in alive if oth[m]], parallel)
        for m in alive:
            others = oth[m]
            if not others: continue
            if pre is None:
                if should_stop(): yield stopped(); return
                yield {"type": "thinking", "member": m, "step": step}
            try:
                raw = reply(m)() if pre is None else pre[m]
                if isinstance(raw, Exception): raise raw
                calls += 1
                got = _votes(raw, {i["id"] for i in others})
            except Exception:
                yield {"type": "absent", "member": m, "why": STEP["absent_round"]}; continue
            changed = [{"id": i, "from": votes[(m, i)]["vote"], "to": v["vote"]} for i, v in got.items() if (m, i) in votes and votes[(m, i)]["vote"] != v["vote"]]
            for i, v in got.items(): votes[(m, i)] = v
            yield {"type": "exchange", "round": rd, "member": m, "votes": [{"id": i, **v} for i, v in got.items()], "changed": changed}
        if pre is not None and should_stop(): yield stopped(); return
        rows = tally(items, votes, alive)
        yield {"type": "tally", "round": rd, "rows": [{k: x[k] for k in ("id", "by", "text", "refs", "agree", "disagree", "hold", "state")} for x in rows]}
        prior = [x for x in rows if x["state"] == SPLIT]
        if not prior: break

    pick = lambda s: [x for x in rows if x["state"] == s]
    adopted = pick(ADOPT)
    res = {"type": "result", "role": role, "state": outcome(rows), "adopted": adopted, "split": pick(SPLIT), "rejected": pick(REJECT), "rounds": rd, "members": alive}
    if role == "K":
        res["evidence"] = sorted({n for x in adopted for n in x["refs"]})
        res["added"] = [e["n"] for e in added if any(e["n"] in x["refs"] for x in adopted)]
    elif adopted:
        if should_stop(): yield stopped(); return
        yield {"type": "thinking", "member": W["composer"], "step": STEP["compose"]}
        try:
            raw = ask(W["composer"], W["composer_system"], _compose(role, run_, adopted), "write"); calls += 1
            ans = str(raw["answer"]).strip()
            res["answer"] = ans; res["unknown_refs"] = sorted({int(x) for x in re.findall(r"\[N(\d+)\]", ans)} - known)
            if check: res["check"] = check(ans, run_["evidence"])
        except Exception:
            res["answer_error"] = STEP["compose_fail"]
    res.update({"seconds": round(time.time() - t0, 1), "calls": calls})
    yield res
