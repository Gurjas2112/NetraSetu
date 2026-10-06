/**
 * Single long flow for screen capture (DEMO_RECORD=1). Run:
 *   npm --prefix web run test:e2e -- demo-walkthrough
 */
import { expect, test } from "@playwright/test";
import { randomBytes } from "node:crypto";
import fs from "node:fs";
import path from "node:path";

const FIXTURES = path.resolve(__dirname, "..", "fixtures");

function freshFixture(name: string) {
  const bytes = fs.readFileSync(path.join(FIXTURES, `${name}.png`));
  return {
    name: `${name}.png`,
    mimeType: "image/png",
    buffer: Buffer.concat([bytes, randomBytes(16)]),
  };
}

test("full app walkthrough for demo recording", async ({ page }) => {
  test.setTimeout(300_000);

  await page.goto("/field");
  await expect(page.getByTestId("consent-notice")).not.toBeEmpty();
  await page.getByTestId("consent-given").check();
  await page.getByTestId("file-input").setInputFiles(freshFixture("grade0_clean"));
  await page.getByRole("button", { name: "Check image" }).click();
  await expect(page.getByTestId("decision")).toHaveAttribute("data-decision", "ROUTINE");

  await page.getByTestId("file-input").setInputFiles(freshFixture("grade2_haem"));
  await page.getByRole("button", { name: "Check image" }).click();
  await expect(page.getByTestId("decision")).toHaveAttribute("data-decision", "REFER");

  await page.getByRole("link", { name: "Review" }).click();
  await expect(page.getByTestId("review-decision")).toHaveText("REFER");

  await page.getByRole("link", { name: "Patient" }).click();
  await expect(page.getByRole("heading", { name: "What we found" })).toBeVisible();

  await page.getByRole("link", { name: "Admin" }).click();
  await expect(page.getByTestId("health-status")).toHaveText("ok");

  await page.getByRole("link", { name: "Screen" }).click();
  await page.getByTestId("consent-given").check();
  await page.getByTestId("file-input").setInputFiles(freshFixture("blur_s8"));
  await page.getByRole("button", { name: "Check image" }).click();
  await expect(page.getByTestId("decision")).toHaveAttribute("data-decision", "RETAKE");
  await expect(page.getByTestId("retake-guidance")).not.toBeEmpty();
});
