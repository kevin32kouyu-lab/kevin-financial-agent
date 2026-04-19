from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from volcenginesdkarkruntime import Ark


DEFAULT_MODEL = "ark-code-latest"
DEFAULT_BASE_URL = "https://ark.cn-beijing.volces.com/api/coding/v3"
PLACEHOLDER_API_KEY_VALUES = {
    "your-ark-api-key-here",
    "replace-with-your-ark-key",
    "your-api-key-here",
}


def _get_first_env(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value.strip()
    return None


def _is_placeholder_api_key(value: str | None) -> bool:
    """判断当前 Key 是否仍是示例占位值，避免把假 Key 发到火山。"""
    if value is None:
        return False
    normalized = value.strip().strip('"').strip("'")
    if not normalized:
        return False
    lowered = normalized.lower()
    if lowered in PLACEHOLDER_API_KEY_VALUES:
        return True
    return "your-ark-api-key" in lowered or "replace-with-your-ark-key" in lowered


class LlmConfigError(ValueError):
    pass


@dataclass(slots=True)
class VolcengineChatConfig:
    api_key: str | None
    model: str
    base_url: str
    timeout_seconds: float = 25.0

    @classmethod
    def from_overrides(cls, *, model: str | None = None, base_url: str | None = None) -> "VolcengineChatConfig":
        resolved_api_key = _get_first_env(
            "VOLCENGINE_ARK_API_KEY",
            "VOLCENGINE_API_KEY",
            "ARK_API_KEY",
        )
        resolved_model = (
            model
            or _get_first_env(
                "VOLCENGINE_ARK_MODEL",
                "VOLCENGINE_MODEL",
                "ARK_MODEL",
            )
            or DEFAULT_MODEL
        )
        resolved_base_url = (
            base_url
            or _get_first_env(
                "VOLCENGINE_ARK_BASE_URL",
                "VOLCENGINE_BASE_URL",
                "ARK_BASE_URL",
            )
            or DEFAULT_BASE_URL
        )
        return cls(
            api_key=resolved_api_key,
            model=resolved_model.strip(),
            base_url=resolved_base_url.strip(),
        )

    def ensure_ready(self) -> None:
        if not self.api_key:
            raise LlmConfigError(
                "未检测到火山 API Key。请先设置环境变量 VOLCENGINE_ARK_API_KEY、VOLCENGINE_API_KEY 或 ARK_API_KEY。"
            )
        if _is_placeholder_api_key(self.api_key):
            raise LlmConfigError(
                "当前检测到的火山 API Key 仍是占位值，请把 .env 里的 VOLCENGINE_ARK_API_KEY 或 ARK_API_KEY 换成真实密钥后再启动服务。"
            )
        if not self.model:
            raise LlmConfigError(
                "未检测到模型配置。请先设置 VOLCENGINE_ARK_MODEL、VOLCENGINE_MODEL 或 ARK_MODEL。"
            )

    def public_view(self) -> dict[str, Any]:
        route_mode = "coding_plan" if "/api/coding" in self.base_url else "online_inference"
        billing_mode = "subscription_plan" if route_mode == "coding_plan" else "token_postpaid"
        return {
            "provider": "volcengine-ark",
            "api_key_configured": bool(self.api_key) and not _is_placeholder_api_key(self.api_key),
            "model": self.model,
            "base_url": self.base_url,
            "route_mode": route_mode,
            "billing_mode": billing_mode,
            "official_sdk": "volcengine-python-sdk[ark]",
        }


class VolcengineChatClient:
    def __init__(self, config: VolcengineChatConfig):
        self.config = config
        self._client: Ark | None = None

    @property
    def client(self) -> Ark:
        if self._client is None:
            self.config.ensure_ready()
            self._client = Ark(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                timeout=self.config.timeout_seconds,
            )
        return self._client

    def chat(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        self.config.ensure_ready()

        request_kwargs: dict[str, Any] = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "timeout": self.config.timeout_seconds,
        }
        if max_tokens is not None:
            request_kwargs["max_tokens"] = max_tokens

        try:
            response = self.client.chat.completions.create(**request_kwargs)
        except Exception as exc:
            raise RuntimeError(f"火山模型请求失败: {exc}") from exc

        try:
            content = response.choices[0].message.content
        except Exception as exc:
            raise RuntimeError(f"火山模型返回格式异常: {response}") from exc

        return {
            "content": str(content or "").strip(),
            "raw_response": response.model_dump() if hasattr(response, "model_dump") else str(response),
        }
