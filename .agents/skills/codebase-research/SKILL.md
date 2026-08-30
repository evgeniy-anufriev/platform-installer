---
name: codebase-research
description: Perform scoped, read-only research in the Platform Installer V2 repository.
---

# Codebase research

Use for repository research before implementation or review.

- Read the relevant `AGENTS.md` first and limit work to the requested scope.
- Prefer `rg`, file lists, symbols and targeted excerpts over full-file reads.
- Skip `_vendor/`, generated output, runtime output and V1 by default.
- Do not modify production code or repository state.
- Do not dump complete source files or successful logs.

Return a concise report with:

`Scope`, `Findings`, `Relevant Files`, `Relevant Types/Functions`,
`Reusable Implementation`, `Risks`, `Recommended Integration Points`, and
`Open Questions`.
