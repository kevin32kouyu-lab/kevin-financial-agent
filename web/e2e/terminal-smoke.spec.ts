import { expect, test } from "@playwright/test";

const routes = ["/terminal", "/terminal/conclusion", "/terminal/backtest", "/terminal/archive"];

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
