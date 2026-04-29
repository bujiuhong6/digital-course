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

export type PrestudyListItem = {
  prestudyId: string;
  title: string;
  order: number;
  submitted: boolean;
  updatedAt: string | null;
};

type Props = {
  onOpen: (id: string) => void;
};

export function PrestudyList({ onOpen }: Props) {
  const [items, setItems] = useState<PrestudyListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    apiJson<{ prestudies: PrestudyListItem[] }>("/v1/student/prestudy")
      .then((data) => {
        if (!cancelled) setItems(data.prestudies);
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
        <CardTitle>AI智能预习</CardTitle>
        <CardDescription>课前先了解核心知识点，并告诉老师哪些内容需要重点讲。</CardDescription>
      </CardHeader>
      <CardContent>
        {err && <p className="sd-error-text">{err}</p>}
        {loading ? (
          <p className="sd-muted">正在加载预习内容…</p>
        ) : items.length === 0 ? (
          <div className="sd-empty">
            <p>还没有开放的预习。</p>
            <span>老师发布后，这里会出现课前预习列表。</span>
          </div>
        ) : (
          <ul className="sd-list">
            {items.map((item) => (
              <li key={item.prestudyId}>
                <Card className="sd-chapter-item" size="sm">
                  <CardHeader>
                    <div className="sd-list-main">
                      <CardTitle className="group-data-[size=sm]/card:text-xl group-data-[size=sm]/card:font-semibold">
                        {item.title}
                      </CardTitle>
                    </div>
                    <CardAction className="sd-list-action">
                      <Badge variant={item.submitted ? "default" : "outline"}>
                        {item.submitted ? "已提交" : "待反馈"}
                      </Badge>
                      <Button type="button" size="sm" onClick={() => onOpen(item.prestudyId)}>
                        {item.submitted ? "查看反馈" : "开始预习"}
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
