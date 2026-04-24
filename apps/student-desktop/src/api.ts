/**
 * 学生 API 基址：构建时 `VITE_API_BASE_URL`（任务 11）。
 * 开发时默认走 **相对路径**（空基址），由 Vite 把 `/v1` 代理到本机 API，避免 Tauri WebView
 * 对 `http://127.0.0.1:8000` 直接请求出现 Load failed。设 `VITE_DEV_API_PROXY=0` 可改回直连。
 */
const raw = import.meta.env.VITE_API_BASE_URL as string | undefined;
const devProxyOff =
  import.meta.env.VITE_DEV_API_PROXY === "0" ||
  import.meta.env.VITE_DEV_API_PROXY === "false";
const viteProxyOn =
  import.meta.env.VITE_USE_VITE_PROXY === "1" ||
  import.meta.env.VITE_USE_VITE_PROXY === "true";
const useViteProxy =
  !devProxyOff && (import.meta.env.DEV || viteProxyOn);
export const API_BASE = useViteProxy
  ? ""
  : (raw && raw.replace(/\/$/, "")) || "http://127.0.0.1:8000";

const TOKEN_KEY = "student_access_token";

export function getToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  sessionStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  sessionStorage.removeItem(TOKEN_KEY);
}

export async function apiJson<T>(
  path: string,
  init: RequestInit = {},
  options: { noAuth?: boolean } = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  if (!headers.has("Content-Type") && init.body) {
    headers.set("Content-Type", "application/json");
  }
  if (!options.noAuth) {
    const t = getToken();
    if (t) {
      headers.set("Authorization", `Bearer ${t}`);
    }
  }
  const r = await fetch(`${API_BASE}${path}`, { ...init, headers });
  const text = await r.text();
  if (!r.ok) {
    let errMsg = text || `HTTP ${r.status}`;
    try {
      const parsed = JSON.parse(text) as { detail?: unknown };
      if (typeof parsed?.detail === "string") {
        errMsg = parsed.detail;
      } else if (parsed?.detail != null) {
        errMsg = JSON.stringify(parsed.detail);
      }
    } catch {
      /* 非 JSON，沿用原文 */
    }
    throw new Error(errMsg);
  }
  if (!text) {
    return {} as T;
  }
  return JSON.parse(text) as T;
}
