# -*- coding: utf-8 -*-
import yaml, feedparser, re
from pathlib import Path
from langdetect import detect, DetectorFactory
DetectorFactory.seed = 0

BASE = Path(__file__).resolve().parent.parent
CFG = yaml.safe_load(open(BASE / "config" / "config.yaml", "r", encoding="utf-8"))

def strip_html(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s or "").strip()

def guess_lang(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return "unknown"
    try:
        return detect(t)
    except Exception:
        return "unknown"

def main():
    feeds = CFG.get("fetch", {}).get("feeds", [])
    total = 0
    for f in feeds:
        url = f.get("url")
        if not url: 
            continue
        d = feedparser.parse(url)
        source = d.feed.get("title", url)
        print(f"\n=== SOURCE: {source} ===")
        cnt = 0
        for e in d.entries[:5]:  # 各フィード上位5件だけ表示
            title = strip_html(getattr(e, "title", ""))
            link  = getattr(e, "link", "")
            summary = strip_html(getattr(e, "summary", "") or getattr(e, "description", ""))
            lang = guess_lang((title + " " + summary)[:1000])
            print(f"- [{lang}] {title}\n  {link}")
            cnt += 1
            total += 1
        if cnt == 0:
            print("(no items)")
    print(f"\nTOTAL ITEMS SHOWN: {total}")

if __name__ == "__main__":
    main()
