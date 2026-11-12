# -*- coding: utf-8 -*-
"""실험 1 사후 점검(미리 정하지 않은 것) — 더해진 회사가 자기 시장 민감도보다 더 빠졌나.
민감도 = 그날 전 250거래일 SPY 회귀 기울기. 입력: exp1_result.json · net/returns.csv.gz · net/universe.json"""
import json
from pathlib import Path
import pandas as pd
import os
K = Path(os.environ.get("CHAINSHIFT_DATA", "data") + ""); H = Path(__file__).parent
px = (1 + pd.read_csv(K / "net/returns.csv.gz", index_col=0, parse_dates=True, float_precision="round_trip")).cumprod().mul(100); R = px.pct_change(fill_method=None) * 100
held = {v["ticker"]: v["value"] for v in json.loads((K / "net/universe.json").read_text(encoding="utf-8"))["companies"].values() if v.get("ticker")}
res = json.loads((H / "exp1_result.json").read_text(encoding="utf-8")); out = []
for o in res:
    d = o["date"]; i = R.index.get_loc(pd.Timestamp(d)); w = R.iloc[i - 250:i]; r = R.iloc[i]; num = den = 0; per = {}
    for t in o["added"]:
        x = w[[t, "SPY"]].dropna()
        if len(x) < 60: per[t] = None; continue
        b = x[t].cov(x["SPY"]) / x["SPY"].var(); e = r[t] - b * r["SPY"]; per[t] = round(float(e), 2); num += held[t] * e; den += held[t]
    out.append({"date": d, "added_excess_pct_vw": round(num / den, 2), "per": per}); print(d, round(num / den, 2), per)
(H / "exp1_posthoc.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
