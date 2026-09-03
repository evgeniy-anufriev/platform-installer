# Go Installer backend rules

`internal/coreadapter` and `internal/installer` own Installer application
semantics, not infrastructure semantics. Ask Core through `coreadapter.Adapter`
for Ansible precedence, catalog/schema, topology, endpoint/provider, PKI and
other infrastructure answers; do not recreate them in Go.

- Thread `context.Context` through blocking process, lock and future execution
  work. Propagate cancellation; do not create fire-and-forget goroutines.
  Every goroutine needs an owner, termination condition, error path and
  shutdown behavior.
- Keep stateful backend objects explicit, bounded, cleanable and concurrency
  safe. `PlanStore` retains opaque plans only; it is not desired-state storage.
- Use stable structured findings/contracts, never parsed human stdout.
- Derive writable destinations in the backend. Enforce project-root containment
  and reject traversal, symlinks and reparse points. Preserve atomic replace,
  rollback/recovery and locking requirements for project transactions.
- Isolate platform-specific filesystem/process behavior behind narrow
  abstractions, as `replace_unix.go` and `replace_windows.go` do.
- Add focused tests for changed transactions, conflicts, cancellation,
  concurrency/races, path safety and deterministic serialization as applicable.
- Future Wails code is transport-only over these application services.
