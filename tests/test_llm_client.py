"""测试火山模型配置校验，避免占位 Key 被当成真实密钥发送。"""

import pytest

from app.integrations.llm_client import LlmConfigError, VolcengineChatConfig


def _clear_ark_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """清理火山相关环境变量，避免测试之间互相污染。"""
    for name in (
        "VOLCENGINE_ARK_API_KEY",
        "VOLCENGINE_API_KEY",
        "ARK_API_KEY",
        "VOLCENGINE_ARK_MODEL",
        "VOLCENGINE_MODEL",
        "ARK_MODEL",
        "VOLCENGINE_ARK_BASE_URL",
        "VOLCENGINE_BASE_URL",
        "ARK_BASE_URL",
    ):
        monkeypatch.delenv(name, raising=False)


def test_placeholder_api_key_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """占位 Key 应该在本地被拦下，而不是继续请求火山。"""
    _clear_ark_env(monkeypatch)
    monkeypatch.setenv("VOLCENGINE_ARK_API_KEY", "your-ark-api-key-here")

    config = VolcengineChatConfig.from_overrides()

    with pytest.raises(LlmConfigError, match="占位值"):
        config.ensure_ready()
    assert config.public_view()["api_key_configured"] is False


def test_non_placeholder_api_key_is_treated_as_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    """看起来像真实值的 Key 不应被误判成占位值。"""
    _clear_ark_env(monkeypatch)
    monkeypatch.setenv("VOLCENGINE_ARK_API_KEY", "ark-demo-real-key")

    config = VolcengineChatConfig.from_overrides()

    config.ensure_ready()
    assert config.public_view()["api_key_configured"] is True
