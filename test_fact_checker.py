# -*- coding: utf-8 -*-
"""
ファクトチェック機能のテスト
"""
import yaml
import feedparser
import re
from pathlib import Path
from dotenv import dotenv_values
from anthropic import Anthropic
from langdetect import detect
import sys

sys.path.append(str(Path(__file__).parent / "src"))
from model_helper import create_message_with_fallback
from fact_checker import fact_check_article, print_fact_check_result

BASE = Path(__file__).resolve().parent
CFG = yaml.safe_load(open(BASE / "config" / "config.yaml", "r", encoding="utf-8"))
ENV = dotenv_values(BASE / ".env")


def strip_html(s):
    return re.sub(r"<[^>]+>", "", s or "").strip()


def fetch_one():
    """RSSフィードから1件取得"""
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
                    "domain": url.split("/")[2],
                    "lang": lang,
                }
        except Exception as e:
            continue
    return None


def main():
    print("=" * 80)
    print("ファクトチェック機能のテスト")
    print("=" * 80)

    # 1. 記事を取得
    print("\n[1] RSSフィードから記事を取得中...")
    item = fetch_one()
    if not item:
        print("❌ 記事が取得できませんでした")
        return

    print("✅ 記事を取得しました")
    print(f"  タイトル: {item['title'][:60]}...")
    print(f"  ソース: {item['source']}")
    print(f"  リンク: {item['link']}")

    # 2. 記事を生成
    print("\n[2] AI記事を生成中...")
    client = Anthropic(api_key=ENV.get("ANTHROPIC_API_KEY"))

    system = """あなたは技術ニュースライターです。

【記事作成の原則】
- ニュース記事として事実を正確に伝える
- 専門知識のない読者でも理解できるよう丁寧に説明する
- 読者にとっての意味や影響を明示する

【文章ルール】
- 1文は20語以内を目安に、短く簡潔に
- 1段落は3-5文以内
- 専門用語は初出時に必ず説明（「○○とは、～のことです」）
- 具体的な数値・日付・固有名詞を使う
- 曖昧な表現を避ける

【HTMLタグ】
- h1, h3, p, ul, li, div, strong, em, codeのみ使用
- コードブロックマーカー（```html など）は絶対に出力しない
- HTMLタグの外にテキストを書かない"""

    user = f"""以下の元記事から、わかりやすい日本語ニュース記事を作成してください。

【記事構成】

1. メタディスクリプション（120字以内）
<p data-meta="description">【誰が】【何を】【いつ】。【主な内容1文】。【影響1文】。</p>

2. タイトル（H1、50-60文字）
<h1>【事実を簡潔に】</h1>

3. リード段落（300-400字）※重要：丁寧にわかりやすく説明
<p>
【第1文】いつ、誰が、何をしたか（5W1H）
【第2-3文】その内容の詳細、重要なポイント
【第4-5文】なぜこれが重要なのか、背景
【第6文】読者への影響や意味
</p>

4. 本文（H3見出しで整理、全体で1,500-2,000字）

<h3>【具体的な見出し】</h3>
<p>
・発表内容の詳細
・数値やデータがあれば具体的に
・専門用語は「○○とは、～のことです。【具体例】」の形で説明
</p>

<h3>背景と経緯</h3>
<p>
・なぜこのニュースが出たのか
・これまでの経緯
・業界の状況
</p>

<h3>技術的な詳細（該当する場合）</h3>
<p>
・どんな技術・仕組みか
・従来との違い
・具体的にどう動作するか
※難しい概念は身近な例えで説明
</p>

<h3>できること・できないこと</h3>
<p>
【文章形式で説明】
この技術により、【具体的にできること】が可能になります。例えば、【具体例1】や【具体例2】といった使い方が考えられます。

一方で、【まだ難しいこと】もあります。【制約や限界を説明】。【時期】には【改善の見込み】でしょう。
</p>

<h3>私たちへの影響</h3>
<p>
【読者の視点で】
このニュースは、【対象読者】に【どんな影響】を与えます。

【短期的な影響】については、【具体的に】。
【中長期的な影響】としては、【予測】が考えられます。

ただし、【注意点や留意事項】。
</p>

5. 出典
<div class="source"><strong>出典：</strong>【元記事タイトル】（【ドメイン】）</div>

【重要な指示】
- リード段落は特に丁寧に、300-400字かけて説明する
- 逆ピラミッド構造：重要な情報を最初に
- 箇条書きは必要最小限、基本は文章で説明
- 「できること・できないこと」「影響」は文章形式
- 専門用語には必ず説明と具体例をつける

元記事情報：
- タイトル: {item['title']}
- リンク: {item['link']}
- 要約: {item['summary']}
- ソース: {item['source']}
- ドメイン: {item['domain']}
- 言語: {item['lang']}

HTMLのみで出力してください。Markdown禁止。コードブロックマーカーは使用禁止。"""

    try:
        msg = create_message_with_fallback(
            client, system=system, messages=[{"role": "user", "content": user}]
        )
        html = "".join([p.text for p in msg.content if p.type == "text"]).strip()
        print("✅ 記事を生成しました")
    except Exception as e:
        print(f"❌ 記事生成エラー: {e}")
        return

    # 3. ファクトチェック実行
    print("\n[3] ファクトチェックを実行中...")
    result = fact_check_article(item, html)

    # 4. 結果を表示
    print_fact_check_result(result)

    # 5. 生成記事のプレビュー
    print("\n[4] 生成された記事のプレビュー（最初の500文字）")
    print("-" * 80)
    text_only = re.sub(r"<[^>]+>", " ", html)
    text_only = re.sub(r"\s+", " ", text_only).strip()
    print(text_only[:500] + "...")
    print("-" * 80)

    # 6. 結果のサマリー
    print("\n" + "=" * 80)
    if result["passed"]:
        print("🎉 テスト成功: 記事はファクトチェックに合格しました")
    else:
        print("⚠️  テスト結果: 記事にはいくつかの問題があります")
        print(f"   - 重大な問題: {len(result['issues'])}件")
        print(f"   - 警告: {len(result['warnings'])}件")
    print("=" * 80)


if __name__ == "__main__":
    main()
