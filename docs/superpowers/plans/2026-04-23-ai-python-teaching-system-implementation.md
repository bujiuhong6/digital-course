# AI + Python 教学系统 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the MVP described in [设计规格](../specs/2026-04-23-ai-python-teaching-system-design.md): HTTPS API with teacher admin + roster + chapter draft/publish + AI generation hook, student auth + chapter read + cell verify + chapter complete + chat proxy; scaffold for Tauri/Electron student shell and teacher web.

**Architecture:** Monorepo: `services/api` (FastAPI + SQLAlchemy + Alembic), `apps/teacher-web` (Vite + React or static HTMX—pick one in Task 1 and stick to it), `apps/student-desktop` (Tauri + webview loading local student UI or embedded); PostgreSQL in Docker; Caddy or Traefik for TLS in production.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2, JWT (python-jose or PyJWT), cryptography (AES-GCM for student passwords), bcrypt; Docker Compose; optional: `httpx` for outbound LLM calls.

---

## File map (greenfield)

| Path | Responsibility |
|------|----------------|
| `services/api/app/main.py` | FastAPI app, CORS, routers |
| `services/api/app/config.py` | Settings from env |
| `services/api/app/db/` | Session, models, alembic env |
| `services/api/app/routers/admin.py` | Bootstrap, login, roster, chapters, publish, progress |
| `services/api/app/routers/student.py` | Register, login, chapters, verify, complete, chat |
| `services/api/app/services/crypto.py` | Student password encrypt/decrypt |
| `services/api/app/services/chapter_gen.py` | Call LLM for draft JSON, validate shape |
| `services/api/tests/` | Pytest |
| `docker-compose.yml` | API + Postgres (+ Caddy optional) |
| `apps/teacher-web/` | Teacher UI |
| `apps/student-desktop/` | Tauri wrapper (later tasks) |

---

### Task 1: Repository layout and FastAPI skeleton

**Files:**
- Create: `services/api/pyproject.toml`
- Create: `services/api/app/main.py`
- Create: `services/api/app/config.py`
- Create: `docker-compose.yml`

- [ ] **Step 1: Add pyproject with dependencies**

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
  "psycopg[binary]>=3.1",
  "python-multipart>=0.0.9",
  "passlib[bcrypt]>=1.7",
  "cryptography>=42.0",
  "pyjwt[crypto]>=2.8",
  "httpx>=0.27",
]
[project.optional-dependencies]
dev = ["pytest>=8", "httpx>=0.27", "ruff>=0.6"]
```

- [ ] **Step 2: Minimal FastAPI app**

```python
# services/api/app/main.py
from fastapi import FastAPI
app = FastAPI(title="Teaching API", version="0.1.0")

@app.get("/health")
def health():
    return {"ok": True}
```

- [ ] **Step 3: Config from env**

```python
# services/api/app/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://teach:teach@localhost:5432/teach"
    jwt_secret: str = "change-me-in-prod"
    student_password_key: str  # 32-byte base64 for AES-GCM
    admin_bootstrap_token: str | None = None  # optional one-time

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
```

- [ ] **Step 4: docker-compose with Postgres**

```yaml
# docker-compose.yml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: teach
      POSTGRES_PASSWORD: teach
      POSTGRES_DB: teach
    ports: ["5432:5432"]
```

- [ ] **Step 5: Run and verify**

Run: `cd services/api && uv run uvicorn app.main:app --reload`  
Run: `curl -s http://127.0.0.1:8000/health`  
Expected: `{"ok":true}`

- [ ] **Step 6: Commit**

```bash
git add services/api docker-compose.yml
git commit -m "chore: scaffold FastAPI and docker-compose postgres"
```

---

### Task 2: SQLAlchemy models and Alembic initial migration

**Files:**
- Create: `services/api/app/db/base.py`, `services/api/app/db/models.py`, `services/api/app/db/session.py`
- Create: `services/api/alembic/versions/001_initial.py` (or autogenerate)
- Modify: `services/api/app/main.py` (include lifespan DB)

- [ ] **Step 1: Define models** matching [design doc §3–4](../specs/2026-04-23-ai-python-teaching-system-design.md): `admin_config`, `students`, `roster_entries`, `chapters`, `cell_verifications`, `chapter_completions` with fields as specified.

- [ ] **Step 2: `alembic init` and first migration** — run `alembic revision --autogenerate -m "initial"` then review.

- [ ] **Step 3: Apply migration** — `alembic upgrade head`

- [ ] **Step 4: Commit** — `git commit -m "feat(api): add db models and initial migration"`

---

### Task 3: Admin bootstrap and login (bcrypt, cookie session)

**Files:**
- Create: `services/api/app/routers/admin.py`
- Create: `services/api/app/deps.py` (teacher session dependency)
- Modify: `services/api/app/main.py` (mount router)

- [ ] **Step 1: POST `/v1/admin/bootstrap`** — body `{"password":"..."}`; if `admin_config` row missing, hash with bcrypt and insert; else 403.

- [ ] **Step 2: POST `/v1/admin/login`** — verify bcrypt; set signed HttpOnly cookie `teacher_session` (or return JWT if SPA prefers header—document choice).

- [ ] **Step 3: GET `/v1/admin/me`** — returns 200 if session valid.

- [ ] **Step 4: Pytest** — `test_bootstrap_and_login` with TestClient.

- [ ] **Step 5: Commit**

---

### Task 4: Roster import and student register/bind

**Files:**
- Modify: `services/api/app/routers/admin.py` — `POST /v1/admin/roster/import` CSV/JSON
- Create: `services/api/app/routers/student.py` — `POST /v1/student/register`

- [ ] **Step 1: Import** creates/updates `roster_entries` with `status=pending` where no `student` yet.

- [ ] **Step 2: Register** — match `student_no`+`full_name` against roster; if ok, create `students` row with encrypted password (see Task 5); set roster `bound`.

- [ ] **Step 3: Tests** for mismatch (401/404) and success.

- [ ] **Step 4: Commit**

---

### Task 5: Reversible student password (AES-GCM) and student JWT login

**Files:**
- Create: `services/api/app/services/crypto.py`
- Modify: `services/api/app/routers/student.py` — `POST /v1/student/login`, `GET /v1/student/me`

- [ ] **Step 1: Implement** `encrypt_password(plain: str) -> str` and `decrypt_password(blob: str) -> str` using `STUDENT_PASSWORD_ENCRYPTION_KEY` and AES-GCM; store `ciphertext:nonce` as base64 in DB.

- [ ] **Step 2: Admin GET** student password — decrypt and return in JSON **only** for `teacher_session` (document security warning in response schema description).

- [ ] **Step 3: JWT** for students `sub=student_id`, `exp=15m`.

- [ ] **Step 4: Commit**

---

### Task 6: Chapters CRUD, AI generate draft, publish with extension validation

**Files:**
- Create: `services/api/app/services/chapter_json.py` — Pydantic models for `published_content` shape; `validate_for_publish` clears or rejects `extensionCell.starterCode` if too long
- Modify: `services/api/app/routers/admin.py`

- [ ] **Step 1: CRUD** draft chapters with `source_material`, `ai_generated_draft` null.

- [ ] **Step 2: POST `/v1/admin/chapters/:id/generate`** — call `chapter_gen.service` (Task 7) or stub that returns static JSON in dev; write `ai_generated_draft` and `content_status=draft`.

- [ ] **Step 3: POST publish** — run validator; set `published_content` and `published`.

- [ ] **Step 4: Commit**

---

### Task 7: LLM generate stub and real `httpx` call (provider TBD)

**Files:**
- Create: `services/api/app/services/chapter_gen.py`

- [ ] **Step 1: If `CHAPTER_GEN_MOCK=1`**, return fixed valid JSON for tests.

- [ ] **Step 2: Else** `httpx` POST to `LLM_BASE_URL` with `LLM_API_KEY` from env; map response to chapter JSON; handle 429.

- [ ] **Step 3: Commit**

---

### Task 8: Student chapter read, cell verify, chapter complete

**Files:**
- Modify: `services/api/app/routers/student.py`

- [ ] **Step 1: GET** published chapters and single chapter (strip draft fields).

- [ ] **Step 2: POST `/v1/student/cells/verify`** — upsert `cell_verifications` (latest only).

- [ ] **Step 3: POST complete** — load chapter JSON, collect required cell ids, check all `run_ok` for student; if ok insert `chapter_completions` (idempotent 200).

- [ ] **Step 4: Tests** for incomplete chapter rejection.

- [ ] **Step 5: Commit**

---

### Task 9: Chat proxy (no RAG)

**Files:**
- Create: `services/api/app/routers/chat.py` or under `student.py`

- [ ] **Step 1: POST `/v1/student/chat`** with `chapterId`, `cellId`, `messages` — forward to OpenAI-compatible endpoint from env; stream optional.

- [ ] **Step 2: Rate limit** per student IP + id (in-memory or Redis later).

- [ ] **Step 3: Commit**

---

### Task 10: Teacher web minimal UI (list chapters, import roster, publish)

**Files:**
- Create under `apps/teacher-web/` — Vite + React **or** server-rendered Jinja2 inside FastAPI (simpler for solo)

- [ ] **Step 1: Login form** → `/v1/admin/login` — if choosing **HTMX in FastAPI**, add `app/templates/` and 5 routes; if **SPA**, CORS to API origin.

- [ ] **Step 2: Roster import form** and **chapter editor** (JSON textarea OK for MVP).

- [ ] **Step 3: E2E** manual checklist in plan footer.

- [ ] **Step 4: Commit**

---

### Task 11: Student desktop (Tauri) shell loading student UI

**Files:**
- Create: `apps/student-desktop/`

- [ ] **Step 1: `pnpm create tauri-app`** with React/Vite; set `API_BASE_URL` build arg.

- [ ] **Step 2: One screen** — login, chapter list, chapter view with iframe or embedded webview pointing to `student` SPA (or same API-served static).

- [ ] **Step 3: Build** for Win/macOS in CI (GitHub Actions) — **optional** for MVP; local build enough first.

- [ ] **Step 4: Commit**

---

### Task 12: Pyodide cell runner in webview (MVP)

**Files:**
- Create: `apps/student-web/` or pages inside Tauri

- [ ] **Step 1: Load Pyodide**; render cells from `GET /v1/student/chapters/:id` JSON.

- [ ] **Step 2: On Run** — if no error, `POST /v1/student/cells/verify` with `runOk: true`.

- [ ] **Step 3: Commit**

---

## Self-review (writing-plans)

1. **Spec coverage:** 准备清单 与 设计 中的 身份、章 JSON、过 关、章 完成、Chat、无 打分、AI 草 稿、人审 —— 均 映射 到 **Task 2–12**。  
2. **Placeholders:** 上 面 **不** 使用「TBD」**实现** 句；**LLM 供应商** 在 **Task 7** 用 **环境变量** 与 **mock** 关 闭 空 白。  
3. **Type consistency:** `cell_id` 全 文 用 **string** 与 **JSON** 一致。

---

## Handoff (per writing-plans)

**Plan 保存 于** `docs/superpowers/plans/2026-04-23-ai-python-teaching-system-implementation.md`.

**执行 时 可 二选 一：**

1. **Subagent-Driven（推荐）** — 每 **Task** 新 子 代理、任务 间 复核。  
2. **Inline** — 本会话 用 **executing-plans** 按 检查点 批量 做。

*实现 时 以 设计 规 格 为 准；**若** 技术栈 与 上 文 不 同（**例** 全 **Node**），**重 写** **Task 1 文件 映射** 后 再 执 行 后续 任务。*
