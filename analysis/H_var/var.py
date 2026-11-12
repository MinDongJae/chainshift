# -*- coding: utf-8 -*-
"""전력 쪽 19종목 장부의 VaR 사후 검증 — 날을 칩으로 고르지 않고 장부 자신의 초과일로 고른 뒤 「그날이 칩 충격일이었나」를 묻는다.
읽는 것(읽기만): $CHAINSHIFT_DATA/net/backtest/returns_long.csv.gz · mcp_kic_precheck/kic_precheck/data/chain.json
  · kic_precheck/regime_monitor.py(칩 충격일 규칙) · net/net_result.json(업종) · ../A3_hedge/etf_long_ret.csv(펀드 수정 종가)
쓰는 것: var.json   실행: python -X utf8 var.py
모든 예상은 그날 앞 250거래일만(hedge.py 와 같은 창 · 같은 종목 고르기 · 같은 자기 업종 펀드)."""
import json, math, sys
from pathlib import Path
import numpy as np, pandas as pd
from scipy.stats import chi2, hypergeom, fisher_exact

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
E = (1 + pd.read_csv(HERE.parent / "A3_hedge/etf_long_ret.csv", index_col=0, parse_dates=True, float_precision="round_trip")).cumprod().mul(100).pct_change().reindex(IDX)
H = RM.monitor_history(PX[CHIPS + POWERS + ["SPY"]], CHIPS, POWERS, RM.MonitorConfig(hysteresis=0.03)).reindex(IDX)
SHOCK = ((H["eligible"] == True) & (H["chip_shock"] == True)).to_numpy()  # noqa: E712
OKD = np.arange(len(IDX)) >= W
SHORT = np.asarray((IDX >= "2025-10-02") & (IDX <= "2026-10-29")); ALL = np.asarray(IDX >= "2023-01-01")
assert (SHOCK & OKD).sum() == 97 and (SHOCK & SHORT).sum() == 46 and SHORT.sum() == 271
spy = R["SPY"]; MKT = ((spy <= spy.rolling(250, min_periods=250).quantile(0.05).shift(1)) & (spy < 0)).to_numpy()  # 시장 하위 5% 날(견줌용)


def kupiec(n, x, p):
    """쿠피엑 초과율 검정: LR = −2·ln[(1−p)^(n−x)·p^x] + 2·ln[(1−x/n)^(n−x)·(x/n)^x] ~ χ²(1)."""
    ph = x / n; l0 = (n - x) * math.log(1 - p) + x * math.log(p)
    l1 = (n - x) * math.log(1 - ph) if x == 0 else (x * math.log(ph) if x == n else (n - x) * math.log(1 - ph) + x * math.log(ph))
    lr = -2 * (l0 - l1); return lr, float(chi2.sf(lr, 1))


assert kupiec(100, 5, 0.05)[0] < 1e-9 and kupiec(250, 25, 0.05)[1] < 0.01   # 자기 검사

tk = [t for t in POWERS if t in PX]; a = R[tk].to_numpy(float); u = np.array([HOLD[t] for t in tk])
etf = E[[SEC_ETF[SEC[t]] for t in tk]].to_numpy(float); SPYv = E["SPY"].to_numpy(); SMHv = E["SMH"].to_numpy()
n = len(IDX); nan = lambda: np.full(n, np.nan)  # noqa: E731
act = nan(); V = {k: nan() for k in ("hs95", "hs99", "f2_95", "f2_99", "f3_95", "f3_99", "n95", "own95", "own99", "os95", "os99")}
hed = {"own": nan(), "os": nan()}; rho = nan(); idcheck = 0.0


def ols(X, y):
    A = np.column_stack([np.ones(len(X)), X]); b = np.linalg.lstsq(A, y, rcond=None)[0]; return b, y - A @ b


for i in range(W, n):
    w = slice(i - W, i + 1); ok = ~np.isnan(a[w]).any(axis=0)
    if not ok.any():
        continue
    y = a[w][:, ok] @ u[ok]; own = etf[w][:, ok] @ (u[ok] / u[ok].sum()); F = {"SPY": SPYv[w], "SMH": SMHv[w], "OWN": own}
    if any(np.isnan(v).any() for v in F.values()):
        continue
    yh = y[:-1]; act[i] = y[-1]
    V["hs95"][i], V["hs99"][i] = np.quantile(yh, [0.05, 0.01])                    # (가) 과거 모의
    V["n95"][i] = yh.mean() - 1.645 * yh.std()                                     # 정규 가정 한도(참고)
    for name, cols in (("f2", ["SPY", "OWN"]), ("f3", ["SPY", "OWN", "SMH"])):     # (나)(다) 요인 모형: 요인 몫과 잔차를 서로 독립으로 두고 250×250 조합
        X = np.column_stack([F[c][:-1] for c in cols]); b, e = ols(X, yh); fit = yh - e
        idcheck = max(idcheck, abs(fit.var() + e.var() - yh.var()) / yh.var())
        V[name + "_95"][i], V[name + "_99"][i] = np.quantile((fit[:, None] + e[None, :]).ravel(), [0.05, 0.01])
    for name, cols in (("own", ["OWN"]), ("os", ["OWN", "SMH"])):                  # 헤지한 장부: 손익 − 기울기×펀드 등락
        X = np.column_stack([F[c] for c in cols]); b, _ = ols(X[:-1], yh); hh = y - X @ b[1:]
        hed[name][i] = hh[-1]; V[name + "95"][i], V[name + "99"][i] = np.quantile(hh[:-1], [0.05, 0.01])
    _, ey = ols(F["SPY"][-61:-1, None], y[-61:-1]); _, es = ols(F["SPY"][-61:-1, None], F["SMH"][-61:-1])
    rho[i] = np.corrcoef(ey, es)[0, 1]                                             # 사전 지표(prereg.md)
assert idcheck < 1e-9   # OLS 항등식: 요인 몫 분산 + 잔차 분산 = 장부 분산 → 정규 가정 요인 VaR 은 요인을 무엇으로 넣든 같다
rs = pd.Series(rho); HIGH = (rs >= rs.rolling(250, min_periods=250).median().shift(1)).to_numpy(); HAVE = rs.rolling(250, min_periods=250).median().shift(1).notna().to_numpy() & ~np.isnan(rho)


def st(exc, m, p):
    m = m & ~np.isnan(act); N = int(m.sum()); x = int((exc & m).sum()); K = int((SHOCK & m).sum()); k = int((exc & m & SHOCK).sum()); lr, pv = kupiec(N, x, p)
    return {"days": N, "expected": round(N * p, 1), "exceed": x, "rate_pct": round(x / N * 100, 2), "kupiec_LR": round(lr, 2), "kupiec_p": round(pv, 4),
            "shock_days_in_period": K, "shock_base_pct": round(K / N * 100, 1), "exceed_on_shock": k, "exceed_shock_pct": round(k / x * 100, 1) if x else None,
            "hypergeom_p": round(float(hypergeom.sf(k - 1, N, K, x)), 6) if x else None,
            "exceed_on_mkt5": int((exc & m & MKT).sum()), "mkt5_days": int((MKT & m).sum()), "exceed_on_shock_not_mkt5": int((exc & m & SHOCK & ~MKT).sum()),
            "shock_exceed_rate_pct": round(k / K * 100, 1) if K else None, "other_exceed_rate_pct": round((x - k) / (N - K) * 100, 1)}


EXC = {"가_과거모의95": (act < V["hs95"], .05), "가_과거모의99": (act < V["hs99"], .01), "나_요인(시장+자기업종)95": (act < V["f2_95"], .05), "나_요인(시장+자기업종)99": (act < V["f2_99"], .01),
       "다_요인(+반도체)95": (act < V["f3_95"], .05), "다_요인(+반도체)99": (act < V["f3_99"], .01), "참고_정규95": (act < V["n95"], .05),
       "헤지_자기업종95": (hed["own"] < V["own95"], .05), "헤지_자기업종99": (hed["own"] < V["own99"], .01),
       "헤지_자기업종+반도체95": (hed["os"] < V["os95"], .05), "헤지_자기업종+반도체99": (hed["os"] < V["os99"], .01),
       "헤지_자기업종+반도체_를_자기업종한도로95": (hed["os"] < V["own95"], .05)}
PER = {"13개월(2025-10-02~2026-10-29)": SHORT, "전체(2023-01~2026-11-10)": ALL}
for yv in (2023, 2024, 2025, 2026):
    PER[str(yv)] = ALL & (IDX.year == yv)
out = {"inputs": {"prices_long": (KIC / "net/backtest/returns_long.csv.gz").as_posix(), "chain": (KIC / "mcp_kic_precheck/kic_precheck/data/chain.json").as_posix(), "etf": "analysis/A3_hedge/etf_long_ret.csv"},
       "W": W, "book_usd_e8": round(float(u.sum() / 1e8), 2), "n_stocks": len(tk), "res": {k: {pn: st(e, pm, p) for pn, pm in PER.items()} for k, (e, p) in EXC.items()}}
# 한도 크기(억 달러, 기간 중간값) — 요인을 더해도 한도가 얼마나 달라지나
out["limit_median_e8"] = {pn: {k: round(float(np.nanmedian(V[k][pm]) / 1e8), 3) for k in V} for pn, pm in list(PER.items())[:2]}
# 13개월 헤지 장부 초과일 목록
eo = EXC["헤지_자기업종95"][0] & SHORT
out["own_hedged_exceed_days_13m"] = [{"d": str(IDX[i].date()), "chip_shock": bool(SHOCK[i]), "mkt5": bool(MKT[i]), "hedged_e8": round(hed["own"][i] / 1e8, 3), "limit_e8": round(V["own95"][i] / 1e8, 3),
                                      "with_smh_e8": round(hed["os"][i] / 1e8, 3), "still_over_own_limit": bool(hed["os"][i] < V["own95"][i])} for i in np.where(eo)[0]]


def split(exc, m):
    m = m & HAVE & ~np.isnan(act); hi, lo = m & HIGH, m & ~HIGH
    tab = [[int((exc & hi).sum()), int((~exc & hi).sum())], [int((exc & lo).sum()), int((~exc & lo).sum())]]
    return {"high_days": int(hi.sum()), "high_exceed": tab[0][0], "high_rate_pct": round(tab[0][0] / max(hi.sum(), 1) * 100, 1), "low_days": int(lo.sum()), "low_exceed": tab[1][0],
            "low_rate_pct": round(tab[1][0] / max(lo.sum(), 1) * 100, 1), "fisher_p_two_sided": round(float(fisher_exact(tab)[1]), 4)}


out["prereg"] = {"주검정_충격일×자기업종헤지95": split(EXC["헤지_자기업종95"][0], ALL & SHOCK), "참고_모든날×자기업종헤지95": split(EXC["헤지_자기업종95"][0], ALL),
                 "참고_모든날×과거모의95": split(EXC["가_과거모의95"][0], ALL), "참고_충격일×과거모의95": split(EXC["가_과거모의95"][0], ALL & SHOCK),
                 "rho_median_all": round(float(np.nanmedian(rho[ALL])), 3)}
(HERE / "var.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print("장부", out["book_usd_e8"], "억 달러", out["n_stocks"], "종목"); print("한도 중간값", json.dumps(out["limit_median_e8"], ensure_ascii=False))
for k, v in out["res"].items():
    print("\n==", k)
    for pn, s in v.items():
        print(f"  {pn}: 날 {s['days']} 기대 {s['expected']} 초과 {s['exceed']}({s['rate_pct']}%) 쿠피엑p {s['kupiec_p']} | 충격일 {s['shock_days_in_period']}({s['shock_base_pct']}%) 초과중충격 {s['exceed_on_shock']}({s['exceed_shock_pct']}%) 초기하p {s['hypergeom_p']} | 시장5% {s['exceed_on_mkt5']}/{s['mkt5_days']} 충격·시장아님 {s['exceed_on_shock_not_mkt5']} | 충격일초과율 {s['shock_exceed_rate_pct']} 그밖 {s['other_exceed_rate_pct']}")
print("\n헤지 초과일(13개월)"); [print("  ", d) for d in out["own_hedged_exceed_days_13m"]]
print("\nprereg", json.dumps(out["prereg"], ensure_ascii=False, indent=1))
