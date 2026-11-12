# -*- coding: utf-8 -*-
"""기대 효과 크기 — 잰 값만 묶는다(가정은 결과에 '가정'으로 적음).
입력: A_problem/short_panel.json(칩 충격일 46일 · 판정 271거래일) · B_agent/exp2_result.json(넘김 · 확정) · net/agent_ui_v4/shots/_live-try-3~6.json(실제 답 기록)
출력: effect.json   실행: python -X utf8 effect.py"""
import json, glob
from pathlib import Path
H = Path(__file__).parent; F1 = H.parent; J = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))
W = J(F1 / "A_problem/short_panel.json")["W250"]; n_chip, n_days = len(W["crit_days"]["chip"]), W["eval_days"]
E2 = J(F1 / "B_agent/exp2_result.json")
print({k: (list(v.keys()) if isinstance(v, dict) else type(v).__name__) for k, v in E2.items()})
ans = []
import os
for f in sorted(glob.glob(os.environ.get("CHAINSHIFT_DATA", "data") + "/net/agent_ui_v4/shots/_live-try-*.json")):
    ev = J(f)["events"]; d = next(e for e in ev if e["type"] == "done"); v = next(e for e in ev if e["type"] == "verify"); e = next(e for e in ev if e["type"] == "evidence")
    ans.append({"file": Path(f).name, "question": next(x for x in ev if x["type"] == "received")["text"], "seconds": d["seconds"], "usd": d["usd"],
                "evidence": e["count"], "cited": len(v["cited"]), "sentences": len(v["sentences"]), "failed_checks": v["failed"]})
per_year = n_chip / n_days * 252
out = {"chip_shock_days": n_chip, "eval_trading_days": n_days, "eval_window": [W["eval_from"], W["eval_to"]], "per_252_trading_days": round(per_year, 1),
       "answers": ans, "answer_seconds_range": [min(a["seconds"] for a in ans), max(a["seconds"] for a in ans)],
       "answer_usd_range": [round(min(a["usd"] for a in ans), 3), round(max(a["usd"] for a in ans), 3)],
       "answer_usd_mean": round(sum(a["usd"] for a in ans) / len(ans), 4),
       "year_cost_usd_if_one_answer_per_shock_day": round(per_year * sum(a["usd"] for a in ans) / len(ans), 2)}
(H / "effect.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8"); print(json.dumps(out, ensure_ascii=False, indent=1))
