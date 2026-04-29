import { useCallback, useEffect, useState } from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { BookOpen, ClipboardList, Lightbulb } from "lucide-react";
import { apiJson, clearToken, getToken, setToken } from "./api";
import { ChapterPractice } from "./ChapterPractice";
import { hasMeaningfulCodeDraft } from "./chapterDraftStorage";
import { PostExerciseDetail } from "./PostExerciseDetail";
import { PostExerciseList } from "./PostExerciseList";
import { PrestudyDetail } from "./PrestudyDetail";
import { PrestudyList } from "./PrestudyList";
import "./App.css";

type Screen =
  | "auth"
  | "chapters"
  | "chapter"
  | "prestudies"
  | "prestudy"
  | "postExercises"
  | "postExercise";

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

function practiceStatusTone(s: PracticeStatus): "default" | "secondary" | "outline" {
  if (s === "submitted") {
    return "default";
  }
  if (s === "inProgress") {
    return "secondary";
  }
  return "outline";
}

function practiceActionLabel(s: PracticeStatus): string {
  if (s === "submitted") {
    return "查看结果";
  }
  if (s === "inProgress") {
    return "继续练习";
  }
  return "去学习";
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
  /** 当前学生在库中 run_ok 为 true 的 cellId（与 complete 要求同源） */
  cellsPassed?: string[];
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
  const [selectedPrestudyId, setSelectedPrestudyId] = useState<string | null>(null);
  const [selectedPostExerciseId, setSelectedPostExerciseId] = useState<string | null>(null);
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
      if (String(e).toLowerCase().includes("unauthorized")) {
        clearToken();
        setCurrentStudentId(null);
      }
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
    setSelectedPrestudyId(null);
    setSelectedPostExerciseId(null);
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

  function switchAuthTab(next: "login" | "register") {
    setAuthTab(next);
    setErr(null);
    setOkHint(null);
  }

  function backToChapters() {
    setSelected(null);
    setScreen("chapters");
    void goChapters();
  }

  function openPrestudy(id: string) {
    setSelectedPrestudyId(id);
    setScreen("prestudy");
  }

  function backToPrestudies() {
    setSelectedPrestudyId(null);
    setScreen("prestudies");
  }

  function openPostExercise(id: string) {
    setSelectedPostExerciseId(id);
    setScreen("postExercise");
  }

  function backToPostExercises() {
    setSelectedPostExerciseId(null);
    setScreen("postExercises");
  }

  const rootClassName = [
    "sd-root",
    screen === "auth" ? "sd-auth-screen" : "",
    screen === "chapter" || screen === "prestudy" || screen === "postExercise" ? "sd-wide" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <main className={rootClassName}>
      <header className="sd-header">
        <div className="sd-header-top">
          <div className="sd-header-copy">
            <p className="sd-eyebrow">《数字技术与应用》课程</p>
            <h1>AI智能编程学习平台</h1>
          </div>
          {screen !== "auth" && getToken() && (
            <div className="sd-header-actions">
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="sd-header-logout"
                onClick={onLogout}
              >
                退出登录
              </Button>
            </div>
          )}
        </div>
        {screen !== "auth" && getToken() && (
          <nav className="sd-module-nav" aria-label="学习模块">
            <div className="sd-module-nav-rail">
              <button
                type="button"
                className={
                  screen === "prestudies" || screen === "prestudy"
                    ? "sd-module-nav-item is-active"
                    : "sd-module-nav-item"
                }
                onClick={() => {
                  setSelectedPrestudyId(null);
                  setScreen("prestudies");
                }}
              >
                <Lightbulb className="sd-module-nav-icon" strokeWidth={2.1} aria-hidden />
                <span className="sd-module-nav-text">
                  <span className="sd-module-nav-label">AI智能预习</span>
                  <span className="sd-module-nav-desc">课前目标反馈</span>
                </span>
              </button>
              <button
                type="button"
                className={
                  screen === "chapters" || screen === "chapter"
                    ? "sd-module-nav-item is-active"
                    : "sd-module-nav-item"
                }
                onClick={() => void goChapters()}
              >
                <BookOpen className="sd-module-nav-icon" strokeWidth={2.1} aria-hidden />
                <span className="sd-module-nav-text">
                  <span className="sd-module-nav-label">AI课堂练习</span>
                  <span className="sd-module-nav-desc">AI助教陪练</span>
                </span>
              </button>
              <button
                type="button"
                className={
                  screen === "postExercises" || screen === "postExercise"
                    ? "sd-module-nav-item is-active"
                    : "sd-module-nav-item"
                }
                onClick={() => {
                  setSelectedPostExerciseId(null);
                  setScreen("postExercises");
                }}
              >
                <ClipboardList className="sd-module-nav-icon" strokeWidth={2.1} aria-hidden />
                <span className="sd-module-nav-text">
                  <span className="sd-module-nav-label">AI课后作业</span>
                  <span className="sd-module-nav-desc">测验与 AI 批改</span>
                </span>
              </button>
            </div>
          </nav>
        )}
      </header>

      {okHint && (
        <Alert className="sd-alert sd-alert-ok">
          <AlertDescription>{okHint}</AlertDescription>
        </Alert>
      )}
      {err && (
        <Alert className="sd-alert" variant="destructive">
          <AlertDescription>{err}</AlertDescription>
        </Alert>
      )}

      {screen === "auth" && (
        <section className="sd-auth-layout">
          <Card className="sd-card sd-auth" size="default">
            <CardHeader>
              <CardTitle>学生入口</CardTitle>
              <CardDescription>使用老师名单中的学号登录。</CardDescription>
            </CardHeader>
            <CardContent>
              <Tabs
                value={authTab}
                onValueChange={(value) =>
                  switchAuthTab(value === "register" ? "register" : "login")
                }
              >
                <TabsList className="sd-auth-tabs">
                  <TabsTrigger value="login">登录</TabsTrigger>
                  <TabsTrigger value="register">注册</TabsTrigger>
                </TabsList>
                <TabsContent value="login">
                  <form className="sd-form" onSubmit={onLogin}>
                    <div className="sd-form-copy">
                      <h2>欢迎回来</h2>
                      <p>使用你的学号和密码登录</p>
                    </div>
                    <label>
                      学号
                      <Input
                        value={studentNo}
                        onChange={(e) => setStudentNo(e.target.value)}
                        autoComplete="username"
                      />
                    </label>
                    <label>
                      密码
                      <Input
                        type="password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        autoComplete="current-password"
                      />
                    </label>
                    <div className="sd-form-actions">
                      <Button type="submit" disabled={loading}>
                        {loading ? "进入中…" : "进入练习"}
                      </Button>
                    </div>
                  </form>
                </TabsContent>
                <TabsContent value="register">
                  <form className="sd-form" onSubmit={onRegister}>
                    <div className="sd-form-copy">
                      <h2>首次使用</h2>
                      <p>
                        请使用金陵科技学院学籍学号与真实姓名完成注册，信息须与教师导入名单一致；登录密码由你自行设置并妥善保管。
                      </p>
                    </div>
                    <label>
                      学号
                      <Input
                        value={studentNo}
                        onChange={(e) => setStudentNo(e.target.value)}
                        autoComplete="username"
                      />
                    </label>
                    <label>
                      姓名
                      <Input
                        value={fullName}
                        onChange={(e) => setFullName(e.target.value)}
                        autoComplete="name"
                      />
                    </label>
                    <label>
                      设置密码
                      <Input
                        type="password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        autoComplete="new-password"
                      />
                    </label>
                    <label>
                      确认密码
                      <Input
                        type="password"
                        value={password2}
                        onChange={(e) => setPassword2(e.target.value)}
                        autoComplete="new-password"
                      />
                    </label>
                    <div className="sd-form-actions">
                      <Button type="submit" disabled={loading}>
                        {loading ? "注册中…" : "创建账号"}
                      </Button>
                    </div>
                  </form>
                </TabsContent>
              </Tabs>
            </CardContent>
          </Card>
        </section>
      )}

      {screen === "chapters" && (
        <Card className="sd-card sd-chapters-card">
          <CardHeader>
            <CardTitle>AI课堂练习</CardTitle>
            <CardDescription>选择一章进入课堂练习，系统会显示你的学习进度。</CardDescription>
          </CardHeader>
          <CardContent>
          {chapters.length === 0 ? (
            <div className="sd-empty">
              <p>还没有开放的课堂练习章节。</p>
              <span>等老师发布后，这里会出现章节列表。</span>
            </div>
          ) : (
            <ul className="sd-list">
              {chapters.map((c) => {
                const mergedStatus = mergePracticeStatusForList(
                  c.practiceStatus,
                  c.chapterId,
                  currentStudentId,
                );
                return (
                <li key={c.chapterId}>
                  <Card className="sd-chapter-item" size="sm">
                    <CardHeader>
                  <div className="sd-list-main">
                    <CardTitle className="group-data-[size=sm]/card:text-xl group-data-[size=sm]/card:font-semibold">
                      {c.title}
                    </CardTitle>
                  </div>
                      <CardAction className="sd-list-action">
                        <Badge
                          variant={practiceStatusTone(mergedStatus)}
                          title="本章练习进度"
                          aria-label={`本章练习状态：${practiceStatusLabel(mergedStatus)}`}
                        >
                          {practiceStatusLabel(mergedStatus)}
                        </Badge>
                        <Button
                          type="button"
                          size="sm"
                          onClick={() => void openChapter(c.chapterId)}
                        >
                          {practiceActionLabel(mergedStatus)}
                        </Button>
                      </CardAction>
                    </CardHeader>
                  </Card>
                </li>
                );
              })}
            </ul>
          )}
          </CardContent>
        </Card>
      )}

      {screen === "chapter" && selected && (
        <section className="sd-chapter-wrap">
          <div className="sd-chapter-topbar">
            <Button type="button" variant="outline" onClick={backToChapters}>
              返回课堂练习
            </Button>
            <span>练习会自动保留本地草稿。</span>
          </div>
          {selected.publishedContent && currentStudentId ? (
            <ChapterPractice
              studentId={currentStudentId}
              chapterId={selected.id}
              title={selected.title}
              publishedContent={selected.publishedContent}
              initialChapterCompleted={!!selected.hasCompletedChapter}
              initialCellsPassed={selected.cellsPassed ?? []}
              onBackToList={backToChapters}
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

      {screen === "prestudies" && <PrestudyList onOpen={openPrestudy} />}

      {screen === "prestudy" && selectedPrestudyId && (
        <PrestudyDetail prestudyId={selectedPrestudyId} onBack={backToPrestudies} />
      )}

      {screen === "postExercises" && <PostExerciseList onOpen={openPostExercise} />}

      {screen === "postExercise" && selectedPostExerciseId && (
        <PostExerciseDetail
          exerciseId={selectedPostExerciseId}
          studentId={currentStudentId}
          onBack={backToPostExercises}
        />
      )}
    </main>
  );
}

export default App;
