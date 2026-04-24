import { useCallback, useEffect, useState } from "react";
import { API_BASE, apiJson, clearToken, getToken, setToken } from "./api";
import { ChapterPractice } from "./ChapterPractice";
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

  return (
    <main className={`sd-root${screen === "chapter" ? " sd-wide" : ""}`}>
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
        <section className="sd-card sd-chapter-wrap">
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
          {selected.publishedContent ? (
            <ChapterPractice
              chapterId={selected.id}
              title={selected.title}
              publishedContent={selected.publishedContent}
            />
          ) : (
            <>
              <h2>{selected.title}</h2>
              <p className="sd-muted">本章暂无 publishedContent。</p>
            </>
          )}
        </section>
      )}
    </main>
  );
}

export default App;
