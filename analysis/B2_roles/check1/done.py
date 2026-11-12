# -*- coding: utf-8 -*-
"""judgments/*.json 25개를 세어 CHECK_DONE.md 의 표와 수를 찍는다. 쓰는 법: python -X utf8 done.py"""
import json, glob, collections
from pathlib import Path
H = Path(__file__).parent; C = collections.Counter
R = [json.loads(Path(f).read_text(encoding="utf-8")) for f in sorted(glob.glob(str(H / "judgments/*.json")))]
drop = lambda r: sum(1 for e in r["recheck"] if "뺌" in e["result"])
print("| 날짜 | 해석 판정 → 끝 판정 | 까닭 갈래 | 확신 | 더 쓴 도구 | 뺀 근거 | 한 줄 |\n|---|---|---|---|---|---|---|")
for r in R:
    print(f"| {r['date']} | {r['interp']} → {r['final']}{' (바꿈)' if r['changed'] else ''} | {r['cause']} | {r['conf']} | {len(r['tools'])} | {drop(r)}/{len(r['recheck'])} | {r['why'][:110]} |")
print("\n해석", dict(C(r["interp"] for r in R)), "· 끝", dict(C(r["final"] for r in R)), "· 바꾼 날", sum(r["changed"] for r in R))
print("옮겨 간 길", {f"{a}→{b}": n for (a, b), n in C((r["interp"], r["final"]) for r in R).items()})
print("확신", dict(C(r["conf"] for r in R)), "· 까닭", dict(C(r["cause"] for r in R)))
T = C(t for r in R for t in r["tools"]); print("도구", dict(T), "합", sum(T.values()), "· 한 날 최대", max(len(r["tools"]) for r in R))
print("다시 확인한 근거", sum(len(r["recheck"]) for r in R), "· 뺀 근거", sum(drop(r) for r in R), "· 근거를 하나라도 뺀 날", sum(1 for r in R if drop(r)))
