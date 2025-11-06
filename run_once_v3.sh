#!/bin/bash
set -euo pipefail
PROJECT_DIR="/Users/macmini-carp/ai-news-auto"
VENV_DIR="$PROJECT_DIR/.venv"
PY="$VENV_DIR/bin/python"
LOCKDIR="/tmp/ai-news-auto.lock"
mkdir -p "$PROJECT_DIR/logs"

if ! mkdir "$LOCKDIR" 2>/dev/null; then
  exit 0
fi
trap 'rmdir "$LOCKDIR" 2>/dev/null || true' EXIT

LOG_FILE="$PROJECT_DIR/logs/run_$(date +%Y%m%d_%H%M%S).log"
{
  echo "=== start: $(date) ==="
  cd "$PROJECT_DIR"
  if [ ! -x "$PY" ]; then
    /usr/bin/python3 -m venv "$VENV_DIR"
    "$PY" -m pip install -U pip
    "$PY" -m pip install feedparser pyyaml python-dotenv langdetect anthropic requests
  fi
  "$PY" - <<'PY'
import feedparser, yaml, dotenv, langdetect, anthropic, requests
print("[check] deps: OK")
PY
  echo "[run] post_dedup_value_add.py"
  "$PY" src/post_dedup_value_add.py
  echo "=== end: $(date) ==="
} >> "$LOG_FILE" 2>&1
