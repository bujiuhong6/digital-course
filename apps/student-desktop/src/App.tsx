import { useCallback, useEffect, useState } from "react";
import { API_BASE, apiJson, clearToken, getToken, setToken } from "./api";
import "./App.css";

type Screen = "login" | "chapters" | "chapter";

type ChapterListItem = {
  chapterId: string;
  slug: string;
  title: string;
  order: number;
  updatedAt: string | null;
};

type ChapterBody = {
  id: string;
  slug: string;
  title: string;
  order: number;
  contentStatus: string;
  publishedContent: Record<string, unknown> | null;
  updatedAt: string | null;
};

function App() {
  const [screen, setScreen] = useState<Screen>("login");
  const [err, setErr] = useState<string | null>(null);
  const [studentNo, setStudentNo] = useState("");
  const [password, setPassword] = useState("");
  const [chapters, setChapters] = useState<ChapterListItem[]>([]);
  const [selected, setSelected] = useState<ChapterBody | null>(null);
  const [loading, setLoading] = useState(false);

  const goChapters = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const data = await apiJson<{ chapters: ChapterListItem[] }>("/v1/student/chapters");
      setChapters(data.chapters);
      setScreen("chapters");
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (getToken()) {
      goChapters().catch(() => setScreen("login"));
    }
  }, [goChapters]);

  async function onLogin(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setErr(null);
    try {
      const data = await apiJson<{
        accessToken: string;
        student: { studentNo: string; fullName: string };
      }>("/v1/student/login", {
        method: "POST",
        body: JSON.stringify({ studentNo, password }),
      });
      setToken(data.accessToken);
      await goChapters();
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  }

  function onLogout() {
    clearToken();
    setChapters([]);
    setSelected(null);
    setScreen("login");
  }

  async function openChapter(id: string) {
    setLoading(true);
    setErr(null);
    try {
      const data = await apiJson<{ chapter: ChapterBody }>(
        `/v1/student/chapters/${id}`,
      );
      setSelected(data.chapter);
      setScreen("chapter");
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  }

  const iframeSrcDoc =
    selected &&
    `<!DOCTYPE html><html lang="zh-Hans"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/></head>
<body style="margin:0;font-family:system-ui,sans-serif;padding:1rem;background:#0b1220;color:#e2e8f0">
<h2 style="margin:0 0 0.5rem">${selected.title.replace(/</g, "&lt;")}</h2>
<p style="color:#94a3b8;font-size:0.9rem">本章 <code>publishedContent</code> 已由 API 拉取。任务 12 将在此用 Pyodide 跑各 cell 并调用 <code>POST /v1/student/cells/verify</code>。</p>
</body></html>`;

  return (
    <main className="sd-root">
      <header className="sd-header">
        <h1>学生端（Tauri）</h1>
        <p className="sd-meta">
          API: <code>{API_BASE}</code>（<code>VITE_API_BASE_URL</code>）
        </p>
        {getToken() && (
          <button type="button" className="sd-btn-ghost" onClick={onLogout}>
            退出
          </button>
        )}
      </header>

      {err && <div className="sd-error">{err}</div>}

      {screen === "login" && (
        <form className="sd-card" onSubmit={onLogin}>
          <h2>登录</h2>
          <label>
            学号
            <input
              value={studentNo}
              onChange={(e) => setStudentNo(e.target.value)}
              autoComplete="username"
            />
          </label>
          <label>
            密码
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
            />
          </label>
          <button type="submit" disabled={loading}>
            {loading ? "…" : "进入"}
          </button>
        </form>
      )}

      {screen === "chapters" && (
        <section className="sd-card">
          <h2>已发布章</h2>
          {chapters.length === 0 ? (
            <p>暂无。请教师端发布章后再试。</p>
          ) : (
            <ul className="sd-list">
              {chapters.map((c) => (
                <li key={c.chapterId}>
                  <button
                    type="button"
                    className="sd-link"
                    onClick={() => void openChapter(c.chapterId)}
                  >
                    {c.title}
                  </button>
                  <span className="sd-muted"> {c.slug}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {screen === "chapter" && selected && (
        <section className="sd-card">
          <button
            type="button"
            className="sd-btn-ghost"
            onClick={() => {
              setSelected(null);
              setScreen("chapters");
            }}
          >
            ← 返回列表
          </button>
          <h2>{selected.title}</h2>
          <p className="sd-muted">状态: {selected.contentStatus}</p>
          <div className="sd-iframe-wrap">
            {iframeSrcDoc && (
              <iframe title="chapter-preview" srcDoc={iframeSrcDoc} />
            )}
          </div>
        </section>
      )}
    </main>
  );
}

export default App;
