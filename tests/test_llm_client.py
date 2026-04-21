"""测试火山模型配置校验，避免占位 Key 被当成真实密钥发送。"""

import pytest

from app.integrations.llm_client import DeepSeekChatConfig, FallbackChatClient, LlmConfigError, VolcengineChatConfig


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
        "DEEPSEEK_API_KEY",
        "DEEPSEEK_MODEL",
        "DEEPSEEK_BASE_URL",
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


def test_deepseek_config_reads_env_with_safe_public_view(monkeypatch: pytest.MonkeyPatch) -> None:
    """DeepSeek 备用源应从独立环境变量读取，公开视图不能泄露密钥。"""
    _clear_ark_env(monkeypatch)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-real-deepseek-key")

    config = DeepSeekChatConfig.from_env()

    assert config.api_key == "sk-real-deepseek-key"
    assert config.model == "deepseek-chat"
    assert config.base_url == "https://api.deepseek.com"
    assert config.can_attempt() is True
    assert config.public_view() == {
        "provider": "deepseek",
        "api_key_configured": True,
        "model": "deepseek-chat",
        "base_url": "https://api.deepseek.com",
        "route_mode": "openai_compatible",
    }


def test_deepseek_key_strips_invisible_bom(monkeypatch: pytest.MonkeyPatch) -> None:
    """从部署平台读取密钥时，应清理可能混入的 BOM 字符。"""
    _clear_ark_env(monkeypatch)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "\ufeffsk-real-deepseek-key")

    config = DeepSeekChatConfig.from_env()

    assert config.api_key == "sk-real-deepseek-key"
    assert config.can_attempt() is True


def test_deepseek_placeholder_key_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """DeepSeek 示例 Key 不能被当成真实备用源。"""
    _clear_ark_env(monkeypatch)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "replace-with-your-deepseek-key")

    config = DeepSeekChatConfig.from_env()

    assert config.can_attempt() is False
    with pytest.raises(LlmConfigError, match="DeepSeek"):
        config.ensure_ready()


def test_fallback_chat_client_uses_deepseek_when_primary_fails() -> None:
    """主模型失败时应自动调用备用模型，并保留主模型错误。"""

    class FailingPrimary:
        def chat(self, **_: object) -> dict[str, object]:
            raise RuntimeError("primary exploded")

    class WorkingFallback:
        def chat(self, **_: object) -> dict[str, object]:
            return {"content": "fallback memo", "raw_response": {"ok": True}, "provider": "deepseek"}

    client = FallbackChatClient(primary=FailingPrimary(), fallback=WorkingFallback())
    result = client.chat(system_prompt="sys", user_prompt="user")

    assert result["content"] == "fallback memo"
    assert result["provider"] == "deepseek"
    assert result["fallback_from"] == "volcengine-ark"
    assert "primary exploded" in result["primary_error"]


def test_fallback_chat_client_reraises_without_fallback() -> None:
    """没有可用备用源时，应保留原始失败，交给结构化报告兜底。"""

    class FailingPrimary:
        def chat(self, **_: object) -> dict[str, object]:
            raise RuntimeError("primary exploded")

    client = FallbackChatClient(primary=FailingPrimary(), fallback=None)

    with pytest.raises(RuntimeError, match="primary exploded"):
        client.chat(system_prompt="sys", user_prompt="user")
