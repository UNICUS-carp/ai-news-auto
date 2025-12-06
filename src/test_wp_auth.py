# -*- coding: utf-8 -*-
import os, sys
from urllib.parse import urljoin
from dotenv import load_dotenv
import requests
from requests.auth import HTTPBasicAuth

load_dotenv()  # .env を読み込む

BASE = os.getenv("WP_URL", "").strip()
USER = os.getenv("WP_USER", "").strip()
APP  = os.getenv("WP_APP_PASSWORD", "").strip()

if not (BASE and USER and APP):
    print("ERROR: WP_URL / WP_USER / WP_APP_PASSWORD のどれかが .env にありません。")
    sys.exit(1)

# 末尾スラッシュは調整
if not BASE.endswith("/"):
    BASE += "/"

url = urljoin(BASE, "wp-json/wp/v2/users/me")
try:
    r = requests.get(url, auth=HTTPBasicAuth(USER, APP), timeout=20)
    print("STATUS:", r.status_code)
    print("BODY:", r.text[:500])
except Exception as e:
    print("ERROR:", e)
    sys.exit(1)
