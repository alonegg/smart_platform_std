import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { readFile } from "node:fs/promises";
import { marked } from "marked";
const data = JSON.parse(
  await readFile(new URL("../src/generated.json", import.meta.url)),
);
const source = await readFile(
  new URL("../../../标准/评审稿/智慧教学-数据模型标准.md", import.meta.url),
  "utf8",
);

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "暂不登记，继续浏览" }).click();
});

test("role paths, search, stable subsection URL and browser history", async ({
  page,
}) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await page.getByRole("tab", { name: "应用厂商" }).click();
  await expect(page.getByRole("tabpanel")).toContainText(
    "从能力范围，核对接入与实现要求",
  );
  await page.getByRole("button", { name: "搜索标准", exact: true }).click();
  await page.getByRole("textbox", { name: "搜索标准全文" }).fill("人工责任");
  const dialog = page.getByRole("dialog");
  await expect(dialog.locator(".search-results")).toContainText("9.5 人工责任");
  await dialog.locator("a").filter({ hasText: "9.5 人工责任" }).first().click();
  await expect(page).toHaveURL(/\/read\/9\/#clause-9-5/);
  await expect(page.locator("#clause-9-5")).toBeInViewport();
  await page.reload();
  await expect(page.locator("#clause-9-5")).toBeInViewport();
  await page.getByRole("link", { name: "上一节" }).click();
  await expect(page.locator("h1")).toHaveText("8 数据交换与接口");
  await page.goBack();
  await expect(page.locator("h1")).toHaveText("9 应用与 AI 能力接入");
  expect(errors).toEqual([]);
});

test("Profile selection retains the common row and exact applicability values", async ({
  page,
}) => {
  await page.goto("/profiles/");
  for (const profile of data.profiles) {
    await page
      .locator(".profile-selector button")
      .filter({ hasText: profile.code })
      .click();
    await expect(page.locator(".profile-detail h2")).toHaveText(profile.name);
    const tables = page.locator(".matrix-panel table");
    for (let i = 0; i < 4; i++) {
      const expected = data.matrixTables[i].rows.filter(
        (row) =>
          row[0].startsWith("P-COM ") || row[0].startsWith(`${profile.code} `),
      );
      await expect(tables.nth(i).locator("tbody tr")).toHaveCount(
        expected.length,
      );
      for (let row = 0; row < expected.length; row++)
        expect(
          await tables
            .nth(i)
            .locator("tbody tr")
            .nth(row)
            .locator("td")
            .allTextContents(),
        ).toEqual(expected[row].slice(1));
    }
  }
});

test("pending decision stage and text filters, including empty state", async ({
  page,
}) => {
  await page.goto("/decisions/");
  await expect(page.locator(".decision-list>section")).toHaveCount(30);
  await page.getByRole("combobox", { name: "筛选决定阶段" }).selectOption("D3");
  await expect(page.locator(".decision-list>section")).toHaveCount(
    data.pending.filter((row) => row.stage.includes("D3")).length,
  );
  await page.getByRole("textbox", { name: "搜索待决事项" }).fill("E20");
  await expect(page.locator(".decision-list>section")).toHaveCount(1);
  await expect(page.locator(".decision-list")).toContainText(
    data.pending.find((item) => item.code === "E20").title,
  );
  await page
    .getByRole("textbox", { name: "搜索待决事项" })
    .fill("this-has-no-matches");
  await expect(
    page.getByRole("heading", { name: "没有找到匹配事项" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "清除筛选" }).click();
  await expect(page.locator(".decision-list>section")).toHaveCount(30);
});

test("all original sections retain their full readable text after rendering", async ({
  page,
}) => {
  const parts = source
    .split(/^## /m)
    .slice(1)
    .filter((part) => !part.startsWith("目次"));
  for (let i = 0; i < data.sections.length; i++) {
    await page.goto(`/read/${data.sections[i].key}/`);
    const original = marked.parse(
      parts[i].split("\n").slice(1).join("\n").trim(),
    );
    const fidelity = await page.evaluate((html) => {
      const doc = new DOMParser().parseFromString(html, "text/html");
      const normalize = (text) => text.replace(/\s+/g, "");
      return (
        normalize(doc.body.textContent) ===
        normalize(document.querySelector(".prose").textContent)
      );
    }, original);
    expect(fidelity, `text changed in ${data.sections[i].title}`).toBe(true);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  }
});

test("mobile navigation, search keyboard dismissal and contained long tables", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.getByRole("button", { name: "切换阅读目录" }).click();
  await page
    .getByRole("navigation", { name: "标准章节" })
    .getByRole("link", { name: "05 公共数据模型" })
    .click();
  await expect(page.locator("h1")).toHaveText("5 公共数据模型");
  await expect(page.locator(".sidebar")).not.toBeVisible();
  await page.getByRole("button", { name: "搜索标准", exact: true }).click();
  await page.getByRole("textbox", { name: "搜索标准全文" }).fill("unknown");
  await expect(page.locator(".search-results")).toContainText("unknown");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).not.toBeVisible();
  for (const url of [
    "/",
    "/profiles/",
    "/decisions/",
    "/downloads/",
    "/read/a/",
    "/read/b/",
  ]) {
    await page.goto(url);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
      url,
    ).toBe(true);
  }
});

test("semantic and contrast accessibility checks on every page type", async ({
  page,
}) => {
  for (const route of [
    "/",
    "/architecture/",
    "/profiles/",
    "/roadmap/",
    "/decisions/",
    "/downloads/",
    "/read/5/",
    "/read/a/",
  ]) {
    await page.goto(route);
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
      .analyze();
    expect(
      results.violations.map((v) => ({
        id: v.id,
        help: v.help,
        nodes: v.nodes.map((n) => ({
          target: n.target,
          summary: n.failureSummary,
        })),
      })),
      route,
    ).toEqual([]);
  }
});

test("vendor and expert review paths and prefilled clause feedback", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.getByRole("tab", { name: "应用厂商" })).toBeVisible();
  await page.getByRole("tab", { name: "标准专家" }).click();
  await expect(page.getByRole("tabpanel")).toContainText("技术一致性");
  await page.getByRole("tab", { name: "标准专家" }).press("ArrowRight");
  await expect(page.getByRole("tab", { name: "应用厂商" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await page.goto("/read/5/");
  const feedback = page
    .locator(".reader-tools")
    .getByRole("link", { name: "提出意见" });
  const target = new URL(await feedback.getAttribute("href"));
  expect(target.origin).toBe("https://github.com");
  expect(target.pathname).toBe("/alonegg/smart_platform_std/issues/new");
  expect(target.searchParams.get("title")).toContain("5 公共数据模型");
  expect(target.searchParams.get("body")).toContain("具体问题与场景");
  await page.goto("/read/c/");
  await expect(page.locator(".prose")).toContainText("应用厂商审阅重点");
  await expect(page.locator(".prose")).toContainText("标准专家审阅重点");
  await page.goto("/downloads/");
  await expect(page.locator(".download-list>a")).toHaveCount(4);
});
