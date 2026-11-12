# B2_roles/check1 결과

점검 역할의 결과 글은 같은 폴더 CHECK_DONE.md 한 장이다(채점 전이라 맞힌 비율은 없다). 사전 고정 prereg.md · 날짜별 판정 judgments/ 25개 · 쓴 차례 order_log.txt · 노출 기록 leaked.txt · 도구 tool.py · 집계 done.py.
입력: analysis/B2_roles/interpret/judgments/*.json · $CHAINSHIFT_DATA/agent/kic_agent/{cases,news} · net/backtest/prices_long.csv.gz · mcp_kic_precheck/kic_precheck/data/chain.json · 연결 도구 news_search.

기획서에 옮길 수 있는 문장(채점 전, 수는 done.py 가 judgments/*.json 을 센 값):
「해석과 다른 개체가 점검을 맡아 칩 충격일 25일의 판정 근거를 원자료에 다시 맞댔다. 해석이 댄 제목은 모두 실제로 있었으나, 25일 중 24일에서 장 마감 뒤에 나온 기사나 앞 충격일의 전력 쪽 값에 기댄 근거가 섞여 있어 그것을 빼고 다시 셌다. 그 결과 해석의 '번진다' 12일 가운데 7일을 '사람에게 넘긴다'로 바꿨다(끝 판정: 번진다 5 · 안 번진다 3 · 넘김 17). 날마다 더 쓴 도구는 1~3번, 모두 43번.」

한계: 마감 뒤 여부는 기사 파일의 시각(15분 단위, 실제 발행보다 늦을 수 있음)으로 갈랐다. 기사 파일은 날마다 상위 15건만 담는다. 해석과 같은 모델이다.
불리한 점: 점검을 거치면 넘김이 10일에서 17일(68%)로 늘고, 넘김을 확정으로 바꾼 날은 0일이다. 2026-09-14 는 미리 적은 '근거 절반이 빠지면 넘긴다' 규칙이 지나치게 걸린 날로, 남은 근거만 보면 '번진다'가 유지된다. 확신 '높음'은 0일.
