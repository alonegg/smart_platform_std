import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
const identity = {
  name: "合成登记验收",
  organization: "自动化测试样例（非真实专家）",
};
async function fill(page) {
  await page.getByLabel(/^姓名/).fill(identity.name);
  await page.getByLabel(/^参与身份/).selectOption("expert");
  await page.getByLabel(/^单位或身份/).fill(identity.organization);
  await page.getByLabel(/^专业或业务方向/).fill("数据模型自动验收");
  await page
    .getByRole("checkbox", {
      name: "我已阅读登记说明，同意为本次评议保存上述信息。",
    })
    .check();
  await page
    .getByRole("checkbox", {
      name: "同意由隐私说明中列明的境外服务处理登记信息。",
    })
    .check();
}

test("fresh deep link proactively prompts, default consent is off, keyboard and accessibility work", async ({
  page,
}) => {
  await page.goto("/read/5/");
  const dialog = page.getByRole("dialog", { name: "阅读者登记" });
  await expect(dialog).toBeVisible();
  await expect(
    page.getByRole("checkbox", {
      name: "我已阅读登记说明，同意为本次评议保存上述信息。",
    }),
  ).not.toBeChecked();
  await expect(
    page.getByRole("checkbox", {
      name: "同意由隐私说明中列明的境外服务处理登记信息。",
    }),
  ).not.toBeChecked();
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(
    results.violations.map((entry) => ({
      id: entry.id,
      targets: entry.nodes.map((node) => node.target),
    })),
  ).toEqual([]);
  await page.getByRole("button", { name: "暂不登记，继续浏览" }).click();
  await expect(dialog).not.toBeVisible();
  await page.reload();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  expect(
    (await (await page.request.get("/api/registration/session")).json())
      .registration,
  ).toBeNull();
  expect(await page.evaluate(() => localStorage.length)).toBe(0);
});

test("real database registration, refresh, self-confirmation, editing and withdrawal", async ({
  page,
}) => {
  await page.goto("/");
  await fill(page);
  try {
    await page.getByRole("button", { name: "登记并继续阅读" }).click();
    await expect(page.getByRole("dialog")).not.toBeVisible();
    const first = (
      await (await page.request.get("/api/registration/session")).json()
    ).registration;
    expect(first.name).toBe(identity.name);
    expect(first.readConfirmedAt).toBeNull();
    await page.reload();
    await expect(page.getByRole("button", { name: "阅读登记" })).toContainText(
      "已登记",
    );
    await expect(page.getByRole("dialog")).not.toBeVisible();
    await page.getByRole("button", { name: "阅读登记" }).click();
    await expect(
      page.getByRole("dialog", { name: "管理阅读登记" }),
    ).toBeVisible();
    await page.getByRole("button", { name: "本人确认已阅本标准" }).click();
    await expect(page.getByRole("status")).toContainText("已记录由本人确认");
    expect(
      (await (await page.request.get("/api/registration/session")).json())
        .registration.readConfirmedAt,
    ).toBeTruthy();
    await page.getByLabel(/^姓名/).fill(identity.name + "修改");
    await page
      .getByRole("checkbox", {
        name: "我已阅读登记说明，同意为本次评议保存上述信息。",
      })
      .check();
    await page
      .getByRole("checkbox", {
        name: "同意由隐私说明中列明的境外服务处理登记信息。",
      })
      .check();
    await page.getByRole("button", { name: "保存修改" }).click();
    await expect(page.getByRole("dialog")).not.toBeVisible();
    expect(
      (await (await page.request.get("/api/registration/session")).json())
        .registration.readConfirmedAt,
    ).toBeNull();
    await page.getByRole("button", { name: "阅读登记" }).click();
    await page.getByRole("button", { name: "撤回登记", exact: true }).click();
    await page.getByRole("button", { name: "确认撤回并删除" }).click();
    await expect(page.getByRole("dialog")).not.toBeVisible();
    expect(
      (await (await page.request.get("/api/registration/session")).json())
        .registration,
    ).toBeNull();
  } finally {
    await page.request.delete("/api/registration", {
      headers: { Origin: new URL(page.url()).origin },
    });
  }
});

test("failed save retains input and never claims registration success", async ({
  page,
}) => {
  await page.goto("/");
  await fill(page);
  await page.route("**/api/registration", async (route) => {
    if (route.request().method() === "POST")
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ error: "合成失败：请重试" }),
      });
    else await route.continue();
  });
  await page.getByRole("button", { name: "登记并继续阅读" }).click();
  await expect(page.getByRole("alert")).toContainText("合成失败");
  await expect(page.getByLabel(/^姓名/)).toHaveValue(identity.name);
  await expect(page.getByRole("dialog")).toBeVisible();
  expect(
    (await (await page.request.get("/api/registration/session")).json())
      .registration,
  ).toBeNull();
});

test("mobile prompt fits, privacy remains accessible and anonymous admin is denied", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/privacy/");
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await page.getByRole("button", { name: "阅读登记" }).click();
  await expect(page.getByRole("dialog", { name: "阅读者登记" })).toBeVisible();
  await expect(page.getByLabel(/^姓名/)).toBeVisible();
  await page.getByRole("button", { name: "暂不登记，继续浏览" }).click();
  await page.evaluate(() => sessionStorage.clear());
  await page.goto("/");
  await expect(page.getByRole("dialog", { name: "阅读者登记" })).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.getByRole("button", { name: "暂不登记，继续浏览" }).click();
  await page.goto("/privacy/");
  await expect(
    page.getByRole("heading", { name: "阅读登记隐私说明" }),
  ).toBeVisible();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  const response = await page.request.get("/admin/api/readers", {
    maxRedirects: 0,
  });
  expect([302, 401, 403]).toContain(response.status());
});
