# AI + Python 教学系统 — 实现计划

> **给自动化执行者看：** 必须配合子技能：优先 `superpowers:subagent-driven-development`（推荐），或 `superpowers:executing-plans`，**按任务逐步**实现。步骤使用复选框（`- [ ]`）方便勾选跟踪。

**目标：** 交付 [设计规格](../specs/2026-04-23-ai-python-teaching-system-design.md) 中描述的 **MVP**：**HTTPS** 接口，含教师管理员、名单、章的草稿/发布、**AI 生成**草稿入口；学生侧含登录、读章、**cell 执行结果上报**、**本章完成**、**聊天代理**；并搭出 **Tauri** 学生端壳、**HTMX** 教师 **Web** 脚手架（与设计一致）。

**架构：** 单仓（monorepo）：`services/api`（**FastAPI** + **SQLAlchemy** + **Alembic** + **Jinja2** + **HTMX** 教师页，**同进程** 或 子包）；`apps/student-desktop`（**Tauri** + **WebView** 加载学生 H5/练习页）。数据库 **初期 SQLite**（WAL 单文件、挂数据卷）；需要时再在 **docker-compose** 里加**可选** **Postgres**；生产 **HTTPS** 用 **Caddy**（与设计一致）。

**技术栈：** Python 3.12+、FastAPI、SQLAlchemy 2、Alembic、Pydantic v2、**PyJWT**、cryptography（**AES-GCM**）、**bcrypt**、**aiosqlite**；Docker Compose；**httpx** 调外部 **LLM**（可选）。**可选**依赖 `psycopg[binary]` 仅在切 **PostgreSQL** 时启用。

---

## 新仓库文件分工（从头建）

| 路径 | 职责 |
|------|------|
| `services/api/app/main.py` | FastAPI 应用、CORS、注册路由 |
| `services/api/app/config.py` | 从环境变量读配置 |
| `services/api/app/db/` | 会话、模型、**Alembic** 环境 |
| `services/api/app/routers/admin.py` | 初始化、登录、名单、章、发布、进度 |
| `services/api/app/routers/student.py` | 注册、登录、读章、验证 cell、完成章、聊天 |
| `services/api/app/services/crypto.py` | 学生密码加解密 |
| `services/api/app/services/chapter_gen.py` | 调 **LLM** 生成章草稿 **JSON**、形状校验 |
| `services/api/tests/` | **pytest** |
| `docker-compose.yml` | **API** + **SQLite 数据卷**；**可选** `postgres` 服务；**Caddy** 反代 |
| `services/api/app/templates/` | **Jinja2** + **HTMX** 教师端页面（**任务 10**；不设独立 `apps/teacher-web` 除非你日后拆分） |
| `apps/student-desktop/` | **Tauri** 学生端外壳（靠后任务） |

---

### 任务 1：目录结构与 FastAPI 骨架

**要创建的文件：**
- `services/api/pyproject.toml`
- `services/api/app/main.py`
- `services/api/app/config.py`
- `docker-compose.yml`

- [x] **步骤 1：写入 pyproject 与依赖**（见下方 `toml` 代码块；**SQLite** 用 **aiosqlite**；**Postgres** 为可选时再加 **psycopg**）

- [x] **步骤 2：最小可跑的 FastAPI**（见下方 `python` 代码块）

- [x] **步骤 3：从环境读配置**（`config.py` 见下方；`student_password_key` 可本地 **`.env`** 提供 32 字节 **base64**；**缺省**有脚手架占位，**仅本机/开发**；生产必换。默认 `database_url` 指向 **SQLite** 文件 `data/teach.db`）

- [x] **步骤 4：docker-compose 挂数据卷、起 API 容器**（见下方 `yaml`；**纯 SQLite** 不强制 **db** 服务；`services/api/Dockerfile` 供镜像构建）

- [x] **步骤 5：运行并验证**  
  执行：`cd services/api && . .venv/bin/activate && uvicorn app.main:app --reload`（或 `python -m uvicorn app.main:app --reload`）  
  再执行：`curl -s http://127.0.0.1:8000/health`  
  期望返回：`{"ok":true}`

- [x] **步骤 6：提交 Git**

```toml
[project]
name = "teaching-api"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.30",
  "sqlalchemy>=2.0",
  "alembic>=1.13",
  "pydantic-settings>=2.0",
  "aiosqlite>=0.20",
  "python-multipart>=0.0.9",
  "passlib[bcrypt]>=1.7",
  "cryptography>=42.0",
  "pyjwt[crypto]>=2.8",
  "httpx>=0.27",
  "jinja2>=3.1",
]
[project.optional-dependencies]
dev = ["pytest>=8", "httpx>=0.27", "ruff>=0.6"]
postgres = ["psycopg[binary]>=3.1"]
```

```python
# services/api/app/main.py
from fastapi import FastAPI
app = FastAPI(title="Teaching API", version="0.1.0")

@app.get("/health")
def health():
    return {"ok": True}
```

```python
# services/api/app/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./data/teach.db"
    jwt_secret: str = "change-me-in-prod"
    student_password_key: str  # 32 字节 base64，供 AES-GCM
    admin_bootstrap_token: str | None = None  # 可选，一次性

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
```

```yaml
# docker-compose.yml（MVP：API + SQLite 数据卷；无独立 db 容器）
services:
  api:
    build: ./services/api
    volumes:
      - teach_data:/data
    environment:
      DATABASE_URL: sqlite+aiosqlite:////data/teach.db
    ports: ["8000:8000"]

volumes:
  teach_data: {}
```

```bash
git add services/api docker-compose.yml
git commit -m "chore: scaffold FastAPI with SQLite volume"
```

---

### 任务 2：SQLAlchemy 数据模型与 Alembic 首版迁移

**文件：** 新建 `services/api/app/db/base.py`、`models.py`、`session.py`；`alembic/versions/001_initial.py`（或 `alembic revision --autogenerate`）；`main.py` 里加数据库生命周期（lifespan）。

- [x] **步骤 1：按[设计规格 §3–4](../specs/2026-04-23-ai-python-teaching-system-design.md)** 定义表：`admin_config`、`students`、`roster_entries`、`chapters`、`cell_verifications`、`chapter_completions` 等字段与类型。

- [x] **步骤 2：执行 `alembic init` 并 `alembic revision --autogenerate -m "initial"`，人工过一遍 diff。**

- [x] **步骤 3：执行 `alembic upgrade head`**

- [x] **步骤 4：提交** `git commit -m "feat(api): add db models and initial migration"`

---

### 任务 3：管理员初始化与登录（bcrypt + 会话 **Cookie**）

**文件：** 新建 `routers/admin.py`、`deps.py`；`main.py` 挂载路由。

- [x] **POST `/v1/admin/bootstrap`**：Body `{"password":"..."}`；若表 `admin_config` 尚无为 **bcrypt** 存哈希并插入，否则 **403**。

- [x] **POST `/v1/admin/login`**：校验 **bcrypt**；设 **HttpOnly、签名** 的 **Cookie** `teacher_session`（若选 **纯 SPA** 用 **Bearer** 亦可，实现里**写死**一种并文档化）。

- [x] **GET `/v1/admin/me`**：会话有效则 **200**。

- [x] **pytest**：`test_bootstrap_and_login` 用 **TestClient**。

- [x] **提交**

---

### 任务 4：名单导入与学生注册/绑定

**文件：** 改 `admin.py` 增加 `POST /v1/admin/roster/import`（**CSV/JSON**）；`student.py` 增加 `POST /v1/student/register`。

- [ ] **导入**：新建或更新 `roster_entries`，尚无学生时 `status=pending`。

- [ ] **注册**：`学号+姓名` 与名单**完全一致**则创建 `students`、加密密码（见**任务 5**），名单行改为 `bound`。

- [ ] **测试**：不匹配、成功**两条**路径。

- [ ] **提交**

---

### 任务 5：学生密码可逆（AES-GCM）与学生 **JWT** 登录

**文件：** 新建 `services/api/app/services/crypto.py`；`student.py` 增加 `POST /v1/student/login`、`GET /v1/student/me`。

- [ ] 实现 `encrypt_password` / `decrypt_password`；库中存 **base64(ciphertext+nonce)**。

- [ ] 教师**查看**学生密码的 **GET**（仅**带** `teacher_session`）：解密后返回，**在 OpenAPI/注释里**写明敏感性与课堂用途。

- [ ] 学生 **JWT**：`sub=学生 id`，`exp=15` 分钟（可按产品调整）。

- [ ] **提交**

---

### 任务 6：章 **CRUD**、**AI 生成**草稿、发布时校验「扩展题」

**文件：** 新建 `services/api/app/services/chapter_json.py`（**Pydantic** 描述 `published_content`；`validate_for_publish` 可清空/拒绝过长的 `extensionCell.starterCode`）；改 `admin.py`。

- [ ] 草稿建章，含 `source_material`，`ai_generated_draft` 可为空。

- [ ] **POST** `/v1/admin/chapters/:id/generate`：调**任务 7** 的 `chapter_gen`；开发中可用**写死** JSON；写 `ai_generated_draft` 与 `content_status=draft`。

- [ ] **发布**：跑校验器后写入 `published_content` 与状态**已发布**。

- [ ] **提交**

---

### 任务 7：**LLM** 生章：开发用假数据 + 正式用 **httpx**（厂家待定）

**文件：** `services/api/app/services/chapter_gen.py`

- [ ] 若环境变量 **`CHAPTER_GEN_MOCK=1`**，返回**固定**合法 **JSON** 给测试用。

- [ ] 否则 **`httpx` POST** 到 `LLM_BASE_URL` + `LLM_API_KEY`；把响应解析成章 **JSON**；**429** 要处理。

- [ ] **提交**

---

### 任务 8：学生读已发布章、上报 cell 执行结果、标记本章完成

**文件：** 改 `student.py`

- [ ] **GET** 只返回**已发布**章；**GET 单章** 去掉**草稿**字段。

- [ ] **POST** `/v1/student/cells/verify`：按「学生+章+cell」**只保留最新**一条或覆盖更新 `cell_verifications`。

- [ ] **POST 本章完成**：从章 **JSON** 展开必做 `cell` id 列表，**全部** `run_ok` 才插入 `chapter_completions`；重复提交**幂等 200**。

- [ ] **测试**：**缺 cell 未完成**时**应失败**。

- [ ] **提交**

---

### 任务 9：聊天**代理**（**无 RAG**）

**文件：** 新建 `routers/chat.py` 或挂在 `student.py`

- [ ] **POST** `/v1/student/chat`，Body 带 `chapterId`、`cellId`、`messages`，转发到环境变量里 **OpenAI 兼容** 的聊天接口；**流式**可选项。

- [ ] **限流**：按**学生**（内存**字典** 即可；日后可上 **Redis**）。

- [ ] **提交**

---

### 任务 10：教师 Web 最小界面（章列表、导入名单、发布）

**文件（与设计一致）：** **FastAPI** 同仓内 `app/templates/` + `Jinja2` + **HTMX** 路由；**不**为教师端单独开 **Vite+React** 仓库，除非你后续要拆**可视化**章编辑器再评估。

- [ ] 登录页 → 调 `POST /v1/admin/login`；**HTMX** 局部刷新或整页**皆可**；**同域** 无需**跨源** **CORS**（学生 **Tauri** 仍用**配置**的 **API** 基址）。

- [ ] 名单**导入表单**、章**编辑**（MVP 可用**大** **textarea** 直接贴 **JSON**）。

- [ ] 手工**走一遍**联调清单（可写在**本计划末尾**自列表）。

- [ ] **提交**

---

### 任务 11：学生**桌面**（Tauri 壳 + 内嵌学生页）

**文件：** `apps/student-desktop/`

- [ ] 执行 `pnpm create tauri-app`（配 **React/Vite**）；**构建**参数绑定 `API_BASE_URL`。

- [ ] 一屏**流程**：登录 → 章列表 → 章练习页（**iframe** 或 **内嵌** **WebView** 打开学生 **SPA** 或由 **API 静**态托管）。

- [ ] **Win/macOS 打包** 可先**本地**；**CI** 上**构建**为**可选项**（MVP 非必须）。

- [ ] **提交**

---

### 任务 12：在 **WebView** 里用 **Pyodide** 跑 **cell**（MVP）

**文件：** 新建 `apps/student-web/` 或 写在 **Tauri** 的 `src` 里

- [ ] 加载 **Pyodide**；用 `GET /v1/student/chapters/:id` 的 **JSON** 渲染**多个** **cell**。

- [ ] 点「运行」：若无未捕获错误，**POST** `cells/verify`，`runOk: true`。

- [ ] **提交**

---

## 自查（**writing-plans** 要求）

1. **规格是否覆盖到任务：** 准备清单、设计里关于 **身份、章 JSON、过关、章完成、聊天、不评分、AI 草稿、人审** 等，在**任务 2–12** 中均有对应。  
2. **禁止留白：** 不用「TBD/以后再补」**代替** 实现说明；**LLM 厂家** 用**环境变量** + **Task 7** 的 **mock** 关住缺口。  
3. **类型一致：** `cell_id` 在 **API** 与 **JSON** 中统一为**字符串**。

---

## 交给执行者（**writing-plans** 收束语）

- 本计划文件路径：`docs/superpowers/plans/2026-04-23-ai-python-teaching-system-implementation.md`  
- **二选一**执行方式：  
  1. **子代理模式（推荐）**：**每个**「任务」换**新**子代理，**任务**之间做**复核**。  
  2. **本会话内联**：用 **`executing-plans`** 按**检查点****批量**推进。

*实现时一律以 **[设计规格](../specs/2026-04-23-ai-python-teaching-system-design.md)** 为准。若**技术栈** 与 上文**不同**（例如**全部**用 **Node**），**先** 重写**任务 1** 的**文件分工表** 和 **首包依赖**，**再** 做 后续 任务。*
