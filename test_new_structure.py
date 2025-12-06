# -*- coding: utf-8 -*-
"""
新構成で記事をテスト生成
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

                # 言語判定
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
            print(f"Error fetching {url}: {e}")
            continue
    return None

def main():
    item = fetch_one()
    if not item:
        print("記事が取得できませんでした")
        return

    print("=== 取得した記事 ===")
    print(f"タイトル: {item['title']}")
    print(f"リンク: {item['link']}")
    print(f"要約: {item['summary'][:200]}...")
    print()

    client = Anthropic(api_key=ENV.get("ANTHROPIC_API_KEY"))

    # 新しいプロンプト
    system = """あなたは技術ニュースライターです。

【記事作成の原則】
- ニュース記事の基本を守る（速報性・事実性・簡潔性）
- 理解しやすく書く（専門用語は説明、具体例を使う）
- 読者視点を忘れない（影響や意味を明示）

【文章ルール】
- 1文20語以内、短く簡潔に
- 1段落3-5文以内
- 専門用語は初出時に必ず説明
- 具体的な数値・日付を使う
- 曖昧な表現を避ける"""

    user = f"""以下の元記事から、わかりやすい日本語ニュース記事を作成してください。

【必須要素と構成】
1. メタディスクリプション（120字以内）
   <p data-meta="description">【誰が】【何を】【いつ】。【主な内容1文】。【影響1文】。</p>

2. タイトル（H1、50-60文字）
   <h1>【主語】が【動詞】【目的語】、【補足情報】</h1>

3. リード段落（150-200字）
   <p>【日時】、【誰が】【何を】しました。【最重要ポイント1文】。【背景または意味1文】。</p>

4. 本文（H3見出しで整理、記事内容に応じて柔軟に構成）
   - 主な内容の説明（必要に応じて箇条書き）
   - 専門用語が出たら、その場で説明
   - 従来との違い（該当する場合）
   - 読者への影響（必須）

5. 出典
   <div class="source"><strong>出典：</strong>【元記事タイトル】（【ドメイン】、【日付推定】）</div>

【重要な指示】
- 逆ピラミッド構造：重要な情報を最初に
- 専門用語は「○○とは、【定義】です」の形で説明
- 具体例を積極的に使用
- 前提知識を要求しない
- 「この技術により、【具体的な変化】が期待されます」のように読者視点を含める

元記事情報：
- タイトル: {item['title']}
- リンク: {item['link']}
- 要約: {item['summary']}
- ソース: {item['source']}
- ドメイン: {item['domain']}
- 言語: {item['lang']}

HTMLのみで出力してください（Markdown禁止）。
使用可能タグ：h1, h3, p, ul, li, div, strong, em, code"""

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
    out_path = out_dir / "test_new_structure.html"

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
