# UI-02C — target credential lease and idempotent Start correlation

Status: **DONE**.

UI-02C adds the closed node-side `PutRuntimeSecretLease/v1alpha1` protocol,
`ExecutionCapabilities/v1alpha2` gate and `StartExecution/v1alpha2`
correlation. It adds no Wails/React Start, generic secret system or target
execution path. The bounded payload travels only through SSH stdin and is
stored only in private Execution Node state. It is never exposed in desired
state, journals, events, results or diagnostics.

The node binds a lease to the exact project/revision/plan/manifest/runtime,
persists retry correlation by `startAttemptId`, rejects caller run IDs and
removes attached material on terminal/recovered terminal lifecycle. No runtime
release was activated and no target host was contacted.

Evidence: focused Go, `go test ./...`, `go vet ./...`, and RED OS Python
protocol tests plus affected Go `-race`/vet passed.

UI-02D is next.
