#!/bin/bash
# ロールバック用スクリプト

echo "=== AI News Auto システムロールバック ==="
echo "このスクリプトは改良前の状態に戻します"
echo ""

# バックアップの確認
BACKUP_DIR=$(ls -1d ../ai-news-auto-backup-* 2>/dev/null | head -n1)
if [ -z "$BACKUP_DIR" ]; then
    echo "❌ バックアップディレクトリが見つかりません"
    exit 1
fi

echo "🔍 バックアップディレクトリ: $BACKUP_DIR"
read -p "本当にロールバックしますか？ (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ ロールバックをキャンセルしました"
    exit 1
fi

# 現在の状態をバックアップ
CURRENT_BACKUP="ai-news-auto-before-rollback-$(date +%Y%m%d_%H%M%S)"
echo "📦 現在の状態をバックアップ中: ../$CURRENT_BACKUP"
cp -r . "../$CURRENT_BACKUP"

# config.yaml のロールバック
echo "🔄 config.yaml をロールバック中..."
cp "$BACKUP_DIR/config/config.yaml" "config/config.yaml"

# 新しく追加されたファイルを削除
echo "🗑️  追加ファイルを削除中..."
rm -f "src/generate_and_post_once_enhanced.py"
rm -f "rollback_to_original.sh"

echo "✅ ロールバック完了"
echo "📂 ロールバック前の状態は ../$CURRENT_BACKUP に保存されました"
echo ""
echo "⚠️  注意: .env ファイルや依存関係は変更されていません"
echo "   必要に応じて手動で調整してください"