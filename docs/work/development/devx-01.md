# DEVX-01: Codex engineering harness

Document scope: the original milestone contract/design. Historical status, review
and QA checkpoints are collected separately; current status and authorization
are recorded only in [CURRENT_STATE](../../../CURRENT_STATE.md).

Recorded status and review scope: [historical checkpoint](evidence/documentation-checkpoints-20261012.md#devx-01-checkpoint-001).

This harness records the accepted engineering workflow; it
does not add product behavior, UI-BE-04 execution, Wails/React code or service
semantics.

## 1. Purpose

Provide small reusable instructions for future Go, Core and QA work while
preserving the standalone-Ansible-first architecture.

## 2. Existing architecture this harness protects

Standard Ansible inventory, `group_vars`, `host_vars` and role defaults are
canonical desired state. Go owns Installer application semantics. Python/
Ansible owns infrastructure semantics. React renders; future Wails transports
typed Go services. ADR-020 is the durable decision record.

| Capability | Owner |
| --- | --- |
| Project/session lifecycle; EditPlan; writer transaction; revision/digest guards; filesystem safety | Go |
| Future execution session, cancellation/event transport and Wails-facing services | Go |
| Ansible precedence; catalog/schema; validation; topology; endpoint/provider; PKI; ProjectSnapshot; DeploymentPlan; apply/verify | Python/Ansible Core |
| Rendering/UI | React |
| Transport binding | Wails, thin Go adapter |

## 3. Actual Go/Core package boundary discovered

The module is `platform-installer`. `internal/installer` contains `Backend`,
`PlanStore`, `EditCommand`/`EditPlan`, deterministic YAML and the guarded
filesystem transaction. `internal/coreadapter` contains `Adapter` and
`CommandAdapter`, which invokes the controller-only
`ansible-core/playbooks/project-snapshot-machine.yml`. Core emits the
authoritative machine-readable `ProjectSnapshot`; Go does not parse human
Ansible stdout.

## 4. AGENTS.md hierarchy

Root [AGENTS.md](../../../AGENTS.md) contains global architecture, state ownership,
security and QA rules. [internal/AGENTS.md](../../../internal/AGENTS.md) adds Go
application/transaction rules. [ansible-core/AGENTS.md](../../../ansible-core/AGENTS.md)
adds Core-controller rules. Child instructions supplement rather than override
the root. No frontend file exists because no stable frontend subtree exists.

## 5. Global rules

Go never reimplements Ansible precedence, service topology, endpoint/provider
or PKI semantics. Python never owns Installer plan, session, process or UI
lifecycle. `ProjectSnapshot` is derived; generated state is machine-owned;
SQLite cannot be canonical configuration authority.

## 6. Go scoped rules

Go uses `context.Context`, structured findings and narrow interfaces. Stateful
objects must have explicit bounded lifecycle and concurrency safety.
Filesystem destinations are backend-derived, root-contained and protected from
traversal/symlink/reparse escape; cross-platform replacement remains isolated.

## 7. Core scoped rules

Core uses Ansible-resolved variables as authority. Go-facing controller
operations are structured, deterministic, secret-safe and target-contact-free
when promised. Python adapters remain thin and do not manage plans, sessions,
writer transactions or Wails state.

## 8. Skills

Repository-local Skills use the established `.agents/skills/<name>/SKILL.md`
format:

- `installer-go-backend` — bounded Go application work;
- `core-adapter-contract` — structured Go/Core operations;
- `ansible-project-writer` — UI-BE-03 writer guards and transaction flow;
- `installer-qa-gates` — milestone finalization.

They are procedures, not duplicated architecture documentation.

## 9. Agent/reviewer roles

The repository includes one project-scoped custom agent:
[architecture-reviewer](../../../.codex/agents/architecture-reviewer.toml).
It is an independent read-only advisor to the owner, not an autonomous approval
authority. It performs one FULL review where required and includes mandatory
overengineering analysis. Its TOML defines read-only behavior and the report
contract; model settings inherit from the caller. PLAN reviews identify the
exact plan revision (git object or deterministic SHA-256); DIFF reviews identify
the base commit and exact head commit or deterministic worktree-diff
fingerprint. Other roles below remain documented prompt templates:

- **go-implementer**: implement one bounded Go backend task with
  `installer-go-backend`; use `core-adapter-contract` when Core interaction
  changes; report missing Core capability rather than recreating it.
- **core-contract-reviewer** (read-only): report `BLOCKING`, `NON_BLOCKING` or
  `PASS` with file, symbol and reason. Check ownership, structure/versioning,
  deterministic payload, diagnostic separation, secret safety, no target
  contact and offline behavior.
- **safety-reviewer** (read-only): use the same finding format for root escape,
  symlink/reparse behavior, locks, races, rollback/recovery, temp cleanup,
  subprocess/cancellation lifecycle and sensitive logs.

No service-specific agents are created. UI implementer is deferred.

### Bounded architecture-review lifecycle

For an architecture-sensitive PLAN, the author creates one concrete revision
and requests one FULL PLAN review. APPROVE goes to owner approval.
APPROVE_WITH_CHANGES may receive obvious bounded nonblocking corrections and is
then presented to the owner without an automatic full re-review. BLOCK stops
automatic work; the parent returns finding IDs, evidence, impact, smallest
corrections and its recommendation to the owner. Further full PLAN review needs
an explicit owner request, except for one new review of a materially changed
owner-approved architecture revision.

Architecture DIFF review is risk-based:

| Risk | Default architecture review |
| --- | --- |
| HIGH — state ownership, transactions/first save, migration, secrets/security, Execution Node/process lifecycle, source/bundle trust, new persistence or public contract architecture | One FULL DIFF review |
| MEDIUM — typed CRUD on an existing lifecycle, server model extension, service editor integration, topology UI on existing contracts | PLAN review normally sufficient; DIFF only when required by the plan, material architecture drift or owner request |
| LOW — React display/layout, labels, application-config values, CLI formatting, docs, straightforward tests or bounded fixes within an approved contract | Normally no architecture review |

For a HIGH-RISK DIFF that returns BLOCK, the parent stops and returns findings
to the owner. After an owner-approved correction, the parent may run one
TARGETED_RECHECK limited to those finding IDs and their immediately affected
boundary. A second BLOCK returns to the owner; no third automatic cycle or full
review restart is allowed.

The formal maximum automatic budget per gate is:

```text
1 initial FULL review + at most 1 TARGETED_RECHECK
```

Nonblocking findings never trigger an automatic rerun. Anything beyond the
budget requires explicit owner authorization. Material architecture change is
limited to ownership, persistence, public contract semantics, execution/source
authority, security boundaries, transaction model, lifecycle subsystem or an
owner-approved architectural scope change. Tests, names, messages, missing
bounds/cleanup, negative tests, documentation and behavior-preserving refactors
do not invalidate the whole review automatically. Uncertainty is reported to
the owner instead of starting a review loop.

Overengineering remains mandatory, but it blocks only when the reviewer shows
a concrete unnecessary mechanism, a viable simpler existing/standard mechanism
that meets the current need, and material maintenance, contract or safety cost.
Aesthetic alternatives are nonblocking. Architecture review does not replace
owner authorization or applicable Core-contract, safety and QA gates.

Concrete process checks:

| Scenario | Expected result |
| --- | --- |
| PLAN → APPROVE | Present to owner; no second review |
| PLAN → APPROVE_WITH_CHANGES → bounded correction | Present revision and findings to owner; no automatic full re-review |
| PLAN → BLOCK | Stop and return blockers to owner; no autonomous redesign loop |
| HIGH DIFF → BLOCK → owner correction → TARGETED_RECHECK PASS | Continue normal gates; do not restart FULL DIFF review |
| TARGETED_RECHECK still BLOCKS | Stop for owner decision; no third automatic review |
| Simple React/display change | No architecture review by default |

## 10. Invocation examples

- UI-BE-04 execution sessions: use `installer-go-backend` and
  `core-adapter-contract`; then request read-only `core-contract-reviewer` and
  `safety-reviewer`, followed by `installer-qa-gates`.
- New read-only Core operation: use `core-adapter-contract`; do not modify
  application lifecycle.
- Project transaction review: request `safety-reviewer` in read-only mode; do
  not modify code.
- Milestone finalization: use `installer-qa-gates` and report every applicable
  gate.

## 11. QA workflow

Read acceptance criteria, identify affected layers, run focused tests, then
run Go/Core/service checks only when affected. Use `scripts/qa-sync.ps1` for
Windows-to-RED OS transfer and cleanup. For pure operations prove no target
contact and use offline `unshare -n` where applicable. Audit secret safety,
temporary artifacts, `git diff --check` and worktree contents before updating
state or committing. Do not repeat unaffected accepted runtime recovery tests.

## 12. Cross-platform policy

The Installer backend is cross-platform. Isolate OS-specific filesystem/process
behavior; do not require WSL or local Ansible. Future execution may select an
approved Linux, WSL2 or execution-node adapter without changing this boundary.

## 13. Offline/security policy

No dynamic download, cloud state or external agent orchestration is part of
acceptance. Runtime credentials stay outside canonical desired state; never
persist plaintext secrets, private keys or sensitive plan/event/log data.
SecretRef identifiers are references, not values, and sensitive temporary
artifacts require explicit cleanup.

## 14. UI-BE-04 handoff

UI-BE-04 extends the same Go backend with execution IDs/sessions, process
lifecycle, cancellation, structured event ingestion/streaming, bounded history
and adapter selection. Core retains DeploymentPlan, playbook/service lifecycle
and structured Core event semantics. This milestone implements none of it.

## 15. Future Wails extension

The future flow is React/TypeScript -> generated thin Wails transport -> Go
application backend. Wails is not a service-semantics layer, Ansible adapter,
database or configuration authority; frontend never calls Core directly.

## 16. Deferred Skills/roles

`wails-ui-boundary`, `installer-execution-session`, `execution-event-contract`
and a UI role remain deferred until UI-BE-04/UI-01 supplies concrete contracts.
No empty Wails/React tree was created.

## 17. Validation evidence

Recorded evidence: [historical checkpoint](evidence/documentation-checkpoints-20261012.md#devx-01-reconciliation-001). Current status: [CURRENT_STATE](../../../CURRENT_STATE.md).

Live parent permission overrides may override sandbox defaults, so read-only
instructions apply independently of the sandbox setting. After adding a role,
use a fresh session if the current role registry has not refreshed. Example:
"Use architecture-reviewer in PLAN mode for docs/<milestone>.md; return the
mandatory overengineering report before owner approval." The review report
tracks stable finding IDs through OPEN, RESOLVED, OWNER_ACCEPTED and SUPERSEDED;
OWNER_ACCEPTED is limited to nonblocking owner-controlled tradeoffs and cannot
waive safety, security, secret-handling or canonical-state invariants. The
parent supplies facts and evidence, never an expected verdict. CURRENT_STATE.md
is the dynamic milestone authority; AGENTS.md supplies durable process rules.
If the custom role is unavailable, the fallback receives the same full
instructions; if no independent reviewer is available, the gate remains
pending. The main agent records the returned evidence; the reviewer never
writes it itself.
DEVX-01 changes documentation/instructions only and
requires no RED OS service runtime replay.
