# -*- coding: utf-8 -*-
"""역할을 서로 다른 개체가 맡은 실험(B2_roles) 채점. 실행: python -X utf8 score.py  (다시 돌리면 check1 이 끝났을 때 자동으로 들어간다)
읽는 것(읽기만):
  ../interpret · ../interpret2 · ../check2 · ../check1 의 judgments/*.json · leaked.txt · CHECK_DONE.md
  $CHAINSHIFT_DATA/agent/kic_agent/days.json  정답(번짐 = 시장 몫 뺀 전력 쪽 ÷ 칩 쪽 ≥ 0.275) — B_agent/score.py 와 같은 파일
  $CHAINSHIFT_DATA/net/backtest/returns_long.csv.gz · kic_precheck/data/chain.json  단순 규칙 · 그날 등락
  ../../A3_hedge/hedge.py 의 계산 부분(파일 쓰는 줄 앞까지만 그대로 실행) · hedge.json(맞춤 검사) · etf_long_ret.csv
  ../../A_problem/short_panel.json  공개 보유 전체의 날마다 예상 대 실제(M3)
쓰는 것: score.json · tables.md · ../SCORE.md(= HEAD.md + tables.md)"""
# closed-class: 이 파일의 한글 낱말은 실험이 정한 닫힌 값이다 — 판정 값 셋(번진다 · 안 번진다 · 넘김), 까닭 갈래 다섯, 표 머리글. 글을 거르는 낱말 목록이 아니다.
import json, re, itertools, random, statistics as S
from math import comb
from pathlib import Path

import os
H = Path(__file__).resolve().parent; B2 = H.parent; AN = B2.parent; K = Path(os.environ.get("CHAINSHIFT_DATA", "data") + "")
J = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))
DAYS = {x["d"]: x for x in J(K / "agent/kic_agent/days.json")["days"]}
YES, NOT, HAND = "번진다", "안 번진다", "넘김"  # closed-class 판정 값
TRUTH = {d: {"예": YES, "아니오": NOT}[x["spread"]] for d, x in DAYS.items()}
NV = lambda v: HAND if "넘긴" in v else v

# ── 개체별 판정 읽기 (폴더, 끝 판정 칸, 해석 판정 칸, 끝났다는 표시 파일)
SPEC = {"해석1": ("interpret", "verdict", None, "INTERPRET_DONE.md"), "해석2": ("interpret2", "verdict", None, "INTERPRET_DONE.md"),
        "점검2(해석2 를 점검)": ("check2", "final_verdict", "interp_verdict", "CHECK_DONE.md"), "점검1(해석1 을 점검)": ("check1", "final", "interp", "CHECK_DONE.md")}
# 눈가림: (나) 정답을 미리 본 날 = 아래 ANSWER. leaked.txt 의 줄 머리 날짜 가운데 ANSWER · AFTER 가 아닌 날은 모두 (다) 곁값을 본 날.
ANSWER = {"interpret": set(),
          "interpret2": {"2025-01-27", "2025-08-29", "2025-12-12", "2026-02-04", "2025-10-14", "2026-06-05", "2025-04-09"},  # 04-09 는 「칩 -5.34 · 전력 -4.51」(정답의 분자·분모)을 봐서 채점자가 정답 쪽에 넣음
          "check2": {"2025-04-09"},   # 같은 값. leaked.txt 「채점 값과 같은 급」
          "check1": {"2025-01-27"}}   # 「기억으로 앎」
AFTER = {"check1": {"2026-07-01", "2026-07-02", "2026-07-15"}}  # 제 판정을 써 둔 뒤에 보인 날(order_log.txt) — 빼지 않음
ENT, LEAK, PENDING = {}, {}, []
for name, (folder, fk, ik, done) in SPEC.items():
    if not (B2 / folder / done).exists():
        PENDING.append(f"{name}: {folder}/{done} 가 없어 이번 채점에 안 듦(판정 파일 {len(list((B2 / folder / 'judgments').glob('*.json')))}개까지 써진 상태)"); continue
    ENT[name] = {}
    for f in sorted((B2 / folder / "judgments").glob("*.json")):
        j = J(f); ENT[name][j["date"]] = {"v": NV(j[fk]), "c": j.get("cause"), "iv": NV(j[ik]) if ik else None, "ic": j.get("interp_cause")}
    lead = set(re.findall(r"^(\d{4}-\d\d-\d\d)", (B2 / folder / "leaked.txt").read_text(encoding="utf-8"), re.M))
    assert ANSWER[folder] <= lead, (folder, ANSWER[folder] - lead)
    LEAK[name] = {"answer": sorted(ANSWER[folder]), "side": sorted(lead - ANSWER[folder] - AFTER.get(folder, set()))}
assert all(set(e) <= set(TRUTH) for e in ENT.values())

# ── 그날 값: A3 헤지 계산을 그대로 실행(파일 쓰는 부분 앞까지) — 전력 쪽 19종목 · 칩 밖 49종목
A3 = AN / "A3_hedge"; g = {"__file__": str(A3 / "hedge.py"), "__name__": "hedge_part"}
exec(compile((A3 / "hedge.py").read_text(encoding="utf-8").split("\nout = {")[0], "hedge_part", "exec"), g)
IDX = g["IDX"]; POS = {str(d.date()): i for i, d in enumerate(IDX)}; M46 = g["SHOCK"] & g["SHORT"]
act19, res19, pick19, _, _ = g["run"](g["POWERS"]); act49, res49, _, _, _ = g["run"](g["T"])
HJ = J(A3 / "hedge.json")["scopes"]["전력 쪽 19종목 합"]["by"]["shock46"]
for k in ("OWN", "SMH", "RULE"):  # 74% · 11% · 30% 가 다시 나오는지
    assert abs(res19[k][M46].sum() / act19[M46].sum() * 100 - HJ[k]["left_pct_of_sum"]) < 0.06, k
R = g["R"]; SV = g["SCOPES"]["서버·네트워크·부품"]
SP = {r["date"]: r for r in J(AN / "A_problem/short_panel.json")["W250"]["external"]["chip"]["M3"]["전체 공개 보유(638종목 중 값 있는 종목)"]["per_day"]}
DAY = {}
for d in TRUTH:
    i = POS[d]; r = R.iloc[i] * 100
    DAY[d] = {"truth": TRUTH[d], "ratio": DAYS[d]["ratio"], "power_ex_mkt_pct": DAYS[d]["power"], "chip_ex_mkt_pct": DAYS[d]["chip"],
              "power_raw_pct": round(float(r[g["POWERS"]].mean()), 2), "spy_pct": round(float(r["SPY"]), 2),
              "server_vs_mkt_pp": round(float(r[[t for t in SV if t in r.index]].dropna().mean() - r["SPY"]), 2),
              "act19_e8": round(act19[i] / 1e8, 3), "gap49_mkt_e8": round(res49["SPY"][i] / 1e8, 3), "gap49_own_e8": round(res49["OWN"][i] / 1e8, 3),
              "gap638_m3_e8": round(SP[d]["actual_e8"] - SP[d]["pred_e8"], 2) if d in SP else None, "in46": bool(M46[i]),
              "left_own_e8": res19["OWN"][i] / 1e8, "left_smh_e8": res19["SMH"][i] / 1e8, "left_rule_e8": res19["RULE"][i] / 1e8}
    DAY[d]["server_rule"] = YES if DAY[d]["server_vs_mkt_pp"] < -1.0 else NOT
ALL = sorted(TRUTH)


def tally(days, get):
    v = {d: get(d) for d in days}; c = [d for d in days if v[d] != HAND]; ok = [d for d in c if v[d] == TRUTH[d]]
    return {"days": len(days), "confirmed": len(c), "right": len(ok), "wrong": len(c) - len(ok), "handed": len(days) - len(c), "wrong_days": [d for d in c if d not in ok]}


def dayset(name, crit):
    lk = LEAK[name]; out_of = set() if crit == "가" else set(lk["answer"]) if crit == "나" else set(lk["answer"]) | set(lk["side"])
    return [d for d in sorted(ENT[name]) if d not in out_of]


CRIT = {"가": "전부", "나": "정답을 미리 본 날을 뺌", "다": "곁값을 본 날까지 뺌"}
out = {"pending": PENDING, "truth": {"file": (K / "agent/kic_agent/days.json").as_posix(), "threshold": 0.275, "spread_yes": sum(v == YES for v in TRUTH.values()), "n": len(TRUTH)},
       "leak": LEAK, "s1": {}, "day": DAY}
# 1 ── 개체별 × 눈가림 기준 셋
for name in ENT:
    out["s1"][name] = {}
    for c in CRIT:
        ds = dayset(name, c)
        out["s1"][name][c] = {"개체": tally(ds, lambda d: ENT[name][d]["v"]), "늘 번진다": tally(ds, lambda d: YES), "서버·부품 규칙": tally(ds, lambda d: DAY[d]["server_rule"])}
        if ENT[name][ds[0]]["iv"] is not None:
            out["s1"][name][c]["점검 전 해석 판정"] = tally(ds, lambda d: ENT[name][d]["iv"])
NO = [d for d in ALL if TRUTH[d] == NOT]
how = lambda v: "판정 없음" if v is None else HAND if v == HAND else "맞힘" if v == NOT else "같이 틀림"
out["non_spread"] = [{"date": d, "ratio": DAY[d]["ratio"], "서버·부품 규칙": how(DAY[d]["server_rule"]),
                      **{n: how(ENT[n].get(d, {}).get("v")) + ("*" if d in LEAK[n]["answer"] else "+" if d in LEAK[n]["side"] else "") for n in ENT}} for d in NO]


# 2 ── 두 해석 개체의 일치
def kappa(a, b):
    n = len(a); cats = sorted(set(a) | set(b)); po = sum(x == y for x, y in zip(a, b)) / n
    pe = sum((a.count(c) / n) * (b.count(c) / n) for c in cats)
    return round((po - pe) / (1 - pe), 3) if pe < 1 else None


assert kappa(list("aabb"), list("aabb")) == 1.0 and kappa(list("aabb"), list("abab")) == 0.0
if "해석1" in ENT and "해석2" in ENT:
    A, B = ENT["해석1"], ENT["해석2"]; out["s2"] = {}
    for c in CRIT:
        ds = [d for d in dayset("해석1", c) if d in dayset("해석2", c)]
        va, vb = [A[d]["v"] for d in ds], [B[d]["v"] for d in ds]
        both = [d for d in ds if A[d]["v"] != HAND and B[d]["v"] != HAND]
        out["s2"][c] = {"days": len(ds), "same_verdict": sum(x == y for x, y in zip(va, vb)), "same_pct": round(sum(x == y for x, y in zip(va, vb)) / len(ds) * 100, 1),
                        "kappa_verdict": kappa(va, vb), "same_cause": sum(A[d]["c"] == B[d]["c"] for d in ds), "kappa_cause": kappa([A[d]["c"] for d in ds], [B[d]["c"] for d in ds]),
                        "both_confirmed": len(both), "both_confirmed_same": sum(A[d]["v"] == B[d]["v"] for d in both),
                        "both_confirmed_same_right": sum(A[d]["v"] == B[d]["v"] == TRUTH[d] for d in both),
                        "split": [{"date": d, "해석1": A[d]["v"], "해석1 까닭": A[d]["c"], "해석2": B[d]["v"], "해석2 까닭": B[d]["c"], "정답": TRUTH[d]} for d in ds if A[d]["v"] != B[d]["v"]],
                        "cause_split": [{"date": d, "해석1": A[d]["c"], "해석2": B[d]["c"]} for d in ds if A[d]["c"] != B[d]["c"]]}
    # 둘이 같은 확정을 냈을 때만 확정하는 규칙(갈리면 넘김)
    out["s2"]["agree_rule"] = {c: tally([d for d in dayset("해석1", c) if d in dayset("해석2", c)], lambda d: A[d]["v"] if A[d]["v"] == B[d]["v"] else HAND) for c in CRIT}

# 3 ── 점검이 한 일
GOOD = ("틀린 확정을 넘김으로 막음", "틀린 확정을 맞는 확정으로", "넘김을 맞는 확정으로"); BAD = ("넘김을 틀린 확정으로", "맞는 확정을 틀린 확정으로"); LOST = "맞았을 확정을 넘김으로 물림"
out["s3"] = {}
for name, e in ENT.items():
    if next(iter(e.values()))["iv"] is None: continue
    ch = []
    for d in sorted(e):
        a, b, t = e[d]["iv"], e[d]["v"], TRUTH[d]
        if a == b: continue
        eff = (GOOD[0] if a not in (HAND, t) and b == HAND else GOOD[1] if a not in (HAND, t) and b == t else
               GOOD[2] if a == HAND and b == t else BAD[0] if a == HAND else LOST if a == t and b == HAND else BAD[1])
        ch.append({"date": d, "해석": a, "끝": b, "정답": t, "effect": eff, "leak": "정답" if d in LEAK[name]["answer"] else "곁값" if d in LEAK[name]["side"] else ""})
    out["s3"][name] = {"days": len(e), "changed": len(ch), "good": sum(x["effect"] in GOOD for x in ch), "bad": sum(x["effect"] in BAD for x in ch),
                       "lost": sum(x["effect"] == LOST for x in ch), "cause_changed": [d for d in sorted(e) if e[d]["ic"] != e[d]["c"]], "rows": ch}


# 4 ── 가르는 힘(연속 값)
def perm(x, y):
    """평균(x) − 평균(y) 와, x 가 더 낮다는 한쪽 순열 p. 조합 수 20만 이하면 전부, 넘으면 2만 번(seed 0)."""
    if not x or not y: return None
    obs = S.mean(x) - S.mean(y); z = x + y; n, k = len(z), len(x); tot = sum(z)
    if comb(n, k) <= 200000: it = itertools.combinations(range(n), k); exact = True
    else:
        rnd = random.Random(0); it = (rnd.sample(range(n), k) for _ in range(20000)); exact = False
    le = m = 0
    for idx in it:
        sx = sum(z[i] for i in idx); m += 1; le += (sx / k - (tot - sx) / (n - k)) <= obs + 1e-12
    return {"diff": round(obs, 3), "n_x": k, "n_y": n - k, "p_one_sided_x_lower": round(le / m, 4), "exact": exact, "perms": m}


assert perm([-3.0, -2.0], [1.0, 2.0])["p_one_sided_x_lower"] == round(1 / 6, 4)
VALS = ("power_ex_mkt_pct", "power_raw_pct", "act19_e8", "gap49_mkt_e8", "gap49_own_e8", "gap638_m3_e8")


def grp(ds):
    o = {"n": len(ds), "truth_spread": sum(TRUTH[d] == YES for d in ds)}
    for v in VALS:
        x = [DAY[d][v] for d in ds if DAY[d][v] is not None]
        o[v] = {"mean": round(S.mean(x), 3), "median": round(S.median(x), 3), "n": len(x)} if x else None
    return o


CMP = (("power_ex_mkt_pct", "전력(시장 몫 뺌) %p"), ("power_raw_pct", "전력(그대로) %p"), ("gap49_mkt_e8", "칩 밖 − 시장 모형 억 달러"))
AI, CHIP = "AI 투자 전반", "칩 고유"  # closed-class 까닭 갈래
out["s4"] = {}
for name, e in ENT.items():
    out["s4"][name] = {}
    for c in CRIT:
        ds = dayset(name, c); o = {"by_cause": {}, "by_verdict": {}}
        for k in sorted({e[d]["c"] for d in ds}): o["by_cause"][k] = grp([d for d in ds if e[d]["c"] == k])
        for k in (YES, NOT, HAND): o["by_verdict"][k] = grp([d for d in ds if e[d]["v"] == k])
        ai, chip = [d for d in ds if e[d]["c"] == AI], [d for d in ds if e[d]["c"] == CHIP]
        o["ai_vs_chip"] = {v: perm([DAY[d][v] for d in ai], [DAY[d][v] for d in chip]) for v, _ in CMP}
        yes, rest = [d for d in ds if e[d]["v"] == YES], [d for d in ds if e[d]["v"] != YES]
        o["yes_vs_rest"] = {v: perm([DAY[d][v] for d in yes], [DAY[d][v] for d in rest]) for v, _ in CMP}
        # 헤지 수단 고르기 — 46일 정의에 드는 날만
        hd = [d for d in ds if DAY[d]["in46"]]; a = sum(DAY[d]["act19_e8"] for d in hd); aa = sum(abs(DAY[d]["act19_e8"]) for d in hd)

        def left(x, n_smh):
            return {"left_pct_of_sum": round(sum(x) / a * 100, 1) if a < 0 else None, "abs_left_pct": round(sum(map(abs, x)) / aa * 100, 1), "smh_days": n_smh, "still_loss_days": sum(v < 0 for v in x)}

        def by(pick):
            return left([DAY[d]["left_smh_e8"] if pick(d) else DAY[d]["left_own_e8"] for d in hd], sum(bool(pick(d)) for d in hd))

        o["hedge"] = {"days": len(hd), "act_sum_e8": round(a, 2), "dates": hd,
                      "늘 자기 업종 펀드": by(lambda d: False), "늘 반도체 펀드": by(lambda d: True),
                      "지난 주가로 고르는 규칙": left([DAY[d]["left_rule_e8"] for d in hd], sum(pick19[POS[d]] == "SMH" for d in hd)),
                      "개체가 「번진다」로 읽은 날만 반도체": by(lambda d: e[d]["v"] == YES),
                      "개체가 「AI 투자 전반」으로 읽은 날만 반도체": by(lambda d: e[d]["c"] == AI),
                      "「번진다」 또는 「AI 투자 전반」인 날만 반도체": by(lambda d: e[d]["v"] == YES or e[d]["c"] == AI),
                      "(견줌) 정답이 번짐인 날만 반도체": by(lambda d: TRUTH[d] == YES)} if hd else None
        out["s4"][name][c] = o
(H / "score.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")

# ── 표
L = []; P = L.append
P("## 0. 채점에 든 개체와 눈가림")
for n in ENT: P(f"- {n}: 판정 {len(ENT[n])}일 · (나) 정답을 미리 본 날 {len(LEAK[n]['answer'])}일 {LEAK[n]['answer']} · (다) 곁값을 본 날 {len(LEAK[n]['side'])}일 {LEAK[n]['side']}")
for s in PENDING: P(f"- 아직 안 든 개체 — {s}")
P(f"- 정답: 25일 중 번진 날 {out['truth']['spread_yes']}일 · 안 번진 날 {len(NO)}일 {NO}")
P("\n## 1. 개체별 확정 · 맞음 · 틀림 · 넘김 (같은 날 집합의 단순 규칙 둘과 나란히)")
P("| 개체 | 눈가림 기준 | 날 | 확정 | 맞은 확정 | 틀린 확정 | 넘김 | 틀린 날 | 늘 번진다(맞음/틀림) | 서버·부품 규칙(맞음/틀림) |"); P("|---|---|---|---|---|---|---|---|---|---|")
for n in ENT:
    for c in CRIT:
        for who in [k for k in out["s1"][n][c] if k in ("점검 전 해석 판정", "개체")][::-1]:
            t = out["s1"][n][c][who]; a, s = out["s1"][n][c]["늘 번진다"], out["s1"][n][c]["서버·부품 규칙"]
            P(f"| {n if who == '개체' else n + ' — 점검 전'} | ({c}) {CRIT[c]} | {t['days']} | {t['confirmed']} | {t['right']} | {t['wrong']} | {t['handed']} | {' '.join(t['wrong_days'])} | {a['right']}/{a['wrong']} | {s['right']}/{s['wrong']} |")
P("\n### 「늘 번진다」가 틀린 날(정답 = 안 번진다)에 개체들이 한 일  (* 정답을 미리 본 날 · + 곁값을 본 날)")
P("| 날 | 전력÷칩 | " + " | ".join(ENT) + " | 서버·부품 규칙 |"); P("|---|---|" + "---|" * (len(ENT) + 1))
for r in out["non_spread"]: P(f"| {r['date']} | {r['ratio']} | " + " | ".join(r[n] for n in ENT) + f" | {r['서버·부품 규칙']} |")
if "s2" in out:
    P("\n## 2. 두 해석 개체(해석1 · 해석2)의 일치"); P("| 눈가림 기준 | 공통 날 | 판정 같은 날 | 비율 | 카파(판정) | 까닭 갈래 같은 날 | 카파(까닭) | 둘 다 확정 | 그중 같은 확정 | 그중 맞음 |"); P("|---|---|---|---|---|---|---|---|---|---|")
    for c in CRIT:
        x = out["s2"][c]; P(f"| ({c}) {CRIT[c]} | {x['days']} | {x['same_verdict']} | {x['same_pct']}% | {x['kappa_verdict']} | {x['same_cause']} | {x['kappa_cause']} | {x['both_confirmed']} | {x['both_confirmed_same']} | {x['both_confirmed_same_right']} |")
    P("\n갈린 날(25일 전부 기준)"); P("| 날 | 해석1 (까닭) | 해석2 (까닭) | 정답 |"); P("|---|---|---|---|")
    for r in out["s2"]["가"]["split"]: P(f"| {r['date']} | {r['해석1']} ({r['해석1 까닭']}) | {r['해석2']} ({r['해석2 까닭']}) | {r['정답']} |")
    P("\n둘이 같은 확정을 냈을 때만 확정하고 갈리면 넘기는 규칙"); P("| 눈가림 기준 | 날 | 확정 | 맞음 | 틀림 | 넘김 | 틀린 날 |"); P("|---|---|---|---|---|---|---|")
    for c in CRIT:
        t = out["s2"]["agree_rule"][c]; P(f"| ({c}) | {t['days']} | {t['confirmed']} | {t['right']} | {t['wrong']} | {t['handed']} | {' '.join(t['wrong_days'])} |")
P("\n## 3. 점검이 한 일 (해석 판정 → 끝 판정)")
for n, x in out["s3"].items():
    P(f"- {n}: {x['days']}일 중 판정을 바꾼 날 {x['changed']}일 — 맞는 쪽 {x['good']} · 틀린 쪽 {x['bad']} · 맞았을 확정을 넘김으로 물린 날 {x['lost']}. 까닭 갈래를 바꾼 날 {len(x['cause_changed'])}일 {x['cause_changed']}")
    for r in x["rows"]: P(f"  - {r['date']}: {r['해석']} → {r['끝']} (정답 {r['정답']}) — {r['effect']}{' · 눈가림 ' + r['leak'] if r['leak'] else ''}")
P("\n## 4. 가르는 힘 — 까닭 갈래별 · 판정별 그날 실제 값 (눈가림 기준 (가) 전부. (나)(다)는 score.json)")
P("값: 전력(시장 몫 뺌) = days.json power %, 전력(그대로) = 19종목 등락 평균 %, 전력 손익 = 19종목 보유 금액 손익(억 달러), 칩 밖 − 시장 모형 = 칩 밖 49종목 실제 손익 − 시장(SPY) 한 요인 예상(억 달러), 전체 − 업종 모형 = 공개 보유 전체 실제 − short_panel M3 예상(억 달러, 46일에 드는 날만)")
f = lambda x: "–" if x is None else f"{x['mean']} / {x['median']} (n={x['n']})"
for n in ENT:
    o = out["s4"][n]["가"]; P(f"\n### {n}"); P("| 묶음 | 날 | 실제 번진 날 | 전력(시장 몫 뺌) 평균/중간 | 전력(그대로) | 전력 손익 | 칩 밖 − 시장 모형 | 전체 − 업종 모형 |"); P("|---|---|---|---|---|---|---|---|")
    for kind in ("by_cause", "by_verdict"):
        for k, x in o[kind].items():
            if x["n"]: P(f"| {'까닭' if kind == 'by_cause' else '판정'}: {k} | {x['n']} | {x['truth_spread']} | {f(x['power_ex_mkt_pct'])} | {f(x['power_raw_pct'])} | {f(x['act19_e8'])} | {f(x['gap49_mkt_e8'])} | {f(x['gap638_m3_e8'])} |")
    for c in CRIT:
        for lab, key in (("「AI 투자 전반」 − 「칩 고유」", "ai_vs_chip"), ("「번진다」 − 나머지", "yes_vs_rest")):
            x = out["s4"][n][c][key]
            P(f"- ({c}) {lab}: " + " · ".join(f"{nm} 차이 {x[v]['diff']} ({x[v]['n_x']}일 대 {x[v]['n_y']}일, 한쪽 순열 p={x[v]['p_one_sided_x_lower']})" if x[v] else f"{nm} 비교할 날 없음" for v, nm in CMP))
P("\n### 헤지 수단 고르기 — 전력 쪽 19종목, 개체의 날 가운데 46일 정의에 드는 날만 (남는 손실 몫 = 헤지 뒤 손익 합 ÷ 실제 손익 합 / 크기 기준 = 날마다 남는 크기 합 ÷ 손익 크기 합)")
P(f"46일 전체에서 다시 낸 값(hedge.json 과 맞춤 검사 통과): 늘 자기 업종 펀드 {HJ['OWN']['left_pct_of_sum']}% · 늘 반도체 펀드 {HJ['SMH']['left_pct_of_sum']}% · 지난 주가로 고르는 규칙 {HJ['RULE']['left_pct_of_sum']}%")
P("| 개체 | 눈가림 | 날 | 실제 손익 합(억 달러) | 고르는 법 | 반도체 펀드를 쓴 날 | 남는 손실 몫 | 크기 기준 | 헤지 뒤에도 손실인 날 |"); P("|---|---|---|---|---|---|---|---|---|")
for n in ENT:
    for c in CRIT:
        h = out["s4"][n][c]["hedge"]
        if not h: continue
        for k, x in h.items():
            if isinstance(x, dict): P(f"| {n} | ({c}) | {h['days']} | {h['act_sum_e8']} | {k} | {x['smh_days']} | {x['left_pct_of_sum']}% | {x['abs_left_pct']}% | {x['still_loss_days']} |")
(H / "tables.md").write_text("\n".join(L), encoding="utf-8")
head = (H / "HEAD.md").read_text(encoding="utf-8") if (H / "HEAD.md").exists() else "# B2_roles 채점 (HEAD.md 아직 없음)\n"
(B2 / "SCORE.md").write_text(head + "\n\n---\n\n# 표 전부 (score.py 가 낸 그대로 — score/tables.md · score/score.json)\n\n" + "\n".join(L), encoding="utf-8")
print("\n".join(L))
