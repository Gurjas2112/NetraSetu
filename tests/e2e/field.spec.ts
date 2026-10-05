import { expect, test } from "@playwright/test";
import path from "node:path";

const FIXTURES = path.resolve(__dirname, "..", "fixtures");

const CASES = [
  { name: "grade0_clean", decision: "ROUTINE" },
  { name: "grade2_haem", decision: "REFER" },
  { name: "grade4_nv", decision: "REFER" },
  { name: "blur_s8", decision: "RETAKE" },
  { name: "underexposed", decision: "RETAKE" },
  { name: "partial_fov", decision: "RETAKE" },
] as const;

for (const { name, decision } of CASES) {
  test(`${name} on /field shows ${decision}`, async ({ page }) => {
    await page.goto("/field");
    await page.getByTestId("file-input").setInputFiles(path.join(FIXTURES, `${name}.png`));
    await page.getByRole("button", { name: "Check image" }).click();

    const banner = page.getByTestId("decision");
    await expect(banner).toHaveAttribute("data-decision", decision);
    await expect(banner).toHaveText(decision);
    if (decision === "RETAKE") {
      await expect(page.getByTestId("retake-guidance")).not.toBeEmpty();
      await expect(page.getByTestId("retake-guidance")).not.toContainText(/ungradeable/i);
    }
  });
}

test("the other three routes render the study", async ({ page }) => {
  await page.goto("/field");
  await page.getByTestId("file-input").setInputFiles(path.join(FIXTURES, "grade2_haem.png"));
  await page.getByRole("button", { name: "Check image" }).click();
  await expect(page.getByTestId("decision")).toHaveAttribute("data-decision", "REFER");

  await page.getByRole("link", { name: "Review" }).click();
  await expect(page.getByTestId("review-decision")).toHaveText("REFER");

  await page.getByRole("link", { name: "Patient" }).click();
  await expect(page.getByRole("heading", { name: "What we found" })).toBeVisible();

  await page.getByRole("link", { name: "Admin" }).click();
  await expect(page.getByTestId("health-status")).toHaveText("ok");
});
