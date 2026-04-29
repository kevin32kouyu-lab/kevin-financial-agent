/** 新手引导演示数据：只在前端展示一份完整示例报告和回测。 */
import type { BacktestDetail, Locale, RunAuditSummary, RunDetailResponse } from "./types";

export const DEMO_GUIDE_RUN_ID = "demo-guide-run";

const DEMO_UPDATED_AT = "2026-04-22T08:00:00Z";

/** 根据语言返回示例问题。 */
export function getDemoGuideQuery(locale: Locale): string {
  return locale === "zh"
    ? "我有 10 万美元，风险偏中等，想配置 3 到 5 年的美股组合。请比较 MSFT、AAPL 和 NVDA，给出建议仓位、风险和回测参考。"
    : "I have $100k, medium risk tolerance, and want a 3 to 5 year US equity portfolio. Compare MSFT, AAPL, and NVDA with sizing, risks, and backtest context.";
}

/** 生成前端演示用的完整研究详情。 */
export function createDemoGuideRunDetail(locale: Locale): RunDetailResponse {
  const query = getDemoGuideQuery(locale);
  const zh = locale === "zh";
  const simpleMarkdown = zh
    ? [
        "# 简单版投资报告",
        "",
        "## 一句话结论",
        "",
        "优先关注 MSFT，把它作为核心仓位；AAPL 适合做稳定补充，NVDA 更适合小比例成长卫星仓位。",
        "",
        "## 建议组合",
        "",
        "- MSFT：50%，作为核心软件和云计算仓位。",
        "- AAPL：30%，作为现金流稳定的消费科技仓位。",
        "- NVDA：20%，作为高波动成长仓位。",
        "",
        "## 主要风险",
        "",
        "估值仍是主要风险，尤其是 NVDA；如果组合回撤超过 12%，应重新检查仓位。"
      ].join("\n")
    : [
        "# Simple Investment Report",
        "",
        "## One-line Verdict",
        "",
        "Use MSFT as the core holding, keep AAPL as the stable compounder, and treat NVDA as a smaller growth satellite.",
        "",
        "## Recommended Portfolio",
        "",
        "- MSFT: 50%, core software and cloud exposure.",
        "- AAPL: 30%, durable consumer technology cash flow.",
        "- NVDA: 20%, higher-volatility growth satellite.",
        "",
        "## Main Risk",
        "",
        "Valuation is still the key risk, especially for NVDA. Re-check sizing if the basket drawdown exceeds 12%."
      ].join("\n");
  const professionalMarkdown = zh
    ? [
        "# 专业版投资报告",
        "",
        "## 核心持仓分析",
        "",
        "MSFT 的云业务、企业软件粘性和现金流质量让它更适合承担核心仓位。AAPL 的回购和生态稳定性提供防守属性。NVDA 的增长弹性更强，但估值和周期波动也更高。",
        "",
        "## 估值与质量",
        "",
        "示例评分把质量、增长、估值和风险放在同一张表里比较。MSFT 综合得分最高，AAPL 稳定性更强，NVDA 成长分更高但风险分也更高。",
        "",
        "## 情景分析",
        "",
        "基准情景下，组合更适合 3 到 5 年持有；若利率重新上行或 AI 预期降温，应降低 NVDA 权重。"
      ].join("\n")
    : [
        "# Professional Investment Report",
        "",
        "## Core Holdings Deep Dive",
        "",
        "MSFT earns the core weight because cloud, enterprise software retention, and free cash flow quality fit the mandate. AAPL adds defensive cash-flow durability. NVDA adds upside but carries higher valuation and cycle risk.",
        "",
        "## Valuation and Quality View",
        "",
        "The example scorecard compares quality, growth, valuation, and risk on one page. MSFT ranks highest overall, AAPL provides stability, and NVDA offers stronger growth with higher risk.",
        "",
        "## Scenario Analysis",
        "",
        "In the base case, the basket fits a 3 to 5 year hold. If rates rise again or AI expectations cool, reduce NVDA first."
      ].join("\n");
  const developmentMarkdown = zh
    ? [
        "# 开发报告",
        "",
        "## Agent Workflow",
        "",
        "- IntakeAgent：解析资金、风险、期限和关注标的。",
        "- DataAgent：读取示例行情、新闻和财报证据。",
        "- ReportAgent：生成简单版、专业版和开发报告。",
        "",
        "## RAG Evidence Coverage",
        "",
        "- 示例证据条数：3",
        "- 校验检查：2",
        "- 回测状态：available"
      ].join("\n")
    : [
        "# Agentic Research Development Report",
        "",
        "## Agent Workflow",
        "",
        "- IntakeAgent: parsed capital, risk, horizon, and focus tickers.",
        "- DataAgent: read example market, news, and filing evidence.",
        "- ReportAgent: produced simple, professional, and development reports.",
        "",
        "## RAG Evidence Coverage",
        "",
        "- Example evidence items: 3",
        "- Validation checks: 2",
        "- Backtest status: available"
      ].join("\n");

  const allocationItems = [
    { ticker: "MSFT", weight: 50 },
    { ticker: "AAPL", weight: 30 },
    { ticker: "NVDA", weight: 20 },
  ];
  const scoreItems = [
    { ticker: "MSFT", composite: 88, quality: 92, growth: 84, valuation: 78, risk: 82 },
    { ticker: "AAPL", composite: 81, quality: 88, growth: 70, valuation: 76, risk: 86 },
    { ticker: "NVDA", composite: 79, quality: 82, growth: 94, valuation: 58, risk: 62 },
  ];
  const riskItems = [
    { name: zh ? "估值风险" : "Valuation risk", value: 42 },
    { name: zh ? "盈利预期" : "Earnings expectations", value: 31 },
    { name: zh ? "集中度" : "Concentration", value: 27 },
  ];

  return {
    run: {
      id: DEMO_GUIDE_RUN_ID,
      mode: "agent",
      workflow_key: "financial_agent",
      status: "completed",
      title: zh ? "新手引导演示研究" : "Guided demo research",
      created_at: DEMO_UPDATED_AT,
      updated_at: DEMO_UPDATED_AT,
      started_at: DEMO_UPDATED_AT,
      finished_at: DEMO_UPDATED_AT,
      parent_run_id: null,
      error_message: null,
      report_mode: "agent",
      attempt_count: 1,
      metadata: { demo_guide: true },
    },
    steps: [
      { step_key: "intake", label: zh ? "理解问题" : "Understand request", status: "completed", position: 1, created_at: DEMO_UPDATED_AT, updated_at: DEMO_UPDATED_AT },
      { step_key: "data", label: zh ? "收集数据" : "Collect data", status: "completed", position: 2, created_at: DEMO_UPDATED_AT, updated_at: DEMO_UPDATED_AT },
      { step_key: "report", label: zh ? "生成报告" : "Generate report", status: "completed", position: 3, created_at: DEMO_UPDATED_AT, updated_at: DEMO_UPDATED_AT },
    ],
    artifacts: [],
    result: {
      status: "completed",
      query,
      final_report: professionalMarkdown,
      report_mode: "deepseek_demo",
      research_context: { research_mode: "realtime", as_of_date: null },
      parsed_intent: {
        system_context: { language: locale },
        agent_control: { is_intent_clear: true, is_intent_usable: true, missing_critical_info: [] },
      },
      report_briefing: {
        meta: {
          title: zh ? "示例：三股组合研究" : "Demo: three-stock portfolio research",
          research_mode: "realtime",
          confidence_level: zh ? "中等" : "medium",
          ticker_count: 3,
          mandate_summary: zh ? "中等风险、3 到 5 年持有、偏核心加卫星的美股组合。" : "Medium risk, 3 to 5 year hold, core-plus-satellite US equity basket.",
          user_profile: {
            capital_amount: 100000,
            currency: "USD",
            risk_tolerance: zh ? "中等" : "medium",
            investment_horizon: zh ? "3 到 5 年" : "3 to 5 years",
            investment_style: zh ? "核心加卫星" : "core plus satellite",
          },
          evidence_summary: {
            headline: zh ? "示例证据覆盖了价格、基本面和公司披露。" : "Example evidence covers price, fundamentals, and company disclosures.",
            items: zh
              ? ["MSFT 质量得分最高。", "AAPL 稳定性强。", "NVDA 增长强但波动更高。"]
              : ["MSFT has the strongest quality score.", "AAPL adds stability.", "NVDA has stronger growth and higher volatility."],
          },
          validation_summary: {
            headline: zh ? "结论和风险提示一致，未发现阻断性降级。" : "Verdict and risk notes are consistent; no blocking degradation is shown.",
          },
          safety_summary: { degraded_modules: [] },
          validation_checks: [
            { name: "allocation_sum", status: "passed" },
            { name: "risk_disclosure", status: "passed" },
          ],
          retrieved_evidence: [
            { title: "MSFT quality snapshot", source: "demo", published_at: "2026-04-20" },
            { title: "AAPL cash-flow snapshot", source: "demo", published_at: "2026-04-21" },
            { title: "NVDA growth risk snapshot", source: "demo", published_at: "2026-04-22" },
          ],
          data_provenance: { source: "frontend_demo", records: 3, last_refresh_at: DEMO_UPDATED_AT },
          score_guide: { composite: zh ? "综合质量、增长、估值和风险。" : "Combines quality, growth, valuation, and risk." },
          assumptions: [],
        },
        executive: {
          display_call: zh ? "优先关注 MSFT，AAPL 稳定补充，NVDA 小比例参与成长。" : "Focus on MSFT first, use AAPL for stability, and keep NVDA as a smaller growth sleeve.",
          primary_call: "MSFT",
          display_action_summary: zh ? "先建核心仓位，再用小比例跟踪高波动成长。" : "Build the core first, then size the higher-volatility growth sleeve cautiously.",
          action_summary: "Core plus satellite",
          top_pick: "MSFT",
          mandate_fit_score: 86,
          market_stance: zh ? "选择性配置" : "Selective",
          watchlist: ["MSFT", "AAPL", "NVDA"],
          avoid_list: [],
          allocation_plan: allocationItems.map((item) => ({ ...item, verdict: item.ticker === "MSFT" ? (zh ? "核心" : "Core") : (zh ? "卫星" : "Satellite") })),
        },
        macro: {
          regime: zh ? "选择性风险偏好" : "Selective risk-on",
          risk_headline: zh ? "估值与回撤是主要风险。" : "Valuation and drawdown risk remain the main watch points.",
          severe_warning: false,
        },
        charts: {
          allocation: allocationItems,
          ranking: scoreItems,
          dimensions: scoreItems,
        },
        scoreboard: scoreItems,
        ticker_cards: scoreItems.map((item) => ({
          ticker: item.ticker,
          verdict: item.ticker === "MSFT" ? (zh ? "优先关注" : "Top pick") : (zh ? "纳入组合" : "Include"),
          composite_score: item.composite,
          rationale: item.ticker === "MSFT" ? (zh ? "质量和现金流最稳。" : "Best quality and cash-flow fit.") : (zh ? "适合补充组合。" : "Useful portfolio complement."),
        })),
        risk_register: [
          { category: zh ? "估值" : "Valuation", summary: zh ? "高估值会放大回撤。" : "High valuation can amplify drawdowns.", mitigation: zh ? "控制 NVDA 权重。" : "Control NVDA sizing." },
        ],
      },
      report_outputs: {
        simple_investment: {
          markdown: simpleMarkdown,
          charts: {
            portfolio_allocation: { status: "ready", items: allocationItems },
            candidate_score_comparison: { status: "ready", items: scoreItems },
            risk_contribution: { status: "ready", items: riskItems },
            portfolio_vs_benchmark_backtest: { status: "available", summary: createDemoGuideBacktest(locale).summary, points: createDemoGuideBacktest(locale).points },
          },
        },
        investment: {
          markdown: simpleMarkdown,
          charts: {
            portfolio_allocation: { status: "ready", items: allocationItems },
            candidate_score_comparison: { status: "ready", items: scoreItems },
            risk_contribution: { status: "ready", items: riskItems },
            portfolio_vs_benchmark_backtest: { status: "available", summary: createDemoGuideBacktest(locale).summary, points: createDemoGuideBacktest(locale).points },
          },
        },
        professional_investment: {
          markdown: professionalMarkdown,
          charts: {
            portfolio_allocation: { status: "ready", items: allocationItems },
            candidate_score_comparison: { status: "ready", items: scoreItems },
            risk_contribution: { status: "ready", items: riskItems },
            portfolio_vs_benchmark_backtest: { status: "available", summary: createDemoGuideBacktest(locale).summary, points: createDemoGuideBacktest(locale).points },
          },
        },
        development: {
          markdown: developmentMarkdown,
          diagnostics: {
            agent_count: 3,
            evidence_count: 3,
            validation_check_count: 2,
            backtest_status: "available",
          },
        },
      },
      memory_summary: {
        applied_fields: [],
        stored_fields: ["risk_tolerance", "investment_horizon", "investment_style"],
      },
    },
  };
}

/** 生成前端演示用的回测详情。 */
export function createDemoGuideBacktest(locale: Locale): BacktestDetail {
  const zh = locale === "zh";
  const points = [
    { point_date: "2026-01-16", portfolio_value: 100000, benchmark_value: 100000, portfolio_return_pct: 0, benchmark_return_pct: 0 },
    { point_date: "2026-02-16", portfolio_value: 103200, benchmark_value: 101500, portfolio_return_pct: 3.2, benchmark_return_pct: 1.5 },
    { point_date: "2026-03-16", portfolio_value: 106800, benchmark_value: 103400, portfolio_return_pct: 6.8, benchmark_return_pct: 3.4 },
    { point_date: "2026-04-22", portfolio_value: 109400, benchmark_value: 105100, portfolio_return_pct: 9.4, benchmark_return_pct: 5.1 },
  ];
  return {
    summary: {
      id: "demo-guide-backtest",
      source_run_id: DEMO_GUIDE_RUN_ID,
      title: zh ? "示例组合回测" : "Demo portfolio backtest",
      status: "completed",
      created_at: DEMO_UPDATED_AT,
      updated_at: DEMO_UPDATED_AT,
      entry_date: "2026-01-16",
      end_date: "2026-04-22",
      benchmark_ticker: "SPY",
      metrics: {
        initial_capital: 100000,
        final_value: 109400,
        benchmark_final_value: 105100,
        total_return_pct: 9.4,
        benchmark_return_pct: 5.1,
        excess_return_pct: 4.3,
        annualized_return_pct: 38.2,
        max_drawdown_pct: -6.4,
        trading_days: 66,
      },
      requested_count: 3,
      coverage_count: 3,
      dropped_tickers: [],
    },
    points,
    positions: [
      createDemoPosition("MSFT", 50, 6.8, 3.4),
      createDemoPosition("AAPL", 30, 3.2, 1.0),
      createDemoPosition("NVDA", 20, 14.5, 2.9),
    ],
    meta: {
      assumptions: {
        transaction_cost_bps: 5,
        slippage_bps: 5,
        dividend_mode: "cash",
        dividend_included: true,
        tax_mode: "none",
        rebalance: "none",
      },
      dividend_coverage: { dividend_included: true },
      tax_summary: { tax_amount: 0 },
      attribution_summary: zh
        ? ["示例组合跑赢 SPY，主要来自 MSFT 和 NVDA。", "最大回撤仍需要关注，NVDA 是主要波动来源。"]
        : ["The demo basket outperformed SPY, mainly from MSFT and NVDA.", "Drawdown still matters; NVDA is the main volatility contributor."],
      data_limitations: zh
        ? ["这是静态引导演示数据，不代表实时市场建议。"]
        : ["This is static guide data and not a live market recommendation."],
    },
  };
}

/** 生成单只股票的示例回测持仓。 */
function createDemoPosition(ticker: string, weight: number, returnPct: number, contributionPct: number) {
  return {
    ticker,
    weight,
    verdict: ticker === "MSFT" ? "Core" : "Satellite",
    entry_date: "2026-01-16",
    entry_price: 100,
    latest_price: 100 + returnPct,
    shares: weight * 10,
    invested_amount: weight * 1000,
    current_value: weight * 1000 * (1 + returnPct / 100),
    return_pct: returnPct,
    contribution_pct: contributionPct,
    timeseries: [
      { point_date: "2026-01-16", close_price: 100, daily_return_pct: 0, cumulative_return_pct: 0, contribution_pct: 0 },
      { point_date: "2026-02-16", close_price: 101 + returnPct * 0.2, daily_return_pct: 1.1, cumulative_return_pct: returnPct * 0.25, contribution_pct: contributionPct * 0.25 },
      { point_date: "2026-03-16", close_price: 102 + returnPct * 0.55, daily_return_pct: 1.4, cumulative_return_pct: returnPct * 0.6, contribution_pct: contributionPct * 0.6 },
      { point_date: "2026-04-22", close_price: 100 + returnPct, daily_return_pct: 0.9, cumulative_return_pct: returnPct, contribution_pct: contributionPct },
    ],
  };
}

/** 生成前端演示用的历史摘要。 */
export function createDemoGuideAuditSummary(locale: Locale): RunAuditSummary {
  return {
    run_id: DEMO_GUIDE_RUN_ID,
    title: locale === "zh" ? "新手引导演示研究" : "Guided demo research",
    status: "completed",
    query: getDemoGuideQuery(locale),
    report_mode: "deepseek_demo",
    research_mode: "realtime",
    as_of_date: null,
    top_pick: "MSFT",
    confidence_level: locale === "zh" ? "中等" : "medium",
    validation_flags: [],
    coverage_flags: [],
    used_sources: ["frontend_demo"],
    degraded_modules: [],
    memory_applied_fields: [],
  };
}
