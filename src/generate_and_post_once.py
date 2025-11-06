# -*- coding: utf-8 -*-
"""
generate_and_post_once.py
- フィードから1本拾って、Claudeで **安全なHTMLのみ** を生成
- 先頭 <p data-meta="description">…</p> からメタディスクリプションを抽出して excerpt に保存
- WordPress に **下書き** 投稿
"""
import os, re, yaml, feedparser, json
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
            return {
                "source": source, "title": title, "link": link,
                "summary": summary, "lang": lang
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

    # === 設定（カテゴリ/ステータス） ===
    wp_cfg = (CFG.get("wordpress") or {})
    category_ids = wp_cfg.get("category_ids") or []
    status = wp_cfg.get("status", "draft")

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
        "あなたは日本語のテック記者です。固有名詞・数値・日付は原文準拠。"
        "過度な一般化・憶測は禁止。出力は **有効なHTMLのみ**。"
        "安全なタグ以外（table, section, script, style, HTMLコメント）は使わないこと。"
    )

    # ————— ここが「安全HTML」指示の本体 —————
    user = f"""
以下の元記事情報にもとづき、**HTMLのみ**でWordPress投稿用の下書きを日本語で生成してください。
Markdownは使用しないでください。改行は <p> で表現します。

# 出力仕様（厳守：HTMLのみ・安全タグのみ）
- 使ってよいタグ：h1, h3, p, ul, li, a, div, strong, em
- 使ってはいけないタグ：table, section, script, style、HTMLコメント（<!-- -->）
- 先頭に <p data-meta="description">…120字以内…</p> を1つ出力（メタディスクリプション）
- 構成：
  <h1>title</h1>
  <p>lead</p>（2–3文）
  <ul><li>要点×5</li></ul>
  <h3>小見出し</h3><p>本文…（700–1000字）</p>
  <h3>影響と活用</h3>
  <ul><li>即効の業務インパクト（3–5点。可能なら定量/準定量％）</li></ul>
  <h3>できるようになること／まだ難しいこと</h3>
  <ul><li>できる：…</li><li>難しい：…</li></ul>
  <h3>部門別ユースケース</h3>
  <ul><li>…</li></ul>
  <h3>成果測定KPI</h3>
  <ul><li>…</li></ul>
  <div class="source"><strong>出典:</strong> <a href="{item["link"]}" target="_blank" rel="nofollow">{item["title"]}</a>（{item["source"]}）</div>

# 元情報
- source: {item["source"]}
- title: {item["title"]}
- link: {item["link"]}
- summary: {item["summary"]}
- language_hint: {item["lang"]}
""".strip()
    # ————— ここまで —————

    msg = client.messages.create(
        model="claude-3-opus-20240229",
        max_tokens=2000,
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
    html = re.sub(r"<!--.*?-->", "", html, flags=re.S)            # HTMLコメント削除
    html = re.sub(r"</?section\b[^>]*>", "", html, flags=re.I)    # section除去（念のため）
    html = re.sub(r"</?table\b[^>]*>.*?</table>", "", html, flags=re.I | re.S)  # table除去

    # === タイトル抽出（<h1>…</h1>） ===
    mtitle = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)
    title_for_wp = strip_html(mtitle.group(1)) if mtitle else "(自動生成)AIニュース"
    title_for_wp = re.sub(r"\s+", " ", title_for_wp)[:62]

    # === WordPressへ下書き投稿 ===
    url = urljoin(WP_URL, "wp-json/wp/v2/posts")
    payload = {
        "title": title_for_wp,
        "content": html,
        "status": status,            # config.yaml の status に従う（draft 推奨）
        "categories": category_ids,  # 複数カテゴリ対応
        "excerpt": meta_desc or "",  # メタディスクリプション
    }
    r = requests.post(url, auth=HTTPBasicAuth(WP_USER, WP_PASS), json=payload, timeout=40)
    print("POST STATUS:", r.status_code)
    try:
        data = r.json()
    except Exception:
        print(r.text[:500]); return

    print(json.dumps({k: data.get(k) for k in ["id","status","link","date","categories","slug"]},
                     ensure_ascii=False, indent=2))

    # ローカル保存（任意）
    outdir = BASE / "out"; outdir.mkdir(exist_ok=True)
    (outdir / "generated_and_posted.html").write_text(html, encoding="utf-8")
    print("ローカル保存:", outdir / "generated_and_posted.html")

if __name__ == "__main__":
    main()
