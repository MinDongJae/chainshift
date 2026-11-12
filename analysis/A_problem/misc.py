# -*- coding: utf-8 -*-
"""(마) 앞 판 숫자 어긋남의 원인 + 딥시크 날 전체 공개 보유(짧은 창) + 국면 높낮이를 직전 250거래일 중간값으로 가른 판.
읽기만. 쓰는 것: misc.json. 쓰는 법: python -X utf8 misc.py"""
import bisect, json
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
import os
NET = Path(os.environ.get("CHAINSHIFT_DATA", "data") + "/net")
R2B = Path(os.environ.get("CHAINSHIFT_DATA", "data") + "/proposal/r2b/analysis")
J = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))  # noqa: E731
out = {}

# 1) 56 대 58 종목
s = J(NET / "holdings_panel/raw/stress_2025-01-27.json")
PL = (1 + pd.read_csv(NET / "backtest/returns_long.csv.gz", index_col=0, parse_dates=True, float_precision="round_trip")).cumprod().mul(100)
out["56_vs_58"] = {"compared_stocks": s["total"]["n_stocks"], "skipped": s["skipped"],
                   "first_price_date": {x["ticker"]: str(PL[x["ticker"]].dropna().index[0].date()) for x in s["skipped"] if x["ticker"] in PL},
                   "source": (NET / "holdings_panel/raw/stress_2025-01-27.json").as_posix()}

# 2) 24일 대 25일
sd = J(os.environ.get("CHAINSHIFT_DATA", "data") + "/mcp_kic_precheck/kic_precheck/data/shock_days.json"); sc = J(R2B / "stress_scan.json")
out["24_vs_25"] = {"list_days": len(sd["days"]), "days_used": sc["days_used"], "days_missing": sc["days_missing"], "price_source": sc["price_source"],
                   "source": [str(R2B / "stress_scan.json"), "kic_precheck/data/shock_days.json"]}

# 3) 246 + 284 = 530 대 549
R = J(NET / "bundles/result.json"); c = Counter()
for b in R["bundles"]:
    d, v = b["regime"]["wk"]["d"], b["regime"]["wk"]["v"]
    for x in b["shock"]["days"]:
        c["all"] += 1
        if x.get("ratio") is None:
            c["평소 숫자가 손실이 아님(배수 없음)"] += 1; continue
        if x["normal_e8"] >= 0:
            c["평소 숫자가 0.005억 달러보다 작은 손실이라 반올림 0.00"] += 1; continue
        i = bisect.bisect_left(d, x["date"]) - 1
        if i < 0 or v[i] is None:
            c["충격일 앞 주 국면 값 없음"] += 1; continue
        c["센 날"] += 1
out["530_vs_549"] = dict(c)

# 4) 677줄 대 650 + 24
h = J(NET / "holdings_cusip.json"); u = J(NET / "universe.json"); f = J(NET / "figi.json")
by_issuer = Counter(v["issuer"] for v in h.values())
fund_issuers = {x[0] for x in u["funds"]}
multi = {k: n for k, n in by_issuer.items() if n > 1}
comp_lines = sum(len(e["tickers"]) for e in u["companies"].values())
out["677_vs_674"] = {"cusip_lines": len(h), "companies": len(u["companies"]), "funds": len(u["funds"]), "company_lines_sum_of_tickers": comp_lines,
                     "companies_with_2plus_lines": {k: [t[0] for t in e["tickers"]] for k, e in u["companies"].items() if len(e["tickers"]) > 1},
                     "issuers_with_2plus_cusips": multi, "fund_tickers": len({x[1] for x in u["funds"]}),
                     "types": dict(Counter(v.get("type") for v in f.values()))}

# 5) 앞 판 수가 나온 곳
ho = J(R2B / "holdout.json")
out["where_from"] = {"19/26": ["holdout.json full.groups_over1", ho["full"]["groups_over1"], ho["full"]["groups"]],
                     "13/17": ["holdout.json holdout.groups_over1", ho["holdout"]["groups_over1"], ho["holdout"]["groups"]],
                     "11/11": ["holdout.json sector.groups_over1", ho["sector"]["groups_over1"], ho["sector"]["groups"]],
                     "1.12": ["holdout.json full.day_ratio_median (534 묶음-날의 중간값; 묶음 중간값들의 중간값은 %s)" % ho["full"]["median_of_medians"], ho["full"]["day_ratio_median"], ho["full"]["days"]],
                     "17/21": ["stress_scan.json validation_summary", sc["validation_summary"]["usual_understated_days"], sc["validation_summary"]["replay_loss_days"]]}

# 6) 딥시크 날(2025-01-27) 전체 공개 보유 — 앞 자료가 79거래일뿐이라 W=75 로만 낼 수 있음
import short_panel as SP  # noqa: E402
P = SP.run(75); i = list(SP.IDX).index(pd.Timestamp("2025-01-27")); allc = list(range(len(SP.T)))
row = {"prior_days_available": i, "W": 75, "spy_pct": round(SP.SPY[i] * 100, 2)}
scopes = {"전체": allc, "AI 인프라 묶음": [SP.col[t] for t in SP.BUN[0][2] if t in SP.col], "AI 인프라 칩 뺀 종목": [SP.col[t] for t in SP.BUN[0][2] if t in SP.col and t not in SP.CHIPS],
          "AI 인프라 밖": [j for j in allc if SP.T[j] not in set(SP.BUN[0][2])]}
for sn, cols in scopes.items():
    for mn in ("M1", "M2", "M3", "M5"):
        a, p, n = SP.scope_series(P[mn], cols); row[f"{sn}|{mn}"] = {"actual_e8": round(a[i] / 1e8, 2), "pred_e8": round(p[i] / 1e8, 2), "stocks": int(n[i])}
out["deepseek_total_W75"] = row

# 7) (라) 국면 높낮이를 「직전 250거래일 국면 값의 중간값」으로 가른 판 — 긴 주가, 칩 충격일, 전력 쪽
import long_panel as LP  # noqa: E402
rng = np.random.default_rng(7); reg = {}
link_prev = LP.H["link"].shift(1); cut250 = LP.H["link"].rolling(250, min_periods=120).median().shift(1)
for W in (250, 60):
    Pm = LP.predict(W); cm = LP.SHOCK.to_numpy() & ~np.isnan(Pm["L2"]).all(axis=1)
    have = (link_prev.notna() & cut250.notna()).to_numpy(); low = (link_prev < cut250).to_numpy()
    for sn, tk in (("전력 쪽 19종목", LP.POWERS), ("칩 뺀 49종목", [t for t in LP.T if t not in LP.CHIPS])):
        a, p = LP.series(Pm["L2"], tk); m = cm & have & ~np.isnan(p)
        reg[f"W{W} {sn}"] = LP.perm_test(low[m], a[m] < p[m], (p[m] - a[m]) / 1e8, rng)
out["regime_rolling250_median"] = reg

(HERE / "misc.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(out, ensure_ascii=False, indent=1))
