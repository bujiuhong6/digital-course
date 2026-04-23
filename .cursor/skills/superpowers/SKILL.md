---
name: superpowers
description: Applies the Superpowers agent methodology from obra/superpowers—brainstorming, git worktrees, written plans, TDD, systematic debugging, code review, and branch completion. Use when building features, fixing bugs, planning implementation, reviewing code, or when the user mentions Superpowers, subagent-driven development, or RED-GREEN-REFACTOR.
---

# Superpowers (Cursor)

[Superpowers](https://github.com/obra/superpowers) is a composable skill library and workflow for coding agents: clarify intent before coding, capture design, plan in small verifiable steps, implement with discipline (especially TDD), debug systematically, and close branches cleanly.

## Submodule and paths

Upstream is vendored as **`vendor/superpowers/`** (git submodule). Full skill bodies:

`vendor/superpowers/skills/<skill-name>/SKILL.md`

After `git clone`, run:

```bash
git submodule update --init --recursive
```

**Cursor:** Read the file for the workflow you need; use **`vendor/superpowers/skills/using-superpowers/SKILL.md`** for when and how to load skills. Prefer the checked-in text over memory.

**Desktop Cursor:** Optional marketplace plugin (`/add-plugin superpowers`) for IDE integration; the submodule supplies **full skill text** for Cloud Agent and offline clones.

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

## Reference (in submodule)

- `vendor/superpowers/README.md` — upstream overview  
- `vendor/superpowers/LICENSE` — MIT  
- `vendor/superpowers/CLAUDE.md` — contributing to **upstream** Superpowers (not this app repo)
