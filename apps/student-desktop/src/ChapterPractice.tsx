import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type MutableRefObject,
} from "react";
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

const SESSION_SUBMIT_KEY_PREFIX = "sd-chap-submit-v1-";

function submitStorageKey(studentId: string, chapterId: string): string {
  return `${SESSION_SUBMIT_KEY_PREFIX}${studentId}-${chapterId}`;
}

function readSessionSubmitDone(studentId: string, chapterId: string): boolean {
  const k = submitStorageKey(studentId, chapterId);
  try {
    if (typeof sessionStorage !== "undefined") {
      if (sessionStorage.getItem(k) === "1") {
        return true;
      }
    }
  } catch {
    /* ignore */
  }
  try {
    if (typeof localStorage !== "undefined") {
      if (localStorage.getItem(k) === "1") {
        return true;
      }
    }
  } catch {
    /* ignore */
  }
  return false;
}

function writeSessionSubmitDone(studentId: string, chapterId: string) {
  const k = submitStorageKey(studentId, chapterId);
  try {
    if (typeof sessionStorage !== "undefined") {
      sessionStorage.setItem(k, "1");
    }
  } catch {
    /* ignore */
  }
  try {
    if (typeof localStorage !== "undefined") {
      localStorage.setItem(k, "1");
    }
  } catch {
    /* ignore */
  }
}

function clearSessionSubmitDone(studentId: string, chapterId: string) {
  const k = submitStorageKey(studentId, chapterId);
  try {
    if (typeof sessionStorage !== "undefined") {
      sessionStorage.removeItem(k);
    }
  } catch {
    /* ignore */
  }
  try {
    if (typeof localStorage !== "undefined") {
      localStorage.removeItem(k);
    }
  } catch {
    /* ignore */
  }
}

type PassRule = {
  mode: string;
  expectedSubstring?: string;
  assertCode?: string;
};

type GuideCell = {
  id: string;
  starterCode: string;
  /** 运行前自动拼接的隐藏准备代码，用于预加载数据等公共上下文。 */
  setupCode?: string | null;
  description: string;
  /** 服务端判分用；学生端不展示 */
  passRule?: PassRule;
  exerciseTitle?: string | null;
  expectedOutput?: string | null;
  expectedImageDataUrl?: string | null;
  expectedImageAlt?: string | null;
  /** 学生 API 不返回，保留类型便于本地/内嵌 */
  referenceAnswer?: string | null;
  codeBackdropLabel?: string | null;
  codeBackdropCode?: string | null;
};

type ExtensionCell = {
  id: string;
  promptHtml: string;
  starterCode: string | null;
  /** 运行前自动拼接的隐藏准备代码，用于预加载数据等公共上下文。 */
  setupCode?: string | null;
  passRule?: PassRule;
  exerciseTitle?: string | null;
  expectedOutput?: string | null;
  expectedImageDataUrl?: string | null;
  expectedImageAlt?: string | null;
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
  /**
   * 为 true 时始终显示作图区；为 false 时始终不显示；缺省由启发式
   *（仅代码/参考答案字段，不用章首或题面说明长文）决定。
   */
  requiresMatplotlibOutput?: boolean | null;
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

/**
 * 基础练习底纹为 `position:absolute`，父框高度由下方 textarea 决定；按红字+灰字行数
 * 拉高输入区，避免多行参考代码溢出带边框区域。
 */
function guideTextareaRowsForBackdrop(g: GuideCell): number {
  const label = (g.codeBackdropLabel ?? "").trim();
  const code = (g.codeBackdropCode ?? "").trim();
  if (!label && !code) {
    return 5;
  }
  const labelLines = label ? label.split("\n").length : 0;
  const codeLines = code ? code.split("\n").length : 0;
  return Math.min(30, Math.max(8, labelLines + codeLines + 4));
}

function exerciseNumberLabel(index: number): string {
  return `第${index}题`;
}

function exerciseTitleWithoutLeadingLabel(
  title: string | null | undefined,
  label: string,
): string {
  const t = (title ?? "").trim();
  if (!t) {
    return "";
  }
  const normalizedTitle = t.replace(/\s+/g, "");
  const normalizedLabel = label.replace(/\s+/g, "");
  if (normalizedTitle === normalizedLabel) {
    return "";
  }
  if (!normalizedTitle.startsWith(normalizedLabel)) {
    return t;
  }
  const labelChars = normalizedLabel.length;
  let seen = 0;
  let cut = 0;
  for (const ch of t) {
    cut += ch.length;
    if (/\s/.test(ch)) {
      continue;
    }
    seen += 1;
    if (seen >= labelChars) {
      break;
    }
  }
  return t
    .slice(cut)
    .replace(/^[\s:：、\-－—]+/, "")
    .replace(/^[(（]\s*(基础|扩展)\s*[)）]\s*/, "")
    .trim();
}

function isPublishedV1(x: unknown): x is PublishedV1 {
  if (!x || typeof x !== "object") {
    return false;
  }
  const o = x as { version?: unknown; blocks?: unknown };
  return o.version === 1 && Array.isArray(o.blocks);
}

/** 与题目/代码中是否出现作图相关关键字匹配（不执行代码，仅作 UI 显隐） */
const MPL_TEXT_HINT =
  /matplotlib|pyplot|pylab|from\s+matplotlib|import\s+matplotlib|\bplt\.|wordcloud|WordCloud|from\s+wordcloud|import\s+wordcloud/i;

function textSuggestsMatplotlib(s: string | null | undefined): boolean {
  if (s == null || !String(s).trim()) {
    return false;
  }
  return MPL_TEXT_HINT.test(s);
}

function buildRunnableCode(
  cell: GuideCell | ExtensionCell,
  visibleCode: string,
): string {
  const setup = cell.setupCode?.trimEnd();
  if (!setup) {
    return visibleCode;
  }
  return `${setup}\n\n${visibleCode}`;
}

/**
 * 发布内容与各格**代码类**内容是否可能用到 matplotlib/wordcloud（作图区显隐，不执行代码）。
 * 不扫描 `chapterIntroHtml` / `knowledgeHtml` / `description` / `promptHtml` /
 * `expectedOutput`，避免课件泛述「预装 … matplotlib」时误开作图区。
 * 需要强制显示时在发布 JSON 根上设 `requiresMatplotlibOutput: true`。
 */
function chapterSuggestsMatplotlib(
  data: PublishedV1,
  codeMap: Record<string, string>,
): boolean {
  for (const v of Object.values(codeMap)) {
    if (textSuggestsMatplotlib(v)) {
      return true;
    }
  }
  for (const b of data.blocks) {
    const g = b.guideCell;
    if (
      textSuggestsMatplotlib(g.setupCode) ||
      textSuggestsMatplotlib(g.starterCode) ||
      textSuggestsMatplotlib(g.codeBackdropCode)
    ) {
      return true;
    }
    const ex = b.extensionCell;
    if (
      textSuggestsMatplotlib(ex.setupCode) ||
      textSuggestsMatplotlib(ex.starterCode)
    ) {
      return true;
    }
  }
  return false;
}

function cellSuggestsMatplotlib(
  cell: GuideCell | ExtensionCell,
  visibleCode: string,
): boolean {
  return (
    textSuggestsMatplotlib(cell.setupCode) ||
    textSuggestsMatplotlib(visibleCode) ||
    textSuggestsMatplotlib(cell.starterCode) ||
    textSuggestsMatplotlib(
      "codeBackdropCode" in cell ? cell.codeBackdropCode : null,
    ) ||
    Boolean(cell.expectedImageDataUrl)
  );
}

function MatplotlibOutputBlock({
  cellId,
  mountRefs,
}: {
  cellId: string;
  mountRefs: MutableRefObject<Record<string, HTMLDivElement | null>>;
}) {
  return (
    <div className="sd-mpl-wrap sd-mpl-wrap--cell" aria-label="图形输出">
      <div className="sd-mpl-label">图形输出</div>
      <p className="sd-mpl-hint">
        使用 <code>matplotlib</code> 或 <code>wordcloud</code> 作图后请调用{" "}
        <code>plt.show()</code>，图形将显示在这里。每次执行会清空上一张图。
      </p>
      <div
        id={`sd-mpl-cell-${cellId}`}
        ref={(el) => {
          mountRefs.current[cellId] = el;
        }}
        className="sd-mpl-target"
      />
    </div>
  );
}

type Props = {
  /** 与 localStorage 草稿隔离，须与 /v1/student/me 的 studentId 一致 */
  studentId: string;
  chapterId: string;
  title: string;
  publishedContent: unknown;
  /** GET 章时服务端是否已有完成记录；用于再次进入时直接提示，勿再提交 */
  initialChapterCompleted?: boolean;
  /**
   * 为 true 时展示 `extensionCell.referenceAnswer`（如教师内嵌学生组件调试）。
   * 学生端须为 false。GET /v1/student/… 已剥除 `referenceAnswer`，此开关为内嵌/本地二道展示控制。
   */
  showExtensionReference?: boolean;
  /** GET 章时库中本学生已通过判分的 cellId，与提交条件对齐 */
  initialCellsPassed?: string[];
  /** 与页顶「← 返回列表」一致；在页底再提供一次，便于长章滚动后返回 */
  onBackToList?: () => void;
};

const REPEAT_CHAPTER_SUBMIT_MSG =
  "你已经完成了本章节练习提交，请勿重复提交。";

const CHAPTER_SUBMITTED_RUN_MSG =
  "该章节练习已经提交，请勿重复执行或重做。如需重新练习，请先取消提交。";

const CELL_PASSED_NO_REDO_MSG =
  "本题已通过并记录，请勿重复执行或重做。";

type CellKind = "guide" | "extension";

/** 运行结果区：纯展示；消息栏与判分逻辑分离 */
type FeedbackKind =
  | "idle"
  | "syntax_error"
  | "logic_fail"
  | "pass"
  | "network"
  | "already_passed"
  | "chapter_submitted";

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

/** Matplotlib 在浏览器里首次导入时常见，对学生无诊断价值。 */
function filterStderrForDisplay(stderr: string): string {
  return stderr
    .split(/\r?\n/)
    .filter(
      (line) =>
        !/matplotlib is building the font cache/i.test(line.trim()),
    )
    .join("\n")
    .trimEnd();
}

function formatRunForDisplay(r: RunResult): string {
  if (!r.runOk) {
    const parts: string[] = [];
    if (r.fullError) {
      parts.push(r.fullError);
    } else if (r.errorExcerpt) {
      parts.push(r.errorExcerpt);
    }
    const stderrShow = filterStderrForDisplay(r.stderr || "");
    if (stderrShow) {
      parts.push(`[stderr]\n${stderrShow}`);
    }
    if (r.stdout) {
      parts.push(`[stdout]\n${r.stdout}`);
    }
    return parts.length > 0 ? parts.join("\n\n") : "运行未成功（无详细消息）。";
  }
  const o = (r.stdout || "").trimEnd();
  const e = filterStderrForDisplay(r.stderr || "");
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
  if (s.feedbackKind === "chapter_submitted") {
    return { kind: "chapter_submitted", showMsg: true };
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
  if (kind === "chapter_submitted") {
    return (
      <div className="jnb-msg jnb-msg--warn" role="status">
        <div className="jnb-msg-label">提示</div>
        <div className="jnb-msg-body">{CHAPTER_SUBMITTED_RUN_MSG}</div>
      </div>
    );
  }
  if (kind === "already_passed") {
    return (
      <div className="jnb-msg jnb-msg--warn" role="status">
        <div className="jnb-msg-label">提示</div>
        <div className="jnb-msg-body">{CELL_PASSED_NO_REDO_MSG}</div>
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
        <div className="jnb-msg-body">
          未做对：程序能运行，但输出与题目要求不符。上方为本次运行结果；可对照题目期望输出与标准答案参考修改，再点「执行」。
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
      return "还有题目未通过。请完成本页全部题目后再点击提交。";
    }
  } catch {
    /* 非 JSON */
  }
  if (raw.includes("cells_not_all_passing")) {
    return "还有题目未通过。请完成本页全部题目后再点击提交。";
  }
  return "提交未成功。请检查网络后重试。";
}

function RunOutputBlock({
  run,
  emptyMessage,
}: {
  run: RunResult | null | undefined;
  emptyMessage?: string;
}) {
  if (!run) {
    return (
      <div className="jnb-out jnb-out--empty">
        <div className="jnb-out-label">运行结果</div>
        <p className="jnb-out-empty">
          {emptyMessage ?? "运行后在此显示标准输出或 Python 报错。"}
        </p>
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
  showExtensionReference = false,
  initialCellsPassed: initialCellsPassedProp = [],
  onBackToList,
}: {
  studentId: string;
  chapterId: string;
  title: string;
  data: PublishedV1;
  initialChapterCompleted?: boolean;
  showExtensionReference?: boolean;
  initialCellsPassed?: string[];
  onBackToList?: () => void;
}) {
  const [codeMap, setCodeMap] = useState<Record<string, string>>({});
  const [cellState, setCellState] = useState<Record<string, CellState>>({});
  const initialCellsPassed = initialCellsPassedProp ?? [];
  const initialPassedSet = useMemo(
    () => new Set(initialCellsPassed),
    [initialCellsPassed],
  );
  const initialPassedSetRef = useRef(initialPassedSet);
  useEffect(() => {
    initialPassedSetRef.current = new Set(initialCellsPassed);
  }, [initialCellsPassed]);
  const [saveHint, setSaveHint] = useState<string | null>(null);
  /** 本章是否已不能再次提交（服务端已有记录，或本页已成功提交过） */
  const [chapterSubmitDone, setChapterSubmitDone] = useState(() => {
    if (initialChapterCompleted) {
      return true;
    }
    return readSessionSubmitDone(studentId, chapterId);
  });
  /** 仅当接口 200 成功时显示（jnb-footer-msg） */
  const [completeSuccessText, setCompleteSuccessText] = useState<string | null>(
    () => {
      if (initialChapterCompleted) {
        return REPEAT_CHAPTER_SUBMIT_MSG;
      }
      if (readSessionSubmitDone(studentId, chapterId)) {
        return "本章已标记完成";
      }
      return null;
    },
  );
  const [completeErrorText, setCompleteErrorText] = useState<string | null>(
    null,
  );
  const [completing, setCompleting] = useState(false);
  const [withdrawing, setWithdrawing] = useState(false);
  const [activeCellId, setActiveCellId] = useState<string | null>(null);
  /** 基础题底纹提示：代码框聚焦后隐藏，让学生凭记忆输入。 */
  const [codeFocusId, setCodeFocusId] = useState<string | null>(null);
  /** matplotlib_pyodide 作图父节点；每题各有一个输出容器，执行时使用当前题容器。 */
  const mplMountRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const lastChapterIdForSyncRef = useRef<string | null>(null);

  const isChapterSubmitted =
    chapterSubmitDone || readSessionSubmitDone(studentId, chapterId);

  useEffect(() => {
    if (readSessionSubmitDone(studentId, chapterId) && !chapterSubmitDone) {
      setChapterSubmitDone(true);
    }
  }, [chapterId, studentId, chapterSubmitDone]);

  useEffect(() => {
    setCompleteErrorText(null);
    const prev = lastChapterIdForSyncRef.current;
    const chapterSwitched = prev != null && prev !== chapterId;
    if (chapterSwitched) {
      lastChapterIdForSyncRef.current = chapterId;
      const done =
        initialChapterCompleted || readSessionSubmitDone(studentId, chapterId);
      setChapterSubmitDone(done);
      if (initialChapterCompleted) {
        setCompleteSuccessText(REPEAT_CHAPTER_SUBMIT_MSG);
      } else if (readSessionSubmitDone(studentId, chapterId)) {
        setCompleteSuccessText("本章已标记完成");
      } else {
        setCompleteSuccessText(null);
      }
      return;
    }
    lastChapterIdForSyncRef.current = chapterId;
    if (initialChapterCompleted) {
      setChapterSubmitDone(true);
      setCompleteSuccessText(REPEAT_CHAPTER_SUBMIT_MSG);
    }
  }, [chapterId, initialChapterCompleted, studentId]);

  const setCode = (id: string, v: string) => {
    setCodeMap((m) => ({ ...m, [id]: v }));
    setCellState((s) => {
      const cur = s[id];
      if (cur?.passed === true) {
        return {
          ...s,
          [id]: {
            ...cur,
            passed: null,
            feedbackKind: "idle",
          },
        };
      }
      if (!cur && initialPassedSetRef.current.has(id)) {
        return {
          ...s,
          [id]: {
            passed: null,
            loading: false,
            lastMsg: null,
            lastRun: null,
            feedbackKind: "idle",
          },
        };
      }
      return s;
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

  const requiredCellIds = useMemo(
    () =>
      data.blocks.flatMap((b) => [b.guideCell.id, b.extensionCell.id]),
    [data.blocks],
  );

  const allCellsPassing = useMemo(() => {
    if (requiredCellIds.length === 0) {
      return false;
    }
    return requiredCellIds.every((id) => {
      const s = cellState[id];
      if (s) {
        return s.passed === true;
      }
      return initialPassedSet.has(id);
    });
  }, [requiredCellIds, cellState, initialPassedSet]);

  const pendingExerciseLabels = useCallback((): string[] => {
    const labels: string[] = [];
    data.blocks.forEach((b, blockIndex) => {
      const cells: Array<{
        id: string;
        label: string;
      }> = [
        {
          id: b.guideCell.id,
          label: exerciseNumberLabel(blockIndex * 2 + 1),
        },
        {
          id: b.extensionCell.id,
          label: exerciseNumberLabel(blockIndex * 2 + 2),
        },
      ];
      for (const cell of cells) {
        const s = cellState[cell.id];
        const passed = s ? s.passed === true : initialPassedSet.has(cell.id);
        if (!passed) {
          labels.push(cell.label);
        }
      }
    });
    return labels;
  }, [data.blocks, cellState, initialPassedSet]);

  const resetCellToStarter = useCallback(
    async (kind: CellKind, cell: GuideCell | ExtensionCell) => {
      const id = cell.id;
      const submitted =
        chapterSubmitDone || readSessionSubmitDone(studentId, chapterId);
      const cellAlreadyPassed =
        cellState[id]?.passed === true || initialPassedSet.has(id);
      if (submitted) {
        if (!chapterSubmitDone) {
          setChapterSubmitDone(true);
        }
        setCellState((s) => ({
          ...s,
          [cell.id]: {
            passed: s[cell.id]?.passed ?? null,
            loading: false,
            lastMsg: null,
            lastRun: s[cell.id]?.lastRun ?? null,
            feedbackKind: "chapter_submitted",
          },
        }));
        setActiveCellId(cell.id);
        setCompleteErrorText(null);
        setSaveHint(
          "本章练习已提交，该题在系统中已计为通过。若要清空代码重做，请先点下方「取消提交」。",
        );
        return;
      }
      if (cellAlreadyPassed) {
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
        setActiveCellId(id);
        setCompleteErrorText(null);
        setSaveHint("本题已通过并记录，请勿重复重做。");
        return;
      }
      if (cellState[id]?.loading) {
        return;
      }
      const starter =
        kind === "extension"
          ? (cell as ExtensionCell).starterCode ?? ""
          : (cell as GuideCell).starterCode;
      setCodeMap((m) => {
        const next = { ...m, [id]: starter };
        const full: Record<string, string> = {};
        for (const b of data.blocks) {
          const g = b.guideCell;
          const ex = b.extensionCell;
          full[g.id] = next[g.id] !== undefined ? next[g.id]! : g.starterCode;
          full[ex.id] =
            next[ex.id] !== undefined ? next[ex.id]! : (ex.starterCode ?? "");
        }
        queueMicrotask(() => {
          try {
            saveChapterCodeDraft(studentId, chapterId, full);
          } catch {
            /* ignore */
          }
        });
        return next;
      });
      setCellState((s) => ({
        ...s,
        [id]: {
          passed: null,
          loading: false,
          lastMsg: null,
          lastRun: null,
          feedbackKind: "idle",
        },
      }));
      try {
        await apiJson<{ ok: boolean; passed: boolean }>(
          "/v1/student/cells/verify",
          {
            method: "POST",
            body: JSON.stringify({
              chapterId,
              cellId: id,
              runOk: false,
              stdout: "",
              stderr: null,
              errorExcerpt: null,
              elapsedMs: 0,
            }),
          },
        );
      } catch {
        /* 网络失败时本地已回到初始，请学生重试执行 */
      }
    },
    [
      chapterSubmitDone,
      cellState,
      data.blocks,
      initialPassedSet,
      studentId,
      chapterId,
    ],
  );

  const blocksStructureKey = useMemo(
    () => data.blocks.map((b) => b.id).join(","),
    [data.blocks],
  );

  const showMatplotlibOutput = useMemo(() => {
    const flag = data.requiresMatplotlibOutput;
    if (flag === true) {
      return true;
    }
    if (flag === false) {
      return false;
    }
    return chapterSuggestsMatplotlib(data, codeMap);
  }, [data, codeMap]);

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
    if (
      chapterSubmitDone || readSessionSubmitDone(studentId, chapterId)
    ) {
      if (!chapterSubmitDone) {
        setChapterSubmitDone(true);
      }
      setCellState((s) => ({
        ...s,
        [id]: {
          passed: s[id]?.passed ?? null,
          loading: false,
          lastMsg: null,
          lastRun: s[id]?.lastRun ?? null,
          feedbackKind: "chapter_submitted",
        },
      }));
      setActiveCellId(id);
      return;
    }
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
    const code = buildRunnableCode(cell, getCode(kind, cell));
    let run: Awaited<ReturnType<typeof runPythonInPyodide>>;
    try {
      await ensurePyodide();
      run = await runPythonInPyodide(code, {
        mplMount: showMatplotlibOutput
          ? mplMountRefs.current[id]
          : undefined,
      });
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
    if (isChapterSubmitted) {
      setCompleteSuccessText(REPEAT_CHAPTER_SUBMIT_MSG);
      setCompleteErrorText(null);
      return;
    }
    const pending = pendingExerciseLabels();
    if (pending.length > 0) {
      const msg = `还有这些题目没有完成：${pending.join("、")}。请先完成并执行通过后再提交。`;
      setCompleteSuccessText(null);
      setCompleteErrorText(msg);
      try {
        window.alert(msg);
      } catch {
        /* ignore */
      }
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
      writeSessionSubmitDone(studentId, chapterId);
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

  const onUncomplete = async () => {
    if (!isChapterSubmitted || withdrawing || completing) {
      return;
    }
    if (
      !window.confirm(
        "确定取消提交？撤回后教师端将不再将本章记为你已提交，你可重新编辑并再次提交。",
      )
    ) {
      return;
    }
    setWithdrawing(true);
    setSaveHint(null);
    setCompleteErrorText(null);
    try {
      const r = await apiJson<{
        ok?: boolean;
        withdrawn?: boolean;
        detail?: string;
      }>(`/v1/student/chapters/${chapterId}/uncomplete`, { method: "POST" });
      if (r.ok === true && r.withdrawn === true) {
        setChapterSubmitDone(false);
        clearSessionSubmitDone(studentId, chapterId);
        setCompleteSuccessText(null);
        setCellState((s) => {
          const next = { ...s };
          for (const k of Object.keys(next)) {
            const v = next[k];
            if (v?.feedbackKind === "chapter_submitted") {
              next[k] = {
                ...v,
                feedbackKind: "idle",
              };
            }
          }
          return next;
        });
      } else {
        setCompleteErrorText("当前没有可撤回的提交记录。");
      }
    } catch (e) {
      const em = e instanceof Error ? e.message : String(e);
      setCompleteErrorText(em || "取消提交未成功，请稍后重试。");
    } finally {
      setWithdrawing(false);
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
          const gCell = b.guideCell;
          const eCell = b.extensionCell;
          const guideLabel = exerciseNumberLabel(bi * 2 + 1);
          const extensionLabel = exerciseNumberLabel(bi * 2 + 2);
          const gTitle =
            exerciseTitleWithoutLeadingLabel(
              gCell.exerciseTitle,
              guideLabel,
            ) || "基础练习";
          const eTitle =
            exerciseTitleWithoutLeadingLabel(
              eCell.exerciseTitle,
              extensionLabel,
            ) || "扩展练习";
          const guideState = cellState[gCell.id];
          const extensionState = cellState[eCell.id];
          const guideFeedback = effectiveFeedback(guideState);
          const extensionFeedback = effectiveFeedback(extensionState);
          const guideEmptyMessage =
            guideFeedback.kind === "chapter_submitted"
              ? CHAPTER_SUBMITTED_RUN_MSG
              : guideFeedback.kind === "already_passed"
                ? CELL_PASSED_NO_REDO_MSG
              : undefined;
          const extensionEmptyMessage =
            extensionFeedback.kind === "chapter_submitted"
              ? CHAPTER_SUBMITTED_RUN_MSG
              : extensionFeedback.kind === "already_passed"
                ? CELL_PASSED_NO_REDO_MSG
              : undefined;
          const guideCodeStr = getCode("guide", gCell);
          const extensionCodeStr = getCode("extension", eCell);
          const guideShowsMatplotlib =
            showMatplotlibOutput && cellSuggestsMatplotlib(gCell, guideCodeStr);
          const extensionShowsMatplotlib =
            showMatplotlibOutput &&
            cellSuggestsMatplotlib(eCell, extensionCodeStr);
          const hasGuideBackdrop =
            Boolean(gCell.codeBackdropLabel?.trim()) ||
            Boolean((gCell.codeBackdropCode ?? "").trim());
          const showGuideBackdrop =
            hasGuideBackdrop &&
            guideCodeStr === "" &&
            codeFocusId !== gCell.id;
          return (
            <div key={b.id} className="jnb-kp">
              <h2 className="jnb-h2">{sec}</h2>
              {b.knowledgeHtml
                ? htmlMd(b.knowledgeHtml, `${b.id}-kp`)
                : null}

              <h3 className="jnb-h3">基础练习</h3>
              <h4 className="jnb-h4 jnb-exercise-title">
                <span className="jnb-exercise-no">{guideLabel}</span>
                <span>{gTitle}</span>
              </h4>
              {htmlMd(b.guideCell.description, `${b.id}-gdesc`)}
              {b.guideCell.expectedOutput || b.guideCell.expectedImageDataUrl ? (
                <div className="jnb-expected">
                  <div className="jnb-expected-h">题目期望的输出或结果</div>
                  {b.guideCell.expectedOutput ? (
                    <div className="jnb-expected-body">
                      {b.guideCell.expectedOutput}
                    </div>
                  ) : null}
                  {b.guideCell.expectedImageDataUrl ? (
                    <img
                      className="jnb-expected-img"
                      src={b.guideCell.expectedImageDataUrl}
                      alt={b.guideCell.expectedImageAlt || "基础题参考图"}
                    />
                  ) : null}
                </div>
              ) : null}
              <div className="jnb-code-row">
                <span className="jnb-prompt jnb-prompt--code">代码</span>
                <div
                  className={
                    showGuideBackdrop
                      ? "jnb-code-col jnb-code-col--backdrop"
                      : "jnb-code-col"
                  }
                >
                  {showGuideBackdrop ? (
                    <div className="jnb-code-backdrop" aria-hidden="true">
                      {gCell.codeBackdropLabel?.trim() ? (
                        <div className="jnb-code-backdrop-label">
                          {gCell.codeBackdropLabel}
                        </div>
                      ) : null}
                      {(gCell.codeBackdropCode ?? "").trim() ? (
                        <pre className="jnb-code-backdrop-code">
                          {gCell.codeBackdropCode}
                        </pre>
                      ) : null}
                    </div>
                  ) : null}
                  <textarea
                    className={
                      showGuideBackdrop
                        ? "jnb-input jnb-input--backdrop-on"
                        : "jnb-input"
                    }
                    value={guideCodeStr}
                    onChange={(e) => setCode(gCell.id, e.target.value)}
                    onFocus={() => {
                      setActiveCellId(gCell.id);
                      setCodeFocusId(gCell.id);
                    }}
                    onBlur={() => setCodeFocusId(null)}
                    rows={
                      hasGuideBackdrop
                        ? guideTextareaRowsForBackdrop(gCell)
                        : 5
                    }
                    spellCheck={false}
                    autoComplete="off"
                    autoCorrect="off"
                    autoCapitalize="off"
                  />
                </div>
              </div>
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
                <button
                  type="button"
                  className="jnb-btn-secondary"
                  onClick={() => void resetCellToStarter("guide", b.guideCell)}
                  disabled={cellState[b.guideCell.id]?.loading}
                >
                  重做
                </button>
              </div>
              {guideState?.loading &&
              !guideState?.lastRun ? (
                <p className="jnb-pending">正在执行代码并上报结果…</p>
              ) : null}
              <RunOutputBlock
                run={guideState?.lastRun}
                emptyMessage={guideEmptyMessage}
              />
              {guideShowsMatplotlib ? (
                <MatplotlibOutputBlock
                  cellId={gCell.id}
                  mountRefs={mplMountRefs}
                />
              ) : null}
              <MessageBar
                {...guideFeedback}
                passedServer={guideState?.passed ?? null}
                text={guideState?.lastMsg}
              />

              <h3 className="jnb-h3 jnb-h3--ext">扩展练习</h3>
              <h4 className="jnb-h4 jnb-exercise-title">
                <span className="jnb-exercise-no">{extensionLabel}</span>
                <span>{eTitle}</span>
              </h4>
              {htmlMd(b.extensionCell.promptHtml || "<p></p>", `${b.id}-exq`)}
              {b.extensionCell.expectedOutput ||
              b.extensionCell.expectedImageDataUrl ? (
                <div className="jnb-expected">
                  <div className="jnb-expected-h">题目期望的输出或结果</div>
                  {b.extensionCell.expectedOutput ? (
                    <div className="jnb-expected-body">
                      {b.extensionCell.expectedOutput}
                    </div>
                  ) : null}
                  {b.extensionCell.expectedImageDataUrl ? (
                    <img
                      className="jnb-expected-img"
                      src={b.extensionCell.expectedImageDataUrl}
                      alt={b.extensionCell.expectedImageAlt || "扩展题参考图"}
                    />
                  ) : null}
                </div>
              ) : null}
              <div className="jnb-code-row">
                <span className="jnb-prompt jnb-prompt--code">代码</span>
                <div className="jnb-code-col">
                  <textarea
                    className="jnb-input"
                    value={extensionCodeStr}
                    onChange={(e) => setCode(eCell.id, e.target.value)}
                    onFocus={() => setActiveCellId(eCell.id)}
                    rows={6}
                    spellCheck={false}
                  />
                </div>
              </div>
              <div className="jnb-run-row jnb-run-row--top">
                <button
                  type="button"
                  onClick={() =>
                    void runAndVerify("extension", eCell)
                  }
                  disabled={extensionState?.loading}
                >
                  {extensionState?.loading
                    ? "执行中…"
                    : "执行"}
                </button>
                <button
                  type="button"
                  className="jnb-btn-secondary"
                  onClick={() =>
                    void resetCellToStarter("extension", eCell)
                  }
                  disabled={extensionState?.loading}
                >
                  重做
                </button>
              </div>
              {extensionState?.loading &&
              !extensionState?.lastRun ? (
                <p className="jnb-pending">正在执行代码并上报结果…</p>
              ) : null}
              <RunOutputBlock
                run={extensionState?.lastRun}
                emptyMessage={extensionEmptyMessage}
              />
              {extensionShowsMatplotlib ? (
                <MatplotlibOutputBlock
                  cellId={eCell.id}
                  mountRefs={mplMountRefs}
                />
              ) : null}
              <MessageBar
                {...extensionFeedback}
                passedServer={extensionState?.passed ?? null}
                text={extensionState?.lastMsg}
              />
              {showExtensionReference && b.extensionCell.referenceAnswer ? (
                <div className="jnb-ref">
                  <div className="jnb-ref-h">教师参考答案（扩展题）</div>
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
            <div className="jnb-footer-btns-main">
            <button
              type="button"
              className="jnb-btn-secondary"
              onClick={onSaveDraft}
            >
              保存
            </button>
            {isChapterSubmitted ? (
              <button
                type="button"
                className="jnb-btn-secondary"
                onClick={() => void onUncomplete()}
                disabled={withdrawing || completing}
              >
                {withdrawing ? "处理中…" : "取消提交"}
              </button>
            ) : null}
            <button
              type="button"
              onClick={() => void onComplete()}
              disabled={completing || isChapterSubmitted}
              title={
                isChapterSubmitted
                  ? undefined
                  : "点击后会检查本章每道题是否已执行通过"
              }
            >
              {completing ? "提交中…" : "提交本章练习"}
            </button>
            </div>
            {onBackToList ? (
              <button
                type="button"
                className="jnb-btn-secondary jnb-footer-back"
                onClick={onBackToList}
              >
                返回列表
              </button>
            ) : null}
          </div>
          {!isChapterSubmitted && !allCellsPassing ? (
            <p className="jnb-footer-hintline jnb-footer-hintline--sub">
              点击「提交本章练习」后会检查未完成题目，并提示题目编号。可用「重做」恢复本题初始代码与状态。
            </p>
          ) : null}
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
  showExtensionReference = false,
  initialCellsPassed = [],
  onBackToList,
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
      showExtensionReference={showExtensionReference}
      initialCellsPassed={initialCellsPassed}
      onBackToList={onBackToList}
    />
  );
}
