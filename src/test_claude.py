# -*- coding: utf-8 -*-
import os, sys
from anthropic import Anthropic, APIStatusError
from model_helper import create_message_with_fallback

# ← 追加：.env を自動読み込み
try:
    from dotenv import load_dotenv
    load_dotenv()  # カレント（~/Desktop/ai-news-auto/.env）を自動検出
except Exception:
    pass

api_key = os.getenv("ANTHROPIC_API_KEY")
if not api_key:
    print("ERROR: ANTHROPIC_API_KEY が .env に設定されていません。")
    sys.exit(1)

try:
    client = Anthropic(api_key=api_key)
    msg = create_message_with_fallback(
        client,
        system="",
        messages=[{"role": "user", "content": "日本語でOKなら『OK』だけ出力して。"}],
        max_tokens=20
    )
    parts = msg.content
    text = "".join([p.text for p in parts if p.type == "text"]).strip()
    print(text or "（空の応答）")
except APIStatusError as e:
    print(f"API ERROR: {e.status_code} {e.message}")
    sys.exit(1)
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)
