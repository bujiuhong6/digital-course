/**
 * 云端演示：教师端「发布预览」+ 学生 Vite 预览章练习区。
 * 需 API :8000、student-desktop `vite preview` :4173 已起；数据库含演示章。
 * 运行：DISPLAY=:1 npx -y node scripts/record_notebook_ui_demo.mjs
 */
import { chromium } from "playwright";

const API = "http://127.0.0.1:8000";
const PREVIEW = "http://127.0.0.1:4173";
const CHAPTER_ID = "d065d28be0c8414ca220745d31ec2dc9";
const ADMIN_PASS = "AdminPass123";
const STU = { no: "2026001", pw: "StuPass123" };

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function main() {
  const browser = await chromium.launch({
    headless: false,
    args: ["--window-size=1400,900", "--no-sand-box", "--window-position=0,0"],
  });
  const page = await browser.newPage({
    viewport: { width: 1280, height: 800 },
  });

  // --- Teacher: login + chapter edit (preview) ---
  await page.goto(`${API}/teacher/login`, { waitUntil: "networkidle" });
  await page.locator('input[name="password"], input#p').first().fill(ADMIN_PASS);
  await page.getByRole("button", { name: "登录" }).click();
  await page.waitForURL("**/teacher**", { timeout: 15_000 });
  await page.goto(
    `${API}/teacher/chapters/${CHAPTER_ID}/edit`,
    { waitUntil: "domcontentloaded" },
  );
  await sleep(800);
  await page
    .getByRole("heading", { name: /发布预览/ })
    .scrollIntoViewIfNeeded();
  await sleep(500);
  for (let i = 0; i < 5; i++) {
    await page.mouse.wheel(0, 480);
    await sleep(400);
  }
  await sleep(1200);

  // --- Student: Vite app ---
  const p2 = await browser.newPage({
    viewport: { width: 1280, height: 800 },
  });
  await p2.goto(PREVIEW, { waitUntil: "networkidle" });
  await p2.getByLabel("学号", { exact: true }).fill(STU.no);
  await p2.getByLabel("密码", { exact: true }).fill(STU.pw);
  await p2.getByRole("button", { name: "进入" }).click();
  await p2.getByText("已发布章节练习").waitFor({ timeout: 15_000 });
  const demoBtn = p2
    .getByRole("button", { name: /演示章/ })
    .or(p2.getByText("演示章", { exact: false }));
  await demoBtn.first().click();
  await sleep(1000);
  for (let i = 0; i < 7; i++) {
    await p2.mouse.wheel(0, 500);
    await sleep(350);
  }
  await sleep(2000);

  await browser.close();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
