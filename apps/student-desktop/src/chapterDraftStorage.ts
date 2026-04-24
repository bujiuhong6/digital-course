/**
 * 将学生在某章中各格代码草稿存于 localStorage，键按学生 id 与章 id 隔离。
 */

const PREFIX = "student-chapter-code-v1:";

function key(studentId: string, chapterId: string): string {
  return `${PREFIX}${studentId}:${chapterId}`;
}

export function loadChapterCodeDraft(
  studentId: string,
  chapterId: string,
): Record<string, string> | null {
  try {
    const raw = localStorage.getItem(key(studentId, chapterId));
    if (!raw) {
      return null;
    }
    const o = JSON.parse(raw) as unknown;
    if (!o || typeof o !== "object") {
      return null;
    }
    const out: Record<string, string> = {};
    for (const [k, v] of Object.entries(o as Record<string, unknown>)) {
      if (typeof v === "string") {
        out[k] = v;
      }
    }
    return out;
  } catch {
    return null;
  }
}

export function saveChapterCodeDraft(
  studentId: string,
  chapterId: string,
  codeByCellId: Record<string, string>,
): void {
  localStorage.setItem(key(studentId, chapterId), JSON.stringify(codeByCellId));
}

export function clearChapterCodeDraft(studentId: string, chapterId: string): void {
  localStorage.removeItem(key(studentId, chapterId));
}

/** 有任意非空（trim 后）代码片段，用于列表显示「练习中」 */
export function hasMeaningfulCodeDraft(
  studentId: string,
  chapterId: string,
): boolean {
  const m = loadChapterCodeDraft(studentId, chapterId);
  if (!m) {
    return false;
  }
  return Object.values(m).some((v) => v.trim() !== "");
}
