# -*- coding: utf-8 -*-
"""A2_problem — 문제 정의 감점 여섯 가지를 같은 자료 · 같은 정의 위에서 더 잰다. 규칙은 prereg.md(돌리기 전에 씀).
읽는 것(읽기만, 망 · 유료 AI 안 씀): ../A_problem/short_panel.py · long_panel.py 가 읽는 파일 그대로
  $CHAINSHIFT_DATA/net/returns.csv.gz · net_result.json · bundles/ · backtest/returns_long.csv.gz
  $CHAINSHIFT_DATA/mcp_kic_precheck/kic_precheck/regime_monitor.py · data/chain.json
  $CHAINSHIFT_DATA/net/universe.json (13F 전체 금액)
  이 폴더 tried.json(지금까지 본 가설 목록) · causes.json(B_agent 판정 기록에서 옮긴 날짜별 까닭)
쓰는 것: a2.json · a2.log(표준 출력). 쓰는 법: python -X utf8 a2.py > a2.log
"""
import json, sys, warnings
from pathlib import Path

sys.dont_write_bytecode = True            # A_problem 은 읽기만 — __pycache__ 도 안 건드림
import numpy as np
import pandas as pd
from scipy.stats import binomtest, fisher_exact

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "A_problem"))
import short_panel as SP  # noqa: E402  638종목 · 2024-10~2026-10-29
import long_panel as LP   # noqa: E402  58종목 · 2021-01~2026-11-10

warnings.filterwarnings("ignore", category=RuntimeWarning)
A, SPY, SF, IDX, T, col, USD, ND = SP.A, SP.SPY, SP.SF, SP.IDX, SP.T, SP.col, SP.USD, SP.ND
CHIPS, POWERS, RM = SP.CHIPS, SP.POWERS, SP.RM
AI58 = [t for t in SP.BUN[0][2] if t in col]
NONCHIP = [t for t in AI58 if t not in CHIPS]
assert len(AI58) == 58 and len(NONCHIP) == 49 and set(AI58) == set(LP.T), "58종목 정의가 두 파일에서 다름"
SYN = {**SP.BD.SUB_SYN, "Semiconductor Equipment & Materials": "Semiconductor Materials & Equipment",
       "Computer Hardware": "Technology Hardware, Storage & Peripherals", "Communication Equipment": "Communications Equipment"}
SUB = {t: SYN.get(ND[t]["sub"], ND[t]["sub"]) for t in T}
TRIED = {k: v for k, v in json.loads((HERE / "tried.json").read_text(encoding="utf-8")).items() if k != "_note"}
CAUSE = {k: v for k, v in json.loads((HERE / "causes.json").read_text(encoding="utf-8")).items() if k != "_note"}
e8 = lambda v: round(float(v) / 1e8, 2)  # noqa: E731
OUT = {}


def st(act, pre, m, oth):
    """m = 충격일, oth = 견줄 다른 날. 차이 = 예상 − 실제(양수면 예상이 손실을 작게 봄)."""
    v = ~np.isnan(act) & ~np.isnan(pre); m = m & v; oth = oth & v
    if m.sum() == 0:
        return {"days": 0}
    w = act[m] < pre[m]; ow = act[oth] < pre[oth]; gap = pre[m] - act[m]
    o = {"days": int(m.sum()), "worse": int(w.sum()), "worse_pct": round(w.mean() * 100, 1), "other_days": int(oth.sum()),
         "other_worse": int(ow.sum()), "other_worse_pct": round(ow.mean() * 100, 1) if oth.sum() else None,
         "sum_actual_e8": e8(act[m].sum()), "sum_pred_e8": e8(pre[m].sum()),
         "sum_ratio": round(float(act[m].sum() / pre[m].sum()), 2) if pre[m].sum() < 0 else None,
         "gap_sum_e8": e8(gap.sum()), "gap_median_e8": round(float(np.median(gap)) / 1e8, 3)}
    if oth.sum():
        o["p_binom"] = float(binomtest(int(w.sum()), int(m.sum()), float(ow.mean())).pvalue)
        o["p_fisher"] = float(fisher_exact([[int(w.sum()), int((~w).sum())], [int(ow.sum()), int((~ow).sum())]])[1])
    return o


def show(tag, d):
    print(tag, json.dumps({k: (f"{v:.2g}" if k.startswith("p_") else v) for k, v in d.items()}, ensure_ascii=False))


def cols_of(ticks):
    return [col[t] for t in ticks if t in col]


def fine(W, ticks, outside_only=False, add_semi=False):
    """종목마다: 시장 + 업종 11 + 자기 세부 업종 평균(자기 제외) [+ 반도체 세부 업종 평균]. 직전 W거래일만으로 맞춤.
    outside_only=True 면 동종을 AI 인프라 58종목 밖에서만 잡는다."""
    n = len(IDX); P = np.full((n, len(T)), np.nan); info = {}
    semi = np.nanmean(A[:, [col[t] for t in T if SUB[t] == "Semiconductors"]], axis=1)
    for t in ticks:
        j = col[t]
        peers = [u for u in T if u != t and SUB[u] == SUB[t] and (u not in AI58 or not outside_only)]
        use = len(peers) >= 2
        info[t] = {"sub": SUB[t], "peers": len(peers), "peers_in_ai58": sum(u in AI58 for u in peers), "sub_factor_used": use}
        X = np.column_stack([SPY, SF] + ([np.nanmean(A[:, cols_of(peers)], axis=1)] if use else []) + ([semi] if add_semi else []))
        for i in range(W, n):
            if np.isnan(A[i - W:i + 1, j]).any() or np.isnan(X[i - W:i + 1]).any():
                continue
            B = np.linalg.lstsq(np.column_stack([np.ones(W), X[i - W:i]]), A[i - W:i, j], rcond=None)[0]
            P[i, j] = X[i] @ B[1:]
    return P, info


def scope(P, ticks):
    a, p, _ = SP.scope_series(P, cols_of(ticks)); return a, p


# ============ 1. 세부 업종 요인 (W250, 칩 충격 46일, 칩 밖 49종목) ============
print("==== 1. 세부 업종 요인")
P250 = SP.run(250)
ok250 = ~np.isnan(P250["M1"]).all(axis=1)
chip = np.array([d in SP.CHIP for d in IDX]) & ok250
oth = ok250 & ~chip
assert chip.sum() == 46, chip.sum()
a3, p3 = scope(P250["M3"], NONCHIP)
base = st(a3, p3, chip, oth); show("M3 다시(기준, A_problem 과 같아야 함)", base)
assert base["worse"] == 32 and abs(base["gap_sum_e8"] - 15.3) < 0.06, base   # 자기 검사: 앞 계산 32/46 · 15.3억 달러 재현
res1 = {"M3": base}; FP = {}; LAB = {"M3": "시장+업종 11 (앞 계산 재현)", "F1": "+자기 세부 업종(보유 안 동종, 자기 제외)", "F2": "+자기 세부 업종(58종목 밖 동종만)",
                                    "F3": "F1+반도체 세부 업종 평균", "F4": "F2+반도체 세부 업종 평균", "M5": "업종 11+칩 9종목 등락(앞 계산)"}
for name, kw in (("F1", {}), ("F2", {"outside_only": True}), ("F3", {"add_semi": True}), ("F4", {"outside_only": True, "add_semi": True})):
    P, info = fine(250, NONCHIP, **kw); FP[name] = P
    a, p = scope(P, NONCHIP); res1[name] = st(a, p, chip, oth); show(name + " " + LAB[name], res1[name])
    ap, pp = scope(P, POWERS); res1[name + "_power19"] = st(ap, pp, chip, oth); show("   전력 쪽 19", res1[name + "_power19"])
    if name in ("F1", "F2"):
        res1[name + "_peers"] = info
        usd_used = sum(ND[t]["usd"] for t, v in info.items() if v["sub_factor_used"]) / sum(ND[t]["usd"] for t in NONCHIP) * 100
        res1[name + "_coverage"] = {"stocks_with_sub_factor": sum(v["sub_factor_used"] for v in info.values()),
                                    "stocks_all_peers_inside_ai58": sum(v["sub_factor_used"] and v["peers"] == v["peers_in_ai58"] for v in info.values()),
                                    "stocks_majority_peers_inside_ai58": sum(v["sub_factor_used"] and v["peers_in_ai58"] * 2 > v["peers"] for v in info.values()),
                                    "usd_pct_with_sub_factor": round(usd_used, 1)}
        print("   ", res1[name + "_coverage"])
res1["M5"] = st(*scope(P250["M5"], NONCHIP), chip, oth); show("M5", res1["M5"])
OUT["labels"] = LAB; OUT["1_fine_industry"] = res1
OUT["usd_e8"] = {"nonchip49": e8(sum(ND[t]["usd"] for t in NONCHIP)), "ai58": e8(sum(ND[t]["usd"] for t in AI58)), "power19": e8(sum(ND[t]["usd"] for t in POWERS)),
                 "priced638": e8(USD.sum()), "all13f_677rows": e8(json.loads((SP.NET / "universe.json").read_text(encoding="utf-8"))["total_usd"])}
print("보유 금액(억 달러)", OUT["usd_e8"])

# ============ 2. 탐색 횟수 보정 + 표본 밖 ============
print("==== 2. 보정 · 표본 밖")
n_before = sum(len(v) for k, v in TRIED.items() if not k.startswith("A2")); n_all = sum(len(v) for v in TRIED.values())
bon = lambda p, n: min(1.0, p * n)  # noqa: E731
OUT["2_multiple"] = {"n_before_A2": n_before, "n_with_A2": n_all, "by_group": {k: len(v) for k, v in TRIED.items()}}
for k in ("M3", "F1", "F2", "F3", "F4", "M5"):
    OUT["2_multiple"][k] = {"p_binom": res1[k]["p_binom"], "p_fisher": res1[k]["p_fisher"], "bonf_binom_before": bon(res1[k]["p_binom"], n_before), "bonf_binom_all": bon(res1[k]["p_binom"], n_all),
                            "bonf_fisher_before": bon(res1[k]["p_fisher"], n_before), "bonf_fisher_all": bon(res1[k]["p_fisher"], n_all)}
print(json.dumps(OUT["2_multiple"], ensure_ascii=False))

# 표본 밖 (가): 업종 모형을 낼 수 있는 유일한 바깥 구간 — 직전 120거래일, 2025-03-27~2025-10-01
P120 = SP.run(120); ok120 = ~np.isnan(P120["M1"]).all(axis=1)
pre_win = ok120 & (IDX < IDX[ok250][0]); chip120 = np.array([d in SP.CHIP for d in IDX])
oos = {"window": [str(IDX[pre_win][0].date()), str(IDX[pre_win][-1].date())], "shock_dates": [str(d.date()) for d in IDX[pre_win & chip120]]}
F120, _ = fine(120, NONCHIP); F120b, _ = fine(120, NONCHIP, outside_only=True)
for k, P in (("M3", P120["M3"]), ("F1", F120), ("F2", F120b), ("M5", P120["M5"]), ("M1", P120["M1"])):
    a, p = scope(P, NONCHIP); oos[k] = st(a, p, pre_win & chip120, pre_win & ~chip120); show("표본 밖(가) W120 " + k, oos[k])
print("표본 밖(가) 구간", oos["window"], oos["shock_dates"])
# 표본 밖 (나): 긴 주가 58종목 — 「시장 + 칩 등락」(L2) · 「시장 하나」(L1). 업종 요인용 넓은 주가가 2024-10 앞에는 없다
LPp = LP.predict(250); LI = LP.IDX; okL = ~np.isnan(LPp["L2"]).all(axis=1); shock = LP.SHOCK.to_numpy() & okL
nonchipL = [t for t in LP.T if t not in CHIPS]
win0, win1 = IDX[ok250][0], IDX[ok250][-1]
per = {"before_2021-12~2025-10-01": LI < win0, "window_2025-10-02~2026-10-29": (LI >= win0) & (LI <= win1), "after_2026-10-30~11-10": LI > win1,
       "outside_both": (LI < win0) | (LI > win1), "all": np.ones(len(LI), bool)}
oosL = {}
for mn in ("L2", "L1"):
    aL, pL = LP.series(LPp[mn], nonchipL)
    for pk, pm in per.items():
        oosL[f"{mn} {pk}"] = st(aL, pL, shock & pm, okL & ~shock & pm); show("표본 밖(나) " + mn + " " + pk, oosL[f"{mn} {pk}"])
OUT["2_out_of_sample"] = {"short_W120": oos, "long_58": oosL}

# ============ 4. 해마다 · 관계가 생긴 때 ============
print("==== 4. 해마다")
aL, pL = LP.series(LPp["L2"], nonchipL); a1L, p1L = LP.series(LPp["L1"], nonchipL); apL, ppL = LP.series(LPp["L2"], POWERS)
yr = {}
for y in range(2022, 2027):
    ym = LI.year == y
    yr[str(y)] = {"nonchip49_L2": st(aL, pL, shock & ym, okL & ~shock & ym), "nonchip49_L1": st(a1L, p1L, shock & ym, okL & ~shock & ym),
                  "power19_L2": st(apL, ppL, shock & ym, okL & ~shock & ym)}
    for k, v in yr[str(y)].items():
        show(f"{y} {k}", v)
F = RM.causal_features(LP.PX[CHIPS + nonchipL + ["SPY"]], CHIPS, nonchipL, RM.MonitorConfig(hysteresis=0.03)).reindex(LI)
roll = F["chip_resid"].rolling(250, min_periods=200).corr(F["power_resid"]).shift(1)
ycorr = {str(y): round(float(F.loc[LI.year == y, "chip_resid"].corr(F.loc[LI.year == y, "power_resid"])), 2) for y in range(2021, 2027)}
onset = {}
for th in (0.2, 0.3, 0.4):
    hit = roll[roll >= th]
    if len(hit) == 0:
        onset[str(th)] = None; print("관계 생긴 때", th, "넘은 날 없음"); continue
    d0 = hit.index[0]; after = np.asarray(LI >= d0)
    onset[str(th)] = {"date": str(d0.date()), "before": st(aL, pL, shock & ~after, okL & ~shock & ~after), "after": st(aL, pL, shock & after, okL & ~shock & after)}
    print("관계 생긴 때", th, d0.date()); show("   앞", onset[str(th)]["before"]); show("   뒤", onset[str(th)]["after"])
qcorr = roll.dropna().resample("QE").last().round(2); qcorr = {str(k.date()): float(v) for k, v in qcorr.items()}
print("해마다 잔차 상관(칩 9 대 칩 밖 49)", ycorr); print("분기 말 직전 250일 상관", qcorr)
slope = {}
for y in range(2022, 2027):
    x = F.loc[LI.year == y, "chip_resid"]; yv = F.loc[LI.year == y, "power_resid"]; ok = x.notna() & yv.notna()
    dn = ok & (x < x[ok].quantile(0.10))
    slope[str(y)] = {"all_days": round(float(np.polyfit(x[ok], yv[ok], 1)[0]), 2), "chip_worst_decile_days": round(float(np.polyfit(x[dn], yv[dn], 1)[0]), 2),
                     "ratio_mean_on_worst_decile": round(float(yv[dn].mean() / x[dn].mean()), 2), "chip_resid_sd_pct": round(float(x[ok].std() * 100), 2)}
print("사후: 해마다 칩 밖 49 잔차의 칩 잔차에 대한 기울기", slope)
OUT["4_by_year"] = {"posthoc_slope_by_year": slope, "by_year": yr, "resid_corr_by_year": ycorr, "rolling250_corr_quarter_end": qcorr, "onset": onset}

# ============ 3. 칩에서 출발한 날 ============
print("==== 3. 대표 사례 후보")
chipf = SP.CHIPF; c49 = cols_of(NONCHIP)
apw, ppw = scope(P250["M3"], POWERS); aF1, pF1 = scope(FP["F1"], NONCHIP); aF2, pF2 = scope(FP["F2"], NONCHIP); a5, p5 = scope(P250["M5"], NONCHIP)
rows = []
for i in np.where(chip)[0]:
    d = str(IDX[i].date()); usd_i = float(np.where(~np.isnan(A[i, c49]) & ~np.isnan(P250["M3"][i, c49]), USD[c49], 0).sum())
    cz = CAUSE.get(d, ["판정 기록 없음", "기록 없음"])
    r = {"date": d, "spy_pct": round(SPY[i] * 100, 2), "chip9_pct": round(chipf[i] * 100, 2), "nonchip_pct": round(a3[i] / usd_i * 100, 2),
         "actual_e8": e8(a3[i]), "pred_M3_e8": e8(p3[i]), "gap_M3_e8": e8(p3[i] - a3[i]), "pred_F1_e8": e8(pF1[i]), "pred_F2_e8": e8(pF2[i]), "pred_M5_e8": e8(p5[i]), "power19_actual_e8": e8(apw[i]), "power19_pred_M3_e8": e8(ppw[i]),
         "cause": cz[0], "cause_line": cz[1]}
    r["flat_or_up"] = r["spy_pct"] >= -0.25; r["chip_fell_more"] = r["chip9_pct"] < 0 and r["chip9_pct"] < r["nonchip_pct"]; r["worse"] = r["gap_M3_e8"] > 0
    rows.append(r)
cand = sorted([r for r in rows if r["flat_or_up"] and r["chip_fell_more"] and r["worse"]], key=lambda r: -r["gap_M3_e8"])
print("46일 중 시장 평탄·상승", sum(r["flat_or_up"] for r in rows), "| 그중 칩이 더 빠짐", sum(r["flat_or_up"] and r["chip_fell_more"] for r in rows), "| 그중 예상보다 나쁨", len(cand),
      "| 그중 칩 고유 기록", sum(r["cause"] == "칩 고유" for r in cand), "| 기록 없음", sum(r["cause"] == "판정 기록 없음" for r in cand))
line = lambda r: (r["date"], r["spy_pct"], r["chip9_pct"], r["nonchip_pct"], "실제", r["actual_e8"], "M3", r["pred_M3_e8"], "차이", r["gap_M3_e8"], "F1", r["pred_F1_e8"],  # noqa: E731
                  "F2", r["pred_F2_e8"], "M5", r["pred_M5_e8"], "전력19", r["power19_actual_e8"], r["power19_pred_M3_e8"], r["cause"], "|", r["cause_line"])
for r in cand:
    print("  ", *line(r))
print("-- 칩 고유로 적힌 날 전부(조건과 무관)")
for r in rows:
    if r["cause"] == "칩 고유":
        print("  ", *line(r), "평탄", r["flat_or_up"], "칩이 더", r["chip_fell_more"])
# 46일 구간 밖의 칩 고유 날(2025-08-29 는 직전 120거래일 업종 모형, 2026-10-30 은 긴 주가 「시장+칩」만)
extra = []
i = IDX.get_loc(pd.Timestamp("2025-08-29")); a120, p120 = scope(P120["M3"], NONCHIP)
extra.append({"date": "2025-08-29", "model": "M3 W120", "spy_pct": round(float(SPY[i]) * 100, 2), "chip9_pct": round(float(chipf[i]) * 100, 2), "actual_e8": e8(a120[i]), "pred_e8": e8(p120[i]), "chip_rule": bool(chip120[i])})
for d in ("2025-08-29", "2026-10-30"):
    i = LI.get_loc(pd.Timestamp(d))
    extra.append({"date": d, "model": "L2 W250", "spy_pct": round(float(LP.SPY[i]) * 100, 2), "chip9_pct": round(float(LP.CHIPF[i]) * 100, 2), "actual_e8": e8(aL[i]), "pred_e8": e8(pL[i]), "pred_market_only_e8": e8(p1L[i]), "chip_rule": bool(shock[i])})
for r in extra:
    print("   구간 밖", r)
OUT["3_cases"] = {"all_46": rows, "candidates_sorted": cand, "outside_window_chip_specific": extra}

# ============ 6. 크기 잣대 ============
print("==== 6. 크기")
gap = (p3 - a3)[chip]; order = np.argsort(-gap); dts = IDX[chip]; u = OUT["usd_e8"]
top5 = [{"date": str(dts[k].date()), "gap_e8": e8(gap[k]), "actual_e8": e8(a3[chip][k]), "pred_e8": e8(p3[chip][k])} for k in order[:5]]
g8 = gap / 1e8
OUT["6_scale"] = {"gap_sum_e8": round(float(g8.sum()), 2), "gap_mean_e8": round(float(g8.mean()), 3), "gap_median_e8": round(float(np.median(g8)), 3),
                  "gap_median_of_worse_days_e8": round(float(np.median(g8[g8 > 0])), 3), "top5": top5, "top5_sum_e8": round(float(g8[order[:5]].sum()), 2),
                  "top5_share_of_sum_pct": round(float(g8[order[:5]].sum() / g8.sum() * 100), 1),
                  "worst_day_pct_of_nonchip49": round(float(g8[order[0]] / u["nonchip49"] * 100), 2), "median_day_pct_of_nonchip49": round(float(np.median(g8) / u["nonchip49"] * 100), 2),
                  "mean_day_pct_of_nonchip49": round(float(g8.mean() / u["nonchip49"] * 100), 2), "sum_pct_of_nonchip49": round(float(g8.sum() / u["nonchip49"] * 100), 1),
                  "sum_pct_of_ai58": round(float(g8.sum() / u["ai58"] * 100), 1), "sum_pct_of_priced638": round(float(g8.sum() / u["priced638"] * 100), 2),
                  "sum_pct_of_all13f": round(float(g8.sum() / u["all13f_677rows"] * 100), 2), "mean_day_pct_of_priced638": round(float(g8.mean() / u["priced638"] * 100), 3),
                  "worst_day_pct_of_priced638": round(float(g8[order[0]] / u["priced638"] * 100), 3), "window_trading_days": int(ok250.sum())}
print(json.dumps(OUT["6_scale"], ensure_ascii=False))

# ============ 5. 다른 사슬 ============
print("==== 5. 다른 사슬")
PXS = SP.BD.PX
CHAINS = {"A_pharma_to_lifesci_tools": (["BMY", "JNJ", "LLY", "MRK", "PFE", "ZTS", "AZN"], ["A", "DHR", "ILMN", "IQV", "MTD", "TMO", "WAT"]),
          "B_oil_producers_to_services_refiners": (["CVE", "IMO", "SU", "TTE", "EXE", "COP", "DVN", "FANG", "EOG", "EQT", "OXY", "OVV", "TPL"], ["BKR", "HAL", "SLB", "FTI", "MPC", "PSX", "VLO"]),
          "C_chip_to_nonchip49_short_calibration": (CHIPS, NONCHIP)}
ch5 = {}
for name, (up, dn) in CHAINS.items():
    assert all(t in col for t in up + dn), [t for t in up + dn if t not in col]
    Hs = RM.monitor_history(PXS[up + dn + ["SPY"]], up, dn, RM.MonitorConfig(hysteresis=0.03)).reindex(IDX)
    sh = (Hs["eligible"] == True).to_numpy() & (Hs["chip_shock"] == True).to_numpy() & ok250  # noqa: E712
    upf = np.nanmean(A[:, cols_of(up)], axis=1)
    r = {"up_n": len(up), "down_n": len(dn), "up_usd_e8": e8(sum(ND[t]["usd"] for t in up)), "down_usd_e8": e8(sum(ND[t]["usd"] for t in dn)),
         "up_sectors": sorted({ND[t]["sector"] for t in up}), "down_sectors": sorted({ND[t]["sector"] for t in dn}),
         "shock_days": int(sh.sum()), "shock_dates": [str(d.date()) for d in IDX[sh]], "up_mean_pct_on_shock": round(float(upf[sh].mean() * 100), 2) if sh.any() else None,
         "overlap_with_long_calibration_46": int((sh & chip).sum())}
    for mn in ("M3", "M1"):
        a, p = scope(P250[mn], dn); r[mn] = st(a, p, sh, ok250 & ~sh)
    Pf, _ = fine(250, dn); a, p = scope(Pf, dn); r["F1"] = st(a, p, sh, ok250 & ~sh)
    ch5[name] = r
    print(name, {k: v for k, v in r.items() if not isinstance(v, dict) and k != "shock_dates"})
    for lab in ("M3", "M1", "F1"):
        show("   " + lab, r[lab])
OUT["5_other_chains"] = ch5

(HERE / "a2.json").write_text(json.dumps(OUT, ensure_ascii=False, indent=1, default=lambda o: o.item()), encoding="utf-8")
print("저장 a2.json")
