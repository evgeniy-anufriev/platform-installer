# UI-DESIGN-01 — Installer V2 interaction architecture

Status: DONE (design only). This document defines the future desktop
interaction model; it does not introduce Wails, React, SQLite desired state,
or a second project model.

Static reference views are in [ui-design-01-mockups.html](ui-design-01-mockups.html).

The 2026-09-05 [project creation design](ui-project-creation-design.md) extends
the reference with a metadata-only new-project entry and empty states. UI-01A
accepted its exact lifecycle and ownership boundaries in the
[contract freeze](ui-01a-contract-freeze.md); no production implementation was
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

ADR-027 (2026-09-15) further separates local **Save**, optional **Project
Verify**, and mandatory fresh **BuildDeploymentPlan**. The current binding
semantics are in [the owner-change architecture](ui-save-verify-architecture.md).

Owner decisions `OWNER-APP-CONFIG-01/02` add one required server type to new
Installer-created servers. The UI receives stable IDs and display labels from
the Go-loaded versioned application config; React does not own the list. Type
is descriptive metadata and future template-slot input only. It remains
separate from server identity and cannot select services, placement,
Execution Node or source policy. Legacy missing and locally unknown valid types
remain readable without automatic defaults or rewrites.

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
| Installation | current-revision readiness summary, plan and deployment lifecycle; it does not prepare the Execution Node |
| Logs | historical runs, audit and sanitized diagnostics |
| Help | offline help and troubleshooting entry point |
| About | version and compatibility information |
| Settings | application-local settings; never portable desired state |

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

## 3. Installation as the project home

The page has six compact regions in this order:

1. Project breadcrumb, page title and aggregate state.
2. Execution Node readiness prerequisite summary: selected node, current
   capability/revision state and a link to Servers. There is no setup or
   preparation card on Installation.
3. Saved-project state with a separate optional **Verify project** action and
   `UNVERIFIED/VERIFIED/INVALID/STALE/UNAVAILABLE` indication.
4. A persistent execution stage strip: Plan → Execute → Result. It remains
   visible on every Installation local page and highlights the current stage;
   Project Verify is not an execution authorization stage.
5. Readiness and actionable findings. Each finding contains plain-language
   impact, technical code in Advanced view, and an explicit destination.
6. A plan preview grouped by Servers, Services and Certificates, with one
   page-level **Generate plan** action on Summary.

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

The page may accept a password or private-key path only as a current-session
runtime credential input. A server record stores transport metadata and, at
most, a `SecretRef`; it never stores the password or private-key material in
the project, inventory, logs, diagnostics or application preferences.

The owner-approved Servers layout keeps the vertical order (session credentials,
server list, Execution Node) while compressing session credentials into a
single horizontal desktop row. Its status is shown inline with the explanation;
at narrow widths the fields wrap into a responsive grid. Only long server lists
scroll independently, while the page header and Execution Node remain visible.

### Topology

Topology owns a header-level **Add service instance**
action and **Save topology** action. It has three local tabs:

- **By services:** three panes — deployment list; logical members, roles and
  host placement for the selected deployment; topology validation and concise
  deployment summary. Deployment configuration is opened only through Service
  settings.
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

## 5. Installation local pages

For plans declaring protected service outputs, Installation → Plan collects
and confirms the shared session-only encryption password. The password stays
on the workstation. Output files are saved automatically under the current
project's `secrets/<deploymentId>/`; there is no output-folder selector.
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
format. The page has a write-only input for the runtime password protecting
generated PKCS#12 Java keystore/truststore files; the value is held in the
active Installer session and never redisplayed or saved in project state.
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
session password sits directly below the page heading; the dependency guide is
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
