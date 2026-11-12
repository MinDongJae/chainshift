# -*- coding: utf-8 -*-
"""점검 역할 도구 — 그날 전력 쪽 등락과 채점 값은 어디서도 찍지 않는다(pre 도 전력 칸 없음).
쓰는 법: tool.py day D | newsstat D | pre D | write D (판정 JSON 을 표준 입력으로)
입력: interpret/judgments · agent/kic_agent/{cases,news} · net/backtest/returns_long.csv.gz · chain.json
(interpret/tool.py 의 pack · mid · newsstat 계산을 옮김. rel 은 뺌)"""
import sys, json, re, hashlib, datetime
from difflib import SequenceMatcher
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


def pack(d):
    out = []
    t = (A / "cases" / d / "materials.md").read_text(encoding="utf-8")
    for sec in re.split(r"(?m)^(?=## )", t):
        if re.match(r"## (그날 숫자|기사 제목|실적 공시 문장)", sec):  # 지난 사례 · 잣대 절은 안 찍음
            L = sec.splitlines(); F = [x for x in L if x.startswith("- F")]
            out += [x[:330] for x in L if not x.startswith("- F") or x in F[:8]]
    return out


def close_utc(d):  # 미국 여름 시간이면 20시, 아니면 21시
    y, m, dd = map(int, d.split("-")); dt = datetime.date(y, m, dd)
    sun = lambda mo, n: [x for x in (datetime.date(y, mo, k) for k in range(1, 22)) if x.weekday() == 6][n - 1]
    return 20 if sun(3, 2) <= dt < sun(11, 1) else 21


cmd, d = sys.argv[1], sys.argv[2]
assert re.fullmatch(r"\d{4}-\d\d-\d\d", d)
CH = J(K / "mcp_kic_precheck/kic_precheck/data/chain.json")
CHIP, MID = CH["stages"][0]["tick"], CH["stages"][1:3]  # 칩 · (장비·소재, 서버·부품). 뒤 세 단계(전력 쪽)는 안 씀
if cmd == "day":
    o = J(H.parent / "interpret/judgments" / f"{d}.json")
    print("### 해석 판정", json.dumps({k: v for k, v in o.items() if k != "evidence"}, ensure_ascii=False))
    P_ = pack(d); n = J(A / "news" / f"{d}.json")
    cand = [("pack", x) for x in P_ if len(x) > 20] + [(f"news {it.get('t')} {it['src']}", it["title"]) for it in n["top"]]
    print(f"### 근거 대조 (마감 {close_utc(d)}:00 UTC · 겹친 글자 수는 가장 긴 이어진 겹침)")
    for i, e in enumerate(o["evidence"]):
        best = max(((SequenceMatcher(None, e["text"].lower(), c.lower(), autojunk=False).find_longest_match().size, w, c) for w, c in cand), default=(0, "", ""))
        print(f" E{i+1} [{e['src']} · {e['pub']}] {e['text'][:260]}\n    → 겹침 {best[0]}자 @ {best[1][:40]} :: {best[2][:110]}")
    print("### pack"); print("\n".join(P_))
    pd, P, R = px(); r = R.loc[d]; spy = r["SPY"]; c = r[CHIP].dropna()
    print(f"### mid\nSPY {spy:.2f}% · 칩 평균 {c.mean():.2f}% 가운데값 {c.median():.2f}% (내린 종목 {(c < 0).sum()}/{len(c)}) · " + ", ".join(f"{t} {v:.1f}" for t, v in c.sort_values().items()))
    for s in MID:
        x = r[[t for t in s["tick"] if t in r.index]].dropna().sort_values()
        print(f"{s['name']}: 평균 {x.mean():.2f}% · 시장 대비 평균 {x.mean() - spy:.2f}%p · 가운데값 {x.median() - spy:.2f}%p · 나쁜 셋 뺀 평균 {x[3:].mean() - spy:.2f}%p · 시장보다 더 빠진 {(x < spy).sum()}/{len(x)} · " + ", ".join(f"{t} {v:.1f}" for t, v in x.items()))
elif cmd == "newsstat":
    n = J(A / "news" / f"{d}.json"); cu = close_utc(d)
    print("창", n["window_utc"], "단계별", n["by_stage"], "\n회사별", n["by_company"], "\n데이터센터 낱말 기사", n["dc_hit_records"], "· 58종목 기사", n["hit_records"], "· 제목", n["unique_titles"], f"· 마감 {cu}:00 UTC")
    for it in n["top"][:45]:
        t = str(it.get("t") or ""); m = re.search(r"T?(\d\d):\d\d", t[8:] if len(t) > 10 else t)
        late = "마감뒤" if m and int(m.group(1)) >= cu else ""
        print("  +", t, late, it["src"], it["title"][:150], it["ticks"], "dc" if it.get("dc") else "")
elif cmd == "pre":
    pd, P, R = px(); i = P.index.get_loc(pd.Timestamp(d))
    print("전날까지 5거래일(그날 제외) 날짜·SPY·칩 평균 (전력 쪽 칸 없음):")
    for dt, row in R.iloc[i - 5:i].iterrows():
        print(f"  {dt.date()} SPY {row['SPY']:.2f} 칩 {row[CHIP].mean():.2f}")
elif cmd == "write":
    p = H / "judgments" / f"{d}.json"; p.parent.mkdir(exist_ok=True)
    assert not p.exists(), "이미 씀 — 덮어쓰지 않음"
    o = json.loads(sys.stdin.buffer.read().decode("utf-8")); o = {"date": d, **o, "written_at": now()}
    for k in ("interp", "recheck", "counter", "final", "cause", "changed", "why", "conf", "tools"):
        assert k in o, k
    assert o["final"] in ("번진다", "안 번진다", "넘긴다") and o["changed"] == (o["final"] != o["interp"])
    b = json.dumps(o, ensure_ascii=False, indent=1); p.write_text(b, encoding="utf-8")
    log(f"write {d} interp={o['interp']} final={o['final']} changed={o['changed']} cause={o['cause']} conf={o['conf']} tools={len(o['tools'])} sha={hashlib.sha256(b.encode()).hexdigest()[:12]}")
    print("썼음", p.name); sys.exit()
log(f"{cmd} {d}")
