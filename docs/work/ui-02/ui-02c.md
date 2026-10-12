# UI-02C — target credential lease and idempotent Start correlation

Document scope: the original milestone contract/design. Historical status, review
and QA checkpoints are collected separately; current status and authorization
are recorded only in [CURRENT_STATE](../../../CURRENT_STATE.md).

Recorded status and review scope: [historical checkpoint](evidence/documentation-checkpoints-20261012.md#ui-02c-checkpoint-001).

UI-02C adds the closed node-side `PutRuntimeSecretLease/v1alpha1` protocol,
`ExecutionCapabilities/v1alpha2` gate and the one approved
`StartExecution/v1alpha2` path through `ExecutionService`. It adds no
Wails/React Start, generic secret system or target execution path. The bounded
payload travels only through SSH stdin and is stored only in private Execution
Node state. It is never exposed in desired state, journals, events, results or
diagnostics.

An executable plan owns only opaque private staging, never an authoritative
run ID. After a fresh approved-plan recheck, `ExecutionService` creates and
retains one `startAttemptId`; for a credentialed Start it performs PUT with
that attempt, keeps the returned lease ID private, and calls v1alpha2 only.
The Execution Node creates the authoritative run ID, persists its immutable
journal binding and the durable attempt-to-run mapping, attaches the exact
non-expired STAGED lease, and only then launches the controller. A lost Start
response is retried with the same attempt; a post-commit controller-launch
failure records terminal `FAILED` evidence on the same node-owned run.

Evidence: focused Go and node protocol tests, `go test ./...`, `go vet ./...`,
and RED OS Core suite (257, 4 skipped), catalog/schema reproducibility and
affected Go `-race` passed. Fault injection proves that PREPARED recovery
metadata left after final attempt-to-run publication cannot roll back the
authoritative run, lease attachment or journal; retry returns the same run
without a second launch. No runtime release was activated and no target host
was contacted.

UI-02D is next.
