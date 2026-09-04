# UI-BE-04: validation, planning, execution and events

UI-BE-04 is split into five independently gated milestones:

1. UI-BE-04A — Execution Architecture Audit;
2. UI-BE-04B — Core Deployment Planning;
3. UI-BE-04C — Execution Node Runtime Protocol;
4. UI-BE-04D — Go ExecutionService;
5. UI-BE-04E — Production E2E.

UI-BE-04A freezes the boundaries below. It adds no production planning,
execution, session, journal, cancellation or frontend implementation.

## Current implementation audit

The accepted EXEC-01A implementation provides a pre-Core bootstrap and a
narrow synchronous service acceptance path:

```text
Go workstation
  -> explicit host-key-checked SSH/SCP
  -> /var/lib/platform-installer/runtime/releases/<bundle-digest>
  -> atomic runtime/current activation
  -> Core capability check
  -> target repository probe
  -> existing artifact resolver
  -> target-filtered RuntimeProjection
  -> fixed Kafka/Keepalived playbook allowlist
  -> shared Ansible artifact source gate
  -> service role
```

`executionnode.Service` owns readiness and digest-bound preparation plans.
`ServiceExecutionService` performs one target repository probe per requirement,
uses `artifactsource.ResolveForNode` as the sole source-selection authority,
builds an ephemeral target-filtered projection and stops a `BLOCKED` result
before transport. `platform.core.artifact_source_gate` independently blocks an
invalid projection before service mutation, while
`platform.core.artifact_delivery` verifies offline bytes on the target.

The current `OpenSSHTransport.ExecuteService` is synchronous. It stages a
project and runtime extra-vars under `/var/tmp`, maps Kafka and Keepalived to
specific playbook and collection paths in Go, waits for `ansible-playbook`,
and returns only a Boolean. It has no deployment plan, run identity, machine
events, terminal result, durable process ownership, journal, replay, reconnect
or cancellation. It remains an EXEC-01A regression path and is not the future
UI-BE-04 execution API.

The published `DeploymentPlan`, `ExecutionEvent` and `DeploymentResult`
schemas are unused architecture foundations. The activated runtime currently
advertises only `validate`. Core has target-free validation and snapshot
entrypoints, but no `BuildDeploymentPlan`, private execution manifest or fixed
execution controller.

## Missing capability matrix

| Missing capability | Authoritative future owner | Delivery gate |
| --- | --- | --- |
| Deterministic public plan and semantic fingerprint | Core | UI-BE-04B |
| Private trusted execution graph/manifest | Core plus package-owned lifecycle declarations | UI-BE-04B |
| Fixed semantic remote operations and compatibility negotiation | Execution Node Core runtime | UI-BE-04C |
| Detached owned process and immutable-release binding | Execution Node Core runtime/systemd | UI-BE-04C |
| Journal, status, event replay, result, cancel and recovery | Execution Node Core runtime | UI-BE-04C |
| Public plan TTL, approval, session/subscriber and stale-plan lifecycle | Go Installer | UI-BE-04D |
| Real integrated execution/reconnect/cancel proof | Existing Core, EXEC-01A and service paths | UI-BE-04E |

## EXEC-01A reuse matrix

| Capability | Classification | UI-BE-04 boundary |
| --- | --- | --- |
| Execution Node identity and selection | REUSE AS-IS | Same node and credential-reference model. |
| Readiness and preparation | REUSE AS-IS | Preparation remains a separate pre-Core lifecycle. |
| SSH/SCP, host-key trust and elevation | REUSE AS-IS | Future operations use the same hardened transport primitives. |
| Fixed bootstrap/runtime paths | REUSE AS-IS | Active immutable runtime remains `/var/lib/platform-installer/runtime/current`. |
| Bundle staging, verification, activation and digest | REUSE AS-IS | Runs bind to an activated digest; they never mutate the bundle. |
| Repository probe | REUSE AS-IS | Still one read-only target-scoped probe per requirement at execution time. |
| Artifact resolver and RuntimeProjection | REUSE AS-IS | Remain the only source-selection path and derived runtime input. |
| `artifact_source_gate` and `artifact_delivery` | REUSE AS-IS | Service packages consume an already resolved projection. |
| Capability handshake | EXTEND | Add only fixed versioned semantic operation names and compatibility data. |
| Project/run staging | EXTEND | Add immutable run-scoped staging bound to project, plan and manifest identities. |
| Status, events, replay and result | DONE | Implemented on the Execution Node in UI-BE-04C. |
| Durable process ownership, cancel and recovery | DONE | Implemented with a fixed detached Core controller in UI-BE-04C. |
| Core DeploymentPlan and ExecutionManifest | MISSING | Implement target-free in UI-BE-04B. |
| Go plan approval/session service | MISSING | Implement only after B and C in UI-BE-04D. |
| Synchronous `ExecuteService` | DEPRECATE FOR UI-BE-04 | Retain for EXEC-01A regression until the generic path is proven; do not copy its service mapping. |
| Existing service apply/verify/reconcile entrypoints | REUSE UNDER CORE | Service packages retain lifecycle; Core invokes trusted package-owned entrypoints through its private graph. |

The current service manifests expose role entrypoints, but several accepted
service lifecycles contain validation, PKI, discovery, barriers or provider
reconciliation outside a role invocation. UI-BE-04B must therefore add the
smallest package-owned declaration of trusted lifecycle entrypoints needed by
Core. Core composes those declarations into the private execution graph. Go
must not infer playbooks from filenames or maintain another service allowlist.

## Authoritative ownership

### Go Installer

Go owns application semantics: remote protocol client calls, public PlanStore,
TTL, review, acknowledgement collection, one-shot approval, run/session IDs,
subscriber management, replay and reconnect requests, stale-plan detection and
the semantic cancel request. It may coordinate Core operations but does not
interpret infrastructure semantics.

### Platform Core

Core owns authoritative project validation, deployment planning, ordered
phases/actions/dependencies, mutation semantics, the trusted execution graph,
the public `DeploymentPlan`, private `ExecutionManifest`, semantic plan
fingerprint and fixed controller behavior. Core derives both plan and manifest
from one resolved semantic model.

### EXEC-01A

EXEC-01A continues to own Execution Node bootstrap/readiness, transport
foundations, immutable bundle activation, target repository probing, artifact
resolution, target-filtered RuntimeProjection and offline artifact delivery.
Source selection happens during execution after a plan has been accepted.

### Ansible and service packages

Service packages own service-specific install, configuration, validation,
mutation, verification and lifecycle barriers. Their standalone entrypoints
remain usable without Go. Core may order and invoke trusted package operations;
it must not move their service semantics into a generic Python reimplementation.

Go is explicitly prohibited from owning role ordering, playbook paths, the
service execution graph, provider order, Kafka/PostgreSQL semantics,
repository/bundle re-resolution or human Ansible output parsing.

For mutating Installer execution, `projectIdentity` must come from explicit
canonical project metadata and remain stable across staging and revisions. The
current snapshot basename fallback is suitable for a local read-model label,
but not for cross-client mutation locking because a temporary remote directory
can change it. A project without an explicit stable identity may still use the
standalone Ansible entrypoints, but Core planning for Installer-managed
mutation returns `PROJECT_IDENTITY_REQUIRED` until identity is provided in the
portable contract.

## DeploymentPlan and ExecutionManifest

The future target-free Core path is:

```text
portable Ansible project
  -> ValidateProject
  -> BuildDeploymentPlan
  -> public DeploymentPlan
  +  private ExecutionManifest
```

`DeploymentPlan` is safe, deterministic, immutable, reviewable and free of
target contact and target runtime state. It contains project and planner
identity, semantic fingerprints, ordered public phases/actions/dependencies,
logical targets, mutation/reboot semantics, artifact requirements, credential
references and purposes, required acknowledgement IDs and findings/blockers.

`ExecutionManifest` is private, trusted and execution-only. It contains the
Core-selected operation handles and runtime inputs needed by the fixed
controller. It is canonically serialized, digest-addressed and bound to the
public plan through `planFingerprint`. It contains no resolved secret values.
Go receives neither its trusted entrypoints nor a means to construct it and
must never derive it from the public plan.

### Existing plan contract audit

`contracts/plan/v1alpha1` already supplies phases, actions, dependencies,
mutation/reboot flags, credential references, acknowledgements, findings and
project/catalog/artifact/Core/plan fingerprints. UI-BE-04B should evolve this
single alpha contract rather than create a second plan DTO:

- add explicit `projectRevision`, stable `projectIdentity`, planner/protocol
  identity and reviewable artifact requirement identities;
- add credential purpose while retaining references only;
- define `acknowledgements[*].code` as the stable acknowledgement ID;
- define `readiness` as static planning readiness only;
- remove `factsSnapshots`, because observed target facts are not plan inputs;
- remove `packageSource`, because `REPOSITORY` versus `OFFLINE_BUNDLE` is an
  execution-time result, not a planning decision;
- retain `id` and `createdAt` as nonsemantic envelope metadata excluded from
  the plan fingerprint.

No playbook path, argv, shell fragment, secret value, resolved SecretRef,
repository probe result, active-bundle cache path or transient path may appear
in the public plan.

## Semantic plan fingerprint

Core computes `fingerprints.plan` as SHA-256 over canonical JSON containing
only semantic planning data:

- plan contract/API and Core planning-protocol versions;
- stable project identity and exact `projectRevision`;
- relevant catalog and service-definition fingerprints;
- required artifact identities and compatibility constraints;
- ordered phase/action IDs, logical targets and dependencies;
- mutation/reboot semantics;
- required credential references and purposes;
- required acknowledgement IDs and semantics.

The hash excludes plan/run IDs, timestamps, localized/display text, summaries,
temporary paths, Execution Node cache paths, event sequences, SSH sessions and
selected repository/bundle sources. Artifact or bundle requirement identity
may affect the hash; whichever current cache directory satisfies it may not.

Changing ordering or any included semantic input changes the fingerprint.
Reordering maps, regenerating display text or rebuilding the same plan at a
later time does not.

## Target-free planning invariant

`BuildDeploymentPlan` runs on the Execution Node as a controller-only Core
operation, but it must not contact managed targets, run repository probes,
refresh facts, check service health or resolve runtime source availability.
It must pass the same network-isolated acceptance as validation.
This target-contact-free property is part of the operation contract, not only
a test convention.

Planning may state that Kafka 4.3.1 and Java 21 are required on a logical node.
It must not state that either source is `REPOSITORY` or `OFFLINE_BUNDLE`.
Observed readiness and drift remain separately versioned runtime observations;
they do not make the immutable plan nondeterministic.

## Fixed Execution Node machine protocol

UI-BE-04C extends the capability handshake with exactly these semantic
operations:

- `GetCapabilities`;
- `ValidateProject`;
- `BuildDeploymentPlan`;
- `StartExecution`;
- `GetExecution`;
- `GetEvents`;
- `CancelExecution`.

There is no `RunCommand`, `RunShell`, `RunPlaybook`, `RunAnsible`, arbitrary
argv or caller-supplied executable path. Requests and responses are versioned
JSON. Ordered event replay is JSONL or an equivalent structured response.
Stdout is reserved for the machine protocol; stderr is bounded, sanitized
diagnostic material and never parsed for state.

Every operation validates protocol compatibility and its minimum required
capability before changing state. Unsupported operations fail semantically and
do not fall back to arbitrary SSH execution.

## Detached controller and process ownership

`StartExecution(runId, projectIdentity, planFingerprint)` verifies the staged
project and Core-created private manifest, then starts one fixed Platform Core
execution controller in a transient systemd unit. Go cannot make systemd run
`ansible-playbook` or a path supplied by the client. The fixed controller reads
the trusted manifest and invokes existing Core/service operations.

The controller binds to the exact immutable runtime release and bundle digest
verified at start; it does not follow `runtime/current` after launch. Runtime
activation or retention must not remove a release referenced by an active run.

The transient unit uses control-group ownership (`KillMode=control-group` or a
proved equivalent) and collection after exit where supported. A run is owned
only when all of these agree:

- run ID;
- stable project identity;
- plan fingerprint;
- private manifest digest;
- controller-owned journal identity;
- transient systemd unit identity.

A PID alone is never authority. A mismatched or missing journal must not be
attached to or killed merely because a process or unit name resembles a run.

## Journal, states and retention

Durable run state belongs under the existing noncanonical Execution Node state
root, conceptually:

```text
/var/lib/platform-installer/execution/runs/<runId>/
  metadata
  private manifest or secure manifest reference
  status
  ordered events
  terminal result
```

Exact filenames remain a UI-BE-04C implementation detail. Directories are
root/controller-owned and private files are mode `0600`. Journal writes are
atomic; events are append-only with a monotonically increasing sequence; one
terminal result is committed exactly once. Journals, events and diagnostics
must not contain secret values.

Project-local or workstation `.runtime/runs` is not the durable authority;
that location may hold only disposable client/QA state. The Execution Node
journal remains available when the Installer workstation is absent.

State is one of `RUNNING`, `SUCCEEDED`, `FAILED`, `CANCELLED`, `INTERRUPTED`
or `CORRUPT_ORPHANED`. Terminal metadata/results are retained by bounded age
and count. Detailed progress and diagnostics have a separately bounded byte
and event limit. If requested history was pruned, `GetEvents(afterSequence)`
returns the current execution state plus the earliest available sequence; it
does not fabricate a complete replay.

Recovery rules are deterministic:

- `RUNNING` plus the matching owned unit means reconnect;
- journal `RUNNING` plus no owned unit becomes `INTERRUPTED` exactly once;
- an owned-looking unit without a valid matching journal/manifest becomes
  `CORRUPT_ORPHANED` and is not trusted or killed automatically;
- a terminal journal is never returned to `RUNNING`;
- cleanup removes only terminal retained state selected by the retention
  policy and never an unrelated unit or active runtime release.

## Disconnect, reconnect and duplicate prevention

Installer exit, SSH loss or subscriber disconnect is not cancellation. The
detached controller continues. A restarted Installer discovers the active run,
calls `GetExecution`, then calls `GetEvents(afterSequence)` to resume.
`GetExecution` supports lookup by known run ID and active-run discovery by
stable project identity; it does not enumerate unrelated projects.

The Execution Node, not only Go, enforces at most one active mutating run for
the same Core-produced project identity. Competing clients receive
`ACTIVE_RUN_EXISTS` with the existing run ID as safe metadata. Repeating
`StartExecution` with the same run ID and matching identities is idempotent;
the same run ID with different identities is rejected as tampering.

## Events and cancellation

Execution events use the existing `ExecutionEvent/v1alpha1` semantic fields:
run and plan identity, monotonic sequence, phase/action/target, status, bounded
safe message and redaction metadata. An Ansible callback may normalize task
events, but human recap text is never the API. Slow or disconnected Go/UI
subscribers cannot block the controller because replay comes from the bounded
Execution Node journal and each Installer subscriber has a bounded buffer.

`CancelExecution` verifies the complete run ownership tuple, records the
request, asks the fixed controller/unit to stop gracefully, then uses owned
control-group termination if needed. It cannot address an arbitrary PID or
unit. Successful cancellation leaves no owned child process and commits one
terminal `CANCELLED` result. Later cancellation requests return that terminal
state without creating another result. SSH disconnect alone never invokes it.

## UI-BE-04D - Go ExecutionService

UI-BE-04D adds a separate deployment PlanStore and ExecutionService rather
than overloading UI-BE-03 EditPlans or EXEC-01A preparation plans. Stored plans
are public, opaque, bounded, concurrency-safe and expiring. Approval binds the
exact plan fingerprint and exact acknowledgement IDs.

Immediately before execution, Go asks Core to build a fresh plan. Only equality
of the complete Core-produced semantic fingerprint permits `StartExecution`;
partial field comparison is not authoritative. A mismatch returns
`PLAN_STALE`. Approval is consumed once the Execution Node accepts the start;
it is never silently reused for a later run.

Go owns local session/subscriber state and requests replay/reconnect/cancel.
The Execution Node journal remains authoritative after workstation failure.
No SQLite or other store becomes desired-state or execution-semantics
authority.

The accepted implementation uses a separate public deployment-plan store. It
keeps plan metadata, public runtime-release identity and acknowledgement codes;
the private ExecutionManifest is never decoded or retained. Approval is an
exact-set one-shot. Start rebuilds immediately through the Core adapter,
compares the complete Core fingerprint, and only then calls semantic
StartExecution. Sessions use bounded sequence-ordered replay/reconnect and
semantic cancellation. Slow subscribers are closed deterministically; Go owns
no polling goroutine or process/systemd implementation.

## UI-BE-04E acceptance design

The primary production fixture is the existing isolated Kafka deployment and
its proven offline artifact:

```text
ValidateProject
  -> BuildDeploymentPlan without target contact
  -> review and one-shot approval
  -> fresh plan fingerprint match
  -> StartExecution
  -> detached fixed controller and structured events
  -> existing target probe/resolver/RuntimeProjection
  -> Kafka OFFLINE_BUNDLE delivery and target SHA-256
  -> apply and verify
  -> terminal DeploymentResult
  -> repeat apply changed=0
```

Acceptance additionally proves SSH disconnect survival, status/event replay
after Installer restart, stale-plan rejection, private-manifest tamper
rejection, exactly one terminal result, safe cancellation of the owned control
group, no remaining child process, a subsequent allowed run and Execution Node
enforcement of one mutating run per project. Current EXEC-01A Kafka,
Keepalived and `BLOCKED` paths remain regression gates.

## Submilestone gates

- **UI-BE-04A — DONE:** actual implementation audit and boundary freeze; no
  production execution code.
- **UI-BE-04B — DONE:** `platform.core.build_deployment_plan` composes the
  authoritative target-free ProjectSnapshot with the same full service catalog
  and immutable runtime-release metadata. It publishes only
  `DeploymentPlan/v1alpha2`; its private in-memory `ExecutionManifest` is
  Core-owned and represented publicly only by a digest. The plan uses explicit
  `EXECUTABLE`/`BLOCKED` status, and no manifest exists for blocked validation
  or missing `project.yml.metadata.id`. It has no target facts, source result,
  secret, path, argv or playbook identity. The semantic fingerprint includes
  canonical project identity/revision, catalog, artifact requirements, ordered
  Core actions/dependencies and immutable bundle release identity, but excludes
  timestamps and `runtime/current`. The standalone machine entrypoint is
  `ansible-core/playbooks/deployment-plan-machine.yml`.
- **UI-BE-04C — DONE:** fixed Execution Node protocol, Core-owned trusted
  manifest dispatch, immutable run ownership, detached controller,
  journal/events/replay/cancel/recovery and bounded retention. RED OS acceptance
  proved disconnect/reconnect, terminal replay, whole-cgroup cancellation,
  duplicate-run rejection, interrupted recovery, foreign-unit safety and
  transient `--collect`. The controller never accepts a client command,
  playbook path or argv; source selection remains outside it and service
  dispatch consumes the existing staged runtime projection.
- **UI-BE-04D — DONE:** Go public deployment-plan store, exact one-shot
  approval, fresh Core fingerprint guard, typed Execution Node lifecycle,
  bounded ordered subscriptions, replay/reconnect and semantic cancel. Focused
  tests cover expiry, acknowledgement and stale-plan rejection, approval
  reuse, replay, overflow, unsubscribe and cancellation.
- **UI-BE-04E — GATED:** real Kafka production E2E and full regression.

UI-BE-04 overall is not complete. UI-BE-04D requires a separate owner request.
