from __future__ import annotations

import re

from app.analysis_runtime import ExplicitTargets, FundamentalFilters, InvestmentStrategy, RiskProfile

from .models import AgentControl, ParsedIntent, PortfolioSizing, SystemContext


SECTOR_KEYWORDS: dict[str, list[str]] = {
    "Technology": ["technology", "tech", "科技", "信息技术"],
    "Healthcare": ["healthcare", "medical", "biotech", "医药", "医疗"],
    "Financial Services": ["financial", "finance", "bank", "insurance", "金融", "银行", "保险"],
    "Energy": ["energy", "oil", "gas", "能源", "石油", "天然气"],
    "Industrials": ["industrial", "manufacturing", "工业", "制造"],
    "Consumer Defensive": ["consumer defensive", "consumer staples", "staples", "必选消费", "消费防御"],
    "Communication Services": ["communication", "media", "telecom", "通信", "传媒"],
    "Utilities": ["utility", "utilities", "公用事业"],
    "Real Estate": ["real estate", "reit", "地产", "房地产"],
    "Materials": ["materials", "material", "材料", "原材料"],
}

INDUSTRY_KEYWORDS: dict[str, list[str]] = {
    "Semiconductors": ["semiconductor", "chip", "芯片", "半导体"],
    "Software": ["software", "saas", "软件"],
    "Banks": ["bank", "banks", "银行"],
    "Insurance": ["insurance", "保险"],
    "Oil & Gas": ["oil", "gas", "石油", "天然气"],
    "Drug Manufacturers - General": ["pharma", "drug", "制药", "药企"],
    "Information Technology Services": ["it service", "cloud", "信息技术服务", "云服务"],
}

COMPANY_TICKER_MAP: dict[str, str] = {
    "apple": "AAPL",
    "microsoft": "MSFT",
    "nvidia": "NVDA",
    "tesla": "TSLA",
    "amazon": "AMZN",
    "alphabet": "GOOGL",
    "google": "GOOGL",
    "meta": "META",
    "johnson & johnson": "JNJ",
    "coca-cola": "KO",
    "procter & gamble": "PG",
    "allstate": "ALL",
    "comcast": "CMCSA",
}

TICKER_STOPWORDS = {
    "USD",
    "HKD",
    "CNY",
    "PE",
    "PB",
    "PS",
    "ROE",
    "ROA",
    "FCF",
    "EPS",
    "RSI",
    "MACD",
    "VIX",
    "ETF",
    "ADR",
    "AI",
    "I",
}

LOW_RISK_HINTS = [
    "low risk",
    "low-risk",
    "conservative",
    "defensive",
    "safe",
    "controlled risk",
    "low volatility",
    "risk-controlled",
    "低风险",
    "风险可控",
    "控制风险",
    "稳健",
    "保守",
    "低波动",
    "回撤可控",
]

MEDIUM_RISK_HINTS = ["medium risk", "moderate", "balanced", "中等风险", "均衡", "平衡"]
HIGH_RISK_HINTS = ["high risk", "aggressive", "speculative", "高风险", "激进", "高波动", "投机"]

LONG_TERM_HINTS = ["long-term", "long term", "buy and hold", "长期", "长期持有", "长期配置", "核心持仓"]
MID_TERM_HINTS = ["mid-term", "mid term", "中期"]
SHORT_TERM_HINTS = ["short-term", "short term", "swing trade", "短期", "波段"]

QUALITY_STYLE_HINTS = [
    "quality",
    "quality compounder",
    "blue chip",
    "blue-chip",
    "franchise",
    "高质量",
    "优质",
    "蓝筹",
    "白马",
]

STAGED_ENTRY_HINTS = [
    "scale in",
    "staged entry",
    "dollar-cost average",
    "dca",
    "分批建仓",
    "分步建仓",
    "逐步建仓",
    "分批买入",
    "回调买入",
    "网格交易",
    "网格",
]

DIVIDEND_HINTS = [
    "dividend",
    "dividend stock",
    "income stock",
    "high dividend",
    "分红",
    "股息",
    "红利",
    "红利股",
    "高股息",
    "高分红",
]

VALUE_INVESTING_HINTS = [
    "value",
    "value investing",
    "价值投资",
    "低估",
    "便宜估值",
    "价值股",
]

GROWTH_INVESTING_HINTS = [
    "growth",
    "growth investing",
    "成长投资",
    "高成长",
    "成长股",
]

INDEX_HINTS = [
    "index",
    "etf",
    "index fund",
    "指数",
    "指数基金",
    "ETF",
]

MOMENTUM_HINTS = [
    "momentum",
    "trend following",
    "动能",
    "动量",
    "趋势",
    "追涨",
]

GARP_HINTS = [
    "garp",
    "growth at reasonable price",
    "合理价格成长",
]

SPECULATIVE_HINTS = [
    "快速翻倍",
    "一夜暴富",
    "暴富",
    "下周翻倍",
    "梭哈",
    "yolo",
    "moon",
    "get rich quick",
    "double next week",
]


def _contains_chinese(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text))


def _detect_language(text: str) -> str:
    return "zh" if _contains_chinese(text) else "en"


def _normalize_query(query: str) -> str:
    translation = str.maketrans(
        {
            "，": ", ",
            "。": ". ",
            "；": "; ",
            "：": ": ",
            "（": "(",
            "）": ")",
            "【": "[",
            "】": "]",
            "“": '"',
            "”": '"',
            "‘": "'",
            "’": "'",
        }
    )
    normalized = query.translate(translation)
    normalized = normalized.replace("\u3000", " ")
    return re.sub(r"\s+", " ", normalized.strip())


def _has_hint(query: str, hints: list[str]) -> bool:
    lowered = query.lower()
    return any(hint in lowered or hint in query for hint in hints)


def _extract_currency(query: str) -> str | None:
    lowered = query.lower()
    if any(token in lowered for token in ["usd", "us$", "dollar"]) or any(token in query for token in ["美元", "美金", "$"]):
        return "USD"
    if any(token in lowered for token in ["hkd", "hk$"]) or any(token in query for token in ["港币", "港元"]):
        return "HKD"
    if any(token in lowered for token in ["cny", "rmb"]) or any(token in query for token in ["人民币", "元"]):
        return "CNY"
    return None


def _apply_multiplier(value: float, suffix: str | None) -> int:
    if not suffix:
        return int(value)
    lowered = suffix.lower()
    if lowered == "k":
        return int(value * 1_000)
    if lowered == "m":
        return int(value * 1_000_000)
    if suffix == "万":
        return int(value * 10_000)
    if suffix == "亿":
        return int(value * 100_000_000)
    return int(value)


def _extract_capital_amount(query: str) -> int | None:
    chinese_match = re.search(r"(\d+(?:\.\d+)?)\s*(万|亿)", query)
    if chinese_match:
        return _apply_multiplier(float(chinese_match.group(1)), chinese_match.group(2))

    currency_tokens = r"(?:\$|usd|hkd|cny|美元|美金|港币|港元|人民币)"
    prefix_match = re.search(rf"{currency_tokens}\s*(\d+(?:,\d{{3}})*(?:\.\d+)?)\s*([kKmM])?", query, flags=re.IGNORECASE)
    if prefix_match:
        return _apply_multiplier(float(prefix_match.group(1).replace(",", "")), prefix_match.group(2))

    suffix_match = re.search(rf"(\d+(?:,\d{{3}})*(?:\.\d+)?)\s*([kKmM])?\s*{currency_tokens}", query, flags=re.IGNORECASE)
    if suffix_match:
        return _apply_multiplier(float(suffix_match.group(1).replace(",", "")), suffix_match.group(2))

    plain_match = re.search(r"\b(\d{4,8})\b", query)
    if plain_match and _extract_currency(query):
        return int(plain_match.group(1))
    return None


def _extract_risk(query: str) -> str | None:
    if _has_hint(query, LOW_RISK_HINTS):
        return "Low"
    if _has_hint(query, MEDIUM_RISK_HINTS):
        return "Medium"
    if _has_hint(query, HIGH_RISK_HINTS):
        return "High"
    return None


def _extract_horizon(query: str) -> str | None:
    if _has_hint(query, LONG_TERM_HINTS):
        return "Long-term"
    if _has_hint(query, MID_TERM_HINTS):
        return "Mid-term"
    if _has_hint(query, SHORT_TERM_HINTS):
        return "Short-term"
    return None


def _extract_style(query: str) -> str | None:
    lowered = query.lower()
    if _has_hint(query, DIVIDEND_HINTS):
        return "Dividend"
    if _has_hint(query, QUALITY_STYLE_HINTS):
        return "Quality"
    if _has_hint(query, VALUE_INVESTING_HINTS):
        return "Value"
    if _has_hint(query, GROWTH_INVESTING_HINTS):
        return "Growth"
    if _has_hint(query, INDEX_HINTS):
        return "Index"
    if _has_hint(query, MOMENTUM_HINTS):
        return "Momentum"
    if _has_hint(query, GARP_HINTS):
        return "GARP"
    if _has_hint(query, ["speculation", "投机"]):
        return "Speculation"
    return None


def _extract_named_values(query: str, mapping: dict[str, list[str]]) -> list[str]:
    lowered = query.lower()
    values: list[str] = []
    for target, keywords in mapping.items():
        if any(keyword in lowered or keyword in query for keyword in keywords):
            values.append(target)
    return values


def _extract_tickers(query: str) -> list[str]:
    tickers = {token for token in re.findall(r"\b[A-Z]{2,5}\b", query) if token not in TICKER_STOPWORDS}
    explicit_match = re.search(r"(?:ticker|tickers|股票|股票代码|个股)\s*[:：]?\s*([A-Z,\s/]{1,120})", query, flags=re.IGNORECASE)
    if explicit_match:
        for token in re.findall(r"\b[A-Z]{1,5}\b", explicit_match.group(1)):
            if token not in TICKER_STOPWORDS:
                tickers.add(token)

    lowered = query.lower()
    for company_name, ticker in COMPANY_TICKER_MAP.items():
        if company_name in lowered:
            tickers.add(ticker)
    return sorted(tickers)


def _extract_percent_value(query: str, patterns: list[str]) -> float | None:
    for pattern in patterns:
        match = re.search(pattern, query, flags=re.IGNORECASE)
        if match:
            return float(match.group(1)) / 100
    return None


def _extract_max_pe(query: str) -> float | None:
    patterns = [
        r"(?:pe|市盈率)\s*(?:<=|<|不高于|低于|上限|最大)?\s*(\d+(?:\.\d+)?)",
        r"(\d+(?:\.\d+)?)\s*(?:倍pe|倍市盈率)",
    ]
    for pattern in patterns:
        match = re.search(pattern, query, flags=re.IGNORECASE)
        if match:
            return float(match.group(1))
    if any(token in query for token in ["估值不要太高", "估值别太高", "合理估值"]) or "reasonable valuation" in query.lower():
        return 30.0
    return None


def _extract_min_roe(query: str) -> float | None:
    direct_value = _extract_percent_value(query, [r"(?:roe|净资产收益率)\s*(?:>=|至少|不低于|高于|下限)?\s*(\d+(?:\.\d+)?)\s*%?"])
    if direct_value is not None:
        return direct_value
    if any(token in query for token in ["roe 要比较稳", "roe比较稳", "roe稳定"]) or "stable roe" in query.lower():
        return 0.10
    return None


def _extract_min_dividend_yield(query: str) -> float | None:
    return _extract_percent_value(query, [r"(?:dividend yield|股息率|分红率)\s*(?:>=|至少|不低于|高于|下限)?\s*(\d+(?:\.\d+)?)\s*%?"])


def _extract_filters(query: str) -> FundamentalFilters:
    lowered = query.lower()
    require_positive_fcf = any(
        token in query or token in lowered
        for token in ["自由现金流为正", "正向自由现金流", "positive free cash flow", "positive fcf"]
    )

    analyst_rating = None
    if "strong buy" in lowered or "强烈买入" in query:
        analyst_rating = "strong_buy"
    elif re.search(r"\bbuy\b", lowered) or "买入评级" in query:
        analyst_rating = "buy"

    return FundamentalFilters(
        max_pe_ratio=_extract_max_pe(query),
        min_roe=_extract_min_roe(query),
        min_dividend_yield=_extract_min_dividend_yield(query),
        require_positive_fcf=require_positive_fcf,
        analyst_rating=analyst_rating,
    )


def _is_speculative(query: str) -> bool:
    return _has_hint(query, SPECULATIVE_HINTS)


def _has_filter_value(filters: FundamentalFilters) -> bool:
    return any(
        [
            filters.max_pe_ratio is not None,
            filters.min_roe is not None,
            filters.min_dividend_yield is not None,
            filters.require_positive_fcf,
            bool(filters.analyst_rating),
        ]
    )


def _build_missing_info(intent: ParsedIntent) -> list[str]:
    missing: list[str] = []
    if intent.portfolio_sizing.capital_amount is None and not intent.explicit_targets.tickers:
        missing.append("capital_amount")
    if not intent.risk_profile.tolerance_level:
        missing.append("risk_tolerance")
    if not intent.investment_strategy.horizon:
        missing.append("investment_horizon")
    if not intent.investment_strategy.style and not _has_filter_value(intent.fundamental_filters):
        missing.append("investment_style")
    return missing


def _is_intent_clear(intent: ParsedIntent, speculative: bool) -> bool:
    if speculative:
        return False

    core_signals = [
        intent.portfolio_sizing.capital_amount is not None,
        bool(intent.risk_profile.tolerance_level),
        bool(intent.investment_strategy.horizon),
    ]
    if sum(core_signals) < 2:
        return False

    optional_signals = [
        bool(intent.investment_strategy.style),
        bool(intent.investment_strategy.preferred_sectors or intent.investment_strategy.preferred_industries),
        bool(intent.explicit_targets.tickers),
        _has_filter_value(intent.fundamental_filters),
    ]
    return sum(optional_signals) >= 1 and sum(core_signals) + sum(optional_signals) >= 4


def _is_intent_usable(intent: ParsedIntent, speculative: bool) -> bool:
    if speculative:
        return False

    has_capital = intent.portfolio_sizing.capital_amount is not None
    has_risk = bool(intent.risk_profile.tolerance_level)
    has_horizon = bool(intent.investment_strategy.horizon)
    has_style = bool(intent.investment_strategy.style)
    has_filters = _has_filter_value(intent.fundamental_filters)
    has_targets = bool(intent.explicit_targets.tickers)
    has_preferences = bool(intent.investment_strategy.preferred_sectors or intent.investment_strategy.preferred_industries)

    if has_targets and (has_horizon or has_risk or has_style or has_filters):
        return True
    if has_capital and (has_horizon or has_risk or has_style or has_filters or has_preferences):
        return True
    return sum([has_capital, has_risk, has_horizon]) >= 2 and (has_style or has_filters or has_targets or has_preferences)


def _localized_assumption(language: str, zh_text: str, en_text: str) -> str:
    return zh_text if language == "zh" else en_text


def _apply_assumptions(intent: ParsedIntent, query: str) -> list[str]:
    language = intent.system_context.language
    assumptions: list[str] = []

    if not intent.risk_profile.tolerance_level and intent.investment_strategy.style in {"Dividend", "Quality", "Value"}:
        intent.risk_profile.tolerance_level = "Medium"
        assumptions.append(
            _localized_assumption(
                language,
                "未明确写出风险等级，系统暂按中等风险偏好继续分析。",
                "Risk tolerance was not explicit, so the analysis assumes a medium-risk mandate.",
            )
        )

    if not intent.investment_strategy.horizon and intent.investment_strategy.style in {"Dividend", "Quality", "Value"}:
        intent.investment_strategy.horizon = "Long-term"
        assumptions.append(
            _localized_assumption(
                language,
                "未明确写出持有期限，系统暂按长期持有继续分析。",
                "The holding horizon was not explicit, so the analysis assumes a long-term mandate.",
            )
        )

    if not intent.investment_strategy.style and intent.explicit_targets.tickers:
        intent.investment_strategy.style = "General"
        assumptions.append(
            _localized_assumption(
                language,
                "未明确写出投资风格，系统暂按通用研究模式继续分析。",
                "The investment style was not explicit, so the analysis proceeds with a general research style.",
            )
        )

    if not intent.portfolio_sizing.capital_amount and intent.explicit_targets.tickers:
        assumptions.append(
            _localized_assumption(
                language,
                "由于未提供资金规模，仓位建议会以比例而不是金额展示。",
                "No capital amount was provided, so position sizing will be shown as percentages instead of dollar allocations.",
            )
        )

    if _has_hint(query, STAGED_ENTRY_HINTS):
        assumptions.append(
            _localized_assumption(
                language,
                "用户明确偏好分批建仓，执行建议会优先采用分批入场。",
                "The user explicitly prefers staged entries, so execution advice will prioritize scaling in.",
            )
        )

    return assumptions


def _build_explicit_intent(normalized_query: str) -> ParsedIntent:
    language = _detect_language(normalized_query)
    capital_amount = _extract_capital_amount(normalized_query)

    return ParsedIntent(
        system_context=SystemContext(language=language),
        portfolio_sizing=PortfolioSizing(
            capital_amount=capital_amount,
            currency=_extract_currency(normalized_query) if capital_amount is not None else None,
        ),
        risk_profile=RiskProfile(
            tolerance_level=_extract_risk(normalized_query),
            max_drawdown_expectation=None,
        ),
        investment_strategy=InvestmentStrategy(
            horizon=_extract_horizon(normalized_query),
            style=_extract_style(normalized_query),
            preferred_sectors=_extract_named_values(normalized_query, SECTOR_KEYWORDS),
            preferred_industries=_extract_named_values(normalized_query, INDUSTRY_KEYWORDS),
        ),
        fundamental_filters=_extract_filters(normalized_query),
        explicit_targets=ExplicitTargets(tickers=_extract_tickers(normalized_query)),
    )


def extract_explicit_intent(query: str) -> ParsedIntent:
    return _build_explicit_intent(_normalize_query(query))


def parse_intent(query: str) -> ParsedIntent:
    normalized_query = _normalize_query(query)
    intent = _build_explicit_intent(normalized_query)
    speculative = _is_speculative(normalized_query)
    assumptions = _apply_assumptions(intent, normalized_query)
    is_clear = _is_intent_clear(intent, speculative)
    is_usable = _is_intent_usable(intent, speculative)
    missing_info = [] if is_clear else _build_missing_info(intent)
    if speculative and "investment_style" not in missing_info:
        missing_info.insert(0, "investment_style")

    intent.agent_control = AgentControl(
        is_intent_clear=is_clear,
        is_intent_usable=is_usable,
        missing_critical_info=missing_info,
        assumptions=assumptions,
    )
    return intent


def _build_follow_up_question(intent: ParsedIntent) -> str:
    language = intent.system_context.language
    missing = intent.agent_control.missing_critical_info

    zh_map = {
        "capital_amount": "你计划投入多少资金？",
        "risk_tolerance": "你能接受多大的波动或回撤？",
        "investment_horizon": "你的投资期限更偏短期、中期还是长期？",
        "investment_style": "你更偏价值、成长、指数、质量蓝筹还是分红风格？",
        "preferred_sectors": "你有偏好的行业或板块吗？",
        "fundamental_filters": "你对 PE、ROE、股息率或自由现金流有明确要求吗？",
    }
    en_map = {
        "capital_amount": "How much capital do you plan to invest?",
        "risk_tolerance": "What level of drawdown or volatility can you accept?",
        "investment_horizon": "Is your horizon short-term, mid-term, or long-term?",
        "investment_style": "Do you prefer value, growth, index, quality blue chips, or dividend style?",
        "preferred_sectors": "Do you have preferred sectors or industries?",
        "fundamental_filters": "Do you have clear PE, ROE, dividend yield, or cash flow requirements?",
    }

    if language == "zh":
        questions = [zh_map[item] for item in missing if item in zh_map]
        base = "我还缺少几项关键信息，暂时不适合直接给你分析结果。"
        return base + (" ".join(questions) if questions else "请补充你的风险偏好、期限和筛选条件。")

    questions = [en_map[item] for item in missing if item in en_map]
    base = "I still need a few key details before giving you a reliable analysis. "
    return base + (" ".join(questions) if questions else "Please share your risk profile, horizon, and key filters.")
