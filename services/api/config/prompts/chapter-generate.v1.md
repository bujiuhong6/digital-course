# 章生成 Prompt v1

与 `generator_prompt_version=v1` 对齐（设计 §4.3）。

模型须输出 **JSON**，根对象含 `version: 1` 与 `blocks[]`；每块含 `guideCell` 与 `extensionCell`。
**扩展题** `extensionCell.starterCode` 以 **null** 为主；`passRule` 需合理（优先 `stdout_contains` 或 `assert_snippet`，避免仅 `no_exception` 作为扩展题主策略）。

具体内容与 few-shot 可在后续迭代中补充；MVP 由 `chapter_gen` 的 mock 或 LLM 调用实现。
