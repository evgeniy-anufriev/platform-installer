# UI-02B — fresh plan and approval

Document scope: the original milestone contract/design. Historical status, review
and QA checkpoints are collected separately; current status and authorization
are recorded only in [CURRENT_STATE](../../../CURRENT_STATE.md).

Recorded status and review scope: [historical checkpoint](evidence/documentation-checkpoints-20261012.md#ui-02b-checkpoint-002).

## Scope and ownership

UI-02B uses the existing target-free `BuildDeploymentPlan` operation through
`executionnode.ExecutionService`. Core remains the only planner. The Wails
facade owns only the current-app reference to the returned `PlanRecord` and
the closed presentation projection.

It adds:

- `CreateInstallationPlan`, `GetInstallationPlan` and
  `ApproveInstallationPlan`;
- a bounded projection of Core-owned phase/action order, target hosts,
  dependencies, findings and acknowledgement summaries;
- exact acknowledgement selection and approval;
- local expiry/context invalidation.

It does not add Start, cancellation, event observation, target credential
transport, preparation, a plan persistence store, raw Core payloads or target
host contact.

## Binding and invalidation

Before creating or approving a plan, the facade requires an open saved project
with no active edit session, READY selected node and trusted runtime binding.
It binds the plan to the exact canonical project revision, project identity
when executable, selected node and exact runtime release. A mismatched revision
or binding clears the app-held plan reference and returns `PLAN_STALE`.

The existing `ExecutionService` remains authoritative for plan TTL, blocked
status, exact acknowledgement equality and future one-shot Start. UI‑02B only
calls CreatePlan, GetPlan and ApprovePlan; tests use a client that fails if a
Start call occurs.

## Presentation boundary

The execution-node decoder retains only the published plan fields consumed by
the UI. It rejects malformed phase/action/acknowledgement shapes and bounded
collection violations before Wails projection. React receives copied typed
values only; it receives no raw maps, runtime paths, secrets, execution
manifest, event stream or transport diagnostics.

## Mockup reconciliation

The existing Installation design already places fresh-plan creation on Summary
and plan review on the Plan tab. UI‑02B implements those two controls. The
Execution and Result tabs remain non-mutating placeholders until UI‑02D.

## Evidence

See [historical checkpoint](evidence/documentation-checkpoints-20261012.md#ui-02b-checkpoint-001). Current status: [CURRENT_STATE](../../../CURRENT_STATE.md).
