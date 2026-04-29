"""测试 DeepSeek 模型配置，确保模型源保持单一。"""

import pytest

from app.integrations import llm_client
from app.integrations.llm_client import DeepSeekChatConfig, LlmConfigError
from app.services.report_service import ReportService


def _clear_llm_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """清理模型相关环境变量，避免测试之间互相污染。"""
    for name in (
        "DEEPSEEK_API_KEY",
        "DEEPSEEK_MODEL",
        "DEEPSEEK_BASE_URL",
    ):
        monkeypatch.delenv(name, raising=False)


def test_deepseek_config_reads_env_with_safe_public_view(monkeypatch: pytest.MonkeyPatch) -> None:
    """DeepSeek 配置应从独立环境变量读取，公开视图不能泄露密钥。"""
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-real-deepseek-key")

    config = DeepSeekChatConfig.from_overrides()

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


def test_deepseek_overrides_model_and_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """请求级覆盖只能改 DeepSeek 模型和地址，不能切回其他供应商。"""
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-real-deepseek-key")

    config = DeepSeekChatConfig.from_overrides(model="deepseek-reasoner", base_url="https://api.deepseek.com/")

    assert config.model == "deepseek-reasoner"
    assert config.base_url == "https://api.deepseek.com"
    assert config.public_view()["provider"] == "deepseek"


def test_unrelated_model_env_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    """非 DeepSeek 环境变量即使存在，也不能成为模型运行配置。"""
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("OTHER_MODEL_API_KEY", "unused-key")
    monkeypatch.setenv("OTHER_MODEL_NAME", "unused-model")
    monkeypatch.setenv("OTHER_MODEL_BASE_URL", "https://example.invalid")

    config = DeepSeekChatConfig.from_overrides()

    assert config.api_key is None
    assert config.model == "deepseek-chat"
    assert config.base_url == "https://api.deepseek.com"
    assert config.public_view()["provider"] == "deepseek"
    assert config.public_view()["api_key_configured"] is False


def test_deepseek_key_strips_invisible_bom(monkeypatch: pytest.MonkeyPatch) -> None:
    """从部署平台读取密钥时，应清理可能混入的 BOM 字符。"""
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "\ufeffsk-real-deepseek-key")

    config = DeepSeekChatConfig.from_overrides()

    assert config.api_key == "sk-real-deepseek-key"
    assert config.can_attempt() is True


def test_deepseek_placeholder_key_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """DeepSeek 示例 Key 不能被当成真实模型源。"""
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "replace-with-your-deepseek-key")

    config = DeepSeekChatConfig.from_overrides()

    assert config.can_attempt() is False
    with pytest.raises(LlmConfigError, match="DeepSeek"):
        config.ensure_ready()


def test_report_service_runtime_config_is_deepseek_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """报告服务公开运行配置中不应再出现备用供应商字段。"""
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-real-deepseek-key")

    runtime = ReportService().get_runtime_config()

    assert runtime["provider"] == "deepseek"
    assert "fallback" not in runtime
    assert "fallback" not in runtime


def test_legacy_symbols_are_not_exported() -> None:
    """集成层不应再暴露旧的主备模型客户端。"""
    assert not hasattr(llm_client, "FallbackChatClient")
