# UI owner change — Save, Project Verify and DeploymentPlan

Document scope: the original milestone contract/design. Historical status, review
and QA checkpoints are collected separately; current status and authorization
are recorded only in [CURRENT_STATE](../../../CURRENT_STATE.md).

Recorded status and review scope: [historical checkpoint](evidence/documentation-checkpoints-20261012.md#ui-save-verify-architecture-checkpoint-001).



The implementation adds the closed `project-save/v1alpha1` and
`project-verification/v1alpha1` contracts, local owned-field server projection,
local structural review through the existing PlanStore/transaction writer, and
explicit target-free Verify. It adds no readiness check or preparation flow;
those remain UI-01E5 scope.

## Decision

Three operations have separate meanings and authorities:

```text
EditSession
  → local candidate assembly
  → local structural/safety review
  → guarded Save
  → canonical saved revision
            ├─ optional Project Verify → target-free Core findings
            └─ mandatory fresh BuildDeploymentPlan → approval → StartExecution
```

### Save

**Сохранить** means persist the current structurally valid managed candidate.
It is a local application operation and requires neither an Execution Node nor
Core validation. It reuses the existing typed/closed command checks, bounded
candidate, base revision and document before-state guards, ownership and fixed
path allow-list, symlink/reparse safety, secret-reference grammar owned by the
application, and journaled atomic transaction with rollback/recovery.

Save proves only that Installer can safely represent and persist the requested
managed source state. It does not prove Ansible precedence, service/topology/
PKI semantics, deployment validity or source resolution. Go must not recreate
those Core rules. A successful semantic Save returns the new canonical revision
and leaves the resulting revision `UNVERIFIED`.

The old remote Core Review and `EditPlan` existed to authorize persistence.
That authorization is no longer required for new Save. The useful local preview
is retained as a structural plan over typed intents and affected documents; it
must not claim Core PASS, expected effective state or snapshot fingerprint.
Published old project-edit plan/result contracts remain immutable compatibility
contracts. New structural plan/result payloads require an additive closed
contract. `COMMITTED_REFRESH_FAILED` is a distinct post-commit local refresh
result: stale rows are cleared and CRUD remains blocked until a read-only local
reopen succeeds; it never retries or rolls back an already committed transaction.

### Project Verify

**Проверить** is an explicit optional preflight for the last saved canonical
revision. Unsaved React/session overlays are neither saved nor verified. It
requires a READY Execution Node and reuses the narrowest fixed target-free Core
read/validation path, preferably `BuildProjectSnapshot` with exact runtime
attestation. It contacts no target server, performs no repository probe or
RuntimeProjection, applies no service and writes no project file.

Derived verification evidence contains only:

- project identity and exact raw-byte canonical project revision;
- attested immutable bundle/Core/catalog/protocol identity;
- `UNVERIFIED`, `VERIFYING`, `VERIFIED`, `INVALID` or `STALE`;
- bounded safe findings and `checkedAt`.

It is in-memory application/runtime state for this milestone, not portable
desired state, a project marker, validation history or second project store.
First Save without prior verification leaves the resulting revision
`UNVERIFIED`. A semantic Save after `VERIFIED` or `INVALID` makes the previous
evidence `STALE`: its old revision identity may be retained for display, but
findings and identity/SAN previews are not current evidence. Core
blocking/partial results make the exact saved revision `INVALID`;
transport/readiness/runtime evidence failure returns a typed error while the
project remains `UNVERIFIED`.
A failed/cancelled Verify never undoes Save.

During Project Verify, a missing required service secret reference is a Core
`WARNING`, not a blocking configuration error. A complete snapshot containing
only warnings remains `PASS` / `VERIFIED`; the UI displays the yellow
“Проверено с предупреждениями” status and retains the instance/setting finding.
Malformed references remain blocking. This does not change DeploymentPlan
generation or its existing approval admission: missing required credentials
must still prevent approval. Warning-only Verify does not authorize execution.

Verify may automatically run a read-only readiness check. If preparation is
required, E5 may continue the same revision/node/runtime-bound Verify request
only after explicit confirmation and successful re-inspection. Failure/cancel
preserves saved state and any unsaved draft.

### Install / Build DeploymentPlan

Project Verify is convenience feedback, not execution authorization. Every
execution attempt retains the existing UI-BE-04 boundary:

```text
current saved canonical revision
  → READY Execution Node
  → fresh BuildDeploymentPlan
  → authoritative plan findings/blockers
  → user approval
  → StartExecution bound to that plan
```

There is no `VERIFIED → StartExecution` path. A prior `VERIFIED`, `INVALID` or
`UNVERIFIED` badge does not bypass or replace fresh planning.
Installation may request a plan regardless of optional Project Verify state,
provided its ordinary prerequisites are available. A successful fresh plan for
the exact revision and same attested runtime may refresh the derived badge to
`VERIFIED` only when the existing planning result semantically proves the same
project-validation claim; no duplicate Core call is made solely for a badge.

`StartExecution` accepts only a current approved authoritative DeploymentPlan,
so temporarily saved invalid/unverified source is owner-approved without
weakening execution safety. A blocked fresh plan authorizes no execution.

## State and UX

| Saved state | Editing/Save | Optional Verify | Request fresh plan | Direct execution |
| --- | --- | --- | --- | --- |
| `UNVERIFIED` | allowed | allowed when node READY | allowed | prohibited |
| `VERIFIED` | allowed | allowed | required before execution | prohibited |
| `INVALID` | allowed | retry after edits | allowed; plan decides authoritatively | prohibited |

User-facing meanings:

- **Сохранить** — записать текущую конфигурацию в проект;
- **Проверить** — проверить последнюю сохранённую конфигурацию через Core;
- **Установка** — построить и подтвердить конкретный свежий план выполнения.

Installation shows saved and verification state separately from DeploymentPlan
state. It may link to E5 readiness/check/prepare, but Installation itself does
not select or prepare the Execution Node.

## Contract direction

Do not mutate existing project-edit schemas. The implementation plan must add
closed, bounded structural Save and derived verification/readiness contracts
only where a typed Wails boundary needs them. The existing
`BuildProjectSnapshot` operation may gain a negotiated evidence mode rather
than a second validation operation. `BuildDeploymentPlan` and
`StartExecution` contracts remain unchanged and mandatory.

No verification database, background worker, automatic verify-after-save,
auto-save, persistent history, local Core emulator, second writer or second
desired-state store is introduced.

## Durable owner decisions

- **OWNER-UI-SAVE-VERIFY-01:** Save and authoritative Core verification are
  separate. Save is local and requires no Execution Node.
- **OWNER-UI-SAVE-VERIFY-02:** a saved project may be `UNVERIFIED`, `VERIFIED`
  or `INVALID`; these states permit editing/Save but do not authorize execution.
- **OWNER-UI-SAVE-VERIFY-03:** Verify validates exactly the current saved
  canonical revision through target-free Core on READY and never mutates it.
- **OWNER-UI-SAVE-VERIFY-04:** verification is derived evidence bound to exact
  project revision and attested active Core/runtime identity; Save makes the
  resulting revision unverified.
- **OWNER-UI-SAVE-VERIFY-05:** fresh `BuildDeploymentPlan` remains mandatory
  before execution and is never bypassed by prior Project Verify.
- **OWNER-UI-SAVE-VERIFY-06:** Verify may check readiness automatically; any
  mutating preparation requires explicit confirmation.

## Milestone impact

### Blocker follow-up evidence

Recorded evidence: [historical checkpoint](evidence/documentation-checkpoints-20261012.md#ui-save-verify-architecture-reconciliation-001). Current status: [CURRENT_STATE](../../../CURRENT_STATE.md).

Verify now requires
`expected.planningProtocol == RuntimeEvidence.Protocol`; a mismatch or either
missing value returns the typed unverified result and cannot publish
`VERIFIED`.



- **UI-01D:** retains EditSession, candidate builder and guarded transaction;
  remote Core Review ceases to authorize new Save. Old contracts/evidence remain
  compatibility history.
- **UI-01E1/E2:** server CRUD remains typed intents → session → local candidate
  → guarded Save. CRUD semantics otherwise remain unchanged.
- **UI-01E3:** no change.
- **UI-01E4:** selection semantics do not change.
- **UI-01E5:** owns readiness/preparation used by Verify, not Save, and the
  minimum derived verification UX state.
- **Installation/UI-02:** always builds a fresh authoritative DeploymentPlan
  and never executes directly from a Project Verify badge.

## Acceptance invariants for later implementation

- Save succeeds with no Execution Node and starts no SSH/Core process.
- Save failures are local candidate/writer/transaction failures; successful
  commits are never reported failed due to absent Core.
- Verify reads only the last saved revision and leaves all project digests
  unchanged.
- `INVALID`/`UNVERIFIED` remains editable/saveable.
- Every StartExecution is traceably bound to a freshly built approved plan for
  the same canonical revision/runtime; no badge bypass exists.
- Existing DeploymentPlan blocker/finding behavior remains authoritative.
