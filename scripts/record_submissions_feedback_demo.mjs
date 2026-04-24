/**
 * 录屏：教师完成记录（人数+CSV）+ 学生运行结果/消息栏/标准答案/语法错。
 * 需 SEED_DEMO_COMPLETION=1 库、:8000 :4173。
 */
import { chromium } from "playwright";

const API = "http://127.0.0.1:8000";
const APP = "http://127.0.0.1:4173";
const ADMIN = "AdminPass123";
const STU = { no: "E2E0001", pw: "E2EPass123" };
const w = (ms) => new Promise((r) => setTimeout(r, ms));

async function main() {
  const browser = await chromium.launch({
    headless: false,
    args: ["--no-sand-box", "--window-size=1400,900"],
  });
  const p = await browser.newPage({ viewport: { width: 1280, height: 820 } });

  await p.goto(`${API}/teacher/login`, { waitUntil: "domcontentloaded" });
  await w(800);
  await p.locator('input[name="password"], input#p').first().fill(ADMIN);
  await p.getByRole("button", { name: "登录" }).click();
  await p.waitForURL("**/teacher**", { timeout: 20_000 });
  await w(1200);
  await p.getByRole("link", { name: "完成记录" }).first().click();
  await p.getByText("已提交人数").waitFor();
  await w(2500);
  const dl = p.waitForEvent("download").catch(() => null);
  await p.getByRole("link", { name: /导出 CSV/ }).click();
  await Promise.race([dl, w(3000)]);
  await w(2000);
  await p.close();

  const s = await browser.newPage({ viewport: { width: 1280, height: 820 } });
  await s.goto(APP, { waitUntil: "domcontentloaded" });
  await s.getByLabel("学号").fill(STU.no);
  await s.getByLabel("密码").fill(STU.pw);
  await s.getByRole("button", { name: "进入" }).click();
  await s.getByText("已发布章节练习").waitFor();
  await s.getByText(/E2E 演示/).first().click();
  await s.locator("textarea.jnb-input").first().waitFor();
  await w(1000);
  // 逻辑错误：能运行但不满足
  await s.locator("textarea.jnb-input").nth(0).fill("print('nope')");
  await s.getByRole("button", { name: "执行" }).nth(0).click();
  await s.getByText("未做对", { exact: false }).first().waitFor({ timeout: 120_000 });
  await s.getByText("标准答案参考", { exact: false }).first().waitFor();
  await w(3000);
  // 语法错
  await s.locator("textarea.jnb-input").nth(0).fill("print(");
  await s.getByRole("button", { name: "执行" }).nth(0).click();
  await s
    .getByText("代码存在错误", { exact: false })
    .first()
    .waitFor({ timeout: 120_000 });
  await w(3000);
  // 通过
  await s.locator("textarea.jnb-input").nth(0).fill('print("all ok now")');
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
