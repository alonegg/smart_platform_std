import { test, expect } from "@playwright/test";
test.skip(process.env.PORTAL_EDITION !== "r2", "r2 preview only");

test("internal preview shows differences, allows unchanged clauses and disables submissions", async ({ page }) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/compare/");
  await expect(page.getByRole("note", { name: "预览状态" })).toContainText("第2轮修订稿预览，非现行征求意见稿");
  await expect(page.locator('meta[name="robots"]')).toHaveAttribute("content", "noindex");
  await expect(page.locator(".r2-comparison")).toHaveCount(27);
  await expect(page.locator('.r2-comparison').filter({ hasText: "4.4.5.4" }).first()).toContainText("R01");
  await page.getByLabel("只看改动").uncheck();
  await expect(page.locator(".r2-comparison")).toHaveCount(805);
  await page.getByLabel("只看改动").check();
  await expect(page.locator(".r2-comparison")).toHaveCount(27);
  await page.screenshot({ path: "../../plan/r2-compare.png", fullPage: false });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: "../../plan/r2-compare-mobile.png", fullPage: false });
  await page.goto("/comment/");
  await expect(page.getByRole("button", { name: "意见提交已禁用" })).toBeDisabled();
  await expect(page.locator("form")).toHaveCount(0);
  await page.screenshot({ path: "../../plan/r2-comment.png", fullPage: false });
  expect(errors).toEqual([]);
});
