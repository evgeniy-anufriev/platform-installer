# UI-02 — Installation workflow architecture

Status: **FINALIZED — implementation NOT STARTED**. `UI02-PLAN-001` is
**RESOLVED BY OWNER DECISION**: credentialed Start uses versioned
`StartExecution/v1alpha2` before capability negotiation through
`ExecutionCapabilities/v1alpha2`. The initial PLAN review and its permitted
targeted recheck are complete; no further architecture review is run for this
exact owner-authorized correction.

UI-02 adds the operational Installation experience after UI-01's editor has saved a portable project. It is not a second desired-state model, planner, Ansible-output viewer, or workstation-to-target execution path.

## 1. Goal and scope

UI-02 exposes one lifecycle through four local views:

~~~text
Summary -> Plan -> Execution -> Result
~~~

An operator builds and reviews one fresh Core deployment plan, supplies its required acknowledgements, starts exactly that approved plan, follows typed progress, requests cancellation through the lifecycle contract, and inspects the terminal result for that exact runId.

The UI-01 mockup already contains Installation and its persistent Plan -> Execute -> Result strip. Its local tabs currently omit standalone Plan and Result views. UI-02A updates the design reference before implementing the screen, without adding Execution Node preparation to Installation.

Out of scope: project editing; Execution Node selection/preparation; service-specific panels; React file tailing; a generic secret store; direct workstation-to-target SSH; Core/Ansible semantic validation; and a durable global run-history database. The existing Logs page is a future retention slice; UI-02 Result covers a known run in the current application session.

## 2. Reused authority and seams

| Concern | Existing authority | UI-02 role |
| --- | --- | --- |
| Desired project | Portable project and guarded local writer | Read saved revision; never write it during installation. |
| Node selection/readiness | UI-01E4/E5 application context | Render a prerequisite and link to Servers; never prepare a node. |
| Plan | BuildDeploymentPlan and ExecutionService.CreatePlan | Trigger and safely project the result. |
| Approval/freshness | ExecutionService.ApprovePlan and one-shot Start replan | Collect exact acknowledgements; never treat Verify as authorization. |
| Execution | StartExecution, GetExecution, CancelExecution | Invoke only fixed lifecycle operations and render safe state. |
| Progress | Journal -> GetEvents -> RunObserver | Subscribe through Go; never parse callback text or files. |
| Operator mirror | .runtime/executions/<runId>/events.jsonl | Display path only as operator aid; React never opens it. |
| Target credential | In-memory runtimesecret.Broker | Show safe availability only; trusted Go resolves it internally. |

Incoming Core/protocol data is bounded and decoded by Go before a closed Wails projection. React receives no raw maps, Ansible stdout/stderr, callback data, secret values, private paths, or internal runtime-secret references.

## 3. State and bindings

UI-02 state is operational memory, not portable state:

~~~text
saved project revision + selected READY node + attested runtime
                         |
                         v
 PlanRecord (id, expiry, revision, fingerprint, acknowledgements)
                         |
                         v
 StartAttempt (startAttemptId, requestId, private leaseId)
                         |
                         v
 ExecutionRun (authoritative runId, state, sequence)
                         |
                         v
 RunObserver subscription / terminal execution evidence
~~~

The Go facade binds every plan to the open project root, canonical saved revision, selected node and attested runtime. It clears an active plan when project context changes or a semantic Save changes revision. The existing 15-minute plan TTL and mandatory fresh replan immediately before Start remain authoritative.

An active execution retains its immutable plan revision. A later Save may proceed under ADR-027, but UI shows ACTIVE_EXECUTION_USES_PREVIOUS_REVISION; it never alters, restarts or cancels that run. Navigation detaches the visual subscriber only. It never cancels remote work. A known runId can reconnect through GetExecution and RunObserver; after process restart UI-02 does not guess a current run from time or another deployment.

## 4. Closed installation state

The Wails facade owns a closed InstallationState containing safe status, exact bindings, bounded findings, plan summary, run summary and observer health.

| State | Meaning / allowed action |
| --- | --- |
| PREREQUISITES_REQUIRED | Missing saved project, clean session, READY node, attested runtime or required capability. Link to owner page only. |
| READY_TO_PLAN | Saved revision and READY attested node; build a fresh plan. |
| PLAN_BLOCKED | Fresh Core findings; reviewable but not approvable/startable. |
| PLAN_REVIEW | Fresh executable unexpired plan bound to revision/runtime. |
| PLAN_APPROVED | Exact acknowledgement set accepted; Start only. |
| PLAN_STALE_OR_EXPIRED | Discard and build a fresh plan. |
| STARTING, RUNNING, CANCELLING | One authoritative run with safe progress/cancel controls. |
| TERMINAL | SUCCEEDED, FAILED, CANCELLED, INTERRUPTED or safe corrupt/orphaned outcome; Result read-only. |
| OBSERVABILITY_DEGRADED | Overlay diagnostic; never converted into execution failure. |

Only ExecutionService decides expiry, approval equality, one-shot use, active-run exclusion and fresh-plan mismatch. UI cannot manufacture a plan, acknowledgement, terminal result or runId.

## 5. Wails contract and event path

UI-02 adds an application facade; React does not bind ExecutionService, RunObserver, ExecutionEvent or Broker directly. Its fixed operations are:

~~~text
GetInstallationState()
CreateInstallationPlan()
GetInstallationPlan(planId)
ApproveInstallationPlan(planId, acknowledgements[])
StartApprovedInstallation(planId)
GetInstallationRun(runId)
SubscribeInstallationRun(runId, afterSequence?)
UnsubscribeInstallationRun(subscriptionId)
CancelInstallationRun(runId)
~~~

The facade checks that IDs belong to the current app/session object and node/runtime binding still agrees before every mutation. It maps lifecycle and observer errors to closed safe UI codes plus bounded findings. It exposes neither generic Core/RPC, arbitrary GetEvents, shell nor filesystem operation.

SubscribeInstallationRun uses one existing RunObserver poller per node/run. It emits validated/redacted ExecutionEvent/v1alpha1 projections with increasing sequences, bounded subscriber capacity and separate EXECUTION_OBSERVER diagnostics. React may filter safe fields but may not infer terminal outcome or redact data itself.

## 6. Plan, approval, start and cancellation

~~~text
React -> Go: CreateInstallationPlan
      -> READY node: BuildDeploymentPlan
      <- revision/runtime-bound PlanRecord (EXECUTABLE or BLOCKED)

React -> Go: ApproveInstallationPlan(exact acknowledgements)
      -> ExecutionService.ApprovePlan

React -> Go: StartApprovedInstallation
      -> capability gate + fresh-plan/run attempt
      -> PutRuntimeSecretLease (only when target credential is required)
      -> idempotent StartExecution with startAttemptId/private leaseId
      <- authoritative runId + state
~~~

Plan shows only Core-provided actions, dependencies, target hosts, findings and acknowledgements. Blocked plans remain readable but never receive approval. Project Verify never skips, replaces or freshens planning. PLAN_STALE returns the user to Plan without starting work.

Cancellation is a request, not a local terminal state. UI prevents a duplicate request while it is in flight and follows GetExecution/events until the node reports terminal outcome. Closing UI, switching tabs, observer loss or mirror failure never cancels execution.

## 7. Required target-secret transport gate

The UI-01E3 broker has no transport capability. Existing ExecutionCapabilities/v1alpha1 and StartExecution/v1alpha1 remain immutable for readiness/planning and legacy execution. Credentialed UI-02 Start requires new closed execution-start/v1alpha2 and execution-capabilities/v1alpha2 contracts. Capabilities v1alpha2 is feature negotiation only: it cannot redefine either Start or lease protocol, and malformed/unsupported v1alpha2 fails closed without reinterpretation as v1alpha1.

### 7.1 StartExecution/v1alpha2

StartExecution/v1alpha2 is the closed successor for credentialed UI-02 Start. Its request inherits exact project, revision, plan, attested runtime and Execution-Node-private manifest binding. It requires startAttemptId and may carry private leaseId; it rejects caller-supplied runId. leaseId is required when the selected credential mode needs a target lease.

The closed response contains only status STARTED or ALREADY_STARTED, startAttemptId and the authoritative runId. The Execution Node alone generates runId. startAttemptId is the idempotency key: first Start validates exact binding and STAGED lease, generates runId, durably records startAttemptId -> runId plus immutable binding, atomically transitions STAGED -> ATTACHED(runId), durably commits, and only then permits controller launch. A same-attempt identical retry returns ALREADY_STARTED and that runId; incompatible reuse returns START_ATTEMPT_CONFLICT.

Before durable run/attach commit, no run exists and STAGED remains or is revoked only under the definite-failure rule. After that commit, no path rolls back to no run: a launch failure transitions the same run through normal FAILED or INTERRUPTED lifecycle. A lost response or controller restart is resolved by repeating the same startAttemptId and returns the same runId. This durable mapping lives in existing controller-private run state, not a new database.

### 7.2 ExecutionCapabilities/v1alpha2 gate

ExecutionCapabilities/v1alpha2 is a closed envelope with all v1alpha1 identity/operation semantics plus required executionStart.protocol = StartExecution/v1alpha2 and optional targetCredentialLease. When present, targetCredentialLease is closed and contains protocol = PutRuntimeSecretLease/v1alpha1, payloadVersions = [TargetCredentialLeasePayload/v1alpha1], positive bounded maxPayloadBytes, and requiredStartProtocol = StartExecution/v1alpha2. It does not carry a redundant idempotency flag because StartExecution/v1alpha2 normatively guarantees it.

Credentialed UI-02 Start is permitted only with an attested v1alpha2 reply containing compatible executionStart, targetCredentialLease, Put protocol, payload version and a maxPayloadBytes value sufficient for the actual bounded payload. Valid v1alpha1 and v1alpha2 without targetCredentialLease may plan where otherwise valid but block credentialed Start. There is no fallback to StartExecution/v1alpha1 or workstation-to-target SSH.


### 7.3 Attempt and lease protocol identities

The workstation creates one opaque startAttemptId after the service confirms the approved plan is still fresh and before remote Start. This removes run-ID circularity: a STAGED lease binds selected Execution Node, attested runtime identity, project identity, saved project revision, exact approved/fresh plan fingerprint and startAttemptId. It does not bind a runId before Start.

The closed PUT request metadata is:

~~~text
PutRuntimeSecretLease/v1alpha1
  requestId              idempotency key
  startAttemptId         opaque Start correlation
  projectIdentity
  projectRevision
  planFingerprint
  executionNodeId + attested runtime identity
  payloadVersion         TargetCredentialLeasePayload/v1alpha1
  payloadLength          bounded by advertised maximum
~~~

The body travels only through authenticated workstation-to-Execution-Node SSH stdin as one bounded TargetCredentialLeasePayload/v1alpha1:

~~~text
username
exactly one of password | privateKey
optional sudoPassword
~~~

No arbitrary secret map is accepted. Secret bytes never enter argv, environment, project files, journal, mirror, results or diagnostics.

The closed Go-side response is:

~~~text
requestId
startAttemptId
status                  STORED | ALREADY_STORED
leaseId                 opaque, application/controller-private only
stagedExpiresAt
~~~

leaseId is never a pathname and never crosses the Wails/React facade.

### 7.4 Node-owned lease state machine

~~~text
no lease --complete accepted PUT--> STAGED
STAGED --atomic successful Start--> ATTACHED(authoritative runId)
STAGED --definite rejection/expiry--> REMOVED
ATTACHED(runId) --terminal or recovered interrupted terminal--> REMOVED
~~~

An incomplete stdin transfer creates no usable lease. Retrying the same requestId with identical metadata and body after a lost response returns ALREADY_STORED with the same private lease identity and does not rewrite it. Reusing requestId with incompatible metadata or payload fails closed with REQUEST_ID_CONFLICT (or a fixed equivalent).

StartExecution/v1alpha2 carries startAttemptId and, only when a target credential is required, private leaseId, alongside its exact project/revision/plan/runtime/manifest binding. The node's durable Start transaction atomically validates a non-expired STAGED lease and all bindings, creates-or-finds the run for startAttemptId, and transitions the lease to ATTACHED(runId). The execution process cannot start before this transition succeeds. A definitive pre-commit failure leaves no execution running and revokes the STAGED lease.

startAttemptId is the Start idempotency key. A lost or unknown Start response is resolved or retried only with that same attempt; the node returns the same authoritative runId if it already created one. The Installer neither uploads another lease under a new request ID nor issues an unrelated Start. If it is definitively established that no run was created, it revokes the still STAGED lease. This prevents a transport timeout from creating duplicate work.

### 7.5 Cleanup and expiry

stagedExpiresAt applies only to STAGED. Expiry before Start securely removes the lease and Start fails with LEASE_EXPIRED; the user needs a fresh attempt and transfer. Once ATTACHED, staging expiry cannot remove credentials while the controller uses them: lifetime is owned by the authoritative run and ends only at terminal outcome or lifecycle recovery of an interrupted/orphaned run.

A Cancel request alone does not remove an ATTACHED lease. Project/UI navigation also does not remove it. Cleanup is performed only once lifecycle evidence proves the run no longer uses it: terminal state, or recovery establishing its terminal/interrupted result. The node keeps lease files outside project and journal in private 0700 runtime state with 0600 material, and excludes them from callback, journal, mirror, result and diagnostics.

This is a fixed narrow protocol, not a vault, per-host credential map, generic upload, renewal service or durable secret store.

### 7.6 Required failure contract and proof

| Situation | Required node/Installer outcome |
| --- | --- |
| Legacy StartExecution/v1alpha1 | Remains unchanged; it cannot authorize credentialed UI-02 Start. |
| v1alpha2 request with caller runId | Closed schema rejects it before any lifecycle work. |
| First v1alpha2 Start | Node generates runId only after durable attempt/run and STAGED -> ATTACHED commit. |
| PUT committed, response lost | Same requestId/startAttemptId retry returns ALREADY_STORED and same private lease identity. |
| Partial stdin body | No usable lease is published. |
| requestId reused incompatibly | Fail closed; do not replace the original lease. |
| PUT succeeds, Start definitively rejected | Revoke the STAGED lease; no run and no target execution. |
| Start response lost, run exists | Same startAttemptId resolves/retries to the same runId; do not PUT again. |
| Controller restart after committed Start | Same startAttemptId returns the persisted authoritative runId. |
| Post-commit controller launch failure | Keep the one authoritative run and transition it through FAILED/INTERRUPTED. |
| Start response unknown, run absent | Retain STAGED until authoritative resolution; revoke only after definitive no-run proof. |
| STAGED reaches expiry | Remove it and return LEASE_EXPIRED; require a new attempt. |
| ATTACHED run outlives staging TTL | Retain credentials while RUNNING; terminal/recovery owns cleanup. |
| Cancel accepted, run nonterminal | Retain ATTACHED lease until terminal/recovery. |
| Capability v1alpha1 | Planning/readiness can proceed; credentialed Start is blocked. |
| v1alpha2 absent lease / malformed capability / unsupported protocol or payload / invalid maximum | Planning remains available only where otherwise valid; credentialed Start fails closed without v1alpha1 fallback. |

UI-02C acceptance includes protocol/schema compatibility; old/new/malformed capability replies; v1alpha2 caller-run rejection; request/Start retry and failure injection at every transition; password/private-key/no-log RED OS proof; terminal/cancel/expiry/interrupted recovery cleanup; and a production-boundary case proving target work cannot start without atomic lease attachment. It additionally proves no secret, private reference or filesystem path is present in Wails projections, journal, event mirror, diagnostics or terminal result.


## 8. Presentation rules

Summary shows saved revision, optional Verify state, node prerequisite and one fresh-plan action. Plan shows exact revision/runtime binding, expiry, actions/dependencies/hosts, findings and acknowledgements. Execution prioritizes phase/action progress and current safe task/host; details are collapsed and a task start may omit host. Result binds outcomes and Verify to one runId and never reruns Verify on view.

The terminal execution result is authoritative. Observer disconnect, history truncation, slow subscriber and local mirror failure are explicit diagnostics, not FAILED. For no_log, UI uses only existing safe task fields; it never reconstructs task details.

## 9. Delivery slices

| Slice | Boundary | Non-goals |
| --- | --- | --- |
| UI-02A | Mockup reconciliation, closed Wails DTO/facade and read-only Installation state/plan display. | No Start, secrets or target contact. |
| UI-02B | Fresh plan, bounded plan projection, acknowledgement and approval. | No Start/cancel or lease transport. |
| UI-02C | Complete PutRuntimeSecretLease/v1alpha1 and idempotent Start correlation, capability gate, atomic attach, cleanup/recovery and RED OS security proof. | No UI Start, generic secret system/history. |
| UI-02D | Approved Start, RunObserver Wails subscription, cancellation, Execution/Result views. | No raw log stream or durable run index. |
| UI-02E | Windows/RED OS production-shaped workflow, reconnect/degradation and secret/redaction acceptance. | No new service/editor feature. |

UI-02C precedes UI-02D so no UI Start reaches targets before capability negotiation, PUT idempotency, idempotent Start correlation, atomic attach, cleanup/recovery and attached-run expiry semantics are proven. UI-02B remains useful without target credentials because planning is target-free.

## 10. Acceptance and owner decisions

- A/B: fresh revision/runtime binding; blocked plans cannot start; Verify never authorizes execution.
- C: password/key bytes use only fixed bounded stdin lease transport. It proves complete/lost/conflicting PUT, definite/unknown Start outcomes, same-attempt Start replay, staged expiry, attached-run expiry, terminal/cancel/recovery cleanup, and no secret/reference in Wails DTOs, argv, environment, project, journal, mirror, diagnostics or result.
- D: Start is one-shot/replan-protected; navigation detaches without cancel; replay/reconnect preserves sequence; observer degradation cannot alter remote outcome.
- E: a supported full lifecycle proves plan, approval, apply, Verify, Result and repeat changed=0, without touching unrelated deployments.

Before implementation, owner confirms: (1) A -> B -> C -> D -> E order; (2) no inferred current run or durable run index after process restart; and (3) whether first Result is lifecycle/terminal evidence only, with Logs retention deferred to a separately approved slice.
