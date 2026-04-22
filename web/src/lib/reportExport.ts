/** 报告导出：保证导出内容与页面看到的结论、依据和回测尽量一致。 */
import { repairText } from "./format";
import { getClientId } from "./clientIdentity";
import type { BacktestDetail, Locale } from "./types";

type GenericRecord = Record<string, unknown>;
export type ReportExportFormat = "markdown" | "html" | "json" | "pdf";

function asRecord(value: unknown): GenericRecord | null {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as GenericRecord) : null;
}

function asArray(value: unknown): GenericRecord[] {
  return Array.isArray(value) ? (value.filter((item) => item && typeof item === "object") as GenericRecord[]) : [];
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => repairText(item, "")).filter(Boolean) : [];
}

function asRecordArray(value: unknown): GenericRecord[] {
  return Array.isArray(value) ? value.filter((item) => item && typeof item === "object") as GenericRecord[] : [];
}

function escapeHtml(value: unknown): string {
  return repairText(value, "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function slugify(value: string): string {
  return (
    repairText(value, "report")
      .toLowerCase()
      .replace(/[^a-z0-9\u4e00-\u9fff]+/gi, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 64) || "report"
  );
}

function timestampStamp(): string {
  return new Date().toISOString().replace(/[:.]/g, "-");
}

function downloadBlob(filename: string, content: string, mime: string) {
  const blob = new Blob([content], { type: mime });
  downloadBlobObject(filename, blob);
}

function downloadBlobObject(filename: string, blob: Blob) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function filenameFromDisposition(header: string | null, fallback: string): string {
  if (!header) return fallback;
  const match = /filename="([^"]+)"/i.exec(header) || /filename=([^;]+)/i.exec(header);
  return match?.[1]?.trim() || fallback;
}

async function downloadPdfFromBackend(runId: string, fallbackName: string) {
  const clientId = getClientId();
  const response = await fetch(`/api/v1/runs/${encodeURIComponent(runId)}/export/pdf`, {
    headers: {
      ...(clientId ? { "X-Client-Id": clientId } : {}),
    },
  });
  if (!response.ok) {
    let detail = response.statusText || "PDF export failed";
    try {
      const body = await response.json();
      detail = typeof body.detail === "string" ? body.detail : detail;
    } catch {
      const text = await response.text();
      detail = text || detail;
    }
    throw new Error(detail);
  }
  const blob = await response.blob();
  const filename = filenameFromDisposition(response.headers.get("Content-Disposition"), `${fallbackName}.pdf`);
  downloadBlobObject(filename, blob);
}

function buildBulletLines(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => repairText(item, "")).filter(Boolean) : [];
}

function buildBacktestSummary(backtest: BacktestDetail | null | undefined, locale: Locale): string[] {
  if (!backtest?.summary?.metrics) return [];
  const metrics = backtest.summary.metrics;
  return [
    locale === "zh" ? "## 回测摘要" : "## Backtest summary",
    `- ${locale === "zh" ? "组合收益" : "Portfolio return"}: ${repairText(metrics.total_return_pct)}%`,
    `- ${locale === "zh" ? "SPY 基准" : "SPY benchmark"}: ${repairText(metrics.benchmark_return_pct)}%`,
    `- ${locale === "zh" ? "超额收益" : "Excess return"}: ${repairText(metrics.excess_return_pct)}%`,
    `- ${locale === "zh" ? "买入日" : "Entry date"}: ${repairText(backtest.summary.entry_date)}`,
    `- ${locale === "zh" ? "结束日" : "End date"}: ${repairText(backtest.summary.end_date)}`,
    "",
  ];
}

function buildReportMarkdown(result: Record<string, unknown>, locale: Locale, backtest?: BacktestDetail | null): string {
  const finalReport = repairText(result.final_report, "");
  const reportBriefing = asRecord(result.report_briefing);
  const meta = asRecord(reportBriefing?.meta);
  const executive = asRecord(reportBriefing?.executive);
  const macro = asRecord(reportBriefing?.macro);
  const scoreboard = asArray(reportBriefing?.scoreboard);
  const researchContext = asRecord(result.research_context);
  const userProfile = asRecord(meta?.user_profile);
  const evidenceSummary = asRecord(meta?.evidence_summary);
  const validationSummary = asRecord(meta?.validation_summary);
  const safetySummary = asRecord(meta?.safety_summary);
  const memorySummary = asRecord(result.memory_summary);
  const confidenceLevel = repairText(meta?.confidence_level, "");
  const coverageFlags = asStringArray(meta?.coverage_flags);
  const memoryAppliedFields = asStringArray(result.memory_applied_fields);
  const queryText = repairText(result.query, locale === "zh" ? "暂无原始问题。" : "No original request.");

  const lines = [
    `# ${repairText(meta?.title, locale === "zh" ? "投资研究报告" : "Investment Research Report")}`,
    "",
    `## ${locale === "zh" ? "原始投资问题" : "Original request"}`,
    `- ${queryText}`,
    `- ${locale === "zh" ? "研究模式" : "Research mode"}: ${
      repairText(researchContext?.research_mode, "realtime") === "historical"
        ? locale === "zh"
          ? "历史研究"
          : "Historical research"
        : locale === "zh"
          ? "实时研究"
          : "Realtime research"
    }`,
    ...(repairText(researchContext?.as_of_date, "") ? [`- as_of_date: ${repairText(researchContext?.as_of_date)}`] : []),
    "",
    `## ${locale === "zh" ? "本次任务理解" : "Mandate understanding"}`,
    `- ${repairText(userProfile?.summary, locale === "zh" ? "暂无用户画像。" : "No mandate summary yet.")}`,
    ...(repairText(memorySummary?.note, "") ? [`- ${repairText(memorySummary?.note)}`] : []),
    "",
    `## ${locale === "zh" ? "执行结论" : "Executive verdict"}`,
    `- ${repairText(executive?.display_call || executive?.primary_call, locale === "zh" ? "暂无结论" : "No verdict yet")}`,
    `- ${repairText(executive?.display_action_summary || executive?.action_summary, "")}`,
    "",
    `## ${locale === "zh" ? "结论依据" : "Decision evidence"}`,
    `- ${repairText(evidenceSummary?.headline, locale === "zh" ? "暂无依据摘要。" : "No evidence summary yet.")}`,
    ...buildBulletLines(evidenceSummary?.items).map((item) => `- ${item}`),
    ...buildBulletLines(evidenceSummary?.source_points).map((item) => `- ${item}`),
    "",
    `## ${locale === "zh" ? "校验与谨慎提示" : "Validation & caveats"}`,
    `- ${repairText(validationSummary?.headline, locale === "zh" ? "暂无校验摘要。" : "No validation summary yet.")}`,
    ...buildBulletLines(validationSummary?.items).map((item) => `- ${item}`),
    ...(confidenceLevel ? [`- ${locale === "zh" ? "可信度等级" : "Confidence level"}: ${confidenceLevel}`] : []),
    "",
    `## ${locale === "zh" ? "安全与数据覆盖" : "Safety & data coverage"}`,
    `- ${repairText(safetySummary?.headline, locale === "zh" ? "暂无安全摘要。" : "No safety summary yet.")}`,
    ...buildBulletLines(safetySummary?.used_sources).map((item) => `- ${item}`),
    ...buildBulletLines(safetySummary?.degraded_modules).map((item) => `- ${item}`),
    ...coverageFlags.map((item) => `- ${item}`),
    ...(memoryAppliedFields.length
      ? [
          "",
          `## ${locale === "zh" ? "本次沿用的偏好" : "Reused preferences"}`,
          ...memoryAppliedFields.map((item) => `- ${item}`),
        ]
      : []),
    "",
    `## ${locale === "zh" ? "市场环境" : "Market regime"}`,
    `- ${repairText(macro?.risk_headline, locale === "zh" ? "暂无宏观摘要" : "No macro summary")}`,
    "",
    `## ${locale === "zh" ? "候选池" : "Scoreboard"}`,
    `| Ticker | ${locale === "zh" ? "综合评分" : "Composite"} | ${locale === "zh" ? "结论" : "Verdict"} |`,
    "| --- | --- | --- |",
  ];

  for (const item of scoreboard) {
    lines.push(`| ${repairText(item.ticker)} | ${repairText(item.composite_score)} | ${repairText(item.verdict_label)} |`);
  }

  lines.push("", ...buildBacktestSummary(backtest, locale));

  if (finalReport) {
    lines.push(locale === "zh" ? "## 完整报告正文" : "## Full memo", "", finalReport);
  }

  return lines.join("\n");
}

function buildReportHtml(result: Record<string, unknown>, locale: Locale, backtest?: BacktestDetail | null): string {
  const reportBriefing = asRecord(result.report_briefing);
  const meta = asRecord(reportBriefing?.meta);
  const executive = asRecord(reportBriefing?.executive);
  const macro = asRecord(reportBriefing?.macro);
  const scoreboard = asArray(reportBriefing?.scoreboard);
  const tickerCards = asArray(reportBriefing?.ticker_cards);
  const riskRegister = asArray(reportBriefing?.risk_register);
  const researchContext = asRecord(result.research_context);
  const assumptions = asStringArray(meta?.assumptions);
  const userProfile = asRecord(meta?.user_profile);
  const evidenceSummary = asRecord(meta?.evidence_summary);
  const validationSummary = asRecord(meta?.validation_summary);
  const safetySummary = asRecord(meta?.safety_summary);
  const memorySummary = asRecord(result.memory_summary);
  const confidenceLevel = repairText(meta?.confidence_level, "");
  const coverageFlags = asStringArray(meta?.coverage_flags);
  const memoryAppliedFields = asStringArray(result.memory_applied_fields);
  const finalReport = repairText(result.final_report, "");
  const queryText = repairText(result.query, locale === "zh" ? "暂无原始问题。" : "No original request.");

  const scoreboardRows = scoreboard
    .map(
      (item) => `
        <tr>
          <td>${escapeHtml(item.ticker)}</td>
          <td>${escapeHtml(item.company_name)}</td>
          <td>${escapeHtml(item.latest_price)}</td>
          <td>${escapeHtml(item.composite_score)}</td>
          <td>${escapeHtml(item.verdict_label)}</td>
        </tr>`,
    )
    .join("");

  const cardBlocks = tickerCards
    .map(
      (item) => {
        const newsLinks = asRecordArray(item.news_items)
          .slice(0, 3)
          .map((entry) => {
            const title = escapeHtml(entry.title || "News");
            const url = repairText(entry.url, "");
            if (!url) return `<li>${title}</li>`;
            return `<li><a href="${escapeHtml(url)}" target="_blank" rel="noreferrer">${title}</a></li>`;
          })
          .join("");
        const filingLinks = asRecordArray(item.audit_links)
          .slice(0, 3)
          .map((entry) => {
            const label = `${escapeHtml(entry.form || "SEC")}${entry.filed_at ? ` (${escapeHtml(entry.filed_at)})` : ""}`;
            const url = repairText(entry.filing_url, "");
            if (!url) return `<li>${label}</li>`;
            return `<li><a href="${escapeHtml(url)}" target="_blank" rel="noreferrer">${label}</a></li>`;
          })
          .join("");
        return `
        <article class="ticker-card">
          <div class="ticker-head">
            <div>
              <p class="ticker">${escapeHtml(item.ticker)}</p>
              <h3>${escapeHtml(item.company_name || item.ticker)}</h3>
            </div>
            <span class="verdict">${escapeHtml(item.verdict_label)}</span>
          </div>
          <p><strong>${locale === "zh" ? "投资主线" : "Thesis"}:</strong> ${escapeHtml(item.thesis)}</p>
          <p><strong>${locale === "zh" ? "适配原因" : "Fit reason"}:</strong> ${escapeHtml(item.fit_reason)}</p>
          ${buildBulletLines(item.evidence_points).length ? `<p><strong>${locale === "zh" ? "依据摘要" : "Evidence summary"}:</strong></p><ul>${buildBulletLines(item.evidence_points).map((point) => `<li>${escapeHtml(point)}</li>`).join("")}</ul>` : ""}
          ${buildBulletLines(item.caution_points).length ? `<p><strong>${locale === "zh" ? "谨慎提示" : "Caveats"}:</strong></p><ul>${buildBulletLines(item.caution_points).map((point) => `<li>${escapeHtml(point)}</li>`).join("")}</ul>` : ""}
          ${item.share_class ? `<p><strong>${locale === "zh" ? "股权类别" : "Share class"}:</strong> ${escapeHtml(item.share_class)}${item.share_class_note ? ` · ${escapeHtml(item.share_class_note)}` : ""}</p>` : ""}
          <p><strong>${locale === "zh" ? "技术面" : "Technical"}:</strong> ${escapeHtml(item.technical_summary)}</p>
          <p><strong>${locale === "zh" ? "新闻面" : "News"}:</strong> ${escapeHtml(item.news_narrative || item.news_label)}${item.alignment ? ` · ${escapeHtml(item.alignment)}` : ""}</p>
          <p><strong>${locale === "zh" ? "审计" : "Audit"}:</strong> ${escapeHtml(item.audit_summary)}</p>
          ${newsLinks ? `<p><strong>${locale === "zh" ? "新闻链接" : "News links"}:</strong></p><ul>${newsLinks}</ul>` : ""}
          ${filingLinks ? `<p><strong>${locale === "zh" ? "审计披露链接" : "Audit filing links"}:</strong></p><ul>${filingLinks}</ul>` : ""}
          <p><strong>${locale === "zh" ? "执行建议" : "Execution"}:</strong> ${escapeHtml(item.execution)}</p>
        </article>`;
      },
    )
    .join("");

  const riskItems = riskRegister
    .map((item) => `<li><strong>${escapeHtml(item.category)}${item.ticker ? ` / ${escapeHtml(item.ticker)}` : ""}</strong>: ${escapeHtml(item.summary)}</li>`)
    .join("");
  const evidenceItems = buildBulletLines(evidenceSummary?.items).map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  const evidenceSources = buildBulletLines(evidenceSummary?.source_points).map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  const validationItems = buildBulletLines(validationSummary?.items).map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  const safetySources = buildBulletLines(safetySummary?.used_sources).map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  const safetyDegraded = buildBulletLines(safetySummary?.degraded_modules).map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  const backtestMetrics = backtest?.summary?.metrics;

  return `<!doctype html>
<html lang="${locale}">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>${escapeHtml(meta?.title || "Investment Report")}</title>
  <style>
    @page { size: A4; margin: 16mm; }
    body { font-family: "Aptos", "Segoe UI", sans-serif; margin: 0; color: #10233b; background: #f4f7fb; }
    .page { max-width: 1100px; margin: 0 auto; padding: 32px 28px 48px; }
    .hero, .section, .ticker-card { background: #fff; border: 1px solid #d8e2ee; border-radius: 22px; box-shadow: 0 12px 28px rgba(15,23,42,.06); }
    .hero { padding: 28px; margin-bottom: 20px; }
    .hero h1, .section h2, .ticker-card h3 { margin: 0; font-family: Cambria, Georgia, serif; }
    .hero p { line-height: 1.7; }
    .grid { display: grid; grid-template-columns: 1.1fr .9fr; gap: 18px; margin-bottom: 18px; }
    .section { padding: 22px; margin-bottom: 18px; }
    .pill-row { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 14px; }
    .pill { padding: 7px 12px; border-radius: 999px; background: #e8f3f0; color: #0f766e; font-size: 12px; }
    table { width: 100%; border-collapse: collapse; margin-top: 12px; }
    th, td { padding: 12px 10px; border-bottom: 1px solid #dfe7f1; text-align: left; }
    th { font-size: 12px; letter-spacing: .08em; text-transform: uppercase; color: #5d7187; }
    .cards { display: grid; gap: 16px; }
    .ticker-card { padding: 18px; }
    .ticker-head { display: flex; justify-content: space-between; gap: 16px; align-items: start; }
    .ticker { margin: 0 0 4px; font-size: 12px; letter-spacing: .18em; text-transform: uppercase; color: #5d7187; }
    .verdict { padding: 8px 12px; border-radius: 999px; background: #eef4ff; color: #205ea8; font-size: 12px; }
    ul { margin: 10px 0 0; padding-left: 20px; line-height: 1.7; }
    @media print { body { background: #fff; } .page { padding: 0; } .hero, .section, .ticker-card { box-shadow: none; } }
  </style>
</head>
<body>
  <div class="page">
    <section class="hero">
      <p>${escapeHtml(meta?.subtitle || "")}</p>
      <h1>${escapeHtml(meta?.title || (locale === "zh" ? "投资研究报告" : "Investment Research Report"))}</h1>
      <p>${escapeHtml(executive?.display_call || executive?.primary_call)}</p>
      <div class="pill-row">
        <span class="pill">Top Pick: ${escapeHtml(executive?.top_pick)}</span>
        <span class="pill">${locale === "zh" ? "市场姿态" : "Market Stance"}: ${escapeHtml(executive?.market_stance)}</span>
        <span class="pill">${locale === "zh" ? "适配度" : "Mandate Fit"}: ${escapeHtml(executive?.mandate_fit_score)}</span>
      </div>
      ${assumptions.length ? `<p><strong>${locale === "zh" ? "默认假设" : "Assumptions"}:</strong> ${escapeHtml(assumptions.join(locale === "zh" ? "；" : "; "))}</p>` : ""}
      ${repairText(memorySummary?.note, "") ? `<p><strong>${locale === "zh" ? "记忆沿用" : "Memory reuse"}:</strong> ${escapeHtml(memorySummary?.note)}</p>` : ""}
    </section>
    <section class="section">
      <h2>${locale === "zh" ? "原始投资问题" : "Original request"}</h2>
      <p>${escapeHtml(queryText)}</p>
      <p>
        <strong>${locale === "zh" ? "研究模式" : "Research mode"}:</strong>
        ${escapeHtml(
          repairText(researchContext?.research_mode, "realtime") === "historical"
            ? locale === "zh"
              ? "历史研究"
              : "Historical research"
            : locale === "zh"
              ? "实时研究"
              : "Realtime research",
        )}
        ${repairText(researchContext?.as_of_date, "") ? ` | as_of_date: ${escapeHtml(repairText(researchContext?.as_of_date))}` : ""}
      </p>
    </section>
    <div class="grid">
      <section class="section">
        <h2>${locale === "zh" ? "本次任务理解" : "Mandate understanding"}</h2>
        <p>${escapeHtml(userProfile?.summary || "")}</p>
      </section>
      <section class="section">
        <h2>${locale === "zh" ? "执行摘要" : "Execution Summary"}</h2>
        <p>${escapeHtml(executive?.display_action_summary || executive?.action_summary)}</p>
      </section>
    </div>
    <div class="grid">
      <section class="section">
        <h2>${locale === "zh" ? "结论依据" : "Decision evidence"}</h2>
        <p>${escapeHtml(evidenceSummary?.headline || "")}</p>
        ${evidenceItems ? `<ul>${evidenceItems}</ul>` : ""}
        ${evidenceSources ? `<ul>${evidenceSources}</ul>` : ""}
      </section>
    <section class="section">
      <h2>${locale === "zh" ? "校验与谨慎提示" : "Validation & caveats"}</h2>
      <p>${escapeHtml(validationSummary?.headline || "")}</p>
      ${validationItems ? `<ul>${validationItems}</ul>` : ""}
      ${confidenceLevel ? `<p><strong>${locale === "zh" ? "可信度等级" : "Confidence level"}:</strong> ${escapeHtml(confidenceLevel)}</p>` : ""}
    </section>
  </div>
  <div class="grid">
    <section class="section">
      <h2>${locale === "zh" ? "市场环境" : "Market Regime"}</h2>
        <p>${escapeHtml(macro?.risk_headline)}</p>
        <p>Regime: ${escapeHtml(macro?.regime)} | VIX: ${escapeHtml(macro?.vix)}</p>
      </section>
      <section class="section">
      <h2>${locale === "zh" ? "安全与数据覆盖" : "Safety & data coverage"}</h2>
      <p>${escapeHtml(safetySummary?.headline || "")}</p>
      ${safetySources ? `<ul>${safetySources}</ul>` : ""}
      ${safetyDegraded ? `<ul>${safetyDegraded}</ul>` : ""}
      ${coverageFlags.length ? `<ul>${coverageFlags.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : ""}
      ${memoryAppliedFields.length ? `<p><strong>${locale === "zh" ? "本次沿用的偏好" : "Reused preferences"}:</strong> ${escapeHtml(memoryAppliedFields.join(locale === "zh" ? "、" : ", "))}</p>` : ""}
    </section>
  </div>
    <section class="section">
      <h2>${locale === "zh" ? "候选池评分板" : "Candidate Scoreboard"}</h2>
      <table>
        <thead><tr><th>Ticker</th><th>${locale === "zh" ? "公司" : "Company"}</th><th>${locale === "zh" ? "现价" : "Price"}</th><th>${locale === "zh" ? "综合评分" : "Composite"}</th><th>${locale === "zh" ? "结论" : "Verdict"}</th></tr></thead>
        <tbody>${scoreboardRows}</tbody>
      </table>
    </section>
    <section class="section">
      <h2>${locale === "zh" ? "逐票研究卡" : "Ticker Research Cards"}</h2>
      <div class="cards">${cardBlocks}</div>
    </section>
    <section class="section">
      <h2>${locale === "zh" ? "风险登记" : "Risk Register"}</h2>
      <ul>${riskItems}</ul>
    </section>
    ${backtest && backtestMetrics ? `
    <section class="section">
      <h2>${locale === "zh" ? "回测摘要" : "Backtest summary"}</h2>
      <p>${locale === "zh" ? "组合收益" : "Portfolio return"}: ${escapeHtml(backtestMetrics.total_return_pct)}%</p>
      <p>${locale === "zh" ? "SPY 基准" : "SPY benchmark"}: ${escapeHtml(backtestMetrics.benchmark_return_pct)}%</p>
      <p>${locale === "zh" ? "超额收益" : "Excess return"}: ${escapeHtml(backtestMetrics.excess_return_pct)}%</p>
      <p>${locale === "zh" ? "区间" : "Period"}: ${escapeHtml(backtest.summary.entry_date)} → ${escapeHtml(backtest.summary.end_date)}</p>
    </section>` : ""}
    ${finalReport ? `
    <section class="section">
      <h2>${locale === "zh" ? "完整报告正文" : "Full memo"}</h2>
      <pre style="white-space:pre-wrap;font-family:inherit;line-height:1.8;">${escapeHtml(finalReport)}</pre>
    </section>` : ""}
  </div>
</body>
</html>`;
}

export function exportReport(
  result: Record<string, unknown>,
  locale: Locale,
  format: ReportExportFormat,
  backtest?: BacktestDetail | null,
  runId?: string,
) {
  const reportBriefing = asRecord(result.report_briefing);
  const meta = asRecord(reportBriefing?.meta);
  const html = buildReportHtml(result, locale, backtest);
  const baseName = `${slugify(repairText(meta?.title, locale === "zh" ? "投资研究报告" : "investment-report"))}-${timestampStamp()}`;

  if (format === "markdown") {
    downloadBlob(`${baseName}.md`, buildReportMarkdown(result, locale, backtest), "text/markdown;charset=utf-8");
    return;
  }
  if (format === "html") {
    downloadBlob(`${baseName}.html`, html, "text/html;charset=utf-8");
    return;
  }
  if (format === "pdf") {
    if (!runId) {
      window.alert(locale === "zh" ? "当前报告缺少 run id，无法生成后端 PDF。" : "This report is missing a run id, so the backend PDF cannot be generated.");
      return;
    }
    void downloadPdfFromBackend(runId, baseName).catch((error) => {
      window.alert(error instanceof Error ? error.message : locale === "zh" ? "PDF 导出失败。" : "PDF export failed.");
    });
    return;
  }
  downloadBlob(
    `${baseName}.json`,
    JSON.stringify({ result, backtest: backtest || null }, null, 2),
    "application/json;charset=utf-8",
  );
}
