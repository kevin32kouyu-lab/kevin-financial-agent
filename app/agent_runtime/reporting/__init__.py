"""Reporting module for generating financial investment memos.

This module provides functions for:
- Profiling: deriving analysis profiles from raw data
- Scoring: calculating financial scores and candidate analysis
- Builder: constructing structured briefings and reports
"""

# Re-export all public functions
from .profiling import (
    _derive_news_profile,
    _derive_tech_profile,
    _derive_smart_money_profile,
    _derive_audit_profile,
)

from .scoring import (
    _build_candidate_analysis,
    _build_allocation_plan,
    _macro_is_severe,
)

from .builder import (
    _format_scalar,
    _labels,
    _language_label,
    _ordered_snapshots,
    _build_merged_data_package,
    _build_report_input,
    _build_report_briefing,
    _build_report_system_prompt,
    _build_report_user_prompt,
    _validate_report_output,
    _build_rule_based_report,
)

__all__ = [
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
    "_format_scalar",
    "_labels",
    "_language_label",
    "_ordered_snapshots",
    "_build_merged_data_package",
    "_build_report_input",
    "_build_report_briefing",
    "_build_report_system_prompt",
    "_build_report_user_prompt",
    "_validate_report_output",
    "_build_rule_based_report",
]
