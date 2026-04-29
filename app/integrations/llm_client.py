"""DeepSeek 模型客户端，供报告生成流程统一调用。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import requests


DEFAULT_DEEPSEEK_MODEL = "deepseek-chat"
DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
PLACEHOLDER_API_KEY_VALUES = {
    "replace-with-your-deepseek-key",
    "your-deepseek-key",
    "your-api-key-here",
}


def _get_first_env(*names: str) -> str | None:
    """按顺序读取环境变量，并清理部署平台可能带入的隐藏字符。"""
    for name in names:
        value = os.getenv(name)
        if value:
            return value.strip().lstrip("\ufeff")
    return None


def _is_placeholder_api_key(value: str | None) -> bool:
    """判断当前 Key 是否仍是示例占位值，避免把假 Key 发到模型服务。"""
    if value is None:
        return False
    normalized = value.strip().strip('"').strip("'")
    if not normalized:
        return False
    lowered = normalized.lower()
    if lowered in PLACEHOLDER_API_KEY_VALUES:
        return True
    return "your-deepseek-key" in lowered or "replace-with-your-deepseek-key" in lowered


class LlmConfigError(ValueError):
    """模型配置缺失或不可用时抛出的明确错误。"""


@dataclass(slots=True)
class DeepSeekChatConfig:
    """DeepSeek OpenAI 兼容接口配置。"""

    api_key: str | None
    model: str = DEFAULT_DEEPSEEK_MODEL
    base_url: str = DEFAULT_DEEPSEEK_BASE_URL
    timeout_seconds: float = 25.0

    @classmethod
    def from_overrides(cls, *, model: str | None = None, base_url: str | None = None) -> "DeepSeekChatConfig":
        """从环境变量读取 DeepSeek 配置，并允许请求级模型和地址覆盖。"""
        resolved_api_key = _get_first_env("DEEPSEEK_API_KEY", "DEEPSEEK_KEY")
        resolved_model = model or _get_first_env("DEEPSEEK_MODEL") or DEFAULT_DEEPSEEK_MODEL
        resolved_base_url = base_url or _get_first_env("DEEPSEEK_BASE_URL") or DEFAULT_DEEPSEEK_BASE_URL
        return cls(
            api_key=resolved_api_key,
            model=resolved_model.strip(),
            base_url=resolved_base_url.strip().rstrip("/"),
        )

    @classmethod
    def from_env(cls) -> "DeepSeekChatConfig":
        """兼容旧调用方式，等价于不传覆盖项。"""
        return cls.from_overrides()

    def can_attempt(self) -> bool:
        """判断 DeepSeek 是否配置完整，可用于模型请求。"""
        return bool(self.api_key and self.model and not _is_placeholder_api_key(self.api_key))

    def ensure_ready(self) -> None:
        """校验 DeepSeek 配置，失败时给出用户能理解的提示。"""
        if not self.api_key:
            raise LlmConfigError("未检测到 DeepSeek API Key。请先设置环境变量 DEEPSEEK_API_KEY。")
        if _is_placeholder_api_key(self.api_key):
            raise LlmConfigError("当前检测到的 DeepSeek API Key 仍是占位值，请换成真实密钥后再启动服务。")
        if not self.model:
            raise LlmConfigError("未检测到 DeepSeek 模型配置。请先设置 DEEPSEEK_MODEL，或使用默认 deepseek-chat。")

    def public_view(self) -> dict[str, Any]:
        """返回不含密钥的运行时视图。"""
        return {
            "provider": "deepseek",
            "api_key_configured": self.can_attempt(),
            "model": self.model,
            "base_url": self.base_url,
            "route_mode": "openai_compatible",
        }


class DeepSeekChatClient:
    """DeepSeek Chat Completions 客户端，使用 OpenAI 兼容 HTTP 接口。"""

    def __init__(self, config: DeepSeekChatConfig):
        self.config = config

    def chat(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        """调用 DeepSeek 生成报告正文。"""
        self.config.ensure_ready()
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        try:
            response = requests.post(
                f"{self.config.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.config.timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            raise RuntimeError(f"DeepSeek 模型请求失败: {exc}") from exc

        try:
            content = data["choices"][0]["message"]["content"]
        except Exception as exc:
            raise RuntimeError(f"DeepSeek 模型返回格式异常: {data}") from exc

        return {
            "content": str(content or "").strip(),
            "raw_response": data,
            "provider": "deepseek",
        }
