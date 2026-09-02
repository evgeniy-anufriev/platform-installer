# UI-DESIGN-01 — Installer V2 interaction architecture

Status: DONE (design only). This document defines the future desktop
interaction model; it does not introduce Wails, React, SQLite desired state,
or a second project model.

Static reference views are in [ui-design-01-mockups.html](ui-design-01-mockups.html).

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
Global navigation is a persistent vertical sidebar. Its primary items are:

| Page | Responsibility |
| --- | --- |
| Projects | project selection, path, compatible Core/catalog/payload and project health |
| Servers | physical server inventory, transport and readiness |
| Topology | service instances, placement, roles and entry-point configuration |
| Installation | readiness, plan, current workflow and direct remediation |
| Logs | historical runs, audit and sanitized diagnostics |
| Help | offline help and troubleshooting entry point |
| About | version and compatibility information |
| Settings | application-local settings; never portable desired state |

Installation has local navigation: **Summary**, **Preparation**, **Services**,
**Certificates**, **Execution**. Topology is deliberately not duplicated there.
Findings and service rows link contextually to **Topology** or **Servers**,
depending on whether the action changes placement or physical-host readiness.

The practical desktop minimum is **1024 × 720 px**. At narrower widths the
sidebar collapses to icons with accessible labels, local tabs scroll
horizontally, split panes become stacked, and tables retain horizontal
scrolling rather than hiding data.

## 3. Installation as the project home

The page has five compact regions in this order:

1. Project breadcrumb, page title and aggregate state.
2. Execution Node strip: selected node, address, Ansible/Python capability,
   offline payload, disk capacity and an **Configure and prepare** action.
3. Workflow: Validate → Plan → Execute → Result.
4. Readiness and actionable findings. Each finding contains plain-language
   impact, technical code in Advanced view, and an explicit destination.
5. A plan preview grouped by Servers, Services and Certificates, with one
   page-level **Generate plan** action on Summary.

The Summary action is disabled until the selected Execution Node has completed
its required preparation successfully. Its disabled explanation links to the
Execution Node strip; it is not duplicated inside an individual service or
node card. A subsequent topology/configuration change invalidates the plan,
but does not silently claim that node preparation still applies when its
observed capability fingerprint has changed.

**Configure and prepare Execution Node** opens a modal workflow with: mode
(local Installer, selected project server or external Linux host), selected
host/transport metadata, current-session credential reference, non-secret
readiness checks (SSH/elevation, Python/Ansible, payload, workspace and disk)
and the planned preparation/result. Checking is read-only; preparation is an
explicit action. The dialog neither stores a password/key nor substitutes the
Execution Node for a topology placement.

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

### Topology

Topology owns a header-level **Add service instance**
action and **Save topology** action. It has three local tabs:

- **By services:** three panes — service-instance list; selected instance
  placement and settings; configuration validation and concise summary.
- **By servers:** three panes — server picker; roles and services on the
  selected server; server summary/readiness.
- **Entry points:** settings for explicitly declared ingress/entry points.
  This is not a listener-name or Kafka-only screen; it is a generic placement
  and policy view over a future versioned entry-point contract.

It supports zero to many deployments of every manifest service. A host can own
multiple members, including several members of one Kafka deployment or members
from different deployments. Generic topology speaks only in deployment,
member, role and host; `controller`, `broker` and listener terminology stays
inside the Kafka editor.

Creating or moving a member edits inventory placement. Editing service mode or
deployment-scoped configuration edits its bound `group_vars` document. The
technical deployment ID is stable; rename is unavailable until an explicit
cross-file transition is designed.

Containers remain a future application-runtime capability, not a global
navigation item in the current desktop shell. When introduced, they must stay
separate from infrastructure services.

### Logs

Logs is historical and immutable. It filters run ID, time, status, service and
host, and renders sanitized operation, playbook, duration, findings, task
events, recap and output references. Installation → Execution is only the
current selected run. Neither page displays runtime secret values.

## 5. Installation local pages

| Local page | Primary content |
| --- | --- |
| Summary | Execution Node strip, readiness, findings, plan preview and the only **Generate plan** action |
| Preparation | desired prerequisites, observed readiness, planned preparation and result; opened from Execution Node configuration as needed |
| Services | catalog-driven deployment editor and effective values |
| Certificates | PKI-01 intent, calculated SAN/identity preview and read-only material state |
| Execution | active run progress, confirmation, safe events and final recap |

Preparation hides implementation detail in normal mode. Advanced mode may
show checks such as SSH/elevation, package source and payload checks, but not
passwords or raw private-key data.

## 6. Service editor architecture

The editor is driven by the service manifest and generated configuration
schema, never by a React service catalog. It has a service/deployment tree on
the left and a schema-driven deployment editor on the right:

- managed settings use manifest type, validation, scopes and `ui.label/order`;
- advanced settings use a separate native-property editor;
- manifest `x-reservedAdvancedProperties` is displayed as protected and is
  validated before save/apply;
- optional service-specific panels may improve a complex object editor, but
  receive the manifest model and cannot create parallel rules.

For Kafka, a listener panel presents named listener identity, purpose,
protocol, port, bind/advertised address and one deployment/member `tlsProfile`.
It must not assign certificate profiles per listener. Listener names are data,
not UI constants; the editor supports any declared name and all SERVICE-02A
purposes.

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
format. It never shows private keys, store passwords, password files, raw
OpenSSL/keytool commands or PKI runtime paths. Imported/external CA, renewal,
rotation, JKS and mTLS remain unavailable until their separate contracts exist.

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
when its recorded input revision plus relevant topology, configuration,
runtime-projection and PKI fingerprints still match. The execution flow is:

```text
validate → plan → explicit confirmation → execute → result
```

The backend owns active runs and event normalization, so navigation does not
lose a run. Frontend shows phase, host/service state, current task, safe logs,
retry/cancel capability and final PLAY RECAP. It does not parse callback text.

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

Save is optimistic and transactional: load revision → frontend draft → backend
semantic validation → affected-file preview → user Save → compare revisions →
stage and atomically replace approved documents → reload → Core validation.
External change mismatch opens conflict review; it never overwrites silently.

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
