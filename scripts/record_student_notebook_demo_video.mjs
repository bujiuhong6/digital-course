/**
 * 云端录屏用：与 record_student_notebook_e2e 同流程，步骤间 pause 便于观看。
 * DISPLAY=:1 ffmpeg x11grab … 与此并行。需 API :8000、vite :4173、E2E 库。
 */
import { chromium } from "playwright";

const BASE = "http://127.0.0.1:4173";
const pause = (ms) => new Promise((r) => setTimeout(r, ms));

async function main() {
  const browser = await chromium.launch({
    headless: false,
    args: ["--no-sand-box", "--disable-dev-shm-usage", "--window-size=1400,900"],
  });
  const page = await browser.newPage({ viewport: { width: 1280, height: 820 } });
  page.setDefaultTimeout(300_000);

  await page.goto(BASE, { waitUntil: "domcontentloaded" });
  await pause(1500);
  await page.getByLabel("学号", { exact: true }).fill("E2E0001");
  await page.getByLabel("密码", { exact: true }).fill("E2EPass123");
  await pause(500);
  await page.getByRole("button", { name: "进入" }).click();
  await page.getByText("已发布章", { exact: true }).waitFor();
  await pause(1200);
  await page.getByText(/E2E 演示/).first().click();
  await page.locator("textarea.jnb-input").first().waitFor();
  await pause(2000);

  const areas = page.locator("textarea.jnb-input");
  const guide = areas.nth(0);
  const ext = areas.nth(1);

  await guide.clear();
  await guide.fill("print('wrong')");
  await pause(600);
  await page.getByRole("button", { name: "执行" }).nth(0).click();
  await page.getByText("未通过", { exact: false }).first().waitFor({
    timeout: 120_000,
  });
  await pause(2500);

  await guide.clear();
  await guide.fill('print("all ok now")');
  await pause(500);
  await page.getByRole("button", { name: "执行" }).nth(0).click();
  await page.getByText("本关已记录为通过", { exact: false }).first().waitFor({
    timeout: 120_000,
  });
  await pause(2500);

  await ext.clear();
  await ext.fill("print('bye')");
  await pause(500);
  await page.getByRole("button", { name: "执行" }).nth(1).click();
  await page.getByText("未通过", { exact: false }).first().waitFor({
    timeout: 120_000,
  });
  await pause(2500);

  await ext.clear();
  await ext.fill('print("Hello, world!")');
  await pause(500);
  await page.getByRole("button", { name: "执行" }).nth(1).click();
  await page.waitForFunction(
    () => (document.body.innerText.match(/本关已记录为通过/g) || []).length >= 2,
    { timeout: 120_000 },
  );
  await pause(2500);

  await page.getByRole("button", { name: "尝试标记本章完成" }).click();
  await page
    .getByText(/本章(已标记完成|此前已标记完成)/)
    .waitFor({ timeout: 30_000 });
  await pause(4000);

  await browser.close();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
