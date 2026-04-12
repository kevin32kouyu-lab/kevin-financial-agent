import type { Locale } from "./types";

export interface LocalePack {
  locale: Locale;
  meta: {
    brand: string;
    title: string;
    subtitle: string;
    languageLabel: string;
    languageOptions: Record<Locale, string>;
    activeMode: string;
    debugMode: string;
  };
  status: {
    ready: string;
    openingRun: (runId: string) => string;
    viewingRun: (runId: string) => string;
    creatingAgent: string;
    creatingStructured: string;
    retryingRun: (runId: string) => string;
    clearedHistory: (count: number) => string;
    eventReceived: (eventType: string) => string;
    eventStreamClosed: string;
  };
  actions: {
    refresh: string;
    clear: string;
    retry: string;
    retrying: string;
    runAgent: string;
    runStructured: string;
    running: string;
    sample: string;
    viewRawJson: string;
  };
  control: {
    launchpad: string;
    launchpadTitle: string;
    launchpadNote: string;
    tabs: {
      agent: string;
      structured: string;
    };
    runtime: string;
    runtimeTitle: string;
    data: string;
    dataTitle: string;
    dataNote: string;
    fields: {
      query: string;
      tickers: string;
      sectors: string;
      industries: string;
      risk: string;
      maxResults: string;
      maxPe: string;
      minRoe: string;
      minDividend: string;
      analyst: string;
      positiveFcf: string;
      liveData: string;
    };
    helperAgent: string;
    helperStructured: string;
    placeholders: {
      query: string;
      tickers: string;
      sectors: string;
      industries: string;
    };
  };
  history: {
    eyebrow: string;
    title: string;
    search: string;
    mode: string;
    status: string;
    all: string;
    latestRuns: string;
    sync: string;
    empty: string;
    clearConfirm: string;
  };
  run: {
    eyebrow: string;
    empty: string;
    summary: string;
    liveEvents: string;
    currentView: string;
    runtime: string;
    research: string;
    execution: string;
    runtimeFields: {
      runId: string;
      createdAt: string;
      startedAt: string;
      finishedAt: string;
      steps: string;
      events: string;
      artifacts: string;
      provider: string;
      model: string;
      route: string;
      billing: string;
      topPick: string;
      verdict: string;
      mandateFit: string;
      marketStance: string;
    };
    watchlist: string;
    avoid: string;
    followUp: string;
    error: string;
    noEvents: string;
  };
  report: {
    empty: string;
    clarificationEyebrow: string;
    clarificationTitle: string;
    clarificationMissing: string;
    clarificationTickers: string;
    clarificationJson: string;
    structuredEyebrow: string;
    structuredTitle: string;
    structuredSummary: string;
    structuredPositioning: string;
    reportEyebrow: string;
    scoreboard: string;
    tickerCards: string;
    risks: string;
    execution: string;
    fullReport: string;
    reportJson: string;
    reportMode: string;
    mandateFit: string;
    candidates: string;
    noTable: string;
    noAllocation: string;
    noRisk: string;
    labels: {
      company: string;
      latestPrice: string;
      thesis: string;
      fitReason: string;
      technical: string;
      smartMoney: string;
      audit: string;
      catalysts: string;
      execution: string;
      regime: string;
      vix: string;
      topPick: string;
      marketStance: string;
      score: string;
      fit: string;
      valuation: string;
      quality: string;
      momentum: string;
      risk: string;
      source: string;
      lastRefresh: string;
    };
  };
  debug: {
    title: string;
    subtitle: string;
    stages: string;
    artifacts: string;
    rawJson: string;
    noStages: string;
    noArtifacts: string;
    selectArtifact: string;
    artifactType: string;
  };
  options: {
    analystAny: string;
    analystBuy: string;
    analystStrongBuy: string;
    riskLow: string;
    riskMedium: string;
    riskHigh: string;
  };
}

const zh: LocalePack = {
  locale: "zh",
  meta: {
    brand: "ROSE Capital Research",
    title: "金融研究前台",
    subtitle: "把投资目标、结论、风险判断和执行建议放在同一张研究页面里。",
    languageLabel: "界面语言",
    languageOptions: { zh: "中文", en: "English" },
    activeMode: "研究模式",
    debugMode: "调试视图",
  },
  status: {
    ready: "系统已准备好，可以发起新的研究。",
    openingRun: (runId) => `正在打开报告 ${runId}...`,
    viewingRun: (runId) => `当前正在查看报告 ${runId}`,
    creatingAgent: "正在生成新的研究报告...",
    creatingStructured: "正在生成结构化筛选结果...",
    retryingRun: (runId) => `正在重新生成报告 ${runId}...`,
    clearedHistory: (count) => `已清理 ${count} 条历史记录。`,
    eventReceived: (eventType) => `已收到事件：${eventType}`,
    eventStreamClosed: "实时事件流已关闭，页面会保留最后一次结果。",
  },
  actions: {
    refresh: "刷新",
    clear: "清理",
    retry: "重新生成",
    retrying: "重新生成中...",
    runAgent: "生成报告",
    runStructured: "运行结构化筛选",
    running: "运行中...",
    sample: "填入示例",
    viewRawJson: "查看原始 JSON",
  },
  control: {
    launchpad: "研究发起",
    launchpadTitle: "输入投资目标",
    launchpadNote: "尽量写清资金规模、风险偏好、持有期限和关注标的，系统会自动生成正式研究报告。",
    tabs: {
      agent: "自然语言研究",
      structured: "结构化筛选",
    },
    runtime: "模型环境",
    runtimeTitle: "模型与路由",
    data: "市场数据",
    dataTitle: "股票池与缓存",
    dataNote: "股票池优先来自本地缓存，只有缓存不可用时才回退到种子数据。",
    fields: {
      query: "投资问题",
      tickers: "股票代码",
      sectors: "偏好板块",
      industries: "偏好行业",
      risk: "风险偏好",
      maxResults: "最多返回",
      maxPe: "PE 上限",
      minRoe: "ROE 下限",
      minDividend: "股息率下限",
      analyst: "分析师评级",
      positiveFcf: "要求自由现金流为正",
      liveData: "同步抓取实时数据",
    },
    helperAgent: "支持中英文输入。投资目标越清晰，结论通常越稳定。",
    helperStructured: "结构化模式适合联调股票池、筛选逻辑和多源数据链路。",
    placeholders: {
      query: "例如：我有 50000 美元，想找适合长期持有的低风险分红股，请优先比较 JNJ、PG、KO，并给出执行建议。",
      tickers: "例如：JNJ, PG, KO",
      sectors: "例如：Healthcare, Consumer Defensive",
      industries: "例如：Drug Manufacturers, Beverages",
    },
  },
  history: {
    eyebrow: "历史报告",
    title: "最近研究记录",
    search: "搜索",
    mode: "模式",
    status: "状态",
    all: "全部",
    latestRuns: "最近更新",
    sync: "同步中...",
    empty: "当前没有匹配的历史记录。",
    clearConfirm: "确认清空当前筛选条件下的历史记录吗？运行中的任务不会被删除。",
  },
  run: {
    eyebrow: "当前报告",
    empty: "先输入一个投资目标，或从历史列表中打开一份已有报告。",
    summary: "报告概览",
    liveEvents: "实时事件",
    currentView: "当前视图",
    runtime: "运行环境",
    research: "研究摘要",
    execution: "执行建议",
    runtimeFields: {
      runId: "报告 ID",
      createdAt: "创建时间",
      startedAt: "开始时间",
      finishedAt: "结束时间",
      steps: "阶段数",
      events: "事件数",
      artifacts: "中间产物",
      provider: "模型服务商",
      model: "模型",
      route: "路由模式",
      billing: "计费模式",
      topPick: "优先关注",
      verdict: "结论",
      mandateFit: "目标匹配度",
      marketStance: "市场环境",
    },
    watchlist: "关注名单",
    avoid: "回避名单",
    followUp: "补充问题",
    error: "错误信息",
    noEvents: "当前还没有收到事件。",
  },
  report: {
    empty: "当前还没有研究结果。生成一份报告后，这里会展示结论、图表和执行建议。",
    clarificationEyebrow: "信息补充",
    clarificationTitle: "还需要补充一些关键信息",
    clarificationMissing: "缺失字段",
    clarificationTickers: "已识别标的",
    clarificationJson: "查看意图识别 JSON",
    structuredEyebrow: "结构化结果",
    structuredTitle: "结构化筛选快照",
    structuredSummary: "筛选摘要",
    structuredPositioning: "当前用途",
    reportEyebrow: "正式研究报告",
    scoreboard: "候选池总览",
    tickerCards: "逐票研究卡片",
    risks: "风险提示",
    execution: "建仓与执行",
    fullReport: "查看完整长文报告",
    reportJson: "查看报告 briefing JSON",
    reportMode: "报告模式",
    mandateFit: "目标匹配度",
    candidates: "候选数",
    noTable: "当前没有可展示的比较表格。",
    noAllocation: "当前没有建议仓位，说明策略更偏观察或等待。",
    noRisk: "当前没有额外风险登记项。",
    labels: {
      company: "公司",
      latestPrice: "现价",
      thesis: "投资逻辑",
      fitReason: "匹配原因",
      technical: "技术面 / 新闻",
      smartMoney: "资金面代理",
      audit: "审计与披露",
      catalysts: "催化因素",
      execution: "执行建议",
      regime: "市场环境",
      vix: "VIX",
      topPick: "优先关注",
      marketStance: "市场观点",
      score: "综合评分",
      fit: "匹配度",
      valuation: "估值",
      quality: "质量",
      momentum: "动量",
      risk: "风险",
      source: "数据来源",
      lastRefresh: "最近刷新",
    },
  },
  debug: {
    title: "开发者视图",
    subtitle: "阶段、产物和原始快照仍然保留，但不再占据前台主视图。",
    stages: "阶段时间线",
    artifacts: "中间产物",
    rawJson: "查看原始 JSON 快照",
    noStages: "当前还没有阶段记录。",
    noArtifacts: "当前筛选下没有中间产物。",
    selectArtifact: "选择左侧产物后可查看详情。",
    artifactType: "类型",
  },
  options: {
    analystAny: "不限",
    analystBuy: "buy",
    analystStrongBuy: "strong_buy",
    riskLow: "低风险",
    riskMedium: "中等风险",
    riskHigh: "高风险",
  },
};

const en: LocalePack = {
  locale: "en",
  meta: {
    brand: "ROSE Capital Research",
    title: "Investment Research Frontend",
    subtitle: "Bring the mandate, verdict, risk view and execution plan into one research surface.",
    languageLabel: "UI language",
    languageOptions: { zh: "中文", en: "English" },
    activeMode: "Research mode",
    debugMode: "Debug view",
  },
  status: {
    ready: "The desk is ready for a new research request.",
    openingRun: (runId) => `Opening report ${runId}...`,
    viewingRun: (runId) => `Viewing report ${runId}`,
    creatingAgent: "Generating a new research report...",
    creatingStructured: "Generating a structured screener snapshot...",
    retryingRun: (runId) => `Regenerating report ${runId}...`,
    clearedHistory: (count) => `Cleared ${count} archived reports.`,
    eventReceived: (eventType) => `Event received: ${eventType}`,
    eventStreamClosed: "The live event stream has closed. The latest result is still available.",
  },
  actions: {
    refresh: "Refresh",
    clear: "Clear",
    retry: "Regenerate",
    retrying: "Regenerating...",
    runAgent: "Generate report",
    runStructured: "Run structured screener",
    running: "Running...",
    sample: "Use sample",
    viewRawJson: "View raw JSON",
  },
  control: {
    launchpad: "Research request",
    launchpadTitle: "Define the investment goal",
    launchpadNote: "A strong request usually includes capital, risk, horizon and target names. The system will turn it into a formal memo.",
    tabs: {
      agent: "Natural-language research",
      structured: "Structured screener",
    },
    runtime: "Model runtime",
    runtimeTitle: "Model and routing",
    data: "Market data",
    dataTitle: "Universe and cache",
    dataNote: "The equity universe comes from the local cache first and falls back to seed data only when needed.",
    fields: {
      query: "Investment request",
      tickers: "Tickers",
      sectors: "Preferred sectors",
      industries: "Preferred industries",
      risk: "Risk profile",
      maxResults: "Max results",
      maxPe: "Max PE",
      minRoe: "Min ROE",
      minDividend: "Min dividend yield",
      analyst: "Analyst rating",
      positiveFcf: "Require positive FCF",
      liveData: "Fetch live data",
    },
    helperAgent: "Both English and Chinese are supported. Clear mandates produce more stable reports.",
    helperStructured: "Structured mode is useful for validating the screener, coverage universe and external data chain.",
    placeholders: {
      query: "For example: I have 50000 USD and want long-term low-risk dividend stocks. Compare JNJ, PG and KO, then give me an execution plan.",
      tickers: "For example: JNJ, PG, KO",
      sectors: "For example: Healthcare, Consumer Defensive",
      industries: "For example: Drug Manufacturers, Beverages",
    },
  },
  history: {
    eyebrow: "Archive",
    title: "Recent research reports",
    search: "Search",
    mode: "Mode",
    status: "Status",
    all: "All",
    latestRuns: "Recently updated",
    sync: "Syncing...",
    empty: "No archived reports match the current filters.",
    clearConfirm: "Clear archived reports under the current filters? Active runs will not be deleted.",
  },
  run: {
    eyebrow: "Current report",
    empty: "Enter a new investment goal or open an archived report.",
    summary: "Report snapshot",
    liveEvents: "Live events",
    currentView: "Current view",
    runtime: "Runtime",
    research: "Research summary",
    execution: "Execution plan",
    runtimeFields: {
      runId: "Report ID",
      createdAt: "Created at",
      startedAt: "Started at",
      finishedAt: "Finished at",
      steps: "Steps",
      events: "Events",
      artifacts: "Artifacts",
      provider: "Provider",
      model: "Model",
      route: "Route mode",
      billing: "Billing mode",
      topPick: "Top pick",
      verdict: "Verdict",
      mandateFit: "Mandate fit",
      marketStance: "Market stance",
    },
    watchlist: "Watchlist",
    avoid: "Avoid",
    followUp: "Follow-up",
    error: "Error",
    noEvents: "No events have arrived yet.",
  },
  report: {
    empty: "No research result is available yet. Once a run finishes, this area will show the verdict, charts and execution plan.",
    clarificationEyebrow: "Clarification",
    clarificationTitle: "More information is required",
    clarificationMissing: "Missing fields",
    clarificationTickers: "Recognized tickers",
    clarificationJson: "Inspect parsed intent JSON",
    structuredEyebrow: "Structured snapshot",
    structuredTitle: "Structured screener snapshot",
    structuredSummary: "Screening summary",
    structuredPositioning: "Current use",
    reportEyebrow: "Formal research memo",
    scoreboard: "Candidate scoreboard",
    tickerCards: "Per-ticker cards",
    risks: "Risk register",
    execution: "Execution plan",
    fullReport: "Open full memo",
    reportJson: "Inspect report briefing JSON",
    reportMode: "Report mode",
    mandateFit: "Mandate fit",
    candidates: "Candidates",
    noTable: "No comparison table is available right now.",
    noAllocation: "No allocation is suggested right now, which implies a watch-and-wait posture.",
    noRisk: "There are no extra items in the risk register.",
    labels: {
      company: "Company",
      latestPrice: "Latest price",
      thesis: "Thesis",
      fitReason: "Fit reason",
      technical: "Technical / News",
      smartMoney: "Positioning proxy",
      audit: "Audit",
      catalysts: "Catalysts",
      execution: "Execution",
      regime: "Market regime",
      vix: "VIX",
      topPick: "Top pick",
      marketStance: "Market stance",
      score: "Composite",
      fit: "Fit",
      valuation: "Valuation",
      quality: "Quality",
      momentum: "Momentum",
      risk: "Risk",
      source: "Source",
      lastRefresh: "Last refresh",
    },
  },
  debug: {
    title: "Developer view",
    subtitle: "Stages, artifacts and raw snapshots remain available without taking over the primary research surface.",
    stages: "Stage timeline",
    artifacts: "Artifacts",
    rawJson: "View raw JSON snapshot",
    noStages: "No stage record is available yet.",
    noArtifacts: "No artifact matches the current filter.",
    selectArtifact: "Select an artifact on the left to inspect it.",
    artifactType: "Type",
  },
  options: {
    analystAny: "Any",
    analystBuy: "buy",
    analystStrongBuy: "strong_buy",
    riskLow: "Low risk",
    riskMedium: "Medium risk",
    riskHigh: "High risk",
  },
};

export const LOCALE_PACKS: Record<Locale, LocalePack> = { zh, en };

export function getLocalePack(locale: Locale): LocalePack {
  return LOCALE_PACKS[locale];
}
