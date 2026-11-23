import { expect, test } from "@playwright/test";

test.skip(process.env.PORTAL_PRIMARY_TEST !== "true", "primary two-edition deployment only");

test("visitors switch editions and read, search, link and download within the revision", async ({ page }) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));

  const selector = page.getByRole("navigation", { name: "选择文稿版本" });
  await page.goto("/");
  await expect(selector.getByRole("link", { name: "第 1 轮征求意见稿" })).toHaveAttribute("aria-current", "true");
  await selector.getByRole("link", { name: "第 2 轮修订稿" }).click();
  await expect(page).toHaveURL(/\/v2\/$/);
  await expect(selector.getByRole("link", { name: "第 2 轮修订稿" })).toHaveAttribute("aria-current", "true");
  await expect(page.getByRole("button", { name: "阅读登记" })).toHaveCount(0);

  await page.getByRole("button", { name: "搜索标准", exact: true }).click();
  await page.getByRole("textbox", { name: "搜索标准全文" }).fill("差分查询");
  const found = page.getByRole("dialog").locator(".search-results a").first();
  await expect(found).toHaveAttribute("href", /^\/v2\/read\/11\//);
  await found.click();
  await expect(page).toHaveURL(/\/v2\/read\/11\//);
  await page.reload();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("安全");
  await page.goBack();
  await expect(page).toHaveURL(/\/v2\/$/);

  await page.getByRole("link", { name: "资料下载", exact: true }).first().click();
  await expect(page).toHaveURL(/\/v2\/downloads\/$/);
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.locator('a[href="/v2/downloads/standard-review.pdf"]').click(),
  ]);
  expect(download.suggestedFilename()).toBe("standard-review.pdf");
  expect(await download.failure()).toBeNull();

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(selector).toBeVisible();
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await selector.getByRole("link", { name: "第 1 轮征求意见稿" }).click();
  await expect(page).toHaveURL(new URL("/", page.url()).href);
  await expect(page.getByRole("button", { name: "阅读登记" })).toHaveCount(1);
  expect(errors).toEqual([]);
});

test("both editions can be selected and read with JavaScript disabled", async ({ baseURL, browser }) => {
  const context = await browser.newContext({ baseURL, javaScriptEnabled: false });
  try {
    const page = await context.newPage();
    await page.goto("/");
    await page.getByRole("link", { name: "第 2 轮修订稿" }).click();
    await page.getByRole("link", { name: "开始阅读" }).click();
    await expect(page).toHaveURL(/\/v2\/read\/introduction\/$/);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("引言");
  } finally {
    await context.close();
  }
});
