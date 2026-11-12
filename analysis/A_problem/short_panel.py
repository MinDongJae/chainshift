# -*- coding: utf-8 -*-
"""(가)(나)(라-26묶음) 공개 보유 638종목 · 바깥 기준 충격일 · 그날 앞 자료 베타 · 더 센 비교 모형.
읽는 것(읽기만, 망 · 유료 AI 안 씀):
  $CHAINSHIFT_DATA/net/returns.csv.gz            야후 수정 종가 2024-10-01~2026-10-29, 638종목+SPY
  $CHAINSHIFT_DATA/net/net_result.json       종목 섹터 · 26묶음 · 2026-06-30 13F 보유 금액
  $CHAINSHIFT_DATA/net/bundles/bundles.py    앞 판 묶음 가르기(split) · 그날 앞 베타 잔차(RC) — 함수만 빌려 씀
  $CHAINSHIFT_DATA/net/bundles/result.json   앞 판 「묶음 자기 등락 하위 5%」 충격일 549번(견줄 대상)
  $CHAINSHIFT_DATA/net/backtest/returns_long.csv.gz   SPY · AI 인프라 58종목 2021-01-04~2026-11-10 (시장 기준선 · 칩 규칙용)
  kic_precheck/regime_monitor.py                         칩 충격 날 규칙(그달 앞 자료 하위 5%)
쓰는 것: short_panel.json. 쓰는 법: python -X utf8 short_panel.py  (1분 안)

모형(모두 그날 앞 W거래일만으로 OLS, 예상 = 기울기 × 그날 실제 요인 등락, 절편은 예상에 안 넣음):
  M1 시장 하나(SPY)
  M2 앞 판 두 요인(SPY + 묶음 앞 단계 평균 등락)
  M3 업종 요인(SPY + 업종 11갈래 같은 비중 평균 등락)
  M4 M3 + 스타일 대용 둘(모멘텀: 126~21거래일 전 등락 상위 1/3 − 하위 1/3 · 변동성: 직전 60거래일 표준편차 상위 1/3 − 하위 1/3. 둘 다 전날까지 자료로 줄 세움)
  M5 M3 + 칩 9종목 같은 비중 평균 등락(칩이 얼마나 빠질지까지 안다고 둔 가장 센 기준 — 단계 사이 번짐 시험용)
  크기 · 가치 요인은 그 시점 시가총액 · 장부가 자료가 없어 넣지 않았다.
충격일 기준:
  mkt   SPY 일간 등락이 직전 250거래일 하위 5% 이하(음수)인 날
  chip  칩 9종목 규칙(regime_monitor, 그달 앞 자료 하위 5%)이 잡는 날
  own   앞 판 방식 — 그 묶음 자기 등락(시장 몫 뺀 값) 하위 5% (견줄 대상, 묶음 단위에만 있음)
"""
import json, math, sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binomtest

HERE = Path(__file__).resolve().parent
import os
NET = Path(os.environ.get("CHAINSHIFT_DATA", "data") + "/net")
sys.path.insert(0, (NET / "bundles").as_posix())
sys.path.insert(0, os.environ.get("CHAINSHIFT_DATA", "data") + "/mcp_kic_precheck")
import bundles as BD  # noqa: E402
from kic_precheck import regime_monitor as RM  # noqa: E402

R = BD.SIMPLE.copy()                 # 단순 등락, 521거래일
T = BD.TICKS; ND = BD.ND
A = R[T].to_numpy(float); SPY = R["SPY"].to_numpy(float); IDX = R.index
USD = np.array([ND[t]["usd"] for t in T])
SECT = sorted({ND[t]["sector"] for t in T})
SF = np.column_stack([np.nanmean(A[:, [j for j, t in enumerate(T) if ND[t]["sector"] == s]], axis=1) for s in SECT])
OLD = json.loads((NET / "bundles/result.json").read_text(encoding="utf-8"))
BUN = [(b["id"], b["name"], b["members"], b["split"]["lead"]) for b in OLD["bundles"]]
col = {t: j for j, t in enumerate(T)}

# 스타일 대용 요인(전날까지 자료로 줄 세움)
LR = np.log1p(R[T])
mom_char = LR.rolling(105, min_periods=90).sum().shift(22)       # d-126 ~ d-22
vol_char = R[T].rolling(60, min_periods=50).std().shift(1)


def ls_factor(char):
    out = np.full(len(IDX), np.nan); C = char.to_numpy(float)
    for i in range(len(IDX)):
        c = C[i]; ok = ~np.isnan(c) & ~np.isnan(A[i])
        if ok.sum() < 300:
            continue
        lo, hi = np.quantile(c[ok], [1 / 3, 2 / 3])
        out[i] = A[i][ok & (c >= hi)].mean() - A[i][ok & (c <= lo)].mean()
    return out


MOM, VOL = ls_factor(mom_char), ls_factor(vol_char)

# 바깥 기준 충격일
PL = (1 + pd.read_csv(NET / "backtest/returns_long.csv.gz", index_col=0, parse_dates=True, float_precision="round_trip")).cumprod().mul(100)
spy_long = PL["SPY"].pct_change(fill_method=None)
assert float((spy_long.reindex(IDX) - R["SPY"]).abs().max()) < 2e-3, "두 주가 파일의 SPY 가 다름"
mkt_cut = spy_long.rolling(250, min_periods=250).quantile(0.05).shift(1)
MKT = set(IDX[(R["SPY"] <= mkt_cut.reindex(IDX)) & (R["SPY"] < 0)])
CH = json.loads(Path(os.environ.get("CHAINSHIFT_DATA", "data") + "/mcp_kic_precheck/kic_precheck/data/chain.json").read_text(encoding="utf-8"))
CHIPS = CH["stages"][0]["tick"]; POWERS = [t for s in CH["stages"] if s["name"] in CH["power_stages"] for t in s["tick"]]
H = RM.monitor_history(PL[CHIPS + POWERS + ["SPY"]], CHIPS, POWERS, RM.MonitorConfig(hysteresis=0.03))
CHIP = set(H.index[H["eligible"] & H["chip_shock"]]) & set(IDX)


MODELS = ("M1", "M2", "M3", "M4", "M5")
CHIPF = np.nanmean(A[:, [col[t] for t in CHIPS if t in col]], axis=1)


def fit_pred(X, Y, x_day):
    """X(W×k) Y(W×n) → 예상(n). 절편 넣고 맞춘 뒤 기울기만 씀."""
    Xc = np.column_stack([np.ones(len(X)), X])
    B = np.linalg.lstsq(Xc, Y, rcond=None)[0]
    return x_day @ B[1:]


def run(W):
    n, m = A.shape
    P = {k: np.full((n, m), np.nan) for k in MODELS}
    for i in range(W, n):
        w = slice(i - W, i)
        ok = ~np.isnan(A[w]).any(axis=0) & ~np.isnan(A[i])
        if ok.sum() == 0 or np.isnan(SPY[w]).any():
            continue
        Y = A[w][:, ok]; j_ok = np.where(ok)[0]
        P["M1"][i, ok] = fit_pred(SPY[w][:, None], Y, np.array([SPY[i]]))
        X3 = np.column_stack([SPY[w], SF[w]]); x3 = np.concatenate([[SPY[i]], SF[i]])
        P["M3"][i, ok] = fit_pred(X3, Y, x3)
        if not (np.isnan(MOM[w]).any() or np.isnan(VOL[w]).any() or np.isnan(MOM[i]) or np.isnan(VOL[i])):
            X4 = np.column_stack([X3, MOM[w], VOL[w]]); x4 = np.concatenate([x3, [MOM[i], VOL[i]]])
            P["M4"][i, ok] = fit_pred(X4, Y, x4)
        X5 = np.column_stack([X3, CHIPF[w]]); x5 = np.concatenate([x3, [CHIPF[i]]])
        P["M5"][i, ok] = fit_pred(X5, Y, x5)
        P["M2"][i, ok] = P["M1"][i, ok]                      # 어느 묶음에도 안 든 종목은 시장 하나
        for _, _, mem, lead in BUN:
            lc = [col[t] for t in lead if t in col]
            L = A[i - W:i + 1][:, lc]
            if (~np.isnan(L)).sum(axis=1).min() < math.ceil(len(lc) * 0.8):
                continue
            lead_r = np.nanmean(L, axis=1)
            mc = [col[t] for t in mem if t in col and ok[col[t]]]
            if mc:
                P["M2"][i, mc] = fit_pred(np.column_stack([SPY[w], lead_r[:-1]]), A[w][:, mc], np.array([SPY[i], lead_r[-1]]))
    return P


def stats(act, pre, base_act=None, base_pre=None):
    """act · pre = 날마다 달러 손익(실제 · 예상). 부족분 = 예상 − 실제(양수면 손실을 작게 봄)."""
    act, pre = np.asarray(act, float), np.asarray(pre, float)
    v = ~np.isnan(act) & ~np.isnan(pre); act, pre = act[v], pre[v]
    if len(act) == 0:
        return {"days": 0}
    gap = pre - act; worse = act < pre; both = (pre < 0)
    o = {"days": int(len(act)), "loss_days": int((act < 0).sum()), "worse_days": int(worse.sum()),
         "worse_pct": round(float(worse.mean() * 100), 1),
         "ratio_days": int(both.sum()), "ratio_median": round(float(np.median(act[both] / pre[both])), 2) if both.any() else None,
         "sum_actual_e8": round(float(act.sum() / 1e8), 2), "sum_pred_e8": round(float(pre.sum() / 1e8), 2),
         "sum_ratio": round(float(act.sum() / pre.sum()), 2) if pre.sum() < 0 else None,
         "gap_sum_e8": round(float(gap.sum() / 1e8), 2), "gap_median_e8": round(float(np.median(gap) / 1e8), 3),
         "gap_max_e8": round(float(gap.max() / 1e8), 2)}
    if base_act is not None:
        ba, bp = np.asarray(base_act, float), np.asarray(base_pre, float); bv = ~np.isnan(ba) & ~np.isnan(bp)
        p0 = float((ba[bv] < bp[bv]).mean()); o["other_days"] = int(bv.sum()); o["other_worse_pct"] = round(p0 * 100, 1)
        o["p_vs_other"] = round(float(binomtest(int(worse.sum()), len(act), p0).pvalue), 4)
    return o


def scope_series(P, cols):
    """날마다 (실제 달러, 예상 달러) — 그날 값이 있는 종목만."""
    c = np.array(cols); a = A[:, c]; p = P[:, c]; ok = ~np.isnan(a) & ~np.isnan(p)
    u = USD[c][None, :]
    act = np.where(ok, a * u, 0).sum(axis=1); pre = np.where(ok, p * u, 0).sum(axis=1)
    none = ok.sum(axis=1) == 0
    return np.where(none, np.nan, act), np.where(none, np.nan, pre), ok.sum(axis=1)


def analyse(W):
    P = run(W)
    days_ok = ~np.isnan(P["M1"]).all(axis=1)
    out = {"W": W, "eval_from": str(IDX[days_ok][0].date()), "eval_to": str(IDX[days_ok][-1].date()), "eval_days": int(days_ok.sum()),
           "m4_from": str(IDX[~np.isnan(P["M4"]).all(axis=1)][0].date()) if (~np.isnan(P["M4"]).all(axis=1)).any() else None}
    crit = {"mkt": np.array([d in MKT for d in IDX]) & days_ok, "chip": np.array([d in CHIP for d in IDX]) & days_ok}
    out["crit_days"] = {k: [str(d.date()) for d in IDX[v]] for k, v in crit.items()}
    allc = list(range(len(T)))
    scopes = {"전체 공개 보유(638종목 중 값 있는 종목)": allc}
    for bid, name, mem, lead in BUN:
        scopes[f"묶음{bid} {name}"] = [col[t] for t in mem if t in col]
    ai_mem = BUN[0][2]
    scopes["AI 인프라 묶음 중 전력 쪽 19종목"] = [col[t] for t in POWERS if t in col]
    scopes["AI 인프라 묶음 중 칩 뺀 종목"] = [col[t] for t in ai_mem if t in col and t not in CHIPS]
    scopes["AI 인프라 묶음 중 칩 9종목"] = [col[t] for t in CHIPS if t in col]
    res = {}
    for cname, cm in crit.items():
        res[cname] = {}
        for mname in MODELS:
            mday = cm & ~np.isnan(P[mname]).all(axis=1); oth = days_ok & ~cm & ~np.isnan(P[mname]).all(axis=1)
            rr = {}
            for sname, cols in scopes.items():
                act, pre, nst = scope_series(P[mname], cols)
                rr[sname] = stats(act[mday], pre[mday], act[oth], pre[oth])
                if sname.startswith("전체"):
                    rr[sname]["stocks_median"] = int(np.median(nst[mday])) if mday.any() else None
                    rr[sname]["usd_e8_median"] = round(float(np.median([USD[np.array(cols)][~np.isnan(A[i]) & ~np.isnan(P[mname][i])].sum() for i in np.where(mday)[0]]) / 1e8), 1) if mday.any() else None
                    rr[sname]["per_day"] = [{"date": str(IDX[i].date()), "spy_pct": round(SPY[i] * 100, 2), "actual_e8": round(act[i] / 1e8, 2), "pred_e8": round(pre[i] / 1e8, 2)} for i in np.where(mday)[0]]
            # 26묶음 요약
            bm = [rr[f"묶음{b[0]} {b[1]}"] for b in BUN]
            bm = [x for x in bm if x.get("ratio_median") is not None and x["ratio_days"] >= 3]
            pooled_w = sum(x["worse_days"] for x in bm); pooled_n = sum(x["days"] for x in bm)
            rr["_26묶음 요약"] = {"bundles_counted": len(bm), "bundles_ratio_median_over1": sum(x["ratio_median"] > 1 for x in bm),
                              "median_of_bundle_medians": round(float(np.median([x["ratio_median"] for x in bm])), 2) if bm else None,
                              "bundle_days": pooled_n, "bundle_days_worse": pooled_w, "bundle_days_worse_pct": round(pooled_w / pooled_n * 100, 1) if pooled_n else None,
                              "gap_sum_e8": round(sum(x["gap_sum_e8"] for x in bm), 2)}
            res[cname][mname] = rr
    # own: 앞 판 충격일(묶음 자기 등락 하위 5%)을 같은 모형으로 다시 — 고르는 방식 효과를 직접 견줌
    own = {}
    pos = {d: i for i, d in enumerate(IDX)}
    for mname in MODELS:
        rows = []; per_b = []
        for b in OLD["bundles"]:
            cols = [col[t] for t in b["members"] if t in col]
            act, pre, _ = scope_series(P[mname], cols)
            ii = [pos[pd.Timestamp(d["date"])] for d in b["shock"]["days"]]
            ii = [i for i in ii if not np.isnan(pre[i])]
            oth = [i for i in range(len(IDX)) if not np.isnan(pre[i]) and i not in set(ii)]
            s = stats(act[ii], pre[ii], act[oth], pre[oth]); s["id"] = b["id"]; per_b.append(s)
            rows += [(act[i], pre[i]) for i in ii]
        a_, p_ = np.array([r[0] for r in rows]), np.array([r[1] for r in rows])
        bm = [x for x in per_b if x.get("ratio_median") is not None and x["ratio_days"] >= 3]
        own[mname] = {"pooled": stats(a_, p_), "bundles_counted": len(bm), "bundles_ratio_median_over1": sum(x["ratio_median"] > 1 for x in bm),
                      "median_of_bundle_medians": round(float(np.median([x["ratio_median"] for x in bm])), 2) if bm else None,
                      "ai_infra": next(x for x in per_b if x["id"] == 0)}
    out["external"] = res; out["own_criterion"] = own
    return out, P


def regime_26(P2):
    """(라) 26묶음: 국면 = 앞 · 뒤 단계 잔차(그날 앞 베타)의 직전 60거래일 상관(전날까지). 높낮이 = 그 묶음의 전날까지 국면 값 중간값.
    결과 = 충격일에 실제 손실이 M2 예상보다 컸나. 충격일 = (a) 앞 판 자기 기준 549번 (b) 시장 급락일."""
    rng = np.random.default_rng(7); out = {}
    pos = {d: i for i, d in enumerate(IDX)}
    rows = {"own": [], "mkt": []}
    for b in OLD["bundles"]:
        lead, rest = b["split"]["lead"], b["split"]["rest"]
        link = BD.bmean(BD.RC, lead).rolling(60, min_periods=50).corr(BD.bmean(BD.RC, rest)).shift(1)   # 전날까지
        med = link.expanding(min_periods=30).median().shift(1)                                           # 전날까지 값의 중간값
        cols = [col[t] for t in b["members"] if t in col]
        act, pre, _ = scope_series(P2, cols)
        for key, dd in (("own", [pd.Timestamp(d["date"]) for d in b["shock"]["days"]]), ("mkt", sorted(MKT))):
            for d in dd:
                i = pos[d]
                if np.isnan(pre[i]) or pd.isna(link[d]) or pd.isna(med[d]):
                    continue
                rows[key].append((b["id"], str(d.date()), bool(link[d] < med[d]), bool(act[i] < pre[i]), (pre[i] - act[i]) / 1e8))
    for key, rr in rows.items():
        low = np.array([r[2] for r in rr]); w = np.array([r[3] for r in rr]); g = np.array([r[4] for r in rr])
        if len(rr) == 0 or low.sum() == 0 or (~low).sum() == 0:
            out[key] = {"n": len(rr)}; continue
        diff = w[low].mean() - w[~low].mean(); gd = g[low].mean() - g[~low].mean()
        perm = np.array([(lambda s: (w[s].mean() - w[~s].mean(), g[s].mean() - g[~s].mean()))(rng.permutation(low)) for _ in range(5000)])
        out[key] = {"n": len(rr), "low_n": int(low.sum()), "low_worse_pct": round(float(w[low].mean() * 100), 1),
                    "high_n": int((~low).sum()), "high_worse_pct": round(float(w[~low].mean() * 100), 1),
                    "diff_pt": round(float(diff * 100), 1), "perm_p_two_sided": round(float((np.abs(perm[:, 0]) >= abs(diff) - 1e-12).mean()), 4),
                    "low_gap_mean_e8": round(float(g[low].mean()), 3), "high_gap_mean_e8": round(float(g[~low].mean()), 3),
                    "gap_perm_p_two_sided": round(float((np.abs(perm[:, 1]) >= abs(gd) - 1e-12).mean()), 4),
                    "note": "같은 날 여러 묶음이 함께 들어가 서로 독립이 아니다 — p 값은 낙관적일 수 있다"}
    return out


if __name__ == "__main__":
    final = {"inputs": {"prices": (NET / "returns.csv.gz").as_posix(), "holdings": (NET / "net_result.json").as_posix(), "old_result": (NET / "bundles/result.json").as_posix(),
                        "prices_long": (NET / "backtest/returns_long.csv.gz").as_posix()},
             "n_stocks": len(T), "usd_total_e8": round(float(USD.sum() / 1e8), 1), "sectors": SECT,
             "mkt_days_all": sorted(str(d.date()) for d in MKT), "chip_days_in_panel": sorted(str(d.date()) for d in CHIP)}
    for W in (250, 120):
        o, P = analyse(W)
        o["regime_26"] = regime_26(P["M2"])
        final[f"W{W}"] = o
    (HERE / "short_panel.json").write_text(json.dumps(final, ensure_ascii=False, indent=1), encoding="utf-8")
    for W in (250, 120):
        o = final[f"W{W}"]; print("==== W", W, o["eval_from"], o["eval_to"], o["eval_days"], "M4 from", o["m4_from"], {k: len(v) for k, v in o["crit_days"].items()})
        for c in ("mkt", "chip"):
            for mname in MODELS:
                t = {k: v for k, v in o["external"][c][mname]["전체 공개 보유(638종목 중 값 있는 종목)"].items() if k != "per_day"}
                print(c, mname, "전체", t); print("   26묶음", o["external"][c][mname]["_26묶음 요약"])
                print("   AI", o["external"][c][mname]["묶음0 AI 데이터센터 인프라"]); print("   전력", o["external"][c][mname]["AI 인프라 묶음 중 전력 쪽 19종목"]); print("   칩뺀", o["external"][c][mname]["AI 인프라 묶음 중 칩 뺀 종목"])
        for mname in MODELS:
            print("own", mname, o["own_criterion"][mname])
        print("regime26", o["regime_26"])
