"""
`published_content` 形态（设计 §4.2, version 1）的 **Pydantic** 描述与**发布**校验。

扩展题 `starterCode` 过长：在 `validate_for_publish` 中**清空**为 `null` 并记 **warnings**；若策略为
**拒绝**可改为抛错（本实现默认可发布但清空，通过设置 `max_len=0` 可改为仅警告仍保留逻辑）。
对「扩展题 `passRule.mode` 仅 `no_exception`」在配置开启时**拒绝发布**（设计 §4.2 表末）。
"""

from __future__ import annotations

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
    starter_code: str = Field(min_length=1, alias="starterCode")
    description: str = Field(min_length=1, max_length=16_000)
    pass_rule: PassRule = Field(alias="passRule")
    reference_answer: str | None = Field(
        default=None,
        max_length=32_000,
        alias="referenceAnswer",
        description="教师可填标准答案/参考代码（发布给学生端作提示，不参与服务端判分）",
    )


class ExtensionCell(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(min_length=1, max_length=128)
    prompt_html: str = Field(min_length=1, max_length=64_000, alias="promptHtml")
    starter_code: str | None = Field(
        default=None, max_length=1_000_000, alias="starterCode"
    )
    pass_rule: PassRule = Field(alias="passRule")
    reference_answer: str | None = Field(
        default=None,
        max_length=32_000,
        alias="referenceAnswer",
        description="教师可填标准答案/参考代码（发布给学生端作提示，不参与服务端判分）",
    )


class ContentBlock(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(min_length=1, max_length=128, description="本块稳定 id，可用 blk- 前缀 + uuid")
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
    return PublishResult(
        ok=True,
        content=model.model_dump(mode="json", by_alias=True),
        warnings=list(w),
    )


def sample_published_v1() -> dict[str, Any]:
    """测试/占位：合法 **version: 1** 最小章 JSON。"""
    bid = f"blk-{uuid4()}"
    return {
        "version": 1,
        "blocks": [
            {
                "id": bid,
                "knowledgeHtml": "<p>Sample</p>",
                "requiredExecutionMode": "pyodide",
                "guideCell": {
                    "id": "c1",
                    "starterCode": "print('hi')",
                    "description": "Run once",
                    "passRule": {"mode": "no_exception"},
                },
                "extensionCell": {
                    "id": "c2",
                    "promptHtml": "<p>Print greeting</p>",
                    "starterCode": None,
                    "passRule": {
                        "mode": "stdout_contains",
                        "expectedSubstring": "Hello",
                    },
                },
            }
        ],
    }
