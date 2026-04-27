# 学生端桌面（Tauri + React + Vite）

与教学 API 对接：**注册**（须与教师导入名单学号+姓名一致）→ **登录** → **已发布章节练习**（每行右侧显示**待完成** / **练习中** / **已提交**，由 `GET /v1/student/chapters` 的 `practiceStatus` 驱动）→ 章练习（Pyodide + cell 上报）。

## 前置

- `pnpm` 8+（或项目使用的包管理器）
- **Rust**（Tauri 2；建议 **stable 1.8x+**）
- 平台依赖见 [Tauri Linux prerequisites](https://tauri.app/start/prerequisites/)（本机构建时已安装 `libwebkit2gtk-4.1-dev`、`libgtk-3-dev` 等）

## 配置

复制 `.env.example` 为 `.env`。

- **Tauri 开发**（`pnpm tauri dev`）：默认在 **Vite 开发服务里走代理**（`vite.config.ts` 中 `/v1` → `http://127.0.0.1:8000`），前端用**相对路径**调接口，与 `http://localhost:1420` 同域，避免 WebView 直接请求 `http://127.0.0.1:8000` 时出现 **Load failed / Failed to fetch**。本机需先启动 API。若你确认直连无问题，可在 `.env` 设 `VITE_DEV_API_PROXY=0` 并配置 `VITE_API_BASE_URL=http://127.0.0.1:8000`。
- `VITE_API_BASE_URL`：打包/未走代理时使用的 API 根（无尾斜杠），同机一般为 `http://127.0.0.1:8000`。
- `VITE_PYODIDE_INDEX_URL`（**可选**）：Pyodide `full/` 包目录的 URL，须以 `/` 结尾。默认与 `index.html` 中加载的 0.27 版本一致；**离线/内网**时可自建镜像并只改本变量与 `index.html` 中的 `pyodide.js` 地址。
- `VITE_PYODIDE_SCRIPT_URL`（**可选**）：`pyodide.js` 完整 URL（见 `.env.example`），与上项版本应一致。仅在动态注入脚本时生效，与 `index.html` 中已写死脚本并存时，以**实际加载的入口**为准。

### Pyodide 与运行环境

- **首包体与首跑**：`ensurePyodide()` 在首次需要执行代码时加载 Pyodide 核心，并 `loadPackage` 预装 **micropip、numpy、pandas、matplotlib、matplotlib-pyodide、Jinja2**；再用 `micropip` 安装 **openpyxl**。总下载与解压体积较大、耗时以网络为准；建议按章节教学场景预留**首次进入练习后的等待**；内网/离线请配置上述镜像与 `https` 可访问的 `full/` 目录。
- **懒载（未实现）**：当前为「首次运行即全量装包」。若需缩短**进入页面**到**可点执行**的间隔，可后续将 `loadPackage` / `micropip.install` 迁到**首次点「执行」**之前的一步（思路：懒触发 `ensurePyodide` 或拆分轻量/重量包），届时在此 README 补充开关说明。
- **作图在页面内**：学生代码使用 `matplotlib` 时，请在作图后调用 `plt.show()`，图形会出现在章练习的 **「图形输出」** 区；`stdout`/`stderr` 仍走原有判题与展示逻辑。

**任务 12**：在 WebView 中加载 **Pyodide**（`index.html` 从 CDN 引入；首次运行会拉取包体）。进入已发布章后，按 `publishedContent.version===1` 的 `blocks` 以 **Notebook 式**（`In [n]:`、灰底代码区，与 design §2/§5 一致）展示**知识/引导/扩展**；样式在 `public/jupyter-cells.css`，与 `services/api/app/static/jupyter-cells.css` **内容应保持一致**（改一处请同步复制）。「执行」运行代码并上报 `POST /v1/student/cells/verify`；全部通过后可「提交本章练习」完成本章。

**AI学习助手（Chat）**：章练习页左下角有 **Chat** 按钮，展开后调 `POST /v1/student/chat`，会把当前聚焦代码格的 `cellId` 与代码作为 `currentCode` 发给服务端（与 API 限流/鉴权一致）。未配 LLM 时返回 `mock: true` 的占位说明。

**保存草稿**：章底部 **「保存」** 将各格当前代码写入本机 **localStorage**（按 `学生 id + 章 id` 隔离）；切章或清浏览器站点数据会丢失。**提交本章练习** 成功时清除该章草稿。列表「练习中」在服务端有通过记录，或本机有非空草稿时显示。


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
