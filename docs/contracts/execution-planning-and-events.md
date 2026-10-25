# Execution planning, protocol and events

## Application library progress

`plan/v1alpha10` adds optional `progressSteps: [{id, summary}]` to
`applications:apply`. `execution-capabilities/v1alpha13` advertises
`applicationProgress` (`ApplicationProgress/v1alpha1`, planContract v1alpha10).
The existing Build request and execution manifest versions are unchanged.
Older plan versions remain readable. Steps are immutable display metadata bound
to the plan fingerprint, not additional executable operations or dependencies.

Steps are shared preparation (`applications:prepare`) followed by installed
libraries in Core order (`applications:library:<libraryId>`). Referenced skipped
providers retain their callbacks, without an installation progress step. Verify
and post_install stay ordinary actions. Existing ACTION_STARTED/ACTION_COMPLETED
events carry the step ID; ordinary TASK events retain the parent action ID.
Core's callback accepts only tagged built-in markers with a closed nonsecret
payload. Linear multi-host execution emits completion once after successful work
on all hosts. A failed or skipped marker never confirms a successful step.

UI counts leaf work units, never both parent and children. Parent operation
outcomes remain visible, but cannot infer missing child completion. Failure may
arrive as TASK failure, diagnostic and terminal run state without a failed parent
ACTION_COMPLETED event. No new execution, retry, cancellation or persistence
mechanism is introduced. See the [implementation plan](../work/application-libraries/library-progress-plan.md).

Contract sections extracted verbatim from [UI-BE-04](../work/ui-backend/ui-be-04.md).

## A8 mixed Core execution extension

The accepted [A8 plan](../work/application-libraries/milestones/a8/a8-technical-plan.md)
extends standalone Core with one mixed run, not a second lifecycle. Infrastructure
Apply/Verify operations keep their existing order. The final applications phase
contains fixed APPLICATION_LIBRARIES_APPLY/VERIFY operations; its Apply depends
on every infrastructure Verify, including unrelated providers. A failure or
cancel prevents transition. No barrier play or scheduler is introduced.

Mixed Build uses execution-runtime/v1alpha3 and produces plan/v1alpha4 plus the
closed execution-manifest/v1alpha2. Source metadata applicationVaultSources is
runtime-only and fingerprint-bound. Established v1alpha2 Build and v1alpha6
capabilities remain infrastructure-compatible; v1alpha3 capability requests
advertise mixed execution as v1alpha7. Go/UI support remains later work.

After the Verify barrier, the controller materializes application inputs from
the operator lease or exact current-run/provider Vault bootstrap output. Only
admin-token crosses that handoff; unseal shares remain service-only. Temporary
inputs follow existing cleanup; durable bootstrap outputs retain delivery policy.
The service and application scopes use the same approved SSH trust and protected
run identity. Existing events carry applications phaseId/actionId without a
fictional serviceDeployment. Repeats require fresh Build/approval/run.
Current status and authorization remain in [CURRENT_STATE](../../CURRENT_STATE.md).
Implementation audit and milestone gates are retained separately.

## B3 shared Go lifecycle and presentation

The existing CreateInstallationPlan(order) retains its legacy request behavior.
CreateInstallationPlanForMode accepts an InstallationPlanRequest with explicit
executionMode, deploymentOrder and applicationVaultSources (source policy only,
never values). FULL_PROJECT, APPLICATION_LIBRARIES_ONLY and the existing
INFRASTRUCTURE_VERIFY_ONLY capability reuse the same plan store, approval,
StartApprovedInstallation, trust staging, typed lease, Cancel and reconnect.
Unsupported mode runtimes fail without a full-install fallback. No frontend
command/playbook or parallel execution lifecycle is introduced.

ExecutionService keeps the mode/source request privately with the reviewed plan
and clones caller-owned maps. Before Start it rebuilds that exact request through
the B1 mode-aware adapter, requiring executable current revision/identity and the
approved fingerprint. Core owns evidence freshness, admission and operation scope;
its Start lock and controller checks remain authoritative. PENDING intent is still
written by the ordinary desktop Start before remote dispatch; uncertain Start
reuses the existing start attempt/lease and existing recovery protocol.

InstallationPlanView adds executionMode and the validated Core infrastructure
verification observation (coverage, source run IDs, dates and safe reason code),
separate from the current execution run ID. Phases/actions are actual Core output;
Go never fabricates successful skipped infrastructure actions. The observation time
is the Build record timestamp. Cache failure is a warning on initial publication,
not execution permission or a replacement Core result.

The B1 bounded local observation cache is updated only from a fresh Core plan.
GetInfrastructureVerification returns previously observed data with current
availability UNKNOWN, including after reopen/offline; cache cannot grant admission.
Binding includes project/root, host identity and runtime, not operator account.
Failed/corrupt/unavailable cache remains UNKNOWN. A library run does not erase this
separate observation. No cache-only readiness predicate or Start branch exists.

UI design/mockups currently describe the common mixed flow. The approved B plan
records mode selection/summary as a later UI amendment: B3 supplies backend types
and lifecycle only; B4 production transport integration/real bridge acceptance and
C visual screen implementation remain separate gates. Browser RPC/frontend
bindings and visuals are not claimed as accepted by Go unit harnesses.

## B0 cross-run infrastructure verification

Owner-approved [B plan](../work/application-libraries/milestones/b/b-technical-plan.md)
adds a separate, negotiated `execution-runtime/v1alpha4` Build request with closed
`executionMode`: FULL_PROJECT, APPLICATION_LIBRARIES_ONLY or INFRASTRUCTURE_VERIFY_ONLY.
It produces plan/v1alpha5 and execution-manifest/v1alpha3. GetCapabilities v1alpha4
returns execution-capabilities/v1alpha8; older requests and A8 semantics stay unchanged.
Start still uses StartExecution/v1alpha2, staged SSH trust and the existing typed lease.

Core computes one infrastructure model from resolved service Apply/Verify operations,
full deployment coverage, runtime, connections, artifact authorities and PKI plans.
Project revision/application operations do not substitute for this model. B0 keeps
an operational index under `<execution-state>/infrastructure-verification/`, keyed
by project identity. It holds generation, model and references to bounded private
run proofs. It is derived execution evidence, never portable desired state.

A mutating infrastructure run invalidates the prior generation once before its
first target operation. Sequential Apply/Verify pairs of that same run share one
generation. Verify-only can complete that generation without Apply or PKI mutation;
a different model or approved host keys starts a new verification generation.
Verify results are published only after durable terminal state. Partial results
from a terminal FAILED run can supplement other Verify-only runs; FAILED remains
FAILED. Missing/corrupt/retained-away journals fail closed; an interrupted index
update may lose readiness but cannot imply success or replay work.

Library-only Build uses saved Verify coverage when it is complete and compatible.
Under the existing active-run admission lock, Start rechecks that evidence revision,
source journals and approved SSH host keys before controller launch. When compatible
saved evidence is absent or stale, the same authoritative plan includes fixed
SERVICE_VERIFY operations for every enabled infrastructure deployment before the
fixed library Apply/Verify suffix. This is one plan, approval and run; no second
Verify-only plan is created. Infrastructure Apply is never included. Core's normal
phase failure/cancel handling prevents library operations from starting if infra
Verify fails. Local client JSON is never accepted as proof. Arbitrary playbook or
command input and skipBarrier remain forbidden.

Library-only contains exactly application Apply and Verify; Vault sources must be
RUNTIME_INPUT. Unseal shares and CURRENT_RUN_BOOTSTRAP have no application producer
in that scope. Verify-only retains the established typed service-input declaration
contract, but dispatch contains no Apply capable of consuming Apply permissions.
PKI materialization is excluded; service Verify reads existing PKI. The existing
PKI_STORE_PASSWORD requirement remains in the same runtime lease when needed to
open existing PKCS12 stores or publish a library's PKI-derived shared credential;
retaining that input does not add a PKI or infrastructure Apply operation. Historical
Verify does not promise continuous target health: normal provider/ownership/readiness
guards remain. Build and evidence inspection stay target-contact free.
Library-only retains the existing project SERVICE_PASSWORD inputs for its provider
hooks through the same approved lease. Saved infrastructure Verify does not replace
those credentials; Apply-only service inputs and secret outputs remain excluded.

Go local caching/integration belongs to B1–B4, not B0. The original A9 operator
acceptance is not imported into the new machine-owned evidence index.

> **Version scope:** the evolution from `plan/v1alpha1` below is the original
> UI-BE-04 design. The standard Core planner emits
> [DeploymentPlan v1alpha2](../../contracts/plan/v1alpha2/schema.json).
> [Plan v1alpha3](../../contracts/plan/v1alpha3/schema.json) separately defines
> selected-source and target scope; its schema alone does not establish runtime
> support or acceptance. Credentialed Start uses the
> [v1alpha2 request](../../contracts/execution-start/v1alpha2/request.schema.json),
> including start attempt, revision, plan/manifest digests and runtime binding.
> [ExecutionCapabilities v1alpha6](../../contracts/execution-capabilities/v1alpha6/schema.json)
> advertises ordered planning request versions;
> [events remain v1alpha1](../../contracts/event/v1alpha1/schema.json).
> See [published schema scopes](../../contracts/README.md).

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
The journal and Go observer admit at most 32768 events per run, with the last
256 journal slots reserved for critical events. Event page and byte limits
remain independent of this record count.

The controller passes the exact owned journal root to the task callback, including
nondefault standalone state roots. Failed task events retain bounded static task
identity, host and a closed diagnostic code/summary with numeric exit or HTTP
status where available. Arbitrary module messages, stdout, stderr, commands,
assertion expressions and tracebacks are never event payloads. Unknown failures
remain generic; `no_log`/censored failures retain identity only and report
`ANSIBLE_FAILURE_REDACTED`. Task names containing Jinja expressions are hidden.

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


## B4 production transport integration

Generated Wails bindings and browser RPC expose B3 CreateInstallationPlanForMode
and GetInfrastructureVerification; TypeScript reuses their data shapes. The
ordinary desktop edit-session allowlist now admits the already validated B2
library operations. No separate writer or command bridge is introduced.

Owner-approved Installation checkbox selects FULL_PROJECT or
APPLICATION_LIBRARIES_ONLY. Libraries always use Apply/Verify. Empty source-policy
map delegates the default to Core (RUNTIME_INPUT); frontend does not infer Vault
producer/bootstrap policy. Unsupported library mode never falls back to full
installation. Full-project legacy API remains available for older callers;
current production transports call mode-aware Build explicitly. Existing
approval, Start, trust, runtime lease, events/results and reconnect are unchanged.

The selected scope is retained across navigation. A plan for another selection
stays visible for review but cannot be approved/started; its services operations
are visually muted when excluded. Selection appears only in the services block
of an existing plan on the Plan tab, not before initial Build. Active run scope is displayed separately
and cannot be changed. Cached observations show UNKNOWN; only fresh plan output
can display Core verification. Actual source infra run IDs are Advanced metadata,
never substitute current library-run operations or imply continuous health.

B4 owner amendment (2026-10-14, final): the services checkbox is local presentation
only and never calls Core. On Approve, a changed scope first builds an authoritative
plan with the existing mode-aware API. Only that returned plan can be approved.
New acknowledgements, changed runtime/revision/node, or re-including infrastructure
require reviewing the returned plan before another confirmation. No separate Build
click is required for the scope change. Libraries remain Apply -> Verify; Start is
unavailable while the displayed plan differs from the selected scope. This replaces
the earlier B4 instruction requiring an explicit fresh Build after checkbox changes.

### B4 application runtime inputs (owner amendment, 2026-10-15)

Performance P2 retains the existing operation/lease contracts. Core Ansible enables
standard SSH pipelining; each controller operation has private, short-lived OpenSSH
ControlMaster sockets, isolated from other runs/operations. Strict host trust,
identity selection and fresh lease admission remain mandatory. Completion/failure
cleans only owned sockets, and confirmed-stop credential cleanup covers recovery.
No socket reuses another operation's lease or trust context.

Library endpoint tasks publish the exact selected source set using one HAProxy
candidate per provider host and one authenticated DNS UPDATE per changed zone.
Partial source lists are derived runtime role inputs, not desired-state persistence
or a new wire mode. Existing prepare/active-validation barriers and recovery
archives remain; this is not a distributed transaction. Network checks retain
their original sequential execution, observer and probe policies.

`BuildRuntimeSecretDescriptors/v1alpha3.applicationInputs` is carried by the existing Go transport. The Installation Plan tab offers session-only password inputs using those Core descriptors. `SetDeploymentRuntimeSecretValues` with an empty serviceDeployment selects the complete application-input subset; its project revision, descriptor fingerprint, project/node/runtime guards remain mandatory. It uses the existing pending Broker and is reattested/promoted at Start. Service dialogs retain their existing scope.

The existing v1alpha3/v1alpha4 `runtimeSecretValues` lease map carries values under Core requirementRef keys. Application purposes from the approved plan participate in exact lease-key-set validation; only the approved subset is serialized. The controller's existing application projection maps those references to runtimeReference and checks provider/library/host/operation scope. No new credential store, lease endpoint or plaintext persistence is introduced.

Requirement quantity is not capped at16/32. Existing per-value4096-byte, aggregate value65536-byte, descriptor response65536-byte, typed-input aggregate and total lease payload bounds remain, together with unique IDs, closed types, exact identity/fingerprint and expiry guards. v1alpha3 descriptor capability omits the old maxDescriptors metadata; older capability responses remain conservative for old clients. Secret output package limits and host/library scope bounds are unchanged.

## Owner amendment 2026-10-17: application failure and explicit Verify skip

Completed service Verify evidence survives application-stage failure/cancel/crash,
including provider/HTTP publication failures. Infrastructure Apply and new
SERVICE_VERIFY attempts retain their existing evidence invalidation. No task-name
or role allowlist and no application-failure-domain.json decide proof retention.

An optional skipInfrastructureVerify boolean in the Wails/Go mode request defaults
to false. True negotiates execution-runtime/v1alpha5 Build and capabilities/v1alpha9
(skipInfrastructureVerify:true), yielding plan/v1alpha6 and manifest/v1alpha4 with
the explicit true flag. False retains the ordinary v1alpha4 request and policy.
Only APPLICATION_LIBRARIES_ONLY may use true. Core omits service operations and
waives saved infra evidence, preserving its real observation, all other admission
checks and the full application Apply/Verify. The flag participates in fingerprint,
stored request and fresh Start rebuild; a changed or unsupported flag is refused.
Skipping never creates successful infra evidence. No new run lifecycle/store.

## Terminal application scripts

Package v1alpha3 may declare `post_install`. Core appends one mutating
`applications:post-install` action (`APPLICATION_LIBRARIES_POST_INSTALL`) after
all ordinary operations, including application Verify/endpoints. The operation
is present only for active scripts of installed libraries. Verify-only and
skipped-library lifecycle never invoke it. Failure or cancel in the prefix
prevents invocation; terminal script failure fails the same run.

The feature uses plan/v1alpha9, execution-manifest/v1alpha7 and the existing
execution-runtime/v1alpha7 request. Capabilities/v1alpha12 adds the closed
`applicationPostInstall` feature with protocol ApplicationPostInstall/v1alpha1,
packageManifestVersion, planContract and manifestContract. Go requires that
capability when receiving the new plan. The complete manifest is schema-checked;
its terminal position/scope and ordered secret-operation permissions are checked
before prior infrastructure-prefix admission. That admission-only compatibility
copy is never dispatched or used for secret authorization. The controller
executes the original approved manifest and reuses existing events/lease/trust
and cancellation. Runtime inputs remain operation-scoped; exact existing Vault
source fields, including generated account bindings, are rematerialized by the
terminal Ansible process and removed by invocation and run cleanup.
