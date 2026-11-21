# Large dump revision cost

Owner request, 2026-11-18: optimize approval and Start for a 700 MiB dump while
retaining fresh content validation before execution. Branch:
`codex/project-verify-performance`, baseline `bc26d5c5` plus the existing unrelated
working-tree changes. No architecture, persisted state, public contract or Core
execution rule changes; this is a bounded implementation correction.

## Implementation

Revision collection now streams package files into SHA-256 and retains only the
digest/size metadata. It reuses that digest when constructing the canonical
revision instead of hashing the same bytes again. Export/import still receive
file contents when needed. Windows/Linux use the same existing handle-relative
opening, link/reparse rejection and before/after file identity/size guards.
The existing zero-limit (unlimited file size) semantics of this branch remain.

Approval returns its already checked view with the approved flag while `editMu`
is still held. It no longer calls the getter that recalculates the revision.
Standalone getters and Start continue to read the current bytes independently.
No timestamp/size cache or cross-request proof reuse was introduced.

Start retains both its initial revision check and its post-dispatch context
check. ExecutionService still rebuilds the authoritative Core plan and compares
revision, identity and fingerprint before dispatch. Project transfer archive
hashing/cache extraction and Core package/restore digest checks are unchanged;
this change does not claim to remove all I/O from the full distributed flow.

## Counts and measurements

Same Windows workstation, Go 1.26.7 toolchain, Ryzen 7 7800X3D; identical synthetic
project with one 700 MiB package asset, no inventory, hosts or operations. The
fixture is written before the timer. This measures only the local revision
stage, not a live deployment or network/Execution Node performance.

Command on baseline and changed code:

```text
go test ./internal/installer -run '^$' -bench '^BenchmarkProjectRevisionPackage$' -benchtime=1x -count=3
```

| Measurement | Baseline | Changed |
| --- | --- | --- |
| Revision elapsed, three samples (s) | 1.229676 / 0.882493 / 0.995441 | 0.528507 / 0.537578 / 0.512205 |
| Median elapsed (s) | 0.995441 | 0.528507 |
| Allocated bytes per revision | 1,852,290,912–1,852,348,696 | 53,272–119,144 |
| Asset reads per revision | 1 | 1 |
| Asset SHA-256 passes per revision | 2 | 1 |
| Successful approval: revision calls / reads / SHA passes | 2 / 2 / 4 | 1 / 1 / 1 |
| Ordinary Start: direct desktop revision calls / reads / SHA passes | 2 / 2 / 4 | 2 / 2 / 2 |
| Initial plan + fresh Start plan invocations | 2 | 2 |
| Added subprocesses / Ansible tasks | 0 / 0 | 0 / 0 |

Timing samples include ordinary system noise; allocation figures are total
allocated bytes, not peak working set. The final changed samples were run after
other Go checks finished. The local median improved about 47%; no
end-to-end approval/Start speedup is claimed from this microbenchmark.

## Regression and acceptance

`TestRevisionStreamsPackageAndDetectsSameSizeSameTimeChange` proves canonical
revision compatibility, digest-only records without retained contents, and fresh
recognition of changed bytes with unchanged length and restored modification time.
`TestStreamLargeRevisionAssetBoundedAndGuarded` streams exactly 700 MiB once into
a counting sink, asserts bounded write chunks and retains the explicit size guard.
`TestStartRejectsPackageAssetChangedAfterApproval` proves a modified dump blocks
before plan rebuild or remote dispatch. Existing combined approval/Start tests
assert the authoritative plan invocation count stays at two.

`go test ./...` and `go vet ./...` passed on the final production changes,
including existing export/import/path guards, approval projection, fresh-plan
counts and the new changed-asset Start regression. Scoped `git diff --check`
passed. Windows runtime tests do not establish Linux runtime QA.
No Python/Ansible sources changed. No installation or target mutation performed.

Real React/Wails acceptance remains blocked: the standard read-only
`node scripts/qa-wails-bridge.cjs` preflight reported
`QA_WAILS_BRIDGE_PREFLIGHT_FAILED`. No saved real project revision, run ID,
terminal execution result or visual PASS is claimed. Rebuild and real UI/Node
acceptance are required before considering the affected flow accepted.
