/**
 * 学生 API 基址：构建时 `VITE_API_BASE_URL`（任务 11）。
 * 同机开发默认 `http://127.0.0.1:8000`；需与 FastAPI 的 CORS 允许来源一致（见 `services/api/app/main.py`）。
 */
const raw = import.meta.env.VITE_API_BASE_URL as string | undefined;
export const API_BASE = (raw && raw.replace(/\/$/, "")) || "http://127.0.0.1:8000";

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
    let detail: unknown = text;
    try {
      detail = JSON.parse(text);
    } catch {
      /* raw */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  if (!text) {
    return {} as T;
  }
  return JSON.parse(text) as T;
}
