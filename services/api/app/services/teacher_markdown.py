"""Convert LLM Markdown for teacher HTML views; output is bleach-sanitized."""

from __future__ import annotations

import bleach
import markdown

_ALLOWED_TAGS = frozenset(
    {
        "p",
        "br",
        "strong",
        "em",
        "u",
        "s",
        "hr",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "ul",
        "ol",
        "li",
        "blockquote",
        "code",
        "pre",
        "table",
        "thead",
        "tbody",
        "tr",
        "th",
        "td",
    }
)

_ALLOWED_ATTRS = {
    "code": ["class"],
    "pre": ["class"],
    "th": ["colspan", "rowspan"],
    "td": ["colspan", "rowspan"],
}


def teacher_markdown_to_safe_html(text: str) -> str:
    raw = markdown.markdown(
        text or "",
        extensions=["fenced_code", "tables", "nl2br"],
        extension_configs={"fenced_code": {"lang_prefix": "language-"}},
    )
    return bleach.clean(
        raw,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRS,
        strip=True,
    )
