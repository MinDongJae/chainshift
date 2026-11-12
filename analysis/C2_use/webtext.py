# -*- coding: utf-8 -*-
"""받아 둔 소개 쪽(web/*.html·pdf)에서 글자만 뽑아 web/*.txt 로 둔다. 쓰는 법: python -I -X utf8 webtext.py web/파일 ..."""
import sys, re, html
from pathlib import Path
for p in map(Path, sys.argv[1:]):
    if p.suffix == ".pdf":
        from pypdf import PdfReader
        t = "\n".join((pg.extract_text() or "") for pg in PdfReader(str(p)).pages)
    else:
        s = p.read_text(encoding="utf-8", errors="replace")
        s = re.sub(r"(?is)<(script|style|noscript|svg)\b.*?</\1>", " ", s)
        t = html.unescape(re.sub(r"(?s)<[^>]+>", "\n", s))
    t = re.sub(r"[ \t\r\f]+", " ", t); t = re.sub(r"\n\s*\n+", "\n", t)
    p.with_suffix(".txt").write_text(t, encoding="utf-8"); print(p.name, len(t))
