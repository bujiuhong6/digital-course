import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { apiJson } from "./api";
import { clearPostExerciseDraft, loadPostExerciseDraft, savePostExerciseDraft } from "./postExerciseDraftStorage";
import { StudentChat } from "./StudentChat";

type Choice = { id: string; text: string };
type Question = {
  id: string;
  type: "singleChoice" | "subjective" | "code";
  prompt: string;
  choices?: Choice[];
  starterCode?: string;
  points: number;
};

type Exercise = {
  exerciseId: string;
  title: string;
  content: { version: 1; questions: Question[] };
  submitted: boolean;
  submission: {
    score: number;
    feedback: string | null;
    submittedAt: string;
    answers: Answer[];
  } | null;
};

type Answer = {
  questionId: string;
  choiceId?: string | null;
  text?: string | null;
  code?: string | null;
};

type Props = {
  exerciseId: string;
  studentId: string | null;
  onBack: () => void;
};

export function PostExerciseDetail({ exerciseId, studentId, onBack }: Props) {
  const [exercise, setExercise] = useState<Exercise | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [activeQuestionId, setActiveQuestionId] = useState<string>("post-exercise");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [saveHint, setSaveHint] = useState<string | null>(null);
  const [result, setResult] = useState<{ score: number; feedback?: string | null } | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    apiJson<{ exercise: Exercise }>(`/v1/student/post-exercises/${exerciseId}`)
      .then((body) => {
        if (cancelled) return;
        setExercise(body.exercise);
        const ex = body.exercise;
        const next: Record<string, string> = {};
        for (const a of ex.submission?.answers ?? []) {
          next[a.questionId] = a.choiceId ?? a.text ?? a.code ?? "";
        }
        if (!ex.submitted) {
          for (const q of ex.content.questions) {
            if (q.type === "code" && q.starterCode && next[q.id] === undefined) {
              next[q.id] = q.starterCode;
            }
          }
        }
        if (!ex.submitted && studentId) {
          const draft = loadPostExerciseDraft(studentId, ex.exerciseId);
          if (draft) {
            const qIds = new Set(ex.content.questions.map((q) => q.id));
            for (const [k, v] of Object.entries(draft)) {
              if (qIds.has(k)) next[k] = v;
            }
          }
        }
        setAnswers(next);
        setResult(
          ex.submission
            ? { score: ex.submission.score, feedback: ex.submission.feedback }
            : null,
        );
        setActiveQuestionId(ex.content.questions[0]?.id ?? "post-exercise");
      })
      .catch((e) => {
        if (!cancelled) setErr(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [exerciseId, studentId]);

  useEffect(() => {
    if (!saveHint) return;
    const t = window.setTimeout(() => setSaveHint(null), 3500);
    return () => window.clearTimeout(t);
  }, [saveHint]);

  const questions = exercise?.content.questions ?? [];
  const canSubmit = useMemo(
    () => questions.length > 0 && questions.every((q) => (answers[q.id] ?? "").trim()),
    [answers, questions],
  );
  const readonly = Boolean(result);

  function answerPayload(): Answer[] {
    return questions.map((q) => {
      const value = answers[q.id] ?? "";
      if (q.type === "singleChoice") return { questionId: q.id, choiceId: value };
      if (q.type === "code") return { questionId: q.id, code: value };
      return { questionId: q.id, text: value };
    });
  }

  async function submit() {
    if (!canSubmit || submitting || readonly) return;
    setSubmitting(true);
    setErr(null);
    try {
      const res = await apiJson<{ score: number; feedback?: string }>(
        `/v1/student/post-exercises/${exerciseId}/submit`,
        { method: "POST", body: JSON.stringify({ answers: answerPayload() }) },
      );
      if (studentId) clearPostExerciseDraft(studentId, exerciseId);
      setResult({ score: res.score, feedback: res.feedback });
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  }

  function saveDraft() {
    if (!studentId || readonly || submitting) return;
    try {
      savePostExerciseDraft(studentId, exerciseId, { ...answers });
      setSaveHint("已保存。下次打开本题可继续作答。");
    } catch {
      setSaveHint("保存未成功。请重试或检查本机存储是否已满。");
    }
  }

  return (
    <section className="sd-chapter-wrap">
      <div className="sd-chapter-topbar">
        <Button type="button" variant="outline" onClick={onBack}>
          返回课后作业
        </Button>
        <span>代码题只提交文本，由 AI 根据标准答案和规则批改。</span>
      </div>
      {loading ? (
        <p className="sd-muted">正在加载课后作业…</p>
      ) : err ? (
        <p className="sd-error-text">{err}</p>
      ) : exercise ? (
        <Card className="sd-card">
          <CardHeader>
            <CardTitle>{exercise.title}</CardTitle>
            <CardDescription>作答时可以问 AI，但请保留自己的思考过程。</CardDescription>
          </CardHeader>
          <CardContent className="sd-post-detail">
            {questions.map((q, index) => (
              <div className="sd-post-question" key={q.id} onFocus={() => setActiveQuestionId(q.id)}>
                <h3>第{index + 1}题 · {q.type === "singleChoice" ? "单选题" : q.type === "code" ? "代码题" : "主观题"}</h3>
                <p>{q.prompt}</p>
                {q.type === "singleChoice" ? (
                  <div className="sd-choice-list">
                    {(q.choices ?? []).map((choice) => (
                      <label key={choice.id}>
                        <input
                          type="radio"
                          name={q.id}
                          disabled={readonly}
                          checked={answers[q.id] === choice.id}
                          onChange={() => setAnswers((prev) => ({ ...prev, [q.id]: choice.id }))}
                        />
                        {choice.id}. {choice.text}
                      </label>
                    ))}
                  </div>
                ) : (
                  <Textarea
                    className={q.type === "code" ? "sd-code-answer" : ""}
                    value={answers[q.id] ?? ""}
                    readOnly={readonly}
                    rows={q.type === "code" ? 8 : 5}
                    onFocus={() => setActiveQuestionId(q.id)}
                    onChange={(e) => setAnswers((prev) => ({ ...prev, [q.id]: e.target.value }))}
                    placeholder={q.type === "code" ? "在这里填写代码，提交后由 AI 批改。" : "写下你的回答。"}
                  />
                )}
              </div>
            ))}
            {result && (
              <div className="sd-score-card">
                <strong>{result.score} / 100</strong>
                <p>{result.feedback || "已完成批改。"}</p>
              </div>
            )}
            <div className="sd-form-actions-wrap">
              <div className="sd-form-actions">
                {!readonly ? (
                  <Button
                    type="button"
                    variant="outline"
                    disabled={!studentId || submitting}
                    onClick={saveDraft}
                  >
                    保存
                  </Button>
                ) : null}
                <Button
                  type="button"
                  disabled={!canSubmit || submitting || readonly}
                  onClick={() => void submit()}
                >
                  {submitting ? "批改中…" : readonly ? "已提交" : "提交并批改"}
                </Button>
              </div>
              {saveHint ? <p className="sd-save-hint sd-muted">{saveHint}</p> : null}
            </div>
          </CardContent>
        </Card>
      ) : null}
      {exercise && (
        <StudentChat
          chapterId={exercise.exerciseId}
          contextKind="postExercise"
          getContext={() => ({
            cellId: activeQuestionId,
            currentCode: answers[activeQuestionId] ?? "",
          })}
        />
      )}
    </section>
  );
}
