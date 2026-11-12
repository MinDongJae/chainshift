# -*- coding: utf-8 -*-
"""실험 2 채점 — judgments/*.json(판정) × days.json(정답 1) × returns_long.csv.gz(정답 2) × records.json(예전 규칙).
출력: exp2_result.json · exp2_table.md   실행: python -X utf8 score.py"""
import json
from pathlib import Path
import pandas as pd
import os
H = Path(__file__).parent; K = Path(os.environ.get("CHAINSHIFT_DATA", "data") + ""); A = K / "agent/kic_agent"
J = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))
DAYS = J(A / "days.json")["days"]; REC = {r["id"]: r for r in J(A / "records.json")["records"]}
CH = J(K / "mcp_kic_precheck/kic_precheck/data/chain.json"); ST = {s["name"]: s["tick"] for s in CH["stages"]}
POW = [t for n in CH["power_stages"] for t in ST[n]]
P = (1 + pd.read_csv(K / "net/backtest/returns_long.csv.gz", index_col=0, parse_dates=True, float_precision="round_trip")).cumprod().mul(100); R = P.pct_change(fill_method=None) * 100
LEAK = {"2025-01-27": "정답을 미리 봄", "2025-04-09": "정답을 미리 봄", "2026-07-02": "전날 판정 2 정답에서 봄"}
FLAG = {"2026-06-05": "전력 쪽 재현 손실 금액을 미리 봄", "2026-10-22": "전력 쪽 재현 손실 금액·58종목 등락을 미리 봄",
        "2026-08-18": "58종목 전체 등락을 미리 봄", "2026-09-14": "58종목 전체 등락을 미리 봄", "2026-10-08": "58종목 전체 등락을 미리 봄"}
LEAN = {"2026-02-04": "안 번진다", "2026-06-16": "번진다", "2026-07-07": "안 번진다", "2026-07-15": "번진다",
        "2026-07-28": "번진다", "2026-08-05": "안 번진다", "2026-10-30": "안 번진다"}  # 끝 판정 글의 「기운 쪽」을 옮김
ORIG = {"2026-03-03": "넘김", "2026-03-30": "넘김", "2026-05-18": "넘김"}  # 끝 판정 글의 「원래 조건으로는」
Y = {"예": "번진다", "아니오": "안 번진다"}
rows = []
for x in DAYS:
    d = x["d"]; g = lambda s: J(H / "judgments" / f"{d}_{s}.json")
    a, b, s2 = g("s1a"), g("s1b"), g("s2"); truth = Y[x["spread"]]
    i = P.index.get_loc(pd.Timestamp(d)); r = R.iloc[i]; n = R.iloc[i + 1]
    mid = lambda nm: r[[t for t in ST[nm] if t in r.index]].dropna().mean() - r["SPY"]
    m_eq, m_sv = mid("반도체 장비·소재"), mid("서버·네트워크·부품")
    t2 = "이어진다" if n[[t for t in POW if t in n.index]].mean() - n["SPY"] < 0 else "안 이어진다"
    old = REC[d]["잣대"]["번짐"]
    rows.append({"date": d, "truth1": truth, "ratio": x["ratio"], "first": a["verdict"], "final": b["verdict"], "changed": a["verdict"] != b["verdict"],
                 "final_orig_rule": ORIG.get(d, b["verdict"]), "lean": LEAN.get(d), "leak": LEAK.get(d), "flag": FLAG.get(d),
                 "old_rule": "넘김" if old["정한 법"] == "사람에게" else Y.get(old["최종"], str(old["최종"])), "old_votes": old["표"],
                 "mid_rule": "번진다" if (m_eq + m_sv) / 2 < 0 else "안 번진다", "mid_eq": round(m_eq, 2), "mid_sv": round(m_sv, 2),
                 "s2": s2["verdict"], "truth2": t2, "spy": round(r["SPY"], 2), "chips_down": int((r[ST["칩"]] < 0).sum())})


def tally(rs, key):
    c = [r for r in rs if r[key] != "넘김"]; ok = sum(r[key] == r["truth1"] for r in c)
    return {"days": len(rs), "handed": len(rs) - len(c), "confirmed": len(c), "right": ok, "wrong": len(c) - ok,
            "wrong_days": [r["date"] for r in c if r[key] != r["truth1"]]}


clean = [r for r in rows if not r["leak"]]; strict = [r for r in clean if not r["flag"]]
out = {"n": len(rows), "truth_spread_yes": sum(r["truth1"] == "번진다" for r in rows)}
for name, rs in (("all25", rows), ("minus_leaked3", clean), ("minus_leaked3_flagged5", strict)):
    out[name] = {k: tally(rs, k) for k in ("old_rule", "first", "final", "final_orig_rule", "mid_rule")}
    out[name]["always_yes"] = {"days": len(rs), "handed": 0, "confirmed": len(rs), "right": sum(r["truth1"] == "번진다" for r in rs),
                               "wrong": sum(r["truth1"] != "번진다" for r in rs)}
ch = [r for r in rows if r["changed"]]
out["changed_days"] = [{"date": r["date"], "first": r["first"], "final": r["final"], "truth": r["truth1"],
                        "effect": ("틀린 확정을 막음" if r["first"] != "넘김" and r["first"] != r["truth1"] and r["final"] != r["first"] and r["final"] in ("넘김", r["truth1"]) else
                                   "맞는 확정으로 바꿈" if r["final"] == r["truth1"] else
                                   "맞았을 확정을 넘김으로 물림" if r["first"] == r["truth1"] and r["final"] == "넘김" else
                                   "넘김으로 바꿈" if r["final"] == "넘김" else "틀린 확정으로 바꿈"), "leak": r["leak"], "flag": r["flag"]} for r in ch]
ln = [r for r in rows if r["lean"]]
out["lean_on_handed"] = {"days": len(ln), "right": sum(r["lean"] == r["truth1"] for r in ln), "wrong_days": [r["date"] for r in ln if r["lean"] != r["truth1"]]}
no = [r for r in rows if r["truth1"] == "안 번진다"]
out["non_spread_days"] = [{"date": r["date"], "first": r["first"], "final": r["final"], "lean": r["lean"], "mid_rule": r["mid_rule"], "old_rule": r["old_rule"]} for r in no]
c2 = [r for r in rows if r["s2"] != "넘김"]
out["s2"] = {"confirmed": len(c2), "right": sum(r["s2"] == r["truth2"] for r in c2), "wrong_days": [r["date"] for r in c2 if r["s2"] != r["truth2"]],
             "truth_continue": sum(r["truth2"] == "이어진다" for r in rows), "same_as_today_rule_right": sum((r["truth1"] == "번진다") == (r["truth2"] == "이어진다") for r in rows)}
out["artifact_day"] = {"date": "2025-04-09", "spy": next(r["spy"] for r in rows if r["date"] == "2025-04-09"), "chips_down": next(r["chips_down"] for r in rows if r["date"] == "2025-04-09")}
out["rows"] = rows
assert out["all25"]["old_rule"]["handed"] == 23 and out["all25"]["old_rule"]["confirmed"] == 2, out["all25"]["old_rule"]  # 기획서의 「확정 2 · 넘김 23」과 맞는지
(H / "exp2_result.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
L = ["| 날 | 정답 | 예전 규칙 | 첫 판정 | 끝 판정 | 기운 쪽 | 한 줄 규칙 | 비고 |", "|---|---|---|---|---|---|---|---|"]
for r in rows:
    L.append(f"| {r['date']} | {r['truth1']} | {r['old_rule']} | {r['first']} | {r['final']}{'(바꿈)' if r['changed'] else ''} | {r['lean'] or ''} | {r['mid_rule']} | {r['leak'] or r['flag'] or ''} |")
(H / "exp2_table.md").write_text("\n".join(L), encoding="utf-8")
for k in ("all25", "minus_leaked3", "minus_leaked3_flagged5"):
    print(k); [print("  ", n, v) for n, v in out[k].items()]
print("changed", json.dumps(out["changed_days"], ensure_ascii=False)); print("lean", out["lean_on_handed"]); print("s2", out["s2"])
print("non-spread", json.dumps(out["non_spread_days"], ensure_ascii=False)); print("truth yes", out["truth_spread_yes"], "/", out["n"])
