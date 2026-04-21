"""RAG 结论校验服务：检查最终报告是否和证据、评分、时间范围一致。"""

from __future__ import annotations

from typing import Any


class ReportValidationService:
    """负责生成校验结果并统一计算报告可信度。"""

    def apply_validation(
        self,
        *,
        final_report: str,
        report_briefing: dict[str, Any],
        language_code: str,
    ) -> dict[str, Any]:
        """检查报告结论是否和结构化数据、RAG 证据一致。"""
        meta = report_briefing.setdefault("meta", {})
        checks = self._build_validation_checks(final_report, report_briefing, language_code=language_code)
        confidence_level = self._confidence_from_checks(checks)
        validation_summary = dict(meta.get("validation_summary") or {})
        existing_items = list(validation_summary.get("items") or [])
        new_items = [item["summary"] for item in checks if item["status"] != "pass"]
        validation_summary["items"] = self._dedupe_texts(existing_items + new_items)
        validation_summary["level"] = "pass" if confidence_level == "high" else "caution" if confidence_level == "medium" else "warning"
        meta["validation_checks"] = checks
        meta["validation_summary"] = validation_summary
        meta["confidence_level"] = confidence_level
        meta["validation_flags"] = list(validation_summary["items"])
        return meta

    def _build_validation_checks(
        self,
        final_report: str,
        report_briefing: dict[str, Any],
        *,
        language_code: str,
    ) -> list[dict[str, Any]]:
        """生成用户可读的一致性校验结果。"""
        meta = report_briefing.get("meta", {}) or {}
        evidence = self._as_list(meta.get("retrieved_evidence"))
        executive = self._as_dict(report_briefing.get("executive"))
        top_pick = self._text(executive.get("top_pick")).upper()
        return [
            self._check_evidence_count(evidence, language_code),
            self._check_evidence_freshness(evidence, language_code),
            self._check_top_pick_evidence(evidence, top_pick, language_code),
            self._check_top_pick_ranking(report_briefing, top_pick, language_code),
            self._check_report_mentions_top_pick(final_report, top_pick, language_code),
            self._check_time_scope(evidence, self._text(meta.get("as_of_date")), language_code),
            self._check_score_consistency(report_briefing, top_pick, language_code),
            self._check_risk_coverage(report_briefing, language_code),
            self._check_data_degradation(meta, language_code),
        ]

    def _check_evidence_count(self, evidence: list[dict[str, Any]], language_code: str) -> dict[str, Any]:
        """检查证据数量是否足够支撑报告。"""
        count = len(evidence)
        status = "pass" if count >= 3 else "warn" if count else "fail"
        summary = (
            f"本次检索到 {count} 条证据，证据覆盖偏少。"
            if language_code == "zh" and status != "pass"
            else f"Retrieved {count} evidence items, which is limited."
            if status != "pass"
            else f"Retrieved {count} evidence items for this report."
        )
        return self._check("evidence_count", "证据数量" if language_code == "zh" else "Evidence count", status, summary)

    def _check_evidence_freshness(self, evidence: list[dict[str, Any]], language_code: str) -> dict[str, Any]:
        """检查 RAG 证据是否过旧或混入未来资料。"""
        stale_items = [item for item in evidence if self._text(item.get("freshness")).lower() == "stale"]
        future_items = [item for item in evidence if self._text(item.get("freshness")).lower() == "future"]
        undated_items = [item for item in evidence if self._text(item.get("freshness")).lower() == "undated"]
        if future_items:
            status = "fail"
            summary = (
                f"发现 {len(future_items)} 条未来证据，需要降低结论可信度。"
                if language_code == "zh"
                else f"Found {len(future_items)} future-dated evidence items; confidence was downgraded."
            )
        elif stale_items:
            status = "warn"
            summary = (
                f"发现 {len(stale_items)} 条较旧证据，结论需要谨慎阅读。"
                if language_code == "zh"
                else f"Found {len(stale_items)} stale evidence items; read the conclusion cautiously."
            )
        elif undated_items and not evidence:
            status = "warn"
            summary = "没有可判断时效的证据。" if language_code == "zh" else "No dateable evidence was available."
        else:
            status = "pass"
            summary = "证据时效没有发现明显问题。" if language_code == "zh" else "Evidence freshness did not show obvious issues."
        return self._check("evidence_freshness", "证据时效" if language_code == "zh" else "Evidence freshness", status, summary)

    def _check_top_pick_evidence(self, evidence: list[dict[str, Any]], top_pick: str, language_code: str) -> dict[str, Any]:
        """检查优先标的是否有直接证据支持。"""
        if not top_pick:
            return self._check(
                "top_pick_has_evidence",
                "优先标的证据" if language_code == "zh" else "Top pick evidence",
                "warn",
                "本次没有明确优先标的，证据校验只能作为辅助。" if language_code == "zh" else "No explicit top pick was available for evidence validation.",
            )
        has_evidence = any(self._text(item.get("ticker")).upper() == top_pick for item in evidence)
        status = "pass" if has_evidence else "fail"
        summary = (
            f"优先标的 {top_pick} 缺少直接证据支持。"
            if language_code == "zh" and not has_evidence
            else f"Top pick {top_pick} lacks direct retrieved evidence."
            if not has_evidence
            else f"Top pick {top_pick} has direct retrieved evidence."
        )
        return self._check("top_pick_has_evidence", "优先标的证据" if language_code == "zh" else "Top pick evidence", status, summary)

    def _check_top_pick_ranking(self, report_briefing: dict[str, Any], top_pick: str, language_code: str) -> dict[str, Any]:
        """检查优先标的是否由评分排序支持。"""
        rows = self._as_list(report_briefing.get("scoreboard"))
        scored_rows = [(self._text(row.get("ticker")).upper(), self._score_value(row)) for row in rows]
        scored_rows = [(ticker, score) for ticker, score in scored_rows if ticker and score is not None]
        top_score = next((score for ticker, score in scored_rows if ticker == top_pick), None)
        best_score = max((score for _, score in scored_rows), default=None)
        if not top_pick or top_score is None or best_score is None:
            return self._check(
                "top_pick_ranking",
                "优先标的排序" if language_code == "zh" else "Top pick ranking",
                "pass",
                "缺少足够评分数据，排序校验由评分一致性检查覆盖。" if language_code == "zh" else "Ranking check was skipped because score data is incomplete.",
            )
        status = "warn" if top_score + 5 < best_score else "pass"
        summary = (
            f"优先标的 {top_pick} 不是评分最高标的，建议谨慎解读。"
            if language_code == "zh" and status != "pass"
            else f"Top pick {top_pick} is not the highest-scored candidate; read the ranking cautiously."
            if status != "pass"
            else f"Top pick {top_pick} is supported by the score ranking."
        )
        return self._check("top_pick_ranking", "优先标的排序" if language_code == "zh" else "Top pick ranking", status, summary)

    def _check_report_mentions_top_pick(self, final_report: str, top_pick: str, language_code: str) -> dict[str, Any]:
        """检查正式报告是否没有遗漏优先标的。"""
        if not top_pick:
            return self._check(
                "report_mentions_top_pick",
                "报告结论一致性" if language_code == "zh" else "Report conclusion consistency",
                "warn",
                "缺少优先标的，无法完整校验报告结论。" if language_code == "zh" else "No top pick is available for report consistency validation.",
            )
        mentioned = top_pick in (final_report or "").upper()
        status = "pass" if mentioned else "fail"
        summary = (
            f"正式报告没有提到优先标的 {top_pick}，结论需要降级。"
            if language_code == "zh" and not mentioned
            else f"The final report did not mention top pick {top_pick}; confidence was downgraded."
            if not mentioned
            else f"The final report mentions top pick {top_pick}."
        )
        return self._check("report_mentions_top_pick", "报告结论一致性" if language_code == "zh" else "Report conclusion consistency", status, summary)

    def _check_time_scope(self, evidence: list[dict[str, Any]], as_of_date: str, language_code: str) -> dict[str, Any]:
        """检查历史研究有没有混入未来证据。"""
        if not as_of_date:
            return self._check("time_scope", "时间范围" if language_code == "zh" else "Time scope", "pass", "No dated research scope was set.")
        future_items = [item for item in evidence if self._text(item.get("published_at")) and self._text(item.get("published_at")) > as_of_date]
        status = "fail" if future_items else "pass"
        summary = (
            f"发现 {len(future_items)} 条研究日期之后的证据。"
            if language_code == "zh" and future_items
            else f"Found {len(future_items)} evidence items after the research date."
            if future_items
            else "证据时间范围与研究日期一致。"
            if language_code == "zh"
            else "Evidence dates are consistent with the research date."
        )
        return self._check("time_scope", "时间范围" if language_code == "zh" else "Time scope", status, summary)

    def _check_score_consistency(self, report_briefing: dict[str, Any], top_pick: str, language_code: str) -> dict[str, Any]:
        """检查低评分标的是否被过度包装成强结论。"""
        row = next((item for item in self._as_list(report_briefing.get("scoreboard")) if self._text(item.get("ticker")).upper() == top_pick), None)
        if not row:
            return self._check(
                "score_consistency",
                "评分一致性" if language_code == "zh" else "Score consistency",
                "warn",
                f"优先标的 {top_pick or 'N/A'} 未在评分表中找到。" if language_code == "zh" else f"Top pick {top_pick or 'N/A'} was not found in the scoreboard.",
            )
        score = self._number(row.get("suitability_score") or row.get("composite_score"))
        verdict = self._text(row.get("verdict_label")).lower()
        is_strong = any(token in verdict for token in ["strong", "buy", "优先", "买入"])
        status = "warn" if score is not None and score < 55 and is_strong else "pass"
        summary = (
            f"优先标的 {top_pick} 的评分较低但结论偏积极。"
            if language_code == "zh" and status != "pass"
            else f"Top pick {top_pick} has a low score but an aggressive verdict."
            if status != "pass"
            else f"Top pick {top_pick} score and verdict are aligned."
        )
        return self._check("score_consistency", "评分一致性" if language_code == "zh" else "Score consistency", status, summary)

    def _check_risk_coverage(self, report_briefing: dict[str, Any], language_code: str) -> dict[str, Any]:
        """检查报告是否至少保留主要风险提示。"""
        risk_register = self._as_list(report_briefing.get("risk_register"))
        card_risks = [
            risk
            for card in self._as_list(report_briefing.get("ticker_cards"))
            for risk in (card.get("risks") or [])
            if self._text(risk)
        ]
        has_risk = bool(risk_register or card_risks)
        status = "pass" if has_risk else "warn"
        summary = (
            "报告没有找到明确风险提示，需要谨慎阅读。"
            if language_code == "zh" and not has_risk
            else "No explicit risk coverage was found; read the report cautiously."
            if not has_risk
            else "报告包含主要风险提示。"
            if language_code == "zh"
            else "The report includes explicit risk coverage."
        )
        return self._check("risk_coverage", "风险覆盖" if language_code == "zh" else "Risk coverage", status, summary)

    def _check_data_degradation(self, meta: dict[str, Any], language_code: str) -> dict[str, Any]:
        """检查是否存在数据降级或覆盖不足提示。"""
        flags = list(meta.get("coverage_flags") or [])
        status = "warn" if flags else "pass"
        summary = (
            f"存在 {len(flags)} 条数据覆盖或降级提示。"
            if language_code == "zh" and flags
            else f"There are {len(flags)} data coverage or fallback warnings."
            if flags
            else "没有发现新的数据降级提示。"
            if language_code == "zh"
            else "No additional data degradation warnings were found."
        )
        return self._check("data_degradation", "数据降级" if language_code == "zh" else "Data degradation", status, summary)

    @staticmethod
    def _check(check_id: str, label: str, status: str, summary: str) -> dict[str, Any]:
        """生成统一校验字典。"""
        return {
            "id": check_id,
            "label": label,
            "status": status,
            "severity": "high" if status == "fail" else "medium" if status == "warn" else "low",
            "summary": summary,
        }

    @staticmethod
    def _confidence_from_checks(checks: list[dict[str, Any]]) -> str:
        """根据校验结果统一计算可信度。"""
        if any(item.get("status") == "fail" for item in checks):
            return "low"
        if any(item.get("status") == "warn" for item in checks):
            return "medium"
        return "high"

    @staticmethod
    def _as_dict(value: Any) -> dict[str, Any]:
        """安全转换字典。"""
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _as_list(value: Any) -> list[dict[str, Any]]:
        """安全转换字典列表。"""
        return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []

    @staticmethod
    def _text(value: Any, fallback: str = "") -> str:
        """安全转换文本。"""
        if value is None:
            return fallback
        text = str(value).strip()
        return text or fallback

    @staticmethod
    def _number(value: Any) -> float | None:
        """安全转换数字。"""
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _score_value(self, row: dict[str, Any]) -> float | None:
        """读取评分表里最能代表排序的分数。"""
        return self._number(row.get("suitability_score") or row.get("composite_score") or row.get("score"))

    @staticmethod
    def _dedupe_texts(values: list[str]) -> list[str]:
        """按原顺序去重文本。"""
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            text = str(value).strip()
            if text and text not in seen:
                result.append(text)
                seen.add(text)
        return result
