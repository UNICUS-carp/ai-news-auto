# -*- coding: utf-8 -*-
import os, re, yaml, feedparser
from pathlib import Path
from langdetect import detect, DetectorFactory
from dotenv import dotenv_values
from anthropic import Anthropic
from model_helper import create_message_with_fallback

DetectorFactory.seed = 0
BASE = Path(__file__).resolve().parent.parent
CFG  = yaml.safe_load(open(BASE / "config" / "config.yaml", "r", encoding="utf-8"))
ENV  = dotenv_values(BASE / ".env")

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

def fetch_one():
    feeds = CFG.get("fetch", {}).get("feeds", [])
    for f in feeds:
        url = f.get("url")
        if not url: 
            continue
        d = feedparser.parse(url)
        if d.entries:
            e = d.entries[0]  # とりあえず各フィードの先頭のみ
            title = strip_html(getattr(e, "title", ""))
            link  = getattr(e, "link", "")
            summary = strip_html(getattr(e, "summary", "") or getattr(e, "description", ""))
            source = d.feed.get("title", url)
            lang = guess_lang((title + " " + summary)[:1000])
            return {
                "source": source, "title": title, "link": link,
                "summary": summary, "lang": lang
            }
    return None

def main():
    item = fetch_one()
    if not item:
        print("記事候補が取得できませんでした。")
        return

    # Claude クライアント
    api_key = ENV.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY が .env にありません。")
        return
    client = Anthropic(api_key=api_key)

    # プロンプト（影響セクションは「具体例・できる/難しい・KPI」を必須に）
    system = "あなたは日本語のテック記者です。固有名詞・数値・日付は原文準拠。過度な一般化は禁止。"
    user = f"""以下の元記事情報にもとづき、WordPress投稿用の下書きを日本語で生成してください。

# 出力仕様（厳守）
- title（~62文字）
- lead（180字以内, 2–3文）
- bullets（5点, <ul><li>…</li></ul>）
- body（700–1000字, セクション小見出しに<h3>推奨）
- impact_block（HTML。以下の順で必須）
  <section id="impact">
    <h3>影響と活用</h3>
    <h4>即効の業務インパクト</h4><ul><li>…</li></ul>（3–5点、定量/準定量を含む）
    <h4>できるようになること／まだ難しいこと</h4>
    <table><thead><tr><th>できるようになること</th><th>まだ難しいこと</th></tr></thead><tbody>
    <tr><td>…</td><td>…</td></tr></tbody></table>
    <h4>導入の前提条件と難易度</h4><p>…</p>
    <h4>部門別ユースケース</h4><ul><li>…</li></ul>
    <h4>成果測定KPI</h4><ul><li>…</li></ul>
  </section>
- meta_description（120字以内）
- source_block（HTML, 出典リンクは target="_blank" rel="nofollow"）

# 元情報
- source: {item["source"]}
- title: {item["title"]}
- link: {item["link"]}
- summary: {item["summary"]}
- language_hint: {item["lang"]}
"""

    msg = create_message_with_fallback(
        client,
        system=system,
        messages=[{"role":"user","content":user}]
    )
    parts = msg.content
    text = "".join([p.text for p in parts if p.type=="text"]).strip()
    if not text:
        print("生成結果が空でした。")
        return

    # 生成物をシンプルなHTMLに包んで保存（プレビュー用）
    html = f"""<!doctype html><meta charset="utf-8">
<style>body{{font-family:-apple-system,Helvetica,Arial,'Hiragino Kaku Gothic ProN',Meiryo;line-height:1.7;padding:24px;max-width:860px;margin:auto}}</style>
<h2>プレビュー（Claude生成）</h2>
<p><strong>元記事:</strong> <a href="{item['link']}" target="_blank" rel="nofollow">{item['title']}</a> / <em>{item['source']}</em></p>
<hr>
{ text }
"""
    outdir = BASE / "out"
    outdir.mkdir(exist_ok=True)
    outpath = outdir / "generated_preview.html"
    outpath.write_text(html, encoding="utf-8")

    print("=== 生成テキスト（先頭だけ） ===")
    print(text[:500] + ("\n...(省略)..." if len(text)>500 else ""))
    print("\n保存先:", outpath)

if __name__ == "__main__":
    main()
