# -*- coding: utf-8 -*-
"""
現在の構成で記事をテスト生成（比較用）
"""
import yaml, feedparser, re
from pathlib import Path
from dotenv import dotenv_values
from anthropic import Anthropic
from langdetect import detect
import sys
sys.path.append(str(Path(__file__).parent / "src"))
from model_helper import create_message_with_fallback

BASE = Path(__file__).resolve().parent
CFG = yaml.safe_load(open(BASE / "config" / "config.yaml", "r", encoding="utf-8"))
ENV = dotenv_values(BASE / ".env")

def strip_html(s):
    return re.sub(r"<[^>]+>", "", s or "").strip()

def fetch_one():
    feeds = CFG.get("fetch", {}).get("feeds", [])
    for f in feeds:
        url = f.get("url")
        if not url:
            continue
        try:
            d = feedparser.parse(url)
            if d.entries:
                e = d.entries[0]
                title = strip_html(e.title)
                link = e.link
                summary = strip_html(e.summary or e.description or "")[:500]
                source = d.feed.get("title", url)
                try:
                    lang = detect((title + " " + summary)[:1000])
                except:
                    lang = "unknown"
                return {
                    "title": title,
                    "link": link,
                    "summary": summary,
                    "source": source,
                    "domain": url.split('/')[2],
                    "lang": lang
                }
        except Exception as e:
            continue
    return None

def main():
    item = fetch_one()
    if not item:
        print("記事が取得できませんでした")
        return

    print("=== 現在の構成でテスト生成 ===")

    client = Anthropic(api_key=ENV.get("ANTHROPIC_API_KEY"))

    # 現在のプロンプト（post_dedup_value_add.pyから）
    system = "あなたは日本語のテック編集者。出力はHTMLのみ。原文のコピペは避け、要約＋独自解説で、実務インパクト・落とし穴・KPIを含めて書く。"

    user = f"""
以下の元記事を踏まえ、HTMLのみで価値ある日本語記事を作成（Markdown禁止）。
使ってよいタグ：h1,h3,p,ul,li,div,strong,em,code
先頭に <p data-meta="description">120字以内の要約</p>
構成：
<h1>独自観点のタイトル</h1>
<p>リード（読者メリット）</p>
<ul><li>要点×5（事実＋示唆）</li></ul>
<h3>背景と何が新しいか</h3><p>…</p>
<h3>現場への影響（部門別）</h3><ul><li>…</li></ul>
<h3>今できること/まだ難しいこと</h3><ul><li>…</li></ul>
<h3>導入の落とし穴と対策</h3><ul><li>…</li></ul>
<h3>KPIと検証プロトコル</h3><ul><li>例：作業時間、品質、誤検出率、ROI</li></ul>
<div class="source"><strong>出典:</strong> {item["title"]}（{item["domain"]}）</div>
厳守：本文はあなた自身の表現。原文と8語以上の連続一致は禁止。リンクは本文に埋め込まない。
元情報：
- title: {item["title"]}
- link: {item["link"]}
- summary: {item["summary"]}
- language_hint: {item["lang"]}
""".strip()

    print("=== 記事生成中... ===")
    msg = create_message_with_fallback(
        client,
        system=system,
        messages=[{"role": "user", "content": user}]
    )

    html = "".join([p.text for p in msg.content if p.type == "text"]).strip()

    if not html:
        print("記事生成が空でした")
        return

    # 保存
    out_dir = BASE / "out"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "test_old_structure.html"

    full_html = f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<style>
body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    line-height: 1.8;
    padding: 40px;
    max-width: 800px;
    margin: 0 auto;
    background: #f5f5f5;
}}
.container {{
    background: white;
    padding: 40px;
    border-radius: 8px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}}
h1 {{
    font-size: 28px;
    line-height: 1.4;
    margin-bottom: 20px;
    color: #333;
}}
h3 {{
    font-size: 20px;
    margin-top: 32px;
    margin-bottom: 16px;
    color: #444;
}}
p {{
    margin-bottom: 16px;
    color: #555;
}}
ul {{
    margin-bottom: 16px;
}}
li {{
    margin-bottom: 8px;
}}
.source {{
    margin-top: 40px;
    padding-top: 20px;
    border-top: 1px solid #ddd;
    font-size: 14px;
    color: #666;
}}
</style>
</head>
<body>
<div class="container">
{html}
</div>
</body>
</html>"""

    out_path.write_text(full_html, encoding="utf-8")

    print(f"\n✅ 記事を生成しました: {out_path}")
    print("\n=== 生成された記事（先頭500文字） ===")
    print(html[:500])
    print("...")

if __name__ == "__main__":
    main()
