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

type PrestudyItem = {
  id: string;
  title: string;
  learningGoal: string;
};

type PrestudyDetailBody = {
  prestudy: {
    prestudyId: string;
    title: string;
    content: { version: 1; items: PrestudyItem[] };
    submitted: boolean;
    response: {
      ratings: { itemId: string; score: number }[];
      feedbackText: string | null;
      submittedAt: string;
    } | null;
  };
};

type Props = {
  prestudyId: string;
  onBack: () => void;
};

export function PrestudyDetail({ prestudyId, onBack }: Props) {
  const [data, setData] = useState<PrestudyDetailBody["prestudy"] | null>(null);
  const [ratings, setRatings] = useState<Record<string, number>>({});
  const [feedback, setFeedback] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    apiJson<PrestudyDetailBody>(`/v1/student/prestudy/${prestudyId}`)
      .then((body) => {
        if (cancelled) return;
        setData(body.prestudy);
        const next: Record<string, number> = {};
        for (const r of body.prestudy.response?.ratings ?? []) {
          next[r.itemId] = r.score;
        }
        setRatings(next);
        setFeedback(body.prestudy.response?.feedbackText ?? "");
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
  }, [prestudyId]);

  const items = data?.content.items ?? [];
  const canSubmit = useMemo(
    () => items.length > 0 && items.every((item) => ratings[item.id] >= 1 && ratings[item.id] <= 7),
    [items, ratings],
  );

  async function submit() {
    if (!data || !canSubmit || saving) return;
    setSaving(true);
    setErr(null);
    try {
      await apiJson(`/v1/student/prestudy/${prestudyId}/responses`, {
        method: "POST",
        body: JSON.stringify({
          ratings: items.map((item) => ({ itemId: item.id, score: ratings[item.id] })),
          feedbackText: feedback,
        }),
      });
      setSaved(true);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="sd-chapter-wrap">
      <div className="sd-chapter-topbar">
        <Button type="button" variant="outline" onClick={onBack}>
          返回预习列表
        </Button>
        <span className="sd-prestudy-scale-hint">1 表示很容易达到，7 表示很难达到。</span>
      </div>
      {loading ? (
        <p className="sd-muted">正在加载预习内容…</p>
      ) : err ? (
        <p className="sd-error-text">{err}</p>
      ) : data ? (
        <Card className="sd-card">
          <CardHeader>
            <CardTitle>{data.title}</CardTitle>
            <CardDescription>请根据课前理解，评价每个学习目标的达成难度。</CardDescription>
          </CardHeader>
          <CardContent className="sd-prestudy-detail">
            {items.map((item) => (
              <div className="sd-prestudy-item" key={item.id}>
                <h3>{item.title}</h3>
                <p>{item.learningGoal}</p>
                <div className="sd-likert" role="radiogroup" aria-label={`${item.title} 难度评分`}>
                  {[1, 2, 3, 4, 5, 6, 7].map((score) => (
                    <button
                      key={score}
                      type="button"
                      className={ratings[item.id] === score ? "is-selected" : ""}
                      onClick={() => setRatings((prev) => ({ ...prev, [item.id]: score }))}
                    >
                      {score}
                    </button>
                  ))}
                </div>
              </div>
            ))}
            <label className="sd-field-label">
              匿名告诉老师你希望重点讲什么（选填）
              <Textarea
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
                placeholder="例如：希望多讲案例、演示步骤，或解释某个概念。"
              />
            </label>
            {saved && <p className="sd-ok-text">已提交，感谢你的课前反馈。</p>}
            <div className="sd-form-actions">
              <Button type="button" disabled={!canSubmit || saving} onClick={() => void submit()}>
                {saving ? "提交中…" : data.submitted ? "更新反馈" : "提交预习反馈"}
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : null}
    </section>
  );
}
