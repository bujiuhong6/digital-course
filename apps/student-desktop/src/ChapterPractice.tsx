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

function htmlBlock(html: string, key: string) {
  return (
    <div
      key={key}
      className="sd-prose"
      // 教师已审发布的 HTML；MVP 内联渲染
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
    <div className="sd-chapter">
      <h2 className="sd-chapter-title">{title}</h2>
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
      {publishedContent.blocks.map((b) => (
        <section key={b.id} className="sd-block">
          {htmlBlock(b.knowledgeHtml, `${b.id}-kn`)}
          {b.requiredExecutionMode && (
            <p className="sd-muted sm">
              本块要求：{b.requiredExecutionMode}
            </p>
          )}

          <h3>引导</h3>
          <p className="sd-cell-desc">{b.guideCell.description}</p>
          <label className="sd-code-label">代码</label>
          <textarea
            className="sd-code"
            value={getCode("guide", b.guideCell)}
            onChange={(e) => setCode(b.guideCell.id, e.target.value)}
            rows={5}
            spellCheck={false}
          />
          <div className="sd-row">
            <button
              type="button"
              onClick={() => void runAndVerify("guide", b.guideCell)}
              disabled={cellState[b.guideCell.id]?.loading}
            >
              {cellState[b.guideCell.id]?.loading ? "运行中…" : "运行并上报"}
            </button>
            {cellState[b.guideCell.id]?.lastMsg && (
              <span className={cellState[b.guideCell.id]?.passed ? "sd-ok" : "sd-warn"}>
                {cellState[b.guideCell.id]?.lastMsg}
              </span>
            )}
          </div>

          <h3>扩展</h3>
          {htmlBlock(b.extensionCell.promptHtml, `${b.id}-ex`)}
          <label className="sd-code-label">代码</label>
          <textarea
            className="sd-code"
            value={getCode("extension", b.extensionCell)}
            onChange={(e) => setCode(b.extensionCell.id, e.target.value)}
            rows={6}
            spellCheck={false}
          />
          <div className="sd-row">
            <button
              type="button"
              onClick={() => void runAndVerify("extension", b.extensionCell)}
              disabled={cellState[b.extensionCell.id]?.loading}
            >
              {cellState[b.extensionCell.id]?.loading ? "运行中…" : "运行并上报"}
            </button>
            {cellState[b.extensionCell.id]?.lastMsg && (
              <span
                className={
                  cellState[b.extensionCell.id]?.passed ? "sd-ok" : "sd-warn"
                }
              >
                {cellState[b.extensionCell.id]?.lastMsg}
              </span>
            )}
          </div>
        </section>
      ))}

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
