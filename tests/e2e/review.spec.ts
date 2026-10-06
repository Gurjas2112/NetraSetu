import { expect, test } from "@playwright/test";
import { randomBytes } from "node:crypto";
import fs from "node:fs";
import path from "node:path";

const FIXTURES = path.resolve(__dirname, "..", "fixtures");

function freshFixture(name: string) {
  const bytes = fs.readFileSync(path.join(FIXTURES, `${name}.png`));
  return { name: `${name}.png`, mimeType: "image/png", buffer: Buffer.concat([bytes, randomBytes(16)]) };
}

test("reviewer keyboard agrees a referred case", async ({ page }) => {
  await page.goto("/field");
  await page.getByTestId("consent-given").check();
  await page.getByTestId("file-input").setInputFiles(freshFixture("grade2_haem"));
  await page.getByRole("button", { name: "Check image" }).click();
  await expect(page.getByTestId("decision")).toHaveAttribute("data-decision", "REFER");

  await page.getByRole("link", { name: "Review" }).click();
  await expect(page.getByTestId("review-decision")).toHaveText("REFER");
  await expect(page.getByTestId("review-console")).toBeVisible();
  await page.keyboard.press("a");
  await expect(page.getByTestId("review-signed")).toContainText("REFER");
});
