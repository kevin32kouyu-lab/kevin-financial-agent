# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: terminal-smoke.spec.ts >> terminal PDF export uses the backend PDF endpoint
- Location: web\e2e\terminal-smoke.spec.ts:588:1

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByRole('button', { name: 'Export Simple PDF' })
Expected: visible
Timeout: 5000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" with timeout 5000ms
  - waiting for getByRole('button', { name: 'Export Simple PDF' })

```

# Page snapshot

```yaml
- generic [ref=e3]:
  - banner [ref=e4]:
    - generic [ref=e5]:
      - paragraph [ref=e6]: ROSE Capital Research
      - strong [ref=e7]: Investment Research Terminal
    - generic [ref=e8]:
      - link "Home" [ref=e9] [cursor=pointer]:
        - /url: /
      - generic [ref=e10]:
        - generic [ref=e11]: UI language
        - combobox "UI language" [ref=e12]:
          - option "中文"
          - option "English" [selected]
      - button "Motion On" [ref=e13] [cursor=pointer]
      - button "Guide" [ref=e14] [cursor=pointer]
      - button "Account" [ref=e17] [cursor=pointer]
  - navigation [ref=e18]:
    - link "Start Research" [ref=e19] [cursor=pointer]:
      - /url: /terminal?run=demo-run
    - link "Research Conclusion" [ref=e20] [cursor=pointer]:
      - /url: /terminal/conclusion?run=demo-run
    - link "Backtest" [ref=e21] [cursor=pointer]:
      - /url: /terminal/backtest?run=demo-run
    - link "Archive" [ref=e22] [cursor=pointer]:
      - /url: /terminal/archive?run=demo-run
  - generic [ref=e23]:
    - article [ref=e24]:
      - generic [ref=e25]:
        - generic [ref=e26]:
          - paragraph [ref=e27]: Research conclusion
          - heading "Focus on MSFT" [level=1] [ref=e28]
          - paragraph [ref=e29]: Focus on MSFT first.
        - generic [ref=e30]:
          - link "Open backtest" [ref=e31] [cursor=pointer]:
            - /url: /terminal/backtest?run=demo-run
          - link "Open archive" [ref=e32] [cursor=pointer]:
            - /url: /terminal/archive?run=demo-run
          - button "Track this thesis" [ref=e33] [cursor=pointer]
      - paragraph [ref=e34]: Validation passed with demo caveats.
      - generic [ref=e35]:
        - article [ref=e36]:
          - text: Verdict
          - strong [ref=e37]: Focus on MSFT first.
        - article [ref=e38]:
          - text: Risk in one line
          - strong [ref=e39]: Macro risk is moderate.
        - article [ref=e40]:
          - text: Suggested action
          - strong [ref=e41]: Start with a small watchlist.
        - article [ref=e42]:
          - text: Top pick
          - strong [ref=e43]: MSFT
        - article [ref=e44]:
          - text: Mandate fit
          - strong [ref=e45]: "82"
        - article [ref=e46]:
          - text: Confidence
          - strong [ref=e47]: medium
      - generic [ref=e48]:
        - generic [ref=e50]:
          - paragraph [ref=e51]: Recommended holdings
          - heading "How the recommendation is sized" [level=2] [ref=e52]
        - generic [ref=e53]:
          - text: Recommended holdings
          - strong [ref=e54]: MSFT
          - paragraph [ref=e55]: No explicit weights yet; start from the top pick.
      - generic [ref=e56]:
        - generic [ref=e58]:
          - paragraph [ref=e59]: Why this is credible
          - heading "Why this is credible" [level=2] [ref=e60]
        - generic [ref=e61]:
          - article [ref=e62]:
            - text: Evidence items
            - strong [ref=e63]: "0"
            - paragraph [ref=e64]: 1 candidates checked.
          - article [ref=e65]:
            - text: Latest evidence
            - strong [ref=e66]: Undated
            - paragraph [ref=e67]: Selective
          - article [ref=e68]:
            - text: Validation
            - strong [ref=e69]: Checked
            - paragraph [ref=e70]: No major degraded coverage.
          - article [ref=e71]:
            - text: Backtest
            - strong [ref=e72]: Not ready
            - paragraph [ref=e73]: Open the backtest page when you need a replay check.
    - complementary [ref=e74]:
      - article [ref=e75]:
        - generic [ref=e77]:
          - paragraph [ref=e78]: Your investment request
          - heading "The request behind this run" [level=2] [ref=e79]
        - generic [ref=e80]: Which US quality stocks should I focus on for a six month demo?
        - generic [ref=e81]:
          - generic [ref=e82]: Historical research
          - generic [ref=e83]: "as_of: 2026-01-15"
          - generic [ref=e84]: Status completed
      - article [ref=e85]:
        - generic [ref=e86]:
          - generic [ref=e87]:
            - paragraph [ref=e88]: Task progress
            - heading "Completed" [level=2] [ref=e89]
          - strong [ref=e90]: 100%
        - generic [ref=e91]:
          - generic [ref=e92]: Current stage
          - strong [ref=e93]: Completed
        - paragraph [ref=e96]: Report is ready for review and export.
        - generic [ref=e97]:
          - generic [ref=e98]: Latest update
          - strong [ref=e99]: 4/22/2026, 16:00:00
  - generic [ref=e101]:
    - generic [ref=e102]:
      - generic [ref=e103]:
        - paragraph [ref=e104]: Formal memo
        - heading "Institutional Investment Research Report" [level=2] [ref=e105]
        - paragraph [ref=e106]: Research terminal / portfolio decision memo
      - generic [ref=e107]:
        - generic [ref=e108]:
          - generic [ref=e109]: "Mode: Historical replay"
          - generic [ref=e110]: "as_of: 2026-01-15"
          - generic [ref=e111]: Mandate fit 82.0
          - generic [ref=e112]: Candidates 1
        - generic [ref=e113]:
          - button "Export Investment PDF" [ref=e114] [cursor=pointer]
          - button "Export Development PDF" [ref=e115] [cursor=pointer]
          - button "Download HTML" [ref=e116] [cursor=pointer]
    - tablist "Report type" [ref=e117]:
      - tab "Investment Report" [selected] [ref=e118] [cursor=pointer]
      - tab "Development Report" [ref=e119] [cursor=pointer]
    - navigation [ref=e120]:
      - link "Overview" [ref=e121] [cursor=pointer]:
        - /url: "#report-overview"
      - link "Charts" [ref=e122] [cursor=pointer]:
        - /url: "#report-charts"
      - link "Scoreboard" [ref=e123] [cursor=pointer]:
        - /url: "#report-scoreboard"
      - link "Coverage" [ref=e124] [cursor=pointer]:
        - /url: "#report-coverage"
      - link "Risk & Execution" [ref=e125] [cursor=pointer]:
        - /url: "#report-risks"
      - link "Full memo" [ref=e126] [cursor=pointer]:
        - /url: "#report-memo"
    - generic [ref=e127]:
      - generic [ref=e128]:
        - heading "Why this conclusion" [level=3] [ref=e129]
        - paragraph [ref=e130]: Evidence is enough for a demo.
        - list [ref=e131]:
          - listitem [ref=e132]: Mocked price and filing evidence.
        - generic [ref=e134]: Mock source, 2026-01-15
      - generic [ref=e135]:
        - heading "Read these caveats first" [level=3] [ref=e136]
        - paragraph [ref=e137]: Validation passed with demo caveats.
        - list [ref=e138]:
          - listitem [ref=e139]: Historical archive is mocked in this test.
    - generic [ref=e140]:
      - article [ref=e141]:
        - paragraph [ref=e142]: Executive verdict
        - heading "Focus on MSFT first." [level=3] [ref=e143]
        - paragraph [ref=e144]: Start with a small watchlist.
      - generic [ref=e145]:
        - generic [ref=e146]:
          - heading "Investor mandate" [level=3] [ref=e147]
          - paragraph [ref=e148]: Mandate summary unavailable.
          - paragraph [ref=e149]: "Top pick: MSFT"
          - paragraph [ref=e150]: "Score: 82.0"
        - generic [ref=e151]:
          - heading "Market stance" [level=3] [ref=e152]
          - paragraph [ref=e153]: "Regime: neutral"
          - paragraph [ref=e154]: "VIX: 16"
          - paragraph [ref=e155]: "Top pick: MSFT"
          - paragraph [ref=e156]: "Fit: 82.0"
        - generic [ref=e157]:
          - heading "Data provenance" [level=3] [ref=e158]
          - paragraph [ref=e159]: "Source: mock"
          - paragraph [ref=e160]: "Universe size: 1"
          - paragraph [ref=e161]: "Last refresh: N/A"
    - generic [ref=e163]:
      - article [ref=e164]:
        - generic [ref=e165]:
          - paragraph [ref=e166]: Report chart
          - heading "Recommended Portfolio Allocation" [level=3] [ref=e167]
        - generic [ref=e169]:
          - generic [ref=e170]: MSFT
          - strong [ref=e173]: 70.0%
      - article [ref=e174]:
        - generic [ref=e175]:
          - paragraph [ref=e176]: Report chart
          - heading "Candidate Score Comparison" [level=3] [ref=e177]
        - generic [ref=e179]:
          - generic [ref=e180]: MSFT
          - strong [ref=e183]: "88.0"
      - article [ref=e184]:
        - generic [ref=e185]:
          - paragraph [ref=e186]: Report chart
          - heading "Portfolio vs Benchmark Backtest" [level=3] [ref=e187]
        - paragraph [ref=e188]: Data is insufficient; this chart was not generated.
      - article [ref=e189]:
        - generic [ref=e190]:
          - paragraph [ref=e191]: Report chart
          - heading "Risk Contribution" [level=3] [ref=e192]
        - generic [ref=e194]:
          - generic [ref=e195]: Valuation
          - strong [ref=e198]: "60.0"
    - generic [ref=e200]:
      - paragraph [ref=e201]: Scoreboard
      - heading "Scoreboard" [level=3] [ref=e202]
    - table [ref=e204]:
      - rowgroup [ref=e205]:
        - row "Ticker Company Latest Score Fit Valuation Quality Momentum Risk Verdict" [ref=e206]:
          - columnheader "Ticker" [ref=e207]
          - columnheader "Company" [ref=e208]
          - columnheader "Latest" [ref=e209]
          - columnheader "Score" [ref=e210]
          - columnheader "Fit" [ref=e211]
          - columnheader "Valuation" [ref=e212]
          - columnheader "Quality" [ref=e213]
          - columnheader "Momentum" [ref=e214]
          - columnheader "Risk" [ref=e215]
          - columnheader "Verdict" [ref=e216]
      - rowgroup [ref=e217]:
        - row "MSFT Microsoft 420 88.0 N/A N/A N/A N/A N/A Top pick" [ref=e218]:
          - cell "MSFT" [ref=e219]
          - cell "Microsoft" [ref=e220]
          - cell "420" [ref=e221]
          - cell "88.0" [ref=e222]
          - cell "N/A" [ref=e223]
          - cell "N/A" [ref=e224]
          - cell "N/A" [ref=e225]
          - cell "N/A" [ref=e226]
          - cell "N/A" [ref=e227]
          - cell "Top pick" [ref=e228]:
            - generic [ref=e229]: Top pick
    - generic [ref=e231]:
      - paragraph [ref=e232]: Coverage
      - heading "Ticker cards" [level=3] [ref=e233]
    - article [ref=e235]:
      - generic [ref=e236]:
        - generic [ref=e237]:
          - paragraph [ref=e238]: MSFT
          - heading "Microsoft" [level=3] [ref=e239]
          - paragraph [ref=e240]: N/A
        - generic [ref=e241]: Top pick
      - generic [ref=e242]:
        - generic [ref=e243]:
          - generic [ref=e245]: Score
          - strong [ref=e246]: N/A
        - generic [ref=e247]:
          - generic [ref=e249]: Fit
          - strong [ref=e250]: N/A
        - generic [ref=e251]:
          - generic [ref=e253]: Valuation
          - strong [ref=e254]: N/A
        - generic [ref=e255]:
          - generic [ref=e257]: Quality
          - strong [ref=e258]: N/A
        - generic [ref=e259]:
          - generic [ref=e261]: Momentum
          - strong [ref=e262]: N/A
        - generic [ref=e263]:
          - generic [ref=e265]: Risk
          - strong [ref=e266]: N/A
      - generic [ref=e267]:
        - generic [ref=e268]:
          - generic [ref=e269]: Thesis
          - paragraph [ref=e270]: Quality compounder.
        - generic [ref=e271]:
          - generic [ref=e272]: Fit reason
          - paragraph [ref=e273]: Matches moderate risk.
      - generic [ref=e274]:
        - generic [ref=e275]: Evidence summary
        - list [ref=e276]:
          - listitem [ref=e277]: Strong cash flow.
      - generic [ref=e278]:
        - generic [ref=e279]:
          - generic [ref=e280]: Technical / News
          - paragraph [ref=e281]: Constructive.
        - generic [ref=e282]:
          - generic [ref=e283]: News
          - paragraph [ref=e284]: Product news remains supportive.
        - generic [ref=e285]:
          - generic [ref=e286]: Positioning proxy
          - paragraph [ref=e287]: N/A
        - generic [ref=e288]:
          - generic [ref=e289]: Audit
          - paragraph [ref=e290]: No major filing warning.
      - generic [ref=e291]:
        - generic [ref=e292]: Caveats
        - list [ref=e293]:
          - listitem [ref=e294]: Valuation risk.
      - generic [ref=e296]:
        - strong [ref=e297]: "Source:"
        - text: Tech Unknown source | News Unknown source | Smart Unknown source
      - generic [ref=e298]:
        - generic [ref=e299]: Execution
        - paragraph [ref=e300]: Scale in gradually.
    - generic [ref=e301]:
      - generic [ref=e302]:
        - generic [ref=e304]:
          - paragraph [ref=e305]: Risk register
          - heading "Risk register" [level=3] [ref=e306]
        - generic [ref=e308]:
          - strong [ref=e309]: Valuation / MSFT
          - paragraph [ref=e310]: Multiple compression risk.
      - generic [ref=e311]:
        - generic [ref=e313]:
          - paragraph [ref=e314]: Execution
          - heading "Execution plan" [level=3] [ref=e315]
        - paragraph [ref=e316]: Candidates 1; execution positions 0.
        - generic [ref=e317]: No allocation suggestion.
    - group [ref=e318]:
      - generic "Open full report" [ref=e319] [cursor=pointer]
```

# Test source

```ts
  493 |           );
  494 |         }, 40);
  495 |       }
  496 | 
  497 |       close() {}
  498 |     }
  499 | 
  500 |     window.EventSource = FakeEventSource as typeof EventSource;
  501 |   });
  502 |   await mockTerminalApis(page, {
  503 |     detailSequence: [staleRunningDetail as typeof demoDetail, demoDetail],
  504 |     historyItems: [runningRun],
  505 |   });
  506 | 
  507 |   await page.goto("/terminal/conclusion?run=demo-run");
  508 |   await expect(page.getByText("Refresh this run after an event.")).toBeVisible();
  509 |   await expect(page.getByRole("heading", { name: "Focus on MSFT", exact: true })).toBeVisible();
  510 | });
  511 | 
  512 | test("running detail refreshes without requiring a browser reload when events are missed", async ({ page }) => {
  513 |   await page.addInitScript(() => {
  514 |     class SilentEventSource extends EventTarget {
  515 |       url: string;
  516 |       onerror: (() => void) | null = null;
  517 | 
  518 |       constructor(url: string | URL) {
  519 |         super();
  520 |         this.url = String(url);
  521 |       }
  522 | 
  523 |       close() {}
  524 |     }
  525 | 
  526 |     window.EventSource = SilentEventSource as typeof EventSource;
  527 |   });
  528 |   await mockTerminalApis(page, {
  529 |     detailSequence: [staleRunningDetail as typeof demoDetail, demoDetail],
  530 |     historyItems: [runningRun],
  531 |   });
  532 | 
  533 |   await page.goto("/terminal/conclusion?run=demo-run");
  534 |   await expect(page.getByText("Refresh this run after an event.")).toBeVisible();
  535 |   await expect(page.getByRole("heading", { name: "Focus on MSFT", exact: true })).toBeVisible({ timeout: 6000 });
  536 | });
  537 | 
  538 | test("terminal route tabs switch pages without a full page reload", async ({ page }) => {
  539 |   await mockTerminalApis(page);
  540 |   await page.goto("/terminal/conclusion?run=demo-run");
  541 |   await expect(page.getByRole("heading", { name: "Focus on MSFT", exact: true })).toBeVisible();
  542 |   await page.evaluate(() => {
  543 |     window.sessionStorage.setItem("terminal-reload-sentinel", "kept");
  544 |     (window as unknown as { __terminalReloadSentinel?: string }).__terminalReloadSentinel = "kept";
  545 |   });
  546 | 
  547 |   await page.getByRole("link", { name: "Backtest", exact: true }).click();
  548 | 
  549 |   await expect(page).toHaveURL(/\/terminal\/backtest\?run=demo-run/);
  550 |   await expect.poll(() => page.evaluate(() => (window as unknown as { __terminalReloadSentinel?: string }).__terminalReloadSentinel)).toBe("kept");
  551 | });
  552 | 
  553 | test("run event stream includes client identity for anonymous research", async ({ page }) => {
  554 |   await page.addInitScript(() => {
  555 |     const NativeEventSource = window.EventSource;
  556 |     const captured: string[] = [];
  557 |     (window as unknown as { __eventSourceUrls?: string[] }).__eventSourceUrls = captured;
  558 |     class WrappedEventSource extends NativeEventSource {
  559 |       constructor(url: string | URL, eventSourceInitDict?: EventSourceInit) {
  560 |         captured.push(String(url));
  561 |         super(url, eventSourceInitDict);
  562 |       }
  563 |     }
  564 |     window.EventSource = WrappedEventSource as typeof EventSource;
  565 |   });
  566 | 
  567 |   await mockTerminalApis(page);
  568 |   await page.goto("/terminal/conclusion?run=demo-run");
  569 |   await expect(page.getByRole("heading", { name: "Focus on MSFT", exact: true })).toBeVisible();
  570 | 
  571 |   await expect.poll(() => page.evaluate(() => (window as unknown as { __eventSourceUrls?: string[] }).__eventSourceUrls?.length || 0)).toBe(1);
  572 |   const eventUrl = await page.evaluate(() => (window as unknown as { __eventSourceUrls?: string[] }).__eventSourceUrls?.[0] || "");
  573 | 
  574 |   expect(eventUrl).toContain("/api/runs/demo-run/events");
  575 |   expect(eventUrl).toContain("client_id=");
  576 | });
  577 | 
  578 | test("opening a historical conclusion does not auto-create a backtest", async ({ page }) => {
  579 |   const backtestPosts: string[] = [];
  580 |   await mockTerminalApis(page, { emptyBacktests: true, captureBacktestPosts: backtestPosts });
  581 | 
  582 |   await page.goto("/terminal/conclusion?run=demo-run");
  583 |   await expect(page.getByRole("heading", { name: "Focus on MSFT", exact: true })).toBeVisible();
  584 | 
  585 |   expect(backtestPosts).toEqual([]);
  586 | });
  587 | 
  588 | test("terminal PDF export uses the backend PDF endpoint", async ({ page }) => {
  589 |   const pdfRequests: string[] = [];
  590 |   await mockTerminalApis(page, { capturePdfRequests: pdfRequests });
  591 | 
  592 |   await page.goto("/terminal/conclusion?run=demo-run");
> 593 |   await expect(page.getByRole("button", { name: "Export Simple PDF" })).toBeVisible();
      |                                                                         ^ Error: expect(locator).toBeVisible() failed
  594 |   await page.getByRole("button", { name: "Export Simple PDF" }).click();
  595 | 
  596 |   await expect.poll(() => pdfRequests.length).toBe(1);
  597 |   expect(pdfRequests[0]).toContain("/api/v1/runs/demo-run/export/pdf");
  598 |   expect(pdfRequests[0]).toContain("kind=simple_investment");
  599 | });
  600 | 
  601 | test("terminal conclusion page switches between simple professional and development reports", async ({ page }) => {
  602 |   const pdfRequests: string[] = [];
  603 |   await mockTerminalApis(page, { capturePdfRequests: pdfRequests });
  604 | 
  605 |   await page.goto("/terminal/conclusion?run=demo-run");
  606 |   await expect(page.getByRole("tab", { name: "Simple Report" })).toHaveAttribute("aria-selected", "true");
  607 |   await expect(page.getByText("Focus on MSFT first.")).toBeVisible();
  608 |   await expect(page.getByText("Recommended Portfolio Allocation")).toBeVisible();
  609 | 
  610 |   await page.getByRole("tab", { name: "Professional Report" }).click();
  611 |   await expect(page.getByRole("tab", { name: "Professional Report" })).toHaveAttribute("aria-selected", "true");
  612 |   await expect(page.getByText("Candidate Scorecard")).toBeVisible();
  613 |   await expect(page.getByText("Risk Register")).toBeVisible();
  614 | 
  615 |   await page.getByRole("tab", { name: "Development Report" }).click();
  616 |   await expect(page.getByRole("tab", { name: "Development Report" })).toHaveAttribute("aria-selected", "true");
  617 |   await expect(page.getByText("Agent Workflow")).toBeVisible();
  618 |   await expect(page.getByText("EvidenceAgent: retrieved mock evidence.")).toBeVisible();
  619 |   await expect(page.getByRole("heading", { name: "RAG evidence", exact: true })).toBeVisible();
  620 |   await expect(page.getByText("1", { exact: true })).toBeVisible();
  621 | 
  622 |   await page.getByRole("button", { name: "Export Development PDF" }).click();
  623 |   await expect.poll(() => pdfRequests.length).toBe(1);
  624 |   expect(pdfRequests[0]).toContain("kind=development");
  625 | 
  626 |   await page.getByRole("tab", { name: "Professional Report" }).click();
  627 |   await page.getByRole("button", { name: "Export Professional PDF" }).click();
  628 |   await expect.poll(() => pdfRequests.length).toBe(2);
  629 |   expect(pdfRequests[1]).toContain("kind=professional_investment");
  630 | });
  631 | 
  632 | test("full memo content mounts only after the memo section is expanded", async ({ page }) => {
  633 |   await mockTerminalApis(page);
  634 | 
  635 |   await page.goto("/terminal/conclusion?run=demo-run");
  636 |   await expect(page.getByRole("heading", { name: "Focus on MSFT", exact: true })).toBeVisible();
  637 |   await expect(page.getByText("Full memo text for the PDF export test.")).toHaveCount(0);
  638 | 
  639 |   await page.locator("details#report-memo summary").click();
  640 |   await expect(page.getByText("Full memo text for the PDF export test.")).toBeVisible();
  641 | });
  642 | 
  643 | test("conclusion page surfaces a user-friendly trust summary", async ({ page }) => {
  644 |   await mockTerminalApis(page);
  645 | 
  646 |   await page.goto("/terminal/conclusion?run=demo-run");
  647 |   const trustBand = page.locator(".terminal-proof-band");
  648 |   await expect(page.getByRole("heading", { name: "Why this is credible" })).toBeVisible();
  649 |   await expect(trustBand.getByText("Evidence items", { exact: true })).toBeVisible();
  650 |   await expect(trustBand.getByText("Latest evidence", { exact: true })).toBeVisible();
  651 |   await expect(trustBand.getByText("Validation", { exact: true })).toBeVisible();
  652 |   await expect(trustBand.getByText("Backtest", { exact: true })).toBeVisible();
  653 | });
  654 | 
  655 | test("account panel can log in and link browser memory", async ({ page }) => {
  656 |   const loginPosts: string[] = [];
  657 |   const linkMemoryPosts: string[] = [];
  658 |   await mockTerminalApis(page, { captureLoginPosts: loginPosts, captureLinkMemoryPosts: linkMemoryPosts });
  659 | 
  660 |   await page.goto("/terminal");
  661 |   await page.getByRole("button", { name: "Account" }).click();
  662 |   const accountSheet = page.locator(".account-panel-sheet");
  663 |   await accountSheet.getByLabel("Email").fill("analyst@example.com");
  664 |   await accountSheet.getByLabel("Password").fill("password123");
  665 |   await accountSheet.getByRole("button", { name: "Sign in" }).last().click();
  666 | 
  667 |   await expect(page.getByText("analyst@example.com")).toBeVisible();
  668 |   await page.getByRole("button", { name: "Sync browser memory" }).click();
  669 |   await expect(page.getByText("Memory synced")).toBeVisible();
  670 |   expect(loginPosts).toEqual(["POST"]);
  671 |   expect(linkMemoryPosts).toEqual(["POST"]);
  672 | });
  673 | 
  674 | test("loaded backtest appears on the conclusion page without auto-creating a new one", async ({ page }) => {
  675 |   const backtestPosts: string[] = [];
  676 |   await mockTerminalApis(page, { captureBacktestPosts: backtestPosts });
  677 | 
  678 |   await page.goto("/terminal/backtest?run=demo-run");
  679 |   await expect(page.getByText("Portfolio return", { exact: true })).toBeVisible();
  680 |   await expect(page.getByText("Portfolio", { exact: true })).toBeVisible();
  681 |   await expect(backtestPosts).toEqual([]);
  682 | 
  683 |   await page.getByRole("link", { name: "Research Conclusion", exact: true }).click();
  684 |   await expect(page).toHaveURL(/\/terminal\/conclusion\?run=demo-run/);
  685 |   await expect(page.getByText("Portfolio vs Benchmark Backtest")).toBeVisible();
  686 |   await expect(page.getByText("Portfolio", { exact: true })).toBeVisible();
  687 |   await expect(page.getByText("Benchmark", { exact: true })).toBeVisible();
  688 |   await expect(page.getByText("Data is insufficient; this chart was not generated.")).toHaveCount(0);
  689 | });
  690 | 
  691 | test("archive can continue a previous run without starting from scratch", async ({ page }) => {
  692 |   await mockTerminalApis(page);
  693 | 
```