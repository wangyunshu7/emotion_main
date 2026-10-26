import { test, expect, type Page } from "@playwright/test";

test("recommendation, timer and optional feedback", async ({ page }) => {
  await register(page);
  await page.goto("/care");
  await page.getByRole("button", { name: "为我推荐" }).click();
  await expect(
    page.getByRole("heading", { name: "此刻的小选择" }),
  ).toBeVisible();
  await page
    .getByRole("link")
    .filter({ hasText: "【开发演示】给此刻写一句话" })
    .first()
    .click();
  await page.getByRole("button", { name: "开始这段关怀" }).click();
  await expect(page.getByText("页面计时已暂停")).toBeVisible();
  await page.getByRole("button", { name: "继续页面计时" }).click();
  await page.getByRole("button", { name: "暂停", exact: true }).click();
  await page.getByRole("button", { name: "继续页面计时" }).click();
  await page.getByRole("button", { name: "完成活动" }).click();
  await page
    .getByRole("combobox", { name: "这次活动", exact: true })
    .selectOption("helpful");
  await page.getByRole("button", { name: "保存反馈" }).click();
  await expect(page.getByRole("button", { name: "反馈已保存" })).toBeVisible();
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "你好，体验者" }),
  ).toBeVisible();
  await page.screenshot({
    path: "../.runtime/screenshots/home-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: "../.runtime/screenshots/home-mobile.png",
    fullPage: true,
  });
});

async function register(page: Page) {
  await page.goto("/register");
  await page
    .getByLabel("邮箱", { exact: true })
    .fill(
      `e2e-${Date.now()}-${Math.random().toString(16).slice(2)}@example.com`,
    );
  await page.getByLabel("怎么称呼你").fill("体验者");
  await page
    .getByLabel("密码", { exact: true })
    .fill("e2e-private-password-123");
  await page.getByLabel("我确认已年满 18 岁").check();
  await page.getByLabel("我已阅读并接受下方使用与隐私说明").check();
  await page.getByRole("button", { name: "创建我的空间" }).click();
  await expect(
    page.getByRole("heading", { name: "这里，不需要一直开心。" }),
  ).toBeVisible();
}

async function createJournal(page: Page, body = "") {
  await page.goto("/journals/new");
  await page.getByRole("button", { name: "还不错", exact: true }).click();
  await page.getByRole("button", { name: "平静", exact: true }).click();
  if (body)
    await page
      .getByPlaceholder(
        "今天发生了什么？那一刻，你有什么感受？只写一句也很好。",
      )
      .fill(body);
  await page.getByRole("button", { name: "保存这段心情" }).click();
  await expect(page).toHaveURL(/\/journals\/[0-9a-f-]+$/);
}

test("private record, edit, trends and deletion on a phone viewport", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await register(page);
  await createJournal(page);
  await expect(
    page.getByText("这次只记录了情绪，没有填写正文。"),
  ).toBeVisible();
  await page.getByRole("link", { name: "编辑", exact: true }).click();
  await page
    .getByPlaceholder("今天发生了什么？那一刻，你有什么感受？只写一句也很好。")
    .fill("今天给自己留了一点休息时间。");
  await page.getByRole("button", { name: "保存这段心情" }).click();
  await expect(
    page.getByText("今天给自己留了一点休息时间。", { exact: true }),
  ).toBeVisible();
  await page.goto("/insights");
  await expect(page.getByRole("heading", { name: "心情的起伏" })).toBeVisible();
  await page.goto("/journals");
  await page
    .getByRole("link")
    .filter({ hasText: "今天给自己留了一点休息时间。" })
    .click();
  await page.getByRole("button", { name: "删除日记" }).click();
  await page.getByRole("button", { name: "确认", exact: true }).click();
  await expect(page.getByText("第一条日记，从此刻开始。")).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
});

test("AI requires consent and produces clearly labelled development analysis", async ({
  page,
}) => {
  await register(page);
  await page.goto("/settings");
  await page.getByRole("button", { name: "阅读并授权 AI 处理" }).click();
  await page.getByRole("button", { name: "确认", exact: true }).click();
  await expect(
    page.getByText("已记录授权。AI 分析仍由你逐条主动触发。"),
  ).toBeVisible();
  await createJournal(page, "今天的工作结束了，想留一点时间给自己。");
  await page.getByRole("button", { name: "主动整理这条日记" }).click();
  await expect(
    page.getByText("【开发模拟】这是用于联调的整理结果，不代表真实模型分析。"),
  ).toBeVisible({ timeout: 30000 });
  await page.getByRole("button", { name: "符合", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "符合", exact: true }),
  ).toHaveAttribute("class", /selected/);
  await page.goto("/insights");
  await page.getByRole("button", { name: "生成 7 天回顾" }).click();
  await expect(page.getByRole("heading", { name: "这一周的你" })).toBeVisible({
    timeout: 30000,
  });
  await expect(
    page.getByText("记录天数还不多，先看看这些小片段。"),
  ).toBeVisible();
});

test("data export and account deletion clear the browser session", async ({
  page,
}) => {
  await register(page);
  await createJournal(page, "用于验证导出的虚构记录。");
  await page.goto("/settings");
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "导出我的数据" }).click();
  expect((await download).suggestedFilename()).toContain("导出");
  await page.getByRole("button", { name: "注销账号" }).click();
  await expect(
    page.getByRole("button", { name: "取消", exact: true }),
  ).toBeEnabled();
  await page.getByLabel("当前密码").fill("e2e-private-password-123");
  await page
    .getByLabel("输入 DELETE_MY_ACCOUNT 确认")
    .fill("DELETE_MY_ACCOUNT");
  await page.getByRole("button", { name: "确认", exact: true }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.goto("/journals");
  await expect(page).toHaveURL(/\/login$/);
  expect(
    await page.evaluate(
      () =>
        Object.keys(sessionStorage).filter((k) =>
          k.startsWith("emotion-draft:"),
        ).length,
    ),
  ).toBe(0);
});
