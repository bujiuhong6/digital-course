/**
 * 浏览器中加载 Pyodide（全局 `loadPyodide`）并执行用户代码，捕获 stdout/stderr。
 * 若 index 里脚本因网络/顺序未加载，会动态插入同一 CDN 脚本并重试（任务 12）。
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

/* jsdelivr 上主包根目录的 pyodide.js 为 404；须用 full/ 下入口脚本 */
const defaultScript =
  "https://cdn.jsdelivr.net/pyodide/v0.27.0/full/pyodide.js";
function scriptUrl(): string {
  const u = import.meta.env.VITE_PYODIDE_SCRIPT_URL;
  if (u && String(u).trim()) {
    return String(u).trim();
  }
  return defaultScript;
}

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

function getLoadPyodideFromWindow() {
  return (window as unknown as { loadPyodide?: (o?: { indexURL: string }) => Promise<PyodideLike> })
    .loadPyodide;
}

async function waitFor(
  test: () => boolean,
  timeoutMs: number,
  stepMs: number,
): Promise<boolean> {
  const t0 = performance.now();
  while (performance.now() - t0 < timeoutMs) {
    if (test()) {
      return true;
    }
    await new Promise((r) => setTimeout(r, stepMs));
  }
  return test();
}

function injectPyodideScriptTag(): Promise<void> {
  return new Promise((resolve, reject) => {
    if (document.querySelector('script[data-app-pyodide="1"]')) {
      resolve();
      return;
    }
    const s = document.createElement("script");
    s.src = scriptUrl();
    s.async = true;
    s.setAttribute("data-app-pyodide", "1");
    s.onload = () => resolve();
    s.onerror = () => {
      reject(
        new Error(
          "无法从网络加载 pyodide.js。请检查网络/防火墙，或把 Pyodide 包放到可访问的 URL 后配置环境变量。",
        ),
      );
    };
    document.head.appendChild(s);
  });
}

/**
 * 等待全局 loadPyodide 出现：先等 index 里脚本，超时则动态插入并重试（首下可能较慢）。
 */
async function waitForLoadPyodideFunction(): Promise<
  (o?: { indexURL: string }) => Promise<PyodideLike>
> {
  const quick = 5000;
  const long = 120000;
  if (
    await waitFor(
      () => typeof getLoadPyodideFromWindow() === "function",
      quick,
      100,
    )
  ) {
    return getLoadPyodideFromWindow()!;
  }
  if (!document.querySelector('script[src*="pyodide"]')) {
    await injectPyodideScriptTag();
  }
  if (
    await waitFor(
      () => typeof getLoadPyodideFromWindow() === "function",
      long,
      200,
    )
  ) {
    return getLoadPyodideFromWindow()!;
  }
  throw new Error(
    "未找到 window.loadPyodide。请确认能访问 cdn.jsdelivr.net，或将 pyodide.js 自托管到 https 可访问处并在页面中引入。",
  );
}

export async function ensurePyodide(): Promise<PyodideLike> {
  if (instance) {
    return instance;
  }
  if (!loadPromise) {
    loadPromise = (async () => {
      const loadPyodide = await waitForLoadPyodideFunction();
      return loadPyodide({ indexURL: indexUrl() });
    })();
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
