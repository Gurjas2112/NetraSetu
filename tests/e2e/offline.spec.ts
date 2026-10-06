import { expect, test } from "@playwright/test";
import { randomBytes } from "node:crypto";
import fs from "node:fs";
import path from "node:path";

const FIXTURES = path.resolve(__dirname, "..", "fixtures");

function freshFixture(name: string) {
  const bytes = fs.readFileSync(path.join(FIXTURES, `${name}.png`));
  return { name: `${name}.png`, mimeType: "image/png", buffer: Buffer.concat([bytes, randomBytes(16)]) };
}

test("offline capture queues then syncs", async ({ page }) => {
  await page.goto("/field");
  await page.getByTestId("consent-given").check();
  await page.getByTestId("file-input").setInputFiles(freshFixture("grade0_clean"));
  await page.route("**/analyze", (route) => route.abort());
  await page.getByRole("button", { name: "Check image" }).click();
  await expect(page.getByTestId("sync-waiting")).toHaveText("1 waiting to sync");
  await page.unroute("**/analyze");
  await page.evaluate(() => window.dispatchEvent(new Event("online")));
  await expect(page.getByTestId("sync-waiting")).toHaveText("0 waiting to sync", { timeout: 30_000 });
  await expect(page.getByTestId("decision")).toHaveAttribute("data-decision", "ROUTINE");
});
