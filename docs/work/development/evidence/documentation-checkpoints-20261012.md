# Historical documentation checkpoints

Extracted on 2026-10-12 from the original milestone documents. Recorded statuses,
versions, review verdicts and test outcomes describe their source scope and dates.
They do not override [CURRENT_STATE](../../../../CURRENT_STATE.md), authorize new
work or prove later acceptance. Requirements and planned QA remain in the source
documents. A moved evidence section retains its original wording and title.

## devx-01.md

Source document: [devx-01.md](../devx-01.md).

<a id="devx-01-checkpoint-001"></a>

Status: **DONE**. This harness records the accepted engineering workflow; it
does not add product behavior, UI-BE-04 execution, Wails/React code or service
semantics.

## Mixed-section reconciliation: devx-01.md

Source: [devx-01.md](../devx-01.md). Extracted on 2026-10-12;
original dates, scopes and reviewer verdicts are preserved. This is historical
evidence, not current authorization.

<a id="devx-01-reconciliation-001"></a>

The current Codex session already discovers the repository's existing
`.agents/skills` entries, proving the local location and frontmatter mechanism.
The four new Skills use that same two-field frontmatter and have no external
references. The session Skill registry is initialized at session start, so a
fresh session will surface newly added names; local frontmatter validation is
the current-session proof before that refresh. Root, Go and Core instruction paths were checked for additive
hierarchy; Markdown headings/fences and UTF-8 text were validated locally.
At original DEVX-01 acceptance, roles were documented templates. The later
architecture-reviewer addition uses the supported project-scoped custom agent
format documented in [Codex subagents](https://developers.openai.com/codex/subagents/).
