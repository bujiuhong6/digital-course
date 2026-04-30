# digital-course

《数字技术与应用》AI 智能编程学习平台。项目包含教师端 FastAPI 管理台、学生端 React/Vite Web SPA（含 Tauri 桌面源码）、Pyodide 代码执行、学生名单与班级管理、OpenAI 兼容大模型接入，以及三类课程模块：

- `AI智能预习`：教师发布课前目标与预习任务，学生提交反馈。
- `AI课堂练习`：学生进入章节练习，完成随堂编程任务，页面内提供 AI 助教陪练。
- `AI课后作业`：教师发布单选、主观、代码混合题，学生提交后由大模型批改并返回分数和反馈。

本仓库提交代码、迁移、静态资源、测试和课程 seed。运行时 SQLite 数据库、管理员账号、学生名单、班级、学生账号、答题记录、本地 `.env` 与 API Key 均留在运行环境（本机或服务器）。

## 目录

- `services/api/`：FastAPI 后端、教师端 HTML 页面、学生 REST API、聊天代理、数据库模型与 Alembic 迁移。
- `apps/student-desktop/`：学生端 React + Vite Web SPA，含 Pyodide 代码练习界面；`src-tauri/` 保留本机桌面包源码。
- `services/api/seeds/chapters.json`：基础课堂练习 seed，不包含运行时账号、名单、班级和答题记录。
- `scripts/initialize_content_db.py`：初始化本地数据库；默认保护已设计的课程内容，清空运行时数据。

## 初始化 API

```bash
cd services/api
/opt/homebrew/bin/python3.12 -m venv .venv   # Mac；其他平台用系统 python3.12
. .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
python -m alembic upgrade head
cd ../..
services/api/.venv/bin/python scripts/initialize_content_db.py --prune-extra-chapters
```

初始化脚本会补齐 seed 中缺失的课堂练习内容，并保留已经存在的 `AI智能预习`、`AI课堂练习`、`AI课后作业` 内容。它会清空管理员账号、学生名单、班级、学生账号、答题记录和审计记录；教师端首次进入会提示设置管理员账号和密码。

如只想补齐课程 seed 并保留运行时数据：

```bash
services/api/.venv/bin/python scripts/initialize_content_db.py --keep-runtime
```

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

常用教师端页面：

- `http://127.0.0.1:8000/teacher/prestudy`：AI智能预习。
- `http://127.0.0.1:8000/teacher`：AI课堂练习。
- `http://127.0.0.1:8000/teacher/post-exercises`：AI课后作业。
- `http://127.0.0.1:8000/teacher/llm-settings`：大模型接入。
- `http://127.0.0.1:8000/teacher/roster`：学生名单。
- `http://127.0.0.1:8000/teacher/classes`：班级管理。

## 启动学生端

本地浏览器测试（主要开发方式）：

```bash
cd apps/student-desktop
pnpm install
pnpm dev
```

访问 `http://127.0.0.1:1420/`，API 需先启动。学生端通过 Vite 代理将 `/v1` 转发到 `http://127.0.0.1:8000`。

生产构建（部署前运行）：

```bash
cd apps/student-desktop
pnpm build
```

输出在 `apps/student-desktop/dist/`，复制或 rsync 到服务器 `student-dist/` 目录，配置细节见 `deploy/README.md`。

Tauri 桌面包（仅本机实验，非生产路径）：

```bash
cd apps/student-desktop
pnpm tauri dev
```

学生使用教师端名单中的学号与姓名注册，登录后可在三个模块之间切换。

## 生产部署

项目部署在同一域名下：

| 入口 | 地址 |
|---|---|
| 学生端 SPA | `https://bujiuhong6.top/student/` |
| 教师端 | `https://bujiuhong6.top/teacher/login` |
| API | `https://bujiuhong6.top/v1/...` |
| 健康检查 | `https://bujiuhong6.top/health` |

部署步骤、Nginx 配置、systemd 单元文件见 `deploy/README.md`。

运行时 SQLite 数据库存放在服务器 `services/api/data/teach.db`，不提交到仓库。本地测试数据保留在本机。

**备份**：定期将服务器上的 `teach.db` 下载到本地安全位置。恢复时停止服务、替换文件、运行 `alembic upgrade head`、再启动服务。

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

`CHAT_LLM_BASE_URL` / `CHAT_LLM_API_KEY` 可单独配置学生 AI 助手；未设置时回退到 `LLM_BASE_URL` / `LLM_API_KEY`。教师端的「大模型接入」也可维护运行时配置。

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
- `AI智能预习`、`AI课堂练习`、`AI课后作业` 属于程序设计好的课程内容。运行 `scripts/initialize_content_db.py` 默认只补齐缺失 seed，并清空学生、名单、班级、提交记录等运行时数据；已有三类课程内容会被保留。
