# -*- coding: utf-8 -*-
"""하루 점검 실행기가 AI 를 직접 부르는 자리. 한 번 묻고 JSON 답 하나를 돌려준다. 도구 없이 글만 주고받는다.
부르는 길은 둘이다.
  api  Anthropic API (pip install anthropic). 환경 변수 ANTHROPIC_API_KEY 가 있으면 이 길로 간다 — 서버의 자동 실행은 이 길.
  cli  Claude Code 명령줄(claude -p). 열쇠가 없을 때. 명령줄 자리는 CHAINSHIFT_CLAUDE_BIN 으로 바꿀 수 있다.
CHAINSHIFT_MODEL_VIA=api 또는 cli 로 길을 정할 수 있다."""
import glob, json, os, re, shutil, subprocess, tempfile, time

SYSTEM = ("너는 주식 리스크 점검 보조다. 받은 입력 묶음 안의 자료만 쓴다. 입력에 없는 기사나 숫자를 지어내지 않는다. "
          "기사를 근거로 들 때는 text 칸에 그 기사 제목을 글자 그대로 옮기고 출처 칸에 N번호를 적는다. "
          "답은 JSON 객체 하나만 쓴다. 앞뒤에 다른 글을 붙이지 않는다.")
EXTRA = ('\n\n위 답 형식의 칸에 더해 "반대 근거"(내 판정과 어긋나는 자료 한 줄, 없으면 빈 글)와 "덧말"(한 줄)을 넣는다.')


def find_bin():
    b = os.environ.get("CHAINSHIFT_CLAUDE_BIN")
    if b: return b
    if os.name == "nt":
        c = sorted(glob.glob(os.path.expanduser("~/.vscode/extensions/anthropic.claude-code-*-win32-x64/resources/native-binary/claude.exe")))
        if c: return c[-1]
    b = shutil.which("claude")
    if b: return b
    raise RuntimeError("claude 명령줄을 찾지 못했습니다. CHAINSHIFT_CLAUDE_BIN 에 실행 파일 자리를 적어 주세요.")


def parse(text):
    m = re.search(r"\{.*\}", text, re.S); ans = json.loads(m.group(0))
    for k in ("까닭 갈래", "근거 문장", "판정", "확신"):
        if k not in ans: raise ValueError(f"답에 「{k}」 칸이 없음")
    return ans


def ask_api(prompt, model):
    """Anthropic API 로 한 번 묻는다. 모델이 답을 거절하면 API 가 다른 모델로 이어 답하게 두고, 실제로 답한 모델을 기록에 남긴다."""
    import anthropic
    client = anthropic.Anthropic(); last = ""
    for attempt in (1, 2):
        t0 = time.time()
        try:
            r = client.beta.messages.create(model=model, max_tokens=16000, system=SYSTEM, output_config={"effort": "high"},
                                            betas=["server-side-fallback-2026-07-01"], fallbacks="default",
                                            messages=[{"role": "user", "content": prompt + EXTRA}])
            if r.stop_reason == "refusal": raise ValueError("모델이 답을 거절함")
            text = "".join(b.text for b in r.content if b.type == "text")
            return parse(text), {"모델": model, "실제로 답한 모델": [r.model], "걸린 초": round(time.time() - t0, 1), "시도": attempt, "답 원문": text,
                                 "길": "api", "토큰": {"입력": r.usage.input_tokens, "출력": r.usage.output_tokens}}
        except (anthropic.RateLimitError, anthropic.APIConnectionError, anthropic.InternalServerError, ValueError, AttributeError) as e:
            last = f"{type(e).__name__}: {e}"
    raise RuntimeError("모델 답을 받지 못했습니다 — " + last)


def ask(prompt, model, timeout=600):
    """prompt 를 model 에 한 번 묻고 (답 dict, 기록 dict) 를 돌려준다. JSON 이 아니면 한 번 더 묻는다."""
    via = os.environ.get("CHAINSHIFT_MODEL_VIA") or ("api" if os.environ.get("ANTHROPIC_API_KEY") else "cli")
    if via == "api": return ask_api(prompt, model)
    cmd = [find_bin(), "-p", "--model", model, "--output-format", "json", "--tools", "", "--strict-mcp-config",
           "--no-session-persistence", "--setting-sources", "local", "--system-prompt", SYSTEM]
    flags = 0x08000000 if os.name == "nt" else 0          # 창을 띄우지 않는다
    last = ""
    for attempt in (1, 2):
        t0 = time.time()
        with tempfile.TemporaryDirectory() as cwd:
            p = subprocess.run(cmd, input=(prompt + EXTRA).encode("utf-8"), capture_output=True, timeout=timeout, cwd=cwd, creationflags=flags)
        raw = p.stdout.decode("utf-8", "replace")
        try:
            env = json.loads(raw); text = env.get("result") or ""
            if env.get("is_error"): raise ValueError(text[:300])
            ans = parse(text)
            return ans, {"길": "cli", "모델": model, "실제로 답한 모델": sorted((env.get("modelUsage") or {}).keys()), "걸린 초": round(time.time() - t0, 1),
                         "시도": attempt, "답 원문": text}
        except Exception as e:
            last = f"{type(e).__name__}: {e} / 종료 코드 {p.returncode} / {p.stderr.decode('utf-8', 'replace')[-300:]}"
    raise RuntimeError("모델 답을 받지 못했습니다 — " + last)
