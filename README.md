# digital-course

《数字技术与应用》AI 智能编程教学平台。仓库包含教师端 FastAPI 页面、学生端 Tauri/React 桌面应用、Pyodide 代码执行、章节练习发布、学生进度记录和 OpenAI 兼容大语言模型接入。

本仓库提交的是代码、迁移、静态资源和章节 seed。运行时数据库、管理员账号、学生名单、答题记录、本地 `.env` 与 API Key 均不提交。

## 目录

- `services/api/`：FastAPI 后端、教师端 HTML、学生 REST、聊天代理、数据库迁移。
- `apps/student-desktop/`：学生端 Tauri + React + Vite 应用。
- `services/api/seeds/chapters.json`：已发布章节练习 seed。保留课程题目，不包含学生、名单、班级、管理员和答题记录。
- `scripts/initialize_content_db.py`：用 seed 初始化数据库，并清空运行时数据。

## 初始化 API

```bash
cd services/api
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
python -m alembic upgrade head
cd ../..
services/api/.venv/bin/python scripts/initialize_content_db.py --prune-extra-chapters
```

初始化后数据库只保留章节练习内容。教师端首次进入会提示设置管理员账号和密码；学生名单、班级、学生账号和答题记录为空。

启动 API：

```bash
cd services/api
./.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

健康检查：

```bash
curl http://127.0.0.1:8000/health
```

教师端入口：`http://127.0.0.1:8000/teacher/login`

## 启动学生端

浏览器调试：

```bash
cd apps/student-desktop
pnpm install
pnpm dev
```

终端会输出本地地址，通常是 `http://localhost:1420`。

桌面 App：

```bash
cd apps/student-desktop
pnpm tauri dev
```

学生端开发默认通过 Vite 代理访问 API：`/v1` → `http://127.0.0.1:8000`。API 需要先启动。

## 接入大语言模型

后端使用 OpenAI 兼容 Chat Completions。复制 `services/api/.env.example` 为 `services/api/.env` 后填写本地密钥。`.env` 已被忽略，不会上传 GitHub。

DeepSeek 示例：

```env
CHAPTER_GEN_MOCK=0
LLM_BASE_URL=https://api.deepseek.com
LLM_API_KEY=你的 DeepSeek API Key
CHAPTER_GEN_MODEL=deepseek-v4-flash

CHAT_LLM_BASE_URL=https://api.deepseek.com
CHAT_LLM_API_KEY=你的 DeepSeek API Key
CHAT_MODEL=deepseek-v4-flash
```

OpenRouter 示例：

```env
CHAPTER_GEN_MOCK=0
LLM_BASE_URL=https://openrouter.ai/api
LLM_API_KEY=你的 OpenRouter API Key
CHAPTER_GEN_MODEL=openai/gpt-4o-mini
CHAT_MODEL=openai/gpt-4o-mini
OPENROUTER_HTTP_REFERER=http://127.0.0.1:8000
OPENROUTER_TITLE=digital-course
```

硅基流动示例：

```env
CHAPTER_GEN_MOCK=0
LLM_BASE_URL=https://api.siliconflow.cn
LLM_API_KEY=你的硅基流动 API Key
CHAPTER_GEN_MODEL=deepseek-ai/DeepSeek-V4-Flash
CHAT_MODEL=deepseek-ai/DeepSeek-V4-Flash
```

`CHAT_LLM_BASE_URL` / `CHAT_LLM_API_KEY` 可单独配置学生 AI 助手；未设置时回退到 `LLM_BASE_URL` / `LLM_API_KEY`。

## 测试

后端：

```bash
cd services/api
pytest -q
ruff check app tests
```

学生端：

```bash
cd apps/student-desktop
pnpm typecheck
pnpm build
```

## 注意事项

- 不提交 `services/api/.env`、`apps/student-desktop/.env`、SQLite 数据库、虚拟环境、缓存和本地截图。
- 推送前可用 `git status --short` 和敏感词扫描确认没有 API Key。
- `services/api/seeds/chapters.json` 是课程内容来源。运行 `scripts/initialize_content_db.py` 会保留这些章节并清空运行时数据。
