# UI-01E5 — Execution Node readiness, preparation and navigation gating

Status: **NEXT — not started**.

## Scope boundary

ADR-027 and the committed pre-E5 Save/Verify correction are complete. They are
not UI-01E5 work:

- local structural Review/Save uses the guarded writer without Core or an
  Execution Node;
- saved Installer-owned server fields reopen locally without Ansible precedence;
- explicit target-free Verify uses `BuildProjectVerificationSnapshot` and
  cannot mutate project files;
- Verify evidence is revision-bound and uses the active runtime's attested
  bundle, Core, catalog and planning-protocol identity;
- Verify requires `expected.planningProtocol == RuntimeEvidence.Protocol`;
  a missing or unequal value returns a typed `UNVERIFIED` result, never
  `VERIFIED`;
- semantic Save makes the resulting revision `UNVERIFIED`;
- `BuildDeploymentPlan` remains the fresh mandatory execution gate.

The owner-authorized AR-SV-001 follow-up was implemented without a third
architecture review. It closed only the missing planning-protocol comparison.

UI-01E5 starts only when explicitly requested. Its remaining scope is:

1. read-only readiness inspection for the already trusted immutable Execution
   Node binding;
2. explicit-confirmation flow for the existing mutating preparation workflow;
3. retry/resume of the same saved-revision Verify after successful preparation;
4. readiness presentation in the App Shell and Servers panel;
5. navigation and Installation prerequisite rendering.

## Non-goals

- No new Save path, candidate writer, EditSession model, local project parser,
  Core emulator or verification persistence.
- No execution, service deployment, target preparation, UI-02 transport, or
  target-secret use.
- No creation of an `executionnode.Node` from a React/Wails DTO or from an E4
  project-server candidate.
- No automatic mutating preparation. A read-only check may be automatic; every
  Prepare action needs explicit user confirmation.
- No bypass from `VERIFIED` to execution: a fresh authoritative
  `BuildDeploymentPlan`, approval and bound `StartExecution` remain required.

## Required design

E5 reuses the existing `executionnode.Service` and one immutable application
binding. The binding is constructed outside Wails from the configured trusted
node, runtime release and transport. UI may select only that binding for
readiness/prepare; it cannot provide address, host-key, credential or transport
details.

### Candidate and trusted binding

**OWNER-UI-E5-01:** an E4 candidate selection does not create transport trust.
Readiness and preparation operate only through an application-owned trusted
Execution Node binding.

`ExecutionNodeContext` remains an app-memory selection/display model. Its
`USER_SELECTED`, `AUTO_LOCAL_LINUX`, `AUTO_FIRST_PROJECT_SERVER` and
`NOT_CONFIGURED` outcomes are candidates, not `executionnode.Node` values.
The required E5 flow is:

```text
ExecutionNodeContext candidate
  → Go application binding resolver
  → existing approved trusted binding / executionnode.Service
```

React/Wails never supplies an address, credential, host-key policy, known-hosts
path or transport. It does not parse Ansible and cannot reuse the E3 target
credential. A sorted server list or automatic candidate selection does not
change trust.

The current startup path already constructs one trusted `projectReader` binding
from CLI/configured trust inputs; `executionnode.Service` accepts only its
validated `Node`. It has no project-candidate-to-binding resolver. E5 therefore
needs exactly one private application operation:

```text
resolveSelectedExecutionNodeBinding(context) -> trusted binding | BINDING_REQUIRED
```

It may return the existing startup binding only when its application-owned
candidate identity matches. Otherwise it returns `BINDING_REQUIRED`, not an
ordinary readiness failure. Establishing a new binding remains the existing
approved bootstrap/trust workflow, outside React and outside this resolver.
This is a lookup over the current immutable application binding, not a node
registry, database, transport provider, discovery worker or portable-project
state.

Replacing a binding invalidates readiness, a pending preparation plan and any
Verify continuation. The binding is runtime application state only.

Readiness is derived application state, never portable-project data. Its safe
view may contain state, checked time, safe display label, attested runtime
identity, bounded safe findings, whether preparation is possible, and a
bounded preparation summary. It must exclude connection data, commands,
staging paths, raw output, secrets and credential references.

### Prepare and Verify continuation

**OWNER-UI-E5-02:** Prepare may legitimately activate a different immutable
runtime. A continuation must not pin pre-Prepare runtime identity as the final
Verify expectation.

The user confirms one bounded preparation plan, not an abstract prepare
action. Before `Prepare`, the continuation binds only project-root identity,
project identity, exact saved revision, selected candidate/trusted-binding
identity, preparation plan ID/digest and expiry, plus the explicit
confirmation. `executionnode.Service.Prepare` already validates its plan ID,
digest, node, expiry and current bundle before mutation.

After successful Prepare, E5 performs a fresh readiness/capability handshake,
obtains fresh active runtime attestation, then invokes Verify for the original
saved revision. Only this post-Prepare attested runtime may enter verification
evidence. No pre-Prepare release is reused as final proof.

```text
Verify(R42) → trusted binding → check → bounded plan → confirm
  → revalidate R42/binding/plan/expiry → Prepare
  → fresh readiness + fresh runtime attestation → Verify(R42)
  → VERIFIED | INVALID
```

Close, project-root/identity replacement, Save to a new revision, candidate or
binding replacement, plan replacement/expiry, cancelled/failed Prepare and
shutdown cancel the continuation. In each case no resumed Verify succeeds, the
saved revision remains `UNVERIFIED`, and canonical files are unchanged.

## UX and gating

- Save remains available without a ready node.
- Verify with a non-READY node offers a clean readiness prerequisite; E5 may
  perform the read-only check automatically, then offer confirmed Prepare.
- Failed/cancelled preparation preserves canonical files and the edit draft.
- Project and Servers remain available before READY. Existing editor pages are
  not disabled merely because readiness is absent.
- Installation presents readiness, optional Verify and authoritative plan state
  separately. It never prepares a node implicitly and never treats Verify as an
  execution authorization.

Readiness presentation reuses typed `executionnode.State` rather than a new
React enum. Its bounded view contains state, checked time, safe label, safe
attested runtime identity, safe findings, preparation availability and the
confirmed plan's bounded actions/expiry. It excludes commands, argv, SSH
parameters, staging paths, credentials and raw output.

## Acceptance criteria

- No-node local Save and reopen continue to pass.
- Readiness check is read-only and never contacts project target hosts.
- Prepare runs only after explicit confirmation and only for the trusted
  binding.
- Candidate without a resolved trusted binding returns `BINDING_REQUIRED` and
  cannot inspect or prepare.
- A runtime-changing Prepare is followed by fresh attestation; a continuation
  never compares final evidence to pre-Prepare runtime identity.
- Verify after Prepare uses the original saved revision and attested runtime;
  mismatch/cancellation leaves the project `UNVERIFIED`.
- Fresh `BuildDeploymentPlan` is still observed before every StartExecution.
- E5 acceptance rechecks the UI mockup and records any discrepancy before
  coding, per `AGENTS.md`.
