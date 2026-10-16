# UI-DESIGN-01 — Installer V2 interaction architecture

Status: DONE (design only). This document defines the future desktop
interaction model; it does not introduce Wails, React, SQLite desired state,
or a second project model.

Static reference views are in [ui-design-01-mockups.html](ui-design-01-mockups.html).

The 2026-09-05 [project creation design](ui-project-creation-design.md) extends
the reference with a metadata-only new-project entry and empty states. UI-01A
accepted its exact lifecycle and ownership boundaries in the
[contract freeze](../work/ui-01/ui-01a-contract-freeze.md); no production implementation was
added by that decision.

Owner-approved mockup refinement (2026-09-05) supersedes the older navigation
below: Topology precedes global Certificates and Services pages; Services
shares its editor with the Topology entry;
the project header carries name/path/edit state. One session credential applies
to all target servers. Execution details are collapsed by default. The HTML
includes an explicitly simulated create/edit/review/save flow, never disk writes.

For the current Services page, the owner selected the master-detail layout:
the deployment list and search stay visible on the left while the selected
deployment editor remains on the right. Topology links select the exact
deployment/member in that editor. Long parameter lists scroll inside the
right-hand parameter column rather than moving the service list.

Owner refinement (2026-10-09): runtime-secret reference fields are omitted
from the service and member parameter lists; they are configured through
the existing Secrets dialog. Show its action card only when the service
catalog declares runtime-secret settings or secret inputs.
The card reports presence for that deployment only: green «Установлены»
when all declared inputs exist in the current session, amber «Не установлены»
otherwise. Project references alone do not establish presence; this status
does not authorize execution or replace Core checks.

Data directory overrides for Kafka, Redis, ClickHouse and PostgreSQL use the
same catalog-driven parameter editor. The service package provides the field
label and help text. Redis and ClickHouse configure a root with member
subdirectories; Kafka and PostgreSQL configure the member directory. The UI
shows that changing a path does not migrate existing data. Target path safety
is checked by the service role before mutation.

Execution Node preparation refinement (2026-10-09): after successful
preparation, invoke the normal node check automatically and publish the new
runtime context together with its readiness evidence. Runtime replacement
must not leave the screen at «Не проверено» awaiting another manual click.

After cancellation, discard the current plan projection and refresh the
authoritative installation state. Consumed plans are stale, never approved
or runnable; preserve the cancelled run as history. A new execution requires
a fresh plan and approval, including current secret checks. When state has no
current plan ID, clear the old plan card rather than retaining its approval.
While execution is STARTING/RUNNING/CANCELLING, the Plan tab retains the
immutable run-plan snapshot for viewing. Creating, approving or starting
another plan is disabled; cancellation remains available. A consumed plan
is unavailable for reuse, but that must not erase the active run's snapshot.

Owner-approved refinement (2026-10-06) for Topology → **By servers** selects a
compact three-panel layout: a server picker, a scrollable placement list and a
concise selected-server summary. Placement and service/member configuration
remain separate actions; member settings are labelled as participant settings,
not node settings. Long server and placement lists scroll within their panels.
This refinement supersedes the older static By servers example below, while
preserving the existing service-settings and member-settings navigation.

Owner-selected visual refinement (2026-10-07) for Topology → **By services**
uses design option 1: a dense divided service-instance list without separate
cards, a visually dominant selected-instance and placement panel, and a concise
topology summary. Reuse
the shared Servers icon and soft status-chip language where it helps scanning.
This is presentation-only: do not add inferred service health/readiness,
change topology actions, or alter the existing placement and settings routes.
The current static Topology HTML remains an older interaction illustration;
the production React screen and the UI-01F contract are authoritative for
available data and actions.

Owner-selected visual refinement (2026-10-07) for Topology → **By servers**
uses the same compact picker language: render servers as a divided list with a
soft blue selected row rather than separate cards. In the placement rows, keep
the placement-edit action primary and service/member configuration outlined,
matching the By services action hierarchy. This changes presentation only and
preserves the existing server selection, placement, and configuration flows.

ADR-027 (2026-09-15) further separates local **Save**, optional **Project
Verify**, and mandatory fresh **BuildDeploymentPlan**. The current binding
semantics are in [the owner-change architecture](../work/ui-lifecycle/ui-save-verify-architecture.md).

Owner decisions `OWNER-APP-CONFIG-01/02` add one required server type to new
Installer-created servers. The UI receives stable IDs and display labels from
the Go-loaded versioned application config; React does not own the list. Type
is descriptive metadata and future template-slot input only. It remains
separate from server identity and cannot select services, placement,
Execution Node or source policy. Legacy missing and locally unknown valid types
remain readable without automatic defaults or rewrites.

## Application libraries editor — C design proposal (2026-10-15)

The [C technical plan](../work/application-libraries/milestones/c/c-technical-plan.md)
adds Applications between Services and Installation. The HTML now includes a
synthetic master-detail prototype: library deployments and recipe slots on the
left, scoped settings on the right. It demonstrates navigation, tabs, filtering,
explicit overrides and separate resolved/observed information. Creation/import
and Review/Save buttons describe their intended flow; they do not implement disk
writes or production bindings. No real installation status is simulated as proof.

Reuse the existing project edit/review/save lifecycle and runtime secret dialog.
Core owns identities, precedence, providers and execution. Origin is currently
RESOLUTION_SCOPE, not per-field provenance. Placement remains library membership.
Installation retains B4 services checkbox, saved infra evidence or fixed Verify
prefix, and library Apply/Verify. Approval of this proposed design is required
before production C implementation.

## 1. Product principle

Platform Installer is a visual editor and orchestrator for the same standard
Ansible project used by an Ansible-only operator:

```text
inventory + group_vars + host_vars + ansible-playbook
                    ^
                    | reads and edits approved, user-owned documents
             Platform Installer
```

The portable project directory is the only desired-state authority. Backend
indexes, drafts, plans, observations, run history and UI preferences are
operational state only. `platform_generated_state` remains machine-owned and
read-only in normal UI flows.

## 2. Navigation and application shell

After a project is opened, **Installation** is the default operational page.
Global navigation is a persistent vertical sidebar. Every project page also
shows the current Execution Node application context in the shell; it is not
portable project desired state. Clicking its status opens Servers and the
Execution Node panel. Its primary items are:

| Page | Responsibility |
| --- | --- |
| Projects | project selection, path, compatible Core/catalog/payload and project health |
| Servers | physical server inventory, transport and readiness |
| Topology | service instances, placement, roles and entry-point configuration |
| Certificates | PKI profile intent, Core-derived consumers/SAN preview; no runtime issuance |
| Services | settings of the same topology deployments, including PKI profile references |
| Applications (C proposal) | library deployments, recipe slots, bindings, placement and authored overrides; execution remains on Installation |
| Installation | current-revision readiness summary, plan and deployment lifecycle; it does not prepare the Execution Node |
| Logs | historical runs, audit and sanitized diagnostics |
| Help | offline help and troubleshooting entry point |
| About | version and compatibility information |
| Settings | portable project data-root and resource-name prefix through Review/Save, plus separate application-local information; staged project values are highlighted and say that project Save is still required |

Installation has local navigation: **Summary**, **Plan**, **Execution**,
**Result**. Execution Node selection and preparation belong to Servers, not an
Installation Preparation page. Topology, Certificates and Services are global pages, in that
order; topology creates instances and placement before profile/settings editing.
Findings and service rows link contextually to **Topology** or **Servers**,
depending on whether the action changes placement or physical-host readiness.

The practical desktop minimum is **1024 × 720 px**. At roughly 1250 px and
below, three-pane views collapse into a vertical sequence; at narrower widths
the sidebar collapses to icons with accessible labels, local tabs scroll
horizontally, and tables retain horizontal scrolling rather than hiding data.

The production target is a fixed-height application shell, not a vertically
scrolling browser page. The project, saved/draft state, Execution Node and
installation status remain visible in the compact header on every page. Long
lists, tables, forms and task events scroll inside their own bounded regions;
primary page actions and dialog actions remain reachable at 1024 × 720. A
dialog is centred within the viewport, has a bounded scrolling form and a
visible action footer, and retains keyboard focus until closed. Its opening
control receives focus again on close. The HTML mockup demonstrates these
layout and interaction goals; it is not proof that the production Wails UI
already meets them.

### Shared typography and dialog rhythm

Use the current Certificates screen as the production typography reference:
page title 22 px, section heading 14 px, subsection heading 13 px, primary
text and form controls 12 px, secondary text 11 px, and helper/caption text
10 px. Dense event/data tables may use 10 px to preserve information density;
branding may remain larger. Apply the same hierarchy on every application
screen and modal instead of page-specific heading scales. Modal forms use a
compact 10 px vertical gap, 16 px inner padding, and approximately 1.3 line
height; labels and their controls are separated by 4 px. Long forms keep
bounded internal scrolling and visible action footers.

The global installation label has distinct **plan not ready**, **not started**,
**running**, **failed** and **completed** states. It reflects the authoritative
run/plan lifecycle, not the currently selected tab or the number of callback
events. During execution, progress is confirmed plan actions divided by total
planned actions; the current action, deployment and target host remain visible.
On failure, the last confirmed percentage remains visible. Only a terminal
successful run reaches 100%. An observer disconnect is shown separately from
execution failure. If the backend cannot provide a trustworthy action count,
show the stage and current task without inventing a percentage. The mockup's
state selector changes demonstration data only and never starts execution.
Protected service outputs have a separate delivery status. After a run ends,
Installer attempts delivery only for packages produced by that run; a failed
delivery does not change the run result or block another Start. Pending packages
from older runs remain available for explicit retrieval. Show source run ID and
generation for each package; local delivery does not delete the remote copy.
Owner refinement (2026-10-09): Result uses one action to check the Execution
Node and save undelivered packages encrypted locally. Verified local files
are labelled «Сохранён на инсталлере» and have no receive action. Hide the
combined action when the complete listed set is already delivered; local
receipts and file validation remain authoritative after reopening a project.
If controller preparation reports `OUTPUT_BUSY`, show a plain-language alert
on the Execution screen: a protected service-output package from an earlier
run remains on the Execution Node and was preserved to prevent overwrite. Give
the operator a direct action to inspect and retrieve pending protected outputs;
never recommend deleting the remote package or expose its contents.

### Shared visual language

The Servers screen is the primary reference for restrained monoline icons and
semantic status chips. Reuse that visual language without changing each
screen's approved layout: consistent outline icons for page and section
identity, the shared Certificates-derived typography scale, and compact status
chips with a soft fill. A status chip always includes a text label and a
mnemonic symbol; color alone never carries meaning. Use green for ready or
confirmed, amber for pending or attention-required, red for errors and
destructive actions, blue for selected or informational state, and gray for
unknown or neutral state. Do not tint whole table rows to indicate status.
These rules are presentation only; backend/Core status remains authoritative.

For the Execution tab, the owner refined the layout on 2026-10-09: the existing
full-width status/progress summary remains above two panels in a 1.9:1 width
ratio, with more space for the event table. Fixed table columns keep all five
event fields visible, allowing long task/deployment text to wrap.
The left panel shows events, and the right panel shows ordered plan actions,
their target hosts/deployment and observed status. Each panel scrolls independently.
No separate event-details block is shown.
The execution panels have a 4 px vertical gap and no additional card margins,
so the lower panels fill the remaining height. The global explanatory banner
about local Save is removed from all screens; workspace content uses its space.
Action outcomes come from existing run progress; unavailable evidence is not
presented as success. Narrow windows stack the two panels.
The live table keeps the latest 512 events only
and auto-scrolls to the newest event on updates; it has no pagination. This is
presentation-only and does not change run lifecycle, progress calculation or
the separate «Журналы» page.

## 3. Installation as the project home

The page has six compact regions in this order:

1. Project breadcrumb, page title and aggregate state.
2. Execution Node readiness prerequisite summary: selected node, current
   capability/revision state and a link to Servers. There is no setup or
   preparation card on Installation.
3. Saved-project state with a separate optional **Verify project** action and
   `UNVERIFIED/VERIFIED/INVALID/STALE/UNAVAILABLE` indication.
4. Compact current-stage status beside the Installation title, such as
   “Текущий этап: План · ожидает одобрения”. It remains visible on every
   Installation local page and reflects the authoritative plan/run lifecycle.
   The Summary/Plan/Execution/Result tabs are navigation only; there is no
   second stage strip. Project Verify is not an execution authorization stage.
5. Readiness and actionable findings. Each finding contains plain-language
   impact, technical code in Advanced view, and an explicit destination.
6. A plan preview grouped by Servers, Services and Certificates, with one
   page-level **Generate plan** action on Summary.

The Plan tab shows the approved plan and its ordered actions. Once approved, a
sticky bottom action bar exposes **Start execution**; it remains disabled while
the run is active or any existing plan/runtime prerequisite is unmet. When
blocked, the action area lists every known plan finding and unmet prerequisite,
including any missing session-only credential, with a safe explanation and
code. It does not add a Certificate-page link; certificate secrets remain
configured on Certificates.
Approval checks that every password required by the fresh Core plan is present
in the current session. Missing entries are listed by service deployment and
field; the plan remains available for retry after entering them on Services.
Approval and Start errors appear in a dedicated card directly below the plan
summary, before protected output settings, with the safe machine code followed
by its Russian explanation.
After an approval attempt fails, keyboard focus moves to that error card,
including when a repeated attempt returns the same error.
Immediately before Start, Go checks the same requirements again because a
session secret may have expired or been cleared after approval. Conditional
service inputs follow their existing operation-specific runtime rules.
The phase list uses collapsible summaries with action counts and target nodes;
long phases initially show a few actions with an explicit control to reveal the
rest. The protected-output password form is collapsed after the password is
set and open only while it still needs to be provided.

The Summary action requires READY Execution Node, a saved canonical project and
no unsaved edit-session changes. It always invokes fresh
`BuildDeploymentPlan`; prior optional Project Verify is neither required nor an
authorization shortcut. Plan findings decide whether approval and
`StartExecution` can follow. Its disabled explanation links to the Servers
Execution Node panel or Save state. Installation never selects, prepares,
bootstraps, activates or updates the Execution Node.

The UI distinguishes desired state, observed state, finding, proposed action
and execution result. A green TCP check is not presented as Kafka health;
Kafka status remains a result of the corresponding verification entrypoint.

## 4. Global pages

### Projects

Project shows display name, optional technical ID, opened path, inventory
source, `ansible.cfg`, Core/catalog/payload compatibility, execution-node
binding and health. Advanced mode shows document origins and compatibility
details. It does not contain service settings or placement editing.

It also owns the portable-project transfer workflow: **Import project** and
**Export project**. These actions are project lifecycle operations, not a
replacement for normal Git/Ansible workflows.

#### Export modes

The export dialog has two explicit modes:

| Mode | Carries | Removes or replaces |
| --- | --- | --- |
| **Full configuration** | canonical desired project documents: server inventory and transport metadata, service deployments and settings, explicit member placement/topology, endpoint/PKI intent, compatible catalog lock and artifact lock | facts, reachability/elevation results, generated state, plans, run history/logs, runtime workspaces and secret values |
| **Template** | the same service, configuration, topology and intent shape | concrete servers and execution-node selection are replaced with deterministic, first-class slots `SERVER-1`, `SERVER-2`, …; every placement formerly using one server refers to its one corresponding slot |

Secret references may be represented as opaque metadata only when the portable
project contract supports them; password values, private-key material, token
values and PKI private keys are never exported. The exported form is a
versioned portable project bundle; its exact container representation and
template-slot schema are an Ansible Core contract, not a UI-defined DTO.

#### Import flow

Import is preview-first and creates a new project directory. It never merges
or overwrites an already opened project. The preview shows the format/schema
and Core/catalog compatibility, export mode, counts of service deployments and
role placements, and any safe findings. For a template it presents every slot
with three choices: bind it to an existing server, add a desired server through
the standard Servers form, or leave it unresolved. One binding rewrites every
placement referencing that slot. Unresolved slots are allowed to preserve a
reviewable topology, but become `ACTION_REQUIRED` and block plan/apply until
they are resolved.

After a full import, servers may retain safe desired transport metadata and
opaque credential references. The UI requires the operator to bind an
unavailable runtime credential through the current-session secret broker; it
does not prompt to copy a credential into the imported project. The backend
validates the imported bundle and target document revisions before creating the
new directory, preserves supported unknown extension fields, and surfaces an
explicit incompatibility rather than silently migrating semantics.

### Servers

Servers is the physical-host page: inventory, transport metadata, readiness and
host-local preparation. It provides **Add server**, per-host editing, **Check
all servers** and **Check configuration** actions. The inventory row shows the
desired host/transport declaration, while its expanded read-only detail shows
the last discovered hostname, OS, architecture, capacity, relevant runtime
capabilities and connection observation. It does not own deployment placement
editing.

Execution Node uses one **Статус** indicator for its latest check and
preparation: **Не проверен**, **Проверен: Требуется подготовка**,
**Проверен: Подготовлен**, and explicit unavailable, incompatible, blocked or
error states. An existing but older active runtime is **Проверен: Требуется
обновление**, not **Подготовлен**. The check compares the observed active
bundle digest with the verified project bundle and explains a mismatch before
plan creation or execution. A newer preparation result replaces the older
check state; a later check supersedes the prior preparation display. After the
operator confirms preparation, the status reads **Выполняется подготовка**
until the operation returns its final result.

The page may accept a password or private-key path only as a current-session
runtime credential input. A server record stores transport metadata and, at
most, a `SecretRef`; it never stores the password or private-key material in
the project, inventory, logs, diagnostics or application preferences.

The owner-approved Servers layout keeps the vertical order (session credentials,
server list, Execution Node) while compressing session credentials into a
single horizontal desktop row. Its status is shown inline with the explanation;
at narrow widths the fields wrap into a responsive grid. Only long server lists
scroll independently, while the page header and Execution Node remain visible.

Previous-run inspection belongs to an outline button inside the Execution
Node panel on Servers. After inspection, show one previous run ID, its original
revision and authoritative state, with **Подключиться** for an active run.
Attach restores Installation / Execution through the existing reconnect,
subscription and Cancel methods; it never repeats Start. No history/status list
or separate recovery page is added. When bundle detection on Project is blocked by an
unconfirmed run, show a Russian explanation and a link to Servers: restore SSH
credentials and host-key trust there, then choose **Проверить прежний запуск**.
Do not show `INSTALLATION_RUN_ACTIVE` as the operator-facing explanation.

### Topology

Topology owns a header-level **Add service instance**
action and **Save topology** action. It has three local tabs:

- **By services:** three panes — deployment list; logical members, roles and
  host placement for the selected deployment; topology validation and concise
  deployment summary. The selected deployment pane shows concise identity,
  service, mode, placement and state facts, followed by role-first host cards.
  Member cards open the matching member section of Service settings; the
  aligned deployment action opens settings for the selected service instance.
  Placement editing is the single route for adding, moving or clearing
  assignments (removing every row and applying an empty placement clears it).
  Keep one action row for placement, instance settings and deletion; do not
  repeat settings buttons inside each host card.
- **By servers:** three panes — server picker; roles and services on the
  selected server; server summary/readiness.
- **Entry points:** derives one row per endpoint-capable deployment with an
  `endpointGroup`: service, group, resolved FQDN and VIP. Editing assignment
  writes `serviceDeployment.endpointGroup`; editing a group writes only its
  domain and wildcard. Provider-side `endpointGroupRef`, `virtualRouterId` and
  `virtualAddresses` remain read-only from fresh Core evidence in UI-01F;
  their editing and related provider/consumer integration semantics belong to
  UI-NET-01, which precedes UI-01G because provider VIPs may affect certificate
  SAN. UI-01G remains the Certificates editor. This page does not edit endpoint bindings, aliases, listener names,
  ports or Kafka endpoints. Transport/routing UI is deferred with NET-03.
  The screen uses three side-by-side panels for endpoint groups, consumer
  assignments, and Provider/VIP. Invalid Core findings and unverified provider
  draft changes remain visible as compact notices; the UI does not calculate
  endpoint addresses or PKI/SAN effects.

It supports zero to many deployments of every manifest service. A host can own
multiple members, including several members of one Kafka deployment or members
from different deployments. Generic topology speaks only in deployment,
member, role and host; `controller`, `broker` and listener terminology stays
inside the Kafka editor.

Creating or moving a member edits inventory placement. Editing service mode or
deployment-scoped configuration edits its bound `group_vars` document. The
technical deployment ID is stable; rename is unavailable until an explicit
cross-file transition is designed.

**Configure service** in the By services view is a second navigation entry to
the same schema-driven **Service settings** detail screen opened from
the global Services page. It does not create a topology-specific configuration
editor or a parallel save path.
The selected deployment also lists its current member-to-host placements and
offers **Configure member** for each `(deploymentId, memberId)`. The By servers
view offers the same navigation from each member assignment. Both routes open
the existing member section of Service settings; host-scoped deployments,
which have no member identity, open deployment settings instead.

Containers remain a future application-runtime capability, not a global
navigation item in the current desktop shell. When introduced, they must stay
separate from infrastructure services.

### Logs

Logs is historical and immutable. It filters run ID, time, status, service and
host, and renders sanitized operation, playbook, duration, findings, task
events, recap and output references. Installation → Execution is only the
current selected run. Neither page displays runtime secret values.

### Help

Help is an offline knowledge entry point with categories for Project and bundle,
Servers, Services and topology, Certificates, Verify and install, Logs, and
Errors. The landing view contains search and category cards. Selecting a
category opens an article list beside the selected article; search results use
the same reading layout. Articles explain the current UI contract with concise
steps, cautions where needed, and a link to the related application page.
Troubleshooting articles belong to Errors. Help content does not run Core or
change a project.

## 5. Installation local pages

For plans declaring protected service outputs, Installation → Plan collects
and confirms the shared session-only encryption password. The password stays
on the workstation. Output files are saved automatically under the current
project's `secrets/<deploymentId>/<packageId>/`; there is no output-folder selector.
Installation → Result shows safe delivery status and the completed location.
Service credential inputs remain in the selected service's Secrets dialog.

| Local page | Primary content and boundary |
| --- | --- |
| Summary | Execution Node strip, readiness, findings, plan preview and the only **Generate plan** action |
| Plan | Core-owned action order, dependencies, deployments and exact target hosts, with Execution Node shown separately. Empty, stale and blocked plans are explicit; editing configuration invalidates approval. Generate remains on Summary; approval/start belongs to UI-02, not editor save. No per-task dry-run changes are invented before execution. |
| Execution | active run progress, explicit confirmation state, safe task events and final PLAY RECAP; it is read-only for the active execution and does not parse/redact callback text in the frontend |
| Result | Observed outcome for a specific runId/planId: successful, failed, skipped and unfinished actions, host-level results where reported, timings and verify outcome. Viewing does not rerun verify. Active runs have no final result; observer disconnect is not execution failure. |

On Servers, Execution Node preparation may reveal advanced SSH/elevation,
package-source and payload checks, but never passwords or raw private-key data.
Installation Result groups plan actions by deployment and target, retaining
success, failure, skipped and unfinished outcomes as reported by the backend;
the detailed task stream belongs in a bounded region, not the main progress
counter. The page must distinguish an active run from a completed Result and
must not imply that opening Result performs another verification.

All user-facing navigation, actions, empty states and safe diagnostics use
Russian. Product and protocol names, IDs and standard technical abbreviations
may remain in their original spelling. Unavailable future pages must not look
like available actions. Keyboard focus, visible focus indication and modal
focus return are part of acceptance, not optional polish. Saved project counts
must come from the local managed projection; absence of a current Core snapshot
is displayed as unknown/not checked, never as a misleading zero.

## 6. Service editor architecture

The editor is driven by the service manifest and generated configuration
schema, never by a React service catalog. It has a service/deployment tree on
the left and a schema-driven deployment editor on the right:

The global **Services** page opens this editor through **Open service
settings** and provides a visible return to Services. The editor is a distinct
detail screen, not an expanded middle pane of the generic overview. Its
sections, fields, validation and help are declared by the selected service
package; consequently service-specific terms belong here only.

- managed settings use manifest type, validation, scopes and `ui.label/order`;
- settings follow the package's numeric `ui.order` across sections, so data
  directory settings can remain first without service-specific React rules;
- advanced settings use a separate native-property editor;
- manifest `x-reservedAdvancedProperties` is displayed as protected and is
  validated before save/apply;
- optional service-specific panels may improve a complex object editor, but
  receive the manifest model and cannot create parallel rules.

For Kafka, a listener panel presents named listener identity, purpose,
protocol, port and bind/advertised address. Kafka resolves one effective
`tlsProfile` at deployment/member scope; every SSL listener in that effective
member configuration consumes that same profile as read-only derived data.
The UI never assigns a certificate profile or independent `tlsProfile` to one
listener. A permitted member override changes the effective profile for all of
that member's SSL listeners. Listener names are data, not UI constants.

### Metadata sufficient now and gaps

`service.yml` already supplies service ID, modes, roles, placement constraints,
setting kind/type/scopes/validation, labels/order, advanced boundary and
reserved properties. `configuration.schema.json` supplies structural schema.
No new Core topology model is required for a read-only UI design.

Before UI-01, add only versioned presentation metadata to service packages:

- field description/help and group/section;
- renderer hint for complex objects (`keyed-object`, `listener-map`, raw JSON),
  not a frontend business rule;
- display/enable conditions expressed as declarative metadata where needed;
- explicit user-facing role labels and optional role ordering;
- reserved-property messages suitable for normal UI.

Do not add default values to schemas: role defaults remain the authority.

## 7. PKI editor

Certificates presents Infrastructure TLS with CA, certificate profile, TLS
profile and materialized-state sections. Normal flows expose MANAGED CA,
profile references, calculated SAN preview, Materialize and Verify. Defaults
are shown as inherited role defaults and are not written merely because they
are displayed.

Advanced mode may show issuer, SAN, EKU, validity, fingerprints and store
format. TLS profile settings provide a write-only password input for generated
PKCS#12 Java keystore/truststore files; the value is held in the active
Installer session and never redisplayed or saved in project state. The project
stores only the fixed opaque reference `runtime:pki-store-password`.
Replacing only this password updates the current session directly and does not
create a project draft command. Changing TLS profile settings still creates a
draft command; the password remains session-only in either case.
Private keys, password files, raw OpenSSL/keytool commands and PKI runtime
paths remain hidden. A password change can rebuild derived stores from the
existing validated PEM identity without issuing a new certificate. Imported/
external CA, automatic certificate renewal, JKS and general mTLS editing remain
unavailable until their separate contracts exist. An explicitly changed
managed certificate request may be reissued only as an exact, Core-selected
action in a fresh approved Installation plan. The Certificates page does not
trigger a separate issuance path.

The owner-approved Certificates layout uses a left-side ordered PKI type
navigator and a right-side editor/list for the selected type. The PKCS#12
session password is entered in TLS profile settings; the dependency guide is
a compact strip. Its graph is a CA → certificate profile chain that branches
to independent TLS profile and certificate scope objects. The bottom Core
section remains read-only evidence and verification, not certificate issuance.

## 8. Effective values, origins and opaque data

The UI displays Core's resolved projection; it does not evaluate Ansible.
For a managed setting it shows a value state and source:

| Projection state/source | UI treatment |
| --- | --- |
| `RESOLVED` / role default, deployment or member source | display value and source |
| `STATIC_REFERENCE` | display resolved value and reference |
| `DEFERRED` | expression, read-only effective value |
| `UNRESOLVED` or `CYCLIC` | blocking finding with source location |
| computed/reserved | read-only derived label |

`physicalOrigin` becomes an Advanced “Source” link, not a primary form field.
The backend must expose logical relative path, source kind and writable status;
it must not invent physical placement from variable names.

Unknown variables are preserved. The UI classifies them as:

- **KNOWN:** manifest-mapped and editable through a typed control;
- **OPAQUE:** preserved, optionally visible in an Advanced raw-variable view;
- **OPAQUE_EXPRESSION:** visible but not visually editable;
- **UNKNOWN_MANAGED_PROPERTY:** a blocking validation finding.

The UI never replaces an expression with a resolved value or removes an opaque
value during a save.

## 9. Findings, plans and execution

One presentation vocabulary is used everywhere: `PASS`, `WARNING`, `BLOCKED`,
`UNKNOWN` and `ACTION_REQUIRED`. A finding has a stable code, user summary,
affected object, severity, safe technical detail and a typed navigation target
such as `service/deployment/setting`, `topology/host` or `certificates/profile`.

An edit invalidates validation and plan snapshots. A plan is executable only
when a fresh authoritative Core plan has the exact approved semantic
fingerprint. The execution flow is:

```text
validate → plan → explicit confirmation → execute → result
```

The backend owns active runs and structured event delivery, so navigation does
not lose a run. Frontend shows phase, host/service state, current task, safe
logs, retry/cancel capability and a structured final recap. It does not parse
callback text.

## 10. Ansible ownership and write model

| UI action | Canonical owner | Backend action |
| --- | --- | --- |
| add deployment / change mode | bound `group_vars` desired-state document | typed patch, preview and atomic write |
| change managed deployment setting | bound `group_vars` document | typed patch, preserve unrelated data |
| add/move/remove member or member override | inventory `platform_deployments` | typed inventory patch |
| add host / transport metadata | inventory or `host_vars` | typed host patch |
| configure PKI intent | bound PKI `group_vars` document | typed patch |
| view Kafka IDs / PKI fingerprints | `platform_generated_state` | read-only query |
| submit secret | runtime SecretRef session | in-memory broker only |

Save is optimistic and transactional: load revision → frontend draft → local
structural/safety validation and affected-file preview → user Save → compare
revisions/digests → stage and atomically replace approved documents → local
source-view refresh. Core infrastructure validation is a separate optional
Project Verify; execution still requires fresh `BuildDeploymentPlan`. External
change mismatch opens conflict review; it never overwrites silently.
When structural review returns `NO_CHANGE` with no affected documents, explain
that there is nothing to save and do not offer a redundant retry. Session-only
secrets such as the PKCS#12 password remain available for execution but are not
written to project files.

## 11. YAML and Jinja preservation

ADR-018 accepts semantic, not byte-identical, round trips. That is sufficient
for generated state but insufficiently precise for an arbitrary user-authored
document editor. UI-01 must therefore use these boundaries:

1. Read every project without mutation.
2. Write only a backend-approved, explicitly bound source document and only
   the selected typed subtree.
3. Preserve unrelated YAML nodes semantically; surface that comments, ordering,
   quoting and anchors cannot be guaranteed by the accepted policy.
4. Treat Jinja, lookups, vault values, anchors/aliases and unsupported YAML
   constructs as `RESOLVED_READONLY`, `OPAQUE_EXPRESSION` or
   `UNSUPPORTED_FOR_VISUAL_EDIT`; offer source inspection, not destructive
   visual editing.
5. Reject a save if external file fingerprint differs from the loaded revision.

This does not select a YAML AST framework. It identifies the exact future
writer acceptance criteria: an existing Ansible project with opaque variables
and expressions must remain semantically runnable after a supported edit.

## 12. Backend and frontend responsibilities

The future Go backend opens projects, reads catalog/schema metadata, asks Core
for resolved projections, maps typed edits to approved files, validates,
previews, persists with revision checks, brokers runtime SecretRefs, invokes
standard playbooks, normalizes safe events and owns run history.

Frontend owns drafts, page selection, forms, topology rendering, source/value
presentation and requests for query/save/execute. It must not parse/write YAML,
implement Ansible precedence, calculate Kafka runtime configuration, generate
certificates or mutate generated state.

Proposed versioned backend/UI query and command contracts:

- `ProjectSnapshot { revision, documents, catalogDigest, findings }`
- `ResolvedEditorModel { deployments, members, effectiveValues, origins,
  opaqueVariables, fingerprints }`
- `EditPreview { baseRevision, patches, affectedFiles, findings, consequences }`
- `SaveProject { expectedRevision, approvedPatchIds }`
- `RunSnapshot` and `RunEvent { runId, stage, target, status, safeOutputRef }`
- `SecretAvailability { secretRef, state }` — never a secret value.

## 13. Compatibility and acceptance

The generic UI model is valid for Kafka, PostgreSQL pg_auto_failover, Redis
Sentinel, ClickHouse/Keeper, Vault Raft, HAProxy and multiple Keepalived
clusters: it models service deployment, members, roles and hosts, not Kafka
controllers/brokers. Detailed forms remain package-provided specialization.

Future UI acceptance: open a valid SERVICE-02A Ansible-only project, display
hosts, Kafka deployment/members/listeners/TLS/PKI state without conversion,
close Installer, then run the same project through standalone
`ansible-playbook` successfully.

## 14. Owner decisions before UI-01

1. Open-workspace YAML policy: which unsupported YAML/Jinja constructs make a
   document read-only versus requiring an explicit raw/source workflow.
2. Write-placement policy: preserve each existing bound `group_vars` location
   or migrate supported edits to one canonical service file.
3. File-origin representation and stable backend patch identifiers.
4. Deployment-ID rename: prohibit initially (recommended) or design a
   transactional cross-file migration.
5. Persistent run-history location, retention and export policy.
6. Confirm the 1024 × 720 minimum practical window size.

## 15. Proposed implementation sequence

UI-DESIGN-01 is complete. The next product service should be **POSTGRES-01**:
it validates that service metadata and generic topology are not Kafka-shaped.
Production UI then requires a minimal backend read/write and run adapter before
React/Wails work; UI-01 cannot safely precede that backend boundary.

Recommended UI-01 scope: open an existing project read-only, Projects, Servers
and Topology (including Entry points) views, catalog-driven managed-setting display, effective source and
findings navigation, draft/preview/save for a small supported literal subset,
and optimistic external-change detection. Execution, secret entry and rich PKI
editing follow only with their backend contracts.

### Owner refinement: server information (2026-10-08)

Servers and Execution Node use one «Проверить сервер» action. Its modal obtains the SSH fingerprint and requires explicit confirmation; the same exact key supplies installation trust. Read-only Go observations appear in one compact, non-wrapping line below the server: hostname, OS/version/architecture, CPU/RAM, server time and last successful check in Russian Moscow time. «Проверен» is independent of «Сохранён» and runtime readiness. A failed/stale session cannot publish successful observations. This supersedes separate key/check controls in the earlier mockup; see [plan](../work/server-information/server-information-check-plan.md).


### B4 owner-approved Installation scope control (2026-10-14)

After the user builds the initial plan, its services block on the Plan tab has
an Infrastructure checkbox. It is not shown before a plan or above the tabs.
The reviewed plan remains visible when the choice changes; services actions are
muted, with Apply rows omitted locally while the displayed plan belongs to the
previous scope. Checked selects
FULL_PROJECT; unchecked selects APPLICATION_LIBRARIES_ONLY and visually mutes
infrastructure. While the displayed plan belongs to the previous scope, the Plan
tab locally omits SERVICE_APPLY rows from the services block but leaves the
underlying Core plan unchanged; this is only a display projection, not an
execution plan. Once Core returns the selected-scope plan, the UI displays it
without filtering. If fresh Core Build finds compatible saved infrastructure Verify
evidence, the plan contains only library Apply/Verify. If that evidence is missing
or stale, the same plan includes infrastructure Verify before library Apply/Verify;
it does not include infrastructure Apply or create another plan/approval. A Core
Verify failure stops the run before libraries. Libraries always run Apply/Verify
and have no checkbox in this stage. The choice is local
presentation state retained across navigation, not portable desired state.
On Approve, Core builds the selected scope; the previous plan cannot be approved
or started for that selection. During an active run the choice is locked. Existing Plan/Approve/Start/
Execution/Result are reused. Core observations display current plan verification,
source run IDs separately in Advanced, and cached observations as UNKNOWN only.
The full application editor and further visual redesign remain C scope.
The static mockup remains a generic full-plan example and does not demonstrate
the checkbox-driven local display projection; it is not an execution-scope
authority.

B4 owner amendment (2026-10-14, final): the services checkbox is local presentation
only and never calls Core. On Approve, a changed scope first builds an authoritative
plan with the existing mode-aware API. Only that returned plan can be approved.
New acknowledgements, changed runtime/revision/node, or re-including infrastructure
require reviewing the returned plan before another confirmation. No separate Build
click is required for the scope change. Libraries remain Apply -> Verify; Start is
unavailable while the displayed plan differs from the selected scope. This replaces
the earlier B4 instruction requiring an explicit fresh Build after checkbox changes.

B4 owner-authorized credential completion (2026-10-15): Plan adds a compact «Секреты библиотек» dialog, using the existing runtime-secret dialog styling and Core-derived applicationInputs. The selected service's Secrets dialog remains unchanged. Password values remain in the existing session Broker/lease, never desired state. This is a minimal integration addition to the Installation mockup, not a library editor.

C owner refinement: the application slot Parameters tab edits image, host
(published) and container ports, inherited from package defaults. Explicit overrides
have independent reset actions; reset removes authored values rather than copying
defaults. Core remains responsible for resolution and port conflicts.

C owner refinement: add application Secrets for credentials of every declared
connection, using typed source settings and the existing runtime input dialog.
Connections without username/password requirements show their actual TLS/PKI/Vault
binding contract. Do not infer a password requirement from a service name.
