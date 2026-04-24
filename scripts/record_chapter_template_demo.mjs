/**
 * 录屏：教师发布预览（新模板）+ 学生端运行结果/消息栏
 */
import { chromium } from "playwright";

const API = "http://127.0.0.1:8000";
const APP = "http://127.0.0.1:4173";
const w = (ms) => new Promise((r) => setTimeout(r, ms));

async function main() {
  const browser = await chromium.launch({
    headless: false,
    args: ["--no-sand-box", "--window-size=1400,900"],
  });
  const p = await browser.newPage({ viewport: { width: 1280, height: 820 } });

  await p.goto(`${API}/teacher/login`, { waitUntil: "domcontentloaded" });
  await p.locator("input#p, input[name=password]").first().fill("AdminPass123");
  await p.getByRole("button", { name: "登录" }).click();
  await p.waitForURL("**/teacher**", { timeout: 20_000 });
  await w(1200);
  await p.locator("table a[href*='/chapters/'][href$='/edit']").first().click();
  await p.getByText("发布预览", { exact: false }).first().waitFor();
  await w(2000);
  for (let i = 0; i < 6; i++) {
    await p.mouse.wheel(0, 400);
    await w(500);
  }
  await w(2000);
  await p.close();

  const s = await browser.newPage({ viewport: { width: 1280, height: 820 } });
  await s.goto(APP, { waitUntil: "domcontentloaded" });
  await s.getByLabel("学号").fill("E2E0001");
  await s.getByLabel("密码").fill("E2EPass123");
  await s.getByRole("button", { name: "进入" }).click();
  await s.getByText("已发布章节练习").waitFor();
  await s.getByText(/E2E 演示章/).first().click();
  await s
    .getByRole("heading", { name: /E2E 演示章/ })
    .first()
    .waitFor({ timeout: 20_000 });
  await s.getByText(/认识 print/, { exact: false }).first().waitFor({ timeout: 20_000 });
  await w(1500);
  await s.locator("textarea.jnb-input").first().fill("print('wrong')");
  await s.getByRole("button", { name: "执行" }).nth(0).click();
  await s
    .getByText("未做对", { exact: false })
    .first()
    .waitFor({ timeout: 120_000 });
  await s.getByText("运行结果", { exact: false }).first().waitFor();
  await w(3000);
  await s.locator("textarea.jnb-input").first().fill("print(");
  await s.getByRole("button", { name: "执行" }).nth(0).click();
  await s
    .getByText("代码存在错误", { exact: false })
    .first()
    .waitFor({ timeout: 120_000 });
  await w(3000);
  await s.locator("textarea.jnb-input").first().fill('print("all ok now")');
  await s.getByRole("button", { name: "执行" }).nth(0).click();
  await s
    .getByText("此题已答对", { exact: false })
    .first()
    .waitFor({ timeout: 120_000 });
  await w(4000);
  await browser.close();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
