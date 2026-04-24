/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  /** Pyodide `full/` 包目录 URL，须以 / 结尾，例如自建 CDN */
  readonly VITE_PYODIDE_INDEX_URL?: string;
  /** 可选：pyodide.js 的 URL（与 index 里 script 同版本）；国内网络可自托管 */
  readonly VITE_PYODIDE_SCRIPT_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
