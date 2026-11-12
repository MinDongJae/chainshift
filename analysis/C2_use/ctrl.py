# -*- coding: utf-8 -*-
"""대조 계산 — 공시 관계로 고른 회사를 더한 것과, 관계와 무관하게 고른 회사를 같은 금액만큼 더한 것을 같은 날에 견준다.
B_agent/exp1.py 와 같은 규칙(확인된 관계 · 가장 이른 공개일이 그날보다 앞 · 한쪽만 58종목 안 · 13F 에 있고 주가 있음)으로 관계 쪽을 다시 내고,
대조 넷을 붙인다:
  size      = 58종목 밖 13F 보유를 금액 큰 차례로(관계 무관) 같은 금액이 찰 때까지(끝 종목은 잘라 맞춤)
  size_x    = 위와 같되 관계로 뽑힌 회사는 빼고
  rand      = 58종목 밖 보유에서 같은 수를 무작위로 뽑아 같은 금액으로 맞춤(5,000번)
  rand_sec  = 관계로 뽑힌 회사마다 같은 업종(GICS 11갈래, net/bundles 의 ND)의 다른 회사 하나로 바꿔 같은 금액(5,000번) — 「기술주라서」를 가르는 대조
  rand_size = 관계로 뽑힌 회사마다 금액 순위가 가까운 10곳(뽑힌 회사 제외) 중 하나로 바꿔 같은 금액(5,000번) — 「큰 회사라서」를 가르는 대조
13F 금액 순위를 시가총액 순위 대신 쓴다(주가 파일에 시가총액이 없다 — 한계).
입력: net/returns.csv.gz · net/universe.json · mcp_kic_precheck/.../chain.json · relations/{us,kr}/edges.json · B_agent/exp1_result.json(맞대기) · A_problem/short_panel.json(칩 충격일 46일)
출력: ctrl_result.json   실행: python -X utf8 ctrl.py"""
import json
from pathlib import Path
import sys
import numpy as np, pandas as pd
from scipy.stats import binomtest
import os
sys.path.insert(0, os.environ.get("CHAINSHIFT_DATA", "data") + "/net/bundles")
import bundles as BD  # 업종 이름만 씀
SEC = {t: v["sector"] for t, v in BD.ND.items()}
K = Path(os.environ.get("CHAINSHIFT_DATA", "data") + ""); H = Path(__file__).parent; F1 = H.parent
REL = K / "relations"
J = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))
px = (1 + pd.read_csv(K / "net/returns.csv.gz", index_col=0, parse_dates=True, float_precision="round_trip")).cumprod().mul(100); ret = px.pct_change(fill_method="pad")
S58 = J(K / "mcp_kic_precheck/kic_precheck/data/chain.json")["holdings_usd"]
held = {v["ticker"]: v["value"] for v in J(K / "net/universe.json")["companies"].values() if v.get("ticker")}
E = [e for e in J(REL / "us/edges.json") + J(REL / "kr/edges.json") if e["status"] == "verified_original"]
EXP1 = {o["date"]: o for o in J(F1 / "B_agent/exp1_result.json")}
SP = J(F1 / "A_problem/short_panel.json")
D46 = SP["W250"]["crit_days"]["chip"]; DALL = [d for d in SP["chip_days_in_panel"]]
D4 = list(EXP1); NDRAW = 5000; rng = np.random.default_rng(20261112)


def rel_set(d, pit=True):
    """그날 쓸 수 있는 관계로 닿는 58종목 밖 13F 회사. pit=False 면 공개일을 안 가림(뒤 자료 섞임 — 참고용)."""
    s = set()
    for e in E:
        if pit and not min(x["published_at"] for x in e["evidence"]) < d: continue
        f, t = e["from"]["id"].split(":")[-1], e["to"]["id"].split(":")[-1]
        if (f in S58) == (t in S58): continue
        s.add(t if f in S58 else f)
    return s


def one(d, pit=True):
    r = ret.loc[d]; ok = lambda t: t in r.index and pd.notna(r[t])
    A = sorted(t for t in rel_set(d, pit) if t in held and ok(t))
    if not A: return None
    base = sum(S58[t] * r[t] for t in S58 if ok(t))
    pool = sorted((t for t in held if t not in S58 and ok(t)), key=lambda t: -held[t])
    hv = np.array([held[t] for t in pool]); rv = np.array([r[t] for t in pool]); pos = {t: i for i, t in enumerate(pool)}
    VA = sum(held[t] for t in A); LA = sum(held[t] * r[t] for t in A)

    def size_loss(skip):
        left, loss, names = VA, 0.0, []
        for t in pool:
            if t in skip: continue
            take = min(left, held[t]); loss += take * r[t]; left -= take; names.append(t)
            if left <= 0: break
        return loss, names
    Ls, ns = size_loss(set()); Lx, nx = size_loss(set(A))
    k = len(A)
    idx = np.array([rng.choice(len(pool), k, replace=False) for _ in range(NDRAW)])
    Lr = VA * (hv[idx] * rv[idx]).sum(1) / hv[idx].sum(1)                       # 같은 수 · 같은 금액으로 맞춤
    notA = [i for i, t in enumerate(pool) if t not in A]
    Lm = np.zeros(NDRAW)
    for t in A:                                                                # 금액 순위 가까운 10곳 중 하나
        near = sorted(notA, key=lambda i: abs(i - pos[t]))[:10]
        Lm += held[t] * rv[rng.choice(near, NDRAW)]
    Lsec = np.zeros(NDRAW)
    for t in A:                                                                # 같은 업종의 다른 회사 하나
        same = [i for i in notA if SEC.get(pool[i]) == SEC.get(t)] or notA
        Lsec += held[t] * rv[rng.choice(same, NDRAW)]
    ratio = lambda L: round(float((base + L) / base), 3)
    m = 1e6
    return {"date": d, "n_rel": k, "rel": A, "rel_value_usd_m": round(VA / m, 1), "loss58_usd_m": round(base / m, 1),
            "spy_pct": round(float(r["SPY"]) * 100, 2),
            "rel_loss_usd_m": round(LA / m, 1), "rel_ratio": ratio(LA),
            "size_loss_usd_m": round(Ls / m, 1), "size_ratio": ratio(Ls), "size_names": ns, "size_overlap_with_rel": sorted(set(ns) & set(A)),
            "size_x_loss_usd_m": round(Lx / m, 1), "size_x_ratio": ratio(Lx), "size_x_names": nx,
            "rand_loss_median_usd_m": round(float(np.median(Lr)) / m, 1), "rand_ratio_median": ratio(np.median(Lr)),
            "rand_ratio_p05_p95": [ratio(np.quantile(Lr, .95)), ratio(np.quantile(Lr, .05))] if base < 0 else None,
            "rel_worse_than_rand_share_pct": round(float((LA < Lr).mean()) * 100, 1),   # 관계 쪽 손실이 더 큰 추첨의 몫
            "randsize_loss_median_usd_m": round(float(np.median(Lm)) / m, 1), "randsize_ratio_median": ratio(np.median(Lm)),
            "rel_worse_than_randsize_share_pct": round(float((LA < Lm).mean()) * 100, 1),
            "randsec_loss_median_usd_m": round(float(np.median(Lsec)) / m, 1), "randsec_ratio_median": ratio(np.median(Lsec)),
            "rel_worse_than_randsec_share_pct": round(float((LA < Lsec).mean()) * 100, 1),
            "rel_sectors": {t: SEC.get(t) for t in A},
            "_": [LA, Ls, Lx, float(np.median(Lr)), float(np.median(Lm)), base, float(np.median(Lsec))]}


def agg(rows):
    rows = [x for x in rows if x]
    S = np.array([x["_"] for x in rows]).sum(0) / 1e6
    n = len(rows); w = lambda key_a, key_b: sum(x[key_a] < x[key_b] for x in rows)
    return {"days": n, "sum_loss58_usd_m": round(S[5], 1),
            "sum_added_usd_m": {"rel": round(S[0], 1), "size": round(S[1], 1), "size_x": round(S[2], 1), "rand_median": round(S[3], 1), "randsize_median": round(S[4], 1), "randsec_median": round(S[6], 1)},
            "sum_ratio": {k: round((S[5] + S[i]) / S[5], 3) for i, k in zip([0, 1, 2, 3, 4, 6], ["rel", "size", "size_x", "rand_median", "randsize_median", "randsec_median"])},
            "days_rel_loss_bigger_than": {"size": w("rel_loss_usd_m", "size_loss_usd_m"), "size_x": w("rel_loss_usd_m", "size_x_loss_usd_m"),
                                          "rand_median": w("rel_loss_usd_m", "rand_loss_median_usd_m"), "randsize_median": w("rel_loss_usd_m", "randsize_loss_median_usd_m"), "randsec_median": w("rel_loss_usd_m", "randsec_loss_median_usd_m")},
            "binom_p_one_sided_vs_half": {k: round(float(binomtest(int(w("rel_loss_usd_m", c)), n, 0.5, alternative="greater").pvalue), 4)
                                          for k, c in (("size", "size_loss_usd_m"), ("rand_median", "rand_loss_median_usd_m"), ("randsize_median", "randsize_loss_median_usd_m"), ("randsec_median", "randsec_loss_median_usd_m"))},
            "days_rel_in_worst_5pct_of_rand": sum(x["rel_worse_than_rand_share_pct"] >= 95 for x in rows),
            "days_rel_in_worst_5pct_of_randsize": sum(x["rel_worse_than_randsize_share_pct"] >= 95 for x in rows),
            "days_rel_in_worst_5pct_of_randsec": sum(x["rel_worse_than_randsec_share_pct"] >= 95 for x in rows),
            "mean_rel_worse_than_randsec_share_pct": round(float(np.mean([x["rel_worse_than_randsec_share_pct"] for x in rows])), 1),
            "mean_rel_worse_than_rand_share_pct": round(float(np.mean([x["rel_worse_than_rand_share_pct"] for x in rows])), 1),
            "mean_rel_worse_than_randsize_share_pct": round(float(np.mean([x["rel_worse_than_randsize_share_pct"] for x in rows])), 1)}


def strip(rows): return [{k: v for k, v in x.items() if k != "_"} for x in rows if x]


r4 = [one(d) for d in D4]
for x in r4:                                   # exp1 과 맞대기
    e = EXP1[x["date"]]; assert abs(x["rel_ratio"] - e["ratio"]) < 0.002 and sorted(e["added"]) == x["rel"], (x["date"], x["rel_ratio"], e["ratio"])
r46 = [one(d) for d in D46]; r46f = [one(d, pit=False) for d in D46]; rall = [one(d, pit=False) for d in DALL]
out = {"note": "금액 백만 달러. 손실은 13F(2026-06-30) 금액 × 그날 종가 등락 — 재현 값. ratio = (58종목 손실 + 더한 손실) ÷ 58종목 손실. 무작위는 5,000번(seed 20261112).",
       "four_days": {"agg": agg(r4), "rows": strip(r4)},
       "chip46_pit": {"what": "칩 충격일 46일(2025-10-02~2026-10-29, 그달 앞 자료 하위 5%) · 관계는 그날 전에 공개된 것만", "days_with_no_relation": sum(x is None for x in r46), "agg": agg(r46), "rows": strip(r46)},
       "chip46_pit_after_0814": {"what": "위 46일 가운데 2026-08-14(국내 반기보고서 · 13F 지분 공시) 뒤 날만 — 그 앞은 쓸 수 있는 관계가 2~5곳뿐", "agg": agg([x for x in r46 if x and x["date"] > "2026-08-14"])},
       "chip46_pit_before_0814": {"what": "위 46일 가운데 2026-08-14 앞 날", "agg": agg([x for x in r46 if x and x["date"] <= "2026-08-14"])},
       "chip46_fixed": {"what": "같은 46일 · 관계 111건을 공개일 안 가리고 전부 씀(뒤 자료 섞임 — 참고용)", "agg": agg(r46f), "rows": strip(r46f)},
       "chip_all_fixed": {"what": f"주가 파일 안 칩 충격일 {len(DALL)}일(2024-10~) · 관계 전부(뒤 자료 섞임 — 참고용)", "agg": agg(rall)}}
(H / "ctrl_result.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=int), encoding="utf-8")
for k in ("four_days", "chip46_pit", "chip46_pit_after_0814", "chip46_pit_before_0814", "chip46_fixed", "chip_all_fixed"):
    print(k, json.dumps(out[k]["agg"], ensure_ascii=False, default=int));
for x in strip(r4):
    print(x["date"], "관계", x["rel_ratio"], "크기순", x["size_ratio"], x["size_names"], "겹침", x["size_overlap_with_rel"], "크기순(관계 제외)", x["size_x_ratio"],
          "무작위 중간", x["rand_ratio_median"], x["rand_ratio_p05_p95"], "관계가 더 큰 손실인 추첨 %", x["rel_worse_than_rand_share_pct"],
          "크기 맞춘 무작위", x["randsize_ratio_median"], x["rel_worse_than_randsize_share_pct"], "같은 업종 무작위", x["randsec_ratio_median"], x["rel_worse_than_randsec_share_pct"], x["rel_sectors"])
