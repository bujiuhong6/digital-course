# Teaching API（`services/api`）

FastAPI 应用，负责教师端 HTML、学生 REST API、学生名单与班级管理、课程内容发布、聊天代理和 OpenAI 兼容大模型接入。

## 本地运行

```bash
cd services/api
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# 编辑 .env（JWT、数据库等）
python -m alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

`GET /health` 应返回 `{"ok":true}`。

## 初始化课程内容

仓库提交代码、迁移、测试和 seed；本地 SQLite 数据库留在运行环境。`AI智能预习`、`AI课堂练习`、`AI课后作业` 都属于程序设计好的课程内容；初始化脚本默认保护这些内容。

基础课堂练习 seed 保存在 `services/api/seeds/chapters.json`，其中不包含管理员账号、学生名单、班级、学生账号、答题记录和审计记录。

从仓库根目录执行：

```bash
services/api/.venv/bin/python scripts/initialize_content_db.py --prune-extra-chapters
```

效果：

- 补齐 seed 中缺失的已发布课堂练习章节。
- 保留已有 `AI智能预习`、`AI课堂练习`、`AI课后作业` 内容。
- 清空 `admin_config`、`students`、`classes`、`roster_entries`、`cell_verifications`、`chapter_completions`、`admin_audit`。
- 教师端下次访问 `/teacher/login` 时会进入首次管理员账号设置流程。

`--prune-extra-chapters` 会被保护逻辑拦住：默认保留教师已设计/发布的额外课堂练习章节。显式加 `--allow-delete-designed-content` 时，脚本才会允许覆盖 seed 中同 slug 的课堂练习内容并删除 seed 外章节。

如只想导入章节并保留运行时数据：

```bash
services/api/.venv/bin/python scripts/initialize_content_db.py --keep-runtime
```

## 学生端 CORS（Chat / `Failed to fetch`）

学生桌面或 Vite  dev 可能使用 `localhost` / `127.0.0.1` 的**不同端口**（1420、5173 等）。默认开启 **`CORS_DEV_LOCALHOST_REGEX=true`**（可在 `.env` 覆盖）：对 `http(s)://localhost`、`127.0.0.1`、`tauri.localhost` **任意端口** 允许跨域。上线时可将 `CORS_DEV_LOCALHOST_REGEX=false` 并仅保留你站点域名。

## OpenAI 兼容 LLM

章「从素材生成」与学生 **AI 学习助手** 均使用 OpenAI 兼容 Chat Completions，`Authorization: Bearer <API Key>`。

### OpenRouter

1. 在 [OpenRouter](https://openrouter.ai/) 创建 API Key，在模型页选用要用的 **model id**（如 `openai/gpt-4o-mini`）。
2. 在 `services/api/.env` 中配置（示例；请替换为你的 Key 与模型名）：

```env
CHAPTER_GEN_MOCK=0
LLM_BASE_URL=https://openrouter.ai/api
LLM_API_KEY=<your-openrouter-api-key>
CHAPTER_GEN_MODEL=openai/gpt-4o-mini
CHAT_MODEL=openai/gpt-4o-mini
```

**Base URL**：OpenRouter 文档里常写 `https://openrouter.ai/api/v1`。本服务会拼 `{base}/v1/chat/completions`，因此请写 **`https://openrouter.ai/api`（不要带 `/v1`）**；若误写 `.../api/v1`，程序会去掉尾部 `/v1`，最终仍请求 `https://openrouter.ai/api/v1/chat/completions`。

聊天可单独指定 `CHAT_LLM_BASE_URL` / `CHAT_LLM_API_KEY`；若不设，则回退到 `LLM_BASE_URL` / `LLM_API_KEY`。

**可选头**（排行榜/来源展示，非鉴权必需）：若 `LLM_BASE_URL` 或 `CHAT_LLM_BASE_URL` 指向 `openrouter.ai`，可设置：

- `OPENROUTER_HTTP_REFERER`（对应 `HTTP-Referer`）
- `OPENROUTER_TITLE`（对应 `X-OpenRouter-Title`）

### 其他厂商（如硅基流动、DeepSeek）

硅基流动等多数 OpenAI 兼容厂商，将 `LLM_BASE_URL` 设为**不含**路径 `/v1` 的根（代码会拼 `/v1/chat/completions`）。DeepSeek 使用官方基址 `https://api.deepseek.com`，本服务会请求 `https://api.deepseek.com/chat/completions`。模型名以厂商控制台为准，例如 `deepseek-v4-flash`。

DeepSeek 学生 AI 助手示例：

```env
CHAPTER_GEN_MOCK=0
CHAT_LLM_BASE_URL=https://api.deepseek.com
CHAT_LLM_API_KEY=<your-deepseek-api-key>
CHAT_MODEL=deepseek-v4-flash
```

硅基流动示例：

```env
CHAPTER_GEN_MOCK=0
LLM_BASE_URL=https://api.siliconflow.cn
LLM_API_KEY=<your-siliconflow-api-key>
CHAPTER_GEN_MODEL=deepseek-ai/DeepSeek-V4-Flash
CHAT_MODEL=deepseek-ai/DeepSeek-V4-Flash
```

**Mock 开发**：保留 `CHAPTER_GEN_MOCK=1` 时，章生成仍返回固定示范 JSON；学生聊天在未配置任何 LLM 基址时会返回带 `mock: true` 的 JSON 响应。

**密钥安全**：只在 `services/api/.env` 填写真实 API Key。`.env` 已被 `.gitignore` 忽略，提交前仍应运行 `git status --short` 确认没有把密钥文件加入暂存区。

## 测试

```bash
cd services/api
pytest -q
ruff check app tests
```

Docker 与生产环境变量见仓库根目录 `docker-compose.yml` 与 `Dockerfile`。
