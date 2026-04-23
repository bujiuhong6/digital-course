---
name: superpowers
description: Applies the Superpowers agent methodology from obra/superpowers—brainstorming, git worktrees, written plans, TDD, systematic debugging, code review, and branch completion. Use when building features, fixing bugs, planning implementation, reviewing code, or when the user mentions Superpowers, subagent-driven development, or RED-GREEN-REFACTOR.
---

# Superpowers (Cursor)

[Superpowers](https://github.com/obra/superpowers) is a composable skill library and workflow for coding agents: clarify intent before coding, capture design, plan in small verifiable steps, implement with discipline (especially TDD), debug systematically, and close branches cleanly.

## Install and sources

**This repo:** Full upstream skills live in the git submodule at **`vendor/superpowers/skills/`** (repository root: [obra/superpowers](https://github.com/obra/superpowers)). After clone, initialize submodules:

```bash
git submodule update --init --recursive
```

**Local Cursor:** You can still install the marketplace plugin (`/add-plugin superpowers`) for IDE integration; the submodule is for **Cloud Agent and reproducible full skill text** in this project.

## How to use skills in Cursor

Upstream `using-superpowers` assumes a host-specific “Skill” tool. In Cursor, **read the matching skill file** when a workflow applies. Prefer the **current** file text over memory.

**Canonical path in this workspace:**

`vendor/superpowers/skills/<skill-name>/SKILL.md`

Example: `vendor/superpowers/skills/test-driven-development/SKILL.md`

Use the **workflow order** and **skill names** below to pick `<skill-name>`. If the submodule directory is missing, run `git submodule update --init --recursive`.

## Workflow order (typical feature)

Follow this sequence unless the user’s instructions define a different priority:

1. **brainstorming** — Refine the problem and design; present digestible chunks; get explicit approval before implementation planning.
2. **using-git-worktrees** — After design approval: isolate work (branch/worktree), run setup, confirm a clean test baseline when tests exist.
3. **writing-plans** — Break approved design into small tasks (concrete files, steps, verification).
4. **executing-plans** or **subagent-driven-development** — Execute the plan with reviews between tasks as the skill describes.
5. **test-driven-development** — During implementation: RED → GREEN → REFACTOR; avoid production code without a failing test first when this skill applies.
6. **requesting-code-review** — Between tasks or before merge: check against plan and severity rules in that skill.
7. **finishing-a-development-branch** — When done: verify tests, summarize outcomes, handle merge/PR/cleanup per skill.

**Process before implementation:** For ambiguous or multi-step product work, run **brainstorming** before deep exploration. For defects, prefer **systematic-debugging** (and **verification-before-completion** before claiming fixed).

## Skill index (what to load)

| Skill | Use when |
|--------|----------|
| using-superpowers | Session shape: how skills override defaults, skill invocation discipline |
| brainstorming | Idea → design; alternatives; sign-off before coding |
| using-git-worktrees | Parallel branch / worktree setup after design lock |
| writing-plans | Approved design → implementation plan |
| executing-plans | Batch execution with human checkpoints |
| subagent-driven-development | Task loop with spec + code review stages |
| dispatching-parallel-agents | Concurrent agent-style workstreams |
| test-driven-development | Implementing with strict TDD |
| systematic-debugging | Root-cause investigation |
| verification-before-completion | Confirming a fix before handoff |
| requesting-code-review | Preparing or running structured review |
| receiving-code-review | Acting on review feedback |
| finishing-a-development-branch | Tests green → merge/PR/cleanup decision |
| writing-skills | Authoring or changing skills in the Superpowers style |

## Principles (short)

- **Tests first** when TDD skill applies.
- **Systematic steps** over ad hoc guesses for debugging and planning.
- **Evidence** (tests, repro, logs) before declaring success.
- **User instructions** outrank skill defaults when they conflict.

## Contributing upstream

To change Superpowers itself, follow [CLAUDE.md](https://github.com/obra/superpowers/blob/main/CLAUDE.md) in that repository (PR template, one problem per PR, evaluation expectations for skill changes).

## More detail

- Submodule checkout: `vendor/superpowers/` (MIT — see `vendor/superpowers/LICENSE`)
- Upstream overview: [README.md](https://github.com/obra/superpowers/blob/main/README.md)
- Plugin manifest (paths): [.cursor-plugin/plugin.json](https://github.com/obra/superpowers/blob/main/.cursor-plugin/plugin.json)
