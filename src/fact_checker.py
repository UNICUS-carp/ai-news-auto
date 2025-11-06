# -*- coding: utf-8 -*-
"""
fact_checker.py
基本的なルールベースのファクトチェック機能
"""
import re
from typing import Dict, List, Set


def extract_numbers(text: str) -> Set[str]:
    """
    テキストから数値を抽出

    Returns:
        数値の文字列セット（"100", "3.5", "20%"など）
    """
    numbers = set()

    # 整数と小数
    numbers.update(re.findall(r'\d+(?:\.\d+)?', text))

    # パーセンテージ
    percentages = re.findall(r'\d+(?:\.\d+)?%', text)
    numbers.update(percentages)

    return numbers


def extract_dates(text: str) -> Set[str]:
    """
    テキストから日付を抽出

    Returns:
        日付の文字列セット
    """
    dates = set()

    # YYYY年MM月DD日形式
    dates.update(re.findall(r'\d{4}年\d{1,2}月\d{1,2}日', text))

    # YYYY/MM/DD, YYYY-MM-DD形式
    dates.update(re.findall(r'\d{4}[/-]\d{1,2}[/-]\d{1,2}', text))

    # MM月DD日形式
    dates.update(re.findall(r'\d{1,2}月\d{1,2}日', text))

    # 英語の日付形式（November 6, 2025など）
    dates.update(re.findall(r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}', text, re.IGNORECASE))

    return dates


def extract_proper_nouns(text: str) -> Set[str]:
    """
    テキストから固有名詞を抽出（簡易版）

    主に英語の大文字で始まる単語、カタカナ語を抽出
    """
    nouns = set()

    # 除外する一般的な英単語
    common_words = {
        'The', 'A', 'An', 'This', 'That', 'These', 'Those',
        'You', 'Your', 'My', 'Our', 'Their', 'His', 'Her',
        'What', 'When', 'Where', 'Why', 'How', 'Who',
        'Can', 'Could', 'Will', 'Would', 'Should', 'May', 'Might',
        'To', 'From', 'With', 'Without', 'For', 'By', 'At', 'In', 'On',
        'But', 'And', 'Or', 'So', 'If', 'As',
        'New', 'Old', 'First', 'Last', 'Next', 'All', 'Some', 'Many',
        'It', 'Its', 'Is', 'Are', 'Was', 'Were', 'Be', 'Been',
    }

    # 英語の固有名詞（連続する大文字開始の単語）
    english_nouns = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text)
    for noun in english_nouns:
        # 一般的な単語を除外
        if noun not in common_words:
            nouns.add(noun)

    # カタカナ語（2文字以上）
    katakana_nouns = re.findall(r'[ァ-ヶー]{2,}', text)
    nouns.update(katakana_nouns)

    # よく使われる企業名・製品名（パターン）
    tech_names = re.findall(r'\b(?:OpenAI|Google|Microsoft|Amazon|Meta|Apple|GPT-?\d+|Claude|Gemini|ChatGPT)\b', text, re.IGNORECASE)
    nouns.update([n.strip() for n in tech_names])

    return nouns


def check_speculation_phrases(text: str) -> List[str]:
    """
    推測表現をチェック

    Returns:
        見つかった推測表現のリスト
    """
    speculation_phrases = [
        'かもしれません',
        'かもしれない',
        'と思われます',
        'と思われる',
        'の可能性があります',
        'の可能性がある',
        'と予想されます',
        'と予想される',
        '〜だろう',
        '〜でしょう',
    ]

    found = []
    for phrase in speculation_phrases:
        if phrase in text:
            # 前後の文脈を取得
            matches = re.finditer(re.escape(phrase), text)
            for match in matches:
                start = max(0, match.start() - 30)
                end = min(len(text), match.end() + 30)
                context = text[start:end]
                found.append(f"{phrase}: ...{context}...")

    return found


def check_forbidden_additions(source_summary: str, generated_text: str) -> List[str]:
    """
    元記事にない情報の追加をチェック（ハルシネーション検出）

    元記事に含まれない数値や固有名詞が生成記事に含まれている場合を検出
    """
    import datetime
    issues = []

    source_numbers = extract_numbers(source_summary)
    generated_numbers = extract_numbers(generated_text)

    # 生成記事にあって元記事にない数値
    new_numbers = generated_numbers - source_numbers

    # 除外すべき数値をフィルタリング
    current_year = datetime.datetime.now().year
    suspicious_numbers = []

    for num in new_numbers:
        # 小さな数字（1-12）は除外（月数など）
        try:
            value = float(num.replace('%', ''))

            # 1-12の数値は月の可能性が高いので除外
            if 1 <= value <= 12:
                continue

            # 現在年の±2年以内は文脈情報として許可
            if current_year - 2 <= value <= current_year + 2:
                continue

            # それ以外で10以下の数値は除外
            if value <= 10:
                continue

            # ここまで来た数値は疑わしい
            suspicious_numbers.append(num)
        except:
            # 数値変換できない場合（パーセンテージなど）は含める
            suspicious_numbers.append(num)

    if suspicious_numbers:
        issues.append(f"元記事にない数値が含まれています: {', '.join(suspicious_numbers)}")

    return issues


def fact_check_article(source_item: Dict, generated_html: str) -> Dict:
    """
    生成記事の基本的なファクトチェック

    Args:
        source_item: 元記事の情報 (title, summary, link, etc.)
        generated_html: 生成されたHTML記事

    Returns:
        {
            "passed": bool,  # チェック合格かどうか
            "issues": [問題のリスト],
            "warnings": [警告のリスト]
        }
    """
    issues = []
    warnings = []

    # HTMLタグを除去してテキストのみを取得
    generated_text = re.sub(r'<[^>]+>', ' ', generated_html)
    generated_text = re.sub(r'\s+', ' ', generated_text).strip()

    source_text = f"{source_item.get('title', '')} {source_item.get('summary', '')}"

    # 1. 数値の照合
    source_numbers = extract_numbers(source_text)
    generated_numbers = extract_numbers(generated_text)

    # 元記事の重要な数値が生成記事に含まれているかチェック
    for num in source_numbers:
        if num not in generated_text:
            # 数値の変換をチェック（例：3.5を「3.5」や「約3.5」）
            if not re.search(rf'[約およそ]?\s*{re.escape(num)}', generated_text):
                warnings.append(f"元記事の数値 '{num}' が見つかりません")

    # 元記事にない数値の追加をチェック
    added_nums = check_forbidden_additions(source_text, generated_text)
    if added_nums:
        issues.extend(added_nums)

    # 2. 日付の照合
    source_dates = extract_dates(source_text)
    generated_dates = extract_dates(generated_text)

    # 元記事の日付が正確に含まれているかチェック
    for date in source_dates:
        if date not in generated_text:
            issues.append(f"元記事の日付 '{date}' が正確に記載されていません")

    # 3. 固有名詞の照合
    source_nouns = extract_proper_nouns(source_text)
    generated_nouns = extract_proper_nouns(generated_text)

    # 重要な固有名詞がすべて含まれているか
    important_nouns = [n for n in source_nouns if len(n) > 2]  # 3文字以上
    for noun in important_nouns:
        if noun not in generated_text:
            # 大文字小文字を無視して再チェック
            if noun.lower() not in generated_text.lower():
                warnings.append(f"固有名詞 '{noun}' が見つかりません")

    # 4. 推測表現のチェック
    speculations = check_speculation_phrases(generated_text)
    if speculations:
        # 元記事にも推測表現があるかチェック
        source_speculations = check_speculation_phrases(source_text)
        if len(speculations) > len(source_speculations) + 2:  # 2つ以上多い場合
            warnings.append(f"推測表現が多く含まれています（{len(speculations)}箇所）")

    # 5. 記事の最小文字数チェック
    if len(generated_text) < 500:
        issues.append(f"記事が短すぎます（{len(generated_text)}文字）")

    # 6. タイトルと本文の一貫性チェック
    title_match = re.search(r'<h1[^>]*>(.*?)</h1>', generated_html, re.IGNORECASE | re.DOTALL)
    if title_match:
        title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
        # タイトルに含まれる重要な語が本文にも含まれているか
        title_words = [w for w in re.findall(r'[ァ-ヶー]{2,}|[A-Z][a-z]+', title) if len(w) > 2]
        for word in title_words[:3]:  # 最初の3つの重要語をチェック
            if word not in generated_text:
                warnings.append(f"タイトルの '{word}' が本文で説明されていません")

    # 判定
    passed = len(issues) == 0

    return {
        "passed": passed,
        "issues": issues,
        "warnings": warnings,
        "details": {
            "source_numbers": list(source_numbers),
            "generated_numbers": list(generated_numbers),
            "source_dates": list(source_dates),
            "generated_dates": list(generated_dates),
            "character_count": len(generated_text)
        }
    }


def print_fact_check_result(result: Dict) -> None:
    """
    ファクトチェック結果を見やすく表示
    """
    print("\n" + "="*60)
    print("ファクトチェック結果")
    print("="*60)

    if result["passed"]:
        print("✅ 合格")
    else:
        print("❌ 不合格")

    if result["issues"]:
        print("\n【重大な問題】")
        for i, issue in enumerate(result["issues"], 1):
            print(f"  {i}. {issue}")

    if result["warnings"]:
        print("\n【警告】")
        for i, warning in enumerate(result["warnings"], 1):
            print(f"  {i}. {warning}")

    print("\n【詳細】")
    details = result["details"]
    print(f"  文字数: {details['character_count']}")
    print(f"  元記事の数値: {details['source_numbers']}")
    print(f"  生成記事の数値: {details['generated_numbers']}")
    print(f"  元記事の日付: {details['source_dates']}")
    print(f"  生成記事の日付: {details['generated_dates']}")

    print("="*60 + "\n")
