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

## 硅基流动（SiliconFlow）OpenAI 兼容 API

章「从素材生成」与学生 **AI 学习助手** 均使用 `POST {base}/v1/chat/completions`，`Authorization: Bearer <API Key>`。

1. 在 [硅基流动控制台](https://cloud.siliconflow.cn/) 创建 API Key，并确认要用的**模型 ID**（文档或控制台中的名称，如 `Qwen/Qwen2.5-7B-Instruct`）。
2. 在 `services/api/.env` 中配置（示例；请替换为你的 Key 与模型名）：

```env
CHAPTER_GEN_MOCK=0
LLM_BASE_URL=https://api.siliconflow.cn
LLM_API_KEY=你的密钥
CHAPTER_GEN_MODEL=Qwen/Qwen2.5-7B-Instruct
CHAT_MODEL=Qwen/Qwen2.5-7B-Instruct
```

聊天可单独指定 `CHAT_LLM_BASE_URL` / `CHAT_LLM_API_KEY`；若不设，则回退到 `LLM_BASE_URL` / `LLM_API_KEY`。

**Base URL**：建议写 **`https://api.siliconflow.cn`（不要带 `/v1`）**，与代码中拼接的 `/v1/chat/completions` 一致。若误写成官方示例里的 `https://api.siliconflow.cn/v1`，程序会自动去掉尾部 `/v1`，避免请求变成 `/v1/v1/chat/completions`。

**Mock 开发**：保留 `CHAPTER_GEN_MOCK=1` 或不在 `.env` 中关 mock 时，章生成仍返回固定示范 JSON；学生聊天在未配置任何 LLM 基址时会返回带 `mock: true` 的 JSON 响应。

## 测试

```bash
cd services/api
pytest -q
ruff check app tests
```

Docker 与生产环境变量见仓库根目录 `docker-compose.yml` 与 `Dockerfile`。
