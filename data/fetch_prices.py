# -*- coding: utf-8 -*-
"""주가 원천을 고르는 얇은 층. 저장소 맨 위에서 돌린다.
저장소에는 종가 원자료가 아니라 종가에서 계산한 일별 등락률 파일이 들어 있다(첫 거래일 0, 그 뒤는 앞 거래일 종가 대비). 분석 코드는 이 등락률을 이어 곱해 쓴다.
  (아무것도 안 돌림)                               기본 — 저장소에 든 등락률 파일을 그대로 쓴다. 기획서의 수는 이 파일에서 나온다.
  python -X utf8 data/fetch_prices.py               지금 든 파일의 종목 수 · 기간만 찍는다(망에 안 감)
  python -X utf8 data/fetch_prices.py --source public      야후 파이낸스(yfinance)에서 같은 종목 · 같은 기간의 일별 종가를 새로 받는다
  python -X utf8 data/fetch_prices.py --source bloomberg   블룸버그 단말(blpapi, localhost:8194)에서 같은 종목 · 같은 기간의 일별 종가를 받는다
옵션: --end 2026-11-12  끝 날을 바꾼다(아침 실행용 — 전날 종가까지)
      --only returns_long  이름에 이 글자가 든 파일만
      --apply             코드가 읽는 자리에 덮어쓴다(없으면 data/refetch/ 에 쓰고 원래 파일은 그대로)
받은 종가를 같은 모양(날짜가 줄 · 티커가 칸 · 일별 등락률)으로 바꿔 쓰므로(종가 자체는 파일로 남기지 않는다) 분석 코드와 하루 실행기는 고칠 것이 없다.
새로 받은 값은 배당 · 분할 조정 시점이 달라 저장소에 든 값과 끝자리가 다를 수 있고, 그러면 결과의 수도 조금 달라질 수 있다.
블룸버그 호출은 bloomberg-mcp-intelligence 의 bdh 도구와 같은 요청(HistoricalDataRequest · PX_LAST · DAILY)이다.
  차이 하나: 야후 수정 종가와 맞추려고 배당 · 분할 조정을 요청에 직접 켠다(bdh 도구는 단말의 DPDF 설정을 따른다)."""
import argparse, csv, sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FILES = ["data/net/backtest/returns_long.csv.gz",   # 58종목 + SPY (한도 검증 · 헤지 · 하루 실행기 01)
         "analysis/A3_hedge/etf_long_ret.csv",         # 펀드 7개
         "data/net/returns.csv.gz",                 # 공개 보유 638종목 등 (하루 실행기 02 · 문제 정의)
         "analysis/C2_use/etf_px_ret.csv"]             # 펀드 7개(짧은 기간)
MAP = {r["ticker"]: r["bloomberg"] for r in csv.DictReader(open(ROOT / "data/bloomberg_tickers.csv", encoding="utf-8"))}
bbg = lambda t: MAP.get(t) or t.replace("-", "/") + " US Equity"   # 표에 없으면 규칙: VRT → VRT US Equity, BRK-B → BRK/B US Equity


def to_ret(px):
    """종가 → 일별 등락률. 첫 유효일은 0, 그 뒤는 직전 유효 종가 대비. 빈 날은 빈 채로 둔다."""
    prev = px.ffill().shift(1)
    return (px / prev - 1).mask(px.notna() & prev.isna(), 0.0)


def public(ticks, start, end):
    import yfinance as yf
    end1 = (pd.Timestamp(end) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")   # yfinance 의 end 는 그날을 안 넣는다
    return yf.download(ticks, start=start, end=end1, auto_adjust=True, progress=False, threads=False)["Close"]


def bloomberg(ticks, start, end):
    try:
        import blpapi
    except ImportError:
        sys.exit("blpapi 가 없음 — 블룸버그 단말이 있는 PC 에서 pip install blpapi (블룸버그 배포판) 뒤 다시 실행")
    o = blpapi.SessionOptions(); o.setServerHost("localhost"); o.setServerPort(8194)
    s = blpapi.Session(o)
    if not s.start() or not s.openService("//blp/refdata"):
        sys.exit("블룸버그 단말에 연결 못 함(localhost:8194) — 단말이 켜져 있고 로그인돼 있는지 확인")
    rq = s.getService("//blp/refdata").createRequest("HistoricalDataRequest")
    back = {bbg(t): t for t in ticks}
    for b in back: rq.getElement("securities").appendValue(b)
    rq.getElement("fields").appendValue("PX_LAST")
    rq.set("startDate", start.replace("-", "")); rq.set("endDate", end.replace("-", "")); rq.set("periodicitySelection", "DAILY")
    for k, v in (("adjustmentFollowDPDF", False), ("adjustmentNormal", True), ("adjustmentAbnormal", True), ("adjustmentSplit", True)): rq.set(k, v)
    s.sendRequest(rq); col = {}
    while True:
        ev = s.nextEvent(10000)
        for msg in ev:
            if msg.hasElement("securityData"):
                sd = msg.getElement("securityData"); fd = sd.getElement("fieldData")
                rows = [fd.getValueAsElement(i) for i in range(fd.numValues())]
                col[back[sd.getElementAsString("security")]] = {pd.Timestamp(str(r.getElementAsDatetime("date"))[:10]): r.getElementAsFloat("PX_LAST") for r in rows if r.hasElement("PX_LAST")}
        if ev.eventType() == blpapi.Event.RESPONSE: break
    s.stop()
    return pd.DataFrame(col).sort_index()


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--source", choices=["public", "bloomberg"]); ap.add_argument("--end"); ap.add_argument("--only", default=""); ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    for f in FILES:
        if a.only not in f: continue
        old = pd.read_csv(ROOT / f, index_col=0, parse_dates=True); ticks = list(old.columns)
        start, end = str(old.index[0].date()), a.end or str(old.index[-1].date())
        if not a.source:
            print(f"{f}: {len(ticks)}종목 · {start}~{str(old.index[-1].date())} · {len(old)}거래일 (저장소에 든 파일)"); continue
        px = (public if a.source == "public" else bloomberg)(ticks, start, end).dropna(how="all")
        empty = [t for t in ticks if t not in px or px[t].isna().all()]
        if px.empty or empty: sys.exit(f"멈춤: {f} 에서 빈 종목 {empty[:10]} ({len(empty)}개) — 덮어쓰지 않음")
        px = to_ret(px[ticks]); px.index.name = old.index.name
        out = ROOT / f if a.apply else ROOT / "data/refetch" / Path(f).name; out.parent.mkdir(parents=True, exist_ok=True)
        px.to_csv(out, **({"compression": {"method": "gzip", "mtime": 0}} if f.endswith(".gz") else {}))
        print(f"{f}: {a.source} 에서 {len(ticks)}종목 · {px.index[0].date()}~{px.index[-1].date()} · {len(px)}거래일 → {out.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    main()
