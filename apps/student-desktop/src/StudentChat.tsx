import { useCallback, useEffect, useRef, useState } from "react";
import { apiJson } from "./api";
import "./StudentChat.css";

type Msg = { role: "user" | "assistant"; content: string };

type Props = {
  chapterId: string;
  /** 当前选中的练习 cell 与代码（与 POST /v1/student/chat 一致） */
  getContext: () => { cellId: string; currentCode: string };
};

export function StudentChat({ chapterId, getContext }: Props) {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Msg[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open && listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [open, messages, loading]);

  const send = useCallback(async () => {
    const t = input.trim();
    if (!t || loading) {
      return;
    }
    const { cellId, currentCode } = getContext();
    const userMsg: Msg = { role: "user", content: t };
    const nextMsgs = [...messages, userMsg];
    setMessages(nextMsgs);
    setInput("");
    setErr(null);
    setLoading(true);
    try {
      const next = nextMsgs;
      const res = await apiJson<{
        message?: string;
        mock?: boolean;
        ok?: boolean;
      }>("/v1/student/chat", {
        method: "POST",
        body: JSON.stringify({
          chapterId,
          cellId,
          currentCode: currentCode || null,
          messages: next.map((x) => ({ role: x.role, content: x.content })),
        }),
      });
      const text = res.message ?? "（无回复内容）";
      setMessages((m) => [...m, { role: "assistant", content: text }]);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [chapterId, getContext, input, loading, messages]);

  return (
    <>
      <button
        type="button"
        className="sd-chat-fab"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        title="学习助手"
      >
        <span className="sd-chat-fab-icon" aria-hidden>
          ✦
        </span>
        <span>Chat</span>
      </button>
      {open && (
        <div className="sd-chat-backdrop" aria-hidden onClick={() => setOpen(false)} />
      )}
      <aside
        className={`sd-chat-panel${open ? " is-open" : ""}`}
        aria-label="学习助手"
      >
        <header className="sd-chat-hd">
          <img
            className="sd-chat-hd-icon"
            src="/chat-assistant.svg"
            width={24}
            height={24}
            alt=""
            aria-hidden
          />
          <h2>学习助手</h2>
          <button
            type="button"
            className="sd-chat-close"
            onClick={() => setOpen(false)}
            aria-label="关闭"
          >
            ×
          </button>
        </header>
        {err && <p className="sd-chat-err">{err}</p>}
        <div className="sd-chat-msgs" ref={listRef}>
          {messages.length === 0 && (
            <p className="sd-chat-hint">
              可询问本题代码、报错原因或改法。当前 cell 的代码会一并发给服务器（作上下文，可能被截断）。
            </p>
          )}
          {messages.map((m, i) => (
            <div
              key={`${i}-${m.role}`}
              className={`sd-chat-bubble ${m.role === "user" ? "is-user" : "is-bot"}`}
            >
              <pre className="sd-chat-bubble-txt">{m.content}</pre>
            </div>
          ))}
          {loading && <p className="sd-chat-loading">…</p>}
        </div>
        <footer className="sd-chat-ft">
          <textarea
            className="sd-chat-input"
            rows={2}
            placeholder="输入问题…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void send();
              }
            }}
          />
          <button
            type="button"
            className="sd-chat-send"
            disabled={loading || !input.trim()}
            onClick={() => void send()}
          >
            发送
          </button>
        </footer>
      </aside>
    </>
  );
}
