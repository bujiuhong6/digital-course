/**
 * 转发到 `.playwright-runner/record_mvp_features_demo.mjs`（该目录有 `playwright` 依赖）。
 * 使用说明见 `.playwright-runner/README.md`。
 */
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const runner = join(here, "../.playwright-runner/record_mvp_features_demo.mjs");
const r = spawnSync(process.execPath, [runner], { stdio: "inherit" });
process.exit(r.status ?? 1);
