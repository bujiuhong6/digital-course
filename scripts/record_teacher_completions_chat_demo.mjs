/**
 * 录屏用：教师「完成记录」页 + 学生章练习 + 打开 Chat。
 * 需 API :8000、vite :4173；库含 SEED_DEMO_COMPLETION=1 种子。
 * DISPLAY=:1 + ffmpeg x11grab 与此并行。
 */
import { chromium } from "playwright";

const API = "http://127.0.0.1:8000";
const PREVIEW = "http://127.0.0.1:4173";
const ADMIN_PW = "AdminPass123";
const STU = { no: "E2E0001", pw: "E2EPass123" };
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

async function main() {
  const browser = await chromium.launch({
    headless: false,
    args: [
      "--no-sand-box",
      "--disable-dev-shm-usage",
      "--window-size=1400,900",
    ],
  });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  page.setDefaultTimeout(120_000);

  // Teacher: login → dashboard → 完成记录
  await page.goto(`${API}/teacher/login`, { waitUntil: "domcontentloaded" });
  await wait(1000);
  await page.locator('input[name="password"], input#p').first().fill(ADMIN_PW);
  await page.getByRole("button", { name: "登录" }).click();
  await page.waitForURL("**/teacher**", { timeout: 15_000 });
  await wait(1500);
  const completionsLink = page.getByRole("link", { name: "完成记录" }).first();
  await completionsLink.waitFor({ state: "visible", timeout: 10_000 });
  await completionsLink.click();
  await page.getByRole("heading", { name: "完成记录" }).waitFor();
  await wait(3000);
  for (let i = 0; i < 3; i++) {
    await page.mouse.wheel(0, 200);
    await wait(500);
  }
  await wait(2500);

  // Student: new tab
  const p2 = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  await p2.goto(PREVIEW, { waitUntil: "domcontentloaded" });
  await wait(1000);
  await p2.getByLabel("学号", { exact: true }).fill(STU.no);
  await p2.getByLabel("密码", { exact: true }).fill(STU.pw);
  await p2.getByRole("button", { name: "进入" }).click();
  await p2.getByText("章节练习列表").waitFor();
  await wait(1200);
  const openCh = p2
    .getByRole("button", { name: /E2E/ })
    .or(p2.getByText(/E2E 演示/));
  await openCh.first().click();
  await p2.locator("textarea.jnb-input").first().waitFor();
  await wait(2000);
  await p2.getByRole("button", { name: "Chat" }).click();
  await wait(2000);
  await p2.locator(".sd-chat-input").fill("print 和字符串怎么拼接？");
  await wait(800);
  await p2.getByRole("button", { name: "发送" }).click();
  await wait(5000);
  for (let i = 0; i < 2; i++) {
    await p2.mouse.wheel(0, 300);
    await wait(400);
  }
  await wait(2000);

  await browser.close();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
