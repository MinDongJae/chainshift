# -*- coding: utf-8 -*-
"""예비 깨우기 — 화~토 오전에 이 PC 에서 돈다. 공개 저장소의 아침 실행 기록(agent/runs_auto/log.jsonl)에
어제(뉴욕 기준 직전 평일) 점검이 끝까지 돈 줄이 없으면 아침 실행을 한 번 깨운다.
이미 있는 gh 로그인만 쓴다(새 열쇠 없음). 기록: tools/morning_fallback.log"""
import base64, datetime, json, os, shutil, subprocess
from pathlib import Path
from zoneinfo import ZoneInfo
REPO = "MinDongJae/chainshift"; LOG = Path(__file__).with_suffix(".log"); NY, KST = ZoneInfo("America/New_York"), ZoneInfo("Asia/Seoul")
gh = shutil.which("gh") or r"C:\Program Files\GitHub CLI\gh.exe"; flags = 0x08000000 if os.name == "nt" else 0
run = lambda *a: subprocess.run([gh, *a], capture_output=True, text=True, encoding="utf-8", creationflags=flags)
now = datetime.datetime.now(NY)
d = now.date() if now.hour * 60 + now.minute >= 16 * 60 + 30 else now.date() - datetime.timedelta(days=1)   # morning.py 와 같은 셈
while d.weekday() >= 5: d -= datetime.timedelta(days=1)
target = d.isoformat()
r = run("api", f"repos/{REPO}/contents/agent/runs_auto/log.jsonl", "-q", ".content")
rows = [json.loads(l) for l in base64.b64decode(r.stdout or "").decode("utf-8").splitlines() if l.strip()] if r.returncode == 0 else []
done = [x for x in rows if x.get("날") == target and x.get("종료 코드") == 0]
if done: msg = f"{target} 점검이 이미 끝남 — 깨우지 않음 ({done[-1].get('결과', '')[:60]})"
else:
    w = run("workflow", "run", "morning.yml", "--repo", REPO); msg = f"{target} 점검 기록이 없어 깨움 — " + ("성공" if w.returncode == 0 else "실패 " + w.stderr.strip()[:200])
with LOG.open("a", encoding="utf-8") as f: f.write(f"{datetime.datetime.now(KST).isoformat(timespec='seconds')} {msg}\n")
print(msg)
