# -*- coding: utf-8 -*-
"""하루치 기사 제목 받기 — 하루 점검의 03 · 04 · 06 단계가 읽는 자료를 만든다.
그날 0시~24시(UTC) GDELT 2.1 GKG 15분 파일 96개를 받으면서 58종목이 나온 기사를 세고, 점수 높은 제목 15건을 남긴다.
회사 찾기: 기사에서 뽑힌 기관 이름에 정식 회사 이름이 그대로 있으면 센다. 한 낱말 이름은 기사 제목이나 주소에도 있어야 센다.
받은 파일은 저장하지 않는다. 남기는 것은 제목 · 출처 · 수집 시각 · 주소뿐이다(본문 없음).
쓰는 법:  python -X utf8 agent/fetch_news.py 2026-11-11        → data/agent/kic_agent/news/2026-11-11.json
          python -X utf8 agent/fetch_news.py 2026-11-11 --stdout  → 파일로 쓰지 않고 찍기만"""
import io, json, re, sys, time, zipfile, ssl, collections, urllib.request, datetime
try:
    import certifi; CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    CTX = ssl.create_default_context()
import os
from pathlib import Path
K = Path(os.environ.get('CHAINSHIFT_DATA', 'data'))
KW = json.loads((K / 'agent/news_kw.json').read_text(encoding='utf-8'))
UA = {'User-Agent': 'chainshift (value chain news titles)'}
get = lambda u: urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=120, context=CTX).read()
DATE = sys.argv[1]; DAY = DATE.replace('-', '')  # YYYY-MM-DD 또는 YYYYMMDD
DATE = f'{DAY[:4]}-{DAY[4:6]}-{DAY[6:]}'
t_end = datetime.datetime.strptime(DAY + '234500', '%Y%m%d%H%M%S')
stamps = [(t_end - datetime.timedelta(minutes=15 * i)).strftime('%Y%m%d%H%M%S') for i in range(96)]
DC = re.compile(r'data[\s\-]?cent(er|re)s?', re.I)
TITLE = re.compile(r'<PAGE_TITLE>(.*?)</PAGE_TITLE>', re.S)
stage_of = {t: v['stage'] for t, v in KW.items()}
cnt_t = collections.Counter(); cnt_s = collections.Counter(); tone_s = collections.defaultdict(float)
dc_all = 0; dc_s = collections.Counter(); tot = 0; hit = 0; files = 0; miss = []; items = {}
t0 = time.time()
for st in stamps:
    try:
        raw = get(f'http://data.gdeltproject.org/gdeltv2/{st}.gkg.csv.zip')
    except Exception:
        miss.append(st); continue
    files += 1
    z = zipfile.ZipFile(io.BytesIO(raw))
    with z.open(z.namelist()[0]) as f:
        for line in io.TextIOWrapper(f, encoding='utf-8', errors='replace'):
            c = line.rstrip('\n').split('\t')
            if len(c) < 16:
                continue
            tot += 1
            orgs = set(o.strip() for o in (c[13] or '').lower().split(';') if o.strip())
            if not orgs:
                continue
            url = (c[4] or '').lower()
            m = TITLE.search(c[26]) if len(c) > 26 else None
            title = re.sub(r'\s+', ' ', m.group(1)).strip() if m else ''
            tl = title.lower()
            ticks = []
            for t, v in KW.items():
                k = v['keys'][0]
                if k in orgs and (not v['single'] or k in tl or k.replace(' ', '') in url):
                    ticks.append(t)
            if not ticks:
                continue
            hit += 1
            try:
                tone = float((c[15] or '0').split(',')[0])
            except ValueError:
                tone = 0.0
            dc = bool(DC.search(tl) or DC.search(url))
            stg = sorted(set(stage_of[t] for t in ticks))
            for t in ticks:
                cnt_t[t] += 1
            for s in stg:
                cnt_s[s] += 1; tone_s[s] += tone
                if dc: dc_s[s] += 1
            dc_all += dc
            if title:
                key = tl[:90]
                score = len(ticks) * 2 + (3 if dc else 0) + len(stg)
                prev = items.get(key)
                if prev is None or score > prev['score']:
                    items[key] = {'t': c[1], 'title': title[:220], 'url': c[4], 'src': c[3], 'ticks': ticks, 'stages': stg,
                                  'tone': round(tone, 2), 'dc': dc, 'score': score}
    time.sleep(0.2)
top = sorted(items.values(), key=lambda x: (-x['score'], -int(x['t'] or 0)))[:15]
OUT = json.dumps({'window_utc': [stamps[-1], stamps[0]], 'files': files, 'missing': miss, 'records': tot, 'hit_records': hit,
                  'by_stage': {s: {'n': cnt_s[s], 'tone': round(tone_s[s] / cnt_s[s], 2) if cnt_s[s] else None, 'dc': dc_s[s]} for s in sorted(set(stage_of.values()))},
                  'by_company': dict(cnt_t.most_common()), 'dc_hit_records': dc_all, 'unique_titles': len(items), 'top': top,
                  'seconds': round(time.time() - t0)}, ensure_ascii=False)
if '--stdout' in sys.argv:
    print(OUT)
else:
    p = K / 'agent/kic_agent/news' / f'{DATE}.json'; p.write_text(OUT, encoding='utf-8')
    print(DATE, '받은 파일', files, '· 기사', tot, '· 58종목이 나온 기사', hit, '· 남긴 제목', len(top), '→', p.as_posix())
