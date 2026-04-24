# Teaching API（`services/api`）

FastAPI 应用，负责教师端 HTML、学生 REST、章发布、聊天代理等。

## 本地运行

```bash
cd services/api
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# 编辑 .env（JWT、数据库等）
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

`GET /health` 应返回 `{"ok":true}`。

## 学生端 CORS（Chat / `Failed to fetch`）

学生桌面或 Vite  dev 可能使用 `localhost` / `127.0.0.1` 的**不同端口**（1420、5173 等）。默认开启 **`CORS_DEV_LOCALHOST_REGEX=true`**（可在 `.env` 覆盖）：对 `http(s)://localhost`、`127.0.0.1`、`tauri.localhost` **任意端口** 允许跨域。上线时可将 `CORS_DEV_LOCALHOST_REGEX=false` 并仅保留你站点域名。

## OpenAI 兼容 LLM（推荐：OpenRouter）

章「从素材生成」与学生 **AI 学习助手** 均使用 `POST {base}/v1/chat/completions`，`Authorization: Bearer <API Key>`。

### OpenRouter

1. 在 [OpenRouter](https://openrouter.ai/) 创建 API Key，在模型页选用要用的 **model id**（如 `openai/gpt-4o-mini`）。
2. 在 `services/api/.env` 中配置（示例；请替换为你的 Key 与模型名）：

```env
CHAPTER_GEN_MOCK=0
LLM_BASE_URL=https://openrouter.ai/api
LLM_API_KEY=sk-or-v1-...
CHAPTER_GEN_MODEL=openai/gpt-4o-mini
CHAT_MODEL=openai/gpt-4o-mini
```

**Base URL**：OpenRouter 文档里常写 `https://openrouter.ai/api/v1`。本服务会拼 `{base}/v1/chat/completions`，因此请写 **`https://openrouter.ai/api`（不要带 `/v1`）**；若误写 `.../api/v1`，程序会去掉尾部 `/v1`，最终仍请求 `https://openrouter.ai/api/v1/chat/completions`。

聊天可单独指定 `CHAT_LLM_BASE_URL` / `CHAT_LLM_API_KEY`；若不设，则回退到 `LLM_BASE_URL` / `LLM_API_KEY`。

**可选头**（排行榜/来源展示，非鉴权必需）：若 `LLM_BASE_URL` 或 `CHAT_LLM_BASE_URL` 指向 `openrouter.ai`，可设置：

- `OPENROUTER_HTTP_REFERER`（对应 `HTTP-Referer`）
- `OPENROUTER_TITLE`（对应 `X-OpenRouter-Title`）

### 其他厂商（如硅基流动）

同样为 OpenAI 兼容时，将 `LLM_BASE_URL` 设为**不含**路径 `/v1` 的根（代码会拼 `/v1/chat/completions`）。模型名以厂商控制台为准。

**Mock 开发**：保留 `CHAPTER_GEN_MOCK=1` 时，章生成仍返回固定示范 JSON；学生聊天在未配置任何 LLM 基址时会返回带 `mock: true` 的 JSON 响应。

## 测试

```bash
cd services/api
pytest -q
ruff check app tests
```

Docker 与生产环境变量见仓库根目录 `docker-compose.yml` 与 `Dockerfile`。
