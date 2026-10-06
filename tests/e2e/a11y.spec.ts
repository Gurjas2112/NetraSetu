import AxeBuilder from "../../web/node_modules/@axe-core/playwright/dist/index.mjs";
import { expect, test, type Page } from "@playwright/test";

async function noSerious(page: Page) {
  const results = await new AxeBuilder({ page }).analyze();
  const serious = results.violations.filter(
    (v) => v.impact === "serious" || v.impact === "critical",
  );
  expect(serious, JSON.stringify(serious, null, 2)).toEqual([]);
}

test("axe has no serious violations on the four routes", async ({ page }) => {
  for (const path of ["/field", "/review", "/patient", "/admin"] as const) {
    await page.goto(path);
    await noSerious(page);
  }
});
