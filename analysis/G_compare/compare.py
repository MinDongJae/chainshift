# -*- coding: utf-8 -*-
"""검색이 붙은 일반 AI 의 답(general_ai_with_search.md) 속 수를 주가 파일로 채점하고, 질문 4(10월 22일 전력·냉각 설비 손익)의 우리 쪽 값을 낸다.
읽는 것(읽기만, 망 · 유료 AI 안 씀):
  $CHAINSHIFT_DATA/net/backtest/returns_long.csv.gz   58종목+SPY 조정 종가 (long_panel.py 가 읽는 파일)
  ../A3_hedge/etf_long_ret.csv                                        SMH · SPY · 업종 펀드 조정 종가
  kic_precheck/data/chain.json                                    단계 · 2026-06-30 공개 보유 금액
  ../../agent/runs/2026-10-22/01_detect.json                      하루 실행기 01 단계 출력(맞대기용)
쓰는 것: compare.json   실행: python -X utf8 compare.py
채점: 주가 파일 등락과 차이 0.05%p 이하 = 맞음 · 0.5%p 이하 = 반올림 차이 · 그 밖 = 틀림 · 파일에 없는 것(지수 등) = 못 찾음.
  답이 범위(−8~9%)면 범위 안 = 맞음, 범위 끝에서 0.5%p 안 = 반올림 차이. 지수는 파일에 없어 반도체 펀드(SMH) · SPY 를 참고로만 옆에 적는다."""
import json
from pathlib import Path
import pandas as pd

HERE = Path(__file__).resolve().parent
import os
KIC = Path(os.environ.get("CHAINSHIFT_DATA", "data") + "")
PX = (1 + pd.read_csv(KIC / "net/backtest/returns_long.csv.gz", index_col=0, parse_dates=True, float_precision="round_trip")).cumprod().mul(100)
ETF = (1 + pd.read_csv(HERE.parent / "A3_hedge/etf_long_ret.csv", index_col=0, parse_dates=True, float_precision="round_trip")).cumprod().mul(100)
CH = json.loads((KIC / "mcp_kic_precheck/kic_precheck/data/chain.json").read_text(encoding="utf-8"))
DET = json.loads((HERE.parent.parent / "agent/runs/2026-10-22/01_detect.json").read_text(encoding="utf-8"))
R = PX.pct_change(fill_method=None) * 100
RE = ETF.pct_change() * 100
HOLD = CH["holdings_usd"]


def ret(t, d):
    if t in R:
        return float(R.loc[d, t])
    if t in RE:
        return float(RE.loc[d, t])
    return None


# (질문, 날, 종목·지수, 파일에서 볼 열, 일반 AI 값 아래, 위, 일반 AI 가 적은 글, 비고)
CLAIMS = [
    ("1", "2026-11-05", "마이크론", "MU", -17.5, -17.5, "약 −17.5% (두 종가로 −17.46%)", "종가"),
    ("1", "2026-11-04", "마이크론", "MU", -7.00, -7.00, "−7.00%", "종가"),
    ("1", "2026-11-02", "마이크론", "MU", -5.78, -5.78, "−5.78%", "종가"),
    ("1", "2026-11-05", "S&P 500", "SPY", -4.4, -4.4, "−4.4%", "지수 대신 SPY"),
    ("1", "2026-11-05", "반도체 지수", None, -12, -12, "약 −12%", "지수 없음 — 참고 SMH"),
    ("1", "2026-11-05", "나스닥 100", None, -6.4, -6.4, "−6.4%", "지수 없음"),
    ("2", "2026-11-04", "S&P 500", "SPY", 1.58, 1.58, "+1.58%", "지수 대신 SPY"),
    ("2", "2026-11-04", "비스트라", "VST", -13.8, -13.8, "−13.8%", "종가"),
    ("2", "2026-11-04", "버티브", "VRT", -12.9, -12.9, "−12.9% (장중 기사 −9%)", "종가"),
    ("2", "2026-11-04", "GE버노바", "GEV", -9, -8, "약 −8~9% (장중)", "장중 값이라고 밝힘"),
    ("2", "2026-11-04", "이튼", "ETN", -7, -7, "약 −7% (장중)", "장중 값이라고 밝힘"),
    ("2", "2026-11-04", "콘스텔레이션", "CEG", -6, -6, "약 −6% (오전)", "오전 값이라고 밝힘"),
    ("2", "2026-11-04", "반도체 지수", None, -4, -1, "한 곳 약 −4% · 다른 곳 SOXX −1% (서로 다르다고 적음)", "지수 없음 — 참고 SMH"),
    ("2", "2026-11-05", "버티브", "VRT", -14.0, -14.0, "−14.0%", "종가"),
    ("2", "2026-11-05", "AMD", "AMD", -17, -15, "−15~17%", "종가"),
    ("2", "2026-11-05", "엔비디아", "NVDA", -9, -9, "약 −9%", "종가"),
    ("3", "2026-10-22", "GE버노바", "GEV", -10.64, -10.64, "−10.64%", "종가"),
    ("3", "2026-10-22", "버티브", "VRT", -7.81, -7.81, "−7.81%", "종가"),
    ("3", "2026-10-22", "이튼", "ETN", -6, -6, "약 −6% (장중, 종가는 못 찾았다고 적음)", "장중 값이라고 밝힘"),
    ("3", "2026-10-22", "램리서치", "LRCX", -11.8, -11.8, "−11.8%", "종가"),
    ("3", "2026-10-22", "반도체 지수", None, -6.72, -6.72, "−6.72%", "지수 없음 — 참고 SMH"),
    ("3", "2026-10-22", "S&P 500", "SPY", -1.21, -1.21, "−1.21%", "지수 대신 SPY"),
    ("3", "2026-10-22", "AMD", "AMD", -8, -8, "약 −8%", "종가"),
    ("3", "2026-10-22", "인텔", "INTC", -8, -8, "약 −8%", "종가"),
    ("3", "2026-10-22", "마이크론", "MU", -6.3, -6.3, "−6.3%", "종가"),
    ("3", "2026-10-22", "엔비디아", "NVDA", -4.4, -4.4, "−4.4%", "종가"),
    ("3", "2026-10-22", "블룸에너지", "BE", -8.70, -8.70, "−8.70%", "종가"),
]


def grade(lo, hi, x):
    if x is None:
        return "못 찾음", None
    gap = 0.0 if lo <= x <= hi else min(abs(x - lo), abs(x - hi))
    return ("맞음" if gap <= 0.05 else "반올림 차이" if gap <= 0.5 else "틀림"), round(gap, 2)


rows = []
for q, d, name, col, lo, hi, said, note in CLAIMS:
    x = ret(col, d) if col else None
    g, gap = grade(lo, hi, x)
    ref = None if col else round(ret("SMH", d), 2) if "반도체" in name else None
    rows.append({"질문": q, "날": d, "대상": name, "일반 AI": said, "주가 파일(%)": None if x is None else round(x, 2), "차이(%p)": gap, "판정": g, "비고": note, "참고 SMH(%)": ref})
cnt = pd.Series([r["판정"] for r in rows]).value_counts().to_dict()
# 요청받은 열 개(마이크론 11-05 · 11-04 비스트라·버티브 · 10-22 GE버노바·버티브·이튼·램리서치 · 시장 11-04·11-05) 만 따로
ASKED = {("2026-11-05", "마이크론"), ("2026-11-04", "비스트라"), ("2026-11-04", "버티브"), ("2026-10-22", "GE버노바"), ("2026-10-22", "버티브"),
         ("2026-10-22", "이튼"), ("2026-10-22", "램리서치"), ("2026-11-04", "S&P 500"), ("2026-11-05", "S&P 500"), ("2026-11-04", "반도체 지수"), ("2026-11-05", "반도체 지수")}
asked = [r for r in rows if (r["날"], r["대상"]) in ASKED]
cnt_asked = pd.Series([r["판정"] for r in asked]).value_counts().to_dict()

# ── 질문 4: 10월 22일 전력·냉각 설비 11종목
D = "2026-10-22"; PREV = PX.index[PX.index.get_loc(D) - 1]; Q2END = "2026-06-30"
ST = {s["name"]: s["tick"] for s in CH["stages"]}
AI_SHARES = {"GEV": 237_000, "ETN": 297_000, "VRT": 339_000, "BE": 187_000}                 # 일반 AI 가 정리 사이트에서 읽은 주식 수(천 주 반올림)
AI_LOSS = {"GEV": 23.3, "ETN": 7.0, "VRT": 5.6, "BE": 5.0}                                   # 일반 AI 어림(백만 달러)
AI_USD = {"PWR": 121, "FIX": 92, "JCI": 89, "VST": 77, "TT": 73, "CEG": 66, "EME": 43}       # 일반 AI 가 읽은 6월 말 평가액(백만 달러) — 등락 못 찾아 −2~−4% 가정
q4 = []
for t in ST["전력·냉각 설비"]:
    u = HOLD[t] / 1e6; r = ret(t, D); roll = float(PX.loc[PREV, t] / PX.loc[Q2END, t])
    q4.append({"종목": t, "이름": CH["names"].get(t, t), "보유 6월 말(백만 달러)": round(u, 1), "10-22 등락(%)": round(r, 2),
               "재현 손익(백만 달러)": round(u * r / 100, 2), "주식 수 그대로일 때(백만 달러)": round(u * roll * r / 100, 2),
               "일반 AI": ("어림 %.1f" % AI_LOSS[t]) if t in AI_LOSS else ("−2~−4% 가정" if t in AI_USD else "빠뜨림"),
               "일반 AI 가 읽은 보유(백만 달러)": AI_USD.get(t)})
tot = round(sum(HOLD[t] * ret(t, D) / 100 for t in ST["전력·냉각 설비"]) / 1e6, 1)
tot_roll = round(sum(HOLD[t] * float(PX.loc[PREV, t] / PX.loc[Q2END, t]) * ret(t, D) / 100 for t in ST["전력·냉각 설비"]) / 1e6, 1)
det = next(s for s in DET["단계별"] if s["단계"] == "전력·냉각 설비")["재현 손익(백만 달러)"]
assert abs(tot - det) < 0.05, (tot, det)                      # 다시 돌려 하루 실행기 01 단계와 같은 값인가
three = round(sum(HOLD[t] * ret(t, D) / 100 for t in ("GEV", "ETN", "VRT")) / 1e6, 1)
three_roll = round(sum(HOLD[t] * float(PX.loc[PREV, t] / PX.loc[Q2END, t]) * ret(t, D) / 100 for t in ("GEV", "ETN", "VRT")) / 1e6, 1)
missed = [x for x in q4 if x["일반 AI"] == "빠뜨림"]
# 일반 AI 가 −2~−4% 로 가정한 종목(주가 파일에 있는 것)의 실제 등락
assumed = [{"종목": t, "단계": next(k for k, v in ST.items() if t in v), "일반 AI 가 읽은 보유(백만 달러)": v, "우리 보유(백만 달러)": round(HOLD[t] / 1e6, 1),
            "실제 10-22 등락(%)": round(ret(t, D), 2), "가정": "−2~−4%"} for t, v in AI_USD.items()]
# 넓은 범위: 전력 쪽 19종목(전력·냉각 + 공사 + 발전)
wide = round(sum(HOLD[t] * ret(t, D) / 100 for k in CH["power_stages"] for t in ST[k]) / 1e6, 1)

out = {"채점": rows, "판정 수(27줄 전체)": cnt, "판정 수(맡은 일에 적힌 11줄)": cnt_asked,
       "질문4": {"날": D, "하루 전 거래일": str(PREV.date()), "종목별": q4, "전력·냉각 설비 11종목 재현 손익(백만 달러)": tot, "01_detect.json 값": det,
                "주식 수 그대로일 때 11종목(백만 달러)": tot_roll, "세 회사(GEV·ETN·VRT) 재현 손익": three, "세 회사 주식 수 그대로일 때": three_roll,
                "일반 AI 세 회사 어림": 35.9, "일반 AI 넓은 어림": [55, 68],
                "일반 AI 가 빠뜨린 종목": [x["종목"] for x in missed], "빠뜨린 종목 재현 손익 합": round(sum(x["재현 손익(백만 달러)"] for x in missed), 1),
                "빠뜨린 종목 보유 합": round(sum(x["보유 6월 말(백만 달러)"] for x in missed), 1),
                "가정한 종목의 실제 등락": assumed, "전력 쪽 19종목 재현 손익(백만 달러)": wide}}
(HERE / "compare.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
for r in rows:
    print(r["질문"], r["날"], r["대상"], "|", r["일반 AI"], "|", r["주가 파일(%)"], "|", r["차이(%p)"], "|", r["판정"], "|", r["참고 SMH(%)"])
print(cnt, cnt_asked)
print(json.dumps(out["질문4"], ensure_ascii=False, indent=1))
print({t: round(float(PX.loc[d, t]), 2) for t, d in (("MU", "2026-11-05"), ("MU", "2026-11-04"), ("GEV", "2026-10-22"), ("LRCX", "2026-10-22"), ("VRT", "2026-11-05"), ("VRT", "2026-10-22"))})

# ── 덧붙임: 일반 AI 가 −2~−4% 로 가정한 7종목(주가 파일에 있는 것)의 가정 손실 대 실제, 전력 쪽 19종목의 주식 수 그대로 값
a_usd = sum(AI_USD.values())
a_act = sum(v * ret(t, D) / 100 for t, v in AI_USD.items())
P19 = [t for k in CH["power_stages"] for t in ST[k]]
wide_roll = sum(HOLD[t] * float(PX.loc[PREV, t] / PX.loc[Q2END, t]) * ret(t, D) / 100 for t in P19) / 1e6
ai_in19 = set(AI_LOSS) | set(AI_USD)
add = {"가정 7종목 보유 합(일반 AI 가 읽은 값, 백만 달러)": a_usd, "가정 손실(−2%~−4%)": [round(a_usd * .02, 1), round(a_usd * .04, 1)],
       "같은 보유에 실제 등락을 곱한 값": round(a_act, 1), "7종목 중 −4% 보다 더 빠진 종목 수": sum(ret(t, D) < -4 for t in AI_USD),
       "전력 쪽 19종목 주식 수 그대로일 때": round(wide_roll, 1), "전력 쪽 19종목 중 일반 AI 가 다룬 종목 수": len(ai_in19 & set(P19)),
       "19종목 중 일반 AI 가 안 다룬 종목": [t for t in P19 if t not in ai_in19],
       "일반 AI 만 넣은 종목(58종목 밖 · 주가 파일에 없음)": ["EMR 65", "CARR 50"],
       "6월 말→10월 21일 주가 비(주식 수 그대로일 때 곱한 값)": {t: round(float(PX.loc[PREV, t] / PX.loc[Q2END, t]), 3) for t in ST["전력·냉각 설비"]}}
out["질문4"]["덧붙임"] = add
(HERE / "compare.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(add, ensure_ascii=False, indent=1))
