/** 历史页刷新测试：确认后台同步不会把已有列表替换成加载态。 */
import { expect, test, type Page, type Route } from "@playwright/test";

const now = "2026-04-22T08:00:00Z";
const productTourStorageKey = "financial-agent-product-tour-v1";

const archivedRun = {
  id: "archive-run",
  mode: "agent",
  workflow_key: "agent",
  status: "completed",
  title: "Archive flicker demo",
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

const archivedDetail = {
  run: archivedRun,
  steps: [{ step_key: "report", label: "Report", status: "completed", position: 1, created_at: now, updated_at: now }],
  artifacts: [],
  result: {
    query: "Review my saved investment research.",
    report_briefing: {
      executive: {
        top_pick: "MSFT",
        display_call: "Focus on MSFT first.",
        display_action_summary: "Keep watching the thesis.",
      },
      meta: {
        confidence_level: "medium",
        evidence_summary: { headline: "Evidence is available." },
        validation_summary: { headline: "Validation is available." },
      },
      macro: { risk_headline: "Risk is moderate." },
      scoreboard: [{ ticker: "MSFT", composite_score: 82, verdict_label: "Top pick" }],
    },
  },
};

/** 安装历史页需要的最小接口模拟。 */
async function mockArchiveApis(page: Page) {
  let historyRequestCount = 0;
  let slowFutureHistory = false;
  const fulfillHistory = async (route: Route) => {
    historyRequestCount += 1;
    if (slowFutureHistory) {
      await new Promise((resolve) => setTimeout(resolve, 1200));
    }
    await route.fulfill({ json: { items: [archivedRun] } });
  };

  await page.route("**/api/v1/agent/runtime-config", (route) =>
    route.fulfill({ json: { provider: "mock", api_key_configured: true, model: "mock", base_url: "", route_mode: "demo", billing_mode: "demo", official_sdk: "mock" } }),
  );
  await page.route("**/api/v1/data/status", (route) =>
    route.fulfill({ json: { dataset: "mock", records: 1, source: "mock", last_refresh_count: 1, seed_path: "", database_path: "", fallback_enabled: true, live_sources: ["mock"] } }),
  );
  await page.route("**/api/v1/profile/preferences", (route) =>
    route.fulfill({ json: { profile_id: "demo-profile", updated_at: null, locale: "en", memory_applied_fields: [], values: {} } }),
  );
  await page.route("**/api/v1/auth/me", (route) => route.fulfill({ json: { user: null } }));
  await page.route("**/api/v1/runs/history?**", fulfillHistory);
  await page.route("**/api/runs?**", fulfillHistory);
  await page.route("**/api/runs/archive-run", (route) => route.fulfill({ json: archivedDetail }));
  await page.route("**/api/runs/archive-run/artifacts", (route) => route.fulfill({ json: { run_id: "archive-run", artifacts: [] } }));
  await page.route("**/api/v1/runs/archive-run/audit-summary", (route) =>
    route.fulfill({
      json: {
        run_id: "archive-run",
        title: "Archive flicker demo",
        status: "completed",
        query: "Review my saved investment research.",
        research_mode: "realtime",
        as_of_date: null,
        top_pick: "MSFT",
        confidence_level: "medium",
        validation_flags: [],
        coverage_flags: [],
        used_sources: ["mock"],
        degraded_modules: [],
        memory_applied_fields: [],
      },
    }),
  );

  return {
    count: () => historyRequestCount,
    slowFutureRequests: () => {
      slowFutureHistory = true;
    },
  };
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript((storageKey) => {
    window.localStorage.setItem(storageKey, "done");
    const sources: EventTarget[] = [];

    class ControlledEventSource extends EventTarget {
      url: string;
      onerror: (() => void) | null = null;

      constructor(url: string | URL) {
        super();
        this.url = String(url);
        sources.push(this);
      }

      close() {}
    }

    window.EventSource = ControlledEventSource as typeof EventSource;
    (window as unknown as { __emitRunEvent?: () => void }).__emitRunEvent = () => {
      for (const source of sources) {
        source.dispatchEvent(
          new MessageEvent("step.completed", {
            data: JSON.stringify({ run_id: "archive-run" }),
            lastEventId: "7",
          }),
        );
      }
    };
  }, productTourStorageKey);
});

test("archive keeps existing runs visible while background history refresh is pending", async ({ page }) => {
  const historyRequests = await mockArchiveApis(page);

  await page.goto("/terminal/archive?run=archive-run");
  await expect(page.getByRole("heading", { name: "Archive flicker demo" })).toBeVisible();

  const countBeforeRefresh = historyRequests.count();
  historyRequests.slowFutureRequests();
  await page.evaluate(() => (window as unknown as { __emitRunEvent: () => void }).__emitRunEvent());
  await expect.poll(historyRequests.count).toBeGreaterThan(countBeforeRefresh);

  await expect(page.getByRole("heading", { name: "Archive flicker demo" })).toBeVisible();
  await expect(page.getByText("Loading archive...")).toHaveCount(0);
});
