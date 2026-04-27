"""
`published_content` 形态（设计 §4.2, version 1）的 **Pydantic** 描述与**发布**校验。

扩展题 `starterCode` 过长：在 `validate_for_publish` 中**清空**为 `null` 并记 **warnings**；若策略为
**拒绝**可改为抛错（本实现默认可发布但清空，通过设置 `max_len=0` 可改为仅警告仍保留逻辑）。
对「扩展题 `passRule.mode` 仅 `no_exception`」在配置开启时**拒绝发布**（设计 §4.2 表末）。
"""

from __future__ import annotations

import ast
from typing import Annotated, Any, Literal, Union
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from ..config import settings


# --- 过关规则（discriminator: mode）


class PassRuleNoException(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    mode: Literal["no_exception"] = "no_exception"


class PassRuleStdoutContains(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    mode: Literal["stdout_contains"] = "stdout_contains"
    expected_substring: str = Field(
        min_length=1, alias="expectedSubstring", description="stdout 须包含子串"
    )


class PassRuleAssertSnippet(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    mode: Literal["assert_snippet"] = "assert_snippet"
    assert_code: str = Field(min_length=1, alias="assertCode")


PassRule = Annotated[
    Union[PassRuleNoException, PassRuleStdoutContains, PassRuleAssertSnippet],
    Field(discriminator="mode"),
]


# --- cells


class GuideCell(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(min_length=1, max_length=128)
    # 允许空串：学生端可用手敲 + 背景提示层，不预置完整代码
    starter_code: str = Field(default="", min_length=0, alias="starterCode")
    setup_code: str | None = Field(
        default=None,
        max_length=2_000_000,
        alias="setupCode",
        description="运行前自动拼接的隐藏准备代码，用于预加载数据等公共上下文",
    )
    description: str = Field(min_length=1, max_length=16_000)
    pass_rule: PassRule = Field(alias="passRule")
    exercise_title: str | None = Field(
        default=None,
        max_length=500,
        alias="exerciseTitle",
        description="习题短标题，学生端以三级标题显示",
    )
    expected_output: str | None = Field(
        default=None,
        max_length=8_000,
        alias="expectedOutput",
        description="本题期望输出/结果说明，学生端在代码区前展示",
    )
    expected_image_data_url: str | None = Field(
        default=None,
        max_length=2_000_000,
        alias="expectedImageDataUrl",
        description="matplotlib 等作图题的参考图片 data URL，供教师预览/学生对照",
    )
    expected_image_alt: str | None = Field(
        default=None,
        max_length=500,
        alias="expectedImageAlt",
        description="参考图片替代文本",
    )
    reference_answer: str | None = Field(
        default=None,
        max_length=32_000,
        alias="referenceAnswer",
        description="教师可填标准答案/参考代码（发布给学生端作提示，不参与服务端判分）",
    )
    code_backdrop_label: str | None = Field(
        default=None,
        max_length=2_000,
        alias="codeBackdropLabel",
        description="基础练习空框时的红色提示行（学生端只读背景）",
    )
    code_backdrop_code: str | None = Field(
        default=None,
        max_length=32_000,
        alias="codeBackdropCode",
        description="基础练习空框时的浅灰示例代码（学生端只读背景）",
    )


class ExtensionCell(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(min_length=1, max_length=128)
    prompt_html: str = Field(min_length=1, max_length=64_000, alias="promptHtml")
    starter_code: str | None = Field(
        default=None, max_length=1_000_000, alias="starterCode"
    )
    setup_code: str | None = Field(
        default=None,
        max_length=2_000_000,
        alias="setupCode",
        description="运行前自动拼接的隐藏准备代码，用于预加载数据等公共上下文",
    )
    pass_rule: PassRule = Field(alias="passRule")
    exercise_title: str | None = Field(
        default=None,
        max_length=500,
        alias="exerciseTitle",
    )
    expected_output: str | None = Field(
        default=None,
        max_length=8_000,
        alias="expectedOutput",
    )
    expected_image_data_url: str | None = Field(
        default=None,
        max_length=2_000_000,
        alias="expectedImageDataUrl",
    )
    expected_image_alt: str | None = Field(
        default=None,
        max_length=500,
        alias="expectedImageAlt",
    )
    reference_answer: str | None = Field(
        default=None,
        max_length=32_000,
        alias="referenceAnswer",
        description="教师可填标准答案/参考代码（发布给学生端作提示，不参与服务端判分）",
    )


class ContentBlock(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(min_length=1, max_length=128, description="本块稳定 id，可用 blk- 前缀 + uuid")
    section_title: str | None = Field(
        default=None,
        max_length=500,
        alias="sectionTitle",
        description="本块对应知识点二级标题；缺省为「知识点 n」",
    )
    knowledge_html: str = Field(
        min_length=0, max_length=500_000, alias="knowledgeHtml"
    )
    required_execution_mode: Literal["pyodide", "cpython"] | None = Field(
        default="pyodide", alias="requiredExecutionMode"
    )
    guide_cell: GuideCell = Field(alias="guideCell")
    extension_cell: ExtensionCell = Field(alias="extensionCell")


class PublishedContentV1(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    version: Literal[1] = 1
    chapter_intro_html: str = Field(
        default="",
        max_length=500_000,
        alias="chapterIntroHtml",
        description="章首主要知识点介绍（在章节名下方、各知识点块之前）",
    )
    requires_matplotlib_output: bool | None = Field(
        default=None,
        alias="requiresMatplotlibOutput",
        description="显式控制学生端是否显示作图区；缺省由 starter/草稿代码等启发式决定",
    )
    blocks: list[ContentBlock] = Field(min_length=1)


_ta = TypeAdapter(PublishedContentV1)


def parse_published_draft(data: object) -> PublishedContentV1:
    """从 dict / 列表根（非法）等解析，失败时抛 Pydantic 异常。"""
    if isinstance(data, list):
        raise ValueError("root must be an object, not a list")
    return _ta.validate_python(data)


class PublishResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    ok: bool
    content: dict[str, Any] | None = None
    error: str | None = None
    warnings: list[str] = Field(default_factory=list)


def _trim_extension_starter(
    data: dict[str, Any], max_len: int
) -> tuple[dict[str, Any], list[str]]:
    out = _deep_copy_json(data)
    warn: list[str] = []
    if max_len <= 0:
        return out, warn
    blocks = out.get("blocks")
    if not isinstance(blocks, list):
        return out, warn
    for i, b in enumerate(blocks):
        if not isinstance(b, dict):
            continue
        ext = b.get("extensionCell")
        if not isinstance(ext, dict):
            continue
        sc = ext.get("starterCode")
        if isinstance(sc, str) and len(sc) > max_len:
            ext["starterCode"] = None
            warn.append(
                f"blocks[{i}].extensionCell.starterCode cleared: length {len(sc)} > max {max_len}",
            )
    return out, warn


def _deep_copy_json(x: object) -> Any:
    if isinstance(x, dict):
        return {k: _deep_copy_json(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_deep_copy_json(i) for i in x]
    return x


def validate_for_publish(
    draft: dict[str, Any] | list[Any],
    *,
    max_extension_starter_len: int | None = None,
    reject_extension_no_exception: bool | None = None,
) -> PublishResult:
    """
    校验**发布**用内容：Pydantic 全量校验、扩展题 `starterCode` 过长**清空**、可选拒绝弱扩展关规则。

    入参一般为 `chapters.ai_generated_draft` 的 dict 形态。
    """
    max_l = max_extension_starter_len
    if max_l is None:
        max_l = settings.chapter_extension_starter_code_max_len
    strict_ne = reject_extension_no_exception
    if strict_ne is None:
        strict_ne = settings.chapter_publish_reject_extension_no_exception
    if not isinstance(draft, dict):
        return PublishResult(
            ok=False, error="root must be an object with version and blocks", warnings=[],
        )
    trimmed, w = _trim_extension_starter(draft, max_l)
    try:
        model = _ta.validate_python(trimmed)
    except Exception as e:  # noqa: BLE001 — 返回可读错误
        return PublishResult(ok=False, error=f"validation: {e!s}", warnings=list(w))
    if strict_ne:
        for b in model.blocks:
            if isinstance(b.extension_cell.pass_rule, PassRuleNoException):
                return PublishResult(
                    ok=False,
                    error="extension passRule must not be only 'no_exception' (design §4.2); use stdout_contains or assert_snippet",
                    warnings=list(w),
                )
    content = model.model_dump(mode="json", by_alias=True)
    _normalize_published_guide_backdrop(content)
    w.extend(_warn_invalid_reference_python(content))
    return PublishResult(
        ok=True,
        content=content,
        warnings=list(w),
    )


def _normalize_published_guide_backdrop(content: dict[str, Any]) -> None:
    """基础题发布时固定补齐「红字提示 + 灰字参考代码」并清掉重复说明注释。"""
    blocks = content.get("blocks")
    if not isinstance(blocks, list):
        return
    for b in blocks:
        if not isinstance(b, dict):
            continue
        g = b.get("guideCell")
        if not isinstance(g, dict):
            continue
        if not (g.get("codeBackdropLabel") or "").strip():
            g["codeBackdropLabel"] = _DEFAULT_GUIDE_BACKDROP_LABEL
        if not (g.get("codeBackdropCode") or "").strip():
            g["codeBackdropCode"] = _guide_backdrop_code_source(g)
        _strip_redundant_guide_first_line(g)
        if (g.get("codeBackdropCode") or "").strip():
            g["starterCode"] = ""


# 与题目底纹并存时易遮挡红字；发布时剥掉仅作说明的首行
_DF_PREFILL_COMMENT = "# 数据已预加载为 df，请在下方补全代码"
_DEFAULT_GUIDE_BACKDROP_LABEL = "提示：请参考灰色代码，在下方代码框中手动输入并运行。"


def _guide_backdrop_code_source(g: dict[str, Any]) -> str:
    ref = g.get("referenceAnswer")
    if isinstance(ref, str) and ref.strip():
        return ref.strip("\n")
    sc = g.get("starterCode")
    if isinstance(sc, str) and sc.strip():
        lines = sc.splitlines()
        if lines and lines[0].strip().startswith("# 数据已预加载为 df"):
            return "\n".join(lines[1:]).strip("\n")
        return sc.strip("\n")
    return ""


def _warn_invalid_reference_python(content: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    blocks = content.get("blocks")
    if not isinstance(blocks, list):
        return warnings
    for i, b in enumerate(blocks):
        if not isinstance(b, dict):
            continue
        for cell_key in ("guideCell", "extensionCell"):
            cell = b.get(cell_key)
            if not isinstance(cell, dict):
                continue
            for field in ("referenceAnswer", "codeBackdropCode"):
                value = cell.get(field)
                if not isinstance(value, str) or not value.strip():
                    continue
                try:
                    ast.parse(value)
                except SyntaxError as e:
                    warnings.append(
                        f"blocks[{i}].{cell_key}.{field} is not valid Python: {e.msg} at line {e.lineno}",
                    )
    return warnings


def _strip_redundant_guide_first_line(g: dict[str, Any]) -> None:
    if not (g.get("codeBackdropLabel") or "").strip():
        return
    sc = g.get("starterCode")
    if not isinstance(sc, str) or not sc.strip():
        return
    lines = sc.splitlines()
    if not lines:
        return
    first = lines[0].strip()
    if first == _DF_PREFILL_COMMENT or first.startswith("# 数据已预加载为 df"):
        g["starterCode"] = "\n".join(lines[1:]).lstrip("\n")


def sample_published_v1() -> dict[str, Any]:
    """测试/占位：合法 **version: 1** 最小章 JSON。"""
    bid = f"blk-{uuid4()}"
    return {
        "version": 1,
        "chapterIntroHtml": "<p>本章为占位示例。下方按知识点分块，含基础与扩展题。</p>",
        "blocks": [
            {
                "id": bid,
                "sectionTitle": "知识点示例",
                "knowledgeHtml": "<p>print 能向标准输出写文本，便于对照过关条件。</p>",
                "requiredExecutionMode": "pyodide",
                "guideCell": {
                    "id": "c1",
                    "starterCode": "print('hi')",
                    "codeBackdropLabel": "提示：向标准输出打印一行字符。",
                    "codeBackdropCode": "print('hi')",
                    "description": "<p>运行一段代码，无异常即通过</p>",
                    "exerciseTitle": "第 1 题（基础）",
                    "expectedOutput": "终端出现 hi 等输出即可（no_exception 模式）",
                    "passRule": {"mode": "no_exception"},
                },
                "extensionCell": {
                    "id": "c2",
                    "promptHtml": "<p>打印含 Hello 的一行</p>",
                    "starterCode": None,
                    "exerciseTitle": "第 1 题（扩展）",
                    "expectedOutput": "含 Hello 子串的 stdout 一行",
                    "passRule": {
                        "mode": "stdout_contains",
                        "expectedSubstring": "Hello",
                    },
                },
            }
        ],
    }
