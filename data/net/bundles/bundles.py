# -*- coding: utf-8 -*-
"""공사 공개 보유 26묶음 전체에 AI 인프라 때와 같은 틀(충격일 · 동적 국면 · 평소 대 실제 손실)을 건다.
2026-11-11 사용자 「우리는 왜 AI 인프라만 다뤄? 이건 내 의도가 아닌데?」, 앞서 「밸류 체인과 동적 국면을 생각해야지요」.

읽는 것(모두 파일 · 망과 유료 AI 안 씀):
  ../returns.csv.gz        야후 수정 종가 2024-10-01~2026-10-29, 638종목+SPY (net_analysis.py 가 쓴 것과 같은 파일)
  ../net_result.json   26묶음 · 종목 섹터/업종 · 2026-06-30 13F 보유 금액
  ../theme_names.json  묶음 이름 · 「섹터를 넘는 테마/섹터 묶음」 이름표
  ../stage_data.json · ../regime_stress.json   AI 인프라 때 값 재현 검사용(아래 self_check)
쓰는 것: result.json · summary.md (만든 시각을 안 넣어 같은 입력이면 같은 파일).
쓰는 법: python -X utf8 bundles.py   (몇 초)

묶음마다
 (가) 충격일: 묶음 종목의 시장 몫을 뺀 등락(같은 비중 평균)이 그 달 앞까지 자료로 잡은 하위 5% 기준 이하이고,
     그 값과 묶음 실제 등락이 모두 음수인 날. 베타는 그날 앞 자료만으로 잼. 규칙은 kic_precheck/regime_monitor.py 와 같다
     (베타 60일 · 기준 126일 · 종목 80% 이상 값 있어야 함).
 (나) 동적 국면: 묶음을 섹터로 둘로 가름(가장 큰 섹터 = 앞 단계, 나머지 = 뒤 단계). 섹터가 하나뿐이면 업종(GICS 세부)으로,
     그래도 한쪽이 2종목 미만이면 1등 종목 대 나머지. 두 쪽의 시장 몫을 뺀 움직임 60거래일 이동 상관.
     2년 안 위치를 AI 인프라 때 값과 견주려고 이 줄만 베타를 기간 전체로 잰다(방법론 문서와 같음).
 (다) 충격일 손실: 공사 보유 금액(2026-06-30) × 그날 등락. 평소 숫자 = 종목마다 시장 몫(그날 앞 베타 × 그날 SPY)
     + 평소 기울기(그날 앞 60거래일, 앞 단계 움직임에 대한 기울기 × 그날 앞 단계 움직임). 배수 = 실제 ÷ 평소(평소가 손실일 때만).
 (라) 섹터를 넘는가: 이름표 + 섹터 수 + 가장 큰 섹터 몫.
"""
import hashlib, json, math
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
NET = HERE.parent
J = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))  # noqa: E731
NR = J(NET / "net_result.json")
TN = {g["id"]: g for g in J(NET / "theme_names.json")["groups"]}
ND = {n["t"]: n for n in NR["nodes"]}
PX = (1 + pd.read_csv(NET / "returns.csv.gz", index_col=0, parse_dates=True, float_precision="round_trip")).cumprod().mul(100)
LOGR = np.log(PX).diff().iloc[1:]
SIMPLE = PX.pct_change(fill_method=None).iloc[1:]
SPY = LOGR["SPY"]
BETA_MIN, CAL_MIN, Q, COVER, WIN, WIN_MIN = 60, 126, 0.05, 0.8, 60, 50
# 같은 업종이 출처(GICS · 야후)마다 이름이 달라 갈라지는 것만 합친다 — 이 자료에서 실제로 본 짝만
SUB_SYN = {"Drug Manufacturers - General": "Pharmaceuticals", "Railroads": "Rail Transportation", "Banks - Diversified": "Diversified Banks",
           "Auto Manufacturers": "Automobile Manufacturers", "Auto Parts": "Automotive Parts & Equipment",
           "Asset Management": "Asset Management & Custody Banks"}
E8 = lambda v: None if v is None else round(v / 1e8, 2)  # noqa: E731  달러 → 억 달러
pct = lambda v: None if v is None or pd.isna(v) else round(float(v) * 100, 2)  # noqa: E731
lpct = lambda v: None if v is None or pd.isna(v) else round(float(np.expm1(v)) * 100, 2)  # noqa: E731
iso = lambda d: pd.Timestamp(d).date().isoformat()  # noqa: E731


def causal_beta(y, x):
    """regime_monitor.causal_features 와 같은 셈: 그날 앞 자료만으로 잰 베타(60일 미만이면 없음)."""
    v = x.notna() & y.notna(); n = v.astype(int).cumsum(); nn = n.replace(0, np.nan)
    xx, yy = x.where(v, 0), y.where(v, 0); sx, sy = xx.cumsum(), yy.cumsum()
    den = (xx * xx).cumsum() - sx * sx / nn; num = (xx * yy).cumsum() - sx * sy / nn
    return (num / den.where(den > 1e-14)).shift(1).where(n.shift(1) >= BETA_MIN)


def full_beta(y, x):
    m = y.notna() & x.notna()
    return float(np.cov(y[m], x[m])[0, 1] / np.var(x[m], ddof=1))


TICKS = [t for t in ND if t in LOGR]
BC = pd.DataFrame({t: causal_beta(LOGR[t], SPY) for t in TICKS})
RC = LOGR[TICKS] - BC.mul(SPY, axis=0)                     # 그날 앞 베타로 뺀 움직임 — 충격일 · 평소 숫자
BF = pd.Series({t: full_beta(LOGR[t], SPY) for t in TICKS})
RF = LOGR[TICKS] - np.outer(SPY.values, BF.values)         # 기간 전체 베타로 뺀 움직임 — 국면 줄(2년 위치)
BFF = pd.DataFrame(np.tile(BF.values, (len(LOGR), 1)), index=LOGR.index, columns=TICKS)


def bmean(frame, ts):
    f = frame[ts]
    return f.mean(axis=1).where(f.notna().sum(axis=1) >= math.ceil(len(ts) * COVER))


def wsum(ts):
    return sum(ND[t]["w"] for t in ts)


def split(members):
    """앞 단계(가장 큰 섹터 → 업종 → 1등 종목) 대 나머지."""
    for how, key in (("섹터", lambda t: ND[t]["sector"]), ("업종", lambda t: SUB_SYN.get(ND[t]["sub"], ND[t]["sub"]))):
        g = {}
        for t in members:
            g.setdefault(key(t), []).append(t)
        if len(g) < 2:
            continue
        lead_name = max(g, key=lambda k: (wsum(g[k]), k))
        lead = g[lead_name]; rest = [t for t in members if t not in lead]
        if len(lead) >= 2 and len(rest) >= 2:
            return {"how": how, "lead_name": lead_name, "lead": lead, "rest": rest, "rest_names": sorted({key(t) for t in rest})}
    top = max(members, key=lambda t: (ND[t]["w"], t))
    return {"how": "1등 종목", "lead_name": top, "lead": [top], "rest": [t for t in members if t != top], "rest_names": ["나머지 종목"]}


def day_loss(d, members, lead_set, lead_r, R, B):
    """그날 공사 보유 금액 기준 실제 손실과 평소 숫자(달러). 앞 단계 · 뒤 단계 따로."""
    i = LOGR.index.get_loc(d); prior = LOGR.index[max(0, i - WIN):i]
    ld = float(lead_r.loc[d]); sd = float(SPY.loc[d])
    # 종목마다 앞 60거래일 기울기 = 두 줄 다 값 있는 날만으로 cov/var(ddof=1) — np.cov 를 종목마다 부른 것과 같은 값
    y = R.loc[prior, members].to_numpy(); x = lead_r.loc[prior].to_numpy()[:, None]
    m = ~np.isnan(y) & ~np.isnan(x); n = m.sum(0)
    xs, ys = np.where(m, x, 0.0), np.where(m, y, 0.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        sx, sy = xs.sum(0), ys.sum(0)
        slope = ((xs * ys).sum(0) - sx * sy / n) / ((xs * xs).sum(0) - sx * sx / n)
    a = SIMPLE.loc[d, members].to_numpy(float); b = B.loc[d, members].to_numpy(float)
    ok = ~np.isnan(a) & ~np.isnan(b) & (n >= WIN_MIN) & ~np.isnan(slope) & (not math.isnan(ld))
    usd = np.array([ND[t]["usd"] for t in members]); normal = np.expm1(b * sd + slope * ld)
    isl = np.array([t in lead_set for t in members])
    out = {k: [float((usd * a)[ok & sel].sum()), float((usd * normal)[ok & sel].sum())] for k, sel in (("lead", isl), ("rest", ~isl))}
    return out, int(ok.sum()), [t for t, g in zip(members, ok) if not g]


def ratio(a, n):
    return round(a / n, 2) if n < 0 else None


def regime(lead, rest):
    link = bmean(RF, lead).rolling(WIN, min_periods=WIN_MIN).corr(bmean(RF, rest)).dropna()
    wk = link.resample("W-FRI").last().dropna()
    last_d, last_v = link.index[-1], float(link.iloc[-1])
    return {"now": [iso(last_d), round(last_v, 2), round(float((link < last_v).mean() * 100), 1)],
            "max": [iso(link.idxmax()), round(float(link.max()), 2)], "min": [iso(link.idxmin()), round(float(link.min()), 2)],
            "from": iso(link.index[0]), "days": int(len(link)),
            "wk": {"d": [iso(x) for x in wk.index], "v": [round(float(x), 3) for x in wk.values]}}


def shocks(members, sp):
    br, ba = bmean(RC, members), bmean(SIMPLE, members)
    cut = pd.Series(np.nan, index=br.index); mon = br.index.strftime("%Y-%m")
    for m in sorted(set(mon)):
        past = br.loc[br.index < br.index[mon == m][0]].dropna()
        if len(past) >= CAL_MIN:
            cut[mon == m] = float(past.quantile(Q))
    el = cut.notna() & br.notna() & ba.notna()
    hit = el & (br <= cut) & (br < 0) & (ba < 0)
    lead_set = set(sp["lead"]); lead_r = bmean(RC, sp["lead"]); rest_r = bmean(RC, sp["rest"]); days = []
    for d in br.index[hit]:
        o, used, skipped = day_loss(d, members, lead_set, lead_r, RC, BC)
        A, N = o["lead"][0] + o["rest"][0], o["lead"][1] + o["rest"][1]
        days.append({"date": iso(d), "bundle_resid_pct": lpct(br[d]), "cut_pct": lpct(cut[d]), "bundle_actual_pct": pct(ba[d]),
                     "spy_pct": pct(SIMPLE.at[d, "SPY"]), "lead_resid_pct": lpct(lead_r[d]), "rest_resid_pct": lpct(rest_r[d]),
                     "actual_e8": E8(A), "normal_e8": E8(N), "ratio": ratio(A, N),
                     "rest_actual_e8": E8(o["rest"][0]), "rest_normal_e8": E8(o["rest"][1]), "rest_ratio": ratio(o["rest"][0], o["rest"][1]),
                     "members_used": used, "skipped": skipped, "before_holdings_date": iso(d) < "2026-06-30"})
    elig = br.index[el]
    rest_led = sum(1 for x in days if None not in (x["rest_resid_pct"], x["lead_resid_pct"]) and x["rest_resid_pct"] < x["lead_resid_pct"])
    return {"rest_led_days": rest_led, "eligible_from": iso(elig[0]) if len(elig) else None, "eligible_to": iso(elig[-1]) if len(elig) else None,
            "eligible_days": int(el.sum()), "n": len(days), "days": days}


def med(xs):
    xs = [x for x in xs if x is not None]
    return (round(float(np.median(xs)), 2), len(xs)) if xs else (None, 0)


def bundle(c):
    M = c["members"]; sp = split(M); tn = TN[c["id"]]
    secs = c["sectors"]; top_share = round(secs[0][1] / c["kic_w"] * 100, 1) if c["kic_w"] else None
    rg = regime(sp["lead"], sp["rest"]); sh = shocks(M, sp)
    r_med, r_n = med([d["ratio"] for d in sh["days"]]); rr_med, rr_n = med([d["rest_ratio"] for d in sh["days"]])
    sA = sum(d["actual_e8"] for d in sh["days"]); sN = sum(d["normal_e8"] for d in sh["days"])
    worst = min(sh["days"], key=lambda d: d["actual_e8"]) if sh["days"] else None
    return {"id": c["id"], "name": tn["theme_ko"], "kind": tn["kind"], "why": tn["why_ko"], "n": c["n"], "kic_w": c["kic_w"],
            "usd_e8": E8(sum(ND[t]["usd"] for t in M)), "n_sectors": len(secs), "top_sector": secs[0][0], "top_sector_share_pct": top_share,
            "split": {"how": sp["how"], "lead_name": sp["lead_name"], "lead_n": len(sp["lead"]), "rest_n": len(sp["rest"]),
                      "rest_names": sp["rest_names"], "lead": sp["lead"], "rest": sp["rest"]},
            "regime": rg, "shock": sh,
            "loss": {"ratio_median": r_med, "ratio_days": r_n, "ratio_none_days": sh["n"] - r_n,
                     "rest_ratio_median": rr_med, "rest_ratio_days": rr_n,
                     "sum_actual_e8": round(sA, 2), "sum_normal_e8": round(sN, 2), "sum_ratio": ratio(sA, sN),
                     "worst": None if worst is None else {k: worst[k] for k in ("date", "actual_e8", "normal_e8", "ratio", "bundle_resid_pct", "spy_pct")}},
            "members": M}


def self_check():
    """AI 인프라 때 값(regime_stress.json)을 이 파일의 함수로 다시 낸다: 국면 0.65 · 딥시크 평소 -10.5 대 실제 -15.1 억 달러."""
    rs = J(NET / "regime_stress.json"); ch = J(NET / "stage_data.json")["chain"]
    tick = {s["name"]: [t for t in s["tick"] if t in TICKS] for s in ch}
    chip = tick["칩"]; power = [t for n in ("전력·냉각 설비", "데이터센터 공사", "발전") for t in tick[n]]
    allm = [t for s in ch for t in tick[s["name"]]]
    rg = regime(chip, power)
    assert rg["now"][:2] == rs["link"]["now"][:2], (rg["now"], rs["link"]["now"])
    o, _, _ = day_loss(pd.Timestamp(rs["link"]["deepseek"]), allm, set(chip), bmean(RF, chip), RF, BFF)
    A, N = (o["lead"][0] + o["rest"][0]) / 1e8, (o["lead"][1] + o["rest"][1]) / 1e8
    assert abs(A - rs["stress"]["tot"]["actual"]) < 0.06 and abs(N - rs["stress"]["tot"]["normal"]) < 0.06, (A, N, rs["stress"]["tot"])
    c0 = NR["communities"][0]; d0 = pd.Timestamp(c0["worst_day"])
    a0 = sum(ND[t]["usd"] * float(SIMPLE.at[d0, t]) for t in c0["members"] if pd.notna(SIMPLE.at[d0, t]))
    assert abs(a0 - c0["worst_loss_usd"]) < 1e4, (a0, c0["worst_loss_usd"])
    return {"regime_now": rg["now"], "deepseek_actual_e8": round(A, 2), "deepseek_normal_e8": round(N, 2), "bundle0_worst_loss_usd": round(a0)}


def table_row(b):
    l, r, s = b["loss"], b["regime"], b["shock"]
    w = l["worst"]
    worst = "—" if w is None else f"{w['date']} 실제 {w['actual_e8']:+.2f} · 평소 {w['normal_e8']:+.2f}"
    f = lambda v: "—" if v is None else f"{v:.2f}배"  # noqa: E731
    return (f"| {b['id']} {b['name']} | {b['n']} | {b['kic_w']:.2f}% | {b['n_sectors']} ({b['top_sector']} {b['top_sector_share_pct']:.0f}%) | "
            f"{r['now'][1]:.2f} (아래에서 {r['now'][2]:.0f}%) | {s['n']} | {s['rest_led_days']} | {f(l['ratio_median'])} ({l['ratio_days']}일) | "
            f"{f(l['rest_ratio_median'])} | {worst} |")


def summary(res):
    B = res["bundles"]; meta = res["meta"]; sc = res["self_check"]
    L = ["# 공사 공개 보유 26묶음 — 충격일 · 동적 국면 · 평소 대 실제 손실", "",
         "bundles.py 가 result.json 에서 만든 글. 손으로 친 숫자 없음.", "",
         "## 무엇을 쟀나", "",
         f"- 대상: 2026-06-30 13F 공개 보유 {meta['n_universe']}종목 중 주가 250일 넘는 {meta['n_used']}종목(공사 몫 {meta['kic_w_used']}%)을 "
         f"같이 움직이는 정도로 나눈 26묶음 {meta['n_in_bundles']}종목(공사 몫 {meta['w_in_bundles']}%). "
         f"어느 묶음에도 안 든 {meta['n_alone']}종목(공사 몫 {meta['w_alone']}%, 큰 것 {', '.join(meta['alone_top'])})은 이 표 밖이다.",
         f"- 주가: {meta['price_from']}~{meta['price_to']} {meta['days']}거래일(../returns.csv.gz, 새로 받은 주가 없음).",
         f"- 충격일: 묶음 종목의 시장 몫을 뺀 등락(같은 비중 평균)이 그 달 앞까지 자료의 하위 5% 기준 이하이고, 그 값과 묶음 실제 등락이 모두 음수인 날. "
         f"베타도 그날 앞 자료로만 잰다. 기준을 세우려면 그 달 앞에 {CAL_MIN}거래일이 있어야 해 판정 가능 기간은 {meta['eligible_from']}~{meta['eligible_to']}"
         f"({meta['eligible_days']}거래일)이다. 그래서 2025-01-27 딥시크 날은 판정 기간 밖이다.",
         "- 동적 국면: 묶음을 가장 큰 섹터(앞 단계) 대 나머지(뒤 단계)로 가르고, 두 쪽의 시장 몫을 뺀 움직임의 60거래일 이동 상관을 잰다. "
         "섹터가 하나면 세부 업종으로, 그래도 한쪽이 2종목 미만이면 1등 종목 대 나머지로 가른다. "
         f"「아래에서 N%」 = 이 묶음의 {res['regime_from'][0]}~2026-10-29 국면 값 가운데 지금보다 낮았던 날의 비율.",
         "- 손실: 2026-06-30 공사 보유 금액 × 충격일 등락(억 달러). 평소 숫자 = 종목마다 시장 몫(그날 앞 베타 × 그날 SPY) + 그날 앞 60거래일 동안 앞 단계 움직임에 대한 기울기 × 그날 앞 단계 움직임. "
         "배수 = 실제 ÷ 평소(평소 숫자가 손실인 날만 셈, 괄호 = 센 날 수). 1배보다 크면 평소 숫자가 손실을 작게 봤다는 뜻. "
         "「뒤 단계가 더 빠진 날」 = 그날 뒤 단계의 시장 몫을 뺀 하락이 앞 단계보다 컸던 날 — 이런 날은 충격이 뒤 단계에서 시작했을 수 있고, 앞 단계로 잰 평소 숫자가 구조적으로 작게 나온다.",
         f"- 재현 검사(이 파일 함수로 AI 인프라 때 값 다시 내기): 국면 {sc['regime_now'][0]} {sc['regime_now'][1]}, 딥시크 날 58종목 평소 {sc['deepseek_normal_e8']} 대 실제 {sc['deepseek_actual_e8']} 억 달러 — "
         "방법론 문서 0.65 · -10.5 대 -15.1 과 같음.", "",
         "## 표", "",
         "| 묶음 | 종목 | 공사 몫 | 섹터 수(가장 큰 섹터 몫) | 지금 국면(2026-10-29) | 충격일 | 그중 뒤 단계가 더 빠진 날 | 평소 대 실제 배수 중간값 | 뒤 단계만 배수 | 가장 컸던 날(억 달러) |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    L += [table_row(b) for b in B]
    L += ["", "## 평소 숫자가 손실을 가장 작게 본 묶음 다섯", "",
          f"배수 중간값 큰 차례. 배수를 센 날이 {res['rank_min_days']}일 이상인 묶음만.", ""]
    for k, b in enumerate(res["top5"], 1):
        l = b["loss"]; sp = b["split"]
        L.append(f"{k}. {b['name']}({b['n']}종목 · 공사 몫 {b['kic_w']:.2f}%) — 배수 중간값 {l['ratio_median']:.2f}배({l['ratio_days']}일), "
                 f"충격일 합계 평소 {l['sum_normal_e8']:+.2f} 대 실제 {l['sum_actual_e8']:+.2f} 억 달러, "
                 f"앞 단계 {sp['lead_name']}({sp['lead_n']}) 대 {', '.join(sp['rest_names'][:4])}({sp['rest_n']}) [가른 기준: {sp['how']}], "
                 f"충격일 {b['shock_n']}일 중 뒤 단계가 더 빠진 날 {b['rest_led_days']}일")
    L += ["", "충격일 손실 합계(실제 합 ÷ 평소 합)로 세면 다섯: " + " · ".join(f"{n} {v:.2f}배" for n, v in res["top5_by_sum"])]
    L += ["", "## 묶음을 어떻게 갈랐나", "", "| 묶음 | 이름표 | 가른 기준 | 앞 단계 | 뒤 단계 |", "|---|---|---|---|---|"]
    for b in B:
        sp = b["split"]
        L.append(f"| {b['id']} {b['name']} | {b['kind']} | {sp['how']} | {sp['lead_name']} {sp['lead_n']}종목 | {', '.join(sp['rest_names'])} {sp['rest_n']}종목 |")
    L += ["", "## 한계", "",
          "- 판정 기간이 약 1년 3개월이고 묶음마다 충격일이 수십 일이 안 된다. 딥시크 같은 2025년 상반기 날은 기준을 세울 앞 자료가 모자라 빠진다.",
          f"- 기준은 그 달 앞 자료의 하위 5%지만 뒤로 갈수록 등락이 커져, 판정 기간에 실제 걸린 날은 묶음마다 {res['shock_share_pct'][0]}~{res['shock_share_pct'][1]}%다.",
          f"- 충격일 가운데 공개 보유 기준일(2026-06-30)보다 앞선 날이 {res['days_before_holdings']}/{res['days_total']}일 — 그날 실제 보유가 아니라 지금 목록을 지난 날에 곱한 재현 값이다.",
          "- 앞 단계 · 뒤 단계는 섹터 · 업종 분류로 가른 것이지 공시로 확인한 거래 관계가 아니다. AI 인프라 때의 여섯 단계(칩 → 발전)처럼 손으로 짠 사슬이 아니다.",
          "- 국면 줄만 기간 전체 베타를 쓴다(2년 안 위치를 AI 인프라 때 값과 견주려고). 충격일과 평소 숫자는 그날 앞 자료만 쓴다.",
          "- 묶음은 2024-10~2026-10 전체 주가로 나눈 것이라 묶음 자체에는 그 기간 뒤 자료가 섞여 있다(누가 같은 묶음인지는 사후에 정함).",
          "- 같은 날 함께 빠졌다는 집계이며 원인을 말하지 않는다. 앞날 손실을 맞히는지는 재지 않았다."]
    return "\n".join(L) + "\n"


def main():
    sc = self_check()
    B = [bundle(c) for c in NR["communities"]]
    inb = {t for b in B for t in b["members"]}; alone = sorted([t for t in TICKS if t not in inb], key=lambda t: -ND[t]["w"])
    allday = [d for b in B for d in b["shock"]["days"]]
    MIN_DAYS = 3
    top5 = sorted([b for b in B if b["loss"]["ratio_days"] >= MIN_DAYS], key=lambda b: (-b["loss"]["ratio_median"], b["id"]))[:5]
    top5s = sorted([b for b in B if b["loss"]["ratio_days"] >= MIN_DAYS and b["loss"]["sum_ratio"] is not None],
                   key=lambda b: (-b["loss"]["sum_ratio"], b["id"]))[:5]
    el = [b["shock"] for b in B if b["shock"]["eligible_from"]]
    sh = [s["n"] / s["eligible_days"] * 100 for s in el]
    meta = {"asof_holdings": NR["asof_holdings"], "price_from": iso(PX.index[0]), "price_to": iso(PX.index[-1]), "days": int(len(PX)),
            "n_universe": NR["n_universe"], "n_used": NR["n_used"], "kic_w_used": NR["kic_w_used"],
            "n_in_bundles": len(inb), "w_in_bundles": round(wsum(inb), 2), "n_alone": len(alone), "w_alone": round(wsum(alone), 2),
            "alone_top": alone[:5], "eligible_from": min(s["eligible_from"] for s in el), "eligible_to": max(s["eligible_to"] for s in el),
            "eligible_days": max(s["eligible_days"] for s in el),
            "inputs_sha256": {p: hashlib.sha256((NET / p).read_bytes()).hexdigest()[:16] for p in ("returns.csv.gz", "net_result.json", "theme_names.json")},
            "params": {"beta_min": BETA_MIN, "calibration_min": CAL_MIN, "shock_quantile": Q, "coverage": COVER, "window": WIN, "window_min": WIN_MIN}}
    res = {"meta": meta, "self_check": sc, "rank_min_days": MIN_DAYS, "days_total": len(allday),
           "days_before_holdings": sum(d["before_holdings_date"] for d in allday),
           "top5_by_sum": [[b["name"], b["loss"]["sum_ratio"]] for b in top5s],
           "regime_from": sorted({b["regime"]["from"] for b in B}),
           "shock_share_pct": [round(min(sh), 1), round(max(sh), 1)],
           "top5": [{"id": b["id"], "name": b["name"], "n": b["n"], "kic_w": b["kic_w"], "loss": b["loss"],
                     "shock_n": b["shock"]["n"], "rest_led_days": b["shock"]["rest_led_days"],
                     "split": {k: b["split"][k] for k in ("how", "lead_name", "lead_n", "rest_n", "rest_names")}} for b in top5],
           "bundles": B}
    (HERE / "result.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    (HERE / "summary.md").write_text(summary(res), encoding="utf-8")
    print(json.dumps({"self_check": sc, "top5": [(b["name"], b["loss"]["ratio_median"], b["loss"]["ratio_days"]) for b in top5]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
