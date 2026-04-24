/**
 * 学生端 E2E：先运行不过关 → 再过关 → 两格都过后标完成。
 * 依赖 `vite preview` :4173、API :8000、E2E 种子库（E2E0001 / E2EPass123）。
 * 运行：在已安装 playwright 的目录中 `node record_student_notebook_e2e.mjs`
 * （通常复制到 /tmp/xxx 后 npm i playwright）
 */
import { chromium } from "playwright";

const BASE = "http://127.0.0.1:4173";
const runBtn = { name: "执行" };
const completeBtn = { name: "提交本章练习" };

async function main() {
  // 默认有界面：无头环境常无法从 CDN 拉全 Pyodide。本地可用 HEADLESS=1 强制无头
  const browser = await chromium.launch({
    headless: process.env.HEADLESS === "1",
    args: ["--no-sand-box", "--disable-dev-shm-usage"],
  });
  const page = await browser.newPage();
  page.setDefaultTimeout(180_000);
  page.setDefaultNavigationTimeout(180_000);

  await page.goto(BASE, { waitUntil: "domcontentloaded" });
  await page.getByLabel("学号", { exact: true }).fill("E2E0001");
  await page.getByLabel("密码", { exact: true }).fill("E2EPass123");
  await page.getByRole("button", { name: "进入" }).click();
  await page.getByText("已发布章节练习", { exact: true }).waitFor();
  const openChapter = page
    .getByRole("button", { name: /E2E 演示/ })
    .or(page.getByText(/E2E 演示/));
  await openChapter.first().click();

  const areas = page.locator("textarea.jnb-input");
  const guide = areas.nth(0);
  const ext = areas.nth(1);

  // Guide: should fail
  await guide.clear();
  await guide.fill("print('wrong')");
  await page.getByRole("button", runBtn).nth(0).click();
  await page.getByText("未通过", { exact: false }).first().waitFor({
    state: "visible",
    timeout: 120_000,
  });
  // Guide: pass
  await guide.clear();
  await guide.fill('print("all ok now")');
  await page.getByRole("button", runBtn).nth(0).click();
  await page
    .getByText("本关已记录为通过", { exact: false })
    .first()
    .waitFor({ state: "visible", timeout: 120_000 });

  // Extension: fail
  await ext.clear();
  await ext.fill("print('bye')");
  await page.getByRole("button", runBtn).nth(1).click();
  // 此时引导格已通过，页面上仅扩展格显示「未通过」
  await page.getByText("未通过", { exact: false }).first().waitFor({
    state: "visible",
    timeout: 120_000,
  });
  // Extension: pass
  await ext.clear();
  await ext.fill('print("Hello, world!")');
  await page.getByRole("button", runBtn).nth(1).click();
  await page.waitForFunction(
    () => (document.body.innerText.match(/本关已记录为通过/g) || []).length >=
      2,
    { timeout: 120_000 },
  );

  // Complete
  await page.getByRole("button", completeBtn).click();
  await page
    .getByText("本章已标记完成", { exact: true })
    .waitFor({ state: "visible", timeout: 15_000 });

  await browser.close();
  console.log("e2e ok");
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
