# -*- coding: utf-8 -*-
"""칩 밖 단계별 — 칩 충격일 재현 손익을 시장 · 자기 업종 펀드 · 반도체 펀드로 헤지했을 때 남는 몫.
읽는 것(읽기만): $CHAINSHIFT_DATA/net/backtest/returns_long.csv.gz (58종목+SPY 2021-01-04~2026-11-10)
  kic_precheck/data/chain.json (단계 · 2026-06-30 공개 보유 금액) · kic_precheck/regime_monitor.py (칩 충격 날 규칙 — long_panel.py 와 같은 호출)
  net/net_result.json (종목 업종) · 자기 폴더 etf_long_ret.csv (fetch_etf.py 가 야후에서 받은 펀드 수정 종가)
쓰는 것: hedge.json   실행: python -X utf8 hedge.py
방법: 날 i 마다, 그날 앞 250거래일 값이 다 있는 종목만으로 단계 손익(보유 금액 × 등락)을 만들고 그 250일을 헤지 수단 등락에 회귀(절편 포함)
  → 남는 손익 = 그날 손익 − 기울기 × 그날 수단 등락. 자기 업종 펀드 = 종목 업종별 펀드 등락의 금액 가중 평균 하나.
  규칙으로 고르기 = 그 250일 회귀에서 남은 변동(잔차 제곱합)이 가장 작았던 수단 하나(시장 · 자기 업종 · 반도체 중)를 그날 씀."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd

HERE = Path(__file__).resolve().parent
import os
KIC = Path(os.environ.get("CHAINSHIFT_DATA", "data") + "")
sys.path.insert(0, (KIC / "mcp_kic_precheck").as_posix())
from kic_precheck import regime_monitor as RM  # noqa: E402

W = 250
CH = json.loads((KIC / "mcp_kic_precheck/kic_precheck/data/chain.json").read_text(encoding="utf-8"))
ND = json.loads((KIC / "net/net_result.json").read_text(encoding="utf-8"))["nodes"]
SEC = {(n.get("id") or n.get("t") or n.get("ticker")): n["sector"] for n in ND} if isinstance(ND, list) else {k: v["sector"] for k, v in ND.items()}
SEC_ETF = {"정보기술": "XLK", "산업재": "XLI", "유틸리티": "XLU", "에너지": "XLE", "소재": "XLB"}
CHIPS = CH["stages"][0]["tick"]; POWERS = [t for s in CH["stages"] if s["name"] in CH["power_stages"] for t in s["tick"]]
HOLD = CH["holdings_usd"]
PX = (1 + pd.read_csv(KIC / "net/backtest/returns_long.csv.gz", index_col=0, parse_dates=True, float_precision="round_trip")).cumprod().mul(100)
R = PX.pct_change(fill_method=None).iloc[1:]; IDX = R.index
E = (1 + pd.read_csv(os.environ.get("CHAINSHIFT_ETF") or HERE / "etf_long_ret.csv", index_col=0, parse_dates=True, float_precision="round_trip")).cumprod().mul(100).pct_change().reindex(IDX)
assert float((E["SPY"] - R["SPY"]).abs().max()) < 2e-3, "두 주가 파일의 SPY 가 다름"
H = RM.monitor_history(PX[CHIPS + POWERS + ["SPY"]], CHIPS, POWERS, RM.MonitorConfig(hysteresis=0.03)).reindex(IDX)
SHOCK = ((H["eligible"] == True) & (H["chip_shock"] == True)).to_numpy()  # noqa: E712
OKD = np.arange(len(IDX)) >= W
SHORT = np.asarray((IDX >= "2025-10-02") & (IDX <= "2026-10-29"))
assert (SHOCK & OKD).sum() == 97 and (SHOCK & SHORT).sum() == 46 and (~SHOCK & SHORT).sum() == 225, ((SHOCK & OKD).sum(), (SHOCK & SHORT).sum(), (~SHOCK & SHORT).sum())

T = [t for t in HOLD if t in PX and t not in CHIPS]
assert len(T) == 49 and all(SEC[t] in SEC_ETF for t in T)
SCOPES = {s["name"]: s["tick"] for s in CH["stages"][1:]}
SCOPES["전력 쪽 19종목 합"] = POWERS; SCOPES["칩 밖 49종목 합"] = T
HEDGES = {"SPY": ["SPY"], "OWN": ["OWN"], "SMH": ["SMH"], "SPY+SMH": ["SPY", "SMH"], "OWN+SMH": ["OWN", "SMH"]}
PICK = ("SPY", "OWN", "SMH")


def fit(X, y, x):
    """X(W×k) y(W) → (그날 헤지 손익 예상, 창 안 잔차 제곱합)."""
    A = np.column_stack([np.ones(len(X)), X]); b, *_ = np.linalg.lstsq(A, y, rcond=None)
    return float(x @ b[1:]), float(((y - A @ b) ** 2).sum())


assert abs(fit(np.arange(5.)[:, None], 2 * np.arange(5.) + 1, np.array([3.]))[0] - 6) < 1e-9   # 자기 검사


def run(ticks):
    tk = [t for t in ticks if t in PX]; a = R[tk].to_numpy(float); u = np.array([HOLD[t] for t in tk])
    etf = E[[SEC_ETF[SEC[t]] for t in tk]].to_numpy(float)
    n = len(IDX); act = np.full(n, np.nan); res = {k: np.full(n, np.nan) for k in list(HEDGES) + ["RULE"]}; pick = np.full(n, "", dtype=object); nst = np.zeros(n, int)
    for i in range(W, n):
        w = slice(i - W, i + 1); ok = ~np.isnan(a[w]).any(axis=0)
        if not ok.any():
            continue
        y = a[w][:, ok] @ u[ok]; own = etf[w][:, ok] @ (u[ok] / u[ok].sum())
        F = {"SPY": E["SPY"].to_numpy()[w], "SMH": E["SMH"].to_numpy()[w], "OWN": own}
        act[i] = y[-1]; nst[i] = ok.sum(); sse = {}
        for k, cols in HEDGES.items():
            X = np.column_stack([F[c] for c in cols]); h, s = fit(X[:-1], y[:-1], X[-1]); res[k][i] = y[-1] - h; sse[k] = s
        pick[i] = min(PICK, key=lambda k: sse[k]); res["RULE"][i] = res[pick[i]][i]
    return act, res, pick, nst, float(u.sum())


def stat(act, r, m):
    a, x = act[m], r[m]; v = ~np.isnan(a) & ~np.isnan(x); a, x = a[v], x[v]
    if len(a) == 0:
        return None
    return {"days": int(len(a)), "act_sum_e8": round(a.sum() / 1e8, 2), "left_sum_e8": round(x.sum() / 1e8, 2),
            "left_pct_of_sum": round(x.sum() / a.sum() * 100, 1) if a.sum() < 0 else None,
            "abs_left_pct": round(np.abs(x).sum() / np.abs(a).sum() * 100, 1),          # 날마다 남는 크기 합 / 날마다 손익 크기 합
            "rms_left_pct": round(float(np.sqrt((x ** 2).mean() / (a ** 2).mean()) * 100), 1),
            "abs_left_median_e8": round(float(np.median(np.abs(x))) / 1e8, 3), "act_abs_median_e8": round(float(np.median(np.abs(a))) / 1e8, 3),
            "act_loss_days": int((a < 0).sum()), "still_loss_days": int((x < 0).sum()), "worst_left_e8": round(float(x.min()) / 1e8, 2)}


out = {"inputs": {"prices_long": (KIC / "net/backtest/returns_long.csv.gz").as_posix(), "chain": (KIC / "mcp_kic_precheck/kic_precheck/data/chain.json").as_posix(),
                  "sector": (KIC / "net/net_result.json").as_posix(), "etf": "analysis/A3_hedge/etf_long_ret.csv"}, "W": W,
       "days": {"shock46": int((SHOCK & SHORT).sum()), "other225": int((~SHOCK & SHORT).sum()), "shock97": int((SHOCK & OKD).sum())}, "scopes": {}}
MASKS = {"shock46": SHOCK & SHORT, "other225": ~SHOCK & SHORT, "shock97": SHOCK & OKD, "other_all": ~SHOCK & OKD}
for y in range(2022, 2027):
    MASKS[f"shock_{y}"] = SHOCK & OKD & (IDX.year == y); MASKS[f"other_{y}"] = ~SHOCK & OKD & (IDX.year == y)
for name, ticks in SCOPES.items():
    act, res, pick, nst, usd = run(ticks)
    tk = [t for t in ticks if t in PX]; ws = {}
    for t in tk: ws[SEC_ETF[SEC[t]]] = ws.get(SEC_ETF[SEC[t]], 0) + HOLD[t]
    o = {"n": len(tk), "usd_e8": round(usd / 1e8, 2), "own_fund_weights_pct": {k: round(v / usd * 100, 1) for k, v in ws.items()},
         "stocks_in_46_min_max": [int(nst[MASKS["shock46"]].min()), int(nst[MASKS["shock46"]].max())], "by": {}}
    for mn, m in MASKS.items():
        o["by"][mn] = {k: stat(act, res[k], m) for k in res}
        o["by"][mn]["pick_counts"] = {k: int((pick[m] == k).sum()) for k in PICK}
    out["scopes"][name] = o
(HERE / "hedge.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

L = {"SPY": "시장", "OWN": "자기업종", "SMH": "반도체", "SPY+SMH": "시장+반도체", "OWN+SMH": "자기업종+반도체", "RULE": "규칙"}
for mn in MASKS:
    print(f"\n==== {mn}")
    for name, o in out["scopes"].items():
        b = o["by"][mn]
        if b["SPY"] is None: continue
        print(f"{name} n={o['n']} {o['usd_e8']}억 | 날 {b['SPY']['days']} 손실일 {b['SPY']['act_loss_days']} 합 {b['SPY']['act_sum_e8']} 중간|손익| {b['SPY']['act_abs_median_e8']} | 고름 {b['pick_counts']}")
        for k in L:
            s = b[k]; print(f"   {L[k]:10s} 합기준 {s['left_pct_of_sum']}%  크기기준 {s['abs_left_pct']}%  rms {s['rms_left_pct']}%  중간|남음| {s['abs_left_median_e8']}  여전히손실 {s['still_loss_days']}  최악 {s['worst_left_e8']}")
