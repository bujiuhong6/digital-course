/**
 * 课后练习作答草稿（questionId → 单选 option id 或文本/代码），按学生 id 与练习 id 存 localStorage。
 */

const PREFIX = "sd-post-exercise-draft-v1:";

function key(studentId: string, exerciseId: string): string {
  return `${PREFIX}${studentId}:${exerciseId}`;
}

export function loadPostExerciseDraft(
  studentId: string,
  exerciseId: string,
): Record<string, string> | null {
  try {
    const raw = localStorage.getItem(key(studentId, exerciseId));
    if (!raw) return null;
    const o = JSON.parse(raw) as unknown;
    if (!o || typeof o !== "object") return null;
    const out: Record<string, string> = {};
    for (const [k, v] of Object.entries(o as Record<string, unknown>)) {
      if (typeof v === "string") out[k] = v;
    }
    return Object.keys(out).length ? out : null;
  } catch {
    return null;
  }
}

export function savePostExerciseDraft(
  studentId: string,
  exerciseId: string,
  answers: Record<string, string>,
): void {
  localStorage.setItem(key(studentId, exerciseId), JSON.stringify(answers));
}

export function clearPostExerciseDraft(studentId: string, exerciseId: string): void {
  localStorage.removeItem(key(studentId, exerciseId));
}
