/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** 为 `0` 或 `false` 时，不启用同域相对路径 + Vite 代理，改为直连 `VITE_API_BASE_URL` */
  readonly VITE_DEV_API_PROXY?: string;
  /** 为 `1` 时，生产/ Preview 也使用空基址 + Vite preview 的 `proxy`（与 `vite preview` 同用） */
  readonly VITE_USE_VITE_PROXY?: string;
  readonly VITE_API_BASE_URL?: string;
  /** Pyodide `full/` 包目录 URL，须以 / 结尾，例如自建 CDN */
  readonly VITE_PYODIDE_INDEX_URL?: string;
  /** 可选：pyodide.js 的 URL（与 index 里 script 同版本）；国内网络可自托管 */
  readonly VITE_PYODIDE_SCRIPT_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
