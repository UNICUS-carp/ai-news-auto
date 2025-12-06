#!/bin/bash
set -euo pipefail

# 絶対パスに変更しないでください（あなたの環境専用のパス）
PROJECT_DIR="$HOME/ai-news-auto"

# ログ
mkdir -p "$PROJECT_DIR/logs"
LOG_FILE="$PROJECT_DIR/logs/run_$(date +%Y%m%d_%H%M%S).log"

{
  echo "=== start: $(date) ==="
  cd "$PROJECT_DIR"
  # 仮想環境
  source .venv/bin/activate
  # 実行（記事を1本下書き投稿）
  python src/post_ultrasafe_once.py
  echo "=== end: $(date) ==="
} >> "$LOG_FILE" 2>&1
