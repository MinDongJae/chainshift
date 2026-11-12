# 쓰임: python -I extract.py <pdf> <out.json>  — 쪽별 글을 뽑아 저장하고 낱말별로 걸린 쪽을 찍는다
import sys, json, re, fitz
doc = fitz.open(sys.argv[1])
pages = [p.get_text() for p in doc]
json.dump(pages, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False)
print("pages", len(pages), "chars", sum(map(len, pages)))
for kw in ["추적오차","VaR","스트레스","한도","시나리오","집중","쏠림","반도체","AI","인공지능","헤지","파생","상호 검증","단계별","TPA","전체 포트폴리오","공통 요인","요인","빅테크","기술주","테마","모니터링"]:
    print(kw, [i+1 for i,t in enumerate(pages) if kw in t])
