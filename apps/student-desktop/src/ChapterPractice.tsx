import { useCallback, useEffect, useMemo, useState } from "react";
import { apiJson } from "./api";
import {
  clearChapterCodeDraft,
  loadChapterCodeDraft,
  saveChapterCodeDraft,
} from "./chapterDraftStorage";
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

/** 进入章时把本地草稿与题目 starter 合并（缺省用 starter） */
function mergeDraftWithStarters(
  draft: Record<string, string> | null,
  blocks: Block[],
): Record<string, string> {
  const m: Record<string, string> = {};
  for (const b of blocks) {
    const g = b.guideCell;
    const ex = b.extensionCell;
    m[g.id] = draft && draft[g.id] !== undefined ? draft[g.id]! : g.starterCode;
    m[ex.id] =
      draft && draft[ex.id] !== undefined
        ? draft[ex.id]!
        : (ex.starterCode ?? "");
  }
  return m;
}

function isPublishedV1(x: unknown): x is PublishedV1 {
  if (!x || typeof x !== "object") {
    return false;
  }
  const o = x as { version?: unknown; blocks?: unknown };
  return o.version === 1 && Array.isArray(o.blocks);
}

type Props = {
  /** 与 localStorage 草稿隔离，须与 /v1/student/me 的 studentId 一致 */
  studentId: string;
  chapterId: string;
  title: string;
  publishedContent: unknown;
  /** GET 章时服务端是否已有完成记录；用于再次进入时直接提示，勿再提交 */
  initialChapterCompleted?: boolean;
};

const REPEAT_CHAPTER_SUBMIT_MSG =
  "你已经完成了本章节练习提交，请勿重复提交。";

type CellKind = "guide" | "extension";

/** 运行结果区：纯展示；消息栏与判分逻辑分离 */
type FeedbackKind =
  | "idle"
  | "syntax_error"
  | "logic_fail"
  | "pass"
  | "network"
  | "already_passed";

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
  if (s.feedbackKind === "already_passed") {
    return { kind: "already_passed", showMsg: true };
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
  if (kind === "already_passed") {
    return (
      <div className="jnb-msg jnb-msg--warn" role="status">
        <div className="jnb-msg-label">提示</div>
        <div className="jnb-msg-body">你已经完成了该题，请勿重复提交。修改代码后可再次执行以重新验证。</div>
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
        <div className="jnb-msg-body">未做对：程序能运行，但输出与题目要求不符。上方为本次运行结果；可对照下方判定标准与标准答案参考修改，再点「执行」。
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

/** 解析 POST /complete 失败时的 `apiJson` 抛错（含 JSON body 字符串）。 */
function parseChapterCompleteError(err: unknown): string {
  const raw = err instanceof Error ? err.message : String(err);
  try {
    const o = JSON.parse(raw) as { detail?: unknown };
    if (o.detail === "cells_not_all_passing") {
      return "还有题目未通过。请完成本页各题并通过判定后再点击提交。";
    }
  } catch {
    /* 非 JSON */
  }
  if (raw.includes("cells_not_all_passing")) {
    return "还有题目未通过。请完成本页各题并通过判定后再点击提交。";
  }
  return "提交未成功。请检查网络后重试。";
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
  studentId,
  chapterId,
  title,
  data,
  initialChapterCompleted = false,
}: {
  studentId: string;
  chapterId: string;
  title: string;
  data: PublishedV1;
  initialChapterCompleted?: boolean;
}) {
  const [codeMap, setCodeMap] = useState<Record<string, string>>({});
  const [cellState, setCellState] = useState<Record<string, CellState>>({});
  const [saveHint, setSaveHint] = useState<string | null>(null);
  /** 本章是否已不能再次提交（服务端已有记录，或本页已成功提交过） */
  const [chapterSubmitDone, setChapterSubmitDone] = useState(
    initialChapterCompleted,
  );
  /** 仅当接口 200 成功时显示（jnb-footer-msg） */
  const [completeSuccessText, setCompleteSuccessText] = useState<string | null>(
    () => (initialChapterCompleted ? REPEAT_CHAPTER_SUBMIT_MSG : null),
  );
  const [completeErrorText, setCompleteErrorText] = useState<string | null>(
    null,
  );
  const [completing, setCompleting] = useState(false);
  const [activeCellId, setActiveCellId] = useState<string | null>(null);

  useEffect(() => {
    setChapterSubmitDone(!!initialChapterCompleted);
    setCompleteErrorText(null);
    if (initialChapterCompleted) {
      setCompleteSuccessText(REPEAT_CHAPTER_SUBMIT_MSG);
    } else {
      setCompleteSuccessText(null);
    }
  }, [chapterId, initialChapterCompleted]);

  const setCode = (id: string, v: string) => {
    setCodeMap((m) => ({ ...m, [id]: v }));
    setCellState((s) => {
      const cur = s[id];
      if (!cur || cur.passed !== true) {
        return s;
      }
      return {
        ...s,
        [id]: {
          ...cur,
          passed: null,
          feedbackKind: "idle",
        },
      };
    });
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

  const buildCodeMapSnapshot = useCallback((): Record<string, string> => {
    const m: Record<string, string> = {};
    for (const b of data.blocks) {
      const g = b.guideCell;
      const ex = b.extensionCell;
      m[g.id] = codeMap[g.id] !== undefined ? codeMap[g.id]! : g.starterCode;
      m[ex.id] =
        codeMap[ex.id] !== undefined
          ? codeMap[ex.id]!
          : (ex.starterCode ?? "");
    }
    return m;
  }, [data.blocks, codeMap]);

  const blocksStructureKey = useMemo(
    () => data.blocks.map((b) => b.id).join(","),
    [data.blocks],
  );

  useEffect(() => {
    const draft = loadChapterCodeDraft(studentId, chapterId);
    setCodeMap(mergeDraftWithStarters(draft, data.blocks));
  }, [studentId, chapterId, blocksStructureKey, data.blocks]);

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
    if (cellState[id]?.passed === true) {
      setCellState((s) => ({
        ...s,
        [id]: {
          passed: true,
          loading: false,
          lastMsg: null,
          lastRun: s[id]?.lastRun ?? null,
          feedbackKind: "already_passed",
        },
      }));
      setCompleteSuccessText(null);
      setCompleteErrorText(null);
      setActiveCellId(id);
      return;
    }
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
    setCompleteSuccessText(null);
    setCompleteErrorText(null);
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

  const onSaveDraft = () => {
    setSaveHint(null);
    try {
      saveChapterCodeDraft(studentId, chapterId, buildCodeMapSnapshot());
      setSaveHint("已保存。下次进入本章可继续编辑。");
    } catch {
      setSaveHint("保存未成功。请重试或检查本机存储是否已满。");
    }
  };

  const onComplete = async () => {
    if (chapterSubmitDone) {
      setCompleteSuccessText(REPEAT_CHAPTER_SUBMIT_MSG);
      setCompleteErrorText(null);
      return;
    }
    setCompleting(true);
    setSaveHint(null);
    setCompleteSuccessText(null);
    setCompleteErrorText(null);
    try {
      const r = await apiJson<{ ok?: boolean; alreadyCompleted?: boolean }>(
        `/v1/student/chapters/${chapterId}/complete`,
        { method: "POST" },
      );
      setChapterSubmitDone(true);
      if (r.alreadyCompleted === true) {
        setCompleteSuccessText(REPEAT_CHAPTER_SUBMIT_MSG);
      } else {
        clearChapterCodeDraft(studentId, chapterId);
        setCompleteSuccessText("本章已标记完成");
      }
    } catch (e) {
      setCompleteErrorText(parseChapterCompleteError(e));
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
                    ? "执行中…"
                    : "执行"}
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
                    ? "执行中…"
                    : "执行"}
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
          <div className="jnb-footer-row">
            <button
              type="button"
              className="jnb-btn-secondary"
              onClick={onSaveDraft}
            >
              保存
            </button>
            <button
              type="button"
              onClick={() => void onComplete()}
              disabled={completing}
            >
              {completing ? "提交中…" : "提交本章练习"}
            </button>
          </div>
          {saveHint ? <p className="jnb-footer-hintline">{saveHint}</p> : null}
          {completeSuccessText ? (
            <p className="jnb-footer-msg">{completeSuccessText}</p>
          ) : null}
          {completeErrorText ? (
            <p className="jnb-footer-err" role="alert">
              {completeErrorText}
            </p>
          ) : null}
        </div>
      </div>
      <StudentChat chapterId={chapterId} getContext={getChatContext} />
    </div>
  );
}

export function ChapterPractice({
  studentId,
  chapterId,
  title,
  publishedContent,
  initialChapterCompleted = false,
}: Props) {
  if (!isPublishedV1(publishedContent)) {
    return (
      <p className="sd-muted">本章尚无有效的 publishedContent（需要 version: 1 与 blocks）。</p>
    );
  }
  return (
    <ChapterPracticeInner
      studentId={studentId}
      chapterId={chapterId}
      title={title}
      data={publishedContent}
      initialChapterCompleted={initialChapterCompleted}
    />
  );
}
