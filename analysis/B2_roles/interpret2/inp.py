# -*- coding: utf-8 -*-
"""해석 역할(interpret2) 입력 도구. 그날 장 마감까지 값만 낸다(다음 거래일·당일 전력 쪽·days.json 정답 칸은 읽지 않음).
쓰는 법: inp.py pack D | mid D | pre D | newsstat D | commit D < 판정.json
입력: agent/kic_agent/{days.json(날짜 칸만),cases/D/materials.md,news/D.json} · net/backtest/returns_long.csv.gz · mcp_kic_precheck/.../chain.json"""
import sys, json, hashlib, datetime
from pathlib import Path
import os
H = Path(__file__).parent; K = Path(os.environ.get("CHAINSHIFT_DATA", "data") + ""); A = K / "agent/kic_agent"
J = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))
now = lambda: datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(timespec="seconds")
def log(s):
    with open(H / "order_log.txt", "a", encoding="utf-8") as f: f.write(f"{now()} {s}\n")
DD = [x["d"] for x in J(A / "days.json")["days"]]
cmd, d = sys.argv[1], sys.argv[2]; assert d in DD
done = [p.stem for p in (H / "judgments").glob("*.json")]
if cmd != "commit":  # 차례 강제: 앞 날을 다 쓴 뒤에만 이 날 자료가 열림
    assert all(x in done for x in DD[:DD.index(d)]), "앞 날 판정을 먼저 써야 함"
if cmd == "pack":
    t = (A / "cases" / d / "materials.md").read_text(encoding="utf-8")
    i = t.find("## 그날 숫자"); j = t.find("## 답하는 법")
    t = t[i:j if j > 0 else None]; h = t.find("## 지난 사례")  # 지난 사례 절은 앞선 날 정답을 담고 있어 자름(2025-04-09 에서 발견)
    if h > 0: t = t[:h] + t[t.find("## 기사 제목"):]
    L = t.splitlines(); F = [x for x in L if x.startswith("- F")]
    L = [x[:330] for x in L if not x.startswith("- F") or x in F[:8]]
    print("=== pack", d, "\n" + "\n".join(L), f"\n(공시 문장 {len(F)}줄 중 8줄까지)")
elif cmd in ("mid", "pre"):
    import pandas as pd
    CH = J(K / "mcp_kic_precheck/kic_precheck/data/chain.json"); ST = {s["name"]: s["tick"] for s in CH["stages"]}
    POW = [t for n in CH["power_stages"] for t in ST[n]]; SEE = ("칩", "반도체 장비·소재", "서버·네트워크·부품")
    P = (1 + pd.read_csv(K / "net/backtest/returns_long.csv.gz", index_col=0, parse_dates=True, float_precision="round_trip")).cumprod().mul(100)
    i = P.index.get_loc(pd.Timestamp(d)); P = P.iloc[:i + 1]  # 그날 뒤 값은 메모리에서도 버림
    R = P.pct_change(fill_method=None) * 100; r = R.iloc[i]; spy = r["SPY"]
    if cmd == "mid":
        print(f"--- mid {d} SPY {spy:.2f}%")
        w = R.iloc[i - 250:i]
        for n in SEE:
            x = r[[t for t in ST[n] if t in r.index]].dropna(); adj = []
            for t in x.index:
                y = w[[t, "SPY"]].dropna()
                if len(y) > 60: adj.append(x[t] - y[t].cov(y["SPY"]) / y["SPY"].var() * spy)
            print(f"{n}: 평균 {x.mean():.2f}% · 시장 대비 {x.mean() - spy:.2f}%p · 민감도 뺀 값 {sum(adj) / len(adj):.2f} · 내린 종목 {(x < 0).sum()}/{len(x)} · 시장보다 더 빠진 {(x < spy).sum()}/{len(x)} · 나쁜 셋 " + ", ".join(f"{t} {v:.1f}" for t, v in x.sort_values()[:3].items()) + " · 좋은 둘 " + ", ".join(f"{t} {v:.1f}" for t, v in x.sort_values()[-2:].items()))
    else:
        print(f"--- pre {d} 전날까지 5거래일(그날 제외) SPY · 칩 · 서버·부품 · 전력 쪽")
        for dt, row in R.iloc[i - 5:i].iterrows():
            print(f"  {dt.date()} SPY {row['SPY']:.2f} 칩 {row[ST['칩']].mean():.2f} 서버 {row[[t for t in ST['서버·네트워크·부품'] if t in row.index]].mean():.2f} 전력 {row[[t for t in POW if t in row.index]].mean():.2f}")
elif cmd == "newsstat":
    n = J(A / "news" / f"{d}.json")
    print("--- newsstat", d, n["window_utc"], "\n단계별", n["by_stage"], "\n회사별", n["by_company"], "\n데이터센터 낱말 기사", n["dc_hit_records"], "· 58종목 기사", n["hit_records"], "· 제목", n["unique_titles"])
    for it in n["top"][12:]: print("  +", it["t"], it["src"], it["title"], it["ticks"])
elif cmd == "commit":
    p = H / "judgments" / f"{d}.json"; assert not p.exists(), "이미 씀"
    o = json.loads(sys.stdin.read()); o = {"date": d, **o, "written_at": now()}
    assert o["verdict"] in ("번진다", "안 번진다", "사람에게 넘긴다") and o["confidence"] in ("높음", "중간", "낮음")
    assert o["cause"] in ("칩 고유", "AI 투자 전반", "시장 전체", "전력 쪽 시작", "규칙이 잘못 고른 날")
    b = json.dumps(o, ensure_ascii=False, indent=1); p.write_text(b, encoding="utf-8")
    log(f"commit {d} verdict={o['verdict']} cause={o['cause']} conf={o['confidence']} tools={len(o['tools'])} sha={hashlib.sha256(b.encode()).hexdigest()[:12]}"); print("썼음", d, o["verdict"]); sys.exit()
log(f"{cmd} {d}")
