import { useCallback, useEffect, useMemo, useState } from "react";
import { apiJson } from "./api";
import { StudentChat } from "./StudentChat";
import {
  runPythonInPyodide,
  ensurePyodide,
  type RunResult,
} from "./pyodideRunner";

type PassRule = {
  mode: string;
  expectedSubstring?: string;
  assertCode?: string;
};

type GuideCell = {
  id: string;
  starterCode: string;
  description: string;
  passRule: PassRule;
};

type ExtensionCell = {
  id: string;
  promptHtml: string;
  starterCode: string | null;
  passRule: PassRule;
};

type Block = {
  id: string;
  knowledgeHtml: string;
  requiredExecutionMode?: string | null;
  guideCell: GuideCell;
  extensionCell: ExtensionCell;
};

type PublishedV1 = { version: 1; blocks: Block[] };

function isPublishedV1(x: unknown): x is PublishedV1 {
  if (!x || typeof x !== "object") {
    return false;
  }
  const o = x as { version?: unknown; blocks?: unknown };
  return o.version === 1 && Array.isArray(o.blocks);
}

type Props = {
  chapterId: string;
  title: string;
  publishedContent: unknown;
};

type CellKind = "guide" | "extension";

type CellState = {
  passed: boolean | null;
  loading: boolean;
  lastMsg: string | null;
  /** 最近一次在浏览器内运行结果（stdout/异常） */
  lastRun: RunResult | null;
};

function htmlMd(html: string, key: string) {
  return (
    <div
      key={key}
      className="jnb-md-cell"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

function formatRunForDisplay(r: RunResult): string {
  if (!r.runOk) {
    const parts: string[] = [];
    if (r.errorExcerpt) {
      parts.push(r.errorExcerpt);
    }
    if (r.stderr) {
      parts.push(`[stderr]\n${r.stderr}`);
    }
    if (r.stdout) {
      parts.push(`[stdout]\n${r.stdout}`);
    }
    return parts.length > 0 ? parts.join("\n\n") : "运行未成功（无详细消息）。";
  }
  const o = (r.stdout || "").trimEnd();
  const e = (r.stderr || "").trimEnd();
  if (e) {
    return o ? `${o}\n\n[stderr]\n${e}` : `[stderr]\n${e}`;
  }
  return o || "（无标准输出）";
}

function RunOutputBlock({ run }: { run: RunResult | null | undefined }) {
  if (!run) {
    return null;
  }
  const bad = !run.runOk;
  return (
    <div className="jnb-out">
      <div className="jnb-out-label">Out：</div>
      <pre
        className={["jnb-out-text", bad ? "jnb-out-text--bad" : ""]
          .filter(Boolean)
          .join(" ")}
      >
        {formatRunForDisplay(run)}
      </pre>
    </div>
  );
}

function ChapterPracticeInner({
  chapterId,
  title,
  data,
}: {
  chapterId: string;
  title: string;
  data: PublishedV1;
}) {
  const [pyStatus, setPyStatus] = useState<"idle" | "loading" | "ready" | "err">("idle");
  const [pyErr, setPyErr] = useState<string | null>(null);
  const [codeMap, setCodeMap] = useState<Record<string, string>>({});
  const [cellState, setCellState] = useState<Record<string, CellState>>({});
  const [completeMsg, setCompleteMsg] = useState<string | null>(null);
  const [completing, setCompleting] = useState(false);
  const [activeCellId, setActiveCellId] = useState<string | null>(null);

  const setCode = (id: string, v: string) => {
    setCodeMap((m) => ({ ...m, [id]: v }));
  };

  const getCode = (kind: CellKind, cell: GuideCell | ExtensionCell) => {
    const o = codeMap[cell.id];
    if (o !== undefined) {
      return o;
    }
    if (kind === "extension") {
      return (cell as ExtensionCell).starterCode ?? "";
    }
    return (cell as GuideCell).starterCode;
  };

  const getCodeByCellId = useCallback(
    (cellId: string) => {
      for (const b of data.blocks) {
        if (b.guideCell.id === cellId) {
          return getCode("guide", b.guideCell);
        }
        if (b.extensionCell.id === cellId) {
          return getCode("extension", b.extensionCell);
        }
      }
      return "";
    },
    [data.blocks, codeMap],
  );

  const defaultChatCellId = useMemo(
    () => data.blocks[0]?.guideCell.id ?? null,
    [data.blocks],
  );

  useEffect(() => {
    if (defaultChatCellId && !activeCellId) {
      setActiveCellId(defaultChatCellId);
    }
  }, [defaultChatCellId, activeCellId]);

  const getChatContext = useCallback(() => {
    const id =
      activeCellId ?? defaultChatCellId ?? data.blocks[0].guideCell.id;
    return { cellId: id, currentCode: getCodeByCellId(id) };
  }, [activeCellId, defaultChatCellId, getCodeByCellId, data.blocks]);

  const prewarmPyodide = useCallback(async () => {
    if (pyStatus === "ready" || pyStatus === "loading") {
      return;
    }
    setPyStatus("loading");
    setPyErr(null);
    try {
      await ensurePyodide();
      setPyStatus("ready");
    } catch (e) {
      setPyStatus("err");
      setPyErr(String(e));
    }
  }, [pyStatus]);

  const runAndVerify = async (kind: CellKind, cell: GuideCell | ExtensionCell) => {
    const id = cell.id;
    setCellState((s) => ({
      ...s,
      [id]: {
        passed: null,
        loading: true,
        lastMsg: null,
        lastRun: null,
      },
    }));
    setCompleteMsg(null);
    setActiveCellId(id);
    const code = getCode(kind, cell);
    let run: Awaited<ReturnType<typeof runPythonInPyodide>>;
    try {
      await ensurePyodide();
      setPyStatus("ready");
      setPyErr(null);
      run = await runPythonInPyodide(code);
    } catch (e) {
      const err = e instanceof Error ? e.message : String(e);
      setPyStatus("err");
      setPyErr(err);
      setCellState((s) => ({
        ...s,
        [id]: {
          passed: false,
          loading: false,
          lastMsg: err,
          lastRun: {
            stdout: "",
            stderr: "",
            runOk: false,
            errorExcerpt: err,
            elapsedMs: 0,
          },
        },
      }));
      return;
    }
    setCellState((s) => ({
      ...s,
      [id]: {
        passed: s[id]?.passed ?? null,
        loading: true,
        lastMsg: s[id]?.lastMsg ?? null,
        lastRun: run,
      },
    }));
    try {
      const res = await apiJson<{
        ok: boolean;
        passed: boolean;
        runOk: boolean;
      }>("/v1/student/cells/verify", {
        method: "POST",
        body: JSON.stringify({
          chapterId,
          cellId: id,
          runOk: run.runOk,
          stdout: run.stdout,
          stderr: run.stderr,
          errorExcerpt: run.errorExcerpt,
          elapsedMs: run.elapsedMs,
        }),
      });
      setCellState((s) => ({
        ...s,
        [id]: {
          passed: res.passed,
          loading: false,
          lastMsg: res.passed ? "本关已记录为通过" : "未通过（见过关规则或输出）",
          lastRun: run,
        },
      }));
    } catch (e) {
      setCellState((s) => ({
        ...s,
        [id]: {
          passed: false,
          loading: false,
          lastMsg: String(e),
          lastRun: run,
        },
      }));
    }
  };

  const onComplete = async () => {
    setCompleting(true);
    setCompleteMsg(null);
    try {
      const r = await apiJson<{ ok?: boolean; alreadyCompleted?: boolean }>(
        `/v1/student/chapters/${chapterId}/complete`,
        { method: "POST" },
      );
      setCompleteMsg(
        r.alreadyCompleted ? "本章此前已标记完成" : "本章已标记完成",
      );
    } catch (e) {
      setCompleteMsg(String(e));
    } finally {
      setCompleting(false);
    }
  };

  return (
    <div
      className="sd-chapter jnb-student-embed"
      style={{ marginTop: "0.5rem" }}
    >
      <div
        className="jnb-page"
        style={{ border: "none", margin: 0, maxWidth: "none" }}
      >
        <h2 className="jnb-hero-title">{title}</h2>
        <p className="jnb-hero-lead">
          Notebook
          式练习（内嵌 Pyodide，与 design
          文档一致；运行环境在浏览器中，为教学用途的轻量实现）。
        </p>
        <div className="jnb-py-box" role="status">
          {pyStatus === "idle" && (
            <>
              点「运行并上报」将自动下载并初始化 Pyodide（首次可能较慢）。也可
              <button
                type="button"
                className="jnb-preload-link"
                onClick={() => void prewarmPyodide()}
              >
                先预载运行环境
              </button>
              。
            </>
          )}
          {pyStatus === "loading" && <span>正在预载 Pyodide…</span>}
          {pyStatus === "ready" && (
            <span className="jnb-status-ok">Pyodide 已就绪</span>
          )}
          {pyStatus === "err" && (
            <span className="jnb-status-err">
              Pyodide：{pyErr || "不可用"}
            </span>
          )}
        </div>
        {data.blocks.map((b, bi) => {
          const i0 = bi * 3 + 1;
          const iGuide = i0 + 1;
          const iExt = i0 + 2;
          return (
            <section key={b.id} className="jnb-section">
              <div className="jnb-sec-h">
                第 <strong>{bi + 1}</strong> 块
              </div>
              {b.requiredExecutionMode && (
                <p
                  className="jnb-hint"
                  style={{ paddingLeft: 0, marginTop: 0 }}
                >
                  本章要求执行模式：<code>{b.requiredExecutionMode}</code>
                </p>
              )}
              <div className="jnb-code-cell">
                <span className="jnb-prompt">In [{i0}]:</span>
                <div className="jnb-code-col">
                  {htmlMd(b.knowledgeHtml || "<p></p>", `${b.id}-kn`)}
                </div>
              </div>

              <div className="jnb-label" style={{ marginTop: "0.75rem" }}>
                引导
              </div>
              {b.guideCell.description && (
                <p className="jnb-cell-desc" style={{ marginTop: 0 }}>
                  {b.guideCell.description}
                </p>
              )}
              <div className="jnb-code-cell">
                <span className="jnb-prompt">In [{iGuide}]:</span>
                <div className="jnb-code-col">
                  <textarea
                    className="jnb-input"
                    value={getCode("guide", b.guideCell)}
                    onChange={(e) => setCode(b.guideCell.id, e.target.value)}
                    onFocus={() => setActiveCellId(b.guideCell.id)}
                    rows={5}
                    spellCheck={false}
                  />
                </div>
              </div>
              <p className="jnb-pass">
                过关：模式 <code>{b.guideCell.passRule?.mode}</code>
                {b.guideCell.passRule?.expectedSubstring ? (
                  <>
                    ，stdout 须含{" "}
                    <code>{b.guideCell.passRule.expectedSubstring}</code>
                  </>
                ) : null}
                {b.guideCell.passRule?.assertCode ? (
                  <>
                    ，断言 <code>{b.guideCell.passRule.assertCode}</code>
                  </>
                ) : null}
              </p>
              <div className="jnb-run-row">
                <button
                  type="button"
                  onClick={() => void runAndVerify("guide", b.guideCell)}
                  disabled={cellState[b.guideCell.id]?.loading}
                >
                  {cellState[b.guideCell.id]?.loading
                    ? "运行中…"
                    : "运行并上报"}
                </button>
                {cellState[b.guideCell.id]?.lastMsg && (
                  <span
                    className={
                      cellState[b.guideCell.id]?.passed ? "jnb-ok" : "jnb-warn"
                    }
                  >
                    {cellState[b.guideCell.id]?.lastMsg}
                  </span>
                )}
              </div>
              <RunOutputBlock run={cellState[b.guideCell.id]?.lastRun} />

              <div className="jnb-label" style={{ marginTop: "0.75rem" }}>
                扩展
              </div>
              <div className="jnb-code-cell">
                <span className="jnb-prompt jnb-prompt--muted">（说明）</span>
                <div className="jnb-code-col">
                  {htmlMd(
                    b.extensionCell.promptHtml || "<p></p>",
                    `${b.id}-ex`,
                  )}
                </div>
              </div>
              <div className="jnb-code-cell">
                <span className="jnb-prompt">In [{iExt}]:</span>
                <div className="jnb-code-col">
                  <textarea
                    className="jnb-input"
                    value={getCode("extension", b.extensionCell)}
                    onChange={(e) => setCode(b.extensionCell.id, e.target.value)}
                    onFocus={() => setActiveCellId(b.extensionCell.id)}
                    rows={6}
                    spellCheck={false}
                  />
                </div>
              </div>
              <p className="jnb-pass">
                过关：模式 <code>{b.extensionCell.passRule?.mode}</code>
                {b.extensionCell.passRule?.expectedSubstring ? (
                  <>
                    ，stdout 须含{" "}
                    <code>{b.extensionCell.passRule.expectedSubstring}</code>
                  </>
                ) : null}
                {b.extensionCell.passRule?.assertCode ? (
                  <>
                    ，断言 <code>{b.extensionCell.passRule.assertCode}</code>
                  </>
                ) : null}
              </p>
              <div className="jnb-run-row">
                <button
                  type="button"
                  onClick={() =>
                    void runAndVerify("extension", b.extensionCell)
                  }
                  disabled={cellState[b.extensionCell.id]?.loading}
                >
                  {cellState[b.extensionCell.id]?.loading
                    ? "运行中…"
                    : "运行并上报"}
                </button>
                {cellState[b.extensionCell.id]?.lastMsg && (
                  <span
                    className={
                      cellState[b.extensionCell.id]?.passed
                        ? "jnb-ok"
                        : "jnb-warn"
                    }
                  >
                    {cellState[b.extensionCell.id]?.lastMsg}
                  </span>
                )}
              </div>
              <RunOutputBlock run={cellState[b.extensionCell.id]?.lastRun} />
            </section>
          );
        })}

        <div className="jnb-footer-actions">
          <button
            type="button"
            onClick={() => void onComplete()}
            disabled={completing}
          >
            {completing ? "…" : "尝试标记本章完成"}
          </button>
          {completeMsg && <p className="jnb-footer-msg">{completeMsg}</p>}
          <p className="jnb-footer-hint">
            需每个 cell 在服务端记录为通过后才能完成；否则接口会返回 400。
          </p>
        </div>
      </div>
      <StudentChat chapterId={chapterId} getContext={getChatContext} />
    </div>
  );
}

export function ChapterPractice({ chapterId, title, publishedContent }: Props) {
  if (!isPublishedV1(publishedContent)) {
    return (
      <p className="sd-muted">本章尚无有效的 publishedContent（需要 version: 1 与 blocks）。</p>
    );
  }
  return (
    <ChapterPracticeInner
      chapterId={chapterId}
      title={title}
      data={publishedContent}
    />
  );
}
