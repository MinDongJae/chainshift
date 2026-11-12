# -*- coding: utf-8 -*-
"""(다) 단계 사이 번짐 · (라) 미리 보이는 신호 · 사건 목록 날 — AI 인프라 58종목, 긴 주가.
읽는 것(읽기만, 망 · 유료 AI 안 씀):
  $CHAINSHIFT_DATA/net/backtest/returns_long.csv.gz   58종목+SPY 조정 종가 2021-01-04~2026-11-10
  kic_precheck/data/chain.json        단계(칩 9 · 전력 쪽 19 …)와 2026-06-30 공개 보유 금액
  kic_precheck/data/shock_days.json   앞 판 「칩 충격일 25일」(기간 전체 자료로 고른 사후 목록)
  kic_precheck/regime_monitor.py      칩 충격 날 규칙(그달 앞 자료 하위 5%) · 국면(link) · 그달 앞 중간값(link_cut)
쓰는 것: long_panel.json. 쓰는 법: python -X utf8 long_panel.py

예상 = 종목마다 그날 앞 W거래일 OLS(절편 넣고 맞춤) 기울기 × 그날 실제 요인 등락.
  L1 시장 하나(SPY) · L2 시장 + 칩 9종목 같은 비중 평균 등락(칩이 얼마나 빠질지 안다고 둔 값 — 앞 판 「평소 숫자」와 같은 생각)
결과 = 보유 금액 × 그날 실제 등락(달러)이 예상보다 더 큰 손실이었나.
"""
import json, sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binomtest, fisher_exact

HERE = Path(__file__).resolve().parent
import os
KIC = Path(os.environ.get("CHAINSHIFT_DATA", "data") + "")
sys.path.insert(0, (KIC / "mcp_kic_precheck").as_posix())
from kic_precheck import regime_monitor as RM  # noqa: E402

DATA = KIC / "mcp_kic_precheck/kic_precheck/data"
CH = json.loads((DATA / "chain.json").read_text(encoding="utf-8"))
CHIPS = CH["stages"][0]["tick"]; POWERS = [t for s in CH["stages"] if s["name"] in CH["power_stages"] for t in s["tick"]]
HOLD = CH["holdings_usd"]
PX = (1 + pd.read_csv(KIC / "net/backtest/returns_long.csv.gz", index_col=0, parse_dates=True, float_precision="round_trip")).cumprod().mul(100)
T = [t for t in HOLD if t in PX]
R = PX.pct_change(fill_method=None).iloc[1:]
IDX = R.index; A = R[T].to_numpy(float); SPY = R["SPY"].to_numpy(float); USD = np.array([HOLD[t] for t in T])
col = {t: j for j, t in enumerate(T)}
CHIPF = R[CHIPS].mean(axis=1).to_numpy(float)
H = RM.monitor_history(PX[CHIPS + POWERS + ["SPY"]], CHIPS, POWERS, RM.MonitorConfig(hysteresis=0.03)).reindex(IDX)
SHOCK = (H["eligible"] == True) & (H["chip_shock"] == True)  # noqa: E712
OLD = [pd.Timestamp(x["d"]) for x in json.loads((DATA / "shock_days.json").read_text(encoding="utf-8"))["days"]]
EVENTS = ["2025-01-27", "2025-01-28", "2026-10-30", "2026-11-02", "2026-11-03", "2026-11-04", "2026-11-05", "2026-11-06"]
spy_s = R["SPY"]; mkt_cut = spy_s.rolling(250, min_periods=250).quantile(0.05).shift(1)
MKT = (spy_s <= mkt_cut) & (spy_s < 0)
# 거울: 칩이 시장보다 크게 오른 날(그달 앞 자료 상위 5%) — 번짐이 내릴 때만 큰지 보려고
cr = H["chip_resid"]; up_cut = pd.Series(np.nan, index=IDX); mon = IDX.strftime("%Y-%m")
for m in sorted(set(mon)):
    past = cr.loc[IDX < IDX[mon == m][0]].dropna()
    if len(past) >= 126:
        up_cut[mon == m] = float(past.quantile(0.95))
SURGE = (cr >= up_cut) & (cr > 0) & (H["chip_return"] > 0)


def predict(W):
    n, m = A.shape; P = {"L1": np.full((n, m), np.nan), "L2": np.full((n, m), np.nan)}
    for i in range(W, n):
        w = slice(i - W, i); ok = ~np.isnan(A[w]).any(axis=0) & ~np.isnan(A[i])
        if not ok.any() or np.isnan(CHIPF[w]).any() or np.isnan(CHIPF[i]):
            continue
        for k, X, x in (("L1", SPY[w][:, None], np.array([SPY[i]])), ("L2", np.column_stack([SPY[w], CHIPF[w]]), np.array([SPY[i], CHIPF[i]]))):
            B = np.linalg.lstsq(np.column_stack([np.ones(W), X]), A[w][:, ok], rcond=None)[0]
            P[k][i, ok] = x @ B[1:]
    return P


def series(P, ticks):
    c = np.array([col[t] for t in ticks if t in col]); a, p = A[:, c], P[:, c]; ok = ~np.isnan(a) & ~np.isnan(p); u = USD[c][None, :]
    none = ok.sum(axis=1) == 0
    return np.where(none, np.nan, np.where(ok, a * u, 0).sum(axis=1)), np.where(none, np.nan, np.where(ok, p * u, 0).sum(axis=1))


def stats(act, pre, oa=None, op=None):
    v = ~np.isnan(act) & ~np.isnan(pre); act, pre = act[v], pre[v]
    if len(act) == 0:
        return {"days": 0}
    gap = pre - act; worse = act < pre; loss = act < 0; both = pre < 0
    o = {"days": int(len(act)), "loss_days": int(loss.sum()), "worse_days": int(worse.sum()), "worse_pct": round(float(worse.mean() * 100), 1),
         "loss_and_worse_days": int((loss & worse).sum()),
         "ratio_days": int(both.sum()), "ratio_median": round(float(np.median(act[both] / pre[both])), 2) if both.any() else None,
         "sum_actual_e8": round(float(act.sum() / 1e8), 2), "sum_pred_e8": round(float(pre.sum() / 1e8), 2),
         "sum_ratio": round(float(act.sum() / pre.sum()), 2) if pre.sum() < 0 else None,
         "gap_sum_e8": round(float(gap.sum() / 1e8), 2), "gap_median_e8": round(float(np.median(gap) / 1e8), 3), "gap_max_e8": round(float(gap.max() / 1e8), 2)}
    if oa is not None:
        bv = ~np.isnan(oa) & ~np.isnan(op); p0 = float((oa[bv] < op[bv]).mean())
        o["other_days"] = int(bv.sum()); o["other_worse_pct"] = round(p0 * 100, 1); o["p_vs_other"] = round(float(binomtest(int(worse.sum()), len(act), p0).pvalue), 4)
    return o


def perm_test(flag, outcome, gap, rng, n=10000):
    flag = np.asarray(flag, bool); w = np.asarray(outcome, float); g = np.asarray(gap, float)
    if flag.sum() == 0 or (~flag).sum() == 0:
        return {"n": int(len(flag))}
    d = w[flag].mean() - w[~flag].mean(); gd = g[flag].mean() - g[~flag].mean(); c = cg = 0
    for _ in range(n):
        s = rng.permutation(flag)
        c += abs(w[s].mean() - w[~s].mean()) >= abs(d) - 1e-12; cg += abs(g[s].mean() - g[~s].mean()) >= abs(gd) - 1e-12
    tab = [[int(w[flag].sum()), int(flag.sum() - w[flag].sum())], [int(w[~flag].sum()), int((~flag).sum() - w[~flag].sum())]]
    return {"n": int(len(flag)), "low_n": int(flag.sum()), "low_worse": tab[0][0], "low_worse_pct": round(float(w[flag].mean() * 100), 1),
            "high_n": int((~flag).sum()), "high_worse": tab[1][0], "high_worse_pct": round(float(w[~flag].mean() * 100), 1),
            "diff_pt": round(float(d * 100), 1), "perm_p_two_sided": round(c / n, 4), "fisher_p": round(float(fisher_exact(tab)[1]), 4),
            "low_gap_mean_e8": round(float(g[flag].mean()), 3), "high_gap_mean_e8": round(float(g[~flag].mean()), 3),
            "low_gap_sum_e8": round(float(g[flag].sum()), 2), "high_gap_sum_e8": round(float(g[~flag].sum()), 2), "gap_perm_p_two_sided": round(cg / n, 4)}


def run(W):
    P = predict(W); ok_day = ~np.isnan(P["L2"]).all(axis=1); rng = np.random.default_rng(7)
    out = {"W": W, "eval_from": str(IDX[ok_day][0].date()), "eval_to": str(IDX[ok_day][-1].date()), "eval_days": int(ok_day.sum())}
    scopes = {"전력 쪽 19종목": POWERS, "칩 뺀 49종목": [t for t in T if t not in CHIPS], "AI 인프라 58종목 전체": T, "칩 9종목": CHIPS}
    for st in CH["stages"][1:]:
        scopes["단계: " + st["name"]] = st["tick"]
    out["scope_usd_e8"] = {k: round(float(sum(HOLD[t] for t in v if t in col) / 1e8), 1) for k, v in scopes.items()}
    crit = {"chip_causal_all": SHOCK.to_numpy() & ok_day,
            "chip_causal_2025_2026oct": SHOCK.to_numpy() & ok_day & (IDX >= "2025-01-01") & (IDX <= "2026-10-29"),
            "chip_old_hindsight_list": np.array([d in set(OLD) for d in IDX]) & ok_day,
            "mkt_bottom5": MKT.to_numpy() & ok_day, "chip_surge_mirror": SURGE.fillna(False).to_numpy() & ok_day}
    out["crit_days"] = {k: int(v.sum()) for k, v in crit.items()}
    out["chip_causal_days"] = [str(d.date()) for d in IDX[crit["chip_causal_all"]]]
    res = {}
    for cn, cm in crit.items():
        res[cn] = {}
        for mn in ("L1", "L2"):
            res[cn][mn] = {}
            for sn, tk in scopes.items():
                act, pre = series(P[mn], tk); oth = ok_day & ~cm
                res[cn][mn][sn] = stats(act[cm], pre[cm], act[oth], pre[oth])
    out["by_criterion"] = res
    # 해마다(전력 쪽, L2, 칩 충격일) — 한 해에 몰린 결과인지
    act, pre = series(P["L2"], POWERS); cm = crit["chip_causal_all"]
    out["power_L2_by_year"] = {str(y): {k: v for k, v in stats(act[cm & (IDX.year == y)], pre[cm & (IDX.year == y)]).items() if k in ("days", "loss_days", "worse_days", "loss_and_worse_days", "gap_sum_e8", "sum_ratio")}
                               for y in sorted(set(IDX.year[cm]))}
    # 앞 판 17/21 과 같은 세기: 전력 쪽 실제가 손실인 날 중 예상도 손실, 그중 예상이 작게 본 날
    def old_count(cm_):
        a, p = act[cm_], pre[cm_]; loss = a < 0
        return {"days": int(cm_.sum()), "power_loss_days": int(loss.sum()), "pred_also_loss": int((loss & (p < 0)).sum()), "pred_understated": int((loss & (p < 0) & (a < p)).sum()),
                "pred_gain_but_loss": int((loss & (p >= 0)).sum()), "gap_sum_e8_on_loss_days": round(float((p - a)[loss].sum() / 1e8), 2)}
    out["old_style_count_power_L2"] = {k: old_count(v) for k, v in crit.items() if k.startswith("chip") and "mirror" not in k}
    # (라) 국면: 전날까지 60거래일 상관 · 그달 앞 자료 중간값으로 높낮이
    link_prev = H["link"].shift(1); cut = H["link_cut"]
    low = (link_prev < cut).to_numpy(); have = (link_prev.notna() & cut.notna()).to_numpy()
    reg = {}
    for sn in ("전력 쪽 19종목", "칩 뺀 49종목"):
        a, p = series(P["L2"], scopes[sn]); m = cm & have & ~np.isnan(p)
        reg[sn] = perm_test(low[m], (a[m] < p[m]), (p[m] - a[m]) / 1e8, rng)
        a1, p1 = series(P["L1"], scopes[sn]); m1 = cm & have & ~np.isnan(p1)
        reg[sn + " (시장 하나 모형 기준)"] = perm_test(low[m1], (a1[m1] < p1[m1]), (p1[m1] - a1[m1]) / 1e8, rng)
        # 크기 자체: 국면 낮을 때 전력 쪽 실제 손실(달러)이 더 큰가
        reg[sn + " (실제 손실 달러 평균, 억)"] = {"low": round(float(a[m][low[m]].mean() / 1e8), 3), "high": round(float(a[m][~low[m]].mean() / 1e8), 3)}
    out["regime_signal"] = reg
    # 사건 목록 날
    ev = []
    for d in EVENTS:
        d = pd.Timestamp(d)
        if d not in IDX:
            ev.append({"date": str(d.date()), "note": "주가 없음"}); continue
        i = IDX.get_loc(d); row = {"date": str(d.date()), "spy_pct": round(SPY[i] * 100, 2), "chip9_pct": round(CHIPF[i] * 100, 2),
                                   "chip_rule_flag": bool(SHOCK.iloc[i]), "link_prev": None if pd.isna(link_prev.iloc[i]) else round(float(link_prev.iloc[i]), 2),
                                   "link_cut": None if pd.isna(cut.iloc[i]) else round(float(cut.iloc[i]), 2)}
        for sn in ("AI 인프라 58종목 전체", "전력 쪽 19종목", "칩 뺀 49종목"):
            for mn in ("L1", "L2"):
                a, p = series(P[mn], scopes[sn]); row[f"{sn}|{mn}"] = None if np.isnan(p[i]) else {"actual_e8": round(a[i] / 1e8, 2), "pred_e8": round(p[i] / 1e8, 2)}
            c = np.array([col[t] for t in scopes[sn] if t in col]); row[f"{sn}|stocks"] = int((~np.isnan(A[i, c]) & ~np.isnan(P["L2"][i, c])).sum())
        ev.append(row)
    out["event_days"] = ev
    return out


if __name__ == "__main__":
    final = {"inputs": {"prices_long": (KIC / "net/backtest/returns_long.csv.gz").as_posix(), "chain": str(DATA / "chain.json"), "old_days": str(DATA / "shock_days.json")},
             "n_stocks": len(T), "old_list_days": [str(d.date()) for d in OLD]}
    for W in (250, 60):
        final[f"W{W}"] = run(W)
    (HERE / "long_panel.json").write_text(json.dumps(final, ensure_ascii=False, indent=1), encoding="utf-8")
    for W in (250, 60):
        o = final[f"W{W}"]; print("==== W", W, o["eval_from"], o["eval_to"], o["eval_days"], o["crit_days"], o["scope_usd_e8"])
        for cn in o["by_criterion"]:
            for mn in ("L1", "L2"):
                for sn in ("전력 쪽 19종목", "칩 뺀 49종목", "AI 인프라 58종목 전체"):
                    print(cn, mn, sn, o["by_criterion"][cn][mn][sn])
        print("단계별 L2 chip_causal_all", {k: {x: v[x] for x in ("days", "worse_days", "other_worse_pct", "p_vs_other", "sum_ratio", "gap_sum_e8")} for k, v in o["by_criterion"]["chip_causal_all"]["L2"].items() if k.startswith("단계")})
        print("by_year", o["power_L2_by_year"]); print("old_style", o["old_style_count_power_L2"]); print("regime", json.dumps(o["regime_signal"], ensure_ascii=False))
        for e in o["event_days"]:
            print(e)
