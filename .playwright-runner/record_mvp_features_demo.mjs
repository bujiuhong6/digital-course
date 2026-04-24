/**
 * 从本目录运行：node record_mvp_features_demo.mjs（已安装 node_modules/playwright）
 */
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";
import { join } from "node:path";

const API = "http://127.0.0.1:8000";
const STUDENT = "http://127.0.0.1:4173";
const ADMIN = "AdminPass123";
const CH_ID = "d065d28b-e0c8-414c-a220-745d31ec2dc9";
const STU = { no: "2026001", pw: "StuPass123" };
const outDir = process.env.OUTPUT_DIR || join(process.cwd(), "../opt/cursor/artifacts");

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function run() {
  mkdirSync(outDir, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({
    recordVideo: { dir: outDir, size: { width: 1280, height: 800 } },
    viewport: { width: 1280, height: 800 },
  });
  const page = await ctx.newPage();
  await page.goto(`${API}/teacher/login`, { waitUntil: "networkidle" });
  await page
    .locator('input[name="password"], input#p')
    .first()
    .fill(ADMIN);
  await page.getByRole("button", { name: "登录" }).click();
  await page.waitForURL("**/teacher**", { timeout: 15_000 });
  await sleep(500);
  await page.getByRole("link", { name: /班级/ }).click();
  await page.waitForURL("**/teacher/classes**", { timeout: 10_000 });
  await sleep(800);
  await page.goto(`${API}/teacher/roster`, { waitUntil: "networkidle" });
  await sleep(1000);
  await page
    .getByRole("heading", { name: "当前名单行" })
    .scrollIntoViewIfNeeded();
  await sleep(800);
  await page.goto(`${API}/teacher`, { waitUntil: "networkidle" });
  await sleep(500);
  const p2 = await ctx.newPage();
  await p2.goto(STUDENT, { waitUntil: "networkidle" });
  const loginForm = p2.locator("form").first();
  await loginForm.locator("input").nth(0).fill(STU.no);
  await loginForm.locator("input").nth(1).fill(STU.pw);
  await p2.getByRole("button", { name: "进入" }).click();
  await p2
    .getByRole("heading", { name: "已发布章节练习" })
    .waitFor({ timeout: 20_000 });
  await sleep(800);
  await p2.getByRole("button", { name: /演示章/ }).first().click();
  await sleep(1500);
  await p2.getByRole("button", { name: "执行" }).first().click();
  await sleep(4000);
  await p2.getByTitle("AI学习助手").click();
  await sleep(1200);
  await p2.mouse.click(200, 400);
  await sleep(500);
  await page.goto(
    `${API}/teacher/chapters/${CH_ID}/completions`,
    { waitUntil: "networkidle" },
  );
  await sleep(1200);
  await p2.close();
  await page.close();
  await ctx.close();
  await browser.close();
  console.log(`Video(s) in ${outDir}`);
}

run().catch((e) => {
  console.error(e);
  process.exit(1);
});
