# Historical documentation checkpoints

Extracted on 2026-10-12 from the original milestone documents. Recorded statuses,
versions, review verdicts and test outcomes describe their source scope and dates.
They do not override [CURRENT_STATE](../../../../CURRENT_STATE.md), authorize new
work or prove later acceptance. Requirements and planned QA remain in the source
documents. A moved evidence section retains its original wording and title.

## ui-02f-runtime-service-secret-transport.md

Source document: [ui-02f-runtime-service-secret-transport.md](../ui-02f-runtime-service-secret-transport.md).

<a id="ui-02f-runtime-service-secret-transport-checkpoint-001"></a>

## Status

**PLAN — owner-approved direction; implementation has not started.**

UI-02F closes the execution prerequisite exposed by SERVICE-INSTALL-06:
the existing credentialed Start transports the target login, optional sudo
password, and the one PKI store password, but cannot transport PostgreSQL
`pg_auto_failover` runtime passwords.  It is a narrow extension of the
existing lease; it is not a vault, secret registry, desired-state store,
workstation-to-target path, or generic file upload API.




## ui-02e-pki-runtime-secret-transport.md

Source document: [ui-02e-pki-runtime-secret-transport.md](../ui-02e-pki-runtime-secret-transport.md).

<a id="ui-02e-pki-runtime-secret-transport-checkpoint-001"></a>

## 8. Completion evidence

The immutable QA runtime release
`sha256:6d85afb53c6994f2f1b152e29b39a329ed35a9af7ed3e9c802be0e888993dca0`
(`qa-ui-02e-20260922-15`) was published and activated through the existing
Execution Node activation path.  Its capability handshake was READY and
advertised the compatible closed lease/start contract before the test staged
the runtime-only store password.

The production-shaped one-host/three-member Kafka acceptance passed with:

```text
go test ./internal/executionnode \
  -run '^TestUI02EProductionSingleHostKafkaLifecycle$' \
  -v -count=1 -timeout 40m

cycle 1: installer-a21c3eed1d053ac7ef073e13214349a6
         SUCCEEDED, 12m16s, 1,260 events, changed=0
cycle 2: installer-a3a4bba6fb97f41b21080ae22c00bcbb
         SUCCEEDED, 12m42s, 1,260 events, changed=0
total:    PASS, 24m58s
```

Both cycles used the generic `CreatePlan -> ApprovePlan -> Start` path.  PKI
apply/verify and Kafka apply/verify completed through the selected Execution
Node.  The second cycle proved repeat apply `changed=0`; it was not accepted
merely from event logs.  The authoritative RunObserver terminal sync also
clears the local active-run binding, so a completed run cannot block the next
plan as `ACTIVE_RUN_EXISTS`.

The isolated QA deployment units remained active after the test:

```text
kafka@kafka-ui02e-1.service  active
kafka@kafka-ui02e-2.service  active
kafka@kafka-ui02e-3.service  active
```

Final regression passed: local `go test ./...`, `go vet ./...`, frontend lint,
62 frontend tests, frontend production build, Wails production build, RED OS
Core suite (280 passed, 4 skipped), fixture-catalog and service-schema
reproducibility, Kafka apply syntax-check, and RED OS
`CGO_ENABLED=1 go test -race ./internal/executionnode ./internal/runtimesecret`.
The remote QA workspace was removed through `scripts/qa-sync.ps1 -Cleanup`.
Changed-scope secret inspection found no production plaintext material;
`git diff --check` passed after the generated Wails binding was normalized with
the new narrow `npm run format:bindings` command.


<a id="ui-02e-pki-runtime-secret-transport-checkpoint-002"></a>

Status: **DONE (2026-09-22).**


## ui-02d.md

Source document: [ui-02d.md](../ui-02d.md).

<a id="ui-02d-checkpoint-001"></a>

Status: **DONE**.


## ui-02c.md

Source document: [ui-02c.md](../ui-02c.md).

<a id="ui-02c-checkpoint-001"></a>

Status: **DONE**.


## ui-02b.md

Source document: [ui-02b.md](../ui-02b.md).

<a id="ui-02b-checkpoint-001"></a>

## Evidence

- Focused Go tests cover executable and blocked plans, exact acknowledgement
  equality, stale revision rejection, current-plan ownership and the invariant
  that UI‑02B never calls Start.
- Runtime-protocol tests cover bounded typed phase/action/acknowledgement
  decoding and malformed action rejection.
- Windows Go/Wails and frontend gates pass; the full frontend suite contains
  60 tests.
- RED OS QA runs `go test -race . ./internal/executionnode` and `go vet` on a
  freshly synchronized worktree. The temporary QA workspace is removed.


<a id="ui-02b-checkpoint-002"></a>

Status: **DONE**


## ui-02a.md

Source document: [ui-02a.md](../ui-02a.md).

<a id="ui-02a-checkpoint-001"></a>

## Evidence

- Focused Go tests prove local-only prerequisite projection, saved revision
  binding, draft gating, trusted-binding gating and safe unreadable-revision
  handling.
- Frontend tests cover the safe prerequisite display, Servers hand-off and all
  four read-only stages; the full frontend suite passes 59 tests.
- `go test ./...`, `go vet ./...`, frontend lint/build, Wails Windows build and
  `git diff --check` pass. No Core, Execution Node or target operation is
  called by this slice.


<a id="ui-02a-checkpoint-002"></a>

Status: **DONE**


## ui-02-architecture.md

Source document: [ui-02-architecture.md](../ui-02-architecture.md).

<a id="ui-02-architecture-checkpoint-001"></a>

Status: **UI-02A through UI-02E DONE; UI-02 overall DONE**. UI-02C uses one
`ExecutionService`-owned v1alpha2 Start path: plan-time staging is private and
is never an authoritative run, and the Execution Node commits the node-owned
run binding, attempt mapping and lease attachment before controller launch.
`UI02-PLAN-001` is
**RESOLVED BY OWNER DECISION**: credentialed Start uses versioned
`StartExecution/v1alpha2` before capability negotiation through
`ExecutionCapabilities/v1alpha2`. The initial PLAN review and its permitted
targeted recheck are complete; no further architecture review is run for this
exact owner-authorized correction.
