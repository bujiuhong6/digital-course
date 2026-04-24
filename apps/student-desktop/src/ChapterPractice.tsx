import { useCallback, useState } from "react";
import { apiJson } from "./api";
import { runPythonInPyodide, ensurePyodide } from "./pyodideRunner";

type PassRule = { mode: string; expectedSubstring?: string };

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

type CellState = { passed: boolean | null; loading: boolean; lastMsg: string | null };

function htmlMd(html: string, key: string) {
  return (
    <div
      key={key}
      className="jnb-md-cell"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

export function ChapterPractice({ chapterId, title, publishedContent }: Props) {
  const [pyStatus, setPyStatus] = useState<"idle" | "loading" | "ready" | "err">("idle");
  const [pyErr, setPyErr] = useState<string | null>(null);
  const [codeMap, setCodeMap] = useState<Record<string, string>>({});
  const [cellState, setCellState] = useState<Record<string, CellState>>({});
  const [completeMsg, setCompleteMsg] = useState<string | null>(null);
  const [completing, setCompleting] = useState(false);

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

  if (!isPublishedV1(publishedContent)) {
    return (
      <p className="sd-muted">本章尚无有效的 publishedContent（需要 version: 1 与 blocks）。</p>
    );
  }

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

  const runAndVerify = async (kind: CellKind, cell: GuideCell | ExtensionCell) => {
    const id = cell.id;
    setCellState((s) => ({
      ...s,
      [id]: { passed: null, loading: true, lastMsg: null },
    }));
    setCompleteMsg(null);
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
        [id]: { passed: false, loading: false, lastMsg: err },
      }));
      return;
    }
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
        },
      }));
    } catch (e) {
      setCellState((s) => ({
        ...s,
        [id]: { passed: false, loading: false, lastMsg: String(e) },
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
    <div className="sd-chapter jnb-practice-surface">
      <h2 className="sd-chapter-title">{title}</h2>
      <p className="sd-muted sm" style={{ margin: "0 0 0.5rem" }}>
        Notebook 式练习（内嵌 Pyodide，与 design §2/§5 一致；非 Jupyter 官方应用）。
      </p>
      <div className="sd-pyodide-bar">
        {pyStatus === "idle" && (
          <span className="sd-muted sm">
            点「运行并上报」将自动下载并初始化 Pyodide（首次可能较慢），也可
            <button type="button" onClick={() => void prewarmPyodide()}>
              先预载
            </button>
            。
          </span>
        )}
        {pyStatus === "loading" && <span>正在预载 Pyodide…</span>}
        {pyStatus === "ready" && <span className="sd-ok">Pyodide 已就绪</span>}
        {pyStatus === "err" && (
          <span className="sd-bad">Pyodide：{pyErr || "不可用"}</span>
        )}
      </div>
      {publishedContent.blocks.map((b, bi) => {
        const i0 = bi * 3 + 1;
        const iGuide = i0 + 1;
        const iExt = i0 + 2;
        return (
          <section key={b.id} className="jnb-surface">
            <div className="jnb-block-title">第 {bi + 1} 块</div>
            {b.requiredExecutionMode && (
              <p className="jnb-hint" style={{ paddingLeft: 0, marginTop: 0 }}>
                本章要求执行模式：{b.requiredExecutionMode}（见 design §5）
              </p>
            )}
            <div className="jnb-code-cell">
              <span className="jnb-prompt">In [{i0}]:</span>
              <div className="jnb-code-col">
                {htmlMd(b.knowledgeHtml || "<p></p>", `${b.id}-kn`)}
              </div>
            </div>

            <div className="jnb-block-title" style={{ marginTop: "0.75rem" }}>
              引导
            </div>
            {b.guideCell.description && (
              <p className="jnb-hint" style={{ paddingLeft: 0 }}>
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
                  rows={5}
                  spellCheck={false}
                />
              </div>
            </div>
            <div className="jnb-run-row">
              <button
                type="button"
                onClick={() => void runAndVerify("guide", b.guideCell)}
                disabled={cellState[b.guideCell.id]?.loading}
              >
                {cellState[b.guideCell.id]?.loading ? "运行中…" : "运行并上报"}
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

            <div className="jnb-block-title" style={{ marginTop: "0.75rem" }}>
              扩展
            </div>
            <div className="jnb-code-cell">
              <span className="jnb-prompt">（说明）</span>
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
                  rows={6}
                  spellCheck={false}
                />
              </div>
            </div>
            <div className="jnb-run-row">
              <button
                type="button"
                onClick={() => void runAndVerify("extension", b.extensionCell)}
                disabled={cellState[b.extensionCell.id]?.loading}
              >
                {cellState[b.extensionCell.id]?.loading
                  ? "运行中…"
                  : "运行并上报"}
              </button>
              {cellState[b.extensionCell.id]?.lastMsg && (
                <span
                  className={
                    cellState[b.extensionCell.id]?.passed ? "jnb-ok" : "jnb-warn"
                  }
                >
                  {cellState[b.extensionCell.id]?.lastMsg}
                </span>
              )}
            </div>
          </section>
        );
      })}

      <div className="sd-complete">
        <button
          type="button"
          onClick={() => void onComplete()}
          disabled={completing}
        >
          {completing ? "…" : "尝试标记本章完成"}
        </button>
        {completeMsg && <p className="sd-muted">{completeMsg}</p>}
        <p className="sd-muted sm">
          需每个 cell 在服务端记录为通过后才能完成；否则会返回 400。
        </p>
      </div>
    </div>
  );
}
