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
    cancel: string;
    cancelling: string;
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
      news: string;
      smartMoney: string;
      audit: string;
      auditLinks: string;
      shareClass: string;
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
      mode: string;
      overview: string;
      charts: string;
      coverage: string;
      riskExecution: string;
      fullMemo: string;
      investorMandate: string;
      dataProvenance: string;
      universeSize: string;
      verdict: string;
      assumptions: string;
      dataWarnings: string;
      stillNeedClarify: string;
      noSevereMacroVeto: string;
    };
  };
  terminal: {
    title: string;
    mode: string;
    overview: string;
    report: string;
    backtest: string;
    archive: string;
    developerView: string;
    decisionEyebrow: string;
    decisionWaiting: string;
    riskWaiting: string;
    nextActionWaiting: string;
    summaryTopPick: string;
    summaryFit: string;
    summaryMode: string;
    summaryRisk: string;
    quickToReport: string;
    quickToBacktest: string;
    modeTitle: string;
    modeSubtitle: string;
    realtime: string;
    historical: string;
    asOfDate: string;
    referenceStartDate: string;
    historicalEndDate: string;
    realtimeBacktestNote: string;
    historicalModeNote: string;
    generateRealtime: string;
    generateHistorical: string;
    waiting: string;
    loadingLatest: string;
    coreHint: string;
    currentAsOf: string;
    currentReferenceStart: string;
    progress: string;
    progressEyebrow: string;
    currentStage: string;
    queued: string;
    processing: string;
    reportReady: string;
    cancelled: string;
    failed: string;
    needClarification: string;
    reportTitle: string;
    updatedAt: string;
    historyReports: string;
    recentReports: string;
    expandHistory: string;
    collapseHistory: string;
    collapsedHistoryHint: string;
    noHistory: string;
    errorHeadline: string;
    onboarding: {
      eyebrow: string;
      title: string;
      step1Title: string;
      step1Body: string;
      step2Title: string;
      step2Body: string;
      step3Title: string;
      step3Body: string;
      skip: string;
      prev: string;
      next: string;
      done: string;
      reopen: string;
    };
    productGuide: {
      eyebrow: string;
      welcomeTitle: string;
      welcomeBody: string;
      start: string;
      skip: string;
      prev: string;
      next: string;
      done: string;
      reopen: string;
      stepLabel: string;
      proofPoints: Array<{ title: string; body: string }>;
      steps: {
        ask: { title: string; body: string };
        progress: { title: string; body: string };
        reportReady: { title: string; body: string };
        conclusion: { title: string; body: string };
        backtest: { title: string; body: string };
        archive: { title: string; body: string };
        account?: { title: string; body: string };
      };
    };
    uiNotice: {
      successTitle: string;
      successBody: string;
      errorTitle: string;
      errorBody: string;
      clarifyTitle: string;
      clarifyBody: string;
    };
  };
  backtest: {
    referenceTitle: string;
    replayTitle: string;
    panelTitle: string;
    referenceDescription: string;
    replayDescription: string;
    referenceCaution: string;
    replayCaution: string;
    blockedNeedClarification: string;
    blockedFailed: string;
    blockedCancelled: string;
    blockedNotCompleted: string;
    entryDate: string;
    endDate: string;
    running: string;
    rerunReference: string;
    rerunReplay: string;
    openCompletedFirst: string;
    loading: string;
    empty: string;
    portfolioReturn: string;
    benchmark: string;
    excess: string;
    versusBenchmark: string;
    maxDrawdown: string;
    annualized: string;
    shortSample: string;
    entryDay: string;
    endDay: string;
    tradingDays: string;
    curveTitle: string;
    curveSubtitle: string;
    portfolio: string;
    weight: string;
    entryPrice: string;
    latestPrice: string;
    investedAmount: string;
    currentValue: string;
    return: string;
    contribution: string;
    compute: string;
    requestedCoverage: string;
    droppedTickerReason: string;
    noDroppedTickers: string;
    ranges: {
      m1: string;
      m3: string;
      m6: string;
      y1: string;
      ytd: string;
      all: string;
    };
    stockTabTitle: string;
    stockSeriesTitle: string;
    stockSeriesSubtitle: string;
    stockSeriesDate: string;
    stockSeriesClose: string;
    stockSeriesDaily: string;
    stockSeriesCum: string;
    stockSeriesContribution: string;
  };
  debug: {
    title: string;
    subtitle: string;
    tabs: {
      overview: string;
      agents: string;
      stages: string;
      artifacts: string;
      rawJson: string;
    };
    stages: string;
    artifacts: string;
    rawJson: string;
    overviewTitle: string;
    overviewSubtitle: string;
    fieldLabels: {
      researchMode: string;
      asOfDate: string;
      backtestKind: string;
      warningFlags: string;
      runtime: string;
      routeBilling: string;
      market: string;
      records: string;
    };
    stageLabels: Record<string, string>;
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
    subtitle: "把投资目标、结论、风险与执行建议放在同一个终端里。",
    languageLabel: "界面语言",
    languageOptions: { zh: "中文", en: "English" },
    activeMode: "研究模式",
    debugMode: "调试视图",
  },
  status: {
    ready: "系统已准备好。",
    openingRun: (runId) => `正在打开报告 ${runId}...`,
    viewingRun: (runId) => `正在查看报告 ${runId}`,
    creatingAgent: "正在生成研究报告...",
    creatingStructured: "正在生成结构化筛选结果...",
    retryingRun: (runId) => `正在重试报告 ${runId}...`,
    clearedHistory: (count) => `已清理 ${count} 条历史记录。`,
    eventReceived: (eventType) => `收到事件：${eventType}`,
    eventStreamClosed: "实时事件流已关闭。",
  },
  actions: {
    refresh: "刷新",
    clear: "清理",
    retry: "重试",
    retrying: "重试中...",
    cancel: "撤回任务",
    cancelling: "撤回中...",
    runAgent: "生成报告",
    runStructured: "运行结构化筛选",
    running: "运行中...",
    sample: "填入示例",
    viewRawJson: "查看原始 JSON",
  },
  control: {
    launchpad: "研究发起",
    launchpadTitle: "输入投资目标",
    launchpadNote: "越清晰的输入，越容易得到稳定结论。",
    tabs: {
      agent: "自然语言研究",
      structured: "结构化筛选",
    },
    runtime: "模型环境",
    runtimeTitle: "模型与路由",
    data: "市场数据",
    dataTitle: "股票池与缓存",
    dataNote: "股票池优先来自缓存，必要时回退种子数据。",
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
    helperAgent: "支持中英文输入。",
    helperStructured: "结构化模式适合联调筛选和数据链路。",
    placeholders: {
      query: "例如：我有 50000 美元，想找长期低风险分红股，比较 JNJ、PG、KO，并给出建仓建议。",
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
    empty: "暂无匹配记录。",
    clearConfirm: "确认清理当前筛选下的历史记录吗？",
  },
  run: {
    eyebrow: "当前报告",
    empty: "先输入一个投资目标，或从历史列表打开报告。",
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
      provider: "服务商",
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
    error: "错误",
    noEvents: "暂无事件。",
  },
  report: {
    empty: "暂无研究结果。",
    clarificationEyebrow: "信息补充",
    clarificationTitle: "还需要补充关键信息",
    clarificationMissing: "缺失字段",
    clarificationTickers: "已识别标的",
    clarificationJson: "查看意图 JSON",
    structuredEyebrow: "结构化结果",
    structuredTitle: "结构化筛选快照",
    structuredSummary: "筛选摘要",
    structuredPositioning: "用途",
    reportEyebrow: "正式研究报告",
    scoreboard: "候选池",
    tickerCards: "逐票研究卡片",
    risks: "风险登记",
    execution: "执行计划",
    fullReport: "查看完整报告",
    reportJson: "查看 briefing JSON",
    reportMode: "报告模式",
    mandateFit: "目标匹配度",
    candidates: "候选数",
    noTable: "暂无表格数据。",
    noAllocation: "暂无建议仓位。",
    noRisk: "暂无额外风险项。",
    labels: {
      company: "公司",
      latestPrice: "现价",
      thesis: "投资逻辑",
      fitReason: "匹配原因",
      technical: "技术面 / 新闻",
      news: "新闻面",
      smartMoney: "资金面代理",
      audit: "审计",
      auditLinks: "审计披露链接",
      shareClass: "股权类别",
      catalysts: "催化因素",
      execution: "执行",
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
      mode: "模式",
      overview: "总览",
      charts: "图表",
      coverage: "逐票覆盖",
      riskExecution: "风险与执行",
      fullMemo: "完整备忘录",
      investorMandate: "投资目标",
      dataProvenance: "数据依据",
      universeSize: "股票池规模",
      verdict: "结论",
      assumptions: "默认假设",
      dataWarnings: "数据提醒",
      stillNeedClarify: "你后续还可以补充这些信息：",
      noSevereMacroVeto: "当前未检测到会直接推翻策略的宏观风险。",
    },
  },
  terminal: {
    title: "金融研究终端",
    mode: "模式",
    overview: "开始研究",
    report: "研究结论",
    backtest: "回测",
    archive: "历史",
    developerView: "开发者视图",
    decisionEyebrow: "本次结论",
    decisionWaiting: "等待研究结论",
    riskWaiting: "风险信息将在报告完成后显示",
    nextActionWaiting: "先输入投资目标，系统会自动生成下一步执行建议。",
    summaryTopPick: "优先关注",
    summaryFit: "匹配度",
    summaryMode: "研究模式",
    summaryRisk: "风险一句话",
    quickToReport: "查看正式报告",
    quickToBacktest: "查看回测表现",
    modeTitle: "在实时研究与历史研究之间切换",
    modeSubtitle: "研究模式",
    realtime: "实时模式",
    historical: "历史回测模式",
    asOfDate: "历史研究时点 (as_of_date)",
    referenceStartDate: "历史表现参考起点",
    historicalEndDate: "历史回放结束日期",
    realtimeBacktestNote: "实时模式中的回测为历史表现参考，用于帮助判断组合在过去区间的收益表现。",
    historicalModeNote: "历史模式会严格限制在 as_of_date 及之前的数据，缺失的数据源会显式降级。",
    generateRealtime: "生成实时研究",
    generateHistorical: "生成历史研究并回测",
    waiting: "等待任务",
    loadingLatest: "正在加载最新结果...",
    coreHint: "这里会显示本次研究的核心结论与风险信息。",
    currentAsOf: "当前 as_of_date",
    currentReferenceStart: "历史参考起点",
    progress: "任务进度",
    progressEyebrow: "研究进展",
    currentStage: "当前阶段",
    queued: "任务排队中，马上开始执行。",
    processing: "处理中",
    reportReady: "报告与回测可以继续查看或导出。",
    cancelled: "任务已撤回，可重新发起研究。",
    failed: "任务失败，请调整输入后重试。",
    needClarification: "需要补充关键信息后继续。",
    reportTitle: "报告标题",
    updatedAt: "更新时间",
    historyReports: "历史报告",
    recentReports: "最近研究记录",
    expandHistory: "展开历史",
    collapseHistory: "收起历史",
    collapsedHistoryHint: "历史区域已折叠（共 {count} 条），点击“展开历史”即可查看。",
    noHistory: "暂无历史报告。",
    errorHeadline: "这次研究没有顺利完成",
    onboarding: {
      eyebrow: "新手引导",
      title: "三步完成一份投资研究",
      step1Title: "先输入投资目标",
      step1Body: "写清资金规模、期限、风险偏好和关注标的，系统会更快给出稳定结论。",
      step2Title: "完成后会自动跳到研究结论",
      step2Body: "结果生成后，系统会自动进入研究结论页，先给你结论、依据摘要和完整报告。",
      step3Title: "再看回测和历史记录",
      step3Body: "回测页专门看历史表现，历史页专门回看过去的研究，不再和提问入口挤在一起。",
      skip: "跳过引导",
      prev: "上一步",
      next: "下一步",
      done: "完成引导",
      reopen: "重新查看新手引导",
    },
    productGuide: {
      eyebrow: "首次使用引导",
      welcomeTitle: "认识你的金融研究助手",
      welcomeBody: "这次会先放入一份示例报告，再带你看提问、结论、三报告和回测页。",
      start: "开始了解",
      skip: "跳过",
      prev: "上一步",
      next: "下一步",
      done: "完成",
      reopen: "引导",
      stepLabel: "步骤",
      proofPoints: [
        { title: "理解问题", body: "识别资金、风险、期限和关注标的。" },
        { title: "收集数据", body: "汇总行情、新闻、财报和证据来源。" },
        { title: "生成报告", body: "给出结论、仓位、风险和 PDF。" },
      ],
      steps: {
        ask: {
          title: "先把问题说清楚",
          body: "这里写资金、风险、期限和关注标的。你也可以点快速条件，让系统更快理解你的投资目标。",
        },
        progress: {
          title: "再看研究进度",
          body: "真实任务运行时，这里会显示当前阶段、进度和最近更新时间。示例报告已经准备好，下一步会直接进入生成后的结论页。",
        },
        reportReady: {
          title: "示例报告已生成",
          body: "现在你看到的是报告生成后的结论页。正式使用时，任务完成后也会自动跳到这里，先给出最终建议和风险摘要。",
        },
        conclusion: {
          title: "读结论和三份报告",
          body: "结论页先给优先标的、仓位、风险和依据；下面可以切换简单版、专业版和开发报告，也能导出 PDF。",
        },
        backtest: {
          title: "再用回测复核",
          body: "回测页会比较推荐组合和 SPY 基准，展示组合收益、最大回撤、单股贡献和本次回测口径。",
        },
        archive: {
          title: "最后回看和同步",
          body: "历史页用来打开过去的研究并继续跟进；右上角账户入口可以把浏览器偏好同步到账户。",
        },
      },
    },
    uiNotice: {
      successTitle: "研究已完成",
      successBody: "你现在可以查看回测结果，或直接导出正式报告。",
      errorTitle: "研究未完成",
      errorBody: "请调整问题描述后重试，系统会继续用可用数据源完成分析。",
      clarifyTitle: "需要补充一点信息",
      clarifyBody: "补充风险偏好或期限后，系统就能继续给出正式建议。",
    },
  },
  backtest: {
    referenceTitle: "历史表现参考",
    replayTitle: "历史建议回放",
    panelTitle: "回看建议在真实市场中的表现",
    referenceDescription: "基于当前报告推荐组合，计算如果在过去某天买入，到今天的历史表现参考。",
    replayDescription: "基于历史时点研究，按报告后下一个交易日开盘买入回放表现。",
    referenceCaution: "提示：这是历史表现参考，不等同于今天建议在当时一定会给出相同结论。",
    replayCaution: "提示：这是严格历史回放，已避免使用 as_of_date 之后的数据。",
    blockedNeedClarification: "当前报告需要先补充关键信息，补齐后才能生成回测。",
    blockedFailed: "当前报告执行失败，暂时无法回测。请先重试报告。",
    blockedCancelled: "当前报告已被撤回，无法回测。请重新发起研究。",
    blockedNotCompleted: "只有 completed 的报告才能回测。",
    entryDate: "买入起点",
    endDate: "结束日期",
    running: "计算中...",
    rerunReference: "重新计算历史表现参考",
    rerunReplay: "重新计算历史回放",
    openCompletedFirst: "请先打开一份已完成报告。",
    loading: "正在读取回测结果...",
    empty: "当前报告还没有回测结果，点击右上角按钮即可生成。",
    portfolioReturn: "组合收益",
    benchmark: "SPY 基准",
    excess: "超额收益",
    versusBenchmark: "相对 SPY",
    maxDrawdown: "最大回撤",
    annualized: "年化",
    shortSample: "样本区间较短",
    entryDay: "买入日",
    endDay: "结束日",
    tradingDays: "交易日",
    curveTitle: "收益曲线",
    curveSubtitle: "组合 vs SPY",
    portfolio: "组合",
    weight: "权重",
    entryPrice: "买入价",
    latestPrice: "最新价",
    investedAmount: "投入金额",
    currentValue: "当前价值",
    return: "收益率",
    contribution: "贡献",
    compute: "重新计算",
    requestedCoverage: "覆盖情况",
    droppedTickerReason: "未覆盖标的",
    noDroppedTickers: "本次回测已覆盖全部执行标的。",
    ranges: {
      m1: "1月",
      m3: "3月",
      m6: "6月",
      y1: "1年",
      ytd: "年内",
      all: "全部",
    },
    stockTabTitle: "逐股表现",
    stockSeriesTitle: "单股收益曲线",
    stockSeriesSubtitle: "日期维度收益与贡献",
    stockSeriesDate: "日期",
    stockSeriesClose: "收盘价",
    stockSeriesDaily: "单日收益",
    stockSeriesCum: "累计收益",
    stockSeriesContribution: "仓位贡献",
  },
  debug: {
    title: "开发者工作台",
    subtitle: "保留阶段、产物与原始快照，便于排查链路。",
    tabs: {
      overview: "概览",
      agents: "智能体",
      stages: "阶段",
      artifacts: "产物",
      rawJson: "原始 JSON",
    },
    stages: "阶段时间线",
    artifacts: "中间产物",
    rawJson: "查看 JSON",
    overviewTitle: "运行概览",
    overviewSubtitle: "先看关键运行信息，再按需进入阶段、产物和原始数据。",
    fieldLabels: {
      researchMode: "研究模式",
      asOfDate: "as_of_date",
      backtestKind: "回测模式",
      warningFlags: "数据提醒",
      runtime: "模型运行环境",
      routeBilling: "路由 / 计费",
      market: "市场数据",
      records: "记录数",
    },
    stageLabels: {
      intent_analysis: "意图解析",
      assumption_fill: "默认假设补全",
      follow_up: "补充追问",
      structured_analysis: "结构化分析",
      final_report: "最终报告",
      screener: "股票池筛选",
      live_data: "多源数据聚合",
      assemble: "研究包组装",
    },
    noStages: "暂无阶段记录。",
    noArtifacts: "暂无产物。",
    selectArtifact: "请选择左侧产物查看详情。",
    artifactType: "类型",
  },
  options: {
    analystAny: "不限",
    analystBuy: "buy",
    analystStrongBuy: "strong_buy",
    riskLow: "低风险",
    riskMedium: "中风险",
    riskHigh: "高风险",
  },
};

const en: LocalePack = {
  locale: "en",
  meta: {
    brand: "ROSE Capital Research",
    title: "Investment Research Frontend",
    subtitle: "Bring mandate, verdict, risk and execution into one surface.",
    languageLabel: "UI language",
    languageOptions: { zh: "中文", en: "English" },
    activeMode: "Research mode",
    debugMode: "Debug view",
  },
  status: {
    ready: "System is ready.",
    openingRun: (runId) => `Opening report ${runId}...`,
    viewingRun: (runId) => `Viewing report ${runId}`,
    creatingAgent: "Generating research report...",
    creatingStructured: "Generating structured result...",
    retryingRun: (runId) => `Retrying report ${runId}...`,
    clearedHistory: (count) => `Cleared ${count} history records.`,
    eventReceived: (eventType) => `Event received: ${eventType}`,
    eventStreamClosed: "Event stream closed.",
  },
  actions: {
    refresh: "Refresh",
    clear: "Clear",
    retry: "Retry",
    retrying: "Retrying...",
    cancel: "Cancel run",
    cancelling: "Cancelling...",
    runAgent: "Generate report",
    runStructured: "Run structured screener",
    running: "Running...",
    sample: "Use sample",
    viewRawJson: "View raw JSON",
  },
  control: {
    launchpad: "Launchpad",
    launchpadTitle: "Enter investment goal",
    launchpadNote: "Clearer mandates lead to more stable outputs.",
    tabs: {
      agent: "Natural-language research",
      structured: "Structured screener",
    },
    runtime: "Runtime",
    runtimeTitle: "Model and route",
    data: "Market data",
    dataTitle: "Universe and cache",
    dataNote: "Universe uses cache first and falls back only when needed.",
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
    helperAgent: "Both English and Chinese are supported.",
    helperStructured: "Structured mode is for screener and data-chain validation.",
    placeholders: {
      query: "For example: I have 50000 USD and want long-term low-risk dividend stocks. Compare JNJ, PG and KO.",
      tickers: "For example: JNJ, PG, KO",
      sectors: "For example: Healthcare, Consumer Defensive",
      industries: "For example: Drug Manufacturers, Beverages",
    },
  },
  history: {
    eyebrow: "Archive",
    title: "Recent reports",
    search: "Search",
    mode: "Mode",
    status: "Status",
    all: "All",
    latestRuns: "Recently updated",
    sync: "Syncing...",
    empty: "No records.",
    clearConfirm: "Clear history under current filters?",
  },
  run: {
    eyebrow: "Current report",
    empty: "Enter a goal or open a report from archive.",
    summary: "Summary",
    liveEvents: "Live events",
    currentView: "Current view",
    runtime: "Runtime",
    research: "Research",
    execution: "Execution",
    runtimeFields: {
      runId: "Run ID",
      createdAt: "Created",
      startedAt: "Started",
      finishedAt: "Finished",
      steps: "Steps",
      events: "Events",
      artifacts: "Artifacts",
      provider: "Provider",
      model: "Model",
      route: "Route",
      billing: "Billing",
      topPick: "Top pick",
      verdict: "Verdict",
      mandateFit: "Mandate fit",
      marketStance: "Market stance",
    },
    watchlist: "Watchlist",
    avoid: "Avoid",
    followUp: "Follow-up",
    error: "Error",
    noEvents: "No events yet.",
  },
  report: {
    empty: "No report yet.",
    clarificationEyebrow: "Clarification",
    clarificationTitle: "More information is needed",
    clarificationMissing: "Missing fields",
    clarificationTickers: "Recognized tickers",
    clarificationJson: "Inspect parsed intent JSON",
    structuredEyebrow: "Structured result",
    structuredTitle: "Structured screener snapshot",
    structuredSummary: "Summary",
    structuredPositioning: "Use case",
    reportEyebrow: "Formal memo",
    scoreboard: "Scoreboard",
    tickerCards: "Ticker cards",
    risks: "Risk register",
    execution: "Execution plan",
    fullReport: "Open full report",
    reportJson: "Inspect briefing JSON",
    reportMode: "Report mode",
    mandateFit: "Mandate fit",
    candidates: "Candidates",
    noTable: "No table available.",
    noAllocation: "No allocation suggestion.",
    noRisk: "No additional risks.",
    labels: {
      company: "Company",
      latestPrice: "Latest",
      thesis: "Thesis",
      fitReason: "Fit reason",
      technical: "Technical / News",
      news: "News",
      smartMoney: "Positioning proxy",
      audit: "Audit",
      auditLinks: "Audit filing links",
      shareClass: "Share class",
      catalysts: "Catalysts",
      execution: "Execution",
      regime: "Regime",
      vix: "VIX",
      topPick: "Top pick",
      marketStance: "Market stance",
      score: "Score",
      fit: "Fit",
      valuation: "Valuation",
      quality: "Quality",
      momentum: "Momentum",
      risk: "Risk",
      source: "Source",
      lastRefresh: "Last refresh",
      mode: "Mode",
      overview: "Overview",
      charts: "Charts",
      coverage: "Coverage",
      riskExecution: "Risk & Execution",
      fullMemo: "Full memo",
      investorMandate: "Investor mandate",
      dataProvenance: "Data provenance",
      universeSize: "Universe size",
      verdict: "Verdict",
      assumptions: "Assumptions",
      dataWarnings: "Data warnings",
      stillNeedClarify: "You may still want to clarify:",
      noSevereMacroVeto: "No severe macro veto is visible.",
    },
  },
  terminal: {
    title: "Investment Research Terminal",
    mode: "Mode",
    overview: "Start Research",
    report: "Research Conclusion",
    backtest: "Backtest",
    archive: "Archive",
    developerView: "Developer view",
    decisionEyebrow: "Current decision",
    decisionWaiting: "Waiting for a research verdict",
    riskWaiting: "Risk summary will appear after the run completes",
    nextActionWaiting: "Start with your investment objective and the system will suggest the next action.",
    summaryTopPick: "Top pick",
    summaryFit: "Mandate fit",
    summaryMode: "Research mode",
    summaryRisk: "Risk in one line",
    quickToReport: "Open full report",
    quickToBacktest: "Open backtest",
    modeTitle: "Switch between realtime and historical research",
    modeSubtitle: "Research mode",
    realtime: "Realtime",
    historical: "Historical replay",
    asOfDate: "As-of date",
    referenceStartDate: "Reference start date",
    historicalEndDate: "Historical replay end date",
    realtimeBacktestNote: "Realtime mode backtest is a historical performance reference for the selected basket.",
    historicalModeNote: "Historical mode is strict as-of and explicitly degrades unavailable sources.",
    generateRealtime: "Generate realtime research",
    generateHistorical: "Generate historical research + replay",
    waiting: "Waiting",
    loadingLatest: "Loading latest result...",
    coreHint: "Core verdict and risk flags will appear here.",
    currentAsOf: "Current as_of_date",
    currentReferenceStart: "Reference start date",
    progress: "Task progress",
    progressEyebrow: "Run progress",
    currentStage: "Current stage",
    queued: "Run is queued and will start shortly.",
    processing: "Processing",
    reportReady: "Report is ready for review and export.",
    cancelled: "Run cancelled. You can start a new one.",
    failed: "Run failed. Adjust request and retry.",
    needClarification: "More information is required to continue.",
    reportTitle: "Report title",
    updatedAt: "Updated at",
    historyReports: "Archive",
    recentReports: "Recent reports",
    expandHistory: "Expand archive",
    collapseHistory: "Collapse archive",
    collapsedHistoryHint: "Archive is collapsed ({count} items). Click “Expand archive” to review past reports.",
    noHistory: "No archived report yet.",
    errorHeadline: "This run did not complete",
    onboarding: {
      eyebrow: "Quick start",
      title: "Finish a research task in 3 steps",
      step1Title: "Describe your objective",
      step1Body: "Include capital, horizon, risk preference and symbols for faster and more stable outputs.",
      step2Title: "Jump straight into the conclusion page",
      step2Body: "Once the run finishes, the terminal moves to the research conclusion page with the verdict, evidence summary, and full memo.",
      step3Title: "Use backtest and archive separately",
      step3Body: "Backtest is dedicated to performance replay, while archive is for reopening past runs without crowding the ask page.",
      skip: "Skip",
      prev: "Previous",
      next: "Next",
      done: "Finish",
      reopen: "Show quick start again",
    },
    productGuide: {
      eyebrow: "First-time guide",
      welcomeTitle: "Meet your Financial Agent",
      welcomeBody: "This guide loads a demo report first, then walks through the ask page, conclusion, reports, and backtest.",
      start: "Start Guide",
      skip: "Skip",
      prev: "Previous",
      next: "Next",
      done: "Finish",
      reopen: "Guide",
      stepLabel: "Step",
      proofPoints: [
        { title: "Understand", body: "Read capital, risk, horizon, and tickers." },
        { title: "Collect data", body: "Gather prices, news, filings, and evidence." },
        { title: "Report", body: "Produce verdict, sizing, risks, and PDF." },
      ],
      steps: {
        ask: {
          title: "Start with a clear question",
          body: "Write capital, risk, horizon, and focus tickers here. Quick hints help the system understand your mandate faster.",
        },
        progress: {
          title: "Track the research run",
          body: "During a real run, this card shows the current stage, progress, and latest update. The demo report is ready, so the next step opens the completed conclusion page.",
        },
        reportReady: {
          title: "Demo report is ready",
          body: "You are now seeing the completed conclusion page. In normal use, a finished run lands here first with the verdict and risk summary.",
        },
        conclusion: {
          title: "Read the conclusion and reports",
          body: "The conclusion page shows the top pick, sizing, risk, and evidence. The report area lets you switch between simple, professional, and development reports, with PDF export.",
        },
        backtest: {
          title: "Validate with backtest",
          body: "The backtest page compares the recommended basket with SPY and shows portfolio return, drawdown, per-stock contribution, and assumptions.",
        },
        archive: {
          title: "Return and sync",
          body: "Use the archive to reopen past research or continue an older question. The account entry syncs browser preferences across devices.",
        },
      },
    },
    uiNotice: {
      successTitle: "Research completed",
      successBody: "You can now review backtest performance or export the formal report.",
      errorTitle: "Research not completed",
      errorBody: "Please refine your request and retry. The system will continue with available sources.",
      clarifyTitle: "A little more information is needed",
      clarifyBody: "Add risk preference or horizon and the formal recommendation will continue.",
    },
  },
  backtest: {
    referenceTitle: "Historical performance reference",
    replayTitle: "Historical recommendation replay",
    panelTitle: "Review how the recommendation performed in market data",
    referenceDescription: "Uses the current recommended basket to estimate performance if bought on a selected past date.",
    replayDescription: "Replays performance from the next trading day open after a historical as-of research run.",
    referenceCaution: "Note: this is a historical performance reference, not proof the same recommendation would have existed then.",
    replayCaution: "Note: this is strict historical replay and avoids data after as-of date.",
    blockedNeedClarification: "This report needs clarification before a backtest can be generated.",
    blockedFailed: "This run failed. Retry the report first before backtesting.",
    blockedCancelled: "This run was cancelled. Start a new report before backtesting.",
    blockedNotCompleted: "Only completed reports can be replayed.",
    entryDate: "Entry date",
    endDate: "End date",
    running: "Running...",
    rerunReference: "Compute reference",
    rerunReplay: "Run replay",
    openCompletedFirst: "Open a completed report first.",
    loading: "Loading backtest...",
    empty: "No backtest exists yet. Generate one from the controls above.",
    portfolioReturn: "Portfolio return",
    benchmark: "SPY benchmark",
    excess: "Excess return",
    versusBenchmark: "Relative to SPY",
    maxDrawdown: "Max drawdown",
    annualized: "Annualized",
    shortSample: "Short sample",
    entryDay: "Entry",
    endDay: "End",
    tradingDays: "Trading days",
    curveTitle: "Return curve",
    curveSubtitle: "Portfolio vs SPY",
    portfolio: "Portfolio",
    weight: "Weight",
    entryPrice: "Entry",
    latestPrice: "Latest",
    investedAmount: "Invested",
    currentValue: "Current value",
    return: "Return",
    contribution: "Contribution",
    compute: "Compute",
    requestedCoverage: "Coverage",
    droppedTickerReason: "Dropped tickers",
    noDroppedTickers: "This backtest covered all planned positions.",
    ranges: {
      m1: "1M",
      m3: "3M",
      m6: "6M",
      y1: "1Y",
      ytd: "YTD",
      all: "ALL",
    },
    stockTabTitle: "Per-stock view",
    stockSeriesTitle: "Single-stock performance",
    stockSeriesSubtitle: "Date-level returns and contribution",
    stockSeriesDate: "Date",
    stockSeriesClose: "Close",
    stockSeriesDaily: "Daily return",
    stockSeriesCum: "Cumulative return",
    stockSeriesContribution: "Contribution",
  },
  debug: {
    title: "Developer workbench",
    subtitle: "Stage timeline, artifacts and raw snapshots for diagnostics.",
    tabs: {
      overview: "Overview",
      agents: "Agents",
      stages: "Stages",
      artifacts: "Artifacts",
      rawJson: "Raw JSON",
    },
    stages: "Stages",
    artifacts: "Artifacts",
    rawJson: "Raw JSON",
    overviewTitle: "Run overview",
    overviewSubtitle: "Start with key runtime signals, then drill into stages, artifacts, and raw payloads.",
    fieldLabels: {
      researchMode: "Research mode",
      asOfDate: "as_of_date",
      backtestKind: "Backtest kind",
      warningFlags: "Warning flags",
      runtime: "Runtime",
      routeBilling: "Route / Billing",
      market: "Market data",
      records: "Records",
    },
    stageLabels: {
      intent_analysis: "Intent parsing",
      assumption_fill: "Assumption fill",
      follow_up: "Clarification",
      structured_analysis: "Structured analysis",
      final_report: "Final report",
      screener: "Screener",
      live_data: "Live data aggregation",
      assemble: "Research package assembly",
    },
    noStages: "No stages yet.",
    noArtifacts: "No artifacts.",
    selectArtifact: "Select an artifact to inspect.",
    artifactType: "Type",
  },
  options: {
    analystAny: "Any",
    analystBuy: "buy",
    analystStrongBuy: "strong_buy",
    riskLow: "Low",
    riskMedium: "Medium",
    riskHigh: "High",
  },
};

export const LOCALE_PACKS: Record<Locale, LocalePack> = { zh, en };

export function getLocalePack(locale: Locale): LocalePack {
  return LOCALE_PACKS[locale];
}
