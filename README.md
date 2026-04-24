# digital-course

单人维护的教学产品规格与开发仓库（**无协作者**；密钥与本地配置不提交到 Git）。

## 使用本仓库

- **Context7 MCP**：根目录需有 **`.env`**，内含从 [Context7](https://context7.com/dashboard) 取得并填入的 `CONTEXT7_API_KEY=...`。复制 **`.env.example`** 为 **`.env`** 后填值。MCP 配置在 **`.cursor/mcp.json`**。  
- **若打开 `mcp.json` 出现 ENOPRO / 未找到 `vscode-remote://backgroundcomposer+.../mcp.json` 的文件系统提供程序**：该 URI 来自**已失效的云端（Background Composer）会话**。在侧栏**从当前工作区**打开 **`.cursor/mcp.json`**，或在 **设置 → Cursor → MCP** 中编辑。编辑本地/工作区里的真实文件路径即可，Context7 与项目根 **`.env`** 中的 `CONTEXT7_API_KEY` 配套使用。
- **Superpowers 技能正文**：`vendor/superpowers` 为子模块。若目录为空，执行 `git submodule update --init --recursive`。
- **准备清单**：[`docs/superpowers/specs/2026-04-23-ai-python-teaching-system-preparation.md`](docs/superpowers/specs/2026-04-23-ai-python-teaching-system-preparation.md)  
- **设计规格**：[`docs/superpowers/specs/2026-04-23-ai-python-teaching-system-design.md`](docs/superpowers/specs/2026-04-23-ai-python-teaching-system-design.md)  
- **实现计划**（`writing-plans`）：[`docs/superpowers/plans/2026-04-23-ai-python-teaching-system-implementation.md`](docs/superpowers/plans/2026-04-23-ai-python-teaching-system-implementation.md) — 与清单、设计一致。  
- **API 骨架**（**任务 1 已完成**）：`services/api/`。本地：进入该目录后 `python3 -m venv .venv && . .venv/bin/activate && pip install -e . && uvicorn app.main:app --reload`；`GET /health` 应返回 `{"ok":true}`。生产镜像见 `services/api/Dockerfile` 与根目录 `docker-compose.yml`。
- **学生桌面（任务 11）**：`apps/student-desktop/`（Tauri + React + Vite，环境变量 `VITE_API_BASE_URL`）。说明见该目录下 `README.md`。
