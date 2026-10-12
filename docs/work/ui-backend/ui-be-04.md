# UI-BE-04: validation, planning, execution and events

Document scope: the original milestone contract/design. Historical status, review
and QA checkpoints are collected separately; current status and authorization
are recorded only in [CURRENT_STATE](../../../CURRENT_STATE.md).

UI-BE-04 is split into five independently gated milestones:

1. UI-BE-04A — Execution Architecture Audit;
2. UI-BE-04B — Core Deployment Planning;
3. UI-BE-04C — Execution Node Runtime Protocol;
4. UI-BE-04D — Go ExecutionService;
5. UI-BE-04E — Production E2E.

UI-BE-04A freezes the boundaries below. It adds no production planning,
execution, session, journal, cancellation or frontend implementation.

The implementation audit below is a historical snapshot. Contract sections are
maintained in [the execution contract](../../contracts/execution-planning-and-events.md).
Current status is recorded only in [CURRENT_STATE](../../../CURRENT_STATE.md).

## Current implementation audit

See [the dedicated document](evidence/ui-be-04-implementation-audit.md#current-implementation-audit).

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

See [the dedicated document](../../contracts/execution-planning-and-events.md#authoritative-ownership).

## DeploymentPlan and ExecutionManifest

See [the dedicated document](../../contracts/execution-planning-and-events.md#deploymentplan-and-executionmanifest).

## Semantic plan fingerprint

See [the dedicated document](../../contracts/execution-planning-and-events.md#semantic-plan-fingerprint).

## Target-free planning invariant

See [the dedicated document](../../contracts/execution-planning-and-events.md#target-free-planning-invariant).

## Fixed Execution Node machine protocol

See [the dedicated document](../../contracts/execution-planning-and-events.md#fixed-execution-node-machine-protocol).

## Detached controller and process ownership

See [the dedicated document](../../contracts/execution-planning-and-events.md#detached-controller-and-process-ownership).

## Journal, states and retention

See [the dedicated document](../../contracts/execution-planning-and-events.md#journal-states-and-retention).

## Disconnect, reconnect and duplicate prevention

See [the dedicated document](../../contracts/execution-planning-and-events.md#disconnect-reconnect-and-duplicate-prevention).

## Events and cancellation

See [the dedicated document](../../contracts/execution-planning-and-events.md#events-and-cancellation).

## UI-BE-04D - Go ExecutionService

See [the dedicated document](../../contracts/execution-planning-and-events.md#ui-be-04d---go-executionservice).

Implementation checkpoint: [audit](evidence/ui-be-04-implementation-audit.md#ui-be-04d-implementation-checkpoint).

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
- **UI-BE-04E — DONE:** real Kafka production E2E and final regression.

### UI-BE-04E completion evidence

See [historical checkpoint](evidence/documentation-checkpoints-20261012.md#ui-be-04-checkpoint-001). Current status: [CURRENT_STATE](../../../CURRENT_STATE.md).
