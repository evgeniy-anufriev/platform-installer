# UI project creation — accepted design input

Status: ACCEPTED by UI-01A, 2026-09-05. Owner requested UI design based on
[UI-DESIGN-01 mockup](ui-design-01-mockups.html), including creation without
inventory, host_vars or group_vars. This is not production UI implementation
or approval to relax the accepted writer/Core contracts.

Exact lifecycle, lock provenance, first-save ownership and implementation gates
are normative in the [UI-01A contract freeze](../work/ui-01/ui-01a-contract-freeze.md).

## 1. Entry point and empty project

Projects has three distinct entry actions: **Создать проект**, **Открыть проект**,
**Импорт проекта**. Export remains an operation on an existing project.
Create is primary when starting from scratch; opening never implicitly imports,
adopts or rewrites another directory.

Create asks for display name and a new local directory on the Installer machine.
The backend generates project identity; normal UI need not ask for a technical
ID. Proposed initial contents: only minimal `project.yml` identity/metadata.
The exact metadata envelope is frozen by UI-01A. No service configuration is
stored in that file. No inventory,
host_vars, group_vars, example servers, implicit deployments, secrets or runtime
workspace are created. `ansible.cfg` and required compatibility inputs are
materialized only as part of the explicitly reviewed first configuration write.

Production creation must validate the destination, reject existing destinations
without overwriting/adopting them, guard symlink/reparse-point escapes and races,
and publish the initial directory transactionally. Cancel writes nothing;
failure does not add a successful recent-project entry. The HTML prototype
does not perform any filesystem operation, uniqueness check or Core validation.

After creation, open **Проект**, not Installation with demo PASS indicators.
Show the actual name/path, zero servers/deployments/runs and the next actions.
Existing populated projects retain Installation as their operational home.

| UI condition | Meaning | Available next action |
| --- | --- | --- |
| Проект ещё не настроен | Metadata only; not corrupt and not validated | Add servers or configure topology/services |
| Есть несохранённые изменения | Session input, not canonical desired state | Review, complete or discard |
| Конфигурация сохранена | Native files committed through validated edit flow | Request readiness/plan checks |
| Требуется внимание | Backend findings or missing execution prerequisites | Follow specific finding to editor/preparation |
| Готов к формированию плана | Backend prerequisites satisfied | Build and review a new plan |

These are presentation descriptions, not a second execution-status enum.
Creation success, saved configuration, node readiness and deployment success
must never share a single green status.

## 2. Progressive editing and files

Pages are complementary views of the same project, not separate configurations.
Owner-approved refinement: **Сервисы** is a global page, with the same editor
reachable from the selected deployment in Topology. Returning preserves the
topology context. Installation focuses on preparation, review and execution.
Navigation order is Projects → Servers → Topology → Certificates → Services →
Installation → History. Topology creates deployments and placement; Certificates
edits PKI intent before Services selects profile references. This is recommended
order, not a forced wizard; non-TLS services need no certificate profile.
The persistent project header shows name, path and shared unsaved/saved state.
Credentials remain one session-scoped password or key for all servers using
the same technical identity and privileges; no per-host credential UI is added.

| Area | Responsibility | Intended native destination after reviewed save |
| --- | --- | --- |
| Servers | Inventory identity, transport metadata; separate observed facts | UI-01A managed-inventory contract; implementation UI-01D/E |
| Topology | Deployment/member identity, roles, host placement, endpoint relations | Existing managed group_vars and member host_vars as applicable |
| Certificates | PKI profile intent; Core-derived SAN/consumer preview | Existing canonical PKI input contract; owned edit support verified in UI-01A/G |
| Services | Catalog-driven settings for the same deployment | `inventory/group_vars/all/platform-installer.yml`; allowed member overrides in existing host scope |

The accepted member placement destination is
`inventory/host_vars/<host>/platform-installer.yml`. Do not create one empty
host_vars file for every server; create it only when that scope contains actual
desired input. A page switch writes no files. Do not create duplicate managed
roots or silently adopt user-owned `inventory/hosts.yml`/`platform.yml`.

Users may start with servers or sketch a deployment first. Incomplete form input
stays in the backend-owned editing session, with a visible unsaved indicator;
changing pages must not lose it. It is not exported or used for execution.
Before closing/switching projects offer to continue editing or explicitly discard.
Do not promise crash-persistent incomplete projects or introduce draft YAML/SQLite
desired-state storage. If Core cannot validate an intermediate configuration,
review one complete bounded session candidate instead; do not bypass BLOCKED validation.

Saving shows semantic changes and affected files, then uses existing
PlanEdit/CommitEdit guards, including revision, ownership, staged Core proof
and concurrency errors. Saving configuration does not apply it to servers.

## 3. Frozen backend gaps and owning milestones

Repository evidence: `docs/work/ui-backend/ui-be-01.md` section 17 names CreateProject, but no
CreateProject implementation was found in `internal`. UI-BE-03 currently writes
managed variable roots and needs initial/staged ProjectSnapshot; it does not
provide a general inventory creation/editor contract.

Required implementation/acceptance work is frozen as follows:

1. Metadata-only create/open lifecycle, identity and safe directory publication.
2. Distinguish an intentionally new metadata-only project from an existing broken
   project; do not downgrade missing inventory errors for arbitrary imports.
3. First-write bootstrap into a Core-loadable project and inventory ownership.
   Preserve Core authority and the established writer; do not assume the current
   PlanEdit accepts a metadata-only initial snapshot.
4. Session lifetime for cross-page incomplete input, reviewed batching, navigation
   guards and a clear unsupported/offline-save explanation.
5. Verify all required capabilities through the selected Execution Node. Creating
   local metadata may work without one; Core validation/commit proof does not run
   Python on the Windows Installer and must not be simulated in React.

No production contract was implemented by this design milestone. In particular, permission
to create new inventory is not permission to rewrite imported human inventory.

## 4. Installation and task observability

Use existing DeploymentPlan, approval and execution lifecycle contracts.
Show runId and Execution Node persistently, plus the current action and elapsed
time. Task details are a table of task, host (when provided), status and duration,
with filters and auto-follow that can be paused without stopping execution.

TASK_STARTED without host is labelled as a task-wide start, not attributed to
all servers. Host results share task UUID; localhost remains distinct from
targets. Redacted names use a fixed label. Do not fabricate percentage completion
from a dynamic task stream or call loss of observer connectivity a failed run.
Show reconnect/degradation independently of the authoritative terminal result.

Future UI consumes typed RunObserver subscriptions through Wails, not the local
events.jsonl file. Installer-side file path is an operator convenience. Navigation
or closing a detail panel detaches the view, not cancellation of the run.

## 5. Review scenarios and implementation order

The mockup now demonstrates: Projects → Create → metadata-only empty project →
server input → topology/deployment/placement → PKI profile → service settings →
review → mock save. Shared form
input survives page navigation. The placement flow is deliberately simplified,
not a validated service topology. Review/save is browser-memory-only, with no
Core call or file write. Populated screens and execution task rows remain
labelled design examples, not evidence of actual backend or target state.
The execution page starts compact; tasks and technical details are expandable.

Subsequent implementation slices expand the simplified flow to catalog-driven
members/settings and the actual backend native-file diff. They must show invalid
input, missing Execution Node, stale revision, unsaved navigation and failed
commit alongside the happy path. The first-write gaps are contractually closed
but remain unimplemented gates of UI-01C/D.

Acceptance for subsequent implementation: initial directory has no inventory or
variable trees; reopen recognizes an intentionally empty project; first reviewed
save writes only required native inputs; cancel/conflict writes nothing; incomplete
input cannot execute; no target contact occurs during create/edit validation;
exported saved state matches what standalone Ansible reads; UI invents no service
defaults, validation results or execution events.
