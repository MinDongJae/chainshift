# -*- coding: utf-8 -*-
"""f4 에서 새로 내는 값. 실행: python -X utf8 calc_f4.py → calc_f4.json  (analysis/ 는 읽기만 · 저장소 맨 위에서 실행: python -X utf8 f4/calc_f4.py)
1) 판단 실험 18일 판(해석 2 가 정답을 미리 본 7일을 뺀 날) 다섯 줄 — score.py 의 tally 와 같은 셈(확정 = 판정이 HAND 가 아닌 날, 맞음 = 판정 == 정답)
2) 헤지 효과 = 100 − 남는 손실의 크기(%) — A3_hedge/RESULT.md 표의 가운데 값(칩 충격일 46일 · 날마다 크기)과 F_dayhedge 의 2026-11-04 값
3) 한 해로 친 한도 초과일 = 13개월 초과일 × 12 / 13
4) 2026-10-22 전력 쪽 19종목의 종목별 재평가 손익(6월 말 공시 평가액 × 그날 등락) — 큰 차례 셋, 합이 실행기 값(−130.5백만 달러)과 같은지 확인
5) 전력 쪽 19종목의 표준 업종 분류(net_result.json sector) 갈래 수"""
# closed-class: 이 파일의 한글 판정 값(YES · HAND)은 실험(B2_roles/score/score.py)이 정한 닫힌 값 셋 가운데 둘이다. 글을 거르는 낱말 목록이 아니다.
import json
from collections import Counter
from pathlib import Path
import pandas as pd

R = Path(__file__).resolve().parent
AN = Path("analysis")
K = Path(__import__("os").environ.get("CHAINSHIFT_DATA", "data"))
J = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))  # noqa: E731
out = {"inputs": {}}
YES, HAND = "번진다", "넘김"  # closed-class 판정 값(score.py 와 같음)

# 1) 18일 판
SC = J(AN / "B2_roles/score/score.json"); out["inputs"]["score"] = (AN / "B2_roles/score/score.json").as_posix()
DAY = SC["day"]; LEAKED = set(SC["leak"]["해석2"]["answer"]); D18 = sorted(d for d in DAY if d not in LEAKED)
assert len(DAY) == 25 and len(LEAKED) == 7 and len(D18) == 18


def read(folder):
    """판정 파일을 score.py 와 같이 읽는다(사람에게 넘긴 판정은 HAND 로)."""
    o = {}
    for f in sorted((AN / f"B2_roles/{folder}/judgments").glob("*.json")):
        j = J(f); o[j["date"]] = j["verdict"] if j["verdict"] in (YES, "안 " + YES) else HAND
    return o


V = {"i1": read("interpret"), "i2": read("interpret2")}
out["inputs"]["judgments"] = [(AN / "B2_roles/interpret/judgments").as_posix(), (AN / "B2_roles/interpret2/judgments").as_posix()]


def tally(days, get):
    v = {d: get(d) for d in days}; c = [d for d in days if v[d] != HAND]; ok = [d for d in c if v[d] == DAY[d]["truth"]]
    return {"days": len(days), "confirmed": len(c), "right": len(ok), "wrong": len(c) - len(ok), "handed": len(days) - len(c)}


both = lambda d: V["i1"][d] if V["i1"][d] == V["i2"][d] else HAND  # noqa: E731  두 해석이 같은 확정일 때만
T18 = {"always": tally(D18, lambda d: YES), "server": tally(D18, lambda d: DAY[d]["server_rule"]), "i1": tally(D18, lambda d: V["i1"][d]),
       "i2": tally(D18, lambda d: V["i2"][d]), "both": tally(D18, both)}
T25 = {"i1": tally(sorted(DAY), lambda d: V["i1"][d]), "both": tally(sorted(DAY), both)}
# 자기 검사: SCORE.md 에 적힌 값과 같아야 한다
assert T25["i1"] == {"days": 25, "confirmed": 15, "right": 13, "wrong": 2, "handed": 10} and T25["both"] == {"days": 25, "confirmed": 14, "right": 13, "wrong": 1, "handed": 11}
assert T18["i2"] == {"days": 18, "confirmed": 11, "right": 11, "wrong": 0, "handed": 7} and T18["both"] == {"days": 18, "confirmed": 10, "right": 10, "wrong": 0, "handed": 8}
assert (T18["always"]["right"], T18["always"]["wrong"], T18["server"]["right"], T18["server"]["wrong"]) == (15, 3, 16, 2)
out["exp18"] = {"days": D18, "excluded": sorted(LEAKED), "truth_spread": sum(DAY[d]["truth"] == YES for d in D18), "rows": T18,
                "handed_pct_both": round(T18["both"]["handed"] / 18 * 100), "handed_pct_both_25": round(T25["both"]["handed"] / 25 * 100)}

# 2) 헤지 효과 = 100 − 남는 손실의 크기
A3 = (AN / "A3_hedge/RESULT.md").read_text(encoding="utf-8").replace("*", ""); out["inputs"]["A3"] = (AN / "A3_hedge/RESULT.md").as_posix()
left = {}
for name, frag in (("자기 업종 펀드", "74% / 71% / 44"), ("반도체 펀드", "11% / 43% / 28"), ("두 펀드 함께", "27% / 38% / 31")):
    assert frag in A3, frag
    left[name] = int(frag.split(" / ")[1][:-1])
out["hedge_effect_46"] = {"left_pct": left, "effect_pct": {k: 100 - v for k, v in left.items()}, "formula": "100 − (날마다 |헤지 뒤 손익| 합 ÷ 날마다 |헤지 전 손익| 합 × 100), 칩 충격일 46일 · 전력 쪽 19종목"}
F = (AN / "F_dayhedge/RESULT.md").read_text(encoding="utf-8").replace("*", ""); out["inputs"]["F"] = (AN / "F_dayhedge/RESULT.md").as_posix()
l4 = {"자기 업종 펀드": 75, "반도체 펀드": 76, "두 펀드 함께": 69}
for s in ("| 자기 업종 펀드로 헤지 | −1.19억 달러 | 75% |", "| 반도체 펀드로 헤지 | −1.20억 달러 | 76% |", "| 자기 업종 + 반도체 두 펀드 | −1.09억 달러 | 69% |"):
    assert s in F, s
out["hedge_effect_1104"] = {"left_pct": l4, "effect_pct": {k: 100 - v for k, v in l4.items()}}

# 3) 한 해로 친 초과일
VAR = J(AN / "H_var/var.json"); out["inputs"]["var"] = (AN / "H_var/var.json").as_posix()
x = VAR["res"]["헤지_자기업종95"]["13개월(2025-10-02~2026-10-29)"]["exceed"]; assert x == 24
out["per_year"] = {"exceed_13m": x, "formula": "24 × 12 / 13", "value": round(x * 12 / 13, 1), "shown": round(x * 12 / 13)}

# 4) 2026-10-22 종목별 재평가 손익(전력 쪽 19종목)
CH = J(K / "mcp_kic_precheck/kic_precheck/data/chain.json"); out["inputs"]["chain"] = (K / "mcp_kic_precheck/kic_precheck/data/chain.json").as_posix()
PX = (1 + pd.read_csv(K / "net/backtest/returns_long.csv.gz", index_col=0, parse_dates=True, float_precision="round_trip")).cumprod().mul(100); out["inputs"]["prices"] = (K / "net/backtest/returns_long.csv.gz").as_posix()
ret = PX.pct_change(fill_method=None).loc["2026-10-22"]
rows = []
for st in CH["stages"]:
    if st["name"] in CH["power_stages"]:
        for t in st["tick"]:
            rows.append({"t": t, "name": CH["names"].get(t, t), "stage": st["name"], "hold_musd": round(CH["holdings_usd"][t] / 1e6, 1), "ret_pct": round(float(ret[t]) * 100, 2), "pnl_musd": round(CH["holdings_usd"][t] * float(ret[t]) / 1e6, 1)})
tot = sum(CH["holdings_usd"][r["t"]] * float(ret[r["t"]]) for r in rows) / 1e6
assert len(rows) == 19 and abs(tot - (-130.5)) < 0.06, tot   # 실행기 sheet.md 의 전력 쪽 19종목 값
rows.sort(key=lambda r: r["pnl_musd"])
out["d1022_stocks"] = {"total_musd": round(tot, 1), "top3": rows[:3], "top3_share_pct": round(sum(r["pnl_musd"] for r in rows[:3]) / tot * 100), "all": rows}

# 5) 전력 쪽 19종목의 표준 업종 분류
ND = J(K / "net/net_result.json")["nodes"]; out["inputs"]["sector"] = (K / "net/net_result.json").as_posix()
SEC = {(n.get("id") or n.get("t") or n.get("ticker")): n["sector"] for n in ND} if isinstance(ND, list) else {k: v["sector"] for k, v in ND.items()}
out["power19_sector"] = dict(Counter(SEC[r["t"]] for r in rows)); out["vrt_etn_sector"] = [SEC["VRT"], SEC["ETN"]]
assert out["vrt_etn_sector"] == ["산업재", "산업재"]

(R / "calc_f4.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({k: out[k] for k in ("hedge_effect_46", "hedge_effect_1104", "per_year", "power19_sector")}, ensure_ascii=False))
print("18일", json.dumps(out["exp18"]["rows"], ensure_ascii=False), out["exp18"]["truth_spread"], out["exp18"]["handed_pct_both"])
print("25일(두 해석이 같을 때만 확정)", json.dumps(T25["both"], ensure_ascii=False), "· 그 가운데 정답을 미리 본 7일을 뺀 18일", json.dumps(T18["both"], ensure_ascii=False))
print("10-22", out["d1022_stocks"]["total_musd"], [(r["t"], r["name"], r["stage"], r["ret_pct"], r["pnl_musd"]) for r in out["d1022_stocks"]["top3"]], out["d1022_stocks"]["top3_share_pct"])
