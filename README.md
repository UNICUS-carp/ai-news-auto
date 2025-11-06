# AI News Auto

自動ニュース記事生成・投稿システム

## 概要

RSSフィードから技術ニュースを取得し、AIで日本語記事を生成してWordPressに自動投稿するシステムです。

## 主な機能

### 📰 記事生成
- RSSフィードから最新ニュースを自動取得
- Claude AIによる高品質な日本語記事生成
- 専門知識のない読者にも理解しやすい構成

### ✅ 2段階ファクトチェック

#### **Phase 1: ルールベースチェック**
高速な基本検証：
- ✓ 数値の整合性（元記事の数値が保持されているか）
- ✓ 日付の正確性
- ✓ 固有名詞の保持確認
- ✓ 推測表現の検出
- ✓ 最小文字数チェック（500文字以上）
- ✓ タイトルと本文の一貫性

#### **Phase 2: LLMベースチェック**
詳細な文脈理解と品質評価（0-100点）：

| 評価項目 | 内容 |
|---------|------|
| **論理的整合性** | 元記事の主張と生成記事の主張が一致しているか<br>因果関係が正しく保たれているか |
| **文脈の正確性** | 専門用語の説明が正確か<br>技術的な詳細に誤解がないか |
| **トーンの一貫性** | 元記事のトーン（ポジティブ/ネガティブ/中立）が保たれているか<br>重要性の度合いが適切か |
| **情報の完全性** | 重要な情報が省略されていないか<br>追加された情報が適切か |
| **意味の正確性** | 元記事の意味が歪曲されていないか<br>引用や説明が正確か |

**合格基準:**
- 各項目70点以上
- 平均75点以上

**不合格時の動作:**
- 記事を破棄し、次の候補記事で再試行（最大5候補）

### 🔄 複数候補システム
- 上位5件の候補を取得
- ファクトチェック不合格時は自動的に次の候補へ
- 全候補が不合格の場合のみエラー報告

### 🎯 記事構成
- リード段落：300-400字（丁寧な導入）
- 本文：1,500-2,000字
- 専門用語には必ず説明と具体例
- 「できること・できないこと」を文章形式で説明
- 「私たちへの影響」を最後に配置

## セットアップ

### 必要な環境
- Python 3.8+
- Anthropic API Key
- WordPress REST API アクセス

### インストール

```bash
# 依存パッケージのインストール
pip install -r requirements.txt

# 環境変数の設定
cp .env.example .env
# .envファイルを編集してAPIキーを設定
```

### 設定ファイル

**`.env`**
```bash
ANTHROPIC_API_KEY=your_api_key_here
WP_URL=https://your-wordpress-site.com
WP_USER=your_username
WP_APP_PASSWORD=your_app_password
```

**`config/config.yaml`**
```yaml
claude:
  models:
    - claude-sonnet-4-5-20250929  # Primary
    - claude-sonnet-4-20250514     # Fallback 1
    - claude-3-opus-20240229       # Fallback 2
  max_tokens: 3000
  temperature: 0.2

fetch:
  feeds:
    - url: https://example.com/feed
      enabled: true
```

## 使用方法

### 記事の自動生成・投稿

```bash
python3 src/post_dedup_value_add.py
```

**処理フロー:**
```
1. RSSフィードから上位5候補を取得
2. for each 候補:
   ├─ AI記事を生成
   ├─ Phase 1: ルールベースチェック
   │   └─ 不合格 → 次の候補へ
   ├─ Phase 2: LLMベースチェック
   │   └─ 不合格 → 次の候補へ
   └─ 合格 → WordPressに投稿して終了
3. 全候補不合格の場合 → エラー報告
```

### テスト

**Phase 1のみテスト:**
```bash
python3 test_fact_checker.py
```

**Phase 2を含む完全テスト:**
```bash
python3 test_phase2_llm_factcheck.py
```

**複数候補のテスト:**
```bash
python3 test_multi_candidate_factcheck.py
```

## ブランチ構成

- `master`: Phase 1（ルールベースファクトチェック）のみ
- `feature/phase2-llm-factcheck`: Phase 2（LLMベースファクトチェック）を含む完全版

### ブランチの切り替え

**Phase 1のみ使用:**
```bash
git checkout master
```

**Phase 2も使用（推奨）:**
```bash
git checkout feature/phase2-llm-factcheck
```

## ファイル構成

```
ai-news-auto/
├── src/
│   ├── fact_checker.py           # ファクトチェッカー（Phase 1 & 2）
│   ├── model_helper.py           # Claude API ヘルパー
│   ├── post_dedup_value_add.py   # メイン処理
│   └── ...
├── config/
│   └── config.yaml               # 設定ファイル
├── state/                        # 状態管理（自動生成）
│   ├── posted_urls.json
│   ├── domain_last.json
│   └── posted_fingerprints.json
├── test_*.py                     # テストスクリプト
├── .env                          # 環境変数
└── README.md                     # このファイル
```

## トラブルシューティング

### モデルが見つからない（404エラー）
`model_helper.py`が自動的にフォールバックします。config.yamlで利用可能なモデルを確認してください。

### ファクトチェックで常に不合格
- Phase 1: `src/fact_checker.py`の閾値を調整
- Phase 2: 合格基準（70点/75点）を調整

### 記事が生成されない
- RSSフィードのURLを確認
- `state/posted_urls.json`に既に投稿済みでないか確認

## 開発

### テストの追加
`test_*.py`ファイルを参考に新しいテストを作成してください。

### コントリビューション
1. ブランチを作成
2. 変更をコミット
3. プルリクエストを作成

## ライセンス

[ライセンス情報を記載]

## クレジット

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
