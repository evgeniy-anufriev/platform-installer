---
name: codebase-research
description: Perform scoped, read-only research in the Platform Installer V2 repository.
---

# Codebase research

Use for repository research before implementation or review.

- Start with current root/scoped `AGENTS.md` and compact `CURRENT_STATE.md`.
  Reuse already loaded identical instructions; reread on change or uncertainty.
- Use [task index](../../../docs/agent-index.md) for recurring tasks and read
  only the relevant contracts/procedures. Historical snapshots are evidence
  for a specific question, not current status or authorization.
- Search known modules/symbols first with `rg`; expand only when needed.
  Read bounded function/section excerpts and limit output at the source.
  For long HTML lines use bounded extraction, not a whole matching line.
- Explicitly exclude `vendor/**` and `ansible-core/**/_vendor/**` in repository
  passes. Skip generated/runtime output and V1 by default; follow root rules
  for narrow dependency or V1 reference exceptions.
- Do not modify production code or repository state.
- Do not dump complete source files or successful logs.

Report findings, relevant paths/symbols, risks and unresolved questions concisely;
include reusable implementation/integration points when relevant to the task.
