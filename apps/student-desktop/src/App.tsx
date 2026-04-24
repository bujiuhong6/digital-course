import { useCallback, useEffect, useState } from "react";
import { apiJson, clearToken, getToken, setToken } from "./api";
import { ChapterPractice } from "./ChapterPractice";
import { hasMeaningfulCodeDraft } from "./chapterDraftStorage";
import "./App.css";

type Screen = "auth" | "chapters" | "chapter";

type PracticeStatus = "pending" | "inProgress" | "submitted";

type ChapterListItem = {
  chapterId: string;
  slug: string;
  title: string;
  order: number;
  updatedAt: string | null;
  practiceStatus: PracticeStatus;
};

function practiceStatusLabel(s: PracticeStatus): string {
  if (s === "submitted") {
    return "已提交";
  }
  if (s === "inProgress") {
    return "练习中";
  }
  return "待完成";
}

function mergePracticeStatusForList(
  server: PracticeStatus,
  chapterId: string,
  studentId: string | null,
): PracticeStatus {
  if (server === "submitted" || !studentId) {
    return server;
  }
  if (server === "inProgress") {
    return "inProgress";
  }
  if (hasMeaningfulCodeDraft(studentId, chapterId)) {
    return "inProgress";
  }
  return "pending";
}

type ChapterBody = {
  id: string;
  slug: string;
  title: string;
  order: number;
  contentStatus: string;
  publishedContent: Record<string, unknown> | null;
  updatedAt: string | null;
  /** 服务端是否已记录本章完成 */
  hasCompletedChapter?: boolean;
};

function App() {
  const [screen, setScreen] = useState<Screen>("auth");
  const [authTab, setAuthTab] = useState<"login" | "register">("login");
  const [err, setErr] = useState<string | null>(null);
  const [okHint, setOkHint] = useState<string | null>(null);
  const [studentNo, setStudentNo] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [password2, setPassword2] = useState("");
  const [chapters, setChapters] = useState<ChapterListItem[]>([]);
  const [selected, setSelected] = useState<ChapterBody | null>(null);
  const [loading, setLoading] = useState(false);
  const [currentStudentId, setCurrentStudentId] = useState<string | null>(null);

  const goChapters = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const me = await apiJson<{
        student: { studentId: string; studentNo: string; fullName: string };
      }>("/v1/student/me");
      setCurrentStudentId(me.student.studentId);
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
      goChapters().catch(() => setScreen("auth"));
    }
  }, [goChapters]);

  async function onLogin(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setErr(null);
    setOkHint(null);
    try {
      const data = await apiJson<{
        accessToken: string;
        student: {
          studentId: string;
          studentNo: string;
          fullName: string;
        };
      }>("/v1/student/login", {
        method: "POST",
        body: JSON.stringify({ studentNo, password }),
      });
      setToken(data.accessToken);
      setCurrentStudentId(data.student.studentId);
      await goChapters();
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  }

  async function onRegister(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setErr(null);
    setOkHint(null);
    if (password !== password2) {
      setErr("两次输入的密码不一致。");
      setLoading(false);
      return;
    }
    try {
      const reg = await apiJson<{ ok: boolean; studentId: string }>(
        "/v1/student/register",
        {
          method: "POST",
          body: JSON.stringify({
            studentNo,
            fullName,
            password,
          }),
        },
        { noAuth: true },
      );
      setCurrentStudentId(reg.studentId);
      setPassword("");
      setPassword2("");
      setOkHint("注册成功。请用刚才的学号与密码登录。");
      setAuthTab("login");
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  }

  function onLogout() {
    clearToken();
    setCurrentStudentId(null);
    setChapters([]);
    setSelected(null);
    setScreen("auth");
    setAuthTab("login");
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
        <h1>章节练习（学生用）</h1>
        {getToken() && (
          <button type="button" className="sd-btn-ghost" onClick={onLogout}>
            退出
          </button>
        )}
      </header>

      {okHint && <div className="sd-okhint">{okHint}</div>}
      {err && <div className="sd-error">{err}</div>}

      {screen === "auth" && (
        <div className="sd-card sd-auth">
          <div className="sd-tabs">
            <button
              type="button"
              className={authTab === "login" ? "sd-tab on" : "sd-tab"}
              onClick={() => {
                setAuthTab("login");
                setErr(null);
                setOkHint(null);
              }}
            >
              登录
            </button>
            <button
              type="button"
              className={authTab === "register" ? "sd-tab on" : "sd-tab"}
              onClick={() => {
                setAuthTab("register");
                setErr(null);
                setOkHint(null);
              }}
            >
              注册
            </button>
          </div>
          {authTab === "login" ? (
            <form onSubmit={onLogin}>
              <h2>登录</h2>
              <p className="sd-muted sm">
                学号、姓名需已由教师在名单导入，且与注册时一致。
              </p>
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
          ) : (
            <form onSubmit={onRegister}>
              <h2>注册</h2>
              <p className="sd-muted sm">
                学号、姓名须与教师导入名单一字不差（含空格）。注册成功后切到「登录」。
              </p>
              <label>
                学号
                <input
                  value={studentNo}
                  onChange={(e) => setStudentNo(e.target.value)}
                  autoComplete="username"
                />
              </label>
              <label>
                姓名
                <input
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  autoComplete="name"
                />
              </label>
              <label>
                设置密码
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="new-password"
                />
              </label>
              <label>
                确认密码
                <input
                  type="password"
                  value={password2}
                  onChange={(e) => setPassword2(e.target.value)}
                  autoComplete="new-password"
                />
              </label>
              <button type="submit" disabled={loading}>
                {loading ? "…" : "注册"}
              </button>
            </form>
          )}
        </div>
      )}

      {screen === "chapters" && (
        <section className="sd-card">
          <h2>章节练习列表</h2>
          {chapters.length === 0 ? (
            <p>暂无。请教师端发布章后再试。</p>
          ) : (
            <ul className="sd-list">
              {chapters.map((c) => (
                <li key={c.chapterId} className="sd-list-row">
                  <div className="sd-list-main">
                    <button
                      type="button"
                      className="sd-link"
                      onClick={() => void openChapter(c.chapterId)}
                    >
                      {c.title}
                    </button>
                    <span className="sd-muted"> {c.slug}</span>
                  </div>
                  <span
                    className="sd-list-status"
                    title="本章练习进度"
                    aria-label={`本章练习状态：${practiceStatusLabel(
                      mergePracticeStatusForList(
                        c.practiceStatus,
                        c.chapterId,
                        currentStudentId,
                      ),
                    )}`}
                  >
                    {practiceStatusLabel(
                      mergePracticeStatusForList(
                        c.practiceStatus,
                        c.chapterId,
                        currentStudentId,
                      ),
                    )}
                  </span>
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
              void goChapters();
            }}
          >
            ← 返回列表
          </button>
          {selected.publishedContent && currentStudentId ? (
            <ChapterPractice
              studentId={currentStudentId}
              chapterId={selected.id}
              title={selected.title}
              publishedContent={selected.publishedContent}
              initialChapterCompleted={!!selected.hasCompletedChapter}
            />
          ) : selected.publishedContent ? (
            <p className="sd-muted">正在加载学生信息…</p>
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
