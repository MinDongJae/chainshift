# -*- coding: utf-8 -*-
"""해석 역할 도구 — 그날 전력 쪽 등락과 채점 값은 어디서도 찍지 않는다.
쓰는 법: tool.py pack D | mid D | pre D | newsstat D | rel D | write D (판정 JSON 을 표준 입력으로)
입력: agent/kic_agent/{cases,news} · net/backtest/returns_long.csv.gz · chain.json · relations edges
(B_agent/ag.py 의 같은 계산을 옮김. reveal · hist · midb 는 뺌)"""
import sys, json, re, hashlib, datetime
from pathlib import Path
import os
H = Path(__file__).parent; K = Path(os.environ.get("CHAINSHIFT_DATA", "data") + ""); A = K / "agent/kic_agent"
J = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))
now = lambda: datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(timespec="seconds")


def log(s):
    with open(H / "order_log.txt", "a", encoding="utf-8") as f:
        f.write(f"{now()} {s}\n")


def px():
    import pandas as pd
    p = (1 + pd.read_csv(K / "net/backtest/returns_long.csv.gz", index_col=0, parse_dates=True, float_precision="round_trip")).cumprod().mul(100)
    return pd, p, p.pct_change(fill_method=None) * 100


cmd, d = sys.argv[1], sys.argv[2]
assert re.fullmatch(r"\d{4}-\d\d-\d\d", d)
CH = J(K / "mcp_kic_precheck/kic_precheck/data/chain.json"); ST = {s["name"]: s["tick"] for s in CH["stages"]}
CHIP, MID = CH["stages"][0]["tick"], CH["stages"][1:3]  # 칩 · (장비·소재, 서버·부품). 뒤 세 단계가 전력 쪽
POW = [t for n in CH["power_stages"] for t in ST[n]]
if cmd == "pack":
    t = (A / "cases" / d / "materials.md").read_text(encoding="utf-8")
    for sec in re.split(r"(?m)^(?=## )", t):
        if re.match(r"## (그날 숫자|기사 제목|실적 공시 문장)", sec):  # 지난 사례 · 잣대 · 답하는 법 절은 안 찍음
            L = sec.splitlines(); F = [x for x in L if x.startswith("- F")]
            print("\n".join(x[:330] for x in L if not x.startswith("- F") or x in F[:8]))
            if F:
                print(f"(공시 문장 {len(F)}줄 중 8줄까지)")
elif cmd == "mid":
    pd, P, R = px(); r = R.loc[d]; spy = r["SPY"]
    c = r[CHIP].dropna()
    print(f"SPY {spy:.2f}% · 칩 평균 {c.mean():.2f}% (내린 종목 {(c < 0).sum()}/{len(c)}) · 칩 종목별 " + ", ".join(f"{t} {v:.1f}" for t, v in c.sort_values().items()))
    for s in MID:
        x = r[[t for t in s["tick"] if t in r.index]].dropna()
        print(f"{s['name']}: 평균 {x.mean():.2f}% · 시장 대비 {x.mean() - spy:.2f}%p · 시장보다 더 빠진 종목 {(x < spy).sum()}/{len(x)} · 가장 나쁜 셋 " + ", ".join(f"{t} {v:.1f}" for t, v in x.sort_values()[:3].items()))
elif cmd == "pre":
    pd, P, R = px(); i = P.index.get_loc(pd.Timestamp(d))
    print("전날까지 5거래일(그날 제외) 날짜·SPY·칩 평균·전력 쪽 평균:")
    for dt, row in R.iloc[i - 5:i].iterrows():
        print(f"  {dt.date()} SPY {row['SPY']:.2f} 칩 {row[CHIP].mean():.2f} 전력 {row[[t for t in POW if t in row.index]].mean():.2f}")
elif cmd == "newsstat":
    n = J(A / "news" / f"{d}.json")
    print("창", n["window_utc"], "단계별", n["by_stage"], "\n회사별", n["by_company"], "\n데이터센터 낱말 기사", n["dc_hit_records"], "· 58종목 기사", n["hit_records"], "· 제목", n["unique_titles"])
    for it in n["top"][12:40]:
        print("  +", it.get("t"), it["src"], it["title"][:140], it["ticks"])
elif cmd == "rel":
    REL = K / "relations"; k = 0
    for e in J(REL / "us/edges.json") + J(REL / "kr/edges.json"):
        pub = min(x["published_at"] for x in e["evidence"]); f, t = e["from"]["id"].split(":")[-1], e["to"]["id"].split(":")[-1]
        if e["status"] == "verified_original" and pub < d and (f in POW or t in POW):
            k += 1; print(f"  {e['edge_id']} {f}→{t} {e['relation']} 공시 {pub}: {e['what'][:80]}")
    print(f"  쓸 수 있는 전력 쪽 관계 {k}건")
elif cmd == "write":
    p = H / "judgments" / f"{d}.json"; p.parent.mkdir(exist_ok=True)
    assert not p.exists(), "이미 씀 — 덮어쓰지 않음"
    o = json.loads(sys.stdin.buffer.read().decode("utf-8")); o = {"date": d, **o, "written_at": now()}
    b = json.dumps(o, ensure_ascii=False, indent=1); p.write_text(b, encoding="utf-8")
    log(f"write {d} verdict={o['verdict']} cause={o['cause']} conf={o['confidence']} tools={len(o['tools'])} dropped={o['dropped']} sha={hashlib.sha256(b.encode()).hexdigest()[:12]}")
    print("썼음", p.name); sys.exit()
log(f"{cmd} {d}")
