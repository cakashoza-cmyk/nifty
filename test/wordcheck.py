"""Recommendation-word check (SEBI-safe framing). Scans UI strings, static pages and, if present, the rendered page text
saved by test/verify.py. Only the exact disclaimer sentences may contain 'investment advice' / 'Investment Adviser' words.
Usage: python3 test/wordcheck.py  (exit 1 on any hit)"""
import re, sys, glob
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
WORDS = [r"\bbuy\w*", r"\bbought\b", r"\bsell\w*", r"\bsold\b", r"\bhold\w*", r"\binvest\w*", r"\bexit\w*", r"\btargets?\b", r"stop[- ]?loss", r"\byou should\b", r"\bentry\b",
         "ખરીદ", "વેચ", "રોકાણ", "હોલ્ડ", "લક્ષ્ય", "ટાર્ગેટ", "નીકળ", "સ્ટોપ",
         "खरीद", "ख़रीद", "बेच", "निवेश", "होल्ड", "लक्ष्य", "टारगेट", "निकल", "स्टॉप"]
ALLOW = ["Not investment advice", "SEBI-registered Investment Adviser", "આ રોકાણ સલાહ નથી", "SEBI-રજિસ્ટર્ડ રોકાણ સલાહકાર", "यह निवेश सलाह नहीं है", "SEBI-पंजीकृत निवेश सलाहकार",
         "not investment advice", "SEBI-registered investment adviser"]


def scan(text):
    for a in ALLOW:
        text = text.replace(a, " ")
    return sorted({m.group(0) for w in WORDS for m in re.finditer(w, text, re.I)})


def main():
    files = [ROOT / "assets/i18n.js", ROOT / "index.html", ROOT / "methodology.html", ROOT / "README.md"] + [Path(p) for p in glob.glob(str(ROOT / "shots/rendered_*.txt"))]
    bad = 0
    for f in files:
        if not f.exists():
            continue
        hits = scan(f.read_text(encoding="utf-8"))
        print(f"{f.relative_to(ROOT)}: {'OK' if not hits else 'HITS ' + ', '.join(hits)}")
        bad += bool(hits)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
