/**
 * 浏览器中加载 Pyodide（由 index.html 注入的全局 `loadPyodide`）并执行用户代码，
 * 捕获 stdout/stderr；异常时 `runOk` 为 false。任务 12。
 */
export type PyodideLike = {
  setStdout: (opts: { batched: (s: string) => void }) => void;
  setStderr: (opts: { batched: (s: string) => void }) => void;
  runPythonAsync: (code: string) => Promise<unknown>;
};

export type RunResult = {
  stdout: string;
  stderr: string;
  runOk: boolean;
  errorExcerpt: string | null;
  elapsedMs: number;
};

const defaultIndex = "https://cdn.jsdelivr.net/pyodide/v0.27.0/full/";

let instance: PyodideLike | null = null;
let loadPromise: Promise<PyodideLike> | null = null;

function indexUrl(): string {
  const u = import.meta.env.VITE_PYODIDE_INDEX_URL;
  if (u && String(u).trim()) {
    return String(u).replace(/\/?$/, "/");
  }
  return defaultIndex;
}

export async function ensurePyodide(): Promise<PyodideLike> {
  if (instance) {
    return instance;
  }
  if (!loadPromise) {
    const loadPyodide = (window as unknown as { loadPyodide?: (o?: { indexURL: string }) => Promise<PyodideLike> })
      .loadPyodide;
    if (typeof loadPyodide !== "function") {
      throw new Error("Pyodide 未就绪：请确认 index.html 已引入 pyodide.js。");
    }
    loadPromise = loadPyodide({ indexURL: indexUrl() });
  }
  instance = await loadPromise;
  return instance;
}

export async function runPythonInPyodide(code: string): Promise<RunResult> {
  const py = await ensurePyodide();
  let stdout = "";
  let stderr = "";
  py.setStdout({ batched: (s: string) => {
    stdout += s;
  } });
  py.setStderr({ batched: (s: string) => {
    stderr += s;
  } });
  const t0 = performance.now();
  try {
    await py.runPythonAsync(code);
    const elapsedMs = Math.max(0, Math.round(performance.now() - t0));
    return { stdout, stderr, runOk: true, errorExcerpt: null, elapsedMs };
  } catch (e) {
    const elapsedMs = Math.max(0, Math.round(performance.now() - t0));
    const msg = e instanceof Error ? e.message : String(e);
    return {
      stdout,
      stderr,
      runOk: false,
      errorExcerpt: msg.length > 500 ? msg.slice(0, 500) : msg,
      elapsedMs,
    };
  }
}
