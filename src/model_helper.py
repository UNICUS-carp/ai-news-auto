# -*- coding: utf-8 -*-
"""
model_helper.py
Claude APIのモデル選択とフォールバック機能を提供
"""
import yaml
from pathlib import Path
from anthropic import Anthropic, APIError

BASE = Path(__file__).resolve().parent.parent
CFG = yaml.safe_load(open(BASE / "config" / "config.yaml", "r", encoding="utf-8"))


def get_claude_config():
    """config.yamlからClaude設定を取得"""
    return CFG.get("claude", {})


def get_available_models():
    """設定ファイルから利用可能なモデルリストを取得"""
    claude_cfg = get_claude_config()
    models = claude_cfg.get("models", ["claude-sonnet-4-5-20250929"])
    return models if isinstance(models, list) else [models]


def get_max_tokens():
    """設定ファイルからmax_tokensを取得"""
    claude_cfg = get_claude_config()
    return claude_cfg.get("max_tokens", 3000)


def get_temperature():
    """設定ファイルからtemperatureを取得"""
    claude_cfg = get_claude_config()
    return claude_cfg.get("temperature", 0.2)


def create_message_with_fallback(client: Anthropic, system: str, messages: list,
                                  max_tokens: int = None, temperature: float = None, timeout: float = None):
    """
    フォールバック機能付きでClaudeメッセージを作成

    Args:
        client: Anthropicクライアント
        system: システムプロンプト
        messages: メッセージリスト
        max_tokens: 最大トークン数（Noneの場合は設定ファイルから取得）
        temperature: 温度パラメータ（Noneの場合は設定ファイルから取得）
        timeout: タイムアウト秒数（Noneの場合はデフォルト値を使用）

    Returns:
        APIレスポンス

    Raises:
        Exception: すべてのモデルで失敗した場合
    """
    models = get_available_models()

    if max_tokens is None:
        max_tokens = get_max_tokens()

    if temperature is None:
        temperature = get_temperature()

    last_error = None

    for model in models:
        try:
            kwargs = {
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "system": system,
                "messages": messages
            }
            if timeout is not None:
                kwargs["timeout"] = timeout

            return client.messages.create(**kwargs)
        except APIError as e:
            # 404エラー（モデルが存在しない）の場合は次のモデルを試行
            if "404" in str(e) or "not_found" in str(e).lower():
                print(f"モデル {model} が利用できません。次のモデルを試行します...")
                last_error = e
                continue
            # その他のエラーは再送出
            raise
        except Exception as e:
            last_error = e
            print(f"モデル {model} でエラーが発生: {str(e)[:100]}")
            continue

    # すべてのモデルで失敗した場合
    raise Exception(f"すべてのモデルで失敗しました。最後のエラー: {last_error}")


def get_primary_model():
    """プライマリモデル名を取得"""
    models = get_available_models()
    return models[0] if models else "claude-sonnet-4-5-20250929"
