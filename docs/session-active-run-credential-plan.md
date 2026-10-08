# Active execution and SSH session expiry

## Milestone

`SESSION-RUN-CREDENTIAL-01` — keep an already authorized Execution Node
reachable for the lifetime of its active installation run, even after the
ordinary two-hour UI credential lease would expire.

## Owner requirement and scope

The owner reported during S11 that expiry of the authorized SSH session
disconnects the UI from the Execution Node while a plan is still running. The
same active run must remain observable and controllable after the ordinary
credential TTL. Do not restart, replace, or alter the run. Preserve ordinary
credential expiry when there is no active run.

This is a process-memory-only lifecycle change. It does not persist credentials,
extend the lifetime of sudo/PKI/service secrets, add a UI-to-SSH path, change
Execution Node trust, or alter detached-run semantics.

## Evidence and current failure

`docs/ui-01a-contract-freeze.md` defines a two-hour `SessionCredential` lease.
`internal/runtimesecret.Broker.expireLocked` clears all material in that lease.
The dynamic Execution Node transport checks `CurrentExecutionIdentity` for
each operation; after expiry, run polling and cancellation cannot authenticate.
The detached controller may continue remotely, so loss of UI transport is not
proof that the run stopped or completed.

## Proposed behavior

1. There can be only one active installation run per project. Use one
   in-memory active-run slot in the existing Broker, not a map or a second
   reservation subsystem. Its state is either `STARTING` (reservation made,
   no authoritative run ID yet) or `RUNNING` (bound to one exact `runId`).
   Before dispatching Start, populate the slot with the already-approved SSH
   identity metadata and captured project/node/trust/credential generations.
   This closes the lease-expiry window while the request is in flight. It does
   not retain key bytes or extend the enclosing lease.
2. When Start returns an authoritative `runId`, change the same slot from
   `STARTING` to `RUNNING(runId)` under the Broker mutex. This single mutation
   is the ownership transition; it must not depend on the ordinary lease
   remaining live. Broker is authoritative for whether SSH credentials and
   host-key trust may change. The run registry and observer consume this slot
   as run metadata; they do not own a second credential reservation.
3. The existing `ExecutionService` owns the opaque `startAttemptID` in its
   `pendingStarts[planID]` entry before dispatch. If the response is uncertain,
   keep the Broker slot in `STARTING` and let the user retry Start for the same
   approved plan in the same app process. `ExecutionService` must reuse its
   existing attempt ID; it is not copied into Broker/UI or a new store. The
   retry is allowed only when `startOutcomeUnknown` is true and the local
   record is the matching `PENDING` record for that same plan/project/node.
   On a validated response, transition the slot to the returned exact
   `runId`; never guess one. A proven not-dispatched first attempt releases the
   slot and restores the prior local record. If that restoration fails, release
   SSH authorization because the remote run is proven absent, leave the
   fail-closed `PENDING` marker, return a clear local-record error, and block
   any new Start while that marker remains.
4. Bind the slot to that exact run and trusted context: project
   identity/generation, selected Execution Node identity, approved host-key
   pin, and accepted SSH credential generation. Retain only the existing
   Execution Node SSH identity metadata needed by the current transport
   (`username`, key path, digest, file identity, and generation); do not copy
   or persist key bytes in a second store. Every operation must continue to
   verify the existing key file against its captured identity and digest.
5. Do not retain or extend the enclosing broker lease. Unrelated sudo, PKI,
   and service secrets still expire on schedule. The hold is not authorization
   for another project, node, or run.
6. Keep the existing app-owned run monitor, independent of presentation
   subscriptions. After the slot enters `RUNNING(runId)`, the monitor observes
   that exact ID through the existing trusted transport/observer while the UI
   navigates or unsubscribes. It retries temporary transport/monitor startup
   errors; no error path may clear the Broker slot. Reconnection resumes the
   same run ID and event sequence through existing replay behavior.
7. A transient transport error, screen navigation, UI unsubscription, or
   local observer disconnect is not terminal evidence. Keep the hold while
   run state is active, unknown, or temporarily unavailable.
8. Reject explicit credential replacement/clear and host-key probe,
   decline, or approval while a Start reservation or run is unresolved, with
   a clear `INSTALLATION_RUN_ACTIVE` result, so the accepted credential
   generation and trust cannot be silently replaced mid-run. Project
   close/replacement or app shutdown clears the in-memory reservation/hold and
   preserves existing recovery behavior; an old hold must never restore access
   under changed trust. Do not claim the remote run is terminal in these cases.
9. If updating the local run record fails after the node accepted Start, keep
   the Broker slot in `RUNNING(runId)`, keep observing, and retry the existing
   record write. Report that the node accepted the run but local status storage
   is pending; do not report Start as rejected and do not permit another Start.
   Monitor startup/transport errors likewise keep the slot and retry the same
   `runId`; only an authoritative terminal result releases it.

The implementation should extend existing Broker, trusted binding, and run
registry lifecycle only. Do not add persistence, a second credential store, a
general session subsystem, arbitrary command access, or a new UI protocol
unless the existing contracts cannot safely express this behavior.

## Required tests and acceptance

- Broker: ordinary lease expiry still clears credentials with no active run;
  an active run retains SSH authorization but expires unrelated secrets; each
  release path zeros retained SSH material.
- Binding/run lifecycle: hold is tied to one run and exact project/node/
  host-key/credential generation; replacement or context change invalidates it.
- Start lifecycle: reservation exists before dispatch; definite
  non-dispatch releases it; uncertain dispatch keeps it while a same-plan UI
  retry reuses the existing `ExecutionService.pendingStarts` attempt ID;
  confirmed Start promotes it to the exact returned run ID.
- Failed restoration after proven non-dispatch leaves a safe `PENDING` marker,
  returns a clear error, and blocks another Start rather than guessing or
  overwriting the prior record.
- Accepted-Start failures: inject local run-record and monitor/transport
  failures after remote acceptance and prove the single Broker slot remains
  bound to the exact `runId`, monitoring retries, host-key and credential
  changes remain blocked, and only terminal status releases the slot.
- Observer/control: expiry during polling, transient transport failure,
  navigation/unsubscribe and reconnect all keep the same run ID and resume
  events while the app-owned lifecycle monitor remains active; cancellation
  uses the existing supported operation; only an authoritative terminal
  result releases the hold.
- Nonvisual React/Wails acceptance through real bindings and the supported
  Execution Node path: start a run, cross the ordinary TTL boundary (using a
  bounded test clock/seam, not a two-hour wait), prove the same run remains
  observable and cancellable without restart/change, then prove credential
  release after terminal status. UI mocks or direct Go tests alone do not
  satisfy this acceptance gate.
- Confirm no credential bytes appear in project files, logs, events, output,
  or diagnostics. Run focused tests, relevant Go tests, frontend checks, and
  `git diff --check`.

## Non-goals

- Keep a UI session alive indefinitely after a run ends.
- Extend credentials for unrelated operations or silently reauthorize a
  changed project/node.
- Change remote controller lifecycle, execution cancellation semantics, or
  run persistence.

## Review identity

Repository base at plan creation: `f59d50186510bb1fe527a75a4726eb4488fb656c`.
Architecture review: `APPROVE_WITH_CHANGES`, finding
`SESSION-RUN-CREDENTIAL-01-001` (nonblocking). The plan incorporates its
clarification and was approved by the owner before implementation.

The owner approved this simpler implementation and explicitly declined another
review. Implementation uses one Broker slot with `STARTING` and
`RUNNING(runId)` states; the existing `ExecutionService.pendingStarts[planID]`
is the authority for retrying the same opaque `startAttemptID` after an
uncertain response. No second recovery store/API was added. A failed
local-record restoration after a proven non-dispatch releases SSH
authorization but leaves `PENDING` and blocks Start; a failed write after
acceptance keeps the exact `RUNNING(runId)` hold while the existing monitor
retries persistence. Focused Go tests, `go test ./...`, and `go vet ./...` pass.
Real React/Wails expiry-boundary acceptance remains pending.
