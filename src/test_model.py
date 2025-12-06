#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""利用可能なClaudeモデルを確認"""

from dotenv import dotenv_values
from pathlib import Path
from anthropic import Anthropic

BASE = Path(__file__).resolve().parent.parent
ENV = dotenv_values(BASE / ".env")

api_key = ENV.get("ANTHROPIC_API_KEY")
if not api_key:
    print("API key not found")
    exit(1)

client = Anthropic(api_key=api_key)

# テストするモデル名のリスト
models_to_test = [
    "claude-sonnet-4-5-20250929",  # Latest Claude Sonnet 4.5
    "claude-sonnet-4-20250514",     # Claude Sonnet 4
    "claude-3-5-sonnet-20241022",
    "claude-3-5-sonnet-20240620",
    "claude-3-sonnet-20240229",
    "claude-3-opus-20240229",
    "claude-3-haiku-20240307",
]

for model_name in models_to_test:
    try:
        msg = client.messages.create(
            model=model_name,
            max_tokens=10,
            temperature=0.2,
            system="You are a test assistant.",
            messages=[{"role": "user", "content": "Say 'OK' if you work."}],
        )
        print(f"✅ {model_name}: Working")
        break  # 最初に動作したモデルで終了
    except Exception as e:
        print(f"❌ {model_name}: {str(e)[:50]}...")