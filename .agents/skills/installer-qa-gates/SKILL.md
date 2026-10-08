---
name: installer-qa-gates
description: Finalize Platform Installer milestones with the repository's focused QA, security and cleanup gates.
---

# Installer QA gates

Use to plan or execute a milestone's final acceptance. Read the milestone
requirements, root `AGENTS.md` and affected scoped rules first.
Reuse already loaded current instructions. For execution prerequisites read
[QA procedure](../../../docs/agent-procedures/qa.md); for updated-bundle UI QA
also read [runtime bundle procedure](../../../docs/agent-procedures/runtime-bundle.md).
SI11 additionally requires its [procedure](../../../docs/agent-procedures/si11.md)
and visible-UI test cases. These routes preserve all real-flow acceptance gates.

1. Identify affected layers and run focused tests before broad regression.
2. When Go changes, run `gofmt`, `go test ./...` and `go vet ./...`; run race
   tests when concurrency changed and appropriate.
3. When Core/contracts change, run the focused tests, Core full regression,
   affected service suites, catalog and configuration-schema reproducibility,
   and real controller-side `validate.yml` as applicable.
4. For pure operations prove no target contact and run the offline `unshare -n`
   gate when applicable. Do not repeat accepted runtime failure/recovery
   scenarios unaffected by the milestone.
5. Follow the common QA procedure for exact Windows-to-RED OS source transfer,
   established SSH identity/noninteractive sudo and temporary-workspace cleanup.
6. Audit secret safety, temporary/rollback artifacts, changed and untracked
   files, then run `git diff --check`.
7. Update docs, state and roadmap only after technical gates pass; commit only
   after the worktree audit and clean up QA workspaces.

Report passed, failed and unavailable gates concisely. Runtime credentials stay
under `.runtime/secrets/` and are never printed or copied.
