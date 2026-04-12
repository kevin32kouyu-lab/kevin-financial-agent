"""
测试意图解析的关键链路。
"""

import pytest

from app.agent_runtime.intent import parse_intent


def test_basic_low_risk_intent():
    query = "我有10万美元，想长期持有低风险蓝筹股"
    intent = parse_intent(query)
    assert intent.investment_strategy.horizon == "Long-term"
    assert intent.investment_strategy.style == "Quality"
    assert intent.portfolio_sizing.capital_amount == 100000
    assert intent.agent_control.is_intent_usable


def test_high_growth_intent():
    query = "帮我找几只高增长的科技股，我可以接受中高风险"
    intent = parse_intent(query)
    assert intent.risk_profile.tolerance_level in ["Medium", "High"]
    assert len(intent.investment_strategy.preferred_sectors) > 0 or intent.investment_strategy.style is None


def test_insufficient_info():
    query = "推荐一些股票"
    intent = parse_intent(query)
    assert not intent.agent_control.is_intent_clear


def test_chinese_terms_parsing():
    query = "我想做红利股投资，每年拿分红，风险偏低"
    intent = parse_intent(query)
    assert intent.investment_strategy.style == "Dividend"
    assert intent.agent_control.is_intent_usable


def test_portfolio_sizing_parsing():
    query = "我有5万美元，想做分散投资"
    intent = parse_intent(query)
    assert intent.portfolio_sizing.capital_amount == 50000
    assert intent.agent_control.missing_critical_info


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
