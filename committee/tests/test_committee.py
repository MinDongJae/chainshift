# -*- coding: utf-8 -*-
"""의견 모으기 로직 시험 — 모델을 부르지 않는다(정해 둔 답). 실행: python -X utf8 tests/test_committee.py  (pytest 로도 돈다)"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import committee as cm, committee_api as api

REC = json.loads((Path(__file__).parent / "rec.json").read_text(encoding="utf-8"))   # 공개 화면의 「받아 둔 실제 답」 기록 그대로
EV = next(e for e in REC if e["type"] == "evidence")["items"]
RUN = {"question": REC[0]["text"], "answer": next(e for e in REC if e["type"] == "done")["answer"], "evidence": EV,
       "issues": [i["label"] for i in next(e for e in REC if e["type"] == "review")["issues"]], "verify": {"bad": 0}}
A, D, H = cm.AGREE, cm.DISAGREE, cm.HOLD
go = lambda role, mode, **kw: list(cm.run(role, RUN, api.fake_ask(mode), **kw))
last = lambda evs: evs[-1]
types = lambda evs: [e["type"] for e in evs]


def test_offers_from_real_record():
    o = cm.offers(RUN); assert [x["role"] for x in o] == ["K", "I", "C"], o
    assert all(x["ask"].endswith("볼까요?") and x["n"] == 3 for x in o)
    assert "18건" in o[0]["why"] and "6건" in o[0]["why"]          # 찾은 자료 18건 가운데 답에 쓰인 6건
    assert "5곳" in o[2]["why"]                                    # 처음 답에서 고칠 곳 5곳


def test_no_offer_when_not_needed():
    ev = [{"n": k, "text": "t", "title": "t"} for k in range(1, 7)]
    r = {"question": "보유 종목 수는", "answer": " ".join(f"문장 [N{k}]." for k in range(1, 7)), "evidence": ev, "issues": [], "verify": {"bad": 0}}
    assert cm.offers(r) == []
    assert cm.offers({"question": "q", "answer": "", "evidence": []}) == []


def test_tally_rules():
    it = [{"id": "1-1", "by": "담당 1", "text": "x", "refs": []}]; M = ["담당 1", "담당 2", "담당 3"]
    st = lambda v: cm.tally(it, v, M)[0]["state"]
    assert st({("담당 2", "1-1"): {"vote": A}, ("담당 3", "1-1"): {"vote": D}}) == cm.ADOPT        # 동의 2(낸 사람 포함) 반대 1
    assert st({("담당 2", "1-1"): {"vote": D}, ("담당 3", "1-1"): {"vote": D}}) == cm.REJECT       # 반대 2
    assert st({("담당 2", "1-1"): {"vote": H}, ("담당 3", "1-1"): {"vote": D}}) == cm.SPLIT        # 동의 1 반대 1 보류 1
    assert st({}) == cm.SPLIT                                                                       # 아무도 답하지 않으면 보류로 센다
    two = ["담당 1", "담당 2"]
    assert cm.tally(it, {("담당 2", "1-1"): {"vote": A}}, two)[0]["state"] == cm.ADOPT
    assert cm.tally(it, {("담당 2", "1-1"): {"vote": D}}, two)[0]["state"] == cm.SPLIT             # 1 대 1 은 갈림


def test_consensus_all_roles():
    for role in "KIC":
        evs = go(role, "agree"); r = last(evs)
        assert types(evs)[0] == "start" and r["type"] == "result" and r["state"] == cm.ST["all"], (role, r["state"])
        assert len([e for e in evs if e["type"] == "opinion"]) == 3 and len([e for e in evs if e["type"] == "exchange"]) == 3
        assert r["rounds"] == 1 and not r["split"] and len(r["adopted"]) == 6
        if role == "K": assert r["evidence"] and "answer" not in r
        else: assert r["answer"] and r["unknown_refs"] == []


def test_exchange_really_shows_others_opinions():
    log = []; list(cm.run("I", RUN, api.fake_ask("agree", log=log)))
    second = [x["prompt"] for x in log if '"votes"' in x["prompt"].splitlines()[-1]]
    assert len(second) == 3
    assert "담당 2가 낸 의견 1" in second[0] and "담당 3가 낸 의견 2" in second[0]     # 담당 1 이 받는 글에 다른 두 담당의 의견이 들어 있다
    assert "(담당 1)" not in second[0].split(cm.P["others"].format(item="주장"))[1]     # 자기 의견은 남의 의견 자리에 없다


def test_minds_change_in_second_round():
    evs = go("I", "turn"); r = last(evs)
    assert max(e["round"] for e in evs if e["type"] == "tally") == 2
    t1 = next(e for e in evs if e["type"] == "tally" and e["round"] == 1)
    assert any(x["state"] == cm.SPLIT for x in t1["rows"])                                       # 첫 차례에는 갈린 의견이 있다
    changed = [c for e in evs if e["type"] == "exchange" and e["round"] == 2 for c in e["changed"]]
    assert any(c["from"] == D and c["to"] == A for c in changed)                                 # 둘째 차례에 반대 → 동의로 바꾼 기록
    assert r["state"] == cm.ST["all"] and not r["split"]                                         # 그 뒤에는 뜻이 모인다


def test_disagreement_stays_split():
    r = last(go("C", "split"))
    assert r["type"] == "result" and r["split"] and r["rounds"] == 2
    assert r["state"] in (cm.ST["some"], cm.ST["none"])
    assert all(len(x["said"]) == 2 for x in r["split"])                                          # 갈린 의견마다 다른 두 담당의 말이 붙는다


def test_all_reject_no_answer():
    r = last(go("I", "reject"))
    assert r["state"] == cm.ST["none"] and not r["adopted"] and "answer" not in r


def test_one_member_absent_continues():
    evs = go("I", "absent2"); r = last(evs)
    assert [e["member"] for e in evs if e["type"] == "absent"] == ["담당 2"]
    assert r["members"] == ["담당 1", "담당 3"] and r["state"] == cm.ST["all"]


def test_nobody_answers():
    r = last(go("K", "silent")); assert r["state"] == cm.ST["short"] and r["calls"] == 0


def test_stop_between_calls():
    for limit in (0, 2, 4):
        n = {"k": 0}
        def ask(*a, _f=api.fake_ask("agree")):
            n["k"] += 1; return _f(*a)
        evs = list(cm.run("I", RUN, ask, should_stop=lambda: n["k"] >= limit))
        assert last(evs)["type"] == "stopped" and n["k"] == limit, (limit, n, types(evs)[-3:])   # 멈추라고 한 뒤에는 한 번도 더 묻지 않는다


def test_member_count():
    for n, want in ((1, 2), (2, 2), (4, 4), (9, 5)):
        assert len(next(iter(cm.run("C", RUN, api.fake_ask("agree"), n=n)))["members"]) == want


def test_k_finds_new_material():
    new = [{"title": "새 자료", "tag": "언론 보도", "text": "새로 찾은 글"}]
    evs = list(cm.run("K", RUN, api.fake_ask("agree"), search=lambda w: new)); r = last(evs)
    f = next(e for e in evs if e["type"] == "found"); assert f["items"][0]["n"] == 19 and f["words"] == ["텍사스 데이터센터"]
    assert 19 in r["evidence"] and r["added"] == [19]


def test_bad_refs_dropped_and_api_guards():
    ask = lambda *a: {"items": [{"text": "주장", "refs": [999, "N3", "x"]}], "votes": []}
    evs = list(cm.run("I", RUN, ask)); op = next(e for e in evs if e["type"] == "opinion")
    assert op["items"][0]["refs"] == [3]                                                         # 자료에 없는 번호는 버린다
    pack = api.Pack()
    assert api.offers({"run": {}}, pack)["offers"] == []
    assert list(api.stream({"role": "X", "run": RUN}, pack, api.fake_ask()))[0]["type"] == "error"
    logged = []
    assert api.decision({"role": "I", "decision": "decline", "run": RUN}, logged.append)["ok"] and logged[0]["decision"] == "decline"
    assert not api.decision({"role": "I", "decision": "whatever"}, logged.append)["ok"]


def test_client_evidence_is_checked_against_pack():
    pack = api.Pack()
    if not pack.texts: return
    forged = EV + [{"n": 99, "title": "지어낸 자료", "tag": "언론 보도", "text": "근거 묶음에 없는 글입니다. 마이크론은 -99% 빠졌습니다."}]
    ok, dropped = pack.clean(forged); assert dropped == 1 and 99 not in {e["n"] for e in ok} and len(ok) == len(EV)
    evs = list(api.stream({"role": "C", "run": {**RUN, "evidence": forged}}, pack, api.fake_ask()))
    assert evs[0] == {"type": "dropped", "count": 1} and evs[-1]["type"] == "result"


def test_deadline_stops_with_reason():
    import time as _t
    slow = lambda *a, _f=api.fake_ask("agree"): (_t.sleep(0.25), _f(*a))[1]
    evs = list(cm.run("I", RUN, slow, deadline=0.6)); e = last(evs)
    assert e["type"] == "stopped" and e["why"] == "time" and 2 <= e["calls"] <= 4, e
    e2 = last(list(cm.run("I", RUN, api.fake_ask("agree"), should_stop=lambda: True)))
    assert e2["type"] == "stopped" and e2["why"] == "user"


def test_parallel_same_result_and_faster():
    import time as _t
    slow = lambda mode: (lambda *a, _f=api.fake_ask(mode): (_t.sleep(0.2), _f(*a))[1])
    key = lambda evs: [(e["type"], e.get("member"), e.get("state")) for e in evs if e["type"] in ("opinion", "exchange", "result")]
    for mode in ("agree", "turn", "split", "absent2"):
        t0 = _t.time(); a = list(cm.run("I", RUN, slow(mode))); ta = _t.time() - t0
        t0 = _t.time(); b = list(cm.run("I", RUN, slow(mode), parallel=True)); tb = _t.time() - t0
        assert key(a) == key(b), mode                                                           # 차례대로 물을 때와 결과 · 순서가 같다
        assert last(a)["calls"] == last(b)["calls"] and tb < ta * 0.75, (mode, round(ta, 2), round(tb, 2))
    n = {"k": 0}
    def ask(*a, _f=api.fake_ask("agree")):
        n["k"] += 1; return _f(*a)
    evs = list(cm.run("I", RUN, ask, parallel=True, should_stop=lambda: n["k"] >= 3))
    assert last(evs)["type"] == "stopped" and n["k"] == 3                                        # 동시에 물어도 멈춘 뒤에는 다음 차례를 시작하지 않는다
    assert last(evs)["calls"] == 3 and len([e for e in evs if e["type"] == "opinion"]) == 3      # 이미 받은 의견 셋은 남기고, 물은 횟수도 실제와 같다


if __name__ == "__main__":
    fs = [f for n, f in sorted(globals().items()) if n.startswith("test_")]; bad = 0
    for f in fs:
        try: f(); print("통과", f.__name__)
        except Exception as e: bad += 1; print("실패", f.__name__, "—", type(e).__name__, str(e)[:300])
    print(f"{len(fs) - bad}/{len(fs)} 통과"); sys.exit(1 if bad else 0)
