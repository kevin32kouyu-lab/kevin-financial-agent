const elements = {
  modeButtons: Array.from(document.querySelectorAll(".mode-button")),
  structuredPanel: document.getElementById("structured-panel"),
  agentPanel: document.getElementById("agent-panel"),
  structuredForm: document.getElementById("structured-form"),
  agentForm: document.getElementById("agent-form"),
  structuredSampleButton: document.getElementById("fill-structured-sample"),
  agentSampleButton: document.getElementById("fill-agent-sample"),
  statusText: document.getElementById("status-text"),
  runSection: document.getElementById("run-section"),
  historySection: document.getElementById("history-section"),
  runtimeSection: document.getElementById("runtime-section"),
  intentSection: document.getElementById("intent-section"),
  artifactSection: document.getElementById("artifact-section"),
  stageSection: document.getElementById("stage-section"),
  followUpSection: document.getElementById("follow-up-section"),
  overviewSection: document.getElementById("overview-section"),
  macroSection: document.getElementById("macro-section"),
  reportSection: document.getElementById("report-section"),
  tickerSection: document.getElementById("ticker-section"),
  rawSection: document.getElementById("raw-section"),
};

const structuredButtons = [
  elements.structuredSampleButton,
  elements.structuredForm.querySelector("button[type='submit']"),
];

const agentButtons = [
  elements.agentSampleButton,
  elements.agentForm.querySelector("button[type='submit']"),
];

const resultSections = [
  elements.runSection,
  elements.runtimeSection,
  elements.intentSection,
  elements.artifactSection,
  elements.stageSection,
  elements.followUpSection,
  elements.overviewSection,
  elements.macroSection,
  elements.reportSection,
  elements.tickerSection,
  elements.rawSection,
];

const SAMPLE_AGENT_QUERY =
  "我有 50000 美元，想找适合长期持有的低风险分红股，最好估值不要太高，ROE 要比较稳，也希望自由现金流为正。";

const HISTORY_MODE_OPTIONS = [
  { value: "", label: "全部模式" },
  { value: "agent", label: "自然语言 Agent" },
  { value: "structured", label: "结构化分析" },
];

const HISTORY_STATUS_OPTIONS = [
  { value: "", label: "全部状态" },
  { value: "queued", label: "排队中" },
  { value: "running", label: "运行中" },
  { value: "completed", label: "已完成" },
  { value: "failed", label: "失败" },
  { value: "needs_clarification", label: "需补充信息" },
];

let currentMode = "structured";
let runtimeCache = null;
let activeRunId = null;
let activeRunMode = null;
let activeEventSource = null;
let currentRunDetail = null;
let currentArtifacts = [];
let currentRunHistory = [];
let selectedArtifactKey = null;
let selectedArtifactKind = "all";
let pendingRetryRunId = null;
let pendingOpenRunId = null;
let historyFilters = {
  search: "",
  mode: "",
  status: "",
};
let historyMutationPending = false;

const TERMINAL_RUN_STATUSES = new Set(["completed", "failed", "needs_clarification"]);

function splitValues(value, uppercase = false) {
  return String(value || "")
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => (uppercase ? item.toUpperCase() : item));
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatTimestamp(value) {
  if (!value) {
    return "N/A";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return String(value);
  }

  return parsed.toLocaleString("zh-CN", { hour12: false });
}

function formatRunMode(mode) {
  return mode === "agent" ? "自然语言 Agent" : "结构化分析";
}

function formatRunStatus(status) {
  const mapping = {
    queued: "排队中",
    running: "运行中",
    completed: "已完成",
    failed: "失败",
    needs_clarification: "需要补充信息",
  };
  return mapping[status] || status || "unknown";
}

function artifactKey(artifact) {
  return `${artifact?.kind || "unknown"}:${artifact?.name || "unknown"}`;
}

function buildOptionsMarkup(options, selectedValue) {
  return options
    .map(
      (option) => `
        <option value="${escapeHtml(option.value)}" ${option.value === selectedValue ? "selected" : ""}>
          ${escapeHtml(option.label)}
        </option>
      `,
    )
    .join("");
}

function normalizeHistoryFilters() {
  return {
    search: String(historyFilters.search || "").trim(),
    mode: String(historyFilters.mode || "").trim(),
    status: String(historyFilters.status || "").trim(),
  };
}

function buildHistoryQueryString(includeLimit = true) {
  const filters = normalizeHistoryFilters();
  const params = new URLSearchParams();

  if (includeLimit) {
    params.set("limit", "12");
  }
  if (filters.search) {
    params.set("search", filters.search);
  }
  if (filters.mode) {
    params.set("mode", filters.mode);
  }
  if (filters.status) {
    params.set("status", filters.status);
  }

  return params.toString();
}

function buildArtifactKindStats(rows) {
  const counts = new Map();
  rows.forEach((artifact) => {
    const kind = String(artifact?.kind || "unknown");
    counts.set(kind, (counts.get(kind) || 0) + 1);
  });

  return [
    { kind: "all", label: "全部", count: rows.length },
    ...Array.from(counts.entries()).map(([kind, count]) => ({
      kind,
      label: kind,
      count,
    })),
  ];
}

function getVisibleArtifacts(rows) {
  if (selectedArtifactKind === "all") {
    return rows;
  }
  return rows.filter((artifact) => String(artifact?.kind || "unknown") === selectedArtifactKind);
}

function getSectionElement(sectionKey) {
  const mapping = {
    run: elements.runSection,
    runtime: elements.runtimeSection,
    intent: elements.intentSection,
    artifacts: elements.artifactSection,
    stages: elements.stageSection,
    follow_up: elements.followUpSection,
    overview: elements.overviewSection,
    macro: elements.macroSection,
    report: elements.reportSection,
    tickers: elements.tickerSection,
    raw: elements.rawSection,
    history: elements.historySection,
  };
  return mapping[sectionKey] || null;
}

function focusSection(sectionKey) {
  const section = getSectionElement(sectionKey);
  if (!section || section.classList.contains("hidden")) {
    return;
  }

  section.scrollIntoView({ behavior: "smooth", block: "start" });
  section.classList.remove("section-focus");
  void section.offsetWidth;
  section.classList.add("section-focus");
  window.setTimeout(() => {
    section.classList.remove("section-focus");
  }, 1600);
}

function resolveArtifactLinks(artifact) {
  const kind = String(artifact?.kind || "").toLowerCase();
  const name = String(artifact?.name || "").toLowerCase();
  const links = [];

  if (kind === "input" && name === "request") {
    links.push({ key: "run", label: "看运行参数" });
    links.push({ key: "raw", label: "看原始 JSON" });
  }
  if (kind === "intent" || name.includes("intent")) {
    links.push({ key: "intent", label: "跳到意图解析" });
  }
  if (kind === "stage" || name.includes("stage")) {
    links.push({ key: "stages", label: "跳到阶段区" });
  }
  if (kind === "analysis" || name.includes("snapshot") || name === "current") {
    links.push({ key: "overview", label: "跳到分析概览" });
    links.push({ key: "tickers", label: "跳到股票卡片" });
  }
  if (kind === "report" || name.includes("report") || name === "final_response") {
    links.push({ key: "report", label: "跳到最终报告" });
  }
  if (name.includes("macro")) {
    links.push({ key: "macro", label: "跳到宏观区" });
  }
  if (name.includes("follow")) {
    links.push({ key: "follow_up", label: "跳到追问区" });
  }

  links.push({ key: "raw", label: "跳到原始 JSON" });

  const seen = new Set();
  return links.filter((link) => {
    if (seen.has(link.key)) {
      return false;
    }
    seen.add(link.key);
    return true;
  });
}

function hideSection(section) {
  section.classList.add("hidden");
  section.innerHTML = "";
}

function showSection(section, html) {
  if (!html) {
    hideSection(section);
    return;
  }
  section.classList.remove("hidden");
  section.innerHTML = html;
}

function clearResults() {
  resultSections.forEach(hideSection);
}

function setStatus(message) {
  elements.statusText.textContent = message;
}

function setLoadingState(mode, isLoading) {
  const targetButtons = mode === "structured" ? structuredButtons : agentButtons;
  [...elements.modeButtons, ...targetButtons].forEach((button) => {
    button.disabled = isLoading;
  });
}

function buildPill(label, value) {
  return `<div class="pill"><strong>${escapeHtml(label)}</strong><span>${escapeHtml(value)}</span></div>`;
}

function buildStatChip(value, label = "") {
  return `
    <div class="stat-chip">
      <strong>${escapeHtml(value)}</strong>
      ${label ? `<span>${escapeHtml(label)}</span>` : ""}
    </div>
  `;
}

function buildTagList(values, emptyText) {
  const items = Array.isArray(values) ? values.filter(Boolean) : [];
  if (!items.length) {
    return `<p class="mini-copy">${escapeHtml(emptyText)}</p>`;
  }
  return `
    <div class="tag-list">
      ${items.map((item) => `<span class="tag">${escapeHtml(item)}</span>`).join("")}
    </div>
  `;
}

function indexRows(rows) {
  const map = new Map();
  (Array.isArray(rows) ? rows : []).forEach((row) => {
    const key = String(row?.ticker || row?.Ticker || "").trim().toUpperCase();
    if (key) {
      map.set(key, row);
    }
  });
  return map;
}

function switchMode(mode) {
  currentMode = mode;
  elements.modeButtons.forEach((button) => {
    button.classList.toggle("active", button.dataset.mode === mode);
  });

  elements.structuredPanel.classList.toggle("hidden", mode !== "structured");
  elements.agentPanel.classList.toggle("hidden", mode !== "agent");
  clearResults();

  if (mode === "structured") {
    setStatus("结构化模式已就绪。适合验证筛选条件、接口格式和多源聚合结果。");
    return;
  }

  setStatus("自然语言 Agent 模式已就绪。你可以直接输入投资问题，系统会先做意图解析，再决定是否继续分析。");
  if (!runtimeCache) {
    loadRuntimeConfig();
    return;
  }
  renderRuntime(runtimeCache);
}

function buildStructuredPayload() {
  const maxPe = document.getElementById("max-pe").value.trim();
  const minRoePercent = document.getElementById("min-roe").value.trim();
  const minDividendYield = document.getElementById("min-dividend-yield").value.trim();

  return {
    risk_profile: {
      tolerance_level: document.getElementById("risk-level").value,
    },
    investment_strategy: {
      preferred_sectors: splitValues(document.getElementById("sectors").value),
      preferred_industries: splitValues(document.getElementById("industries").value),
    },
    fundamental_filters: {
      max_pe_ratio: maxPe ? Number(maxPe) : null,
      min_roe: minRoePercent ? Number(minRoePercent) / 100 : null,
      min_dividend_yield: minDividendYield ? Number(minDividendYield) / 100 : null,
      require_positive_fcf: document.getElementById("require-positive-fcf").checked,
      analyst_rating: document.getElementById("analyst-rating").value || null,
    },
    explicit_targets: {
      tickers: splitValues(document.getElementById("tickers").value, true),
    },
    options: {
      fetch_live_data: document.getElementById("fetch-live-data").checked,
      max_results: Number(document.getElementById("max-results").value || 5),
    },
  };
}

function buildAgentPayload() {
  return {
    query: document.getElementById("agent-query").value.trim(),
    options: {
      fetch_live_data: document.getElementById("agent-fetch-live-data").checked,
      max_results: Number(document.getElementById("agent-max-results").value || 5),
    },
  };
}

function buildRunCreatePayload(mode) {
  if (mode === "agent") {
    return {
      mode: "agent",
      agent: buildAgentPayload(),
    };
  }

  return {
    mode: "structured",
    structured: buildStructuredPayload(),
  };
}

function renderRunSummary(detail) {
  if (!detail?.run) {
    showSection(elements.runSection, "");
    return;
  }

  const run = detail.run;
  const statusClass = String(run.status || "unknown").replaceAll("-", "_");
  const retryDisabled =
    pendingRetryRunId === run.id || run.status === "queued" || run.status === "running";
  const retryLabel = pendingRetryRunId === run.id ? "正在重试..." : "重试这次运行";
  showSection(
    elements.runSection,
    `
      <div class="run-header">
        <div>
          <p class="eyebrow">Run</p>
          <h2>当前运行</h2>
        </div>
        <div class="run-actions">
          <span class="run-status-badge status-${escapeHtml(statusClass)}">${escapeHtml(formatRunStatus(run.status))}</span>
          <button
            type="button"
            class="ghost-button"
            data-action="retry-run"
            data-run-id="${escapeHtml(run.id)}"
            ${retryDisabled ? "disabled" : ""}
          >
            ${escapeHtml(retryLabel)}
          </button>
        </div>
      </div>
      <div class="run-meta-grid">
        <article class="meta-card">
          <span class="mini-label">Run ID</span>
          <strong>${escapeHtml(run.id)}</strong>
        </article>
        <article class="meta-card">
          <span class="mini-label">模式</span>
          <strong>${escapeHtml(formatRunMode(run.mode))}</strong>
        </article>
        <article class="meta-card">
          <span class="mini-label">创建时间</span>
          <strong>${escapeHtml(formatTimestamp(run.created_at))}</strong>
        </article>
        <article class="meta-card">
          <span class="mini-label">最近更新时间</span>
          <strong>${escapeHtml(formatTimestamp(run.updated_at))}</strong>
        </article>
      </div>
      ${
        run.error_message
          ? `<p class="mini-copy warning">错误信息：${escapeHtml(run.error_message)}</p>`
          : ""
      }
    `,
  );
}

function renderRunHistory(items) {
  const rows = Array.isArray(items) ? items : [];
  const filters = normalizeHistoryFilters();
  const subtitle = rows.length
    ? `当前显示 ${rows.length} 条记录`
    : filters.search || filters.mode || filters.status
      ? "当前筛选下没有记录"
      : "还没有历史 run";

  showSection(
    elements.historySection,
    `
      <div class="run-header">
        <div>
          <p class="eyebrow">Runs</p>
          <h2>最近运行</h2>
          <p class="mini-copy">${escapeHtml(subtitle)}</p>
        </div>
        <div class="run-actions">
          <button type="button" class="ghost-button" data-action="refresh-history">刷新列表</button>
          <button type="button" class="ghost-button" data-action="reset-history-filters">重置筛选</button>
          <button
            type="button"
            class="ghost-button danger-button"
            data-action="clear-history"
            ${historyMutationPending ? "disabled" : ""}
          >
            ${historyMutationPending ? "清理中..." : "清空当前筛选"}
          </button>
        </div>
      </div>
      <form id="history-filter-form" class="history-toolbar">
        <label class="history-search">
          <span class="mini-label">搜索</span>
          <input
            id="history-search"
            type="search"
            value="${escapeHtml(historyFilters.search)}"
            placeholder="按标题或 Run ID 搜索"
          >
        </label>
        <label>
          <span class="mini-label">模式</span>
          <select id="history-mode">
            ${buildOptionsMarkup(HISTORY_MODE_OPTIONS, historyFilters.mode)}
          </select>
        </label>
        <label>
          <span class="mini-label">状态</span>
          <select id="history-status">
            ${buildOptionsMarkup(HISTORY_STATUS_OPTIONS, historyFilters.status)}
          </select>
        </label>
        <button type="submit" class="ghost-button">应用筛选</button>
      </form>
      ${
        rows.length
          ? `
            <div class="history-list">
              ${rows
                .map(
                  (run) => {
                    const isOpening = pendingOpenRunId === run.id;
                    const isActive = run.id === activeRunId;
                    return `
                    <button
                      type="button"
                      class="history-item ${isActive ? "active" : ""} ${isOpening ? "pending" : ""}"
                      data-action="open-run"
                      data-run-id="${escapeHtml(run.id)}"
                      data-run-mode="${escapeHtml(run.mode)}"
                      ${isOpening ? "disabled" : ""}
                    >
                      <div class="history-item-head">
                        <p class="history-item-title">${escapeHtml(run.title || run.id)}</p>
                        <span class="run-status-badge status-${escapeHtml(String(run.status || "unknown").replaceAll("-", "_"))}">
                          ${escapeHtml(isOpening ? "正在打开" : formatRunStatus(run.status))}
                        </span>
                      </div>
                      <div class="history-item-meta">
                        <span>${escapeHtml(formatRunMode(run.mode))}</span>
                        <span>${escapeHtml(formatTimestamp(run.created_at))}</span>
                        ${
                          run.report_mode
                            ? `<span>报告: ${escapeHtml(run.report_mode)}</span>`
                            : ""
                        }
                      </div>
                    </button>
                  `;
                  },
                )
                .join("")}
            </div>
          `
          : `<p class="mini-copy history-empty">先运行一次结构化分析或自然语言 Agent，再回来查看这里的历史记录。</p>`
      }
    `,
  );
}

function renderRuntime(runtime) {
  if (!runtime) {
    showSection(elements.runtimeSection, "");
    return;
  }

  const apiStatus = runtime.api_key_configured ? "已检测到 API Key" : "未检测到 API Key";
  showSection(
    elements.runtimeSection,
    `
      <p class="eyebrow">LLM Runtime</p>
      <h2>后端模型环境</h2>
      <div class="overview-stats">
        ${buildPill("Provider", runtime.provider || "unknown")}
        ${buildPill("API Key", apiStatus)}
        ${buildPill("Model", runtime.model || "N/A")}
        ${buildPill("Route", runtime.route_mode || "unknown")}
        ${buildPill("Billing", runtime.billing_mode || "unknown")}
      </div>
      <p class="mini-copy">Base URL: ${escapeHtml(runtime.base_url || "N/A")}</p>
    `,
  );
}

function renderIntent(parsedIntent) {
  if (!parsedIntent) {
    showSection(elements.intentSection, "");
    return;
  }

  const agentControl = parsedIntent.agent_control || {};
  const investment = parsedIntent.investment_strategy || {};
  const filters = parsedIntent.fundamental_filters || {};
  const missingInfo = Array.isArray(agentControl.missing_critical_info)
    ? agentControl.missing_critical_info.join(", ")
    : "";

  showSection(
    elements.intentSection,
    `
      <p class="eyebrow">Intent</p>
      <h2>意图解析结果</h2>
      <div class="overview-stats">
        ${buildPill("Language", parsedIntent.system_context?.language || "N/A")}
        ${buildPill("Intent Clear", String(agentControl.is_intent_clear))}
        ${buildPill("Risk", parsedIntent.risk_profile?.tolerance_level || "N/A")}
        ${buildPill("Style", investment.style || "N/A")}
      </div>
      <p class="mini-copy">缺失关键信息: ${escapeHtml(missingInfo || "无")}</p>
      <p class="mini-copy">
        过滤条件:
        PE <= ${escapeHtml(filters.max_pe_ratio ?? "N/A")} |
        ROE >= ${escapeHtml(filters.min_roe ?? "N/A")} |
        Dividend >= ${escapeHtml(filters.min_dividend_yield ?? "N/A")}
      </p>
      <pre class="inline-json">${escapeHtml(JSON.stringify(parsedIntent, null, 2))}</pre>
    `,
  );
}

function flattenStages(data) {
  const topStages = Array.isArray(data.stages) ? data.stages : [];
  const nestedStages = Array.isArray(data.analysis?.debug_stages)
    ? data.analysis.debug_stages.map((stage) => ({
        ...stage,
        label: `分析 / ${stage.label || stage.key}`,
      }))
    : Array.isArray(data.debug_stages)
      ? data.debug_stages
      : [];

  return [...topStages, ...nestedStages];
}

function renderStages(data) {
  const stages = flattenStages(data);
  if (!stages.length) {
    showSection(elements.stageSection, "");
    return;
  }

  const stageHtml = stages
    .map(
      (stage) => `
        <article class="stage-card stage-${escapeHtml(stage.status || "unknown")}">
          <div class="stage-head">
            <strong>${escapeHtml(stage.label || stage.key || "stage")}</strong>
            <span class="stage-status">${escapeHtml(stage.status || "unknown")}</span>
          </div>
          <p class="mini-copy">${escapeHtml(stage.summary || "无摘要")}</p>
          <p class="stage-time">${escapeHtml(stage.elapsed_ms ?? "N/A")} ms</p>
        </article>
      `,
    )
    .join("");

  showSection(
    elements.stageSection,
    `
      <p class="eyebrow">Stages</p>
      <h2>执行阶段</h2>
      <div class="stage-grid">${stageHtml}</div>
    `,
  );
}

function renderFollowUp(text) {
  if (!text) {
    showSection(elements.followUpSection, "");
    return;
  }

  showSection(
    elements.followUpSection,
    `
      <p class="eyebrow">Follow Up</p>
      <h2>Agent 需要你补充的信息</h2>
      <div class="report-body">${escapeHtml(text)}</div>
    `,
  );
}

function renderOverview(analysis) {
  if (!analysis?.debug_summary) {
    showSection(elements.overviewSection, "");
    return;
  }

  const summary = analysis.debug_summary;
  const selectedTickers = Array.isArray(summary.selected_tickers) ? summary.selected_tickers.join(", ") : "";
  const liveStatus = summary.live_data_enabled ? "实时数据已开启" : "实时数据已关闭";

  showSection(
    elements.overviewSection,
    `
      <p class="eyebrow">Run Summary</p>
      <h2>本次分析概览</h2>
      <p class="overview-copy">${escapeHtml(analysis.analysis_context || "分析已完成。")}</p>
      <div class="overview-stats">
        ${buildStatChip(summary.selected_ticker_count ?? 0, "进入分析的股票")}
        ${buildStatChip(liveStatus)}
        ${buildStatChip(analysis.request_echo?.risk_profile?.tolerance_level || "N/A", "风险偏好")}
        ${summary.stage_count ? buildStatChip(summary.stage_count, "阶段") : ""}
      </div>
      ${selectedTickers ? `<p class="mini-copy">候选股票：${escapeHtml(selectedTickers)}</p>` : ""}
    `,
  );
}

function renderMacro(analysis) {
  const macro = analysis?.macro_data;
  if (!macro) {
    showSection(elements.macroSection, "");
    return;
  }

  const regime = macro.Global_Regime || macro.Status || "Unknown";
  const warning = macro.Systemic_Risk_Warning || "暂无宏观风险提示。";

  showSection(
    elements.macroSection,
    `
      <p class="eyebrow">Macro</p>
      <h2>宏观环境</h2>
      <div class="overview-stats">
        ${buildPill("Regime", regime)}
        ${buildPill("VIX", macro.VIX_Volatility_Index ?? "N/A")}
        ${buildPill("S&P 500", macro.SP500_Level ?? "N/A")}
        ${buildPill("US10Y", macro.US10Y_Treasury_Yield ?? "N/A")}
      </div>
      <p class="macro-copy">${escapeHtml(warning)}</p>
    `,
  );
}

function renderInlineMarkdown(value) {
  return escapeHtml(value ?? "")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, "<code>$1</code>");
}

function isMarkdownTableLine(line) {
  const trimmed = line.trim();
  return trimmed.startsWith("|") && trimmed.endsWith("|");
}

function isMarkdownTableSeparator(line) {
  return /^\|?(\s*:?-{3,}:?\s*\|)+\s*$/.test(line.trim());
}

function renderMarkdownTable(lines) {
  const rows = lines
    .filter((line) => !isMarkdownTableSeparator(line))
    .map((line) =>
      line
        .trim()
        .replace(/^\|/, "")
        .replace(/\|$/, "")
        .split("|")
        .map((cell) => renderInlineMarkdown(cell.trim())),
    )
    .filter((row) => row.length);

  if (!rows.length) {
    return "";
  }

  const [header, ...body] = rows;
  return `
    <div class="report-table-wrap">
      <table class="report-table">
        <thead>
          <tr>${header.map((cell) => `<th>${cell}</th>`).join("")}</tr>
        </thead>
        <tbody>
          ${body.map((row) => `<tr>${row.map((cell) => `<td>${cell}</td>`).join("")}</tr>`).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderMarkdownReport(markdown) {
  if (!markdown) {
    return "";
  }

  const lines = String(markdown).replace(/\r\n/g, "\n").split("\n");
  const blocks = [];

  for (let index = 0; index < lines.length; ) {
    const line = lines[index].trim();
    if (!line) {
      index += 1;
      continue;
    }

    if (isMarkdownTableLine(line)) {
      const tableLines = [];
      while (index < lines.length && isMarkdownTableLine(lines[index].trim())) {
        tableLines.push(lines[index]);
        index += 1;
      }
      blocks.push(renderMarkdownTable(tableLines));
      continue;
    }

    if (line.startsWith("### ")) {
      blocks.push(`<h4>${renderInlineMarkdown(line.slice(4))}</h4>`);
      index += 1;
      continue;
    }

    if (line.startsWith("## ")) {
      blocks.push(`<h3>${renderInlineMarkdown(line.slice(3))}</h3>`);
      index += 1;
      continue;
    }

    if (line.startsWith("# ")) {
      blocks.push(`<h2>${renderInlineMarkdown(line.slice(2))}</h2>`);
      index += 1;
      continue;
    }

    if (line.startsWith("- ")) {
      const items = [];
      while (index < lines.length && lines[index].trim().startsWith("- ")) {
        items.push(`<li>${renderInlineMarkdown(lines[index].trim().slice(2))}</li>`);
        index += 1;
      }
      blocks.push(`<ul>${items.join("")}</ul>`);
      continue;
    }

    const paragraphLines = [];
    while (index < lines.length) {
      const currentLine = lines[index].trim();
      if (!currentLine) {
        index += 1;
        break;
      }
      if (
        currentLine.startsWith("# ") ||
        currentLine.startsWith("## ") ||
        currentLine.startsWith("### ") ||
        currentLine.startsWith("- ") ||
        isMarkdownTableLine(currentLine)
      ) {
        break;
      }
      paragraphLines.push(currentLine);
      index += 1;
    }

    if (paragraphLines.length) {
      blocks.push(`<p>${renderInlineMarkdown(paragraphLines.join(" "))}</p>`);
    }
  }

  return blocks.join("");
}

function buildReportPreview(briefing) {
  if (!briefing) {
    return "";
  }

  const language = briefing?.meta?.language || "en";
  const macro = briefing?.macro || {};
  const priceAction = Array.isArray(briefing.price_action) ? briefing.price_action : [];
  const audits = Array.isArray(briefing.audit) ? briefing.audit : [];
  const technicalNews = Array.isArray(briefing.technical_news) ? briefing.technical_news : [];
  const verdicts = Array.isArray(briefing.verdicts) ? briefing.verdicts : [];
  const severeAudits = audits.filter((row) => row.severe_warning);

  const cards = [];

  cards.push(`
    <article class="preview-card">
      <p class="eyebrow">Macro</p>
      <h3>${language === "zh" ? "系统环境" : "System Regime"}</h3>
      <div class="preview-keyline">
        <strong>${escapeHtml(macro.regime || "N/A")}</strong>
        <span>${escapeHtml(macro.warning_text || "N/A")}</span>
      </div>
      <div class="mini-grid preview-mini-grid">
        <div class="mini-card">
          <p class="mini-label">VIX</p>
          <p class="mini-value">${escapeHtml(macro.vix ?? "N/A")}</p>
        </div>
        <div class="mini-card">
          <p class="mini-label">US10Y</p>
          <p class="mini-value">${escapeHtml(macro.us10y ?? "N/A")}</p>
        </div>
      </div>
    </article>
  `);

  if (priceAction.length) {
    cards.push(`
      <article class="preview-card">
        <p class="eyebrow">Price & Smart Money</p>
        <h3>${language === "zh" ? "核心对照表" : "Core Comparison"}</h3>
        <div class="report-table-wrap">
          <table class="report-table compact">
            <thead>
              <tr>
                <th>Ticker</th>
                <th>Latest Price</th>
                <th>Tech</th>
                <th>Smart Money</th>
              </tr>
            </thead>
            <tbody>
              ${priceAction
                .map(
                  (row) => `
                    <tr>
                      <td>${escapeHtml(row.ticker || "N/A")}</td>
                      <td>${escapeHtml(row.latest_price ?? "N/A")}</td>
                      <td>${escapeHtml(row.tech_sentiment || "N/A")}</td>
                      <td>${escapeHtml(row.smart_money_positioning || "N/A")}</td>
                    </tr>
                  `,
                )
                .join("")}
            </tbody>
          </table>
        </div>
      </article>
    `);
  }

  if (technicalNews.length) {
    cards.push(`
      <article class="preview-card preview-card-wide">
        <p class="eyebrow">Technical & News</p>
        <h3>${language === "zh" ? "技术面与新闻催化" : "Technical & Catalysts"}</h3>
        <div class="stack-list">
          ${technicalNews
            .map(
              (row) => `
                <div class="stack-item">
                  <div class="stack-head">
                    <strong>${escapeHtml(row.ticker || "N/A")}</strong>
                    <span>${escapeHtml(row.alignment || "N/A")}</span>
                  </div>
                  <p>${escapeHtml(row.tech_summary || "N/A")}</p>
                  <p class="mini-copy">
                    新闻情绪：${escapeHtml(row.news_label || "N/A")} |
                    分数：${escapeHtml(row.news_score ?? "N/A")}
                  </p>
                  ${buildTagList(row.catalysts || [], language === "zh" ? "暂无近期催化剂" : "No recent catalysts")}
                </div>
              `,
            )
            .join("")}
        </div>
      </article>
    `);
  }

  if (severeAudits.length) {
    cards.push(`
      <article class="preview-card audit-alert-card">
        <p class="eyebrow">Audit Alerts</p>
        <h3>${language === "zh" ? "审计 veto 风险" : "Audit Veto Risks"}</h3>
        <div class="verdict-grid">
          ${severeAudits
            .map(
              (row) => `
                <div class="verdict-card verdict-veto">
                  <strong>${escapeHtml(row.ticker || "N/A")}</strong>
                  <p>${escapeHtml(row.audit_text || "N/A")}</p>
                </div>
              `,
            )
            .join("")}
        </div>
      </article>
    `);
  }

  if (verdicts.length) {
    cards.push(`
      <article class="preview-card">
        <p class="eyebrow">PM Verdicts</p>
        <h3>${language === "zh" ? "最终结论" : "PM Verdicts"}</h3>
        <div class="verdict-grid">
          ${verdicts
            .map(
              (row) => `
                <div class="verdict-card ${row.veto ? "verdict-veto" : ""}">
                  <strong>${escapeHtml(row.ticker || "N/A")}</strong>
                  <span>${escapeHtml(row.verdict_label || "N/A")}</span>
                  <p>${escapeHtml(row.execution || row.rationale || "")}</p>
                </div>
              `,
            )
            .join("")}
        </div>
      </article>
    `);
  }

  return cards.length ? `<div class="report-preview-grid">${cards.join("")}</div>` : "";
}

function renderReport(report, briefing, reportMode, reportError) {
  if (!report) {
    showSection(elements.reportSection, "");
    return;
  }

  const meta = briefing?.meta || {};
  const macro = briefing?.macro || {};
  const language = meta.language || "en";
  const modeLabel =
    reportMode === "fallback"
      ? language === "zh"
        ? "本地规则报告"
        : "Fallback Report"
      : language === "zh"
        ? "LLM 研究报告"
        : "LLM Research Report";

  const warningBanner = macro.severe_warning
    ? `<div class="report-warning">${escapeHtml(macro.warning_text || "N/A")}</div>`
    : "";
  const debugNote =
    reportMode === "fallback" && reportError
      ? `<p class="mini-copy">LLM 报告阶段失败，当前展示本地备选报告。原因：${escapeHtml(reportError)}</p>`
      : "";

  showSection(
    elements.reportSection,
    `
      <p class="eyebrow">Report</p>
      <h2>最终报告</h2>
      <div class="report-meta">
        ${buildPill("Mode", modeLabel)}
        ${buildPill("Language", meta.language || "N/A")}
        ${buildPill("Tickers", meta.ticker_count ?? "N/A")}
      </div>
      ${warningBanner}
      ${debugNote}
      ${buildReportPreview(briefing)}
      <article class="report-shell">
        ${renderMarkdownReport(report)}
      </article>
    `,
  );
}

function buildNewsHtml(news) {
  if (!news.length) {
    return `<p class="mini-copy">暂无新闻，或者本次关闭了实时数据。</p>`;
  }

  return `
    <ul class="news-list">
      ${news
        .slice(0, 3)
        .map(
          (item) => `
            <li class="news-item">
              <a href="${escapeHtml(item.link || "#")}" target="_blank" rel="noreferrer">${escapeHtml(item.title || "Untitled news")}</a>
              <span>${escapeHtml(item.published_at || "No publish time")}</span>
            </li>
          `,
        )
        .join("")}
    </ul>
  `;
}

function renderTickerCards(analysis, briefing) {
  const snapshots = Array.isArray(analysis?.ticker_snapshots) ? analysis.ticker_snapshots : [];
  if (!analysis || !("ticker_snapshots" in analysis)) {
    showSection(elements.tickerSection, "");
    return;
  }

  const verdictMap = indexRows(briefing?.verdicts);
  const technicalNewsMap = indexRows(briefing?.technical_news);

  elements.tickerSection.classList.remove("hidden");

  if (!snapshots.length) {
    elements.tickerSection.innerHTML = `
      <article class="ticker-card">
        <p class="eyebrow">No Result</p>
        <h3>这次没有筛出股票</h3>
        <p class="mini-copy">你可以放宽 PE / ROE / 股息率条件，或者直接填入 ticker 测试后续链路。</p>
      </article>
    `;
    return;
  }

  elements.tickerSection.innerHTML = snapshots
    .map((snapshot) => {
      const tickerKey = String(snapshot.ticker || "").toUpperCase();
      const quant = snapshot.quant || {};
      const price = snapshot.price || {};
      const technical = snapshot.technical || {};
      const audit = snapshot.audit || {};
      const smart = snapshot.smart_money || {};
      const news = Array.isArray(snapshot.news) ? snapshot.news : [];
      const verdict = verdictMap.get(tickerKey) || {};
      const technicalNews = technicalNewsMap.get(tickerKey) || {};

      const verdictHtml = verdict.verdict_label
        ? `
          <div class="ticker-banner ${verdict.veto ? "ticker-banner-veto" : ""}">
            <div class="ticker-banner-head">
              <div>
                <p class="mini-label">Chief PM</p>
                <p class="ticker-verdict">${escapeHtml(verdict.verdict_label || "N/A")}</p>
              </div>
              <span class="ticker-alignment">${escapeHtml(technicalNews.alignment || "N/A")}</span>
            </div>
            <p class="mini-copy">${escapeHtml(verdict.execution || verdict.rationale || "")}</p>
          </div>
        `
        : "";

      return `
        <article class="ticker-card">
          ${verdictHtml}

          <div class="ticker-meta">
            <div>
              <p class="eyebrow">${escapeHtml(snapshot.sector || "Unknown sector")}</p>
              <h3>${escapeHtml(snapshot.ticker)}</h3>
              <p class="mini-copy">${escapeHtml(snapshot.company_name || "Unknown company")}</p>
            </div>
            <div class="score-badge">Score ${escapeHtml(quant.Total_Quant_Score ?? 0)}</div>
          </div>

          <div class="mini-grid">
            <div class="mini-card">
              <p class="mini-label">Price</p>
              <p class="mini-value">${escapeHtml(price.Latest_Price ?? price.Status ?? "N/A")}</p>
            </div>
            <div class="mini-card">
              <p class="mini-label">ROE</p>
              <p class="mini-value">${escapeHtml(quant.ROE ?? "N/A")}</p>
            </div>
            <div class="mini-card">
              <p class="mini-label">Dividend</p>
              <p class="mini-value">${escapeHtml(quant.Dividend_Yield ?? "N/A")}</p>
            </div>
            <div class="mini-card">
              <p class="mini-label">Analyst</p>
              <p class="mini-value">${escapeHtml(quant.Analyst_Rating ?? "N/A")}</p>
            </div>
            <div class="mini-card">
              <p class="mini-label">RSI</p>
              <p class="mini-value">${escapeHtml(technical.RSI_14 ?? technical.Status ?? "N/A")}</p>
            </div>
            <div class="mini-card">
              <p class="mini-label">Smart Money</p>
              <p class="mini-value">${escapeHtml(smart.Smart_Money_Signal ?? smart.Status ?? "N/A")}</p>
            </div>
          </div>

          <div>
            <p class="mini-label">审计结论</p>
            <p class="${audit.Overall_Risk_Level === "High Risk" ? "warning" : "success"}">
              ${escapeHtml(audit.Overall_Risk_Level ?? audit.Status ?? "N/A")}
            </p>
            <p class="mini-copy">
              D/E: ${escapeHtml(audit.Debt_to_Equity ?? "N/A")} |
              Current Ratio: ${escapeHtml(audit.Current_Ratio ?? "N/A")} |
              Retained Earnings(B): ${escapeHtml(audit.Retained_Earnings_B ?? "N/A")}
            </p>
          </div>

          <div>
            <p class="mini-label">技术 / 新闻</p>
            <p class="mini-copy">${escapeHtml(technicalNews.tech_summary || "N/A")}</p>
            <p class="mini-copy">
              一致性：${escapeHtml(technicalNews.alignment || "N/A")} |
              新闻：${escapeHtml(technicalNews.news_label || "N/A")}
            </p>
            ${buildTagList(technicalNews.catalysts || [], "暂无近期催化剂")}
          </div>

          <div>
            <p class="mini-label">近期新闻</p>
            ${buildNewsHtml(news)}
          </div>
        </article>
      `;
    })
    .join("");
}

function renderRawJson(data) {
  showSection(
    elements.rawSection,
    `
      <details open>
        <summary>查看原始 JSON</summary>
        <pre>${escapeHtml(JSON.stringify(data, null, 2))}</pre>
      </details>
    `,
  );
}

function renderArtifacts(artifacts) {
  const rows = Array.isArray(artifacts) ? artifacts : [];
  if (!rows.length) {
    showSection(elements.artifactSection, "");
    return;
  }

  const kindStats = buildArtifactKindStats(rows);
  if (!kindStats.some((item) => item.kind === selectedArtifactKind)) {
    selectedArtifactKind = "all";
  }

  const visibleRows = getVisibleArtifacts(rows);
  const selected =
    visibleRows.find((artifact) => artifactKey(artifact) === selectedArtifactKey) ||
    visibleRows[0];
  selectedArtifactKey = artifactKey(selected);

  const content =
    typeof selected.content === "string"
      ? selected.content
      : JSON.stringify(selected.content, null, 2);
  const quickLinks = resolveArtifactLinks(selected);

  showSection(
    elements.artifactSection,
    `
      <div class="artifact-header">
        <div>
          <p class="eyebrow">Artifacts</p>
          <h2>中间产物</h2>
        </div>
        <div class="artifact-actions">
          <span class="run-status-badge">${escapeHtml(`${visibleRows.length} / ${rows.length} 项`)}</span>
        </div>
      </div>
      <div class="artifact-kind-list">
        ${kindStats
          .map(
            (item) => `
              <button
                type="button"
                class="artifact-kind-chip ${item.kind === selectedArtifactKind ? "active" : ""}"
                data-action="filter-artifacts"
                data-artifact-kind="${escapeHtml(item.kind)}"
              >
                ${escapeHtml(`${item.label} · ${item.count}`)}
              </button>
            `,
          )
          .join("")}
      </div>
      <div class="artifact-layout">
        <div class="artifact-list">
          ${visibleRows
            .map(
              (artifact) => `
                <button
                  type="button"
                  class="artifact-item ${artifactKey(artifact) === selectedArtifactKey ? "active" : ""}"
                  data-action="select-artifact"
                  data-artifact-key="${escapeHtml(artifactKey(artifact))}"
                >
                  <strong>${escapeHtml(`${artifact.kind} / ${artifact.name}`)}</strong>
                  <span>${escapeHtml(formatTimestamp(artifact.updated_at))}</span>
                </button>
              `,
            )
            .join("")}
        </div>
        <div class="artifact-viewer">
          <div class="artifact-meta-grid">
            <article class="meta-card">
              <span class="mini-label">类型</span>
              <strong>${escapeHtml(selected.kind)}</strong>
            </article>
            <article class="meta-card">
              <span class="mini-label">名称</span>
              <strong>${escapeHtml(selected.name)}</strong>
            </article>
            <article class="meta-card">
              <span class="mini-label">更新时间</span>
              <strong>${escapeHtml(formatTimestamp(selected.updated_at))}</strong>
            </article>
          </div>
          <div class="artifact-link-list">
            ${quickLinks
              .map(
                (link) => `
                  <button
                    type="button"
                    class="artifact-link-button"
                    data-action="jump-section"
                    data-section-key="${escapeHtml(link.key)}"
                  >
                    ${escapeHtml(link.label)}
                  </button>
                `,
              )
              .join("")}
          </div>
          <pre>${escapeHtml(content)}</pre>
        </div>
      </div>
    `,
  );
}

function buildStageFromStep(step) {
  return {
    key: step?.step_key || "",
    label: step?.label || step?.step_key || "stage",
    status: step?.status || "unknown",
    elapsed_ms: step?.elapsed_ms ?? null,
    summary: step?.summary || "",
  };
}

function buildRunRenderData(detail) {
  const snapshot = detail?.result && typeof detail.result === "object" ? { ...detail.result } : {};
  const stepStages = Array.isArray(detail?.steps) ? detail.steps.map(buildStageFromStep) : [];
  const hasDebugStages = Array.isArray(snapshot.debug_stages) && snapshot.debug_stages.length;

  if ((!Array.isArray(snapshot.stages) || !snapshot.stages.length) && !hasDebugStages) {
    snapshot.stages = stepStages;
  } else if (stepStages.length && Array.isArray(snapshot.stages)) {
    const knownKeys = new Set(snapshot.stages.map((stage) => String(stage?.key || "")));
    stepStages.forEach((stage) => {
      if (!knownKeys.has(String(stage.key || ""))) {
        snapshot.stages.push(stage);
      }
    });
  }

  if (!snapshot.status && detail?.run?.status) {
    snapshot.status = detail.run.status;
  }
  if (!snapshot.mode && detail?.run?.mode) {
    snapshot.mode = detail.run.mode;
  }
  if (!snapshot.report_mode && detail?.run?.report_mode) {
    snapshot.report_mode = detail.run.report_mode;
  }
  if (!snapshot.report_error && detail?.run?.error_message) {
    snapshot.report_error = detail.run.error_message;
  }

  return snapshot;
}

function renderResult(data, rawData = data) {
  clearResults();

  const analysis = data.analysis || (data.debug_summary ? data : null);
  renderRuntime(data.runtime || (data.mode === "natural_language" ? runtimeCache : null));
  renderIntent(data.parsed_intent);
  renderStages(data);
  renderFollowUp(data.follow_up_question);
  renderOverview(analysis);
  renderMacro(analysis);
  renderReport(data.final_report, data.report_briefing, data.report_mode, data.report_error);
  renderTickerCards(analysis, data.report_briefing);
  renderRawJson(rawData);
}

function buildRunStatusMessage(detail, mode) {
  const run = detail?.run || {};
  const status = run.status || "queued";

  if (status === "queued") {
    return mode === "agent" ? "自然语言 Agent 已创建，正在排队..." : "结构化分析任务已创建，正在排队...";
  }

  if (status === "running") {
    return mode === "agent" ? "自然语言 Agent 正在运行，请稍等..." : "结构化分析正在运行，请稍等...";
  }

  if (status === "needs_clarification") {
    return "Agent 已完成意图分析，但还需要你补充一些关键信息。";
  }

  if (status === "failed") {
    return `运行失败: ${run.error_message || "未知错误"}`;
  }

  if (mode === "agent") {
    const reportLabel = run.report_mode === "fallback" ? "本地备选报告" : "LLM 报告";
    return `自然语言 Agent 已完成，当前展示的是${reportLabel}。`;
  }

  return "结构化分析已完成，你可以继续检查每个 ticker 的聚合结果和原始 JSON。";
}

function stopRunStream() {
  if (activeEventSource) {
    activeEventSource.close();
  }
  activeEventSource = null;
}

async function fetchRunDetail(runId) {
  const response = await fetch(`/api/runs/${runId}`);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "获取 run 详情失败。");
  }
  return data;
}

async function fetchRunArtifacts(runId) {
  const response = await fetch(`/api/runs/${runId}/artifacts`);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "获取 artifacts 失败。");
  }
  return data;
}

async function loadRunHistory() {
  const query = buildHistoryQueryString(true);
  const response = await fetch(`/api/runs?${query}`);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "获取历史 run 失败。");
  }
  currentRunHistory = Array.isArray(data.items) ? data.items : [];
  renderRunHistory(currentRunHistory);
  return data.items;
}

async function syncRunArtifacts(runId) {
  const payload = await fetchRunArtifacts(runId);
  currentArtifacts = Array.isArray(payload.artifacts) ? payload.artifacts : [];
  if (!currentArtifacts.length) {
    selectedArtifactKey = null;
    selectedArtifactKind = "all";
  } else if (!currentArtifacts.some((artifact) => artifactKey(artifact) === selectedArtifactKey)) {
    selectedArtifactKey = artifactKey(currentArtifacts[0]);
  }
  renderArtifacts(currentArtifacts);
}

async function syncRunDetail(runId, mode) {
  const detail = await fetchRunDetail(runId);
  currentRunDetail = detail;
  const renderData = buildRunRenderData(detail);
  renderResult(renderData, detail);
  renderRunSummary(detail);
  await syncRunArtifacts(runId);
  setStatus(buildRunStatusMessage(detail, mode));
  void loadRunHistory().catch(() => {});

  if (TERMINAL_RUN_STATUSES.has(detail?.run?.status)) {
    setLoadingState(mode, false);
    if (activeRunId === runId) {
      stopRunStream();
    }
  }

  return detail;
}

async function openRun(runId, mode) {
  if (!runId) {
    return;
  }

  if (runId === activeRunId && currentRunDetail?.run?.id === runId) {
    focusSection("run");
    return;
  }

  pendingOpenRunId = runId;
  renderRunHistory(currentRunHistory);
  activeRunId = runId;
  activeRunMode = mode;
  stopRunStream();
  setStatus("正在打开这次历史运行...");

  try {
    const detail = await syncRunDetail(runId, mode);
    if (!TERMINAL_RUN_STATUSES.has(detail?.run?.status)) {
      startRunStream(runId, mode);
    }
  } finally {
    pendingOpenRunId = null;
    renderRunHistory(currentRunHistory);
  }
}

function startRunStream(runId, mode) {
  stopRunStream();
  activeRunId = runId;
  activeRunMode = mode;

  const source = new EventSource(`/api/runs/${runId}/events`);
  activeEventSource = source;

  const sync = async () => {
    try {
      await syncRunDetail(runId, mode);
    } catch (error) {
      if (activeRunId !== runId) {
        return;
      }
      setStatus(`同步运行状态失败: ${error.message}`);
      setLoadingState(mode, false);
      stopRunStream();
    }
  };

  ["run.created", "run.started", "artifact.updated", "step.completed", "run.completed", "run.failed", "run.needs_clarification"].forEach(
    (eventName) => {
      source.addEventListener(eventName, () => {
        void sync();
      });
    },
  );

  source.onopen = () => {
    void sync();
  };

  source.onerror = async () => {
    if (activeRunId !== runId) {
      return;
    }

    try {
      const detail = await syncRunDetail(runId, mode);
      if (!TERMINAL_RUN_STATUSES.has(detail?.run?.status)) {
        setStatus("实时连接暂时中断，正在等待后端继续返回状态...");
      }
    } catch (error) {
      setStatus(`实时连接失败: ${error.message}`);
      setLoadingState(mode, false);
      stopRunStream();
    }
  };
}

function applyStructuredSample() {
  document.getElementById("tickers").value = "AAPL, MSFT, NVDA";
  document.getElementById("sectors").value = "Technology";
  document.getElementById("industries").value = "Semiconductors, Software";
  document.getElementById("risk-level").value = "medium";
  document.getElementById("max-results").value = "5";
  document.getElementById("max-pe").value = "35";
  document.getElementById("min-roe").value = "12";
  document.getElementById("min-dividend-yield").value = "1";
  document.getElementById("analyst-rating").value = "buy";
  document.getElementById("require-positive-fcf").checked = true;
  document.getElementById("fetch-live-data").checked = false;
  setStatus("结构化示例已填入。这个示例默认关闭实时数据，方便先验证筛选逻辑和页面展示。");
}

function applyAgentSample() {
  document.getElementById("agent-query").value = SAMPLE_AGENT_QUERY;
  document.getElementById("agent-max-results").value = "5";
  document.getElementById("agent-fetch-live-data").checked = false;
  setStatus("自然语言示例已填入。这个示例会先跑意图解析，再继续执行结构化分析和最终报告生成。");
}

async function loadRuntimeConfig() {
  try {
    const response = await fetch("/api/v1/agent/runtime-config");
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "获取运行时配置失败。");
    }

    runtimeCache = data;
    if (currentMode === "agent") {
      renderRuntime(data);
    }
  } catch (error) {
    runtimeCache = null;
    if (currentMode === "agent") {
      setStatus(`获取 LLM runtime 失败: ${error.message}`);
    }
  }
}

async function createRun(mode) {
  const payload = buildRunCreatePayload(mode);
  setLoadingState(mode, true);
  stopRunStream();
  activeRunId = null;
  activeRunMode = mode;
  currentRunDetail = null;
  currentArtifacts = [];
  selectedArtifactKey = null;
  setStatus(mode === "agent" ? "正在创建自然语言 Agent 任务..." : "正在创建结构化分析任务...");

  try {
    const response = await fetch("/api/runs", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "后端返回了错误状态。");
    }

    activeRunId = data.run?.id || null;
    activeRunMode = mode;
    currentRunDetail = data;
    renderResult(buildRunRenderData(data), data);
    renderRunSummary(data);
    renderArtifacts([]);
    await loadRunHistory();
    setStatus(mode === "agent" ? "自然语言 Agent 已创建，正在启动..." : "结构化分析任务已创建，正在启动...");

    if (!activeRunId) {
      throw new Error("后端没有返回 run_id。");
    }

    startRunStream(activeRunId, mode);
    await syncRunDetail(activeRunId, mode);
  } catch (error) {
    clearResults();
    if (currentMode === "agent" && runtimeCache) {
      renderRuntime(runtimeCache);
    }
    setStatus(`运行失败: ${error.message}`);
    stopRunStream();
    activeRunId = null;
    activeRunMode = null;
    currentRunDetail = null;
    currentArtifacts = [];
    selectedArtifactKey = null;
    setLoadingState(mode, false);
  }
}

async function retryRun(runId) {
  if (!runId) {
    return;
  }

  const mode = currentRunDetail?.run?.mode || activeRunMode || "agent";
  pendingRetryRunId = runId;
  if (currentRunDetail?.run?.id === runId) {
    renderRunSummary(currentRunDetail);
  }
  setLoadingState(mode, true);
  stopRunStream();
  setStatus("正在重试这次运行...");

  try {
    const response = await fetch(`/api/runs/${runId}/retry`, { method: "POST" });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "重试失败。");
    }

    activeRunId = data.run?.id || null;
    activeRunMode = data.run?.mode || mode;
    currentRunDetail = data;
    currentArtifacts = [];
    selectedArtifactKey = null;
    renderResult(buildRunRenderData(data), data);
    renderRunSummary(data);
    renderArtifacts([]);
    await loadRunHistory();

    if (!activeRunId) {
      throw new Error("后端没有返回新的 run_id。");
    }

    startRunStream(activeRunId, activeRunMode);
    await syncRunDetail(activeRunId, activeRunMode);
  } catch (error) {
    setStatus(`重试失败: ${error.message}`);
    setLoadingState(mode, false);
  } finally {
    pendingRetryRunId = null;
    if (currentRunDetail) {
      renderRunSummary(currentRunDetail);
    }
  }
}

async function clearHistory() {
  const filters = normalizeHistoryFilters();
  const filterLabel = [filters.search, filters.mode, filters.status].filter(Boolean).join(" / ");
  const message = filterLabel
    ? `确认清空当前筛选下的历史运行吗？\n筛选条件：${filterLabel}\n正在运行的任务不会被删除。`
    : "确认清空当前可见的历史运行吗？正在运行的任务不会被删除。";

  if (!window.confirm(message)) {
    return;
  }

  historyMutationPending = true;
  renderRunHistory(currentRunHistory);

  try {
    const query = buildHistoryQueryString(false);
    const response = await fetch(`/api/runs${query ? `?${query}` : ""}`, {
      method: "DELETE",
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "清空历史失败。");
    }

    await loadRunHistory();
    setStatus(data.deleted_count ? `已清理 ${data.deleted_count} 条历史运行。` : "当前筛选下没有可清理的历史运行。");
  } catch (error) {
    setStatus(`清空历史失败: ${error.message}`);
  } finally {
    historyMutationPending = false;
    renderRunHistory(currentRunHistory);
  }
}

elements.structuredSampleButton.addEventListener("click", applyStructuredSample);
elements.agentSampleButton.addEventListener("click", applyAgentSample);

elements.structuredForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await createRun("structured");
});

elements.agentForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await createRun("agent");
});

document.addEventListener("click", async (event) => {
  const target = event.target.closest("[data-action]");
  if (!target) {
    return;
  }

  const action = target.dataset.action;
  if (action === "open-run") {
    event.preventDefault();
    await openRun(target.dataset.runId, target.dataset.runMode || "agent");
    return;
  }

  if (action === "retry-run") {
    event.preventDefault();
    await retryRun(target.dataset.runId);
    return;
  }

  if (action === "refresh-history") {
    event.preventDefault();
    await loadRunHistory();
    return;
  }

  if (action === "reset-history-filters") {
    event.preventDefault();
    historyFilters = { search: "", mode: "", status: "" };
    await loadRunHistory();
    return;
  }

  if (action === "clear-history") {
    event.preventDefault();
    await clearHistory();
    return;
  }

  if (action === "select-artifact") {
    event.preventDefault();
    selectedArtifactKey = target.dataset.artifactKey || null;
    renderArtifacts(currentArtifacts);
    return;
  }

  if (action === "filter-artifacts") {
    event.preventDefault();
    selectedArtifactKind = target.dataset.artifactKind || "all";
    renderArtifacts(currentArtifacts);
    return;
  }

  if (action === "jump-section") {
    event.preventDefault();
    focusSection(target.dataset.sectionKey || "");
  }
});

document.addEventListener("submit", async (event) => {
  const form = event.target;
  if (!(form instanceof HTMLFormElement) || form.id !== "history-filter-form") {
    return;
  }

  event.preventDefault();
  historyFilters = {
    search: document.getElementById("history-search")?.value || "",
    mode: document.getElementById("history-mode")?.value || "",
    status: document.getElementById("history-status")?.value || "",
  };
  await loadRunHistory();
});

document.addEventListener("input", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLInputElement) || target.id !== "history-search") {
    return;
  }
  historyFilters = { ...historyFilters, search: target.value };
});

document.addEventListener("change", async (event) => {
  const target = event.target;
  if (!(target instanceof HTMLSelectElement)) {
    return;
  }

  if (target.id === "history-mode" || target.id === "history-status") {
    historyFilters = {
      ...historyFilters,
      mode: document.getElementById("history-mode")?.value || "",
      status: document.getElementById("history-status")?.value || "",
    };
    await loadRunHistory();
  }
});

elements.modeButtons.forEach((button) => {
  button.addEventListener("click", () => switchMode(button.dataset.mode));
});

applyStructuredSample();
loadRuntimeConfig();
loadRunHistory().catch(() => {
  renderRunHistory([]);
});
