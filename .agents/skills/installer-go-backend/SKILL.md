---
name: installer-go-backend
description: Implement bounded Go Installer backend work without recreating Ansible/Core infrastructure semantics.
---

# Installer Go backend

Use for Go application/backend changes under `internal/`, including future
sessions, process coordination, history and Wails-facing services. Do not use
for Core/service semantics or frontend-only work.

1. Load current root and `internal/AGENTS.md` (reuse identical loaded rules),
   then use [task index](../../../docs/agent-index.md) for relevant UI/backend
   contracts. Read [review procedure](../../../docs/agent-procedures/review.md)
   when architecture-sensitive planning or risk classification is required.
2. Classify ownership. If the request needs Ansible precedence, catalog/schema,
   topology, endpoint/provider or PKI semantics, stop Go implementation and
   define a `coreadapter.Adapter` capability instead.
3. Reuse `installer.Backend`, `PlanStore`, structured `Finding`/contracts and
   `coreadapter.Adapter`; keep interfaces narrow and use dependency injection
   at filesystem/process boundaries where it makes tests possible.
4. Thread `context.Context` through blocking work. Give any goroutine explicit
   ownership, cancellation, error propagation and cleanup.
5. For filesystem work verify ownership, root containment, traversal and
   symlink/reparse rejection, atomicity, rollback/recovery and writer
   concurrency. Keep OS-specific behavior isolated like `replace_unix.go` and
   `replace_windows.go`.
6. Add focused Go tests. Run `gofmt`, `go test ./...` and `go vet ./...`; add
   race tests when concurrency changed and the environment supports them.
7. Run Core/service QA only when the change affects that layer.

Do not add service-specific behavior, a second desired-state store or Wails UI
scaffolding.
