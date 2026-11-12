# 자료 — 출처 · 수집일 · 라이선스 · 전처리

대회 규정 「데이터 출처, 수집일, 라이선스 및 전처리 방법 등을 제출물에 반드시 기재」에 맞춘 표입니다. 「확인 못 함」은 약관 원문을 아직 열어 보지 못했다는 뜻입니다.

| 자료 | 출처 | 수집일 · 구간 | 라이선스 · 이용 조건 | 전처리 | 이 저장소에 |
|---|---|---|---|---|---|
| 한국투자공사 공개 보유 | 13F 정보표 (미국 SEC EDGAR, sec.gov) | 2026-06-30 기준 · 2026-08-12 제출분 | 미국 정부 공개 공시. SEC 공정 접근 규칙(초당 10회 이하 · 요청자 표시) | 종목 이름 → 티커. AI 데이터센터 58종목은 회사의 사업 내용을 보고 여섯 단계에 배정한 고정 분류표(업종 분류와 별개) | 계산 결과에 든 종목 · 금액만 |
| 종목 주가 | 야후 파이낸스 수정 종가 (yfinance 1.7.0, 코드는 Apache-2.0) | 58종목 + SPY 2021-01-04~2026-11-10, 2026-11-11 수집 / 공개 보유 638종목 2024-10-01~2026-10-29, 2026-10-30 저장 | **야후 약관 — 개인 · 비상업 이용.** 연구용으로만 씀 | 수정 종가 → 하루 등락 → 재평가 손익(6월 말 공시 평가액 × 그날 등락) → 직전 250거래일 회귀로 헤지 비율 → 직전 250거래일 헤지 뒤 손익의 5% 분위 = 다음 날 한도(95% VaR) | **종가는 넣지 않음. 종가에서 계산한 일별 등락률만 넣음** — `data/net/backtest/returns_long.csv.gz`(59칸 · 1,471거래일) · `data/net/returns.csv.gz`(651칸 · 522거래일). 받은 호출 기록은 `data/net/backtest/prices_long.meta.json` |
| 펀드 주가 | 야후 파이낸스 수정 종가 | 7개(SPY · SMH · XLI · XLU · XLK · XLE · XLB) 2021-01-04~2026-11-10, 2026-11-12 00:54 KST 받음 (`analysis/A3_hedge/etf_long.meta.json`) | 위와 같음 | 위와 같음 | **종가는 넣지 않음. 일별 등락률만 넣음** — `analysis/A3_hedge/etf_long_ret.csv` · 짧은 기간 판(SPY · SMH · SOXX · XLU · XLI · XLK · QQQ, 2024-10-01~2026-10-29, 2026-11-12 받음) `analysis/C2_use/etf_px_ret.csv` |
| 업종 분류 | S&P 구성표 업종 분류(GICS), 구성표에 없는 종목은 야후 분류 | 2026-11 수집 | 분류 이름만 씀. 약관 원문 확인 못 함 | S&P 구성표 493종목 + 야후 분류로 대신한 145종목 | 결과에 든 이름만 |
| 거래 관계 | 미국 SEC EDGAR 공시 · 한국 DART 오픈API | 128건, 2026-11-10 모음 | SEC 는 공개 공시. DART 약관 확인 못 함 | 공시 문장 · 공개일 · 주소를 보존하고, 원문에서 확인한 111건만 씀 | **넣음** — `data/relations/us/edges.json`(63건) · `kr/edges.json`(65건). 관계마다 근거 문장(공시 138곳 · 회사 IR 2곳 · 언론 보도 24곳, 언론 인용은 가장 긴 것이 273자) · 공개일 · 주소 |
| 기사 | GDELT 15분 파일(전 세계 기사 목록 공개 자료, 급락일 점검) · 구글 뉴스 검색(RSS — 공개 화면 기사 칸은 5분마다 AWS 수집기가 받음, 공개 MCP news_search 도 같은 곳, 제목 · 출처 · 시각 · 링크만) · 공개 화면 답 엔진은 구글 뉴스 RSS 검색 + 본문 추출(trafilatura 2.3.1, Apache-2.0) | GDELT: 판단 실험 25일분 / 구글 뉴스: 묻는 순간 | GDELT 공개 자료(출처 표시, 약관 원문 확인 못 함) · 구글 뉴스 개인 · 비상업 · 기사 저작권은 각 언론사 | 날마다 점수 높은 제목 15건. GDELT 수집 시각이 그날 뉴욕 16:00 뒤인 기사는 근거에서 뺌 | **넣음 — 제목 · 출처 이름 · 수집 시각 · 주소만.** `data/agent/kic_agent/news/` 25일분(날마다 15건, 본문 없음) |
| 공사 공개 문서 | KIC 2025 연차보고서 · 공사 누리집(kic.kr) | 2026-11-12 읽음 | 공사 저작물 — 인용 범위로만 | 쪽 번호와 인용문 | **PDF · 받아 둔 원문 넣지 않음.** `analysis/K_kicdocs/RESULT.md` 의 인용문만 |
| 기존 상품 소개 | Bloomberg · FactSet · S&P Global 의 공개 소개 자료 | 2026-11-12 읽음 | 각 회사 저작물 — 짧은 인용만 | 인용문과 주소 | 받아 둔 웹 원문 넣지 않음. `analysis/C2_use/RESULT.md` 의 인용문만 |
| AI 모델 | Anthropic Claude | — | 유료 상용 약관(공개 화면) · 구독(판단 실험) | 모델에는 질문 글과 공개 근거 조각만 보냄 | 판정 파일(`judgments/`)에 모델 답 |

## 넣은 자료 (`data/` 와 그 밖)

| 파일 | 무엇 | 출처 · 받은 날 · 범위 |
|---|---|---|
| `data/net/backtest/returns_long.csv.gz` | AI 데이터센터 58종목 + SPY 일별 등락률(수정 종가에서 계산). 날짜가 줄 · 티커가 칸 | 야후 파이낸스(yfinance 1.7.0, `auto_adjust=True`) · 2026-11-11 받음 · 2021-01-04~2026-11-10 (1,471거래일) |
| `data/net/returns.csv.gz` | 공개 보유 638종목 + SPY 등 651칸 일별 등락률 | 야후 파이낸스 · 2026-10-30 저장 · 2024-10-01~2026-10-29 (522거래일). |
| `analysis/A3_hedge/etf_long_ret.csv` | 펀드 7개(SPY · SMH · XLI · XLU · XLK · XLE · XLB) 일별 등락률 | 야후 파이낸스 · 2026-11-12 00:54 KST 받음 · 2021-01-04~2026-11-10 |
| `analysis/C2_use/etf_px_ret.csv` | 펀드 7개(SPY · SMH · SOXX · XLU · XLI · XLK · QQQ) 일별 등락률 | 야후 파이낸스 · 2026-11-12 받음 · 2024-10-01~2026-10-29 |
| `data/mcp_kic_precheck/kic_precheck/data/chain.json` | 종목 단계 분류표 — 58종목의 여섯 단계 · 2026-06-30 공개 보유 금액 | 13F 정보표(SEC EDGAR) + 우리가 회사 사업 내용을 보고 배정 |
| `data/mcp_kic_precheck/kic_precheck/regime_monitor.py` | 칩 충격일 규칙 코드 | 우리 코드 |
| `data/mcp_kic_precheck/kic_precheck/data/shock_days.json` | 앞 판의 충격일 목록 | 우리 계산 |
| `data/agent/kic_agent/days.json` | 판단 실험 정답 표 — 25일의 칩 · 전력 쪽 등락과 번짐 여부 | 위 주가로 우리가 계산 |
| `data/agent/kic_agent/news/<날>.json` | 기사 제목 자료 25일분 — 날마다 제목 · 출처 · 수집 시각 · 주소 15건 | GDELT 15분 파일 |
| `data/relations/{us,kr}/edges.json` | 거래 관계 장부 128건 | SEC EDGAR · DART · 회사 자료 · 언론 보도, 2026-11-10 모음 |
| `data/net/net_result.json` · `universe.json` · `theme_names.json` · `bundles/` | 공개 보유 종목의 업종 · 보유 금액 · 묶음 가르기 코드와 결과 | 13F 정보표 · 업종 분류 · 우리 계산 |
| `data/bloomberg_tickers.csv` | 티커 → 블룸버그 종목 표기 659줄 | 규칙으로 만듦(단말 대조 못 함) |

## 주가는 등락률로 넣었습니다

야후 파이낸스 약관은 개인 · 비상업 이용이라 종가 원자료는 넣지 않았습니다. 대신 종가에서 계산한 일별 등락률(첫 거래일 0, 그 뒤는 앞 거래일 수정 종가 대비 — 반올림 없이)을 넣었고, 분석 코드는 이 등락률을 이어 곱해(첫날 100) 씁니다. 코드가 쓰는 것은 등락률과 2026-06-30 공개 보유 금액뿐이라 결과는 종가로 계산한 것과 같습니다(2026-11-12 에 두 방법으로 돌려 결과 파일을 맞대 봄 — 반올림해 적은 값은 모두 같았고, 반올림 없이 적힌 `analysis/B2_roles/score/score.json` 의 값만 소수 15째 자리에서 달랐습니다). 종가 자체가 필요하면 `python -X utf8 data/fetch_prices.py --source public`(야후) 이나 `--source bloomberg`(블룸버그 단말)로 새로 받습니다. 쓰는 법은 README 「주가 원천 바꾸기」. 앞 판의 받기 코드 `analysis/A3_hedge/fetch_etf.py` · `analysis/C2_use/fetch_etf.py` 는 이 코드로 합쳐 뺐습니다.

기사 본문 · 받아 둔 웹 원문 · 공사 보고서 PDF 는 저작권이 각 언론사 · 회사 · 공사에 있어 넣지 않았습니다. 제목 · 출처 · 날짜 · 주소 · 짧은 인용만 넣었습니다.

## 글이 가리키지만 이 저장소에 없는 파일

- 판단 실험에서 AI 에게 보여 준 날마다 자료 묶음(`agent/kic_agent/cases/`) · 앞 판 판정관 기록(`records.json`): 넣지 않음(기사에서 뽑은 글이 들어 있을 수 있는데 한 줄씩 확인하지 못함). 그래서 `analysis/B2_roles/` · `B_agent/` 의 입력 묶음 만들기 코드(`tool.py` · `inp.py` · `chk.py` · `ag.py`)와 `B_agent/score.py` 는 다시 돌지 않음
- 앞 판 폴더 `analysis/C_use/` · `D_ledger/` 와 중간 자료(`net/holdings_panel/` · `proposal/r2b/` · 공개 화면 기록): `analysis/C2_use/sheet2.py` · `effect.py` · `analysis/A_problem/misc.py` 가 읽음
- 받아 둔 웹 원문 · 공사 문서 원문: `analysis/C2_use/web/` · `analysis/K_kicdocs/web/` · `pages.json` · `pages_sel.txt` · `board.txt` · `f2_pages.txt` · `misc.txt`
