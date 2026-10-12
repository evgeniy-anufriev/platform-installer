# Execution planning, protocol and events

Contract sections extracted verbatim from [UI-BE-04](../work/ui-backend/ui-be-04.md).
Current status and authorization remain in [CURRENT_STATE](../../CURRENT_STATE.md).
Implementation audit and milestone gates are retained separately.

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
