/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  /** Pyodide `full/` 包目录 URL，须以 / 结尾，例如自建 CDN */
  readonly VITE_PYODIDE_INDEX_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
