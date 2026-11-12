# -*- coding: utf-8 -*-
"""날마다 헤지 뒤 남는 손익 — A3_hedge/hedge.py 의 계산(그날 앞 250거래일 회귀, 절편 포함)을 그대로 옮겨 날 단위로 낸다.
읽는 것(읽기만): net/backtest/returns_long.csv.gz · mcp_kic_precheck/kic_precheck/data/chain.json · net/net_result.json
  ../A3_hedge/etf_long_ret.csv (야후 일별 수정 종가, 2026-11-12 00:54 KST 받음, 2026-11-10 까지 — 새로 받지 않음)
  ../B2_roles/interpret/judgments/*.json · ../B2_roles/interpret2/judgments/*.json (까닭 갈래)
쓰는 것: days.json · days.md   실행: python -X utf8 dayhedge.py"""
import json, sys, glob
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
E = (1 + pd.read_csv(HERE.parent / "A3_hedge/etf_long_ret.csv", index_col=0, parse_dates=True, float_precision="round_trip")).cumprod().mul(100).pct_change().reindex(IDX)
assert float((E["SPY"] - R["SPY"]).abs().max()) < 2e-3
H = RM.monitor_history(PX[CHIPS + POWERS + ["SPY"]], CHIPS, POWERS, RM.MonitorConfig(hysteresis=0.03)).reindex(IDX)
SHOCK = ((H["eligible"] == True) & (H["chip_shock"] == True)).to_numpy()  # noqa: E712
SHORT = np.asarray((IDX >= "2025-10-02") & (IDX <= "2026-10-29"))
assert (SHOCK & SHORT).sum() == 46
HEDGES = {"SPY": ["SPY"], "OWN": ["OWN"], "SMH": ["SMH"], "OWN+SMH": ["OWN", "SMH"]}
L = {"SPY": "시장 펀드", "OWN": "자기 업종 펀드", "SMH": "반도체 펀드", "OWN+SMH": "자기 업종+반도체"}


def fit(X, y, x):
    A = np.column_stack([np.ones(len(X)), X]); b, *_ = np.linalg.lstsq(A, y, rcond=None)
    return float(x @ b[1:]), b[1:]


assert abs(fit(np.arange(5.)[:, None], 2 * np.arange(5.) + 1, np.array([3.]))[0] - 6) < 1e-9


def day(ticks, i):
    """hedge.py run() 의 한 날치. → 손익, 수단별 남는 손익, 수단별 기울기(달러/등락1), 든 종목 수, 금액, 자기 업종 펀드 등락"""
    tk = [t for t in ticks if t in PX]; a = R[tk].to_numpy(float); u = np.array([HOLD[t] for t in tk])
    etf = E[[SEC_ETF[SEC[t]] for t in tk]].to_numpy(float)
    w = slice(i - W, i + 1); ok = ~np.isnan(a[w]).any(axis=0)
    y = a[w][:, ok] @ u[ok]; own = etf[w][:, ok] @ (u[ok] / u[ok].sum())
    F = {"SPY": E["SPY"].to_numpy()[w], "SMH": E["SMH"].to_numpy()[w], "OWN": own}
    res, beta = {}, {}
    for k, cols in HEDGES.items():
        X = np.column_stack([F[c] for c in cols]); h, b = fit(X[:-1], y[:-1], X[-1]); res[k] = y[-1] - h; beta[k] = [float(v) for v in b]
    return float(y[-1]), res, beta, int(ok.sum()), float(u[ok].sum()), float(own[-1])


SCOPES = {"전력 쪽 19종목": POWERS, **{s["name"]: s["tick"] for s in CH["stages"] if s["name"] in CH["power_stages"]}}
J = {}
for tag, d in (("해석1", "interpret"), ("해석2", "interpret2")):
    for f in glob.glob(str(HERE.parent / f"B2_roles/{d}/judgments/*.json")):
        j = json.loads(Path(f).read_text(encoding="utf-8")); J.setdefault(j["date"], {})[tag] = j
D25 = sorted(J); assert len(D25) == 25
dates = sorted(set(D25) | {str(x.date()) for x in IDX[SHOCK & SHORT]} | {"2026-11-04"})
CU = np.array([HOLD[t] for t in CHIPS])
rows = []
for ds in dates:
    i = IDX.get_loc(pd.Timestamp(ds)); assert i >= W
    cr = R[CHIPS].iloc[i].to_numpy(float); assert not np.isnan(cr).any()
    r = {"date": ds, "in46": bool(SHOCK[i] and SHORT[i]), "in25": ds in J, "rule_shock": bool(SHOCK[i]),
         "chip_pct": round(float(cr @ CU / CU.sum()) * 100, 2), "chip_usd_e8": round(float(cr @ CU) / 1e8, 2), "chip_down_n": int((cr < 0).sum()),
         "smh_pct": round(float(E["SMH"].iloc[i]) * 100, 2), "spy_pct": round(float(E["SPY"].iloc[i]) * 100, 2), "scopes": {}}
    for name, ticks in SCOPES.items():
        act, res, beta, n, usd, own = day(ticks, i)
        best = min(res, key=lambda k: abs(res[k]))
        r["scopes"][name] = {"n": n, "usd_e8": round(usd / 1e8, 2), "act_e8": round(act / 1e8, 3), "act_pct": round(act / usd * 100, 2), "own_pct": round(own * 100, 2),
                             "left_e8": {k: round(v / 1e8, 3) for k, v in res.items()},
                             "left_pct": {k: round(v / act * 100, 0) for k, v in res.items()},
                             "hedge_usd_e8": {k: [round(-b / 1e8, 2) for b in v] for k, v in beta.items()},   # 음수 = 그만큼 수단을 팔아 둠(억 달러)
                             "best": best}
    for tag in ("해석1", "해석2"):
        j = J.get(ds, {}).get(tag)
        if j: r[tag] = {"cause": j["cause"], "verdict": j["verdict"], "confidence": j.get("confidence"), "evidence1": j["evidence"][0] if j.get("evidence") else None, "counter": j.get("counter")}
    rows.append(r)

P = "전력 쪽 19종목"


def grp(sel):
    a = np.array([r["scopes"][P]["act_e8"] for r in sel]); o = {"days": len(sel), "act_sum_e8": round(float(a.sum()), 2), "loss_days": int((a < 0).sum())}
    for k in HEDGES:
        x = np.array([r["scopes"][P]["left_e8"][k] for r in sel])
        o[k] = {"left_sum_e8": round(float(x.sum()), 2), "left_pct_of_sum": round(float(x.sum() / a.sum() * 100), 1) if a.sum() < 0 else None,
                "abs_left_pct": round(float(np.abs(x).sum() / np.abs(a).sum() * 100), 1), "median_abs_day_pct": round(float(np.median(np.abs(x) / np.abs(a)) * 100), 1),
                "still_loss_days": int((x < 0).sum()), "best_days": sum(r["scopes"][P]["best"] == k for r in sel)}
    return o


r46 = [r for r in rows if r["in46"]]; r25 = [r for r in rows if r["in25"]]
out = {"rows": rows, "groups": {"46일": grp(r46), "25일": grp(r25), "25일 중 46일에 드는 날": grp([r for r in r25 if r["in46"]])}, "by_cause": {}}
# 자기 검사: 46일 값이 A3_hedge/hedge.json 과 같은가
A3 = json.loads((HERE.parent / "A3_hedge/hedge.json").read_text(encoding="utf-8"))["scopes"]["전력 쪽 19종목 합"]["by"]["shock46"]
for k in HEDGES:
    assert abs(out["groups"]["46일"][k]["left_pct_of_sum"] - A3[k]["left_pct_of_sum"]) < 0.3 and abs(out["groups"]["46일"][k]["abs_left_pct"] - A3[k]["abs_left_pct"]) < 0.3, (k, out["groups"]["46일"][k], A3[k])
for tag in ("해석1", "해석2"):
    for pop, sel0 in (("25일", r25), ("46일에 드는 날만", [r for r in r25 if r["in46"]])):
        cs = sorted({r[tag]["cause"] for r in sel0})
        out["by_cause"][f"{tag} · {pop}"] = {c: grp([r for r in sel0 if r[tag]["cause"] == c]) | {"dates": [r["date"] for r in sel0 if r[tag]["cause"] == c]} for c in cs}
worst = lambda sel: [r["date"] for r in sorted(sel, key=lambda r: r["scopes"][P]["left_e8"]["SMH"])[:5]]
out["worst5_smh"] = {"46일": worst(r46), "25일": worst(r25)}
(HERE / "days.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

# ---- 글
m = []


def tab(sel, title):
    m.append(f"\n### {title}\n\n| 날짜 | 칩 9종목 | 반도체 펀드 | 시장 | 전력 쪽 손익(억$) | 전력 쪽 % | 시장 헤지 뒤 | 자기 업종 뒤 | 반도체 뒤 | 자기 업종+반도체 뒤 | 가장 잘 지운 수단 | 까닭(해석1 / 해석2) |\n|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in sel:
        s = r["scopes"][P]; c = " / ".join(r[t]["cause"] if t in r else "—" for t in ("해석1", "해석2")) if r["in25"] else "판단 실험 밖"
        f = lambda k: f"{s['left_e8'][k]:+.2f} ({s['left_pct'][k]:.0f}%)"
        m.append(f"| {r['date']} | {r['chip_pct']:+.2f}% | {r['smh_pct']:+.2f}% | {r['spy_pct']:+.2f}% | {s['act_e8']:+.2f} | {s['act_pct']:+.2f}% | {f('SPY')} | {f('OWN')} | {f('SMH')} | {f('OWN+SMH')} | {L[s['best']]} | {c} |")


def gtab(d, title):
    m.append(f"\n### {title}\n\n| 묶음 | 날 | 손실일 | 전력 쪽 손익 합(억$) | 수단 | 남는 손익 합(억$) | 합계 기준 남는 몫 | 날마다 크기 기준 | 하루 남는 몫 중간값 | 헤지 뒤에도 손실인 날 | 가장 잘 지운 날 수 |\n|---|---|---|---|---|---|---|---|---|---|---|")
    for g, o in d.items():
        for k in HEDGES:
            v = o[k]; m.append(f"| {g} | {o['days']} | {o['loss_days']} | {o['act_sum_e8']:+.2f} | {L[k]} | {v['left_sum_e8']:+.2f} | {v['left_pct_of_sum']}% | {v['abs_left_pct']}% | {v['median_abs_day_pct']}% | {v['still_loss_days']} | {v['best_days']} |")


x = next(r for r in rows if r["date"] == "2026-11-04")
m.append(f"## 2026-11-04 한 날\n\n칩 충격 날 규칙에 걸린 날인가: {x['rule_shock']} · 칩 9종목(보유 금액 가중) {x['chip_pct']:+.2f}% ({x['chip_usd_e8']:+.2f}억$, 내린 종목 {x['chip_down_n']}/9) · 반도체 펀드(SMH) {x['smh_pct']:+.2f}% · 시장(SPY) {x['spy_pct']:+.2f}%\n")
m.append("| 범위 | 종목 | 보유(억$) | 손익(억$) | 등락 | 자기 업종 펀드 등락 | 시장 헤지 뒤 | 자기 업종 뒤 | 반도체 뒤 | 자기 업종+반도체 뒤 | 반도체 펀드 헤지 포지션(억$) |\n|---|---|---|---|---|---|---|---|---|---|---|")
for name, s in x["scopes"].items():
    f = lambda k: f"{s['left_e8'][k]:+.3f} ({s['left_pct'][k]:.0f}%)"
    m.append(f"| {name} | {s['n']} | {s['usd_e8']} | {s['act_e8']:+.3f} | {s['act_pct']:+.2f}% | {s['own_pct']:+.2f}% | {f('SPY')} | {f('OWN')} | {f('SMH')} | {f('OWN+SMH')} | {s['hedge_usd_e8']['SMH'][0]} |")
m.append("\n괄호 = 남는 몫(남는 손익 ÷ 그날 손익). 100% 넘으면 헤지가 손실을 키운 것, 음수면 부호가 뒤집힌 것.")
tab(r46, "칩 충격 46일 (2025-10-02 ~ 2026-10-29) — 전력 쪽 19종목, 남는 손익 억$ (남는 몫)")
tab([r for r in r25 if not r["in46"]], "판단 실험 25일 가운데 46일 밖의 날")
gtab(out["groups"], "묶음 합계")
for k, d in out["by_cause"].items():
    gtab(d, f"까닭 갈래별 — {k}")
m.append("\n### 반도체 펀드 헤지가 가장 크게 빗나간 날 다섯 (남는 손익이 가장 큰 손실)\n")
for pop, ds in out["worst5_smh"].items():
    m.append(f"\n**{pop} 가운데**\n")
    for d in ds:
        r = next(q for q in rows if q["date"] == d); s = r["scopes"][P]
        m.append(f"- {d}: 칩 {r['chip_pct']:+.2f}% · 반도체 펀드 {r['smh_pct']:+.2f}% · 시장 {r['spy_pct']:+.2f}% · 전력 쪽 {s['act_e8']:+.2f}억$ → 반도체 펀드 헤지 뒤 {s['left_e8']['SMH']:+.2f}억$ ({s['left_pct']['SMH']:.0f}%) · 자기 업종 뒤 {s['left_e8']['OWN']:+.2f} · 둘 함께 {s['left_e8']['OWN+SMH']:+.2f} · 가장 잘 지운 수단 {L[s['best']]}")
        for t in ("해석1", "해석2"):
            if t in r:
                e = r[t]["evidence1"] or {}; e = e if isinstance(e, dict) else {"text": e, "src": "출처 칸 없음"}; m.append(f"  - {t}: 까닭 「{r[t]['cause']}」 · 판정 {r[t]['verdict']}({r[t]['confidence']}) · 근거 「{e.get('text')}」({e.get('src')}) · 반대 근거: {r[t]['counter']}")
        if not r["in25"]:
            m.append("  - 판단 실험 25일 밖 — 해석 개체의 글 없음")
(HERE / "days.md").write_text("\n".join(m), encoding="utf-8")
print("\n".join(m))
