# -*- coding: utf-8 -*-
"""아침 자동 실행 — 전날(미국) 종가를 받아 하루 점검을 끝까지 돌린다.
차례: ① 주가 받기(전날 종가까지 덧붙임) → ② 01 감지 → 반도체 급락일이면 ③ 기사 제목 받기 → ④ 하루 점검(AI 직접 부름) → ⑤ 기록 한 줄.
저장소에 든 자료(data/)는 건드리지 않는다. 처음 돌 때 data_live/ 로 복사해 그쪽에만 덧붙인다(기획서의 수를 다시 내는 명령은 data/ 를 읽는다).
쓰는 법:  python -X utf8 agent/morning.py                 전날(뉴욕 기준 직전 평일)
          python -X utf8 agent/morning.py 2026-11-11      날을 정해서
          python -X utf8 agent/morning.py --source bloomberg   주가를 블룸버그 단말에서(기본 public = 야후 파이낸스)
          --force 를 붙이면 그날을 이미 돌렸어도 다시 돈다
기록: agent/runs_auto/<날>/ (하루 점검 기록) · agent/runs_auto/log.jsonl (날마다 한 줄)"""
import datetime, json, os, shutil, subprocess, sys, time
from pathlib import Path
from zoneinfo import ZoneInfo
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "data"))
LIVE = ROOT / "data_live"; AUTO = ROOT / "agent/runs_auto"
FILES = ["net/backtest/returns_long.csv.gz", "etf_long_ret.csv", "net/returns.csv.gz"]   # 58종목+SPY · 펀드 7개 · 공개 보유 전체
NY, KST = ZoneInfo("America/New_York"), ZoneInfo("Asia/Seoul")
FLAGS = 0x08000000 if os.name == "nt" else 0


def last_weekday(now=None):
    """가장 최근에 장이 끝난 미국 평일. 뉴욕 16:30 이 지났으면 그날, 아니면 그 앞 평일(한국 아침 08:40 = 뉴욕 전날 저녁 → 전날)."""
    now = now or datetime.datetime.now(NY)
    d = now.date() if now.hour * 60 + now.minute >= 16 * 60 + 30 else now.date() - datetime.timedelta(days=1)
    while d.weekday() >= 5: d -= datetime.timedelta(days=1)
    return d.isoformat()


def prepare():
    if not LIVE.exists():
        shutil.copytree(ROOT / "data", LIVE, ignore=shutil.ignore_patterns("refetch", "__pycache__"))
        shutil.copy(ROOT / "analysis/A3_hedge/etf_long_ret.csv", LIVE / "etf_long_ret.csv")


def append_prices(d, source):
    """세 파일에 마지막 날 다음부터 d 까지의 일별 등락률을 덧붙인다. 앞의 값은 바꾸지 않는다."""
    import fetch_prices as fp
    get = fp.public if source == "public" else fp.bloomberg; out = []
    for f in FILES:
        p = LIVE / f; old = pd.read_csv(p, index_col=0, parse_dates=True, float_precision="round_trip"); last = old.index[-1]
        if last >= pd.Timestamp(d): out.append(f"{f}: 이미 {last.date()} 까지 있음"); continue
        px = get(list(old.columns), str((last - pd.Timedelta(days=10)).date()), d).dropna(how="all")
        new = px.reindex(columns=old.columns).pct_change(fill_method=None).loc[lambda x: (x.index > last) & (x.index <= pd.Timestamp(d))]
        if new.empty: out.append(f"{f}: {last.date()} 뒤 새 거래일 없음"); continue
        both = pd.concat([old, new]); both.index.name = old.index.name
        both.to_csv(p, **({"compression": {"method": "gzip", "mtime": 0}} if f.endswith(".gz") else {}))
        out.append(f"{f}: {new.index[0].date()}~{new.index[-1].date()} {len(new)}일 덧붙임 (빈 종목 {int(new.iloc[-1].isna().sum())})")
    return out


def run(args, env):
    p = subprocess.run([sys.executable, "-X", "utf8"] + args, cwd=ROOT, env=env, capture_output=True, creationflags=FLAGS)
    return p.returncode, (p.stdout.decode("utf-8", "replace").strip().splitlines() or [""])[-1], p.stderr.decode("utf-8", "replace")[-400:]


def main():
    a = [x for x in sys.argv[1:] if not x.startswith("--")]; d = a[0] if a else last_weekday()
    source = sys.argv[sys.argv.index("--source") + 1] if "--source" in sys.argv else "public"
    log = AUTO / "log.jsonl"
    if "--force" not in sys.argv and log.exists():      # 같은 날을 이미 끝까지 돌렸으면 다시 돌지 않는다(예약이 두 번 깨워도 요금이 한 번만 나게)
        for l in log.read_text(encoding="utf-8").splitlines():
            r = json.loads(l)
            if r.get("날") == d and r.get("종료 코드") == 0:
                print(d, "이미 돌았음 —", r.get("결과")); return
    t0 = time.time(); rec = {"날": d, "시작(KST)": datetime.datetime.now(KST).isoformat(timespec="seconds"), "주가 원천": source}
    env = dict(os.environ, CHAINSHIFT_DATA=str(LIVE), CHAINSHIFT_ETF=str(LIVE / "etf_long_ret.csv"))
    AUTO.mkdir(parents=True, exist_ok=True)
    try:
        prepare(); rec["주가"] = append_prices(d, source)
        have = pd.read_csv(LIVE / FILES[0], index_col=0, parse_dates=True).index
        if pd.Timestamp(d) not in have:
            rec["결과"] = "그날 종가가 없음(휴장이거나 아직 안 나옴) — 점검하지 않음"
        else:
            day = ["agent/chainshift_day.py", d, "--live", "1", "--runs", "runs_auto"]
            code, line, err = run(day, env); det = AUTO / d / "01_detect.json"
            shock = det.exists() and json.loads(det.read_text(encoding="utf-8")).get("칩 충격일")
            rec["반도체 급락일"] = bool(shock)
            if shock and not (LIVE / "agent/kic_agent/news" / f"{d}.json").exists():
                c2, l2, e2 = run(["agent/fetch_news.py", d], env); rec["기사"] = l2 or e2
                code, line, err = run(day, env)
            rec["결과"] = line or err; rec["종료 코드"] = code
    except SystemExit as e: rec["결과"] = f"멈춤 — {e}"
    except Exception as e: rec["결과"] = f"오류 — {type(e).__name__}: {e}"
    rec["걸린 초"] = round(time.time() - t0, 1)
    with open(AUTO / "log.jsonl", "a", encoding="utf-8") as f: f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(json.dumps(rec, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
