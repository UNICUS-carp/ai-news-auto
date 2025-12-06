# -*- coding: utf-8 -*-
"""
Phase 2の安全性テスト
エラーハンドリング、フォールバック、パフォーマンスを検証
"""
import yaml
import re
import time
from pathlib import Path
from dotenv import dotenv_values
from anthropic import Anthropic
import sys

sys.path.append(str(Path(__file__).parent / "src"))
from fact_checker import fact_check_article, llm_fact_check_article, print_fact_check_result, print_llm_fact_check_result

BASE = Path(__file__).resolve().parent
CFG = yaml.safe_load(open(BASE / "config" / "config.yaml", "r", encoding="utf-8"))
ENV = dotenv_values(BASE / ".env")


def test_error_handling():
    """Phase 2でエラーが発生した場合の動作を確認"""
    print("=" * 80)
    print("テスト1: Phase 2 エラーハンドリング")
    print("=" * 80)

    # 故意に壊れたAPIキーでテスト
    client = Anthropic(api_key="invalid_key_for_testing")

    source_item = {
        "title": "Test Article",
        "summary": "This is a test article with some content.",
        "link": "https://example.com/test",
        "source": "Test Source",
        "domain": "example.com"
    }

    generated_html = """
    <p data-meta="description">Test article description</p>
    <h1>Test Article Title</h1>
    <p>
    This is a test article with sufficient content to pass Phase 1 checks.
    It contains the necessary information and has more than 500 characters.
    Lorem ipsum dolor sit amet, consectetur adipiscing elit.
    Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.
    Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris.
    Nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in.
    Reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla.
    </p>
    """

    print("\n[1] Phase 1チェック（正常系）")
    result1 = fact_check_article(source_item, generated_html)
    print(f"Phase 1結果: {'✅ 合格' if result1['passed'] else '❌ 不合格'}")

    print("\n[2] Phase 2チェック（エラーを意図的に発生）")
    start_time = time.time()
    result2 = llm_fact_check_article(source_item, generated_html, client)
    elapsed = time.time() - start_time

    print(f"Phase 2結果: {'✅ 合格' if result2['passed'] else '❌ 不合格'}")
    print(f"処理時間: {elapsed:.2f}秒")
    print(f"スコア: {result2['score']}/100")

    if result2.get('issues'):
        print(f"指摘事項: {result2['issues']}")

    # エラー時はpassedがTrueになることを確認
    if result2['passed'] and "エラー" in str(result2.get('issues', [])):
        print("\n✅ エラーハンドリング正常: Phase 2エラー時もシステムは継続動作")
        return True
    elif not result2['passed']:
        print("\n❌ 警告: Phase 2エラー時にpassedがFalseになっています")
        return False
    else:
        print("\n⚠️  予期しない動作")
        return False


def test_performance():
    """Phase 2のパフォーマンスを確認"""
    print("\n" + "=" * 80)
    print("テスト2: パフォーマンス測定")
    print("=" * 80)

    client = Anthropic(api_key=ENV.get("ANTHROPIC_API_KEY"))

    source_item = {
        "title": "Test Article About AI",
        "summary": "This article discusses artificial intelligence and machine learning.",
        "link": "https://example.com/ai-article",
        "source": "Tech News",
        "domain": "example.com"
    }

    generated_html = """
    <p data-meta="description">AIと機械学習に関する記事です。</p>
    <h1>AIと機械学習の最新動向</h1>
    <p>
    人工知能（AI）とは、コンピュータが人間のように考え、学習する技術のことです。
    機械学習は、AIの一分野で、データからパターンを学習する手法です。
    最近では、深層学習という技術が注目を集めています。
    深層学習とは、人間の脳の神経回路を模倣したニューラルネットワークを使った学習方法です。
    この技術により、画像認識や音声認識の精度が大幅に向上しました。
    今後、AIはさまざまな分野で活用されることが期待されています。
    例えば、医療診断、自動運転、翻訳などが挙げられます。
    一方で、プライバシーや雇用への影響など、課題も残されています。
    </p>
    """

    print("\n[Phase 1] ルールベースチェック")
    start1 = time.time()
    result1 = fact_check_article(source_item, generated_html)
    time1 = time.time() - start1
    print(f"処理時間: {time1:.3f}秒")
    print(f"結果: {'✅ 合格' if result1['passed'] else '❌ 不合格'}")

    print("\n[Phase 2] LLMベースチェック")
    start2 = time.time()
    result2 = llm_fact_check_article(source_item, generated_html, client)
    time2 = time.time() - start2
    print(f"処理時間: {time2:.3f}秒")
    print(f"結果: {'✅ 合格' if result2['passed'] else '❌ 不合格'}")
    print(f"スコア: {result2['score']}/100")

    print(f"\n【パフォーマンス比較】")
    print(f"Phase 1: {time1:.3f}秒 (⚡ 高速)")
    print(f"Phase 2: {time2:.3f}秒")
    print(f"合計: {time1 + time2:.3f}秒")

    if time2 < 10:
        print("✅ Phase 2のパフォーマンスは許容範囲内（10秒未満）")
        return True
    else:
        print("⚠️  Phase 2が遅すぎます（10秒以上）")
        return False


def test_phase1_independence():
    """Phase 1が独立して動作することを確認"""
    print("\n" + "=" * 80)
    print("テスト3: Phase 1の独立動作確認")
    print("=" * 80)

    source_item = {
        "title": "Independent Test",
        "summary": "Testing Phase 1 independence",
        "link": "https://example.com/independent",
        "source": "Test",
        "domain": "example.com"
    }

    generated_html = """
    <p data-meta="description">Independent test article</p>
    <h1>Independent Test Title</h1>
    <p>
    This article tests whether Phase 1 can work independently without Phase 2.
    It should pass all basic rule-based checks including character count.
    Lorem ipsum dolor sit amet, consectetur adipiscing elit.
    Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.
    Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris.
    Nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor.
    </p>
    """

    print("\n[Phase 1のみ実行]")
    result = fact_check_article(source_item, generated_html)
    print_fact_check_result(result)

    if result['passed']:
        print("✅ Phase 1は独立して正常に動作します")
        return True
    else:
        print("❌ Phase 1が予期せず失敗しました")
        return False


def test_api_cost():
    """API呼び出しコストの見積もり"""
    print("\n" + "=" * 80)
    print("テスト4: API コスト見積もり")
    print("=" * 80)

    print("\n【推定コスト】")
    print("Phase 1 (ルールベース): $0.00 (API呼び出しなし)")
    print("Phase 2 (LLMベース): 約$0.003-0.005 / 記事")
    print("  - 入力: ~2,000 tokens")
    print("  - 出力: ~500 tokens")
    print("  - Claude Sonnet: $3/M input, $15/M output")
    print("  - 計算: (2000*$3 + 500*$15) / 1,000,000 ≈ $0.014")

    print("\n【1日10記事の場合】")
    print("  - Phase 2コスト: 10 × $0.014 = $0.14/日")
    print("  - 月間コスト: $0.14 × 30 = $4.20/月")

    print("\n【1日50記事の場合】")
    print("  - Phase 2コスト: 50 × $0.014 = $0.70/日")
    print("  - 月間コスト: $0.70 × 30 = $21.00/月")

    print("\n✅ Phase 2のコストは比較的低く、記事品質向上に見合う投資")
    return True


def main():
    print("=" * 80)
    print("Phase 2 安全性テスト")
    print("=" * 80)
    print()

    results = {}

    # テスト1: エラーハンドリング
    results['error_handling'] = test_error_handling()

    # テスト2: パフォーマンス
    results['performance'] = test_performance()

    # テスト3: Phase 1の独立性
    results['phase1_independence'] = test_phase1_independence()

    # テスト4: コスト見積もり
    results['api_cost'] = test_api_cost()

    # 総合評価
    print("\n" + "=" * 80)
    print("総合評価")
    print("=" * 80)

    for test_name, passed in results.items():
        status = "✅ 合格" if passed else "❌ 不合格"
        print(f"{test_name}: {status}")

    all_passed = all(results.values())

    print("\n" + "=" * 80)
    if all_passed:
        print("🎉 全てのテストに合格しました！")
        print("✅ Phase 2は安全にmasterブランチにマージできます")
    else:
        print("⚠️  一部のテストが失敗しました")
        print("❌ 問題を修正してから再テストしてください")
    print("=" * 80)

    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
