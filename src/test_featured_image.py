# -*- coding: utf-8 -*-
"""
test_featured_image.py
アイキャッチ画像のランダム選択機能をテスト
"""
import sys
import yaml
from pathlib import Path

# パスを追加してモジュールをインポート
sys.path.insert(0, str(Path(__file__).parent))
from post_dedup_value_add import select_featured_image, load_json, IMG_HISTORY_PATH

def test_featured_image_selection():
    print("=== アイキャッチ画像選択テスト ===")
    
    # 5回連続で選択して、連続3回同じ画像が選ばれないことを確認
    for i in range(5):
        selected = select_featured_image()
        print(f"選択 {i+1}: 画像ID {selected}")
        
        # 履歴確認
        history = load_json(IMG_HISTORY_PATH)
        recent = history.get("recent_images", [])
        print(f"  履歴: {recent}")
        
        # 連続3回チェック
        if len(recent) >= 3 and recent[-1] == recent[-2] == recent[-3]:
            print("  ⚠️ 警告: 連続3回同じ画像が選ばれました！")
        else:
            print("  ✅ OK: 連続回避ロジック正常")
        print()

if __name__ == "__main__":
    test_featured_image_selection()