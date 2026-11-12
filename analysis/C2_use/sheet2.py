# -*- coding: utf-8 -*-
"""점검 보고서(가상 20종목 10억 달러 · 미국 장 2026-10-22 → 서울 10-23 아침)의 빈칸 계산.
C_use/calc.py 와 같은 포지션 · 같은 계산 함수(net/bundles/bundles.py)로 걸린 고리(AI 데이터센터 인프라 6종목)를 다시 내어 맞대고,
 ③ 한도 점검(가상 한도 둘) ④ 헤지(시장 · 업종 상장지수펀드) ⑤ 군집 밖 4종목의 시장 요인 값을 더한다.
뒤 자료 안 섞음: 헤지 비율은 그날 전 250거래일 회귀, 베타는 bundles 의 그날 앞 베타(BC).
입력: net/bundles/bundles.py · result.json · net/returns.csv.gz · net/net_result.json · etf_px_ret.csv(fetch_etf.py 가 야후에서 받은 수정 종가) · C_use/sheet.json(맞대기)
출력: sheet2.json   실행: python -X utf8 sheet2.py"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
import os
sys.path.insert(0, os.environ.get("CHAINSHIFT_DATA", "data") + "/net/bundles")
import bundles as BD  # noqa: E402
H = Path(__file__).resolve().parent
R = json.loads(Path(os.environ.get("CHAINSHIFT_DATA", "data") + "/net/bundles/result.json").read_text(encoding="utf-8"))
OLD = json.loads((H.parent / "C_use/sheet.json").read_text(encoding="utf-8"))
PORT = OLD["portfolio"]; ASOF = "2026-10-22"; asof = pd.Timestamp(ASOF)
assert sum(PORT.values()) == 1000
ETF = (1 + pd.read_csv(H / "etf_px_ret.csv", index_col=0, parse_dates=True, float_precision="round_trip")).cumprod().mul(100).pct_change()
assert abs(ETF.at[asof, "SPY"] - BD.SIMPLE.at[asof, "SPY"]) < 2e-4            # 두 주가 출처가 같은 값인지
lab = {t: b["id"] for b in R["bundles"] for t in b["members"]}; BY = {b["id"]: b for b in R["bundles"]}
for t in BD.ND: BD.ND[t]["usd"] = PORT.get(t, 0) * 1e6                        # 메모리 안에서만


def el_hit(M):   # calc.py 와 같음 — bundles.shocks 의 판정 가능일 · 충격일
    br, ba = BD.bmean(BD.RC, M), BD.bmean(BD.SIMPLE, M)
    cut = pd.Series(np.nan, index=br.index); mon = br.index.strftime("%Y-%m")
    for m in sorted(set(mon)):
        past = br.loc[br.index < br.index[mon == m][0]].dropna()
        if len(past) >= BD.CAL_MIN: cut[mon == m] = float(past.quantile(BD.Q))
    el = cut.notna() & br.notna() & ba.notna()
    return el, el & (br <= cut) & (br < 0) & (ba < 0)


bid = lab["NVDA"]; b = BY[bid]; M = b["members"]; held = [t for t in M if t in PORT]; amt = pd.Series({t: float(PORT[t]) for t in held})
lead_set = set(b["split"]["lead"]); lead_r = BD.bmean(BD.RC, b["split"]["lead"])
el, hit = el_hit(M); days = [d for d in BD.LOGR.index[hit] if d <= asof]
pnl_ser = BD.SIMPLE[held].mul(amt, axis=1).sum(axis=1)                          # 고리 6종목 하루 손익(백만 달러), 금액 고정


POWER = [t for t in held if t in ("CAT", "ETN", "VRT")]                              # 고리 안 칩 밖(전력 · 냉각 설비) 3종목
pnl_pow = BD.SIMPLE[POWER].mul(amt[POWER], axis=1).sum(axis=1)


def hedge_resid(d, cols, win=250, pnl_ser=pnl_ser):
    """그날 전 win 거래일의 고리 손익을 cols 등락에 회귀(절편 포함) → 그날 헤지 뒤 남는 손익과 헤지 명목."""
    i = ETF.index.get_loc(d); X = ETF[cols].iloc[i - win:i]; y = pnl_ser.reindex(X.index)
    ok = X.notna().all(axis=1) & y.notna(); A = np.column_stack([np.ones(ok.sum()), X[ok].values])
    coef = np.linalg.lstsq(A, y[ok].values, rcond=None)[0][1:]
    return float(pnl_ser[d] - (coef * ETF.loc[d, cols].values).sum()), {c: round(float(v), 1) for c, v in zip(cols, coef)}


HEDGES = {"SPY": ["SPY"], "SPY+SMH": ["SPY", "SMH"], "SMH": ["SMH"], "SMH+XLI": ["SMH", "XLI"], "SMH+XLU": ["SMH", "XLU"], "SPY+SMH+XLI": ["SPY", "SMH", "XLI"]}
HEDGES_POW = {"SPY": ["SPY"], "XLI": ["XLI"], "SPY+XLI": ["SPY", "XLI"], "XLU": ["XLU"], "SMH": ["SMH"], "SMH+XLI": ["SMH", "XLI"]}
rep = []
for d in days:
    o, _, _ = BD.day_loss(d, M, lead_set, lead_r, BD.RC, BD.BC)
    A = (o["lead"][0] + o["rest"][0]) / 1e6; N = (o["lead"][1] + o["rest"][1]) / 1e6
    mk = sum(PORT[t] * float(np.expm1(BD.BC.at[d, t] * float(BD.SPY.loc[d]))) for t in held if pd.notna(BD.BC.at[d, t]))
    row = {"date": BD.iso(d), "actual_m": round(A, 2), "normal_m": round(N, 2), "market_part_m": round(mk, 2), "spy_pct": round(float(BD.SIMPLE.at[d, "SPY"]) * 100, 2)}
    for k, cols in HEDGES.items(): row["resid_" + k] = round(hedge_resid(d, cols)[0], 2)
    row["power_actual_m"] = round(float(pnl_pow[d]), 2)
    for k, cols in HEDGES_POW.items(): row["power_resid_" + k] = round(hedge_resid(d, cols, pnl_ser=pnl_pow)[0], 2)
    rep.append(row)
today = next(r for r in rep if r["date"] == ASOF); old = [r for r in rep if r["date"] < ASOF]
o0 = OLD["bundles"][[x["id"] for x in OLD["bundles"]].index(bid)]
assert len(old) == o0["past_shock_days"] == 33 and abs(sum(r["actual_m"] for r in old) - o0["replay_sum_actual_m"]) < 0.05 and abs(today["actual_m"] - (-15.06)) < 0.01, "C_use 값과 안 맞음"
sA = sum(r["actual_m"] for r in old)

# ③ 한도 — 가상 값 둘(담당자가 넣는 값의 예시). 고리 하루 손실 한도 = 포지션 전체(10억 달러)의 1.0% · 1.5%
LIM = {"고리 하루 손실 한도 가(포지션의 1.0% = 10.0)": -10.0, "고리 하루 손실 한도 나(포지션의 1.5% = 15.0)": -15.0}
limits = {}
for name, L in LIM.items():
    br_a = [r["date"] for r in old if r["actual_m"] <= L]; br_n = [r["date"] for r in old if r["normal_m"] <= L]
    only_a = [r for r in old if r["actual_m"] <= L < r["normal_m"]]
    limits[name] = {"limit_m": L, "past33_replay_breach": len(br_a), "past33_model_breach": len(br_n),
                    "past33_replay_breach_but_model_inside": len(only_a), "those_days": [(r["date"], r["actual_m"], r["normal_m"]) for r in only_a],
                    "past33_model_breach_but_replay_inside": sum(r["normal_m"] <= L < r["actual_m"] for r in old),
                    "today_replay_breach": today["actual_m"] <= L, "today_model_breach": today["normal_m"] <= L,
                    "today_headroom_replay_m": round(today["actual_m"] - L, 2), "today_headroom_model_m": round(today["normal_m"] - L, 2)}

# ④ 헤지 — 지난 33번에서 헤지 뒤 남는 몫
hedge = {"market_beta_part": {"how": "Σ 금액 × (exp(그날 앞 시장 베타 × 그날 SPY) − 1) — C_use 와 같은 식", "sum_m": round(sum(r["market_part_m"] for r in old), 2),
                              "removed_pct": round(sum(r["market_part_m"] for r in old) / sA * 100, 1)}}
for k, cols in HEDGES.items():
    res = [r["resid_" + k] for r in old]
    hedge[k] = {"how": f"그날 전 250거래일 회귀로 정한 {' · '.join(cols)} 매도 헤지", "past33_resid_sum_m": round(sum(res), 2), "past33_left_pct": round(sum(res) / sA * 100, 1),
                "past33_abs_resid_sum_m": round(sum(abs(x) for x in res), 2), "past33_abs_left_pct": round(sum(abs(x) for x in res) / abs(sA) * 100, 1),
                "past33_days_still_loss": sum(x < 0 for x in res), "past33_resid_median_m": round(float(np.median(res)), 2), "past33_resid_worst_m": round(min(res), 2),
                "today_resid_m": today["resid_" + k], "today_left_pct": round(today["resid_" + k] / today["actual_m"] * 100, 1), "today_notional_m": hedge_resid(asof, cols)[1]}

sP = sum(r["power_actual_m"] for r in old)
hedge_power = {"what": f"고리 안 칩 밖 3종목({' · '.join(POWER)}) {float(amt[POWER].sum()):.0f}백만 달러만 따로", "past33_actual_sum_m": round(sP, 2),
               "past33_days_loss": sum(r["power_actual_m"] < 0 for r in old), "today_actual_m": today["power_actual_m"]}
for k, cols in HEDGES_POW.items():
    res = [r["power_resid_" + k] for r in old]
    hedge_power[k] = {"past33_resid_sum_m": round(sum(res), 2), "past33_left_pct": round(sum(res) / sP * 100, 1),
                      "past33_abs_left_pct": round(sum(abs(x) for x in res) / sum(abs(r["power_actual_m"]) for r in old) * 100, 1),
                      "past33_days_still_loss": sum(x < 0 for x in res), "today_resid_m": today["power_resid_" + k],
                      "today_notional_m": hedge_resid(asof, cols, pnl_ser=pnl_pow)[1]}

# ⑤ 군집 밖 4종목 — 시장 요인으로만
out4 = [t for t in PORT if t not in lab]; spy_l = float(BD.SPY.loc[asof])
rows4 = [{"t": t, "usd_m": PORT[t], "beta": round(float(BD.BC.at[asof, t]), 2), "actual_m": round(PORT[t] * float(BD.SIMPLE.at[asof, t]), 2),
          "market_only_m": round(PORT[t] * float(np.expm1(BD.BC.at[asof, t] * spy_l)), 2)} for t in out4]
tot = sum(PORT[t] * float(BD.SIMPLE.at[asof, t]) for t in PORT)
port_mkt = sum(PORT[t] * float(np.expm1(BD.BC.at[asof, t] * spy_l)) for t in PORT)
others = [t for t in PORT if t in lab and t not in held]
sheet = {"asof_us_close": ASOF, "seoul_morning": "2026-10-23", "note": "가상 예시 포지션 20종목 10억 달러(실제 계좌 아님). 금액 백만 달러.",
         "portfolio_today_m": round(tot, 2), "portfolio_market_only_m": round(port_mkt, 2), "spy_today_pct": round(float(BD.SIMPLE.at[asof, "SPY"]) * 100, 2),
         "chain": {"id": bid, "name": b["name"], "held": held, "usd_m": float(amt.sum()), "today": today,
                   "today_gap_m": round(today["actual_m"] - today["normal_m"], 2), "today_ratio": round(today["actual_m"] / today["normal_m"], 2),
                   "past33": {"n": len(old), "from": old[0]["date"], "to": old[-1]["date"], "sum_actual_m": round(sA, 2), "sum_normal_m": round(sum(r["normal_m"] for r in old), 2),
                              "median_actual_m": round(float(np.median([r["actual_m"] for r in old])), 2), "median_normal_m": round(float(np.median([r["normal_m"] for r in old])), 2),
                              "worst": min(old, key=lambda r: r["actual_m"]), "best": max(old, key=lambda r: r["actual_m"]),
                              "p10_actual_m": round(float(np.quantile([r["actual_m"] for r in old], 0.1)), 2), "p90_actual_m": round(float(np.quantile([r["actual_m"] for r in old], 0.9)), 2),
                              "days_actual_worse_than_model": sum(r["actual_m"] < r["normal_m"] for r in old),
                              "biggest_gap_day": min(old, key=lambda r: r["actual_m"] - r["normal_m"])}},
         "limits_virtual": limits, "hedge": hedge, "hedge_power_part": hedge_power,
         "outside_cluster": {"tickers": out4, "usd_m": sum(PORT[t] for t in out4), "rows": rows4, "actual_m": round(sum(r["actual_m"] for r in rows4), 2),
                             "market_only_m": round(sum(r["market_only_m"] for r in rows4), 2),
                             "spy_hedge_notional_m": round(sum(PORT[t] * float(BD.BC.at[asof, t]) for t in out4), 1)},
         "other_clusters": {"tickers": others, "usd_m": sum(PORT[t] for t in others), "actual_m": round(sum(PORT[t] * float(BD.SIMPLE.at[asof, t]) for t in others), 2),
                            "market_only_m": round(sum(PORT[t] * float(np.expm1(BD.BC.at[asof, t] * spy_l)) for t in others), 2)},
         "replay_days": rep}
(H / "sheet2.json").write_text(json.dumps(sheet, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
print(json.dumps({k: v for k, v in sheet.items() if k != "replay_days"}, ensure_ascii=False, indent=1, default=float))
