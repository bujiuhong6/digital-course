# 学生端 Web SPA（React + Vite）

学生端现在以 Web SPA 为生产形态，部署在同域路径 `/student/`。目录名仍叫 `student-desktop`，`src-tauri/` 保留为历史桌面端实验源码。

主流程：注册（须与教师导入名单学号 + 姓名一致）→ 登录 → `AI智能预习` / `AI课堂练习` / `AI课后作业` → Pyodide 代码执行、AI 助手或课后作业提交。

## 前置

- `pnpm` 8+（或项目使用的包管理器）
- 本地需先启动后端 API：`http://127.0.0.1:8000`
- 只有运行 Tauri 实验入口时才需要 Rust 和 Tauri 平台依赖

## 配置

复制 `.env.example` 为 `.env`。

- 本地开发默认在 Vite 开发服务里走代理：`/v1` → `http://127.0.0.1:8000`。
- 生产构建使用 `.env.production` 中的 `VITE_API_BASE_URL=`，让请求走同域相对路径 `/v1/...`，由 Nginx 反代到 FastAPI。
- `VITE_API_BASE_URL`：未走代理时使用的 API 根（无尾斜杠）。
- `VITE_PYODIDE_INDEX_URL`（**可选**）：Pyodide `full/` 包目录的 URL，须以 `/` 结尾。默认读取随学生端一起发布的 `/student/pyodide/v0.27.0/full/`。
- `VITE_PYODIDE_SCRIPT_URL`（**可选**）：`pyodide.js` 完整 URL。默认读取本地静态资源 `/student/pyodide/v0.27.0/full/pyodide.js`。

### Pyodide 与运行环境

- **首包体与首跑**：`pnpm dev` / `pnpm build` 会先运行 `pnpm prepare:pyodide`，把 Pyodide 0.27.0 核心文件和课程所需 wheel 同步到 `public/pyodide/v0.27.0/full/`。`ensurePyodide()` 首次执行代码时加载这些本地静态资源，并 `loadPackage` 预装 **micropip、numpy、pandas、matplotlib、matplotlib-pyodide、Jinja2**；再用 `micropip` 安装 **openpyxl**。总下载与解压体积较大，首次执行需要等待。
- **懒载（未实现）**：当前为「首次运行即全量装包」。若需缩短**进入页面**到**可点执行**的间隔，可后续将 `loadPackage` / `micropip.install` 迁到**首次点「执行」**之前的一步（思路：懒触发 `ensurePyodide` 或拆分轻量/重量包），届时在此 README 补充开关说明。
- **作图在页面内**：学生代码使用 `matplotlib` 时，请在作图后调用 `plt.show()`，图形会出现在章练习的 **「图形输出」** 区；`stdout`/`stderr` 仍走原有判题与展示逻辑。

Web 端通过本地静态资源加载 Pyodide。进入已发布章后，按 `publishedContent.version===1` 的 `blocks` 以 Notebook 式样展示知识、引导和扩展；样式在 `public/jupyter-cells.css`，与 `services/api/app/static/jupyter-cells.css` 内容应保持一致。「执行」运行代码并上报 `POST /v1/student/cells/verify`；全部通过后可「提交本章练习」完成本章。

**AI学习助手（Chat）**：章练习页左下角有 Chat 按钮，展开后调 `POST /v1/student/chat`，会把当前聚焦代码格的 `cellId` 与代码作为 `currentCode` 发给服务端（与 API 限流/鉴权一致）。未配 LLM 时返回 `mock: true` 的占位说明。

**保存草稿**：章底部「保存」将各格当前代码写入浏览器 localStorage（按 `学生 id + 章 id` 隔离）；切章或清浏览器站点数据会丢失。「提交本章练习」成功时清除该章草稿。列表「练习中」在服务端有通过记录，或本机有非空草稿时显示。


## 开发

在仓库根启动 API 后：

```bash
cd apps/student-desktop
pnpm install
pnpm dev
```

Vite 默认端口是 `1420`，访问 `http://127.0.0.1:1420/`。若出现 `ERR_CONNECTION_REFUSED`，先确认 `pnpm dev` 是否仍在运行。

## 生产构建

```bash
cd apps/student-desktop
pnpm build
```

生产构建产物在 `dist/`。`vite.config.ts` 会在 build 时把资源路径改为 `/student/`，线上由 Nginx 从 `/www/wwwroot/digital-course/student-dist/` 提供静态文件。

## Tauri 实验入口

桌面端源码保留在 `src-tauri/`。当前生产部署走 Web SPA，桌面包只用于本机实验：

```bash
cd apps/student-desktop
pnpm tauri dev
```

Tauri 构建产物在 `src-tauri/target/`，不提交。

## 你无需额外提供的资料

当前流程使用已有学生账号（名单导入后注册、教师端发布内容）。本地测试只需 API 可访问；生产构建默认走同域 `/v1/...`。
