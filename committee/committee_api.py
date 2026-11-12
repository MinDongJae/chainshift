# -*- coding: utf-8 -*-
"""의견 모으기의 서버 쪽 — 요청 받기 · 자료 확인 · 묻는 길 고르기. 어느 서버에든 끼울 수 있게 통신 틀과 떼어 둔다.

  offers(body)                      → 권할 역할 목록(모델을 부르지 않는다)
  stream(body, ask, should_stop)    → 사건을 차례로 냄(승인받은 역할 하나)
  decision(body, log)               → 승인 · 거절 · 취소를 기록에 남김

화면이 돌려보내는 자료(evidence)는 그대로 믿지 않는다. 근거 묶음에 있는 글인지 확인하고, 없는 것은 빼고 그 수를 알린다.
묻는 길 셋: fake_ask(시험용 · 정해 둔 답) · cli_ask(이 PC 의 Claude 명령줄) · engine_ask(답 엔진이 이미 가진 연결을 그대로 씀).
"""
import glob, json, os, re, shutil, subprocess, sys, tempfile, time
from pathlib import Path

import committee

HERE = Path(__file__).resolve().parent
ENGINE_DIR = Path(os.environ.get("KIC_ENGINE_DIR", HERE.parent / "kic_agent_build" / "image_mcp1"))
MODELS = {"fast": "claude-haiku-5-5", "write": "claude-sonnet-5-5"}   # 답 엔진과 같은 두 모델


# ---------------------------------------------------------------- 근거 묶음 · 답 엔진의 코드 함수
class Pack:
    """근거 묶음에서 화면이 보낸 자료를 확인한다. 답 엔진을 불러올 수 있으면 자료 찾기와 숫자 대조도 그 함수를 쓴다."""
    def __init__(self):
        self.texts = set(); self.engine = None
        f = ENGINE_DIR / "pack" / "chunks.jsonl"
        if f.exists():
            for l in f.open(encoding="utf-8"):
                c = json.loads(l); self.texts.add(self._key(c.get("text")))
        try:
            for w in glob.glob(str(ENGINE_DIR / '*.whl')): sys.path.insert(0, w)      # 답 엔진이 쓰는 점검 묶음(올린 재료에 든 것)
            sys.path.insert(0, str(ENGINE_DIR)); import engine; self.engine = engine
        except Exception as e:
            self.engine_error = f"{type(e).__name__}: {e}"

    @staticmethod
    def _key(t): return re.sub(r"\s+", " ", t or "")[:120]

    def clean(self, evidence):
        """(확인된 자료, 뺀 수). 근거 묶음이 없으면 확인을 못 하므로 그대로 두고 뺀 수를 None 으로 돌려준다."""
        ev = [e for e in evidence or [] if isinstance(e, dict) and isinstance(e.get("n"), int) and e.get("text")]
        if not self.texts: return ev, None
        ok = [e for e in ev if self._key(e["text"]) in self.texts or e.get("tag") in ("지금 값", "방금 찾음")]
        return ok, len(ev) - len(ok)

    def search(self, category):
        if not self.engine: return None
        def f(word):
            hits = self.engine.search(word, category or "holding", k=4)
            return [{k: c.get(k) for k in ("title", "tag", "text", "published_at", "url", "source_kind")} for s, c in hits if s >= self.engine.MIN_SCORE]
        return f

    def check(self, question):
        if not self.engine: return None
        def f(answer, evidence):
            rows = self.engine.verify(answer, [{**e, "id": e.get("id") or f"n{e['n']}"} for e in sorted(evidence, key=lambda x: x["n"])], question)
            return {"sentences": len(rows), "failed": sum(1 for r in rows if not r["ok"]), "bad": [r["sentence"] for r in rows if not r["ok"]][:5]}
        return f


# ---------------------------------------------------------------- 요청 처리
def _run_of(body, pack):
    run = body.get("run") or {}
    ev, dropped = pack.clean(run.get("evidence"))
    return {"question": str(run.get("question") or "")[:500], "answer": str(run.get("answer") or "")[:4000], "evidence": ev,
            "issues": [str(x)[:80] for x in run.get("issues") or []][:20], "verify": run.get("verify") or {}, "category": run.get("category")}, dropped


def offers(body, pack):
    run, dropped = _run_of(body, pack)
    if not run["question"] or not run["evidence"]: return {"offers": [], "dropped": dropped}
    return {"offers": committee.offers(run), "dropped": dropped}


def stream(body, pack, ask, should_stop=lambda: False, parallel=False, deadline=None):
    role = body.get("role"); run, dropped = _run_of(body, pack)
    if role not in committee.ROLES or not run["question"] or len(run["evidence"]) < 1:
        yield {"type": "error", "why": "bad_request"}; return
    if dropped: yield {"type": "dropped", "count": dropped}
    try:
        yield from committee.run(role, run, ask, n=body.get("n", 3), should_stop=should_stop, parallel=parallel, deadline=float(deadline or os.environ.get("COMMITTEE_DEADLINE", 240)),
                                 search=pack.search(run.get("category")), check=pack.check(run["question"]))
    except Exception as e:
        yield {"type": "error", "why": "failed", "detail": f"{type(e).__name__}: {e}"[:200]}


def decision(body, log):
    rec = {"t": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "role": body.get("role"), "decision": body.get("decision"),
           "question": str((body.get("run") or {}).get("question") or body.get("question") or "")[:200], "run_id": body.get("run_id")}
    if rec["decision"] not in ("approve", "decline", "cancel") or rec["role"] not in committee.ROLES: return {"ok": False}
    log(rec); return {"ok": True}


# ---------------------------------------------------------------- 묻는 길
def _json_of(text):
    m = re.search(r"\{.*\}", text, re.S)
    return json.loads(m.group(0))


def fake_ask(mode="agree", delay=0.0, log=None):
    """시험용. 모델을 부르지 않고 정해 둔 답을 낸다. mode: agree(다 동의) · split(끝까지 갈림) · turn(둘째 차례에 생각을 바꿈) ·
    reject(다 반대) · absent2(둘째 담당이 답을 못 함) · silent(아무도 의견을 못 냄)."""
    A, D, H = committee.AGREE, committee.DISAGREE, committee.HOLD
    def ask(member, system, prompt, tier):
        if delay: time.sleep(delay)
        if log is not None: log.append({"member": member, "tier": tier, "prompt": prompt})
        k = int(member.split()[-1]) if member.split()[-1].isdigit() else 0
        if mode == "silent": raise RuntimeError("no answer")
        if mode == "absent2" and k == 2: raise RuntimeError("no answer")
        if '"answer"' in prompt.splitlines()[-1]:
            return {"answer": "마이크론은 11월 5일 -17.46% 떨어졌습니다 [N10]. 같은 날 미국 시장 전체는 -4.41%였습니다 [N15]."}
        if '"votes"' in prompt.splitlines()[-1]:
            ids = re.findall(r"^- ((?:\d+|new)-\d+) \(", prompt, re.M); second = committee.P["prior"] in prompt
            def v(i):
                if mode == "reject": return D
                if mode == "split": return D if (k + int(i.split("-")[1])) % 2 else H
                if mode == "turn": return A if second or not i.endswith("-1") else (D if k == 2 else H if k == 3 else A)
                return A
            return {"votes": [{"id": i, "vote": v(i), "why": f"{member}의 까닭"} for i in ids]}
        refs = [int(x) for x in re.findall(r"^\[N(\d+)\]", prompt, re.M)][:3]
        out = {"items": [{"text": f"{member}가 낸 의견 {j + 1}", "refs": refs[j:j + 1]} for j in range(2)]}
        if "search" in prompt.splitlines()[-1]: out["search"] = ["텍사스 데이터센터"] if k == 1 else []
        return out
    return ask


def _cli_bin():
    b = os.environ.get("CHAINSHIFT_CLAUDE_BIN")
    if b: return b
    if os.name == "nt":
        c = sorted(glob.glob(os.path.expanduser("~/.vscode/extensions/anthropic.claude-code-*-win32-x64/resources/native-binary/claude.exe")))
        if c: return c[-1]
    return shutil.which("claude")


def cli_ask(log=None, timeout=300):
    """이 PC 의 Claude 명령줄로 한 번씩 묻는다(구독, 창을 띄우지 않음). 실제 흐름 검증용."""
    exe = _cli_bin(); flags = 0x08000000 if os.name == "nt" else 0
    def ask(member, system, prompt, tier):
        t0 = time.time()
        cmd = [exe, "-p", "--model", MODELS[tier], "--output-format", "json", "--tools", "", "--strict-mcp-config",
               "--no-session-persistence", "--setting-sources", "local", "--system-prompt", system]
        with tempfile.TemporaryDirectory() as cwd:
            p = subprocess.run(cmd, input=prompt.encode("utf-8"), capture_output=True, timeout=timeout, cwd=cwd, creationflags=flags)
        env = json.loads(p.stdout.decode("utf-8", "replace")); text = env.get("result") or ""
        if env.get("is_error"): raise RuntimeError(text[:200])
        out = _json_of(text)
        if log is not None: log.append({"member": member, "model": sorted((env.get("modelUsage") or {}).keys()), "seconds": round(time.time() - t0, 1), "prompt": prompt, "answer": text})
        return out
    return ask


def engine_ask(model, log=None):
    """답 엔진이 이미 가진 연결(model.c)로 묻는다 — 서버에 올릴 때 쓰는 길. 이 폴더에서는 돌려 보지 않았다."""
    def ask(member, system, prompt, tier):
        r = model.c.messages.create(model=MODELS[tier], max_tokens=4000, system=system, output_config={"effort": "low"},
                                    messages=[{"role": "user", "content": prompt}])
        if r.stop_reason == "refusal": raise RuntimeError("refused")
        if log is not None: log(MODELS[tier], r.usage.input_tokens, r.usage.output_tokens)
        return _json_of("".join(b.text for b in r.content if b.type == "text"))
    return ask
