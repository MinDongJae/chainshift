# 기획서의 수와 근거 파일

명령은 저장소 맨 위 폴더에서 돌립니다.

## 평가 항목별 근거

| 평가 항목 (배점) | 기획서가 답하는 한 문장 | 근거 수 | 이 저장소의 파일 | 다시 돌리는 명령 |
|---|---|---|---|---|
| 문제 정의 및 주제 적합성 (20) | 업종 펀드로 헤지해 둔 전력 쪽 장부가 한도를 넘은 날은 대부분 칩이 급락한 날이었고, 지금의 업종 기준 위험 관리로는 이 연결이 보이지 않습니다. | 13개월(2025-10-02~2026-10-29, 271거래일) 한도 초과 **24일 중 21일(88%)** 이 칩 충격일. 칩 충격일은 271일 중 46일(17%)뿐 | `analysis/H_var/RESULT.md` · `var.json` · `prereg.md` / 공사 문서 인용 `analysis/K_kicdocs/RESULT.md` | `python -X utf8 analysis/H_var/var.py` |
| AI Agent 구성 및 설계 (25) | 계산은 코드가, 그날 원인 분석은 AI가 맡고, 서로 모르게 읽은 두 해석이 같을 때만 확정하며 나머지는 사람에게 넘깁니다. | 두 해석이 25일 중 **22일(88%)** 에서 같은 판정. 칩 충격일 25일 전체로는 확정 14 · 틀린 확정 1 · 사람에게 11, 정답을 미리 본 7일을 뺀 18일에서는 확정 10 · 틀린 확정 0 · 사람에게 8 | `agent/chainshift_day.py` · `agent/runs/2026-10-22/` · `agent/runs/2026-07-15/` / `analysis/B2_roles/SCORE.md` · `score/score.json` | `python -X utf8 agent/chainshift_day.py 2026-10-22` / `python -X utf8 analysis/B2_roles/score/score.py` |
| 차별성 및 창의성 (20) | 검색이 붙은 일반 AI 는 그날 뉴스는 잘 답하지만, 보유 종목 전체의 손익과 헤지 뒤 남는 손실은 계산하지 못했습니다. | 일반 AI 가 빠뜨린 5종목의 그날 손익 −23.8백만 달러. 일반 AI 답 속 등락 27개: 맞음 15 · 반올림 차이 6 · 틀림 2 · 못 찾음 4 | `analysis/G_compare/COMPARE.md` · `compare.json` · `general_ai_with_search.md` / 기존 상품 견줌 `analysis/C2_use/RESULT.md` | `python -X utf8 analysis/G_compare/compare.py` |
| 실현 가능성 (20) | 하루 실행기의 코드 단계는 지금 돌고, 실제 두 날을 처음부터 끝까지 돌린 기록이 있습니다. | 2026-10-22 한 날: 일곱 단계 · 1.6초 · 확정 「번진다」 / 2026-07-15: 두 해석이 갈려 사람에게 넘김 | `agent/RESULT.md` · `agent/runs/<날>/trace.md` · `sheet.md` | `python -X utf8 agent/chainshift_day.py 2026-07-15` |
| 활용성 및 확장성 (15) | 점검 보고서에 「한도 대 실제 · 헤지 수단별 남는 손익 · 그날 까닭과 출처」를 담고, 다른 포지션을 넣어도 같은 계산이 돕니다. | 반도체 펀드를 헤지에 더하면 한도 초과 **24일 → 8일**. 2026-11-04 하루: 전력 쪽 −1.58억 달러, 시장 펀드로 헤지하면 −2.17억 달러로 오히려 커짐 | `analysis/F_dayhedge/RESULT.md` · `days.md` / `analysis/A3_hedge/RESULT.md` / 점검 보고서 견본 `analysis/C2_use/sheet2.json` | `python -X utf8 analysis/F_dayhedge/dayhedge.py` / `python -X utf8 analysis/A3_hedge/hedge.py` |

## 수마다 낸 코드와 결과 파일

| 수 | 뜻 | 낸 코드 | 결과 파일 |
|---|---|---|---|
| 한도 초과 24일 중 21일(88%)이 칩 충격일 | 날을 칩으로 고르지 않고 장부 자신이 한도를 넘은 날로 골라도, 그 날의 대부분은 칩이 급락한 날이었다(기대 초과일은 13.6일) | `analysis/H_var/var.py` | `analysis/H_var/var.json` · `RESULT.md` 맨 위 표 |
| 그 21일 중 19일은 시장 급락일이 아님 | 시장 전체가 빠져서 같이 빠진 것이 아니다 | 같은 코드 | `analysis/H_var/RESULT.md` 문장 1 |
| 반도체 펀드를 헤지에 더하면 24 → 8일 | 같은 한도에 견줘 넘는 날이 줄고(칩 충격일 21 → 4일) 초과 횟수가 기대 범위로 돌아온다. 자기 한도로 다시 재면 20일이다 | 같은 코드 | `analysis/H_var/RESULT.md` 표 넷째 줄 |
| 2023년 18일 중 1일 → 2026년 21일 중 20일 | 한도 초과일 가운데 칩 충격일의 수. 이 연결은 2023년에는 없었고(2024년 17일 중 8일 · 2025년 20일 중 10일) 해마다 세졌다 | 같은 코드 | `analysis/H_var/RESULT.md` 「해마다」 |
| 2026-10-22 한도 −0.48억 · 실제 −1.08억 · 반도체 펀드를 더했으면 −0.62억 달러 | 점검 보고서의 「어제 한도 대 실제」 한 줄 | 같은 코드 | `analysis/H_var/var.json` `own_hedged_exceed_days_13m` |
| 칩 충격일 46일에 전력 쪽 19종목이 합쳐 22.7억 달러 손실 | 헤지 수단(시장 · 자기 업종 · 반도체 펀드)마다 이 손실이 얼마나 남는지 견준 바탕 | `analysis/A3_hedge/hedge.py` | `analysis/A3_hedge/RESULT.md` · `hedge_print.txt` |
| 46일 중 32일, 예상 −57.3억 대 실제 −72.6억 달러(1.27배) | 칩 충격일에 칩 밖 49종목이 「시장 + 업종」으로 본 예상보다 더 빠진 날 수와 합계 | `analysis/A_problem/short_panel.py` · `long_panel.py` | `analysis/A_problem/RESULT.md` |
| 세부 업종까지 넣으면 29 / 46일, 2025-10 앞 47일에서는 20 / 47일 | 위 수가 약해지는 조건. 2026년에 뚜렷해진 현상이다 | `analysis/A2_problem/a2.py` | `analysis/A2_problem/RESULT.md` · `a2.json` |
| 두 해석 일치 25일 중 22일(88%, 카파 0.79) | 같은 자료를 서로 모르게 두 번 읽혔을 때 판정이 같았던 날. 두 해석은 같은 모델이라 「독립한 두 눈」이 아니라 「두 번 읽어도 흔들리지 않는다」는 뜻 | `analysis/B2_roles/score/score.py` | `analysis/B2_roles/SCORE.md` · `score/score.json` |
| 판단 실험 18일: 두 해석이 같을 때만 확정 10 · 틀림 0 · 사람에게 8 (25일 전체로는 확정 14 · 틀림 1 · 사람에게 11) | 정답을 미리 본 7일을 뺀 18일에서, 두 해석이 같은 확정을 낸 날만 확정했을 때. 같은 18일에서 한 줄 규칙(「서버·부품이 시장보다 1%p 넘게 더 빠지면 번진다」)은 18일 중 16일을 맞히고 2일을 틀렸다 | `f4/calc_f4.py` | `f4/calc_f4.json` 의 `exp18.rows.both`. 날마다 판정은 `analysis/B2_roles/interpret/judgments/` · `interpret2/judgments/`, 25일 기준(확정 14 · 맞음 13 · 틀림 1 · 넘김 11)은 `analysis/B2_roles/SCORE.md` |
| 2026-10-22 한 날: 칩 −6.16%(문턱 −2.93%) · 58종목 −733.7백만 달러 · 전력 쪽 −130.5백만 달러 · 확정 「번진다」 | 하루 실행기가 일곱 단계를 끝까지 돈 실물. 헤지 뒤 남는 손익은 시장 −89.9 · 자기 업종 펀드 −107.7 · 반도체 펀드 −48.3백만 달러 | `agent/chainshift_day.py` | `agent/runs/2026-10-22/` (`01_detect.json` ~ `07_final.json` · `sheet.md` · `trace.md`) |
| 2026-07-15 한 날: 사람에게 넘김 | 해석 A 는 「넘긴다」, 해석 B 는 「번진다」로 갈려 확정하지 않은 날 | 같은 코드 | `agent/runs/2026-07-15/` |
| 장 마감 뒤 기사 1건을 근거에서 뺌(10-22) | 그날 16:00(뉴욕) 뒤에 잡힌 기사는 그날 판단의 근거가 될 수 없어 코드가 거른다 | 같은 코드 06 단계 | `agent/runs/2026-10-22/06_hygiene.json` |
| 2026-11-04: 전력 쪽 −8.90%(−1.58억 달러), 시장은 +1.65% | 시장이 오른 날에도 전력 쪽이 칩과 함께 빠진 한 날. 시장 펀드 헤지는 손실을 137% 로 키웠다 | `analysis/F_dayhedge/dayhedge.py` | `analysis/F_dayhedge/RESULT.md` · `days.md` |
| 일반 AI 답 속 등락 27개: 맞음 15 · 반올림 차이 6 · 틀림 2 · 못 찾음 4 | 검색이 붙은 일반 AI 에 같은 질문 넷을 물어 채점한 값 | `analysis/G_compare/compare.py` | `analysis/G_compare/compare.json` · `COMPARE.md` |
| 사람에게 넘기는 날 23일 → 9일, 확정 16일 중 15일 맞음 | 앞선 실험: 한 개체가 더 볼 자료를 스스로 고르게 했을 때. 정답을 미리 본 날을 빼면 22일 중 확정 14 · 맞음 13 | `analysis/B_agent/score.py` | `analysis/B_agent/RESULT.md` |
| 공사 문서 인용 다섯 | 스트레스 테스트 · 공통 요인 점검 등 이 서비스가 닿는 업무를 공사가 직접 적은 문장(쪽 번호와 함께) | 사람이 원문을 열어 옮김 | `analysis/K_kicdocs/RESULT.md` |

## 다시 돌렸을 때 값이 찍히는 자리

| 다시 나오는 수 | 어디에 찍히나 |
|---|---|
| 한도를 넘은 24일 · 그중 칩 충격일 21일 (13개월 271거래일) | `analysis/H_var/var.json` 의 `res` → `헤지_자기업종95` → `13개월(2025-10-02~2026-10-29)` 의 `exceed` 24 · `exceed_on_shock` 21 |
| 반도체 펀드를 더하면 8일 | 같은 파일 `헤지_자기업종+반도체_를_자기업종한도로95` 의 `exceed` 8 |
| 2023년 18일 중 1일 → 2026년 21일 중 20일 | 같은 파일 `헤지_자기업종95` 의 `2023` · `2026` |
| 헤지 뒤 남는 손실 74% 대 11% | `analysis/A3_hedge/hedge.json` 의 `scopes` → `전력 쪽 19종목 합` → `by` → `shock46` 의 `OWN.left_pct_of_sum` 73.9 · `SMH.left_pct_of_sum` 10.5 |
| 판단 실험 — 칩 충격일 25일 전체: 확정 14 · 틀림 1 · 사람에게 11 | `f4/calc_f4.py` 가 찍는 「25일」 줄의 `{"days": 25, "confirmed": 14, "right": 13, "wrong": 1, "handed": 11}` · `analysis/B2_roles/SCORE.md` 맨 위 표 |
| 그 25일에서 해석 2 가 정답을 미리 본 7일을 뺀 18일: 확정 10 · 틀림 0 · 사람에게 8 | 같은 줄의 `{"days": 18, "confirmed": 10, "right": 10, "wrong": 0, "handed": 8}` (값이 다르면 코드의 assert 가 멈춥니다). 뺀 7일에서는 확정 4 · 그중 틀림 1 · 사람에게 3 이라 두 줄이 서로 맞습니다 |
| 2026-10-22 확정 · 2026-07-15 사람에게 넘김 | 실행기가 마지막에 찍는 한 줄과 `agent/runs/<날>/07_final.json` |

- 위 명령은 결과 파일을 같은 값으로 다시 씁니다. 돌린 뒤 `git status` 에 남는 것은 `agent/runs/<날>/trace.md` 의 걸린 시간 칸뿐입니다.
- 하루 실행기의 AI 해석 두 개(03 · 04 단계)는 모델을 새로 부르지 않고 저장해 둔 답(`agent/runs/<날>/03_interpret_A.output.json` · `04_interpret_B.output.json`)을 이어 붙여 재생합니다. 코드 단계(01 · 02 · 05 · 06 · 07)는 그때 다시 계산합니다.
- 그 밖에 같은 방법으로 다시 도는 것: `analysis/A_problem/long_panel.py` · `short_panel.py` · `analysis/A2_problem/a2.py`(약 1분) · `analysis/C2_use/ctrl.py` · `analysis/B_agent/exp1.py` · `exp1_posthoc.py`.
- 자료를 다른 폴더에 두려면 `CHAINSHIFT_DATA` 가 그 폴더를 가리키게 합니다(정하지 않으면 `./data`).
