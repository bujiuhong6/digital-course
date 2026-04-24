# 学生端桌面（Tauri + React + Vite）

与教学 API 对接：**注册**（须与教师导入名单学号+姓名一致）→ **登录** → 已发布章列表 → 章练习（Pyodide + cell 上报）。

## 前置

- `pnpm` 8+（或项目使用的包管理器）
- **Rust**（Tauri 2；建议 **stable 1.8x+**）
- 平台依赖见 [Tauri Linux prerequisites](https://tauri.app/start/prerequisites/)（本机构建时已安装 `libwebkit2gtk-4.1-dev`、`libgtk-3-dev` 等）

## 配置

复制 `.env.example` 为 `.env`。

- `VITE_API_BASE_URL`：已运行的教学 API 根（无尾部斜杠），同机一般为 `http://127.0.0.1:8000`。
- `VITE_PYODIDE_INDEX_URL`（**可选**）：Pyodide `full/` 包目录的 URL，须以 `/` 结尾。默认与 `index.html` 中加载的 0.27 版本一致；**离线/内网**时可自建镜像并只改本变量与 `index.html` 中的 `pyodide.js` 地址。

**任务 12**：在 WebView 中加载 **Pyodide**（`index.html` 从 CDN 引入；首次运行会拉取包体）。进入已发布章后，按 `publishedContent.version===1` 的 `blocks` 以 **Notebook 式**（`In [n]:`、灰底代码区，与 design §2/§5 一致）展示**知识/引导/扩展**；样式在 `public/jupyter-cells.css`，与 `services/api/app/static/jupyter-cells.css` **内容应保持一致**（改一处请同步复制）。「执行」运行代码并上报 `POST /v1/student/cells/verify`；全部通过后可「提交本章练习」完成本章。

**学习助手（Chat）**：章练习页左下角有 **Chat** 按钮，展开后调 `POST /v1/student/chat`，会把当前聚焦代码格的 `cellId` 与代码作为 `currentCode` 发给服务端（与 API 限流/鉴权一致）。未配 LLM 时返回 `mock: true` 的占位说明。

## 开发

在仓库根启动 API 后（`services/api` 内 `uvicorn app.main:app --reload` 等）：

```bash
cd apps/student-desktop
pnpm install
pnpm tauri dev
```

Vite 默认端口 **1420**；`services/api/app/main.py` 已允许该来源跨域。若你改了 Vite 端口，在 API 的 CORS 里加上对应 `http` 源。

## 生产构建

```bash
cd apps/student-desktop
pnpm tauri build
```

产物在 `src-tauri/target/release/bundle/`（因平台不同而异）。`src-tauri/target` 不提交，由本机构建生成。

## 你无需额外提供的资料

MVP 流程使用已有学生账号（名单导入后注册、教师端发布的章）。只需本机/服务器上 API 可访问，并在 `.env` 中设好 `VITE_API_BASE_URL`。
