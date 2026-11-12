# -*- coding: utf-8 -*-
"""order_log.txt 에서 날마다 「끝 판정을 쓴 줄 < 정답 1 을 연 줄」, 「판정 2 를 쓴 줄 < 정답 2 를 연 줄」인지 검사."""
import json
from pathlib import Path
H = Path(__file__).parent; L = (H / "order_log.txt").read_text(encoding="utf-8").splitlines()
days = [r["date"] for r in json.loads((H / "exp2_result.json").read_text(encoding="utf-8"))["rows"]]
pos = lambda s: next(i for i, l in enumerate(L) if s in l)
ok1 = [d for d in days if pos(f"commit {d} s1b") < pos(f"reveal1 {d}")]
ok2 = [d for d in days if pos(f"commit {d} s2") < pos(f"reveal2 {d}")]
# 다음 거래일이 다음 충격일인 날: 앞 날의 정답 2 가 뒷날 끝 판정보다 먼저 열렸으면 새어 든 것
leak = [(a, b) for a, b in zip(days, days[1:]) if pos(f"reveal2 {a}") < pos(f"commit {b} s1b") and (a, b) in (("2026-07-01", "2026-07-02"), ("2026-07-15", "2026-07-16"))]
print("정답 1 보다 판정이 먼저:", len(ok1), "/", len(days), "· 정답 2 보다 판정이 먼저:", len(ok2), "/", len(days), "· 이웃한 날 새어 듦:", leak)
assert len(ok1) == len(ok2) == len(days)
