---
name: installer-qa-gates
description: Finalize Platform Installer milestones with the repository's focused QA, security and cleanup gates.
---

# Installer QA gates

Use to plan or execute a milestone's final acceptance. Read the milestone
requirements, root `AGENTS.md` and affected scoped rules first.

1. Identify affected layers and run focused tests before broad regression.
2. When Go changes, run `gofmt`, `go test ./...` and `go vet ./...`; run race
   tests when concurrency changed and appropriate.
3. When Core/contracts change, run the focused tests, Core full regression,
   affected service suites, catalog and configuration-schema reproducibility,
   and real controller-side `validate.yml` as applicable.
4. For pure operations prove no target contact and run the offline `unshare -n`
   gate when applicable. Do not repeat accepted runtime failure/recovery
   scenarios unaffected by the milestone.
5. Use `scripts/qa-sync.ps1` for Windows-to-RED OS source transfer and its
   cleanup mode for exact temporary workspaces. Never replace it with tar/SSH
   streaming or dynamic downloads.
6. Audit secret safety, temporary/rollback artifacts, changed and untracked
   files, then run `git diff --check`.
7. Update docs, state and roadmap only after technical gates pass; commit only
   after the worktree audit and clean up QA workspaces.

Report passed, failed and unavailable gates concisely. Runtime credentials stay
under `.runtime/secrets/` and are never printed or copied.
