# digital-course

单人维护的教学产品规格与开发仓库（**无协作者**；密钥与本地配置不提交到 Git）。

## 使用本仓库

- **Context7 MCP**：根目录需有 **`.env`**，内含从 [Context7](https://context7.com/dashboard) 取得的 `CONTEXT7_API_KEY`。可参考 **`.env.example`** 自建 **`.env`**。配置见 **`.cursor/mcp.json`**。
- **Superpowers 技能正文**：`vendor/superpowers` 为子模块。若目录为空，执行 `git submodule update --init --recursive`。
- **教学产品准备清单**：`docs/superpowers/specs/2026-04-23-ai-python-teaching-system-preparation.md`（详细需求见文内，章素材为后续提供、AI 辅助生成、人工定稿，仍由**本人**拍板）。
