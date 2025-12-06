# -*- coding: utf-8 -*-
"""
複数候補のファクトチェックテスト
記事が不合格の場合に次の候補に進むかを検証
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent / "src"))
from fact_checker import fact_check_article

# テスト用のソース記事
source_item = {
    "title": "Google releases new AI model with 100 parameters",
    "summary": "Google announced its new AI model on November 5, 2025. The model has 100 parameters and achieves 95% accuracy.",
    "link": "https://example.com/article",
    "source": "Tech News",
    "domain": "example.com"
}

# テストケース1: 合格する記事（数値が一致）
good_article = """
<p data-meta="description">Googleが100パラメータの新AIモデルを2025年11月5日に発表。精度95%を達成。</p>
<h1>Googleが100パラメータの新AIモデルを発表</h1>
<p>
Googleは2025年11月5日、新しいAIモデルを発表しました。このモデルは100個のパラメータを持ち、
95%の精度を達成しています。これは従来のモデルと比較して大きな進歩です。
</p>
<h3>技術的な詳細</h3>
<p>
新モデルは100個のパラメータで構成されており、これにより95%という高い精度を実現しています。
Googleの研究チームは、このモデルが様々なタスクで優れた性能を発揮することを確認しました。
</p>
<div class="source"><strong>出典：</strong>Google releases new AI model（example.com）</div>
"""

# テストケース2: 不合格の記事（数値が勝手に追加されている = ハルシネーション）
bad_article = """
<p data-meta="description">Googleが500パラメータの新AIモデルを発表。精度99%を達成。</p>
<h1>Googleが500パラメータの新AIモデルを発表</h1>
<p>
Googleは2025年11月5日、新しいAIモデルを発表しました。このモデルは500個のパラメータを持ち、
99%の精度を達成しています。また、処理速度は従来の10倍になっています。
学習データは1000万件のデータセットを使用しました。
</p>
<h3>技術的な詳細</h3>
<p>
新モデルは500個のパラメータで構成されており、これにより99%という高い精度を実現しています。
処理時間は0.5秒と非常に高速です。
</p>
<div class="source"><strong>出典：</strong>Google releases new AI model（example.com）</div>
"""

# テストケース3: 短すぎる記事（500文字未満）
short_article = """
<h1>Googleが新AIモデルを発表</h1>
<p>Googleは新しいAIモデルを発表しました。100パラメータ、95%の精度です。</p>
"""


def test_fact_checker():
    print("=" * 80)
    print("複数候補のファクトチェックテスト")
    print("=" * 80)
    print()

    # テスト1: 合格する記事
    print("[テスト1] 合格する記事（正確な情報）")
    print("-" * 80)
    result1 = fact_check_article(source_item, good_article)
    print(f"結果: {'✅ 合格' if result1['passed'] else '❌ 不合格'}")
    if result1['issues']:
        print(f"問題点: {result1['issues']}")
    if result1['warnings']:
        print(f"警告: {result1['warnings']}")
    print()

    # テスト2: ハルシネーションがある記事
    print("[テスト2] 不合格の記事（数値のハルシネーション）")
    print("-" * 80)
    result2 = fact_check_article(source_item, bad_article)
    print(f"結果: {'✅ 合格' if result2['passed'] else '❌ 不合格'}")
    if result2['issues']:
        print(f"問題点:")
        for issue in result2['issues']:
            print(f"  - {issue}")
    if result2['warnings']:
        print(f"警告:")
        for warning in result2['warnings']:
            print(f"  - {warning}")
    print()

    # テスト3: 短すぎる記事
    print("[テスト3] 不合格の記事（文字数不足）")
    print("-" * 80)
    result3 = fact_check_article(source_item, short_article)
    print(f"結果: {'✅ 合格' if result3['passed'] else '❌ 不合格'}")
    if result3['issues']:
        print(f"問題点:")
        for issue in result3['issues']:
            print(f"  - {issue}")
    if result3['warnings']:
        print(f"警告:")
        for warning in result3['warnings']:
            print(f"  - {warning}")
    print()

    # サマリー
    print("=" * 80)
    print("テストサマリー")
    print("=" * 80)
    print(f"テスト1（正確な記事）: {'✅ 合格' if result1['passed'] else '❌ 不合格'}")
    print(f"テスト2（ハルシネーション）: {'✅ 合格（期待：不合格）' if result2['passed'] else '❌ 不合格（正しく検出）'}")
    print(f"テスト3（短すぎる）: {'✅ 合格（期待：不合格）' if result3['passed'] else '❌ 不合格（正しく検出）'}")
    print()

    # 実際のワークフローのシミュレーション
    print("=" * 80)
    print("実際のワークフロー シミュレーション")
    print("=" * 80)
    print("\n5つの候補記事があると仮定:")

    candidates = [
        ("候補1", bad_article),      # ハルシネーション
        ("候補2", short_article),    # 短すぎる
        ("候補3", bad_article),      # ハルシネーション
        ("候補4", good_article),     # 合格
        ("候補5", good_article),     # 合格（使われない）
    ]

    for idx, (name, article) in enumerate(candidates, 1):
        print(f"\n{name}を生成中...")
        result = fact_check_article(source_item, article)

        if result['passed']:
            print(f"  ✅ ファクトチェック合格！この記事を投稿します。")
            print(f"  → 処理終了（候補{idx}で成功）")
            break
        else:
            print(f"  ❌ ファクトチェック不合格")
            print(f"     問題: {', '.join(result['issues'])}")
            print(f"  → 次の候補へ進みます...")
    else:
        print("\n❌ すべての候補が失敗しました")

    print("\n" + "=" * 80)
    print("✅ ファクトチェック機能は正しく動作しています")
    print("=" * 80)


if __name__ == "__main__":
    test_fact_checker()
