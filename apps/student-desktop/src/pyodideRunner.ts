/**
 * 浏览器中加载本地自托管 Pyodide 并执行用户代码，捕获 stdout/stderr。
 */
export type PyodideLike = {
  setStdout: (opts: { batched: (s: string) => void }) => void;
  setStderr: (opts: { batched: (s: string) => void }) => void;
  runPythonAsync: (code: string) => Promise<unknown>;
};

/** `loadPyodide` 完整返回值（含 `loadPackage`） */
export type PyodideWithPackages = PyodideLike & {
  loadPackage: (names: string | string[]) => Promise<unknown>;
};

declare global {
  interface Document {
    /** matplotlib_pyodide 作图时挂载的父节点（见 browser_backend._create_root_element） */
    pyodideMplTarget?: HTMLElement;
    /** 部分 matplotlib-pyodide 版本/后端读取的挂载名。 */
    pyodideMatplotlibPlotTarget?: HTMLElement;
  }
}

export type RunResult = {
  stdout: string;
  stderr: string;
  runOk: boolean;
  errorExcerpt: string | null;
  /** 完整异常信息，供学生端「运行结果」区展示（不截断） */
  fullError: string | null;
  elapsedMs: number;
};

const bundledPyodideBase = `${import.meta.env.BASE_URL}pyodide/v0.27.0/full/`;
const defaultScript = `${bundledPyodideBase}pyodide.js`;
function scriptUrl(): string {
  const u = import.meta.env.VITE_PYODIDE_SCRIPT_URL;
  if (u && String(u).trim()) {
    return String(u).trim();
  }
  return defaultScript;
}

const defaultIndex = bundledPyodideBase;

let instance: PyodideWithPackages | null = null;
let loadPromise: Promise<PyodideWithPackages> | null = null;
let packagesReady = false;

function indexUrl(): string {
  const u = import.meta.env.VITE_PYODIDE_INDEX_URL;
  if (u && String(u).trim()) {
    return String(u).replace(/\/?$/, "/");
  }
  return defaultIndex;
}

function getLoadPyodideFromWindow() {
  return (window as unknown as {
    loadPyodide?: (o?: { indexURL: string }) => Promise<PyodideWithPackages>;
  }).loadPyodide;
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
          "无法加载 pyodide.js。请确认学生端静态资源已完整构建并部署。",
        ),
      );
    };
    document.head.appendChild(s);
  });
}

/**
 * 等待全局 loadPyodide 出现；页面未预置脚本时动态插入本地 pyodide.js。
 */
async function waitForLoadPyodideFunction(): Promise<
  (o?: { indexURL: string }) => Promise<PyodideWithPackages>
> {
  const quick = 5000;
  const long = 120000;
  if (
    typeof getLoadPyodideFromWindow() !== "function" &&
    !document.querySelector('script[src*="pyodide"]')
  ) {
    await injectPyodideScriptTag();
  }
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
    "未找到 window.loadPyodide。请确认学生端 Pyodide 静态资源已完整构建并部署。",
  );
}

const BUILTIN_PACKAGES = [
  "micropip",
  "numpy",
  "pandas",
  "matplotlib",
  "matplotlib-pyodide",
  "wordcloud",
  "Jinja2",
] as const;

async function ensureBuiltinPackages(py: PyodideWithPackages): Promise<void> {
  if (packagesReady) {
    return;
  }
  await py.loadPackage([...BUILTIN_PACKAGES]);
  await py.runPythonAsync(`
import micropip
try:
    await micropip.install("openpyxl", keep_going=True)
except Exception:
    # openpyxl is only needed for Excel files. Keep Python exercises available
    # when PyPI/network access is blocked in the browser.
    pass
`);
  await py.runPythonAsync(`
import matplotlib
matplotlib.use("module://matplotlib_pyodide.wasm_backend")
`);
  packagesReady = true;
}

/** 运行前关闭 matplotlib 图形（忽略未导入时错误） */
const CLOSE_MPL = `
try:
    import matplotlib.pyplot as _plt
    _plt.close("all")
except Exception:
    pass
`;

export async function ensurePyodide(): Promise<PyodideWithPackages> {
  if (instance) {
    return instance;
  }
  if (!loadPromise) {
    loadPromise = (async () => {
      const loadPyodide = await waitForLoadPyodideFunction();
      const raw = (await loadPyodide({ indexURL: indexUrl() })) as PyodideWithPackages;
      if (typeof raw.loadPackage !== "function") {
        throw new Error("Pyodide 实例缺少 loadPackage，请检查 pyodide 版本与 indexURL。");
      }
      await ensureBuiltinPackages(raw);
      return raw;
    })();
  }
  instance = await loadPromise;
  return instance;
}

export type RunPythonOptions = {
  /** 图形挂载父节点；未提供时 `matplotlib_pyodide` 回退到 `document.body` 作为根 */
  mplMount?: HTMLElement | null;
};

/**
 * 学生代码执行：预装 numpy / pandas / matplotlib（含 matplotlib-pyodide）/ wordcloud / Jinja2、micropip 装 openpyxl；
 * 若提供 `mplMount`，图形显示在该节点内；运行前会 `plt.close('all')` 并清空 `mplMount` 子节点。
 */
export async function runPythonInPyodide(
  code: string,
  options?: RunPythonOptions,
): Promise<RunResult> {
  const py = await ensurePyodide();
  if (options?.mplMount) {
    options.mplMount.replaceChildren();
    document.pyodideMplTarget = options.mplMount;
    document.pyodideMatplotlibPlotTarget = options.mplMount;
  } else {
    delete document.pyodideMplTarget;
    delete document.pyodideMatplotlibPlotTarget;
  }
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
    await py.runPythonAsync(CLOSE_MPL);
    await py.runPythonAsync(code);
    const elapsedMs = Math.max(0, Math.round(performance.now() - t0));
    return {
      stdout,
      stderr,
      runOk: true,
      errorExcerpt: null,
      fullError: null,
      elapsedMs,
    };
  } catch (e) {
    const elapsedMs = Math.max(0, Math.round(performance.now() - t0));
    const msg = e instanceof Error ? e.message : String(e);
    return {
      stdout,
      stderr,
      runOk: false,
      errorExcerpt: msg.length > 500 ? msg.slice(0, 500) : msg,
      fullError: msg,
      elapsedMs,
    };
  }
}
