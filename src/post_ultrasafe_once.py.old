# -*- coding: utf-8 -*-
"""
post_ultrasafe_once.py (Python 3.8 互換)
- フィードから1本拾って、Claudeで日本語記事を生成
- その後、WAF回避の「超安全サニタイズ」を適用（タグ・属性を極力排除）
- WordPressに draft で投稿
"""
import os, re, yaml, feedparser, json
from pathlib import Path
from typing import Tuple
from langdetect import detect, DetectorFactory
from dotenv import dotenv_values
from anthropic import Anthropic
import requests
from model_helper import create_message_with_fallback
from requests.auth import HTTPBasicAuth
from urllib.parse import urljoin, urlparse

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
            return {"source": source, "title": title, "link": link, "summary": summary, "lang": lang}
    return None

def ultrasafe_sanitize(html: str, source_title: str, source_link: str, source_site: str) -> Tuple[str, str]:
    """
    極力安全にするためのサニタイズ：
      - コメント削除、禁止タグ削除（script/style/section/table等）
      - 許可タグ以外は除去
      - すべての属性を除去（<p class=...> -> <p>）
      - <a> はテキストに変換（リンクは使わない）
      - 文字数を上限で切り詰め
      - メタディスクリプションは data-meta から抽出（あれば）
    """
    # 1) コメント/禁止タグ削除
    html = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    html = re.sub(r"</?(script|style|section|table|iframe|form|noscript)\b[^>]*>.*?</\1>", "", html, flags=re.I|re.S)

    # 2) <a>…</a> をテキストに（中身だけ残す）
    html = re.sub(r"<a\b[^>]*>(.*?)</a>", r"\1", html, flags=re.I|re.S)

    # 3) 許可タグ（h1,h3,p,ul,li,div,strong,em）以外のタグを除去
    allowed = ("h1","h3","p","ul","li","div","strong","em")
    def keep_or_drop(m):
        tag = m.group(1).lower()
        return m.group(0) if tag in allowed else ""
    html = re.sub(r"</?([a-zA-Z0-9]+)\b[^>]*>", lambda m: keep_or_drop(m), html)

    # 4) 残った許可タグから属性を全削除（<tag ...> -> <tag>）
    def strip_attrs(m):
        tag = m.group(1)
        closing = m.group(0).startswith("</")
        return "</{0}>".format(tag) if closing else "<{0}>".format(tag)
    html = re.sub(r"</?([a-zA-Z0-9]+)(\s+[^>]*)?>", strip_attrs, html)

    # 5) メタディスクリプション抽出（data-meta）→ なければ先頭<p>
    meta_desc = ""
    m = re.search(r"<p[^>]*data-meta=['\"]?description['\"]?[^>]*>(.*?)</p>", html, flags=re.I|re.S)
    if m:
        meta_desc = re.sub(r"\s+"," ", strip_html(m.group(1))).strip()
    if not meta_desc:
        m2 = re.search(r"<p>(.*?)</p>", html, flags=re.S)
        if m2:
            meta_desc = re.sub(r"\s+"," ", strip_html(m2.group(1))).strip()
    if len(meta_desc) > 120:
        meta_desc = meta_desc[:119] + "…"

    # 6) 出典はプレーンテキストで最下部に追加
    domain = urlparse(source_link).netloc or source_site
    source_text = "\n<p>出典: {0}（{1}）</p>".format(source_title, domain)
    html = (html.strip() + source_text)

    # 7) 総量制限
    if len(html) > 8000:
        html = html[:8000] + "…"

    return html, meta_desc

def main():
    # WP接続
    WP_URL  = (ENV.get("WP_URL","") or "").strip()
    WP_USER = (ENV.get("WP_USER","") or "").strip()
    WP_PASS = (ENV.get("WP_APP_PASSWORD","") or "").strip()
    if not (WP_URL and WP_USER and WP_PASS):
        raise SystemExit("WP_URL / WP_USER / WP_APP_PASSWORD が不足しています。")
    if not WP_URL.endswith("/"):
        WP_URL += "/"

    wp_cfg = (CFG.get("wordpress") or {})
    category_ids = wp_cfg.get("category_ids") or []
    status = wp_cfg.get("status", "draft")

    item = pick_first_item()
    if not item:
        print("記事候補が取得できませんでした。"); return

    client = Anthropic(api_key=ENV.get("ANTHROPIC_API_KEY"))
    system = ("あなたは日本語のテック記者。出力はHTMLのみ。"
              "安全なタグ（h1,h3,p,ul,li,div,strong,em）のみ使用。"
              "リンクや表、section、コメントは使わない。")

    user = ("""
以下の元記事情報にもとづき、HTMLのみで日本語の下書きを作成してください（Markdown禁止）。
- 先頭に <p data-meta="description">…120字以内…</p>
- <h1>title</h1>
- <p>lead</p>
- <ul><li>要点×5</li></ul>
- <h3>小見出し</h3><p>本文（700–900字）</p>
- 最後に「出典: {title}（{source}）」という一文を<p>で入れてください（リンク禁止）

元情報:
- source: {source}
- title: {title}
- link: {link}
- summary: {summary}
- language_hint: {lang}
""").format(
        source=item["source"], title=item["title"], link=item["link"],
        summary=item["summary"], lang=item["lang"]
    ).strip()

    msg = create_message_with_fallback(
        client, system=system, messages=[{"role":"user","content":user}]
    )
    html = "".join([p.text for p in msg.content if p.type=="text"]).strip()
    if not html:
        print("生成結果が空でした。"); return

    # 超安全サニタイズ
    safe_html, meta_desc = ultrasafe_sanitize(
        html, item["title"], item["link"], item["source"]
    )

    # タイトル抽出
    mtitle = re.search(r"<h1>(.*?)</h1>", safe_html, flags=re.S|re.I)
    title_for_wp = strip_html(mtitle.group(1)) if mtitle else "(自動生成)AIニュース"
    title_for_wp = re.sub(r"\s+"," ", title_for_wp)[:62]

    # 投稿
    url = urljoin(WP_URL, "wp-json/wp/v2/posts")
    payload = {
        "title": title_for_wp,
        "content": safe_html,
        "status": status,
        "categories": category_ids,
        "excerpt": meta_desc or ""
    }
    r = requests.post(url, auth=HTTPBasicAuth(WP_USER, WP_PASS), json=payload, timeout=40)
    print("POST STATUS:", r.status_code)
    try:
        data = r.json()
        print(json.dumps({k: data.get(k) for k in ["id","status","link","date","categories"]},
                         ensure_ascii=False, indent=2))
    except Exception:
        print(r.text[:500])

if __name__ == "__main__":
    main()
