# -*- coding: utf-8 -*-
"""급락일 알림 — 아침 실행이 끝난 뒤 돈다. 점검한 날이 반도체 급락일이면 그날의 점검 보고서를 저장소 알림 글(이슈)로 올린다.
저장소를 지켜보는(Watch) 담당자에게 메일 · 앱 알림이 간다. 같은 날 글이 이미 있으면 다시 올리지 않는다.
쓰는 법:  python -X utf8 agent/alert.py [날짜]   (날짜를 빼면 agent/runs_auto/log.jsonl 의 마지막 날)
GitHub Actions 안에서는 gh 와 GITHUB_TOKEN(issues: write)으로 올린다."""
import json, os, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; AUTO = ROOT / "agent/runs_auto"
rows = [json.loads(l) for l in (AUTO / "log.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()] if (AUTO / "log.jsonl").exists() else []
d = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] else (rows[-1]["날"] if rows else None)
fin, sheet = AUTO / str(d) / "07_final.json", AUTO / str(d) / "sheet.md"
if not d or not fin.exists() or not sheet.exists():
    print(d, "급락일 점검 기록 없음 — 알리지 않음"); sys.exit(0)
f = json.loads(fin.read_text(encoding="utf-8")); title = f"[ChainShift 급락일 점검] {d} — {f['상태']}" + (f" 「{f['판정']}」" if f.get("판정") else "")
gh = lambda *a: subprocess.run(["gh", *a], capture_output=True, text=True, encoding="utf-8")
have = gh("issue", "list", "--state", "all", "--search", f"\"[ChainShift 급락일 점검] {d}\" in:title", "--json", "number", "-q", "length")
if have.stdout.strip() not in ("", "0"):
    print(d, "알림 글이 이미 있음 — 다시 올리지 않음"); sys.exit(0)
body = f"**{f['한 줄']}**\n\n" + sheet.read_text(encoding="utf-8")[:60000] + f"\n\n---\n기록: `agent/runs_auto/{d}/`"
r = gh("issue", "create", "--title", title, "--body", body)
print(d, "알림 글 올림" if r.returncode == 0 else "알림 실패 " + r.stderr.strip()[:200], r.stdout.strip())
