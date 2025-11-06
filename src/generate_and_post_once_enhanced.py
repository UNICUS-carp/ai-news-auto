# -*- coding: utf-8 -*-
"""
generate_and_post_once_enhanced.py
- より詳しく実用的な記事生成（実用性重視・信頼性向上）
- 段階的導入のための安全版
"""
import os, re, yaml, feedparser, json
from datetime import datetime, timedelta
from pathlib import Path
from langdetect import detect, DetectorFactory
from dotenv import dotenv_values
from anthropic import Anthropic
import requests
from requests.auth import HTTPBasicAuth
from urllib.parse import urljoin

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

def calculate_freshness(published_date=None):
    """記事の新しさを計算"""
    if not published_date:
        return "発表日不明"
    
    try:
        if hasattr(published_date, 'strftime'):
            pub_date = published_date
        else:
            # 文字列の場合のパース処理
            return "発表日解析中"
        
        now = datetime.now()
        diff = now - pub_date
        
        if diff.days == 0:
            return f"本日発表"
        elif diff.days == 1:
            return f"昨日発表"
        elif diff.days <= 7:
            return f"{diff.days}日前発表"
        elif diff.days <= 30:
            weeks = diff.days // 7
            return f"{weeks}週間前発表"
        else:
            months = diff.days // 30
            return f"{months}ヶ月前発表"
    except:
        return "発表日不明"

def pick_first_item():
    """シンプルに：登録フィードの先頭エントリを1本だけ選ぶ"""
    feeds = CFG.get("fetch", {}).get("feeds", [])
    for f in feeds:
        url = f.get("url")
        if not url:
            continue
        d = feedparser.parse(url)
        if d.entries:
            e = d.entries[0]
            title = strip_html(getattr(e, "title", ""))
            link  = getattr(e, "link", "")
            summary = strip_html(getattr(e, "summary", "") or getattr(e, "description", ""))
            source = d.feed.get("title", url)
            lang = guess_lang((title + " " + summary)[:1000])
            
            # 発表日の取得
            published = getattr(e, 'published_parsed', None)
            freshness = calculate_freshness(published)
            
            return {
                "source": source, "title": title, "link": link,
                "summary": summary, "lang": lang, "freshness": freshness
            }
    return None

def main():
    # === WP接続情報 ===
    WP_URL  = (ENV.get("WP_URL","") or "").strip()
    WP_USER = (ENV.get("WP_USER","") or "").strip()
    WP_PASS = (ENV.get("WP_APP_PASSWORD","") or "").strip()
    if not (WP_URL and WP_USER and WP_PASS):
        raise SystemExit("WP_URL / WP_USER / WP_APP_PASSWORD が不足しています。")
    if not WP_URL.endswith("/"):
        WP_URL += "/"

    # === 設定読み込み ===
    wp_cfg = (CFG.get("wordpress") or {})
    category_ids = wp_cfg.get("category_ids") or []
    status = wp_cfg.get("status", "draft")
    
    # 新しい設定の読み込み
    gen_cfg = CFG.get("generate", {})
    body_target = gen_cfg.get("body_target_chars", 2000)
    practical_cfg = gen_cfg.get("practical_focus", {})
    reliability_cfg = gen_cfg.get("reliability", {})

    # === フィードから1件 ===
    item = pick_first_item()
    if not item:
        print("記事候補が取得できませんでした。")
        return

    # === Claude ===
    api_key = ENV.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("ANTHROPIC_API_KEY が .env にありません。")
    client = Anthropic(api_key=api_key)

    system = (
        "あなたは日本語のテック記者で、実用性と信頼性を重視します。"
        "固有名詞・数値・日付は原文準拠。過度な一般化・憶測は明確に区別。"
        "出力は **有効なHTMLのみ**。安全なタグ以外は使用禁止。"
    )

    # 実用性重視と信頼性向上の指示を追加
    practical_instructions = ""
    if practical_cfg.get("include_implementation_steps"):
        practical_instructions += "- 具体的な実装手順・導入ステップを詳述\n"
    if practical_cfg.get("include_required_skills"):
        practical_instructions += "- 必要なスキル・技術的要件を明記\n"
    if practical_cfg.get("include_cost_estimation"):
        practical_instructions += "- 想定コスト・投資規模を可能な限り具体的に\n"
    if practical_cfg.get("include_risk_analysis"):
        practical_instructions += "- 潜在的リスクと対処法を分析\n"

    reliability_instructions = ""
    if reliability_cfg.get("show_information_freshness"):
        reliability_instructions += f"- 情報の新しさ：{item['freshness']}\n"
    if reliability_cfg.get("distinguish_confirmed_vs_speculation"):
        reliability_instructions += "- 確定情報と推測を明確に区別（「確定：」「推測：」で表記）\n"

    user = f"""
以下の元記事情報にもとづき、**HTMLのみ**でWordPress投稿用の詳細記事を日本語で生成してください。
目標文字数：{body_target}文字程度の充実した内容にしてください。

# 出力仕様（厳守：HTMLのみ・安全タグのみ）
- 使ってよいタグ：h1, h3, p, ul, li, a, div, strong, em
- 使ってはいけないタグ：table, section, script, style、HTMLコメント（<!-- -->）
- 先頭に <p data-meta="description">…120字以内…</p> を1つ出力（メタディスクリプション）

# 記事構成（文章中心・社会的影響と個人への影響重視）
<h1>title</h1>

<p>背景と現状の課題説明（400-500字程度）
この技術が生まれた背景、現在の社会が抱える課題、なぜこの解決が必要なのかを、ITやAIの専門知識がまったくない読者にも分かるように、日常生活の例を使って丁寧に説明してください。</p>

<p>技術の詳細解説（500-600字程度）
この技術が具体的にどのような仕組みで動くのか、従来の方法と何が根本的に違うのかを説明してください。専門用語（AI、アルゴリズム、API、機械学習など）が出てきた場合は、必ずその場で「〜とは○○のことです」という形で詳しい説明を挿入してください。一般の人が想像できるような身近な例（料理、買い物、読書など）に例えて説明してください。</p>

<h3>この技術で可能になること</h3>
<p>この技術によって具体的にどのようなことができるようになったのかを詳しく説明（400-500字程度）
従来は不可能だったこと、困難だったことが、この技術によってどのように実現可能になったのかを具体例を使って説明してください。「これまでは〜をするために〜の手順が必要でしたが、この技術では〜のように簡単にできるようになりました」という形で、技術的な進歩を分かりやすく説明してください。</p>

<h3>あなたの日常生活への影響</h3>
<p>読者個人の生活にどのような変化をもたらすのかを詳しく説明（400-500字程度）
仕事での変化、家庭生活での変化、学習や娯楽での変化など、読者が「自分の生活がこう変わるかもしれない」と具体的にイメージできるように説明してください。メリットだけでなく、注意すべき点や適応が必要な部分も含めて、バランスよく説明してください。</p>

<h3>重要なポイント</h3>
<p>この技術について読者が覚えておくべき最も重要な3つのポイントを、文章で説明してください（300字程度）
箇条書きではなく、「第一に〜です。第二に〜という点も重要です。第三に〜ということを理解しておく必要があります」という形で、文章として説明してください。</p>

<div class="source"><strong>出典:</strong> <a href="{item["link"]}" target="_blank" rel="nofollow">{item["title"]}</a>（{item["source"]}）</div>

# 実用性重視の指示
{practical_instructions.strip()}

# 元情報
- source: {item["source"]}
- title: {item["title"]}
- link: {item["link"]}
- summary: {item["summary"]}
- language_hint: {item["lang"]}
- freshness: {item["freshness"]}
""".strip()

    msg = client.messages.create(
        model="claude-3-opus-20240229",
        max_tokens=4000,  # より長い生成のため増加
        temperature=0.2,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    parts = msg.content
    html = "".join([p.text for p in parts if p.type == "text"]).strip()
    if not html:
        print("生成結果が空でした。")
        return

    # === メタディスクリプション抽出（data-meta属性） ===
    meta_desc = ""
    m = re.search(r'<p[^>]*data-meta=["\']description["\'][^>]*>(.*?)</p>', html, re.I | re.S)
    if m:
        meta_desc = re.sub(r"\s+", " ", strip_html(m.group(1))).strip()
        if len(meta_desc) > 120:
            meta_desc = meta_desc[:119] + "…"

    # === 念のためのサニタイズ（WAF対策） ===
    html = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    html = re.sub(r"</?section\b[^>]*>", "", html, flags=re.I)
    html = re.sub(r"</?table\b[^>]*>.*?</table>", "", html, flags=re.I | re.S)

    # === タイトル抽出（<h1>…</h1>） ===
    mtitle = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)
    title_for_wp = strip_html(mtitle.group(1)) if mtitle else "(自動生成)AIニュース詳細版"
    title_for_wp = re.sub(r"\s+", " ", title_for_wp)[:62]

    # === WordPressへ下書き投稿（安全のため強制的にdraft） ===
    url = urljoin(WP_URL, "wp-json/wp/v2/posts")
    payload = {
        "title": title_for_wp,
        "content": html,
        "status": "draft",  # 安全のため強制的に下書き
        "categories": category_ids,
        "excerpt": meta_desc or "",
    }
    r = requests.post(url, auth=HTTPBasicAuth(WP_USER, WP_PASS), json=payload, timeout=40)
    print("POST STATUS:", r.status_code)
    try:
        data = r.json()
    except Exception:
        print(r.text[:500]); return

    print(json.dumps({k: data.get(k) for k in ["id","status","link","date","categories","slug"]},
                     ensure_ascii=False, indent=2))

    # ローカル保存（詳細版）
    outdir = BASE / "out"; outdir.mkdir(exist_ok=True)
    (outdir / "generated_enhanced.html").write_text(html, encoding="utf-8")
    print("詳細版ローカル保存:", outdir / "generated_enhanced.html")
    
    # 文字数カウント表示
    text_content = strip_html(html)
    print(f"生成された記事の文字数: {len(text_content)}文字")

if __name__ == "__main__":
    main()