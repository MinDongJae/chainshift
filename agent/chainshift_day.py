# -*- coding: utf-8 -*-
"""한 날을 처음부터 끝까지 도는 실행기 — 01 감지/계산 → 02 파급 → 03·04 해석 A·B(모델, 파일로 받음) → 05 일치 문 → 06 근거 검증 → 07 점검 보고서.
쓰는 법:  python -X utf8 chainshift_day.py 2026-10-22 [--a 해석A판정.json --b 해석B판정.json]
          python -X utf8 chainshift_day.py 2026-10-22 --holdings 내보유.csv --runs runs_mine   내 보유 파일로 같은 점검 보고서
            (csv 칸: ticker 와 value_usd(금액) 또는 shares(수량). 해석은 같은 날 runs_api 기록을 그대로 씀 — --reuse 로 바꿈)
  --a/--b 는 이미 써 둔 판정 파일을 03/04 output 형식으로 옮겨 넣는다(output 이 없을 때만, 내용은 '원본' 칸에 그대로).
  해석 답 파일이 없으면 입력 묶음만 쓰고 「대기」로 멈춘다(종료 코드 2). 답을 넣고 같은 명령을 다시 치면 이어 돈다.
  --live 1 을 붙이면 답 파일이 없는 해석을 모델에 직접 물어 받는다(model_call.py — 해석 A 는 claude-fable-5-2, 해석 B 는 claude-opus-5-5).
  --runs <폴더> 로 기록 폴더를 바꾼다(기본 runs).
--live 가 없으면 모델을 부르지 않는다. 코드 단계는 그날(뉴욕 종가)까지 자료만 쓴다.
읽는 것(읽기만):
  A3_hedge/hedge.py (계산부만 불러 씀 — 그 파일의 fit · 헤지 수단 · 자료 읽기) · A3_hedge/etf_long_ret.csv
  $CHAINSHIFT_DATA/net/backtest/returns_long.csv.gz · mcp_kic_precheck/kic_precheck/{regime_monitor.py,data/chain.json}
  net/returns.csv.gz · net/universe.json · relations/{us,kr}/edges.json (B_agent/exp1.py 와 같은 경로 · 같은 규칙)
  agent/kic_agent/news/<날>.json (B2_roles/interpret/tool.py 가 읽는 기사 자료 — 제목 · GDELT 수집 시각)
쓰는 것: runs/<날>/NN_*.json · sheet.md · trace.md"""
import sys, json, re, time, hashlib, datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np, pandas as pd

HERE = Path(__file__).resolve().parent
import os
K = Path(os.environ.get("CHAINSHIFT_DATA", "data") + "")
HEDGE_PY = HERE.parent / "analysis/A3_hedge/hedge.py"
REL = K / "relations"
NEWS = K / "agent/kic_agent/news"
NY, UTC, KST = ZoneInfo("America/New_York"), datetime.timezone.utc, ZoneInfo("Asia/Seoul")
J = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))
M = lambda x: round(float(x) / 1e6, 1)          # 백만 달러
P = lambda x: round(float(x) * 100, 2)          # %
L_HEDGE = {"SPY": "시장(SPY)", "OWN": "자기 업종 펀드", "SMH": "반도체 펀드(SMH)"}
CONFIRM = ("번진다", "안 번진다")


def load_hedge():
    """hedge.py 의 계산부(자료 읽기 · fit · run 정의)까지만 실행한다. 결과 파일을 쓰는 뒷부분은 실행하지 않는다."""
    src = HEDGE_PY.read_text(encoding="utf-8"); cut = src.index("\nout = {")
    ns = {"__file__": str(HEDGE_PY), "__name__": "hedge_calc"}
    exec(compile(src[:cut], str(HEDGE_PY), "exec"), ns)
    return ns


def read_holdings(path, d):
    """내 보유 파일(csv: 종목, 금액 또는 수량) → {종목: 금액(달러)}. 금액 칸 이름은 value_usd · 금액 · value, 수량 칸은 shares · 수량.
    수량만 있으면 그날 종가를 야후 파이낸스에서 받아 곱한다(망 필요)."""
    import csv
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    key = lambda r, names: next((r[k] for k in names if k in r and str(r[k]).strip()), None)
    out, need = {}, {}
    for r in rows:
        t = (key(r, ("ticker", "종목", "symbol")) or "").strip().upper()
        if not t: continue
        v = key(r, ("value_usd", "금액", "value"))
        if v is not None: out[t] = out.get(t, 0.0) + float(str(v).replace(",", ""))
        elif key(r, ("shares", "수량")) is not None: need[t] = need.get(t, 0.0) + float(str(key(r, ("shares", "수량"))).replace(",", ""))
    if need:
        import yfinance as yf
        end = (pd.Timestamp(d) + pd.Timedelta(days=1)).strftime("%Y-%m-%d"); start = (pd.Timestamp(d) - pd.Timedelta(days=10)).strftime("%Y-%m-%d")
        px = yf.download(list(need), start=start, end=end, auto_adjust=False, progress=False, threads=False)["Close"]
        px = px.to_frame(list(need)[0]) if isinstance(px, pd.Series) else px
        for t, n in need.items():
            c = px[t].dropna() if t in px else pd.Series(dtype=float)
            if len(c): out[t] = out.get(t, 0.0) + n * float(c.iloc[-2] if c.index[-1] >= pd.Timestamp(d) and len(c) > 1 else c.iloc[-1])   # 그날 앞 종가 × 수량
    return out


def hedge_day(ns, ticks, i):
    """hedge.py run() 의 날 i 한 칸 — 그날 앞 250거래일 회귀, 그날 수단 등락으로 남는 손익."""
    W, R, E, PX, HOLD, SEC, ETF = ns["W"], ns["R"], ns["E"], ns["PX"], ns["HOLD"], ns["SEC"], ns["SEC_ETF"]
    tk = [t for t in ticks if t in PX]; w = slice(i - W, i + 1)
    a = R[tk].to_numpy(float)[w]; u = np.array([HOLD[t] for t in tk]); etf = E[[ETF[SEC[t]] for t in tk]].to_numpy(float)[w]
    ok = ~np.isnan(a).any(axis=0); y = a[:, ok] @ u[ok]
    F = {"SPY": E["SPY"].to_numpy()[w], "SMH": E["SMH"].to_numpy()[w], "OWN": etf[:, ok] @ (u[ok] / u[ok].sum())}
    left, sse = {}, {}
    for k, cols in ns["HEDGES"].items():
        X = np.column_stack([F[c] for c in cols]); h, s = ns["fit"](X[:-1], y[:-1], X[-1]); left[k] = y[-1] - h; sse[k] = s
    pick = min(ns["PICK"], key=lambda k: sse[k])
    return {"act": float(y[-1]), "left": left, "pick": pick, "n": int((ok & (u > 0)).sum()), "usd": float(u[ok].sum())}


def s01(d, ns):
    RM, CH, PX, R = ns["RM"], ns["CH"], ns["PX"], ns["R"]
    ts = pd.Timestamp(d); assert ts in R.index, "거래일이 아님"
    pxd = PX.loc[:ts]                                                    # 그날 뒤 값은 버림
    h = RM.monitor_history(pxd[ns["CHIPS"] + ns["POWERS"] + ["SPY"]], ns["CHIPS"], ns["POWERS"], RM.MonitorConfig(hysteresis=0.03)).iloc[-1]
    assert bool(h["chip_shock"]) == bool(ns["H"].loc[ts, "chip_shock"]), "그날까지 자료로 낸 감지가 전체 자료로 낸 것과 다름"
    i = R.index.get_loc(ts); r = R.iloc[i]; spy = float(r["SPY"]); HOLD = ns["HOLD"]
    stages = []
    for s in CH["stages"]:
        tk = [t for t in s["tick"] if t in r.index and pd.notna(r[t])]
        stages.append({"단계": s["name"], "종목 수": len(tk), "보유 금액(백만 달러)": M(sum(HOLD[t] for t in tk)), "평균 등락(%)": P(r[tk].mean()),
                       "시장 대비(%p)": P(r[tk].mean() - spy), "시장보다 더 빠진 종목": f"{int((r[tk] < spy).sum())}/{len(tk)}",
                       "재현 손익(백만 달러)": M(sum(HOLD[t] * r[t] for t in tk))})
    hedge = []
    for name, ticks in ns["SCOPES"].items():
        if sum(HOLD.get(t, 0.0) for t in ticks) <= 0: continue
        x = hedge_day(ns, ticks, i)
        hedge.append({"범위": re.sub(r"\d+종목 ", "", name) if ns.get("MINE") else name, "종목 수": x["n"], "보유 금액(백만 달러)": M(x["usd"]), "재현 손익(백만 달러)": M(x["act"]),
                      "헤지 뒤 남는 손익(백만 달러)": {L_HEDGE[k]: M(x["left"][k]) for k in L_HEDGE},
                      "지난 250거래일로 고른 수단": L_HEDGE[x["pick"]], "그 수단으로 남는 손익(백만 달러)": M(x["left"][x["pick"]])})
    # 자기 검사: 날 한 칸 계산이 hedge.py run() 전체 계산의 같은 날 값과 같은가
    if sum(HOLD.get(t, 0.0) for t in ns["POWERS"]) > 0:
      act, res, pick, _, _ = ns["run"](ns["POWERS"]); x = hedge_day(ns, ns["POWERS"], i)
      assert abs(act[i] - x["act"]) < 1e-3 and all(abs(res[k][i] - x["left"][k]) < 1e-3 for k in L_HEDGE) and pick[i] == x["pick"]
    shock = bool(h["eligible"]) and bool(h["chip_shock"])
    return {"date": d, "칩 충격일": shock,
            "감지": {"규칙": "칩 9종목의 시장 몫을 뺀 등락이 그달 앞 자료 하위 5% 이하 (kic_precheck/regime_monitor.py, short_panel.py 와 같은 호출)",
                   "칩 등락(시장 몫 뺀 값, %)": P(h["chip_resid"]), "그달 문턱(%)": P(h["shock_cut"]), "문턱을 정한 자료": f"{h['calibration_start']} ~ {h['calibration_end']}",
                   "칩 평균 등락(%)": P(h["chip_return"]), "SPY(%)": P(spy), "쓴 주가": f"~ {d} (그날 뒤 값은 읽은 뒤 버림)"},
            "단계별": stages, "58종목 재현 손익(백만 달러)": M(sum(HOLD[t] * r[t] for t in HOLD if t in r.index and pd.notna(r[t]))),
            "헤지": hedge, "보유 기준": (f"내 보유 파일 {ns['MINE_NAME']} — 58종목 안 {sum(1 for t in ns['MINE'] if t in ns['HOLD'])}종목, 밖 {len(ns['MINE_OUT'])}종목({', '.join(ns['MINE_OUT'][:8])}) 은 단계 · 헤지 계산에서 뺌"
                                       if ns.get("MINE") else f"공개 보유(13F) {CH['asof']}")}


def s02(d, ns):
    """B_agent/exp1.py 와 같은 규칙: 원문 확인된 관계 가운데 그날 앞에 공개됐고 한쪽만 58종목인 것."""
    S58 = ns["CH"]["holdings_usd"]
    held = dict(ns["MINE"]) if ns.get("MINE") else {v["ticker"]: v["value"] for v in J(K / "net/universe.json")["companies"].values() if v.get("ticker")}
    px = (1 + pd.read_csv(K / "net/returns.csv.gz", index_col=0, parse_dates=True, float_precision="round_trip")).cumprod().mul(100).loc[:d]; r = px.pct_change(fill_method=None).iloc[-1] if str(px.index[-1].date()) == d else pd.Series(dtype=float)
    add, outside, n_all = {}, [], 0
    for e in J(REL / "us/edges.json") + J(REL / "kr/edges.json"):
        if e["status"] != "verified_original": continue
        n_all += 1; pub = min(x["published_at"] for x in e["evidence"])
        if not pub < d: continue
        f, t = e["from"]["id"].split(":")[-1], e["to"]["id"].split(":")[-1]
        if (f in S58) == (t in S58): continue
        o, inn = (t, f) if f in S58 else (f, t); ev = min(e["evidence"], key=lambda x: x["published_at"])
        row = {"관계 번호": e["edge_id"], "58종목 안": inn, "밖": o, "관계": e["relation"], "공개일": pub, "공시 문장": ev["quote"][:260], "주소": ev["url"]}
        (add.setdefault(o, []) if o in held and o in r.index and pd.notna(r[o]) else outside).append(row)
    comp = [{"회사": t, "보유 금액(백만 달러)": M(held[t]), "그날 등락(%)": P(r[t]), "재현 손익(백만 달러)": M(held[t] * r[t]), "까닭(공시)": rows} for t, rows in add.items()]
    return {"date": d, "원문 확인된 관계 전체": n_all, "그날 앞에 공개돼 쓸 수 있는 관계": sum(len(v) for v in add.values()) + len(outside),
            "같이 볼 회사(보유 중)": comp, "더한 재현 손익(백만 달러)": M(sum(held[t] * r[t] for t in add)),
            "보유 밖 회사(이름만)": sorted({x["밖"] for x in outside}), "주가": "net/returns.csv.gz (~2026-10-29)" if len(r) else "그날 값 없음"}


def news_list(d):
    """기사 자료의 제목 · 수집 시각(UTC 15분 칸) → 뉴욕 시각 · 마감(16:00) 앞뒤."""
    close = datetime.datetime.fromisoformat(d + "T16:00").replace(tzinfo=NY); out = []
    for k, it in enumerate(J(NEWS / f"{d}.json")["top"], 1):
        t = datetime.datetime.strptime(it["t"], "%Y%m%d%H%M%S").replace(tzinfo=UTC)
        out.append({"번호": f"N{k}", "제목": it["title"], "출처": it["src"], "공개 시각(뉴욕)": t.astimezone(NY).strftime("%Y-%m-%d %H:%M"),
                    "공개 시각(UTC)": t.strftime("%Y-%m-%d %H:%M"), "마감 뒤": t >= close, "주소": it["url"]})
    return out


def interpret_input(d, o1, o2, news, who):
    pre = [n for n in news if not n["마감 뒤"]]
    L = [f"# 해석 {who} 입력 묶음 — {d} (미국 장 마감 16:00 뉴욕까지)", "",
         "물음: 그날 칩 하락이 전력 쪽(전력·냉각 설비 · 데이터센터 공사 · 발전)으로 번졌나. 다른 해석의 답은 보지 않는다.",
         "답 형식(JSON): {\"까닭 갈래\": \"칩 고유 | AI 투자 전반 | 시장 전체 | 전력 쪽 시작 | 규칙이 잘못 고른 날\", \"근거 문장\": [{\"text\": \"\", \"출처\": \"N번호 또는 계산\", \"공개 시각\": \"\"}], \"판정\": \"번진다 | 안 번진다 | 넘긴다\", \"확신\": \"높음 | 중간 | 낮음\"}",
         "", "## 그날 등락 표 (01 — 코드)", f"SPY {o1['감지']['SPY(%)']}% · 칩 시장 몫 뺀 등락 {o1['감지']['칩 등락(시장 몫 뺀 값, %)']}% (문턱 {o1['감지']['그달 문턱(%)']}%)", "",
         "| 단계 | 종목 | 평균 등락 % | 시장 대비 %p | 시장보다 더 빠진 종목 |", "|---|---|---|---|---|"]
    L += [f"| {s['단계']} | {s['종목 수']} | {s['평균 등락(%)']} | {s['시장 대비(%p)']} | {s['시장보다 더 빠진 종목']} |" for s in o1["단계별"][:3]]
    L += ["(전력 쪽 세 단계의 그날 등락은 물음의 답이라 싣지 않는다)", "", f"## 기사 제목 · 시각 — 장 마감 전 {len(pre)}건 (마감 뒤 {len(news) - len(pre)}건은 「마감 시각 거름」이 뺌)"]
    L += [f"- {n['번호']} {n['공개 시각(뉴욕)']} {n['출처']} 「{n['제목']}」" for n in pre]
    L += ["", f"## 같이 볼 회사 (02 — 공시 관계, 그날 앞 공개분 {o2['그날 앞에 공개돼 쓸 수 있는 관계']}건)"]
    L += [f"- {c['회사']}: " + " / ".join(f"{x['관계 번호']} {x['58종목 안']}–{x['밖']} {x['관계']} (공개 {x['공개일']})" for x in c["까닭(공시)"]) for c in o2["같이 볼 회사(보유 중)"]]
    return "\n".join(L) + "\n"


def convert(src, who):
    """B2_roles 판정 파일 → 실행기 output 형식. 내용은 바꾸지 않고 '원본' 칸에 통째로 둔다."""
    raw = Path(src).read_bytes(); o = json.loads(raw.decode("utf-8")); ev = []
    for e in o["evidence"]:
        if isinstance(e, dict): ev.append({"text": e["text"], "출처": e.get("src"), "공개 시각": e.get("pub")})
        else:
            m = re.match(r"(.+?) (\d{4}-\d\d-\d\d(?: [\d:]+ UTC)?) 「(.+)」(.*)$", e)
            ev.append({"text": m.group(3), "출처": m.group(1), "공개 시각": m.group(2), "덧말": m.group(4)} if m else {"text": e, "출처": e.split(":")[0], "공개 시각": None})
    return {"date": o["date"], "역할": f"해석 {who}", "까닭 갈래": o["cause"], "근거 문장": ev, "판정": o["verdict"], "확신": o["confidence"],
            "원본": {"경로": Path(src).as_posix(), "원본을 쓴 시각": o["written_at"], "sha256": hashlib.sha256(raw).hexdigest(),
                   "옮긴 시각": datetime.datetime.now(KST).isoformat(timespec="seconds"), "내용": o}}


MODELS = {"A": "claude-fable-5-2", "B": "claude-opus-5-5"}   # 두 해석은 서로 다른 모델이 맡는다


def live(d, inp, who, model):
    """03 · 04 — 입력 묶음을 모델에 직접 보내 답을 받는다(model_call.py)."""
    sys.path.insert(0, str(HERE)); import model_call
    ans, log = model_call.ask(Path(inp).read_text(encoding="utf-8"), model)
    ev = [e if isinstance(e, dict) else {"text": str(e), "출처": None, "공개 시각": None} for e in ans["근거 문장"]]
    return {"date": d, "역할": f"해석 {who}", "까닭 갈래": ans["까닭 갈래"], "근거 문장": ev, "판정": ans["판정"], "확신": ans["확신"],
            "원본": {"경로": "실행기가 직접 부름", "원본을 쓴 시각": datetime.datetime.now(KST).isoformat(timespec="seconds"), "모델": model,
                   "실제로 답한 모델": log["실제로 답한 모델"], "부른 길": log.get("길"), "토큰": log.get("토큰"), "걸린 초": log["걸린 초"], "입력": Path(inp).name,
                   "내용": {"counter": ans.get("반대 근거"), "note": ans.get("덧말"), "답 원문": log["답 원문"]}}}


norm = lambda s: re.sub(r"[^a-z0-9가-힣]", "", s.lower())
CALC = ("mid", "pre", "newsstat")


def hygiene(ans, news):
    """「마감 시각 거름」: 근거마다 기사 자료에 제목이 있는지 · 공개 시각이 16:00 뉴욕 뒤인지 가른다."""
    rows = []
    for k, e in enumerate(ans["근거 문장"], 1):
        et = norm(e["text"]); hit = next((n for n in news if norm(n["제목"]) in et or (len(et) >= 25 and et in norm(n["제목"]))), None)
        calc = (e.get("출처") or "").strip().split("(")[0].split(" ")[0].rstrip(":") in CALC
        row = {"순번": k, "근거": e["text"], "해석이 적은 출처": e.get("출처"), "해석이 적은 공개 시각": e.get("공개 시각")}
        if hit:
            row.update({"종류": "기사", "기사 자료 번호": hit["번호"], "공개 시각(뉴욕)": hit["공개 시각(뉴욕)"], "주소": hit["주소"], "기사 출처": hit["출처"],
                        "남김": not hit["마감 뒤"], "까닭": "장 마감(16:00 뉴욕) 뒤 공개" if hit["마감 뒤"] else "기사 자료에 있고 마감 전"})
        elif calc: row.update({"종류": "계산", "남김": True, "까닭": "코드 값(기사 아님) — 거름 대상 아님"})
        else: row.update({"종류": "기사", "남김": False, "까닭": "기사 자료에 제목이 없음 — 있는지 · 언제 나왔는지 확인 못 함"})
        rows.append(row)
    art = [r for r in rows if r["종류"] == "기사"]; drop = [r for r in art if not r["남김"]]
    return {"근거": rows, "기사 근거": len(art), "뺀 근거": len(drop), "마감 뒤라서 뺌": sum("마감" in r["까닭"] for r in drop),
            "자료에 없어서 뺌": sum("없음" in r["까닭"] for r in drop), "절반 넘게 빠짐": len(art) == 0 or len(drop) / len(art) > 0.5}


def gate(a, b):
    same = a["판정"] == b["판정"] and a["판정"] in CONFIRM
    side = {w: {"판정": x["판정"], "까닭 갈래": x["까닭 갈래"], "확신": x["확신"], "근거": [e["text"] for e in x["근거 문장"]],
                "스스로 적은 반대 근거": x["원본"]["내용"].get("counter"), "스스로 적은 덧말": x["원본"]["내용"].get("note")} for w, x in (("해석 A", a), ("해석 B", b))}
    if same: line = f"두 해석이 같은 확정 「{a['판정']}」"
    elif a["판정"] == b["판정"]: line = f"두 해석 모두 「{a['판정']}」 — 확정이 아님"
    else: line = f"판정이 갈림 — 해석 A 「{a['판정']}」(까닭 {a['까닭 갈래']} · 확신 {a['확신']}) 대 해석 B 「{b['판정']}」(까닭 {b['까닭 갈래']} · 확신 {b['확신']})"
    return {"규칙": "두 해석의 판정이 같은 확정(번진다 · 안 번진다)이면 통과, 아니면 사람에게 넘김", "결과": "통과" if same else "사람에게 넘김",
            "같이 낸 판정": a["판정"] if same else None, "갈린 지점 한 줄": line, "까닭 갈래 같음": a["까닭 갈래"] == b["까닭 갈래"], "담당자가 받는 것": side}


def sheet(d, o1, o2, g, h, final):
    f = o1["감지"]; L = [f"# 점검 보고서 — {d} (미국) 칩 충격일", "",
        f"**상태: {final['상태']}** — {final['한 줄']}", "",
        "## 1. 그날 숫자 (코드 · " + ("내 보유 파일 기준" if o1["보유 기준"].startswith("내 보유") else "공개 보유 기준") + " 재현)", f"- 칩 9종목 시장 몫 뺀 등락 {f['칩 등락(시장 몫 뺀 값, %)']}% (그달 문턱 {f['그달 문턱(%)']}%) · SPY {f['SPY(%)']}% · " + ("내 보유" if o1["보유 기준"].startswith("내 보유") else "58종목") + f" 재현 손익 {o1['58종목 재현 손익(백만 달러)']}백만 달러",
        "", "| 단계 | 종목 | 보유(백만 달러) | 평균 등락 % | 시장 대비 %p | 재현 손익(백만 달러) |", "|---|---|---|---|---|---|"]
    L += [f"| {s['단계']} | {s['종목 수']} | {s['보유 금액(백만 달러)']} | {s['평균 등락(%)']} | {s['시장 대비(%p)']} | {s['재현 손익(백만 달러)']} |" for s in o1["단계별"]]
    L += ["", f"같이 볼 회사(공시 거래 관계, 그날 앞 공개분): " + (" · ".join(f"{c['회사']} {c['그날 등락(%)']}% ({c['까닭(공시)'][0]['관계 번호']}, 공개 {c['까닭(공시)'][0]['공개일']})" for c in o2["같이 볼 회사(보유 중)"]) or "없음") + f" — 더한 재현 손익 {o2['더한 재현 손익(백만 달러)']}백만 달러",
          "", "## 2. 번졌나 — " + final["상태"], f"- 일치 문: {g['갈린 지점 한 줄']}"]
    if final["상태"] == "확정": L.append(f"- 판정 「{g['같이 낸 판정']}」 · 까닭 갈래 A 「{g['담당자가 받는 것']['해석 A']['까닭 갈래']}」 / B 「{g['담당자가 받는 것']['해석 B']['까닭 갈래']}」")
    else:
        L += ["", "담당자가 받는 것 — 두 해석 나란히", "", "| | 해석 A | 해석 B |", "|---|---|---|"]
        A, B = g["담당자가 받는 것"]["해석 A"], g["담당자가 받는 것"]["해석 B"]
        cell = lambda s: str(s or "").replace("|", "/").replace("\n", " ")
        L += [f"| {k} | {cell(A[k])} | {cell(B[k])} |" for k in ("판정", "까닭 갈래", "확신", "스스로 적은 반대 근거")]
        L += [f"| 근거 검증 뒤 남은 기사 근거 | {h['해석 A']['기사 근거'] - h['해석 A']['뺀 근거']}/{h['해석 A']['기사 근거']} | {h['해석 B']['기사 근거'] - h['해석 B']['뺀 근거']}/{h['해석 B']['기사 근거']} |"]
    L += ["", "남은 근거 문장 (기사 자료 번호 · 공개 시각은 뉴욕)"]
    seen = {}
    for w in ("해석 A", "해석 B"):
        for r in h[w]["근거"]:
            if r["종류"] == "기사" and r["남김"]: seen.setdefault(r["기사 자료 번호"], [r, []])[1].append(w[-1])
    L += [f"- [{n}] {r['공개 시각(뉴욕)']} {r['기사 출처']} 「{r['근거'] if len(r['근거']) < 140 else r['근거'][:140]}」 (쓴 해석: {'·'.join(ws)}) {r['주소']}" for n, (r, ws) in seen.items()] or ["- 없음"]
    L += ["", "「마감 시각 거름」이 뺀 근거"]
    L += [f"- 해석 {w[-1]} 근거 {r['순번']}: 「{r['근거'][:110]}」 — {r['까닭']}" + (f" ({r['공개 시각(뉴욕)']} 뉴욕)" if r.get("공개 시각(뉴욕)") else "") for w in ("해석 A", "해석 B") for r in h[w]["근거"] if not r["남김"]] or ["- 없음"]
    L += ["", "## 3. 헤지 수단별 남는 손익 (코드 · 그날 앞 250거래일 회귀, 백만 달러)", "", "| 범위 | 재현 손익 | 시장(SPY) | 자기 업종 펀드 | 반도체 펀드(SMH) | 지난 250거래일로 고른 수단 → 남는 손익 |", "|---|---|---|---|---|---|"]
    L += [f"| {x['범위']} ({x['종목 수']}종목) | {x['재현 손익(백만 달러)']} | " + " | ".join(str(x["헤지 뒤 남는 손익(백만 달러)"][k]) for k in L_HEDGE.values()) + f" | {x['지난 250거래일로 고른 수단']} → {x['그 수단으로 남는 손익(백만 달러)']} |" for x in o1["헤지"]]
    L += ["", "(종목 수가 단계 표보다 적은 줄은 그날 앞 250거래일 값이 다 있는 종목만 회귀에 넣어서다)"]
    L += ["", "## 4. 한도 칸 (담당자 입력)", "- 하루 손실 한도: ________ 백만 달러 (담당자 입력 — 실행기는 값을 지어내지 않음)", f"- 견줄 값: 전력 쪽 {'내 보유' if o1['보유 기준'].startswith('내 보유') else '19종목'} 재현 손익 {next((x['재현 손익(백만 달러)'] for x in o1['헤지'] if x['범위'].startswith('전력 쪽')), 0.0)}백만 달러 · 한도 초과 여부: 한도를 넣으면 계산",
          "", f"보유 기준 {o1['보유 기준']}{'' if o1['보유 기준'].startswith('내 보유') else ' — 실제 계좌가 아님'}. 해석 A · B 는 모델(Claude 개체)의 답을 파일로 받은 것이고 나머지는 코드."]
    return "\n".join(L) + "\n"


def main():
    d = sys.argv[1]; assert re.fullmatch(r"\d{4}-\d\d-\d\d", d)
    opt = dict(zip(sys.argv[2::2], sys.argv[3::2])); RUN = HERE / opt.get("--runs", "runs") / d; RUN.mkdir(parents=True, exist_ok=True)
    tr = [f"# 단계별 기록 — {d}", "", "| 단계 | 누가 | 받은 것 | 한 일 | 낸 것 | 걸린 시간 |", "|---|---|---|---|---|---|"]
    W = lambda name, o: (RUN / name).write_text(o if isinstance(o, str) else json.dumps(o, ensure_ascii=False, indent=1), encoding="utf-8")
    T = lambda t0: f"{time.time() - t0:.1f}초"
    fin = lambda: W("trace.md", "\n".join(tr) + "\n")

    t0 = time.time(); ns = load_hedge()
    if "--holdings" in opt:   # 내 보유 파일로 같은 점검 — 단계 · 헤지 · 같이 볼 회사의 금액을 내 보유로 바꾼다. 해석(03 · 04)은 그날 시장 판단이라 같은 날 기록을 그대로 쓴다
        mine = read_holdings(opt["--holdings"], d); ns["MINE"], ns["MINE_NAME"] = mine, Path(opt["--holdings"]).name
        ns["MINE_OUT"] = sorted(t for t in mine if t not in ns["HOLD"]); ns["HOLD"] = {t: mine.get(t, 0.0) for t in ns["HOLD"]}
        src = HERE / opt.get("--reuse", "runs_api") / d
        for f in ("03_interpret_A.output.json", "04_interpret_B.output.json", "06_check.output.json"):
            if (src / f).exists() and not (RUN / f).exists(): (RUN / f).write_bytes((src / f).read_bytes())
    o1 = s01(d, ns); W("01_detect.json", o1); f = o1["감지"]; pw = next(x for x in o1["헤지"] if x["범위"].startswith("전력 쪽"))
    tr.append(f"| 01 감지·계산 | 코드 | 주가 ~{d} · {o1['보유 기준'][:40]} | 칩 충격일 규칙 · 단계별 등락 · 재현 손익 · 헤지 회귀 | 칩 {f['칩 등락(시장 몫 뺀 값, %)']}% ≤ 문턱 {f['그달 문턱(%)']}% → 충격일 {'맞음' if o1['칩 충격일'] else '아님'} · {'내 보유' if o1['보유 기준'].startswith('내 보유') else '58종목'} {o1['58종목 재현 손익(백만 달러)']}백만 달러 · 전력 쪽 {pw['재현 손익(백만 달러)']} | {T(t0)} |")
    if not o1["칩 충격일"]:
        tr.append("| — | 코드 | | 충격일이 아니라 여기서 끝냄 | 점검 보고서 없음 | |"); fin(); print("칩 충격일 아님 — 끝"); return 0

    t0 = time.time(); o2 = s02(d, ns); W("02_spread.json", o2); cs = o2["같이 볼 회사(보유 중)"]
    tr.append(f"| 02 파급 | 코드 | 공시 거래 관계 장부(원문 확인 {o2['원문 확인된 관계 전체']}건) | 그날 앞 공개 · 한쪽만 58종목인 관계로 넓힘 | 쓸 수 있는 관계 {o2['그날 앞에 공개돼 쓸 수 있는 관계']}건 → 같이 볼 회사 {len(cs)}곳({' · '.join(c['회사'] + ' ' + str(c['그날 등락(%)']) + '%' for c in cs)}) · 더한 손익 {o2['더한 재현 손익(백만 달러)']}백만 달러 | {T(t0)} |")

    news = news_list(d); ans = {}; wait = []
    for no, who in (("03", "A"), ("04", "B")):
        t0 = time.time(); W(f"{no}_interpret_{who}.input.md", interpret_input(d, o1, o2, news, who)); out = RUN / f"{no}_interpret_{who}.output.json"
        if not out.exists() and f"--{who.lower()}" in opt: W(out.name, convert(opt[f"--{who.lower()}"], who))
        if not out.exists() and "--live" in opt:
            W(out.name, live(d, RUN / f"{no}_interpret_{who}.input.md", who, opt.get(f"--model-{who.lower()}", MODELS[who])))
        if not out.exists():
            wait.append(out.name); tr.append(f"| {no} 해석 {who} | 모델 | 입력 묶음 {no}_interpret_{who}.input.md | — | **대기** — {out.name} 이 아직 없음 | {T(t0)} |"); continue
        a = ans[who] = J(out)
        if a["원본"].get("모델"):
            tr.append(f"| {no} 해석 {who} | 모델(실행기가 직접 부름 · {a['원본'].get('부른 길') or 'cli'} · {a['원본']['모델']}) | 등락 표 · 마감 전 기사 {sum(not n['마감 뒤'] for n in news)}건 · 같이 볼 회사 {len(cs)}곳 | 입력 묶음을 모델에 보내 답을 받음 (부른 시각 {a['원본']['원본을 쓴 시각']}) | 까닭 「{a['까닭 갈래']}」 · 판정 「{a['판정']}」 · 확신 {a['확신']} · 근거 {len(a['근거 문장'])}줄 | 모델 {a['원본']['걸린 초']}초 |"); continue
        tr.append(f"| {no} 해석 {who} | 모델(파일로 받음) | 등락 표 · 마감 전 기사 {sum(not n['마감 뒤'] for n in news)}건 · 같이 볼 회사 {len(cs)}곳 | 저장된 답을 읽음 (원본 {a['원본']['경로'].split('analysis/')[-1]}, 쓴 시각 {a['원본']['원본을 쓴 시각']}) | 까닭 「{a['까닭 갈래']}」 · 판정 「{a['판정']}」 · 확신 {a['확신']} · 근거 {len(a['근거 문장'])}줄 | 읽기 {T(t0)} (모델이 쓴 시간은 잰 값 없음) |")
    if wait:
        fin(); print("대기 —", ", ".join(wait), "를 넣고 다시 실행"); return 2

    t0 = time.time(); g = gate(ans["A"], ans["B"]); W("05_gate.json", g)
    tr.append(f"| 05 일치 문 | 코드 | 두 해석의 판정 | 같은 확정인지 견줌 | {g['결과']} — {g['갈린 지점 한 줄']} | {T(t0)} |")

    t0 = time.time(); h = {f"해석 {w}": hygiene(ans[w], news) for w in "AB"}
    chk = RUN / "06_check.output.json"; mc = J(chk) if chk.exists() else None
    h["규칙"] = "「마감 시각 거름」 — 기사 근거가 기사 자료에 있고 공개 시각이 그날 16:00(뉴욕) 앞일 때만 남김. 한 해석이라도 기사 근거가 절반 넘게 빠지면 넘김"
    h["기사 자료"] = f"agent/kic_agent/news/{d}.json 의 제목 {len(news)}건(마감 뒤 {sum(n['마감 뒤'] for n in news)}건)"; h["절반 넘게 빠진 해석"] = [w for w in ("해석 A", "해석 B") if h[w]["절반 넘게 빠짐"]]
    h["모델 점검 답"] = mc or "없음 — 코드 거름만 적용 (06_check.input.md 는 써 둠)"
    W("06_check.input.md", f"# 점검 입력 묶음 — {d}\n\n코드가 거른 뒤 남은 근거만으로 두 해석의 판정이 서는지 본다. 답: {{\"판정\": \"그대로 | 넘긴다\", \"까닭\": \"\"}}\n\n" + "\n".join(
        f"## {w} — 판정 「{ans[w[-1]]['판정']}」\n" + "\n".join(f"- [{'남김' if r['남김'] else '뺌'}] {r['근거'][:200]} — {r['까닭']}" for r in h[w]["근거"]) for w in ("해석 A", "해석 B")) + "\n")
    W("06_hygiene.json", h); dr = [f"{w[-1]} {h[w]['뺀 근거']}/{h[w]['기사 근거']}" for w in ("해석 A", "해석 B")]
    tr.append(f"| 06 점검·근거 검증 | 코드 (+모델 입력 묶음) | 두 해석의 근거 {sum(len(h[w]['근거']) for w in ('해석 A', '해석 B'))}줄 · 기사 자료 {len(news)}건 | 「마감 시각 거름」 — 제목 대조 · 16:00 뉴욕 견줌 | 기사 근거 중 뺀 것 {' · '.join(dr)} → " + ("절반 넘게 빠진 해석 " + "·".join(h["절반 넘게 빠진 해석"]) + " → 넘김" if h["절반 넘게 빠진 해석"] else "절반 안 넘음") + f" | {T(t0)} |")

    t0 = time.time(); why = []
    if g["결과"] != "통과": why.append("일치 문: " + g["갈린 지점 한 줄"])
    if h["절반 넘게 빠진 해석"]: why.append("근거 검증: " + "·".join(h["절반 넘게 빠진 해석"]) + " 기사 근거가 절반 넘게 빠짐")
    if mc and mc.get("판정") == "넘긴다": why.append("모델 점검: " + str(mc.get("까닭")))
    final = {"date": d, "상태": "사람에게 넘김" if why else "확정", "판정": None if why else g["같이 낸 판정"],
             "한 줄": " / ".join(why) if why else f"두 해석이 같은 확정 「{g['같이 낸 판정']}」, 근거 검증 통과(뺀 근거 {' · '.join(dr)})"}
    W("07_final.json", final); W("sheet.md", sheet(d, o1, o2, g, h, final))
    tr.append(f"| 07 점검 보고서 | 코드 | 01 · 02 · 05 · 06 | 한 장으로 묶음 · 한도 칸은 빈칸 | **{final['상태']}**" + (f" 「{final['판정']}」" if final["판정"] else "") + f" · sheet.md | {T(t0)} |")
    fin(); print(d, final["상태"], "—", final["한 줄"]); return 0


if __name__ == "__main__":
    sys.exit(main())
