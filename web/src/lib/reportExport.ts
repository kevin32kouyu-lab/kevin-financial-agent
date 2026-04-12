import { repairText } from "./format";
import type { Locale } from "./types";

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
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function buildReportMarkdown(result: Record<string, unknown>, locale: Locale): string {
  const finalReport = repairText(result.final_report, "");
  if (finalReport) {
    return finalReport;
  }

  const reportBriefing = asRecord(result.report_briefing);
  const meta = asRecord(reportBriefing?.meta);
  const executive = asRecord(reportBriefing?.executive);
  const macro = asRecord(reportBriefing?.macro);
  const scoreboard = asArray(reportBriefing?.scoreboard);

  const lines = [
    `# ${repairText(meta?.title, locale === "zh" ? "投资研究报告" : "Investment Research Report")}`,
    "",
    `## ${locale === "zh" ? "执行结论" : "Executive verdict"}`,
    `- ${repairText(executive?.primary_call, locale === "zh" ? "暂无结论" : "No verdict yet")}`,
    `- ${repairText(executive?.action_summary, "")}`,
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

  return lines.join("\n");
}

function buildReportHtml(result: Record<string, unknown>, locale: Locale): string {
  const reportBriefing = asRecord(result.report_briefing);
  const meta = asRecord(reportBriefing?.meta);
  const executive = asRecord(reportBriefing?.executive);
  const macro = asRecord(reportBriefing?.macro);
  const scoreboard = asArray(reportBriefing?.scoreboard);
  const tickerCards = asArray(reportBriefing?.ticker_cards);
  const riskRegister = asArray(reportBriefing?.risk_register);
  const assumptions = asStringArray(meta?.assumptions);

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
      (item) => `
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
          <p><strong>${locale === "zh" ? "技术 / 新闻" : "Technical / News"}:</strong> ${escapeHtml(item.technical_summary)} / ${escapeHtml(item.news_label)} / ${escapeHtml(item.alignment)}</p>
          <p><strong>${locale === "zh" ? "审计" : "Audit"}:</strong> ${escapeHtml(item.audit_summary)}</p>
          <p><strong>${locale === "zh" ? "执行建议" : "Execution"}:</strong> ${escapeHtml(item.execution)}</p>
        </article>`,
    )
    .join("");

  const riskItems = riskRegister
    .map((item) => `<li><strong>${escapeHtml(item.category)}${item.ticker ? ` / ${escapeHtml(item.ticker)}` : ""}</strong>: ${escapeHtml(item.summary)}</li>`)
    .join("");

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
      <p>${escapeHtml(executive?.primary_call)}</p>
      <div class="pill-row">
        <span class="pill">Top Pick: ${escapeHtml(executive?.top_pick)}</span>
        <span class="pill">${locale === "zh" ? "市场姿态" : "Market Stance"}: ${escapeHtml(executive?.market_stance)}</span>
        <span class="pill">${locale === "zh" ? "适配度" : "Mandate Fit"}: ${escapeHtml(executive?.mandate_fit_score)}</span>
      </div>
      ${assumptions.length ? `<p><strong>${locale === "zh" ? "默认假设" : "Assumptions"}:</strong> ${escapeHtml(assumptions.join(locale === "zh" ? "；" : "; "))}</p>` : ""}
    </section>
    <div class="grid">
      <section class="section">
        <h2>${locale === "zh" ? "市场环境" : "Market Regime"}</h2>
        <p>${escapeHtml(macro?.risk_headline)}</p>
        <p>Regime: ${escapeHtml(macro?.regime)} | VIX: ${escapeHtml(macro?.vix)}</p>
      </section>
      <section class="section">
        <h2>${locale === "zh" ? "执行摘要" : "Execution Summary"}</h2>
        <p>${escapeHtml(executive?.action_summary)}</p>
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
  </div>
</body>
</html>`;
}

function openPrintPreview(filename: string, html: string) {
  const printWindow = window.open("", "_blank", "noopener,noreferrer");
  if (!printWindow) {
    downloadBlob(`${filename}.html`, html, "text/html;charset=utf-8");
    return;
  }

  const printableHtml = html.replace(
    "</body>",
    `<script>window.addEventListener("load", () => window.setTimeout(() => window.print(), 180));</script></body>`,
  );
  printWindow.document.open();
  printWindow.document.write(printableHtml);
  printWindow.document.close();
  printWindow.focus();
}

export function exportReport(result: Record<string, unknown>, locale: Locale, format: ReportExportFormat) {
  const reportBriefing = asRecord(result.report_briefing);
  const meta = asRecord(reportBriefing?.meta);
  const html = buildReportHtml(result, locale);
  const baseName = `${slugify(repairText(meta?.title, locale === "zh" ? "投资研究报告" : "investment-report"))}-${timestampStamp()}`;

  if (format === "markdown") {
    downloadBlob(`${baseName}.md`, buildReportMarkdown(result, locale), "text/markdown;charset=utf-8");
    return;
  }
  if (format === "html") {
    downloadBlob(`${baseName}.html`, html, "text/html;charset=utf-8");
    return;
  }
  if (format === "pdf") {
    openPrintPreview(baseName, html);
    return;
  }
  downloadBlob(`${baseName}.json`, JSON.stringify(result, null, 2), "application/json;charset=utf-8");
}
