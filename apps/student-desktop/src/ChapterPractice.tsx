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
  exerciseTitle?: string | null;
  expectedOutput?: string | null;
  referenceAnswer?: string | null;
};

type ExtensionCell = {
  id: string;
  promptHtml: string;
  starterCode: string | null;
  passRule: PassRule;
  exerciseTitle?: string | null;
  expectedOutput?: string | null;
  referenceAnswer?: string | null;
};

type Block = {
  id: string;
  sectionTitle?: string | null;
  knowledgeHtml: string;
  requiredExecutionMode?: string | null;
  guideCell: GuideCell;
  extensionCell: ExtensionCell;
};

type PublishedV1 = {
  version: 1;
  chapterIntroHtml?: string;
  blocks: Block[];
};

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

/** 运行结果区：纯展示；消息栏与判分逻辑分离 */
type FeedbackKind =
  | "idle"
  | "syntax_error"
  | "logic_fail"
  | "pass"
  | "network";

type CellState = {
  passed: boolean | null;
  loading: boolean;
  lastMsg: string | null;
  /** 最近一次在浏览器内运行结果（stdout/异常） */
  lastRun: RunResult | null;
  feedbackKind: FeedbackKind;
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
    if (r.fullError) {
      parts.push(r.fullError);
    } else if (r.errorExcerpt) {
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

function runOutputIsSyntaxStyle(run: RunResult | null | undefined): boolean {
  return Boolean(run) && !run!.runOk;
}

/** 在状态未及时写入 feedbackKind 时，从 run + passed 回退派生 */
function effectiveFeedback(
  s: CellState | undefined,
): { kind: FeedbackKind; showMsg: boolean } {
  if (!s) {
    return { kind: "idle", showMsg: false };
  }
  if (s.feedbackKind === "network" && s.lastMsg) {
    return { kind: "network", showMsg: true };
  }
  if (s.feedbackKind === "network") {
    return { kind: "network", showMsg: false };
  }
  if (s.feedbackKind !== "idle") {
    return { kind: s.feedbackKind, showMsg: true };
  }
  if (!s.lastRun) {
    return { kind: "idle", showMsg: false };
  }
  if (!s.lastRun.runOk) {
    return { kind: "syntax_error", showMsg: true };
  }
  if (s.passed === true) {
    return { kind: "pass", showMsg: true };
  }
  if (s.passed === false) {
    return { kind: "logic_fail", showMsg: true };
  }
  return { kind: "idle", showMsg: false };
}

function MessageBar({
  kind,
  showMsg,
  passedServer,
  text,
}: {
  kind: FeedbackKind;
  showMsg: boolean;
  passedServer: boolean | null;
  text: string | null;
}) {
  if (!showMsg) {
    return null;
  }
  if (kind === "network" && text) {
    return (
      <div className="jnb-msg jnb-msg--err" role="alert">
        <div className="jnb-msg-label">系统</div>
        <div className="jnb-msg-body">{text}</div>
      </div>
    );
  }
  if (kind === "syntax_error") {
    return (
      <div className="jnb-msg jnb-msg--err" role="status">
        <div className="jnb-msg-label">运行</div>
        <div className="jnb-msg-body">代码存在错误，请按上方「运行结果」区中的 Python 提示修改后再试。</div>
      </div>
    );
  }
  if (kind === "logic_fail") {
    return (
      <div className="jnb-msg jnb-msg--warn" role="status">
        <div className="jnb-msg-label">本题</div>
        <div className="jnb-msg-body">未做对：程序能运行，但输出与题目要求不符。上方为本次运行结果；可对照下方过关说明与标准答案参考修改，再点「运行并上报」。
        </div>
      </div>
    );
  }
  if (kind === "pass" && passedServer === true) {
    return (
      <div className="jnb-msg jnb-msg--ok" role="status">
        <div className="jnb-msg-label">恭喜</div>
        <div className="jnb-msg-body">此题已答对。上方为运行结果，系统已记录为通过。</div>
      </div>
    );
  }
  return null;
}

function RunOutputBlock({ run }: { run: RunResult | null | undefined }) {
  if (!run) {
    return (
      <div className="jnb-out jnb-out--empty">
        <div className="jnb-out-label">运行结果</div>
        <p className="jnb-out-empty">运行后在此显示标准输出或 Python 报错。</p>
      </div>
    );
  }
  const bad = runOutputIsSyntaxStyle(run);
  return (
    <div className="jnb-out">
      <div className="jnb-out-label">运行结果</div>
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

  const runAndVerify = async (kind: CellKind, cell: GuideCell | ExtensionCell) => {
    const id = cell.id;
    setCellState((s) => ({
      ...s,
      [id]: {
        passed: null,
        loading: true,
        lastMsg: null,
        lastRun: null,
        feedbackKind: "idle",
      },
    }));
    setCompleteMsg(null);
    setActiveCellId(id);
    const code = getCode(kind, cell);
    let run: Awaited<ReturnType<typeof runPythonInPyodide>>;
    try {
      await ensurePyodide();
      run = await runPythonInPyodide(code);
    } catch (e) {
      const err = e instanceof Error ? e.message : String(e);
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
            fullError: err,
            elapsedMs: 0,
          },
          feedbackKind: "network",
        },
      }));
      return;
    }
    const isSyntaxErr = !run.runOk;
    setCellState((s) => ({
      ...s,
      [id]: {
        passed: s[id]?.passed ?? null,
        loading: !isSyntaxErr,
        lastMsg: null,
        lastRun: run,
        feedbackKind: isSyntaxErr ? "syntax_error" : "idle",
      },
    }));
    if (isSyntaxErr) {
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
      const fk: FeedbackKind = res.passed ? "pass" : "logic_fail";
      setCellState((s) => ({
        ...s,
        [id]: {
          passed: res.passed,
          loading: false,
          lastMsg: null,
          lastRun: run,
          feedbackKind: fk,
        },
      }));
    } catch (e) {
      const em = e instanceof Error ? e.message : String(e);
      setCellState((s) => ({
        ...s,
        [id]: {
          passed: false,
          loading: false,
          lastMsg: em,
          lastRun: run,
          feedbackKind: "network",
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
        <h1 className="jnb-chapter-h1">{title}</h1>
        {data.chapterIntroHtml
          ? htmlMd(data.chapterIntroHtml, "chapter-intro")
          : null}
        {data.blocks.map((b, bi) => {
          const sec = b.sectionTitle?.trim() || `知识点 ${bi + 1}`;
          const gTitle =
            b.guideCell.exerciseTitle?.trim() || "第 1 题（基础）";
          const eTitle =
            b.extensionCell.exerciseTitle?.trim() || "第 1 题（扩展）";
          return (
            <div key={b.id} className="jnb-kp">
              <h2 className="jnb-h2">{sec}</h2>
              {b.knowledgeHtml
                ? htmlMd(b.knowledgeHtml, `${b.id}-kp`)
                : null}

              <h3 className="jnb-h3">基础练习</h3>
              <h4 className="jnb-h4">{gTitle}</h4>
              {htmlMd(b.guideCell.description, `${b.id}-gdesc`)}
              {b.guideCell.expectedOutput ? (
                <div className="jnb-expected">
                  <div className="jnb-expected-h">题目期望的输出或结果</div>
                  <div className="jnb-expected-body">
                    {b.guideCell.expectedOutput}
                  </div>
                </div>
              ) : null}
              <div className="jnb-code-row">
                <span className="jnb-prompt jnb-prompt--code">代码</span>
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
                判定标准：模式 <code>{b.guideCell.passRule?.mode}</code>
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
              <div className="jnb-run-row jnb-run-row--top">
                <button
                  type="button"
                  onClick={() => void runAndVerify("guide", b.guideCell)}
                  disabled={cellState[b.guideCell.id]?.loading}
                >
                  {cellState[b.guideCell.id]?.loading
                    ? "运行中…"
                    : "运行并上报"}
                </button>
              </div>
              {cellState[b.guideCell.id]?.loading &&
              !cellState[b.guideCell.id]?.lastRun ? (
                <p className="jnb-pending">正在执行代码并上报结果…</p>
              ) : null}
              <RunOutputBlock run={cellState[b.guideCell.id]?.lastRun} />
              <MessageBar
                {...effectiveFeedback(cellState[b.guideCell.id])}
                passedServer={cellState[b.guideCell.id]?.passed ?? null}
                text={cellState[b.guideCell.id]?.lastMsg}
              />
              {b.guideCell.referenceAnswer ? (
                <div className="jnb-ref">
                  <div className="jnb-ref-h">标准答案参考</div>
                  <pre className="jnb-ref-pre">{b.guideCell.referenceAnswer}</pre>
                </div>
              ) : null}

              <h3 className="jnb-h3 jnb-h3--ext">扩展练习</h3>
              <h4 className="jnb-h4">{eTitle}</h4>
              {htmlMd(b.extensionCell.promptHtml || "<p></p>", `${b.id}-exq`)}
              {b.extensionCell.expectedOutput ? (
                <div className="jnb-expected">
                  <div className="jnb-expected-h">题目期望的输出或结果</div>
                  <div className="jnb-expected-body">
                    {b.extensionCell.expectedOutput}
                  </div>
                </div>
              ) : null}
              <div className="jnb-code-row">
                <span className="jnb-prompt jnb-prompt--code">代码</span>
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
                判定标准：模式 <code>{b.extensionCell.passRule?.mode}</code>
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
              <div className="jnb-run-row jnb-run-row--top">
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
              </div>
              {cellState[b.extensionCell.id]?.loading &&
              !cellState[b.extensionCell.id]?.lastRun ? (
                <p className="jnb-pending">正在执行代码并上报结果…</p>
              ) : null}
              <RunOutputBlock run={cellState[b.extensionCell.id]?.lastRun} />
              <MessageBar
                {...effectiveFeedback(cellState[b.extensionCell.id])}
                passedServer={cellState[b.extensionCell.id]?.passed ?? null}
                text={cellState[b.extensionCell.id]?.lastMsg}
              />
              {b.extensionCell.referenceAnswer ? (
                <div className="jnb-ref">
                  <div className="jnb-ref-h">标准答案参考</div>
                  <pre className="jnb-ref-pre">
                    {b.extensionCell.referenceAnswer}
                  </pre>
                </div>
              ) : null}
            </div>
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
