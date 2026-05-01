# digital-course

《数字技术与应用》AI 智能编程学习平台。项目包含教师端 FastAPI 管理台、学生端 React/Vite Web SPA、Pyodide 代码执行、学生名单与班级管理、OpenAI 兼容大模型接入，以及三类课程模块：

- `AI智能预习`：教师发布课前目标与预习任务，学生提交反馈。
- `AI课堂练习`：学生进入章节练习，完成随堂编程任务，页面内提供 AI 助教陪练。
- `AI课后作业`：教师发布单选、主观、代码混合题，学生提交后由大模型批改并返回分数和反馈。

本仓库提交代码、数据库迁移、静态资源、测试和预置课程内容。运行时 SQLite 数据库、管理员账号、学生名单、班级、学生账号、答题记录、本地 `.env` 与 API Key 均留在运行环境（本机或服务器）。

## 目录结构

```text
digital-course/
├── services/api/          # FastAPI 后端、教师端 HTML、学生 API、Alembic 迁移
├── apps/student-desktop/  # React + Vite 学生端 Web SPA；src-tauri/ 为桌面版实验源码
├── scripts/               # 数据库内容初始化脚本
├── docs/                  # 文档与模板
├── deploy/                # Nginx 配置、systemd 单元文件、部署检查清单
└── docker-compose.yml     # API + SQLite 数据卷快速体验
```

## 数据与密钥

以下内容只保存在本机或服务器运行环境中，提交前请用 `git status --short` 检查暂存区：

- `services/api/.env`：数据库路径、JWT 密钥、LLM API Key、学生密码加密密钥。
- `apps/student-desktop/.env`：学生端本地开发环境变量。
- `services/api/data/teach.db`：SQLite 运行时数据库。
- `services/api/.venv/`：Python 虚拟环境。
- `apps/student-desktop/node_modules/`：Node 依赖。
- `apps/student-desktop/dist/`、服务器 `student-dist/`：构建产物。

## 一、新设备完整安装与本地开发

### 1. 前置要求

- Python 3.12+
- Node.js 20+
- pnpm 8+
- Git

检查版本：

```bash
python3.12 --version
node --version
pnpm --version
git --version
```

### 2. 获取代码

```bash
git clone https://github.com/bujiuhong6/digital-course.git
cd digital-course
```

### 3. 初始化后端 API

Linux / macOS：

```bash
cd services/api

# macOS Homebrew Python
/opt/homebrew/bin/python3.12 -m venv .venv

# Linux 常见写法
# python3.12 -m venv .venv

source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
python -m alembic upgrade head
```

Windows PowerShell：

```powershell
cd services/api
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
python -m alembic upgrade head
```

如 PowerShell 阻止启用虚拟环境，可在当前终端执行：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

回到仓库根目录，初始化预置课程内容。

Linux / macOS：

```bash
cd ../..
services/api/.venv/bin/python scripts/initialize_content_db.py --prune-extra-chapters
```

Windows PowerShell：

```powershell
cd ..\..
.\services\api\.venv\Scripts\python.exe .\scripts\initialize_content_db.py --prune-extra-chapters
```

初始化脚本会补齐预置课堂练习内容，并保留已经存在的 `AI智能预习`、`AI课堂练习`、`AI课后作业` 内容。它会清空管理员账号、学生名单、班级、学生账号、答题记录和审计记录；教师端首次进入会提示设置管理员账号和密码。

如需补齐预置课程内容并保留运行时数据，使用 `--keep-runtime`。

Linux / macOS：

```bash
services/api/.venv/bin/python scripts/initialize_content_db.py --keep-runtime
```

Windows PowerShell：

```powershell
.\services\api\.venv\Scripts\python.exe .\scripts\initialize_content_db.py --keep-runtime
```

启动 API：

Linux / macOS：

```bash
cd services/api
.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Windows PowerShell：

```powershell
cd services/api
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

健康检查：

```bash
curl http://127.0.0.1:8000/health
```

期望返回：

```json
{"ok":true}
```

教师端入口：`http://127.0.0.1:8000/teacher/login`

常用教师端页面：

- `http://127.0.0.1:8000/teacher/prestudy`：AI智能预习。
- `http://127.0.0.1:8000/teacher`：AI课堂练习。
- `http://127.0.0.1:8000/teacher/post-exercises`：AI课后作业。
- `http://127.0.0.1:8000/teacher/llm-settings`：大模型接入。
- `http://127.0.0.1:8000/teacher/roster`：学生名单。
- `http://127.0.0.1:8000/teacher/classes`：班级管理。

### 4. 初始化学生端

新开一个终端，进入学生端目录：

Linux / macOS：

```bash
cd apps/student-desktop
pnpm install
cp .env.example .env
pnpm dev
```

Windows PowerShell：

```powershell
cd apps/student-desktop
pnpm install
Copy-Item .env.example .env
pnpm dev
```

访问 `http://127.0.0.1:1420/`。Vite 开发服务器会将 `/v1` 和 `/health` 代理到 `http://127.0.0.1:8000`，启动学生端前请先启动后端 API。

`pnpm dev` 会执行 `prepare:pyodide`，把 Pyodide 0.27.0 核心文件和课程需要的 wheel 文件同步到 `public/pyodide/v0.27.0/full/`。首次运行需要联网下载，耗时取决于网络环境。

学生使用教师端名单中的学号与姓名注册，登录后可在三个模块之间切换。

### 5. 学生端生产构建与本地预览

```bash
cd apps/student-desktop
pnpm build
```

构建产物输出到 `apps/student-desktop/dist/`。本地预览生产构建：

```bash
pnpm preview
```

`pnpm preview` 只用于本地预览构建结果，生产环境使用 Nginx 提供静态文件。

### 6. 桌面版实验入口

```bash
cd apps/student-desktop
pnpm tauri dev
```

当前生产部署走 Web SPA，`src-tauri/` 保留为桌面版实验源码。

## 二、Docker 快速体验（API）

Docker Compose 当前用于快速启动后端 API 和 SQLite 数据卷，适合检查 API 服务是否能运行。完整预置课程内容初始化建议使用上一节的本地 venv 流程，或使用后文云服务器部署流程。

### 1. 前置要求

- Docker Desktop，或 Docker Engine + Docker Compose V2

检查：

```bash
docker --version
docker compose version
```

### 2. 启动 API

在仓库根目录执行：

```bash
docker compose up --build -d
```

检查容器状态：

```bash
docker compose ps
docker compose logs api
```

健康检查：

```bash
curl http://127.0.0.1:8000/health
```

停止：

```bash
docker compose down
```

### 3. Docker 数据说明

`docker-compose.yml` 使用命名卷 `teach_data` 保存 SQLite 数据，容器内数据库路径是 `/data/teach.db`，数据库地址是 `sqlite+aiosqlite:////data/teach.db`。

当前 Compose 只显式设置 `DATABASE_URL`。如需在 Docker 场景中使用真实 LLM Key，可在本机创建 `docker-compose.override.yml`：

```yaml
services:
  api:
    env_file:
      - ./services/api/.env
```

## 三、云服务器部署（Nginx + systemd）

本节示例路径为 `/www/wwwroot/digital-course`，示例域名为 `your-domain.com`。如使用其他路径或域名，请同步修改：

- `deploy/nginx/digital-course.conf`
- `deploy/systemd/digital-course-api.service`

### 1. 服务器前置准备

服务器需要 Python 3.12、Nginx、systemd、Git 和可用 HTTPS 证书。防火墙建议对外开放 `80`、`443`，API 端口 `8000` 只绑定 `127.0.0.1`，由 Nginx 反向代理访问。

### 2. 上传代码

```bash
cd /www/wwwroot
git clone https://github.com/bujiuhong6/digital-course.git
cd digital-course
```

也可以使用 `rsync` 或 `scp` 上传本地代码。

### 3. 配置后端 `.env`

```bash
cd /www/wwwroot/digital-course/services/api
cp .env.example .env
```

生产环境建议至少设置：

```env
DATABASE_URL=sqlite+aiosqlite:///./data/teach.db
JWT_SECRET=<openssl rand -hex 32 的输出>
ADMIN_COOKIE_SECURE=true
CORS_DEV_LOCALHOST_REGEX=false

CHAPTER_GEN_MOCK=0
LLM_BASE_URL=
LLM_API_KEY=
CHAPTER_GEN_MODEL=

CHAT_LLM_BASE_URL=
CHAT_LLM_API_KEY=
CHAT_MODEL=
```

生成随机密钥示例：

```bash
openssl rand -hex 32
openssl rand -base64 32
```

`JWT_SECRET` 必须使用强随机值。`STUDENT_PASSWORD_KEY` 用于学生密码可逆加密；全新部署可生成新的 Base64 32 字节密钥。迁移已有 SQLite 数据库时，必须与原环境保持一致；原环境为空或注释时，服务器也保持为空或注释。

### 4. 初始化 Python 环境

```bash
cd /www/wwwroot/digital-course/services/api
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e "."
mkdir -p data
python -m alembic upgrade head
```

全新部署时，从仓库根目录初始化预置课程内容：

```bash
cd /www/wwwroot/digital-course
services/api/.venv/bin/python scripts/initialize_content_db.py --prune-extra-chapters
```

迁移已有数据库时，先把本地 `teach.db` 上传到服务器，再只执行迁移：

```bash
scp services/api/data/teach.db user@your-server:/www/wwwroot/digital-course/services/api/data/teach.db

cd /www/wwwroot/digital-course/services/api
.venv/bin/python -m alembic upgrade head
```

迁移已有数据时保留原 `.env` 中的 `STUDENT_PASSWORD_KEY` 状态。

### 5. 构建并上传学生端

可以在本机或 CI 构建学生端：

```bash
cd apps/student-desktop
pnpm install
pnpm build
```

上传构建产物到服务器：

```bash
rsync -avz --delete apps/student-desktop/dist/ \
  user@your-server:/www/wwwroot/digital-course/student-dist/
```

服务器目录应为 `/www/wwwroot/digital-course/student-dist/`。

### 6. 配置 systemd

复制服务文件：

```bash
cp /www/wwwroot/digital-course/deploy/systemd/digital-course-api.service \
  /etc/systemd/system/digital-course-api.service
```

检查服务文件中的路径：

```bash
grep -E "WorkingDirectory|EnvironmentFile|ExecStart" \
  /etc/systemd/system/digital-course-api.service
```

期望路径指向：

- `/www/wwwroot/digital-course/services/api`
- `/www/wwwroot/digital-course/services/api/.env`
- `/www/wwwroot/digital-course/services/api/.venv/bin/python`

启用并启动：

```bash
systemctl daemon-reload
systemctl enable --now digital-course-api
systemctl status digital-course-api
```

本机回环健康检查：

```bash
curl -sS http://127.0.0.1:8000/health
```

查看日志：

```bash
journalctl -u digital-course-api -f
```

### 7. 配置 Nginx + HTTPS

示例配置位于 `deploy/nginx/digital-course.conf`。复制到 Nginx 配置目录：

```bash
cp /www/wwwroot/digital-course/deploy/nginx/digital-course.conf \
  /etc/nginx/sites-available/digital-course.conf

ln -s /etc/nginx/sites-available/digital-course.conf \
  /etc/nginx/sites-enabled/digital-course.conf
```

编辑配置：

```bash
nano /etc/nginx/sites-available/digital-course.conf
```

需要替换：

- `server_name`：替换为你的域名。
- `ssl_certificate`：替换为你的证书 `fullchain.pem` 路径。
- `ssl_certificate_key`：替换为你的证书 `privkey.pem` 路径。
- `alias /www/wwwroot/digital-course/student-dist/;`：确认与实际学生端构建产物目录一致。
- `proxy_pass http://127.0.0.1:8000;`：确认与 systemd API 监听地址一致。

检查并重载：

```bash
nginx -t
systemctl reload nginx
```

浏览器访问：

- 学生端：`https://your-domain.com/student/`
- 教师端：`https://your-domain.com/teacher/login`
- 健康检查：`https://your-domain.com/health`
- API：`https://your-domain.com/v1/...`

示例 Nginx 配置当前代理了 `/teacher`、`/v1`、`/health`、`/static`、`/favicon.ico`。如需在生产访问在线 API 调试页面（FastAPI 默认 `/docs` 和 `/openapi.json`），请额外添加对应 `location` 并评估访问控制策略。

## 四、接入大语言模型

后端使用 OpenAI 兼容 Chat Completions。真实 API Key 只写入 `services/api/.env`，也可通过教师端「大模型接入」页面维护运行时配置。

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
OPENROUTER_HTTP_REFERER=https://your-domain.com
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

`CHAT_LLM_BASE_URL` / `CHAT_LLM_API_KEY` 可单独配置学生 AI 助手；未设置时回退到 `LLM_BASE_URL` / `LLM_API_KEY`。多数 OpenAI 兼容厂商的 `LLM_BASE_URL` 写到服务根地址即可，通常省略尾部 `/v1`，代码会拼接 Chat Completions 路径。

## 五、备份与恢复

运行时数据主要保存在 `services/api/data/teach.db`。生产服务器示例路径：

```text
/www/wwwroot/digital-course/services/api/data/teach.db
```

### 1. 备份

```bash
mkdir -p /www/backup/digital-course

cp /www/wwwroot/digital-course/services/api/data/teach.db \
  /www/backup/digital-course/teach-$(date +%Y%m%d-%H%M%S).db
```

建议同时备份：

- `services/api/.env`
- `services/api/data/teach.db`
- 当前代码版本或 Git commit
- 当前 `student-dist/` 目录

`.env` 含有密钥，应放在受控位置，避免发送到公开聊天、公开网盘或仓库。

### 2. 恢复

```bash
systemctl stop digital-course-api

cp /www/backup/digital-course/teach-<时间戳>.db \
  /www/wwwroot/digital-course/services/api/data/teach.db

cd /www/wwwroot/digital-course/services/api
.venv/bin/python -m alembic upgrade head

systemctl start digital-course-api
systemctl status digital-course-api
curl -sS http://127.0.0.1:8000/health
```

恢复学生端静态文件：

```bash
rm -rf /www/wwwroot/digital-course/student-dist
cp -r /www/backup/digital-course/student-dist-<时间戳> \
  /www/wwwroot/digital-course/student-dist
systemctl reload nginx
```

## 六、测试与检查

后端：

```bash
cd services/api
source .venv/bin/activate
pytest -q
ruff check app tests
```

学生端：

```bash
cd apps/student-desktop
pnpm typecheck
pnpm build
```

部署后检查：

```bash
curl -sS http://127.0.0.1:8000/health
systemctl status digital-course-api
journalctl -u digital-course-api -n 100 --no-pager
nginx -t
curl -I https://your-domain.com/health
curl -I https://your-domain.com/student/
```

浏览器检查：

- `https://your-domain.com/student/` 能打开学生端。
- `https://your-domain.com/teacher/login` 能打开教师端。
- 教师端可完成首次管理员设置。
- 学生可用教师端名单中的学号和姓名注册。
- 课堂练习页可加载 Pyodide 并执行代码。
- AI 学习助手在配置 LLM 后可返回真实模型响应。

## 七、常见问题

### 1. 学生端访问 API 失败

本地开发时先检查 API：

```bash
curl http://127.0.0.1:8000/health
```

学生端 Vite 开发服务默认代理 `/v1` 到 `http://127.0.0.1:8000`。生产环境请确认 Nginx 代理包含 `/v1` 和 `/health`，并且 systemd 服务正在监听 `127.0.0.1:8000`。

### 2. 首次运行学生端很慢

学生端需要准备 Pyodide 0.27.0 和课程依赖包。首次 `pnpm dev` 或 `pnpm build` 会下载并同步静态资源，网络慢时耗时较长。

### 3. 迁移数据库后学生无法登录

检查服务器 `.env` 中的 `STUDENT_PASSWORD_KEY`。迁移已有 SQLite 数据库时，该值必须与原环境保持一致。原环境为空或注释时，服务器也保持为空或注释。

### 4. 生产环境 Cookie 登录异常

HTTPS 部署时建议设置：

```env
ADMIN_COOKIE_SECURE=true
```

同时确认浏览器访问的是 HTTPS 域名，Nginx 已传递：

```nginx
proxy_set_header X-Forwarded-Proto https;
```

### 5. 生产环境需要在线 API 调试页面

当前示例 Nginx 配置代理了教学平台的核心入口。需要生产访问在线 API 调试页面时，在 Nginx 中增加 `/docs` 和 `/openapi.json` 对应 `location`，并设置访问控制策略。
