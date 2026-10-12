# UI-BE-03: safe Ansible-native project writer

Document scope: the original milestone contract and constraints. Historical
results are linked separately; current status and authorization are recorded
only in [CURRENT_STATE](../../../CURRENT_STATE.md).

> **Lifecycle scope:** the Core-backed `PlanEdit` / `EditPlan` flow below
> describes the original writer contract. New UI Save uses local structural
> review and the guarded transaction under [ADR-027](../../architecture-decisions.md#adr-027-save-project-verify-and-deploymentplan-are-separate-operations)
> and [Save / Project Verify / DeploymentPlan](../ui-lifecycle/ui-save-verify-architecture.md).
> A remote Core Review is not required to authorize new Save. Writer ownership,
> path guards and transaction requirements remain applicable.

## 1. Goal

UI-BE-03 adds the smallest production Go backend needed to turn a bounded semantic edit into a reviewed, validated and crash-recoverable update of the same portable Ansible project consumed by Core. It adds neither UI nor validate/plan/apply runtime execution.

## 2. Go/Python ownership boundary

Go owns Installer application semantics: commands, reviewed plans, sessions, concurrency checks and filesystem transactions. Python/Ansible remains the authority for project interpretation, inventory loading, precedence, validation and all infrastructure semantics.

## 3. Why Go owns Installer application semantics

An edit plan has an application lifetime independent of an Ansible playbook: it is held for review, expires, is discarded, is guarded against concurrent writers and commits a group of documents atomically. This belongs in the Go Installer backend that a future Wails transport will call, not in Core.

## 4. Why Python/Core remains infrastructure authority

Go does not resolve Ansible variables, role defaults, topology, service configuration, endpoint, PKI or HAProxy rules. It invokes the existing target-free `ProjectSnapshot` through `CoreAdapter`; the staged snapshot is the proof that the proposed native documents produce the requested effective state.

## 5. Go CoreAdapter

`internal/coreadapter` invokes the machine-readable `ansible-core/playbooks/project-snapshot-machine.yml` entrypoint. A temporary request and callback response carry only the published snapshot contract; human Ansible stdout is discarded and stderr is bounded. Invocation has a context timeout and does not target project hosts.

## 6. Writable document ownership

An arbitrary project is read-only by default. This writer changes only files that carry the exact Installer-managed header and are reported by Core as `INSTALLER_OWNED`. All other inventory and variable files, including `inventory/hosts.yml` and the ordinary `platform.yml`, remain user-owned.

## 7. Actual managed Ansible document layout

The single writable logical roots are deliberately split by normal Ansible loading scope:

```
inventory/group_vars/all/platform-installer.yml       platform_desired_state
inventory/host_vars/<host>/platform-installer.yml     platform_deployments
```

The header identifies each file as owned. The paths are ordinary Ansible inputs; no Installer-specific project database is introduced.

## 8. Variable-root ownership / precedence constraints

Each writable root has one managed file. The layout never divides a managed mapping across files or recreates Ansible precedence in Go. The accepted Core configuration retains its normal Ansible semantics, including the repository's configured hash merge behavior; writer safety does not depend on guessing that merge order.

## 9. Semantic EditCommand

`platform.installer/edit-command/v1alpha1` is a bounded semantic command surface: deployment, managed configuration, endpoint-group, HAProxy relation and placement changes, plus bounded batches. It rejects unknown command shapes and plaintext secret-like values. Service behavior is checked through the catalog and Core, rather than by service-type branches in Go.

## 10. EditPlan lifecycle

`PlanEdit` reads the authoritative initial snapshot, applies a command only to a staging copy, runs the staged snapshot, and returns `READY`, `NO_CHANGE` or `BLOCKED`. A `READY` plan is reviewed by opaque ID and may be committed once or discarded. Planning writes zero canonical project bytes.

## 11. PlanStore lifecycle

The in-memory PlanStore holds the private staged bytes and guards behind an opaque cryptographically random plan ID. Its public plan is a safe review projection. Plans expire after five minutes, are defensively copied, and are removed on discard or successful commit; callers cannot submit edited plan contents to commit.

## 12. Staged authoritative validation

Core builds a fresh `ProjectSnapshot` from the staged project. A blocked snapshot blocks the plan, and requested effective-state expectations must be visible in that snapshot. Changes shadowed by Ansible loading/precedence are rejected as `EDIT_SHADOWED` instead of being written.

## 13. projectRevision/document digest guards

The raw-byte-derived project revision is checked at planning and again under the writer lock at commit. Every affected document's before digest is also checked. An outside edit therefore returns `PROJECT_CHANGED` or `DOCUMENT_CHANGED`; it is never overwritten.

## 14. Deterministic YAML

The writer serializes managed YAML deterministically: map keys are sorted, scalar tags are explicit where needed, and the managed header is retained. It owns semantics rather than comments or formatting in its own files, and it never rewrites user-owned YAML.

## 15. User-owned file protection

Discovery accepts only the fixed owned paths and requires the managed header. User-owned `hosts.yml`, `platform.yml`, unrelated variables and generated provider/PKI artifacts are outside the edit set and are preserved byte-for-byte.

## 16. Shadowed edit rejection

The staged Core result, rather than a local merge model, decides whether an edit has effect. If normal Ansible loading makes a requested setting invisible or changes its effective origin unexpectedly, the plan is blocked and cannot be committed.

## 17. Transaction semantics

Commit is serialized by a project-local lock. It writes synced sibling temporary files, journals exact old bytes under `.runtime/edit-transactions`, atomically replaces the approved files, and syncs directories. POSIX uses rename; Windows uses replace-existing `MoveFileExW`. No operation runs apply or touches targets.

## 18. Failure recovery/crash consistency

Journals record `PREPARING`, `PREPARED`, `REPLACING` and `COMMITTED` phases. Any failure after replacement begins restores every old document byte sequence; the next commit first recovers interrupted journals. The guaranteed terminal state is the complete old set or the complete new set, never a partial set.

## 19. Path/symlink safety

Fixed logical paths are cleaned and constrained beneath the project root. Traversal, reparse points and symlinks in managed paths, canonical documents or staged projects are blocked. Transaction, backup and temporary paths are derived only from verified paths.

## 20. Cross-platform filesystem abstraction

The transaction uses a narrow replace and directory-sync abstraction. POSIX and Windows replacement rules are isolated behind it; the public edit contract does not expose operating-system-specific paths or retry behavior.

## 21. SecretRef boundary

Desired state accepts secret/credential references only. The writer rejects plaintext secret-shaped values, emits safe findings and shows digest-only file review information, so plan output, journals and diagnostics do not disclose secret material.

## 22. Post-commit ProjectSnapshot

After a successful replacement the backend rebuilds `ProjectSnapshot` from the committed project. A successful commit returns that new authoritative snapshot. If refresh cannot be built, the write remains committed and is reported as `COMMITTED_REFRESH_FAILED`, never silently rolled back.

## 23. No-target-contact/offline proof

The machine snapshot entrypoint runs only on `localhost`, with no apply, runtime workspace or target transport. Recorded evidence: [historical checkpoint](evidence/documentation-checkpoints-20261012.md#ui-be-03-reconciliation-001). Current status: [CURRENT_STATE](../../../CURRENT_STATE.md).



## 24. Performance

Representative RED OS authoritative round-trip timing is recorded by the Go acceptance test: plan application is about 2 ms, initial and staged snapshots are each about 0.7-0.9 s, filesystem commit about 0.3 ms, and post-commit snapshot about 0.8 s. Snapshot construction is intentionally dominant because Core remains authoritative.

## 25. Limitations

Only the declared command subset and Installer-owned layout are writable. There is no adoption workflow for arbitrary YAML, persistent PlanStore, collaborative editing, UI, generic YAML AST preservation, execution session, event stream, validation/apply/verify orchestration or runtime secret store.

## 26. Exact UI-BE-04 handoff

UI-BE-04 extends this same Go backend with validation and deployment-plan orchestration, execution sessions, subprocess lifecycle, cancellation and event streaming. It must reuse `CoreAdapter`, `EditPlan`, revision/digest guards and the portable project; it must not add a second desired-state store or move Core infrastructure rules into Go.
