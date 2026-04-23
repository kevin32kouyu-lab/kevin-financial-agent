"""PDF 导出服务：把 run 的正式报告渲染成后端生成的真实 PDF。"""

from __future__ import annotations

import asyncio
import html
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import AppSettings, ROOT_DIR


class PdfExportUnavailable(RuntimeError):
    """PDF 引擎不可用或渲染失败时抛出的明确异常。"""


@dataclass(slots=True)
class PdfExportResult:
    """PDF 下载结果，供 API 层直接返回给浏览器。"""

    filename: str
    content: bytes
    media_type: str = "application/pdf"


class PdfExportService:
    """负责生成 PDF 专用 HTML，并调用 Playwright 渲染真实 PDF。"""

    def __init__(self, *, settings: AppSettings, project_root: Path = ROOT_DIR):
        self.settings = settings
        self.project_root = project_root
        self.renderer_script = project_root / "scripts" / "render_pdf.mjs"

    def build_report_html(
        self,
        *,
        run_id: str,
        result: dict[str, Any],
        backtest: Any = None,
        kind: str = "investment",
    ) -> str:
        """把报告数据整理成 PDF 专用 HTML，不依赖前端临时拼接。"""
        normalized_kind = _normalize_pdf_kind(kind)
        report_briefing = _record(result.get("report_briefing"))
        meta = _record(report_briefing.get("meta"))
        executive = _record(report_briefing.get("executive"))
        macro = _record(report_briefing.get("macro"))
        scoreboard = _records(report_briefing.get("scoreboard"))
        ticker_cards = _records(report_briefing.get("ticker_cards"))
        risk_register = _records(report_briefing.get("risk_register"))
        research_context = _record(result.get("research_context"))
        evidence_summary = _record(meta.get("evidence_summary"))
        validation_summary = _record(meta.get("validation_summary"))
        retrieved_evidence = _records(meta.get("retrieved_evidence"))
        backtest_payload = _plain(backtest)
        report_outputs = _record(result.get("report_outputs"))
        investment_output = _record(report_outputs.get("investment"))
        development_output = _record(report_outputs.get("development"))

        if normalized_kind == "development":
            return _build_development_report_html(
                run_id=run_id,
                result=result,
                report_briefing=report_briefing,
                development_output=development_output,
                backtest_payload=backtest_payload,
            )

        title = _text(meta.get("title"), "Investment Research Report")
        subtitle = _text(meta.get("subtitle"), "Research terminal / portfolio decision memo")
        query = _text(result.get("query"), "No original request.")
        final_report = _text(investment_output.get("markdown") or result.get("final_report"), "")
        generated_at = _text(meta.get("generated_at") or result.get("updated_at"), "")
        confidence = _text(meta.get("confidence_level"), "not rated")
        chart_block = _build_investment_chart_block(_record(investment_output.get("charts")), backtest_payload)

        scoreboard_rows = "".join(
            "<tr>"
            f"<td>{_esc(item.get('ticker'))}</td>"
            f"<td>{_esc(item.get('company_name'))}</td>"
            f"<td>{_esc(item.get('latest_price'))}</td>"
            f"<td>{_esc(item.get('composite_score'))}</td>"
            f"<td>{_esc(item.get('verdict_label'))}</td>"
            "</tr>"
            for item in scoreboard
        )
        ticker_blocks = "\n".join(_build_ticker_card(item) for item in ticker_cards)
        risk_items = "".join(
            f"<li><strong>{_esc(item.get('category'))}{' / ' + _esc(item.get('ticker')) if item.get('ticker') else ''}</strong>: {_esc(item.get('summary'))}</li>"
            for item in risk_register
        )
        evidence_items = _bullet_list([*_strings(evidence_summary.get("items")), *_strings(evidence_summary.get("source_points"))])
        validation_items = _bullet_list(_strings(validation_summary.get("items")))
        retrieved_block = _build_retrieved_evidence(retrieved_evidence)
        backtest_block = _build_backtest_block(backtest_payload)

        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{_esc(title)}</title>
  <style>
    @page {{ size: A4; margin: 15mm 13mm 17mm; }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: #f5f1e8;
      color: #162033;
      font-family: "Aptos", "Segoe UI", "Noto Sans", sans-serif;
      font-size: 12px;
      line-height: 1.58;
    }}
    .page {{ max-width: 980px; margin: 0 auto; padding: 26px 22px 40px; }}
    .hero {{
      color: #f8efe0;
      background: linear-gradient(135deg, #13243d 0%, #1e4d4a 58%, #b17b39 100%);
      border-radius: 26px;
      padding: 30px;
      margin-bottom: 18px;
    }}
    .eyebrow {{ margin: 0 0 9px; letter-spacing: .22em; text-transform: uppercase; font-size: 10px; opacity: .82; }}
    h1 {{ margin: 0; font-family: Georgia, "Times New Roman", serif; font-size: 30px; line-height: 1.08; }}
    h2 {{ margin: 0 0 12px; font-family: Georgia, "Times New Roman", serif; font-size: 20px; color: #13243d; }}
    h3 {{ margin: 0 0 8px; font-size: 15px; color: #13243d; }}
    .hero-summary {{ max-width: 760px; margin: 16px 0 0; font-size: 14px; }}
    .chips {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px; }}
    .chip {{ display: inline-flex; padding: 6px 10px; border-radius: 999px; background: rgba(255,255,255,.16); border: 1px solid rgba(255,255,255,.22); }}
    .section {{
      background: #fffaf2;
      border: 1px solid #e2d5bf;
      border-radius: 20px;
      padding: 18px;
      margin-bottom: 14px;
      break-inside: avoid;
    }}
    .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }}
    .muted {{ color: #637083; }}
    .question {{ padding: 13px 15px; background: #f0eadf; border-radius: 14px; font-size: 13px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ padding: 9px 8px; border-bottom: 1px solid #e5dccd; text-align: left; vertical-align: top; }}
    th {{ color: #6f5b3e; text-transform: uppercase; letter-spacing: .08em; font-size: 10px; }}
    ul {{ margin: 8px 0 0; padding-left: 18px; }}
    li {{ margin: 4px 0; }}
    .cards {{ display: grid; gap: 12px; }}
    .ticker-card {{ border: 1px solid #ded2bf; border-radius: 16px; padding: 14px; background: #fffdf8; }}
    .ticker-head {{ display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }}
    .badge {{ border-radius: 999px; padding: 5px 9px; background: #e5f0ed; color: #17645e; font-size: 10px; white-space: nowrap; }}
    .memo {{ white-space: pre-wrap; font-family: inherit; }}
    .chart {{ width: 100%; max-height: 220px; }}
    a {{ color: #185d8f; text-decoration: none; }}
    .footer-note {{ margin-top: 16px; color: #768195; font-size: 10px; }}
  </style>
</head>
<body>
  <main class="page">
    <section class="hero">
      <p class="eyebrow">Investment report PDF</p>
      <h1>{_esc(title)}</h1>
      <p class="hero-summary">{_esc(executive.get("display_call") or executive.get("primary_call"))}</p>
      <div class="chips">
        <span class="chip">Run: {_esc(run_id)}</span>
        <span class="chip">Top pick: {_esc(executive.get("top_pick"))}</span>
        <span class="chip">Confidence: {_esc(confidence)}</span>
        <span class="chip">Mode: {_esc(research_context.get("research_mode") or meta.get("research_mode") or "realtime")}</span>
      </div>
      <p class="muted">{_esc(subtitle)}{f" · {_esc(generated_at)}" if generated_at else ""}</p>
    </section>

    <section class="section">
      <h2>Original request</h2>
      <div class="question">{_esc(query)}</div>
      {_optional_line("As of date", research_context.get("as_of_date") or meta.get("as_of_date"))}
    </section>

    <div class="grid">
      <section class="section">
        <h2>Executive conclusion</h2>
        <p>{_esc(executive.get("display_action_summary") or executive.get("action_summary"))}</p>
      </section>
      <section class="section">
        <h2>Market context</h2>
        <p>{_esc(macro.get("risk_headline"))}</p>
        <p class="muted">Regime: {_esc(macro.get("regime"))} · VIX: {_esc(macro.get("vix"))}</p>
      </section>
    </div>

    <div class="grid">
      <section class="section">
        <h2>Evidence summary</h2>
        <p>{_esc(evidence_summary.get("headline"))}</p>
        {evidence_items}
      </section>
      <section class="section">
        <h2>Validation and caveats</h2>
        <p>{_esc(validation_summary.get("headline"))}</p>
        {validation_items}
      </section>
    </div>

    {retrieved_block}

    {chart_block}

    <section class="section">
      <h2>Candidate scoreboard</h2>
      <table>
        <thead><tr><th>Ticker</th><th>Company</th><th>Price</th><th>Score</th><th>Verdict</th></tr></thead>
        <tbody>{scoreboard_rows or '<tr><td colspan="5">No scoreboard available.</td></tr>'}</tbody>
      </table>
    </section>

    <section class="section">
      <h2>Ticker research cards</h2>
      <div class="cards">{ticker_blocks or '<p>No ticker cards available.</p>'}</div>
    </section>

    <section class="section">
      <h2>Risk register</h2>
      <ul>{risk_items or '<li>No risk register available.</li>'}</ul>
    </section>

    {backtest_block}

    <section class="section">
      <h2>Full memo</h2>
      <div class="memo">{_esc(final_report) if final_report else 'No full memo available.'}</div>
    </section>

    <p class="footer-note">Generated by Financial Agent. This report is for research workflow review only and is not financial advice.</p>
  </main>
</body>
</html>"""

    async def export_report_pdf(
        self,
        *,
        run_id: str,
        result: dict[str, Any],
        backtest: Any = None,
        kind: str = "investment",
    ) -> PdfExportResult:
        """生成真实 PDF 字节，并返回浏览器可下载的文件名。"""
        normalized_kind = _normalize_pdf_kind(kind)
        html_content = self.build_report_html(run_id=run_id, result=result, backtest=backtest, kind=normalized_kind)
        content = await self._render_html_to_pdf(html_content)
        if not content.startswith(b"%PDF"):
            raise PdfExportUnavailable("PDF 渲染失败：输出内容不是有效 PDF。")
        return PdfExportResult(filename=self._build_filename(result, kind=normalized_kind), content=content)

    async def _render_html_to_pdf(self, html_content: str) -> bytes:
        """调用 Node Playwright 脚本，把 HTML 渲染为 PDF。"""
        return await asyncio.to_thread(self._render_html_to_pdf_sync, html_content)

    def _render_html_to_pdf_sync(self, html_content: str) -> bytes:
        """同步执行 Playwright，方便放到线程中运行。"""
        if not self.renderer_script.exists():
            raise PdfExportUnavailable("PDF 渲染脚本不存在。")
        with tempfile.TemporaryDirectory(prefix="financial-agent-pdf-") as temp_dir:
            temp_path = Path(temp_dir)
            html_path = temp_path / "report.html"
            pdf_path = temp_path / "report.pdf"
            html_path.write_text(html_content, encoding="utf-8")
            try:
                completed = subprocess.run(
                    ["node", str(self.renderer_script), str(html_path), str(pdf_path)],
                    cwd=self.project_root,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=self.settings.pdf_export_timeout_seconds,
                    check=False,
                )
            except FileNotFoundError as exc:
                raise PdfExportUnavailable("当前环境未安装 Node.js，无法生成 PDF。") from exc
            except subprocess.TimeoutExpired as exc:
                raise PdfExportUnavailable("PDF 渲染超时，请稍后重试。") from exc
            if completed.returncode != 0:
                message = (completed.stderr or completed.stdout or "Playwright 渲染失败。").strip()
                raise PdfExportUnavailable(message)
            if not pdf_path.exists():
                raise PdfExportUnavailable("PDF 渲染完成但没有生成文件。")
            return pdf_path.read_bytes()

    def _build_filename(self, result: dict[str, Any], *, kind: str = "investment") -> str:
        """生成稳定、浏览器友好的 PDF 文件名。"""
        report_briefing = _record(result.get("report_briefing"))
        meta = _record(report_briefing.get("meta"))
        date_part = _text(meta.get("as_of_date") or _text(result.get("as_of_date"), ""), "")
        if not date_part:
            date_part = _text(meta.get("generated_at"), "")[:10]
        suffix = date_part if re.match(r"^\d{4}-\d{2}-\d{2}$", date_part) else "latest"
        prefix = "development-report" if kind == "development" else "investment-report"
        return f"{prefix}-{suffix}.pdf"


def _normalize_pdf_kind(kind: str) -> str:
    """规范化 PDF 报告类型。"""
    normalized = _text(kind, "investment").lower()
    if normalized not in {"investment", "development"}:
        raise PdfExportUnavailable("PDF kind 只支持 investment 或 development。")
    return normalized


def _build_development_report_html(
    *,
    run_id: str,
    result: dict[str, Any],
    report_briefing: dict[str, Any],
    development_output: dict[str, Any],
    backtest_payload: Any,
) -> str:
    """渲染面向开源项目读者的开发报告 PDF。"""
    meta = _record(report_briefing.get("meta"))
    diagnostics = _record(development_output.get("diagnostics"))
    markdown = _text(development_output.get("markdown"), "")
    if not markdown:
        markdown = _build_development_fallback_markdown(result=result, report_briefing=report_briefing)
    query = _text(result.get("query"), "No original request.")
    generated_at = _text(meta.get("generated_at") or result.get("updated_at"), "")
    backtest_summary = _build_development_backtest_summary(backtest_payload)
    diagnostics_rows = "".join(
        f"<tr><th>{_esc(label)}</th><td>{_esc(value)}</td></tr>"
        for label, value in _development_diagnostic_rows(diagnostics)
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Agentic Research Development Report</title>
  <style>
    @page {{ size: A4; margin: 15mm 13mm 17mm; }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: #f4f7fb;
      color: #172033;
      font-family: "Aptos", "Segoe UI", "Noto Sans", sans-serif;
      font-size: 12px;
      line-height: 1.58;
    }}
    .page {{ max-width: 980px; margin: 0 auto; padding: 26px 22px 40px; }}
    .hero {{
      color: #edf7ff;
      background: linear-gradient(135deg, #13233b 0%, #214b68 55%, #4c7f73 100%);
      border-radius: 26px;
      padding: 30px;
      margin-bottom: 18px;
    }}
    .eyebrow {{ margin: 0 0 9px; letter-spacing: .22em; text-transform: uppercase; font-size: 10px; opacity: .82; }}
    h1 {{ margin: 0; font-family: Georgia, "Times New Roman", serif; font-size: 30px; line-height: 1.08; }}
    h2 {{ margin: 20px 0 10px; font-family: Georgia, "Times New Roman", serif; font-size: 20px; color: #13233b; }}
    h3 {{ margin: 16px 0 8px; font-size: 15px; color: #13233b; }}
    .section {{
      background: #ffffff;
      border: 1px solid #d7e2ef;
      border-radius: 20px;
      padding: 18px;
      margin-bottom: 14px;
      break-inside: avoid;
    }}
    .question {{ padding: 13px 15px; background: #eef4fa; border-radius: 14px; font-size: 13px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ padding: 9px 8px; border-bottom: 1px solid #dbe6f2; text-align: left; vertical-align: top; }}
    th {{ color: #496071; text-transform: uppercase; letter-spacing: .08em; font-size: 10px; }}
    ul {{ margin: 8px 0 0; padding-left: 18px; }}
    li {{ margin: 4px 0; }}
    .markdown {{ white-space: normal; }}
    .markdown p {{ margin: 7px 0; }}
    .muted {{ color: #66758a; }}
  </style>
</head>
<body>
  <main class="page">
    <section class="hero">
      <p class="eyebrow">Development report PDF</p>
      <h1>Agentic Research Development Report</h1>
      <p>Run {_esc(run_id)} explains how agent workflow, RAG evidence, validation checks and backtest assumptions supported the final investment conclusion.</p>
      <p class="muted">{_esc(generated_at)}</p>
    </section>
    <section class="section">
      <h2>Original request</h2>
      <div class="question">{_esc(query)}</div>
    </section>
    <section class="section">
      <h2>Development diagnostics</h2>
      <table><tbody>{diagnostics_rows or '<tr><td>No diagnostics available.</td></tr>'}</tbody></table>
      {backtest_summary}
    </section>
    <section class="section markdown">
      {_markdown_to_html(markdown)}
    </section>
  </main>
</body>
</html>"""


def _build_development_fallback_markdown(*, result: dict[str, Any], report_briefing: dict[str, Any]) -> str:
    """旧 run 没有 development 输出时，生成一个不编造细节的兜底开发报告。"""
    meta = _record(report_briefing.get("meta"))
    evidence = _records(meta.get("retrieved_evidence"))
    checks = _records(meta.get("validation_checks"))
    agent_trace = _records(result.get("agent_trace"))
    lines = [
        "# Agentic Research Development Report",
        "",
        "## Run Overview",
        f"- Query: {_text(result.get('query'), 'No original request.')}",
        f"- Report mode: {_text(result.get('report_mode'), 'unknown')}",
        f"- Confidence: {_text(meta.get('confidence_level'), 'not rated')}",
        "",
        "## Agent Workflow",
    ]
    if agent_trace:
        lines.extend(f"- {_text(item.get('agent_name'), 'Agent')}: {_text(item.get('output_summary'), 'No summary.')}" for item in agent_trace)
    else:
        lines.append("- Agent trace is not available for this historical run.")
    lines.extend(
        [
            "",
            "## RAG Evidence Coverage",
            f"- Retrieved evidence items: {len(evidence)}",
            "",
            "## Validation Checks",
            f"- Validation check items: {len(checks)}",
            "",
            "## Known Limitations",
            "- This fallback report only summarizes available artifacts and does not invent missing engineering details.",
        ]
    )
    return "\n".join(lines)


def _build_development_backtest_summary(backtest: Any) -> str:
    """为开发 PDF 渲染可复现回测口径摘要。"""
    payload = _record(backtest)
    assumptions = _record(_record(payload.get("meta")).get("assumptions"))
    if not assumptions:
        return "<p class=\"muted\">Backtest assumptions are not available for this run.</p>"
    return (
        "<p class=\"muted\">Backtest assumptions: "
        f"cost {_esc(assumptions.get('transaction_cost_bps'))} bps, "
        f"slippage {_esc(assumptions.get('slippage_bps'))} bps, "
        f"dividend {_esc(assumptions.get('dividend_mode'))}, "
        f"rebalance {_esc(assumptions.get('rebalance'))}.</p>"
    )


def _development_diagnostic_rows(diagnostics: dict[str, Any]) -> list[tuple[str, Any]]:
    """统一开发报告诊断字段，优先读取新字段并兼容历史别名。"""
    return [
        ("Agent Count", diagnostics.get("agent_count")),
        ("Evidence Count", diagnostics.get("evidence_count", diagnostics.get("rag_evidence_count"))),
        ("Validation Check Count", diagnostics.get("validation_check_count", diagnostics.get("validation_warning_count"))),
        ("Backtest Status", diagnostics.get("backtest_status")),
    ]


def _build_investment_chart_block(charts: dict[str, Any], backtest: Any) -> str:
    """渲染投资报告固定四类图表区域。"""
    if not charts:
        charts = {}
    allocation = _build_bar_chart(
        title="Recommended Portfolio Allocation",
        chart=_record(charts.get("portfolio_allocation")),
        value_keys=("weight", "weight_pct", "allocation"),
        label_keys=("ticker", "name"),
        suffix="%",
    )
    scores = _build_bar_chart(
        title="Candidate Score Comparison",
        chart=_record(charts.get("candidate_score_comparison")),
        value_keys=("composite", "composite_score", "score"),
        label_keys=("ticker", "name"),
        suffix="",
    )
    backtest_chart = _build_backtest_chart_card(_record(charts.get("portfolio_vs_benchmark_backtest")), backtest)
    risk = _build_bar_chart(
        title="Risk Contribution",
        chart=_record(charts.get("risk_contribution")),
        value_keys=("value", "risk", "risk_score", "weight"),
        label_keys=("name", "category", "ticker"),
        suffix="%",
    )
    return f"""
    <section class="section">
      <h2>Report charts</h2>
      <div class="grid">{allocation}{scores}{backtest_chart}{risk}</div>
    </section>
    """


def _build_bar_chart(
    *,
    title: str,
    chart: dict[str, Any],
    value_keys: tuple[str, ...],
    label_keys: tuple[str, ...],
    suffix: str,
) -> str:
    """用 SVG 柱形图渲染简单图表，数据不足时明确说明。"""
    items = _records(chart.get("items"))
    if chart.get("status") == "missing" or not items:
        message = _text(chart.get("message"), "Data is insufficient; this chart was not generated.")
        return f"<div class=\"ticker-card\"><h3>{_esc(title)}</h3><p class=\"muted\">{_esc(message)}</p></div>"

    rows: list[tuple[str, float]] = []
    for item in items[:8]:
        label = next((_text(item.get(key), "") for key in label_keys if _text(item.get(key), "")), "Item")
        value = next((_float(item.get(key)) for key in value_keys if _float(item.get(key)) is not None), None)
        if value is not None:
            rows.append((label, value))
    if not rows:
        return f"<div class=\"ticker-card\"><h3>{_esc(title)}</h3><p class=\"muted\">Data is insufficient; this chart was not generated.</p></div>"
    max_value = max(max(value for _, value in rows), 1.0)
    bar_rows = []
    for index, (label, value) in enumerate(rows):
        y = 34 + index * 27
        width = max(8, (value / max_value) * 210)
        bar_rows.append(
            f'<text x="12" y="{y + 13}" fill="#4c596a" font-size="11">{_esc(label)}</text>'
            f'<rect x="115" y="{y}" width="{width:.1f}" height="16" rx="8" fill="#17645e" />'
            f'<text x="{125 + width:.1f}" y="{y + 13}" fill="#4c596a" font-size="11">{value:.1f}{_esc(suffix)}</text>'
        )
    height = 54 + len(rows) * 27
    return f"""
    <div class="ticker-card">
      <h3>{_esc(title)}</h3>
      <svg class="chart" viewBox="0 0 380 {height}" role="img" aria-label="{_esc(title)}">
        <rect x="0" y="0" width="380" height="{height}" rx="18" fill="#f0eadf" />
        {''.join(bar_rows)}
      </svg>
    </div>
    """


def _build_backtest_chart_card(chart: dict[str, Any], backtest: Any) -> str:
    """渲染组合 vs 基准回测图表卡。"""
    payload = _record(backtest)
    points = _records(payload.get("points")) or _records(chart.get("points"))
    svg = _build_backtest_svg(points)
    if not svg:
        if chart.get("status") == "missing":
            message = _text(chart.get("message"), "Backtest data is insufficient; this chart was not generated.")
            return f"<div class=\"ticker-card\"><h3>Portfolio vs Benchmark Backtest</h3><p class=\"muted\">{_esc(message)}</p></div>"
        return "<div class=\"ticker-card\"><h3>Portfolio vs Benchmark Backtest</h3><p class=\"muted\">Backtest data is insufficient; this chart was not generated.</p></div>"
    return f"<div class=\"ticker-card\"><h3>Portfolio vs Benchmark Backtest</h3>{svg}</div>"


def _markdown_to_html(markdown: str) -> str:
    """把报告 Markdown 转为 PDF 够用的轻量 HTML。"""
    rows = []
    in_list = False
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line:
            if in_list:
                rows.append("</ul>")
                in_list = False
            continue
        if line.startswith("### "):
            if in_list:
                rows.append("</ul>")
                in_list = False
            rows.append(f"<h3>{_esc(line[4:])}</h3>")
        elif line.startswith("## "):
            if in_list:
                rows.append("</ul>")
                in_list = False
            rows.append(f"<h2>{_esc(line[3:])}</h2>")
        elif line.startswith("# "):
            if in_list:
                rows.append("</ul>")
                in_list = False
            rows.append(f"<h2>{_esc(line[2:])}</h2>")
        elif line.startswith("- "):
            if not in_list:
                rows.append("<ul>")
                in_list = True
            rows.append(f"<li>{_esc(line[2:])}</li>")
        elif "|" in line and line.startswith("|"):
            if in_list:
                rows.append("</ul>")
                in_list = False
            rows.append(f"<p>{_esc(line)}</p>")
        else:
            if in_list:
                rows.append("</ul>")
                in_list = False
            rows.append(f"<p>{_esc(line)}</p>")
    if in_list:
        rows.append("</ul>")
    return "\n".join(rows)


def _float(value: Any) -> float | None:
    """安全转换浮点数。"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _plain(value: Any) -> Any:
    """把 Pydantic 对象转成普通 dict，便于模板统一读取。"""
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return value


def _record(value: Any) -> dict[str, Any]:
    """安全读取对象字典。"""
    value = _plain(value)
    return value if isinstance(value, dict) else {}


def _records(value: Any) -> list[dict[str, Any]]:
    """安全读取对象列表。"""
    value = _plain(value)
    if not isinstance(value, list):
        return []
    return [_record(item) for item in value if isinstance(_plain(item), dict)]


def _strings(value: Any) -> list[str]:
    """安全读取字符串列表。"""
    return [_text(item, "") for item in value] if isinstance(value, list) else []


def _text(value: Any, fallback: str = "") -> str:
    """把任意值转成干净文本。"""
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text else fallback


def _esc(value: Any) -> str:
    """HTML 转义，防止报告内容破坏模板。"""
    return html.escape(_text(value, ""), quote=True)


def _bullet_list(items: list[str]) -> str:
    """把文本数组渲染成列表。"""
    filtered = [item for item in items if item]
    if not filtered:
        return ""
    return "<ul>" + "".join(f"<li>{_esc(item)}</li>" for item in filtered) + "</ul>"


def _optional_line(label: str, value: Any) -> str:
    """有值时输出一行元信息。"""
    text = _text(value, "")
    return f"<p class=\"muted\"><strong>{_esc(label)}:</strong> {_esc(text)}</p>" if text else ""


def _build_ticker_card(item: dict[str, Any]) -> str:
    """渲染逐票研究卡。"""
    evidence = _bullet_list(_strings(item.get("evidence_points")))
    cautions = _bullet_list(_strings(item.get("caution_points")))
    return f"""
    <article class="ticker-card">
      <div class="ticker-head">
        <div>
          <p class="eyebrow">{_esc(item.get("ticker"))}</p>
          <h3>{_esc(item.get("company_name") or item.get("ticker"))}</h3>
        </div>
        <span class="badge">{_esc(item.get("verdict_label"))}</span>
      </div>
      <p><strong>Thesis:</strong> {_esc(item.get("thesis"))}</p>
      <p><strong>Fit reason:</strong> {_esc(item.get("fit_reason"))}</p>
      {evidence}
      {cautions}
      <p><strong>Execution:</strong> {_esc(item.get("execution"))}</p>
    </article>
    """


def _build_retrieved_evidence(items: list[dict[str, Any]]) -> str:
    """渲染 RAG 证据引用入口。"""
    if not items:
        return ""
    rows = []
    for item in items[:12]:
        title = _esc(item.get("title") or item.get("summary") or "Evidence")
        source = _esc(item.get("source_name") or item.get("source_type") or "Source")
        published = _esc(item.get("published_at") or item.get("as_of_date") or "")
        url = _text(item.get("url"), "")
        link = f'<a href="{_esc(url)}">{title}</a>' if url else title
        rows.append(f"<li>{link}<br><span class=\"muted\">{source}{' · ' + published if published else ''}</span></li>")
    return f"<section class=\"section\"><h2>Evidence sources</h2><ul>{''.join(rows)}</ul></section>"


def _build_backtest_block(backtest: Any) -> str:
    """渲染最近一次回测摘要和简图。"""
    payload = _record(backtest)
    summary = _record(payload.get("summary"))
    metrics = _record(summary.get("metrics"))
    if not summary or not metrics:
        return ""
    points = _records(payload.get("points"))
    assumptions = _record(_record(payload.get("meta")).get("assumptions"))
    chart = _build_backtest_svg(points)
    return f"""
    <section class="section">
      <h2>Backtest summary</h2>
      <div class="grid">
        <div>
          <p><strong>Portfolio return:</strong> {_esc(metrics.get("total_return_pct"))}%</p>
          <p><strong>Benchmark return:</strong> {_esc(metrics.get("benchmark_return_pct"))}%</p>
          <p><strong>Excess return:</strong> {_esc(metrics.get("excess_return_pct"))}%</p>
          <p><strong>Period:</strong> {_esc(summary.get("entry_date"))} to {_esc(summary.get("end_date"))}</p>
        </div>
        <div>
          <p><strong>Cost:</strong> {_esc(assumptions.get("transaction_cost_bps"))} bps</p>
          <p><strong>Slippage:</strong> {_esc(assumptions.get("slippage_bps"))} bps</p>
          <p><strong>Dividend:</strong> {_esc(assumptions.get("dividend_mode"))}</p>
          <p><strong>Rebalance:</strong> {_esc(assumptions.get("rebalance"))}</p>
        </div>
      </div>
      {chart}
    </section>
    """


def _build_backtest_svg(points: list[dict[str, Any]]) -> str:
    """用 SVG 画一张轻量回测曲线，方便 PDF 保留图表信息。"""
    if len(points) < 2:
        return ""
    values = [float(point.get("portfolio_value") or 0) for point in points if point.get("portfolio_value") is not None]
    bench = [float(point.get("benchmark_value") or 0) for point in points if point.get("benchmark_value") is not None]
    all_values = values + bench
    if not all_values:
        return ""
    min_value = min(all_values)
    max_value = max(all_values)
    spread = max(max_value - min_value, 1.0)

    def path_for(series: list[float]) -> str:
        coords = []
        count = max(len(series) - 1, 1)
        for index, value in enumerate(series):
            x = 40 + (index / count) * 520
            y = 170 - ((value - min_value) / spread) * 130
            coords.append(f"{x:.1f},{y:.1f}")
        return " ".join(coords)

    return f"""
    <svg class="chart" viewBox="0 0 620 220" role="img" aria-label="Backtest chart">
      <rect x="0" y="0" width="620" height="220" rx="18" fill="#f0eadf" />
      <line x1="40" y1="170" x2="580" y2="170" stroke="#b8ab98" />
      <line x1="40" y1="35" x2="40" y2="170" stroke="#b8ab98" />
      <polyline points="{path_for(values)}" fill="none" stroke="#17645e" stroke-width="4" />
      <polyline points="{path_for(bench)}" fill="none" stroke="#a05d25" stroke-width="3" stroke-dasharray="8 6" />
      <text x="42" y="204" fill="#637083" font-size="12">Portfolio</text>
      <line x1="110" y1="200" x2="150" y2="200" stroke="#17645e" stroke-width="4" />
      <text x="170" y="204" fill="#637083" font-size="12">Benchmark</text>
      <line x1="250" y1="200" x2="290" y2="200" stroke="#a05d25" stroke-width="3" stroke-dasharray="8 6" />
    </svg>
    """
