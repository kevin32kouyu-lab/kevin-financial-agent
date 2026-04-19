"""
Reporting module for generating financial investment memos.

This module has been refactored into submodules for better maintainability:
- profiling: derive analysis profiles from raw data
- scoring: calculate financial scores and candidate analysis
- builder: construct structured briefings and reports

This file maintains backward compatibility by re-exporting all public functions.
"""

# Re-export all functions from submodules
from .reporting.profiling import (
    _derive_news_profile,
    _derive_tech_profile,
    _derive_smart_money_profile,
    _derive_audit_profile,
)

from .reporting.scoring import (
    _build_candidate_analysis,
    _build_allocation_plan,
    _macro_is_severe,
)

from .reporting.builder import (
    _ordered_snapshots,
    _build_merged_data_package,
    _build_report_briefing,
    _build_report_system_prompt,
    _build_report_user_prompt,
    _validate_report_output,
    _build_rule_based_report,
)

# Re-export constants for backward compatibility
from .reporting.profiling import (
    POSITIVE_HEADLINE_KEYWORDS,
    NEGATIVE_HEADLINE_KEYWORDS,
    SMART_MONEY_HOT_SIGNALS,
)

# Re-export helper functions
from .reporting.profiling import (
    _labels,
    _coerce_float,
    _coerce_percent_points,
    _format_scalar,
    _headline_score,
    _clamp,
)

from .reporting.scoring import (
    _normalize_trend_score,
    _analyst_bonus,
    _localize_verdict,
    _alignment_label,
)

from .reporting.builder import (
    _language_label,
    _build_report_input,
    _market_stance,
)

__all__ = [
    # Constants
    "POSITIVE_HEADLINE_KEYWORDS",
    "NEGATIVE_HEADLINE_KEYWORDS",
    "SMART_MONEY_HOT_SIGNALS",
    # Helpers
    "_labels",
    "_coerce_float",
    "_coerce_percent_points",
    "_format_scalar",
    "_headline_score",
    "_clamp",
    "_language_label",
    "_normalize_trend_score",
    "_analyst_bonus",
    "_localize_verdict",
    "_market_stance",
    "_alignment_label",
    "_build_report_input",
    # Profiling
    "_derive_news_profile",
    "_derive_tech_profile",
    "_derive_smart_money_profile",
    "_derive_audit_profile",
    # Scoring
    "_build_candidate_analysis",
    "_build_allocation_plan",
    "_macro_is_severe",
    # Builder
    "_ordered_snapshots",
    "_build_merged_data_package",
    "_build_report_briefing",
    "_build_report_system_prompt",
    "_build_report_user_prompt",
    "_validate_report_output",
    "_build_rule_based_report",
]
