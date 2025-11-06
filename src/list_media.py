# -*- coding: utf-8 -*-
"""
list_media.py
WordPressメディアライブラリの画像一覧とIDを取得
"""
import json
import requests
from requests.auth import HTTPBasicAuth
from dotenv import dotenv_values
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
ENV = dotenv_values(BASE / ".env")

def list_media():
    # WordPress接続情報
    WP_URL = (ENV.get("WP_URL", "") or "").rstrip("/") + "/"
    WP_USER = (ENV.get("WP_USER", "") or "")
    WP_PASS = (ENV.get("WP_APP_PASSWORD", "") or "")
    
    if not (WP_URL and WP_USER and WP_PASS):
        raise SystemExit("WP_URL / WP_USER / WP_APP_PASSWORD が不足しています。")
    
    # メディア一覧を取得（画像のみ）
    url = f"{WP_URL}wp-json/wp/v2/media"
    params = {
        "media_type": "image",  # 画像のみ
        "per_page": 50,         # 50件まで表示
        "orderby": "date",      # 日付順
        "order": "desc"         # 新しい順
    }
    
    try:
        response = requests.get(url, auth=HTTPBasicAuth(WP_USER, WP_PASS), params=params, timeout=30)
        response.raise_for_status()
        
        media_list = response.json()
        
        print(f"=== WordPressメディアライブラリ（画像一覧）===")
        print(f"取得件数: {len(media_list)}")
        print()
        
        for media in media_list:
            print(f"ID: {media['id']}")
            print(f"ファイル名: {media['title']['rendered']}")
            print(f"URL: {media['source_url']}")
            print(f"アップロード日: {media['date']}")
            print(f"MIME: {media['mime_type']}")
            if 'sizes' in media['media_details']:
                sizes = list(media['media_details']['sizes'].keys())
                print(f"サイズ: {', '.join(sizes)}")
            print("-" * 50)
            
    except requests.exceptions.RequestException as e:
        print(f"エラー: {e}")
        return
    except Exception as e:
        print(f"予期しないエラー: {e}")
        return

if __name__ == "__main__":
    list_media()