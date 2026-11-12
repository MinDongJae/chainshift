# 주가 원천 바꾸기

기본은 저장소에 든 일별 등락률 파일입니다. 한국투자공사처럼 블룸버그 단말이 있는 곳은 아래 한 줄로 같은 종목 · 같은 기간의 일별 종가를 블룸버그에서 받아 같은 자리에 같은 모양(등락률)으로 바꿔 쓰고, 그 뒤 위 명령을 그대로 돌립니다(분석 코드와 하루 실행기는 고칠 것이 없습니다).

```
python -X utf8 data/fetch_prices.py --source bloomberg --apply      # 블룸버그 단말(blpapi, localhost:8194)
python -X utf8 data/fetch_prices.py --source public --apply         # 무료 공개 출처(야후 파이낸스, pip install yfinance)
python -X utf8 data/fetch_prices.py                                 # 지금 든 파일의 종목 수 · 기간만 찍음
```

- 아침 실행: `python -X utf8 agent/morning.py --source bloomberg` 가 전날 종가까지 받아 `data_live/` 에 덧붙이고 하루 점검을 돌립니다. 급락일이면 그날 기사 제목도 받습니다(`agent/fetch_news.py`). 저장소에 든 `data/` 는 바꾸지 않습니다.
- `--apply` 를 빼면 `data/refetch/` 에 쓰고 원래 파일은 그대로 둡니다. 새로 받은 값은 배당 · 분할 조정 시점이 달라 든 값과 끝자리가 다를 수 있고 결과의 수도 조금 달라질 수 있습니다(야후에서 펀드 7개를 2026-11-12 에 다시 받아 보니 하루 등락률의 가장 큰 차이가 0.00008%p 였습니다). 받은 종가 자체는 파일로 남기지 않습니다.
- 블룸버그 종목 표기는 `data/bloomberg_tickers.csv`(659줄, 예: `VRT` → `VRT US Equity` · `BRK-B` → `BRK/B US Equity`)에서 읽습니다. 「티커 + US Equity」 규칙으로 만든 표라 단말에서 대조하지는 못했습니다. 틀린 줄은 이 파일에서 고치면 됩니다.
- 호출은 우리 팀의 블룸버그 MCP(bloomberg-mcp-intelligence, 별도 저장소 — 코드는 여기 넣지 않음)의 `bdh` 도구와 같은 요청입니다(`HistoricalDataRequest` · `PX_LAST` · `DAILY`). AI 가 대화 중에 같은 값을 직접 조회하게 하려면 `.mcp.json.example` 을 `.mcp.json` 으로 복사해 그 저장소 경로를 적고, `bdh(securities=["VRT US Equity"], fields=["PX_LAST"], start_date="20261001", end_date="20261022")` 처럼 부릅니다. 차이 하나: `fetch_prices.py` 는 야후 수정 종가와 맞추려고 배당 · 분할 조정을 요청에 직접 켜고, `bdh` 도구는 단말의 조정 설정을 따릅니다.
- 블룸버그 경로는 단말(localhost:8194)이 켜진 PC 에서 돕니다. 이 저장소는 단말이 없는 PC 에서 만들어, 실제로 받아 확인한 것은 공개 출처 경로입니다(2026-11-12 아침 실행으로 2026-11-11 종가까지 받음).
