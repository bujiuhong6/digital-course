"""
据设计 §4.2 的 `passRule` 与客户端上报的 `runOk`、**stdout** 等计算是否过关（任务 8）。

- `no_exception`：以 **`runOk`** 为准（无未捕获异常则客户端报 true）。
- `stdout_contains`：需 **`runOk` 为 true 且** `stdout` **包含** `expectedSubstring`。
- `assert_snippet`：本阶段**不**在服务器上执行 `assertCode`（无 Pyodide 环境）；**以 `runOk` 为过关依据**（断言应在学生端与代码一并执行，客户端对结果负责）。后续可在服务端沙箱中加强。
"""

from __future__ import annotations

from typing import Any, Mapping

# 类型别名：与 `chapter_json` 的 dict 形式兼容（camelCase 键）


def _rule_from_cell(cell: Mapping[str, Any] | object) -> dict[str, Any]:
    if isinstance(cell, dict):
        pr = cell.get("passRule")
        return pr if isinstance(pr, dict) else {}
    d = cell.model_dump(mode="json", by_alias=True)  # type: ignore[union-attr]
    pr = d.get("passRule")
    return pr if isinstance(pr, dict) else {}


def _find_cell_in_chapter(
    content: dict[str, Any] | list[Any] | object,
    cell_id: str,
) -> dict[str, Any] | None:
    """在 `published_content` 中找 `guideCell` / `extensionCell` 含此 `id` 的项。"""
    if hasattr(content, "model_dump"):
        c = content.model_dump(mode="json", by_alias=True)  # type: ignore[union-attr]
    else:
        c = content
    if not isinstance(c, dict) or c.get("version") != 1:
        return None
    blocks = c.get("blocks")
    if not isinstance(blocks, list):
        return None
    for b in blocks:
        if not isinstance(b, dict):
            continue
        for key in ("guideCell", "extensionCell"):
            cell = b.get(key)
            if isinstance(cell, dict) and cell.get("id") == cell_id:
                return cell
    return None


def is_cell_passing(
    chapter_published: dict[str, Any] | object,
    cell_id: str,
    *,
    run_ok: bool,
    stdout: str | None,
    stderr: str | None,
) -> bool:
    cell = _find_cell_in_chapter(chapter_published, cell_id)
    if cell is None:
        return False
    rule = _rule_from_cell(cell)
    mode = rule.get("mode")
    if mode == "no_exception":
        return bool(run_ok)
    if mode == "stdout_contains":
        if not run_ok:
            return False
        sub = rule.get("expectedSubstring") or rule.get("expected_substring")
        if not isinstance(sub, str) or not sub:
            return False
        return sub in (stdout or "")
    if mode == "assert_snippet":
        return bool(run_ok)
    return False


def required_cell_ids_from_content(
    content: dict[str, Any] | list[Any] | object,
) -> list[str]:
    if hasattr(content, "model_dump"):
        c = content.model_dump(mode="json", by_alias=True)  # type: ignore[union-attr]
    else:
        c = content
    if not isinstance(c, dict) or c.get("version") != 1:
        return []
    blocks = c.get("blocks")
    if not isinstance(blocks, list):
        return []
    ids: list[str] = []
    for b in blocks:
        if not isinstance(b, dict):
            continue
        for key in ("guideCell", "extensionCell"):
            cell = b.get(key)
            if isinstance(cell, dict) and isinstance(cell.get("id"), str):
                ids.append(cell["id"])
    return ids
