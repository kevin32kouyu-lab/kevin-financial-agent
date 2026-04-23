import { expect, test, type Page } from "@playwright/test";

const routes = ["/terminal", "/terminal/conclusion", "/terminal/backtest", "/terminal/archive"];
const now = "2026-04-22T08:00:00Z";

const demoRun = {
  id: "demo-run",
  mode: "agent",
  workflow_key: "agent",
  status: "completed",
  title: "Demo research",
  created_at: now,
  updated_at: now,
  started_at: now,
  finished_at: now,
  parent_run_id: null,
  error_message: null,
  report_mode: "terminal",
  attempt_count: 1,
  metadata: {},
};

const demoResult = {
  query: "Which US quality stocks should I focus on for a six month demo?",
  research_context: { research_mode: "historical", as_of_date: "2026-01-15" },
  report_briefing: {
    meta: {
      title: "Demo Investment Report",
      subtitle: "Demo report",
      confidence_level: "medium",
      research_mode: "historical",
      as_of_date: "2026-01-15",
      evidence_summary: {
        headline: "Evidence is enough for a demo.",
        items: ["Mocked price and filing evidence."],
        source_points: ["Mock source, 2026-01-15"],
      },
      validation_summary: {
        headline: "Validation passed with demo caveats.",
        items: ["Historical archive is mocked in this test."],
      },
      safety_summary: {
        headline: "No internal cards should block the terminal view.",
        used_sources: ["Mock data"],
        degraded_modules: [],
      },
      user_profile: { summary: "Moderate risk, six month horizon." },
      ticker_count: 1,
    },
    executive: {
      display_call: "Focus on MSFT first.",
      primary_call: "Focus on MSFT first.",
      display_action_summary: "Start with a small watchlist.",
      action_summary: "Start with a small watchlist.",
      top_pick: "MSFT",
      market_stance: "Selective",
      mandate_fit_score: 82,
    },
    macro: {
      risk_headline: "Macro risk is moderate.",
      regime: "neutral",
      vix: 16,
    },
    scoreboard: [
      {
        ticker: "MSFT",
        company_name: "Microsoft",
        latest_price: 420,
        composite_score: 88,
        verdict_label: "Top pick",
      },
    ],
    ticker_cards: [
      {
        ticker: "MSFT",
        company_name: "Microsoft",
        verdict_label: "Top pick",
        thesis: "Quality compounder.",
        fit_reason: "Matches moderate risk.",
        evidence_points: ["Strong cash flow."],
        caution_points: ["Valuation risk."],
        technical_summary: "Constructive.",
        news_narrative: "Product news remains supportive.",
        audit_summary: "No major filing warning.",
        execution: "Scale in gradually.",
      },
    ],
    risk_register: [{ category: "Valuation", ticker: "MSFT", summary: "Multiple compression risk." }],
  },
  final_report: "Full memo text for the PDF export test.",
  report_outputs: {
    investment: {
      markdown: "# Institutional Investment Research Report\n\n## Executive Summary\n\nFocus on MSFT first.",
      charts: {
        portfolio_allocation: { status: "ready", items: [{ ticker: "MSFT", weight: 70 }] },
        candidate_score_comparison: { status: "ready", items: [{ ticker: "MSFT", composite: 88 }] },
        portfolio_vs_benchmark_backtest: { status: "missing", message: "Data is insufficient; this chart was not generated." },
        risk_contribution: { status: "ready", items: [{ name: "Valuation", value: 60 }] },
      },
    },
    development: {
      markdown: "# Agentic Research Development Report\n\n## Agent Workflow\n\n- EvidenceAgent: retrieved mock evidence.\n\n## RAG Evidence Coverage\n\n- Retrieved evidence items: 1",
      diagnostics: {
        agent_count: 6,
        evidence_count: 1,
        validation_check_count: 0,
        backtest_status: "missing",
      },
    },
  },
};

const demoBacktest = {
  summary: {
    id: "bt-1",
    source_run_id: "demo-run",
    mode: "replay",
    entry_date: "2026-01-16",
    end_date: "2026-04-22",
    metrics: {
      total_return_pct: 8.4,
      benchmark_return_pct: 5.1,
      excess_return_pct: 3.3,
    },
  },
  positions: [],
  points: [
    { date: "2026-01-16", portfolio_value: 100, benchmark_value: 100 },
    { date: "2026-04-22", portfolio_value: 108.4, benchmark_value: 105.1 },
  ],
  meta: {
    assumptions: {
      transaction_cost_bps: 10,
      slippage_bps: 5,
      dividend_mode: "cash_only",
      rebalance: "buy_and_hold",
    },
  },
};

const demoDetail = {
  run: demoRun,
  steps: [{ step_key: "report", label: "Report", status: "completed", position: 1, created_at: now, updated_at: now }],
  artifacts: [],
  result: demoResult,
};

async function mockTerminalApis(
  page: Page,
  options: {
    emptyBacktests?: boolean;
    captureBacktestPosts?: string[];
    capturePdfRequests?: string[];
    authEmail?: string | null;
    captureLoginPosts?: string[];
    captureLinkMemoryPosts?: string[];
  } = {},
) {
  await page.route("**/api/v1/agent/runtime-config", (route) =>
    route.fulfill({ json: { provider: "mock", api_key_configured: true, model: "mock", base_url: "", route_mode: "demo", billing_mode: "demo", official_sdk: "mock" } }),
  );
  await page.route("**/api/v1/data/status", (route) =>
    route.fulfill({ json: { dataset: "mock", records: 1, source: "mock", last_refresh_count: 1, seed_path: "", database_path: "", fallback_enabled: true, live_sources: ["mock"] } }),
  );
  await page.route("**/api/v1/profile/preferences", (route) =>
    route.fulfill({ json: { profile_id: "demo-profile", updated_at: null, locale: "en", memory_applied_fields: [], values: {} } }),
  );
  await page.route("**/api/v1/auth/me", (route) =>
    route.fulfill({
      json: {
        user: options.authEmail
          ? {
              id: "user-1",
              email: options.authEmail,
              role: "user",
              created_at: now,
            }
          : null,
      },
    }),
  );
  await page.route("**/api/v1/auth/login", async (route) => {
    options.captureLoginPosts?.push(route.request().method());
    await route.fulfill({
      json: {
        user: {
          id: "user-1",
          email: options.authEmail || "analyst@example.com",
          role: "user",
          created_at: now,
        },
        session_token: "session-token",
        expires_at: now,
      },
    });
  });
  await page.route("**/api/v1/auth/register", async (route) => {
    options.captureLoginPosts?.push(route.request().method());
    await route.fulfill({
      json: {
        user: {
          id: "user-1",
          email: options.authEmail || "analyst@example.com",
          role: "user",
          created_at: now,
        },
        session_token: "session-token",
        expires_at: now,
      },
    });
  });
  await page.route("**/api/v1/auth/logout", (route) => route.fulfill({ json: { ok: true } }));
  await page.route("**/api/v1/profile/link-client-memory", async (route) => {
    options.captureLinkMemoryPosts?.push(route.request().method());
    await route.fulfill({
      json: {
        profile_id: "user:user-1",
        updated_at: now,
        locale: "en",
        memory_applied_fields: ["risk_tolerance"],
        values: {
          risk_tolerance: "medium",
        },
      },
    });
  });
  await page.route("**/api/v1/runs/history?**", (route) => route.fulfill({ json: { items: [demoRun] } }));
  await page.route("**/api/runs?**", (route) => route.fulfill({ json: { items: [demoRun] } }));
  await page.route("**/api/runs/demo-run", (route) => route.fulfill({ json: demoDetail }));
  await page.route("**/api/runs/demo-run/artifacts", (route) => route.fulfill({ json: { run_id: "demo-run", artifacts: [] } }));
  await page.route("**/api/v1/runs/demo-run/audit-summary", (route) =>
    route.fulfill({ json: { run_id: "demo-run", title: "Demo research", status: "completed", query: demoResult.query, research_mode: "historical", as_of_date: "2026-01-15", top_pick: "MSFT", confidence_level: "medium", validation_flags: [], coverage_flags: [], used_sources: ["mock"], degraded_modules: [], memory_applied_fields: [] } }),
  );
  await page.route("**/api/v1/backtests?**", (route) =>
    route.fulfill({ json: { items: options.emptyBacktests ? [] : [{ id: "bt-1", source_run_id: "demo-run", mode: "replay" }] } }),
  );
  await page.route("**/api/v1/backtests/bt-1", (route) => route.fulfill({ json: demoBacktest }));
  await page.route("**/api/v1/backtests", async (route) => {
    options.captureBacktestPosts?.push(route.request().method());
    await route.fulfill({ json: demoBacktest });
  });
  await page.route("**/api/v1/runs/demo-run/export/pdf**", async (route) => {
    options.capturePdfRequests?.push(route.request().url());
    await route.fulfill({
      status: 200,
      headers: { "Content-Type": "application/pdf", "Content-Disposition": 'attachment; filename="investment-report-demo.pdf"' },
      body: "%PDF-1.4\n% demo\n",
    });
  });
}

for (const route of routes) {
  test(`${route} returns the SPA shell`, async ({ page }) => {
    const response = await page.request.get(route);
    expect(response.ok()).toBeTruthy();

    await page.goto(route, { waitUntil: "commit" });
    await expect(page.locator("#root")).toBeAttached();
  });
}

test("terminal conclusion page does not expose internal system cards by default", async ({ page }) => {
  await page.goto("/terminal/conclusion", { waitUntil: "commit" });
  await expect(page.locator("#root")).toBeAttached();
  await expect(page.getByText(/系统理解到的目标|长期记忆|安全与数据覆盖/)).toHaveCount(0);
});

test("landing page presents a concise user-first entry", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Ask once, get verifiable investment research" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Ask once", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "See verdict", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Verify before acting", exact: true })).toBeVisible();
  await expect(page.getByText(/project|PPT|presentation/i)).toHaveCount(0);
});

test("ask page shows mandate chips and a clear four-step preview", async ({ page }) => {
  await mockTerminalApis(page);
  await page.goto("/terminal");
  await expect(page.getByRole("heading", { name: "Ask your investment question directly" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Single question" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Portfolio research" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Ongoing tracking" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Low risk" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Long term" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "What the system will do" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Screen the universe" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Cross-check evidence" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Generate both reports" })).toBeVisible();
  await page.getByRole("button", { name: "Portfolio research" }).click();
  await expect(page.getByText("Get a sized basket instead of a single ticker.")).toBeVisible();
  await page.getByRole("button", { name: "Ongoing tracking" }).click();
  await expect(page.getByText("Bring back an earlier thesis and monitor what changed.")).toBeVisible();
});

test("terminal route tabs switch pages without a full page reload", async ({ page }) => {
  await mockTerminalApis(page);
  await page.goto("/terminal/conclusion?run=demo-run");
  await expect(page.getByRole("heading", { name: "Focus on MSFT", exact: true })).toBeVisible();
  await page.evaluate(() => {
    window.sessionStorage.setItem("terminal-reload-sentinel", "kept");
    (window as unknown as { __terminalReloadSentinel?: string }).__terminalReloadSentinel = "kept";
  });

  await page.getByRole("link", { name: "Backtest", exact: true }).click();

  await expect(page).toHaveURL(/\/terminal\/backtest\?run=demo-run/);
  await expect.poll(() => page.evaluate(() => (window as unknown as { __terminalReloadSentinel?: string }).__terminalReloadSentinel)).toBe("kept");
});

test("opening a historical conclusion does not auto-create a backtest", async ({ page }) => {
  const backtestPosts: string[] = [];
  await mockTerminalApis(page, { emptyBacktests: true, captureBacktestPosts: backtestPosts });

  await page.goto("/terminal/conclusion?run=demo-run");
  await expect(page.getByRole("heading", { name: "Focus on MSFT", exact: true })).toBeVisible();

  expect(backtestPosts).toEqual([]);
});

test("terminal PDF export uses the backend PDF endpoint", async ({ page }) => {
  const pdfRequests: string[] = [];
  await mockTerminalApis(page, { capturePdfRequests: pdfRequests });

  await page.goto("/terminal/conclusion?run=demo-run");
  await expect(page.getByRole("button", { name: "Export Investment PDF" })).toBeVisible();
  await page.getByRole("button", { name: "Export Investment PDF" }).click();

  await expect.poll(() => pdfRequests.length).toBe(1);
  expect(pdfRequests[0]).toContain("/api/v1/runs/demo-run/export/pdf");
  expect(pdfRequests[0]).toContain("kind=investment");
});

test("terminal conclusion page switches between investment and development reports", async ({ page }) => {
  const pdfRequests: string[] = [];
  await mockTerminalApis(page, { capturePdfRequests: pdfRequests });

  await page.goto("/terminal/conclusion?run=demo-run");
  await expect(page.getByRole("tab", { name: "Investment Report" })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByText("Recommended Portfolio Allocation")).toBeVisible();

  await page.getByRole("tab", { name: "Development Report" }).click();
  await expect(page.getByRole("tab", { name: "Development Report" })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByText("Agent Workflow")).toBeVisible();
  await expect(page.getByText("EvidenceAgent: retrieved mock evidence.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "RAG evidence", exact: true })).toBeVisible();
  await expect(page.getByText("1", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Export Development PDF" }).click();
  await expect.poll(() => pdfRequests.length).toBe(1);
  expect(pdfRequests[0]).toContain("kind=development");
});

test("conclusion page surfaces a user-friendly trust summary", async ({ page }) => {
  await mockTerminalApis(page);

  await page.goto("/terminal/conclusion?run=demo-run");
  const trustBand = page.locator(".terminal-proof-band");
  await expect(page.getByRole("heading", { name: "Why this is credible" })).toBeVisible();
  await expect(trustBand.getByText("Evidence items", { exact: true })).toBeVisible();
  await expect(trustBand.getByText("Latest evidence", { exact: true })).toBeVisible();
  await expect(trustBand.getByText("Validation", { exact: true })).toBeVisible();
  await expect(trustBand.getByText("Backtest", { exact: true })).toBeVisible();
});

test("account panel can log in and link browser memory", async ({ page }) => {
  const loginPosts: string[] = [];
  const linkMemoryPosts: string[] = [];
  await mockTerminalApis(page, { captureLoginPosts: loginPosts, captureLinkMemoryPosts: linkMemoryPosts });

  await page.goto("/terminal");
  await page.getByRole("button", { name: "Account" }).click();
  const accountSheet = page.locator(".account-panel-sheet");
  await accountSheet.getByLabel("Email").fill("analyst@example.com");
  await accountSheet.getByLabel("Password").fill("password123");
  await accountSheet.getByRole("button", { name: "Sign in" }).last().click();

  await expect(page.getByText("analyst@example.com")).toBeVisible();
  await page.getByRole("button", { name: "Sync browser memory" }).click();
  await expect(page.getByText("Memory synced")).toBeVisible();
  expect(loginPosts).toEqual(["POST"]);
  expect(linkMemoryPosts).toEqual(["POST"]);
});

test("loaded backtest appears on the conclusion page without auto-creating a new one", async ({ page }) => {
  const backtestPosts: string[] = [];
  await mockTerminalApis(page, { captureBacktestPosts: backtestPosts });

  await page.goto("/terminal/backtest?run=demo-run");
  await expect(page.getByText("Portfolio return", { exact: true })).toBeVisible();
  await expect(page.getByText("Portfolio", { exact: true })).toBeVisible();
  await expect(backtestPosts).toEqual([]);

  await page.getByRole("link", { name: "Research Conclusion", exact: true }).click();
  await expect(page).toHaveURL(/\/terminal\/conclusion\?run=demo-run/);
  await expect(page.getByText("Portfolio vs Benchmark Backtest")).toBeVisible();
  await expect(page.getByText("Portfolio", { exact: true })).toBeVisible();
  await expect(page.getByText("Benchmark", { exact: true })).toBeVisible();
  await expect(page.getByText("Data is insufficient; this chart was not generated.")).toHaveCount(0);
});

test("archive can continue a previous run without starting from scratch", async ({ page }) => {
  await mockTerminalApis(page);

  await page.goto("/terminal/archive?run=demo-run");
  await page.getByRole("button", { name: "Continue follow-up" }).first().click();

  await expect(page).toHaveURL(/\/terminal$/);
  await expect(page.getByRole("textbox", { name: "Investment request" })).toHaveValue(/continue monitoring/i);
});
