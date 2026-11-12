# -*- coding: utf-8 -*-
"""실험 1 — 업종만으로 짠 58종목 대 공시 관계로 넓힌 단계의 재현 손실. 규칙은 exp1_prereg.md.
입력: net/returns.csv.gz · net/universe.json · mcp_kic_precheck/kic_precheck/data/chain.json · relations/{us,kr}/edges.json
출력: exp1_result.json   실행: python -X utf8 exp1.py"""
import json
from pathlib import Path
import pandas as pd
import os
K = Path(os.environ.get("CHAINSHIFT_DATA", "data") + ""); H = Path(__file__).parent
REL = K / "relations"
J = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))
px = (1 + pd.read_csv(K / "net/returns.csv.gz", index_col=0, parse_dates=True, float_precision="round_trip")).cumprod().mul(100); ret = px.pct_change()
CH = J(K / "mcp_kic_precheck/kic_precheck/data/chain.json"); S58 = CH["holdings_usd"]
held = {v["ticker"]: v["value"] for v in J(K / "net/universe.json")["companies"].values() if v.get("ticker")}
E = J(REL / "us/edges.json") + J(REL / "kr/edges.json")
DAYS = ["2026-08-18", "2026-09-14", "2026-10-08", "2026-10-22"]
out = []
for d in DAYS:
    r = ret.loc[d]
    add, outside = {}, []
    for e in E:
        if e["status"] != "verified_original": continue
        pub = min(x["published_at"] for x in e["evidence"])
        if not pub < d: continue
        f, t = e["from"]["id"].split(":")[-1], e["to"]["id"].split(":")[-1]
        if (f in S58) == (t in S58): continue
        o, inn = (t, f) if f in S58 else (f, t)
        ev = min(e["evidence"], key=lambda x: x["published_at"])
        row = {"edge": e["edge_id"], "in58": inn, "outside": o, "relation": e["relation"], "published_at": pub,
               "quote": ev["quote"][:260], "url": ev["url"]}
        if o in held and o in r.index and pd.notna(r[o]): add.setdefault(o, []).append(row)
        else: outside.append(row)
    w = lambda ts: sum(held[t] * r[t] for t in ts) / sum(held[t] for t in ts) * 100
    base = sum(S58[t] * r[t] for t in S58 if t in r.index and pd.notna(r[t])) / 1e6
    addl = {t: held[t] * r[t] / 1e6 for t in add}
    rest = [t for t in held if t not in S58 and t not in add and t in r.index and pd.notna(r[t])]
    a_ret, rest_ret, spy = w(add), w(rest), r["SPY"] * 100
    out.append({"date": d, "loss58_usd_m": round(base, 1), "added_usd_m": round(sum(addl.values()), 1),
                "expanded_usd_m": round(base + sum(addl.values()), 1),
                "ratio": round((base + sum(addl.values())) / base, 3),
                "added_value_usd_m": round(sum(held[t] for t in add) / 1e6, 1), "base_value_usd_m": round(sum(S58.values()) / 1e6, 1),
                "ret58_pct": round(base * 1e6 / sum(S58.values()) * 100, 2), "added_ret_pct": round(a_ret, 2),
                "rest_ret_pct": round(rest_ret, 2), "spy_pct": round(spy, 2), "n_rest": len(rest),
                "added_worse_than_spy": bool(a_ret < spy), "added_worse_than_rest": bool(a_ret < rest_ret),
                "added": {t: {"usd_m": round(v, 1), "ret_pct": round(r[t] * 100, 2), "value_usd_m": round(held[t] / 1e6, 1), "why": add[t]} for t, v in addl.items()},
                "outside_not_held": sorted({x["outside"] for x in outside}), "n_edges_usable": sum(len(v) for v in add.values()) + len(outside)})
assert all(abs(o["expanded_usd_m"] - o["loss58_usd_m"] - o["added_usd_m"]) < 0.11 for o in out)
(H / "exp1_result.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
for o in out:
    print(o["date"], "58:", o["loss58_usd_m"], "더함:", o["added_usd_m"], "넓힘:", o["expanded_usd_m"], "배", o["ratio"],
          "| 등락 58", o["ret58_pct"], "더한 회사", o["added_ret_pct"], "나머지", o["rest_ret_pct"], "SPY", o["spy_pct"],
          "| SPY보다↓", o["added_worse_than_spy"], "나머지보다↓", o["added_worse_than_rest"])
    print("   ", {t: (v["ret_pct"], v["usd_m"]) for t, v in o["added"].items()}, "보유 밖", len(o["outside_not_held"]))
