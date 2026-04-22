"""验证仓库密钥扫描脚本能拦截真实 key，并放过占位符。"""
from __future__ import annotations

from pathlib import Path

from scripts.check_secrets import find_secret_candidates


def test_secret_scan_flags_high_entropy_api_key(tmp_path: Path) -> None:
    """高熵 API Key 格式应被识别为风险。"""
    target = tmp_path / "sample.txt"
    target.write_text("DEEPSEEK_API_KEY=" + "sk-" + "abcdefghijklmnopqrstuvwxyz123456\n", encoding="utf-8")

    findings = find_secret_candidates([target])

    assert len(findings) == 1
    assert findings[0].path == target


def test_secret_scan_allows_placeholder_values(tmp_path: Path) -> None:
    """示例占位符不应阻断提交。"""
    target = tmp_path / ".env.example"
    target.write_text("DEEPSEEK_API_KEY=replace-with-your-deepseek-key\n", encoding="utf-8")

    assert find_secret_candidates([target]) == []


def test_secret_scan_ignores_code_references(tmp_path: Path) -> None:
    """普通代码里的配置引用不应被当成真实密钥。"""
    target = tmp_path / "settings.py"
    target.write_text("api_key = self.settings.alpha_vantage_api_key\n", encoding="utf-8")

    assert find_secret_candidates([target]) == []
