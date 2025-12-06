# -*- coding: utf-8 -*-
import os, yaml, json
from urllib.parse import urljoin
from dotenv import dotenv_values
import requests
from requests.auth import HTTPBasicAuth

# .env と config を読む
cfg_env = dotenv_values('.env')
WP_URL  = (cfg_env.get('WP_URL','') or '').strip()
WP_USER = (cfg_env.get('WP_USER','') or '').strip()
WP_PASS = (cfg_env.get('WP_APP_PASSWORD','') or '').strip()
if not (WP_URL and WP_USER and WP_PASS):
    raise SystemExit("WP_URL / WP_USER / WP_APP_PASSWORD が不足しています。")

if not WP_URL.endswith('/'):
    WP_URL += '/'
with open('config/config.yaml', 'r', encoding='utf-8') as f:
    cfg = yaml.safe_load(f) or {}
wp_cfg = cfg.get('wordpress', {})
category_ids = wp_cfg.get('category_ids') or []
status = wp_cfg.get('status', 'draft')

# 最小の下書き本文（安全なテスト用）
title = "（接続テスト）自動投稿の下書き"
content = """<p>この投稿はAPI接続テストです。後で削除して構いません。</p>
<ul>
  <li>作成元：ai-news-auto</li>
  <li>モード：ドラフト</li>
</ul>"""

# POST
url = urljoin(WP_URL, "wp-json/wp/v2/posts")
payload = {
    "title": title,
    "content": content,
    "status": status,           # config.yaml の status に従う（draft 推奨）
    "categories": category_ids  # 配列（空でもOK）
}
r = requests.post(url, auth=HTTPBasicAuth(WP_USER, WP_PASS), json=payload, timeout=30)

print("STATUS:", r.status_code)
try:
    data = r.json()
except Exception:
    print(r.text[:500])
    raise SystemExit()

print(json.dumps({k: data.get(k) for k in ["id","status","link","date","categories","slug"]}, ensure_ascii=False, indent=2))
