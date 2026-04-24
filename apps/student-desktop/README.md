# 学生端桌面（Tauri + React + Vite）

与教学 API 对接：登录 → 已发布章列表 → 章练习占位（`iframe` + `srcDoc`）。任务 12 将在练习区接入 Pyodide 与各 cell 上报。

## 前置

- `pnpm` 8+（或项目使用的包管理器）
- **Rust**（Tauri 2；建议 **stable 1.8x+**）
- 平台依赖见 [Tauri Linux prerequisites](https://tauri.app/start/prerequisites/)（本机构建时已安装 `libwebkit2gtk-4.1-dev`、`libgtk-3-dev` 等）

## 配置 API 根地址

复制 `.env.example` 为 `.env`，修改 `VITE_API_BASE_URL` 指向已运行的 API（无尾部斜杠）。开发时同机一般为 `http://127.0.0.1:8000`。

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
