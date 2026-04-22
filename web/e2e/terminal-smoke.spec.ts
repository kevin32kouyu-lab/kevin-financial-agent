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
};

const demoDetail = {
  run: demoRun,
  steps: [{ step_key: "report", label: "Report", status: "completed", position: 1, created_at: now, updated_at: now }],
  artifacts: [],
  result: demoResult,
};

async function mockTerminalApis(
  page: Page,
  options: { emptyBacktests?: boolean; captureBacktestPosts?: string[]; capturePdfRequests?: string[] } = {},
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
  await page.route("**/api/v1/runs/history?**", (route) => route.fulfill({ json: { items: [demoRun] } }));
  await page.route("**/api/runs?**", (route) => route.fulfill({ json: { items: [demoRun] } }));
  await page.route("**/api/runs/demo-run", (route) => route.fulfill({ json: demoDetail }));
  await page.route("**/api/runs/demo-run/artifacts", (route) => route.fulfill({ json: { run_id: "demo-run", artifacts: [] } }));
  await page.route("**/api/v1/runs/demo-run/audit-summary", (route) =>
    route.fulfill({ json: { run_id: "demo-run", title: "Demo research", status: "completed", query: demoResult.query, research_mode: "historical", as_of_date: "2026-01-15", top_pick: "MSFT", confidence_level: "medium", validation_flags: [], coverage_flags: [], used_sources: ["mock"], degraded_modules: [], memory_applied_fields: [] } }),
  );
  await page.route("**/api/v1/backtests?**", (route) => route.fulfill({ json: { items: options.emptyBacktests ? [] : [] } }));
  await page.route("**/api/v1/backtests", async (route) => {
    options.captureBacktestPosts?.push(route.request().method());
    await route.fulfill({ json: { summary: { id: "bt-1", source_run_id: "demo-run", mode: "replay", entry_date: "2026-01-16", end_date: "2026-04-22", metrics: {} }, positions: [], points: [], meta: {} } });
  });
  await page.route("**/api/v1/runs/demo-run/export/pdf", async (route) => {
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
  await expect(page.getByRole("button", { name: "Export PDF" })).toBeVisible();
  await page.getByRole("button", { name: "Export PDF" }).click();

  await expect.poll(() => pdfRequests.length).toBe(1);
  expect(pdfRequests[0]).toContain("/api/v1/runs/demo-run/export/pdf");
});
