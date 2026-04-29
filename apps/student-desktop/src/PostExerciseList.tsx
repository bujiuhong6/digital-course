import { useEffect, useState } from "react";
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
import { apiJson } from "./api";

type PostExerciseListItem = {
  exerciseId: string;
  title: string;
  order: number;
  submitted: boolean;
  updatedAt: string | null;
};

type Props = {
  onOpen: (id: string) => void;
};

export function PostExerciseList({ onOpen }: Props) {
  const [items, setItems] = useState<PostExerciseListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    apiJson<{ exercises: PostExerciseListItem[] }>("/v1/student/post-exercises")
      .then((data) => {
        if (!cancelled) setItems(data.exercises);
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
  }, []);

  return (
    <Card className="sd-card sd-chapters-card">
      <CardHeader>
        <CardTitle>AI课后练习</CardTitle>
        <CardDescription>完成课后题目后，系统会调用 AI 给出分数和反馈。</CardDescription>
      </CardHeader>
      <CardContent>
        {err && <p className="sd-error-text">{err}</p>}
        {loading ? (
          <p className="sd-muted">正在加载课后练习…</p>
        ) : items.length === 0 ? (
          <div className="sd-empty">
            <p>还没有开放的课后练习。</p>
            <span>老师发布后，这里会出现练习列表。</span>
          </div>
        ) : (
          <ul className="sd-list">
            {items.map((item) => (
              <li key={item.exerciseId}>
                <Card className="sd-chapter-item" size="sm">
                  <CardHeader>
                    <div className="sd-list-main">
                      <CardTitle className="group-data-[size=sm]/card:text-xl group-data-[size=sm]/card:font-semibold">
                        {item.title}
                      </CardTitle>
                    </div>
                    <CardAction className="sd-list-action">
                      <Badge variant={item.submitted ? "default" : "outline"}>
                        {item.submitted ? "已提交" : "待完成"}
                      </Badge>
                      <Button type="button" size="sm" onClick={() => onOpen(item.exerciseId)}>
                        {item.submitted ? "查看分数" : "开始练习"}
                      </Button>
                    </CardAction>
                  </CardHeader>
                </Card>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
