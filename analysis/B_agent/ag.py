# -*- coding: utf-8 -*-
"""실험 2 도구 — 판정을 먼저 써야 실제 값이 열린다. 순서는 order_log.txt.
쓰는 법: ag.py pack D | tool D 이름 | commit D 단계(s1a·s1b·s2) 판정 "글" | reveal1 D | reveal2 D
입력: agent/kic_agent/{days.json,cases,news} · net/backtest/returns_long.csv.gz · chain.json · relations edges"""
import sys, json, hashlib, datetime
from pathlib import Path
import pandas as pd
import os
H = Path(__file__).parent; K = Path(os.environ.get("CHAINSHIFT_DATA", "data") + ""); A = K / "agent/kic_agent"
J = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))
now = lambda: datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(timespec="seconds")


def log(s):
    with open(H / "order_log.txt", "a", encoding="utf-8") as f:
        f.write(f"{now()} {s}\n")


DAYS = J(A / "days.json")["days"]; DD = [x["d"] for x in DAYS]
CH = J(K / "mcp_kic_precheck/kic_precheck/data/chain.json"); ST = {s["name"]: s["tick"] for s in CH["stages"]}
POW = [t for n in CH["power_stages"] for t in ST[n]]; MID = {n: ST[n] for n in ("반도체 장비·소재", "서버·네트워크·부품")}


def px():
    p = (1 + pd.read_csv(K / "net/backtest/returns_long.csv.gz", index_col=0, parse_dates=True, float_precision="round_trip")).cumprod().mul(100)
    return p, p.pct_change(fill_method=None) * 100


jf = lambda d, s: H / "judgments" / f"{d}_{s}.json"
cmd, d = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else None)
if cmd == "pack":
    t = (A / "cases" / d / "materials.md").read_text(encoding="utf-8")
    i = t.find("## 그날 숫자"); j = t.find("## 답하는 법")
    L = t[i:j if j > 0 else None].splitlines(); F = [x for x in L if x.startswith("- F")]
    L = [x[:330] for x in L if not x.startswith("- F") or x in F[:8]]  # 공시 문장은 앞 8줄·줄당 330자만(2025-10-14 부터, 출력 길이 줄임)
    print("=== pack", d, "\n", "\n".join(L), f"\n(공시 문장 {len(F)}줄 중 8줄까지 보임)"); log(f"pack {d}")
elif cmd == "tool":
    name = sys.argv[3]; P, R = px(); i = P.index.get_loc(pd.Timestamp(d)); r = R.iloc[i]; spy = r["SPY"]
    print(f"--- tool {name} {d}")
    if name == "mid":
        print(f"SPY {spy:.2f}% · 칩 9종목 평균 {r[ST['칩']].mean():.2f}% (내린 종목 {(r[ST['칩']] < 0).sum()}/9)")
        for n, ts in MID.items():
            x = r[[t for t in ts if t in r.index]].dropna()
            print(f"{n}: 평균 {x.mean():.2f}% · 시장 대비 {x.mean() - spy:.2f}%p · 시장보다 더 빠진 종목 {(x < spy).sum()}/{len(x)} · 가장 나쁜 셋 " + ", ".join(f"{t} {v:.1f}" for t, v in x.sort_values()[:3].items()))
    elif name == "midb":  # 중간 수정 2 — 종목별 민감도(그날 전 250거래일 회귀 기울기) × SPY 를 뺀 값. 오늘과 앞선 충격일을 함께 보임
        def adj(day):
            k = P.index.get_loc(pd.Timestamp(day)); w = R.iloc[k - 250:k]; rr = R.iloc[k]; o = {}
            for n, ts in list(MID.items()) + [("칩", ST["칩"])]:
                v = []
                for t in ts:
                    x = w[[t, "SPY"]].dropna()
                    if len(x) > 60 and pd.notna(rr[t]):
                        v.append(rr[t] - x[t].cov(x["SPY"]) / x["SPY"].var() * rr["SPY"])
                o[n] = sum(v) / len(v)
            return o
        for x in DAYS:
            if x["d"] <= d:
                o = adj(x["d"]); past = x["d"] < d
                print(f"  {x['d']} 민감도 뺀 값: 칩 {o['칩']:.2f} 장비 {o['반도체 장비·소재']:.2f} 서버·부품 {o['서버·네트워크·부품']:.2f}" + (f" → 번짐 {x['spread']}(비율 {x['ratio']})" if past else " → (오늘, 정답 가림)"))
    elif name == "pre":
        print("전날까지 5거래일(그날 제외) 날짜·SPY·칩 평균·전력 쪽 평균:")
        for dt, row in R.iloc[i - 5:i].iterrows():
            print(f"  {dt.date()} SPY {row['SPY']:.2f} 칩 {row[ST['칩']].mean():.2f} 전력 {row[[t for t in POW if t in row.index]].mean():.2f}")
    elif name == "hist":
        for x in DAYS:
            if x["d"] < d:
                print(f"  {x['d']} 칩 {x['chip']} 전력 {x['power']} 비율 {x['ratio']} 번짐 {x['spread']} 직전 연동 {x['link_before']}")
        if d <= DD[0]:
            print("  (앞선 충격일 없음)")
    elif name == "newsstat":
        n = J(A / "news" / f"{d}.json")
        print("단계별", n["by_stage"], "\n회사별", n["by_company"], "\n데이터센터 낱말 기사", n["dc_hit_records"], "· 58종목 기사", n["hit_records"], "· 제목", n["unique_titles"])
        for it in n["top"][12:]:
            print("  +", it["src"], it["title"], it["ticks"])
    elif name == "rel":
        REL = K / "relations"; k = 0
        for e in J(REL / "us/edges.json") + J(REL / "kr/edges.json"):
            pub = min(x["published_at"] for x in e["evidence"]); f, t = e["from"]["id"].split(":")[-1], e["to"]["id"].split(":")[-1]
            if e["status"] == "verified_original" and pub < d and (f in POW or t in POW):
                k += 1; print(f"  {e['edge_id']} {f}→{t} {e['relation']} 공시 {pub}: {e['what'][:80]}")
        print(f"  쓸 수 있는 전력 쪽 관계 {k}건")
    log(f"tool {d} {name}")
elif cmd == "commit":
    s, verdict, text = sys.argv[3], sys.argv[4], sys.argv[5]; p = jf(d, s)
    assert not p.exists(), "이미 씀 — 덮어쓰지 않음"
    if s == "s1b":
        assert jf(d, "s1a").exists()
    if s == "s2":
        assert (H / "judgments" / f"{d}_reveal1.flag").exists(), "판정 1 정답을 연 뒤에 판정 2"
    o = {"date": d, "stage": s, "verdict": verdict, "text": text, "written_at": now()}
    b = json.dumps(o, ensure_ascii=False, indent=1); p.write_text(b, encoding="utf-8")
    log(f"commit {d} {s} verdict={verdict} sha={hashlib.sha256(b.encode()).hexdigest()[:12]}"); print("썼음", p.name, verdict)
elif cmd == "reveal1":
    assert jf(d, "s1b").exists(), "끝 판정을 먼저 써야 열림"
    x = next(x for x in DAYS if x["d"] == d); P, R = px(); r = R.loc[d]
    print(f"[정답1 {d}] 칩 {x['chip']} · 전력 {x['power']} · 비율 {x['ratio']} · 번짐 {x['spread']} · 직전 연동 {x['link_before']}")
    print("  전력 쪽 단계별 실제 등락(SPY %.2f): " % r["SPY"] + " · ".join(f"{n} {r[[t for t in ST[n] if t in r.index]].mean():.2f}" for n in CH["power_stages"]))
    (H / "judgments" / f"{d}_reveal1.flag").write_text(now()); log(f"reveal1 {d}")
elif cmd == "reveal2":
    assert jf(d, "s2").exists(), "판정 2 를 먼저 써야 열림"
    P, R = px(); i = P.index.get_loc(pd.Timestamp(d)); r = R.iloc[i + 1]; pw = r[[t for t in POW if t in r.index]].mean()
    print(f"[정답2 {d} → 다음 거래일 {P.index[i + 1].date()}] 전력 쪽 {pw:.2f}% · SPY {r['SPY']:.2f}% · 차이 {pw - r['SPY']:.2f}%p → {'이어진다' if pw - r['SPY'] < 0 else '안 이어진다'} · 칩 {r[ST['칩']].mean():.2f}%")
    log(f"reveal2 {d}")
