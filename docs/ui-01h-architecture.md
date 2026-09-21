# UI-01H — Service settings and PKI profile assignments architecture

Status: **H1–H3 IMPLEMENTED; H4 ARCHITECTURE REMAINS NEXT**

Milestone: **UI-01H**

Implementation status: **UI-01H1, UI-01H2 and UI-01H3 DONE; UI-01H4 NEXT**

Prerequisites: UI-01F, UI-NET-01 and UI-01G are DONE. This document is
documentation-only. It does not authorize UI-01H implementation, service
apply/verify, PKI materialization, or a change to standalone Ansible/Core
semantics.

## 1. Goal

UI-01H implements the global **Services** page for deployments created in
Topology. It edits only catalog-declared service configuration overrides and
uses the existing shared lifecycle:

```text
typed Service settings intent
  -> one EditSession
  -> structural Review (at most 16 commands)
  -> guarded local Save
  -> authoritative local reopen
  -> separate optional Project Verify
```

The page is not another deployment editor. Deployment identity, service type,
mode and placement remain owned by **Topology**; endpoint-provider relations
remain owned by UI-NET-01; PKI entities remain owned by **Certificates**. A
Topology selection opens this same Services editor with the deployment already
selected. Returning to Topology retains the selection and unsaved shared
draft.

UI-01H is not a universal service-settings editor. It is a safe editor for the
provably understood subset of managed settings. A setting is editable only
when its complete safe semantics are established by a closed primitive
descriptor or trusted catalog metadata. Unknown semantics are always
`UNSUPPORTED`/read-only; the canonical value remains intact for a later,
explicitly approved contract extension.

UI-01H makes the existing `configuration.tlsProfile` reference selectable from
saved TLS profiles. It does not issue, materialize, reissue, distribute or
inspect certificates. Core remains the sole authority for effective Ansible
configuration, certificate identity/SAN, provider-VIP effects, PKI impact and
`CERTIFICATE_REISSUE_REQUIRED`.

## 2. Mockup and current seam reconciliation

The pre-start mockup check covers:

- the global navigation order **Project → Servers → Topology → Certificates →
  Services → Installation**;
- the Services list and selected deployment editor;
- the explicit entry from a selected deployment in Topology;
- the TLS-profile selector and link back to Certificates; and
- shared Save/Discard state rather than a service-local save action.

The mockup is aspirational in two material places. Its apparent default values
and completion statuses are not Core facts, and its wording about an
``unverified input`` predates the accepted Save/Verify split. UI-01H instead
shows only the directly saved override as **Set**, an absent override as
**Inherited**, and the existing project status as **Saved / changed / verified
/ stale / invalid**. It never calculates an effective default locally.

The current React shell deliberately has a disabled Services navigation item,
and Topology deliberately has a disabled **Configure service** action. Those
are correct before this milestone. UI-01H enables both only after its one
Services page exists; it must not create a second route or a placeholder page.

## 3. Authority and fixed boundaries

1. The portable Ansible-native project remains the only desired state.
   `configuration.settings` and role defaults remain the service package/Core
   contract; React never parses project YAML, service YAML or Ansible values.
2. A service manifest and the project's exact verified catalog define setting
   vocabulary, allowed scope, type, bounds, UI metadata and reference kind.
   Go projects a bounded typed subset; React never receives raw catalog maps
   or schemas. React and Go never infer semantics from setting ID, service ID,
   label/description, object shape or property names such as
   `passwordSecretRef`, `dnsServerRef` or `serviceDeploymentRef`.
3. Go owns command admission, catalog binding, final-state reduction,
   reference integrity, managed-document ownership/path checks and the
   existing atomic transaction. It must not encode `kafka`, `haproxy`,
   `postgresql`, listener, VIP or role-variable branches.
4. Core owns validation of the saved revision through Project Verify and all
   resolved/effective values. A local Save requires neither Core nor a READY
   Execution Node. A Verify is target-free, requires READY, and never changes
   files. Fresh `BuildDeploymentPlan` remains the mandatory execution gate.
5. Runtime credentials, stable SecretRefs and secret values never enter an
   editable UI-01H control, Service page command value, Review, local typed
   value projection, log or event stream. There is no approved trusted
   metadata seam for credential-object editing in this milestone. Credential-
   or secret-shaped settings are `UNSUPPORTED`/read-only; their canonical
   values remain writer-preserved. UI-01H never infers secret semantics from a
   setting/property name, label, string shape or object shape and performs no
   secret discovery or resolution.
6. `ADVANCED`, protected, opaque, unmodelled or structurally unsupported
   settings are preserved verbatim by the managed writer but are not editable
   in UI-01H. The UI explains that they are read-only/deferred; it does not
   offer an unsafe generic YAML/JSON escape hatch.

## 4. Additive edit contract

### 4.1 Active v1alpha8

`project-edit/v1alpha8` is a new additive, closed contract. It contains the
complete unchanged v1alpha7 operation set plus these two operation families:

| Operation | Required fields | Meaning |
| --- | --- | --- |
| `SetServiceConfigurationValue` | `deploymentId`, `scope`, `setting`, `value`; `memberId` exactly when `scope=MEMBER` | Set one direct managed override. |
| `RemoveServiceConfigurationOverride` | `deploymentId`, `scope`, `setting`; `memberId` exactly when `scope=MEMBER` | Remove one direct managed override, returning it to inherited state. |

`scope` is the closed enum `DEPLOYMENT | MEMBER`. For `DEPLOYMENT`, `memberId`
is forbidden; for `MEMBER`, it is required and identifies the member within
the selected deployment. This is a deliberate closed operation, not a generic
JSON patch and not a mutation hidden in a placement reconcile.

`value` is present only for Set, is non-null, is bounded JSON data, and must
conform to the catalog-declared setting descriptor before candidate mutation.
Clear is always the separate Remove operation, which keeps `false`, `0`, an
empty allowed string and an empty allowed collection distinguishable from an
absent override. Removing an already absent override is an explicit safe
no-change.

v1alpha1 through v1alpha7 stay immutable compatibility inputs. Historical
configuration commands in older versions are not reactivated as a second,
Core-coupled Save path. New sessions emit v1alpha8 only. The one existing Go
`EditCommand` gains the minimum `scope` and `memberId` fields and remains the
only internal command model.

### 4.2 Admission and catalog availability

Set and Remove require the exact READY catalog locked by the opened project,
because both need proof of the setting vocabulary and permitted scope. The
reducer verifies, without service-name branches:

- the final-state deployment exists and its service type/mode match the
  catalog descriptor;
- `setting` is declared `MANAGED`, is editable by the supported form shape,
  and admits the requested scope;
- a member target exists in the final placement of that deployment when
  `scope=MEMBER`;
- the submitted value has the descriptor's exact closed primitive shape, enum
  and declared bounds; and
- a pattern is locally editable/validated only when it belongs to the explicit
  closed validator subset. Arbitrary JSON-Schema regular expressions and
  unsupported schema constructs make the descriptor `UNSUPPORTED`; Go does
  not become a generic JSON-Schema engine.

When the catalog is unavailable or incompatible, `ManagedProjectView` remains
the direct-owned saved-state projection. It may expose only bounded stable
setting IDs and override presence where these can be read safely; it does not
expose arbitrary raw configuration values to React. The page labels such rows
`UNKNOWN`/`UNSUPPORTED` and disables every configuration mutation. It must not
guess a descriptor, type or reference kind, reclassify an unknown field, or
erase it. A later exact catalog reopen may join that saved projection and
restore typed values/editing. This narrow availability rule is intentional:
unlike a pure topology delete, config removal needs vocabulary proof to avoid
deleting an operator-owned or no-longer-managed value.

## 5. Catalog and managed read projections

### 5.1 Bounded descriptor

The existing lock-bound `ProjectCatalogView` currently exposes no service
settings. UI-01H extends it with a deterministic `configurationSettings` list
per service, sorted by UI section/order/label/ID. Each item is a closed typed
descriptor containing only:

- setting ID, kind (`MANAGED`, `ADVANCED` or `PROTECTED`), supported scopes
  and presentation label/description/section/order;
- one closed editor shape: `BOOLEAN`, `INTEGER`, `NUMBER`, `ENUM`,
  `BOUNDED_STRING`, `TLS_PROFILE` or `UNSUPPORTED`;
- bounds, enum literals and the bounded property descriptors required by that
  shape; and
- an optional closed application `referenceKind`, projected only from the
  existing compatible `configuration.settings.*.ui.x-referenceKind`
  extension seam and initially limited to `TLS_PROFILE`.

The projection is generated from the verified service manifest/catalog and
does not disclose role variable names, raw schemas, arbitrary catalog maps or
runtime semantics. A descriptor is emitted as editable only when its manifest
shape and every relevant constraint are safely represented by this closed
projection. `BOUNDED_STRING` requires complete length/bound semantics in the
approved descriptor; when a pattern is present it must belong to the explicit
supported validator subset with identical schema/Go behavior. Unannotated
free-form strings, unknown manifest members, unsupported patterns/schema
constructs, every object/map shape and advanced settings produce a
deterministic `UNSUPPORTED` descriptor rather than a permissive form. `ENUM`
is editable only from its complete closed literal set.

`ui.x-referenceKind: TLS_PROFILE` uses a schema-authorized v1alpha1 extension;
UI-01H does not add or modify a published top-level manifest/catalog v1alpha1
field. `ProjectCatalogView` validates the extension and projects it into the
closed application enum. `TLS_PROFILE` targets the existing managed TLS-profile
collection and participates in the existing generic final-state reference
graph. Unknown extension values fail closed; absent or unsupported values
produce an ordinary or `UNSUPPORTED` descriptor as appropriate and never a
reference-aware editor. Old v1alpha1 bundles without this annotation continue
to open, but their TLS-looking strings are not guessed to be profile
references. There is no `serviceType`, setting-name, label or role-variable
branch in React or Go.

No other reference kind is approved in UI-01H. In particular,
`dnsServerRef` and nested `serviceDeploymentRef` settings remain
`UNSUPPORTED`/read-only; they must not appear as ordinary string/object
editors. Future editability requires an owner-approved closed
`ui.x-referenceKind`, a canonical target collection, final-state
`REFERENCE_NOT_FOUND`/`REFERENCE_IN_USE` semantics and catalog-unavailable
behavior that preserves existing references. UI-01H invents no target
collection.

Credential/secret-shaped settings also remain `UNSUPPORTED`/read-only. No
`SECRET_REF`, `ui.x-secretRef` or equivalent metadata contract is introduced
or inferred in this milestone. Their existing values are writer-preserved.

The initial editability matrix is exact:

| Catalog semantics | UI-01H behavior |
| --- | --- |
| boolean with a closed primitive descriptor | editable `BOOLEAN` |
| integer with complete supported bounds | editable `INTEGER` |
| number with complete supported bounds | editable `NUMBER` |
| complete closed literal set | editable `ENUM` |
| bounded string whose complete validation is in the supported subset | editable `BOUNDED_STRING` |
| trusted `ui.x-referenceKind: TLS_PROFILE` | editable `TLS_PROFILE` selector |
| unannotated free-form string | `UNSUPPORTED`/read-only |
| arbitrary object or map | `UNSUPPORTED`/read-only |
| credential/SecretRef-shaped structure | `UNSUPPORTED`/read-only |
| `dnsServerRef` / `serviceDeploymentRef` semantics without trusted metadata | `UNSUPPORTED`/read-only |
| Kafka/listener-style complex configuration | `UNSUPPORTED`/read-only |
| unknown or incompletely represented semantics | `UNSUPPORTED`/read-only |

This classification is shape/metadata driven only. There are no name-based
exceptions or service-specific allow/deny lists.

### 5.2 Direct owned configuration projection

`ManagedProjectView` gains a bounded configuration section per deployment and
per canonical `(deploymentId, memberId)` placement. Independently of catalog
availability it exposes direct saved override presence and stable setting IDs
where safely available. Typed copied values are exposed only after joining an
exact READY catalog descriptor. It does not expose a role default, Ansible
precedence, an effective value, raw YAML, arbitrary unknown values, opaque
variables or generated state.

Read-only does not mean deletion or reconstruction. Unsupported canonical
values remain in the managed document and are copied forward unchanged by the
candidate/writer. React never receives or resubmits their raw JSON/YAML
payload. Editing a supported sibling must neither remove nor rewrite
unsupported configuration. Without an exact READY catalog, the local view
retains only safely available setting ID/override-presence evidence and labels
it `UNKNOWN`/`UNSUPPORTED`; catalog loss never erases the saved override.

The reader uses the F1 same-opened-object safety and project revision coherence
rules. It is all-or-nothing for consumed managed configuration: malformed
known configuration or a malformed member identity yields the existing safe
managed-project error, never a partial configuration view. Unsupported and
unconsumed fields remain writer-preserved but are not copied to React. Absence
of `configuration` means no overrides and does not materialize an empty map
until a successful Save actually sets one.

The Services page may combine this direct view with a READY catalog only when
both belong to the same coherent canonical project revision. It must discard
selection/form data rather than display a mixed revision after reopen or
post-commit refresh failure.

## 6. Candidate reduction, references and persistence

The v1alpha8 reducer extends the one UI-01D/F/G structural candidate and
managed writer. For deployment scope it changes only:

```text
platform_desired_state.serviceDeployments[deploymentId].configuration[setting]
```

For member scope it changes only the existing canonical member configuration
for the final `(deploymentId, memberId)` placement. It neither converts
placement kind nor rewrites unrelated members, hosts, endpoint groups,
provider data, PKI roots, extensions or opaque configuration.

Final-state reference checks are evaluated after all commands reduce. The
descriptor-driven reference graph is extended for both scopes:

```text
deployment configuration[referenceKind=TLS_PROFILE] -> tlsProfile
member configuration[referenceKind=TLS_PROFILE]     -> tlsProfile
```

The trusted, closed `ui.x-referenceKind: TLS_PROFILE` projection is the only
authority that creates these edges. A TLS-profile delete therefore resolves the
exact project-lock-bound READY catalog even when no other command needs catalog
vocabulary; unavailable or incompatible catalog evidence blocks deletion
fail-closed. There is no `if service == kafka` branch, hardcoded setting name,
or inference from a setting label or role variable. Consequently a
TLS-profile delete returns the existing safe `REFERENCE_IN_USE` when a final
deployment or member override declared by the exact catalog still refers to
it; a set to a missing final TLS profile returns `REFERENCE_NOT_FOUND`.
Unknown/absent reference metadata never enables an editor or creates a TLS
edge. Other reference-bearing settings remain writer-preserved and read-only.

Save retains all established base-revision and digest guards, managed document
ownership and path safety, staging, atomic replacement, rollback/recovery and
post-commit local reopen. It does not call Core, an Execution Node or target
hosts. A semantic setting Save clears the shared draft and makes any prior
verification evidence stale/unverified under ADR-027. `COMMITTED_REFRESH_FAILED`
retains the existing cross-page recovery: bytes are already saved, the draft
is consumed, configuration CRUD is disabled, and only safe read-only reopen
may restore the current view; Commit is never retried.

## 7. Services page UX

The page has a compact two-pane layout:

1. A searchable deployment list shows the saved/final-draft deployment ID,
   service display name, mode and direct draft state. It does not duplicate
   placement controls.
2. The selected deployment shows immutable identity/mode context, a
   deployment/member scope switch only where the catalog admits it, and
   settings grouped by the catalog's presentation section/order.

Each supported field shows **Inherited** when absent and **Override** when a
direct value is present. Set creates one typed intent; **Reset to inherited**
creates the explicit Remove intent. The shared footer uses the existing
Review, Save and Discard controls. It does not add per-field, per-service or
remote save.

The shared Review limit remains exactly 16 acknowledged commands. Form input
may change locally before **Apply**, but Apply appends exactly one Set or Remove
command. After acknowledgement that exact `(deploymentId, scope, memberId?,
setting)` target is locked until Save or Discard; UI-01H performs no backend
coalescing, command rewriting, implicit undo or replacement. The page shows
remaining capacity from the existing shared session state. At zero capacity it
preserves local/draft state, disables further Apply and shows the existing
safe `EDIT_SESSION_LIMIT` recovery: Save the acknowledged draft or Discard all
changes and re-enter.

For a `TLS_PROFILE` field, the control lists only saved IDs from
`ManagedProjectView.PKI.TLSProfiles`, with a clear inherited option and a
visible link to Certificates. Creation/edition of a profile occurs only on
Certificates. The selector never displays Core-calculated certificate identity
or SAN, and a profile selection alone never claims that a certificate is
ready. The ordinary post-Save Verify panel may show current `VerifiedPKIView`
evidence; stale, invalid, unavailable or incomplete evidence shows safe
status/findings only.

Member scope is offered only after selecting a final member of a
member-scoped deployment. Moving an existing canonical member preserves its
configuration with the same `(deploymentId, memberId)` identity and
invalidates only the stale host-bound open form. Deleting that member removes
the configuration target and invalidates the open form rather than retaining
a dangling target. The reducer remains authoritative for final-state
conflicts.

Unsupported/protected settings have a minimal non-editable row with their
safe label and reason. Existing direct values are not rendered as raw payload
and are never dropped when another supported setting is saved. Credential and
secret-shaped settings never receive an input control; the row states that the
setting is preserved but unsupported in this milestone.

## 8. Delivery slices

### UI-01H1 — v1alpha8 contract and bounded projections

- add immutable `project-edit/v1alpha8` as a complete v1alpha7 superset plus
  scoped Set/Remove configuration operations;
- implement command decoding/admission, catalog descriptor projection and
  direct owned deployment/member configuration reopen;
- add descriptor-driven generic TLS reference integrity; and
- prove no Core/Execution Node/target call on Review/Save/reopen.

Acceptance includes v1alpha7 compatibility, final-state member existence,
absence versus false/zero/empty semantics, malformed/unsupported descriptors,
reference failures, canonical no-change and byte/semantic preservation of
unsupported sibling configuration. Tests prove classification without service
IDs, setting/property names or labels.

### UI-01H2 — Services navigation and supported managed forms

- add the one Services route/page, global navigation and Topology selected
  deployment hand-off;
- render the bounded descriptor shapes and direct inherited/override state;
- attach typed intents to the shared draft, Review/Save/Discard lifecycle; and
- render unavailable catalog, unsupported field and refresh-failure states.

Acceptance proves that all paths select the same editor and session, no second
deployment is created, and no raw YAML/catalog data reaches React.

### UI-01H3 — TLS selector and member overrides

- implement catalog-declared TLS-profile selectors and Certificates return
  flow;
- implement final-member scope selection and member override UX; and
- prove credential/secret-shaped and other unapproved reference-bearing
  settings, unannotated free-form strings and every object/map remain read-only
  and writer-preserved.

Acceptance proves profile deletion/set reference protection, draft-safe
cross-page navigation, no credential/SecretRef/plaintext input or leakage, and
stale verification after a semantic setting Save.

### UI-01H4 — Windows/RED OS acceptance and regression

- Windows Wails service configuration Save/reopen without an Execution Node;
- READY-node target-free Verify evidence and stale/invalid display;
- RED OS race/target-free Core validation as relevant; and
- full Go, frontend, Wails, catalog/schema reproducibility, secret audit and
  diff-check gates.

No slice starts service installation, certificates materialization, target
contact or UI-01I export work.

## 9. Required evidence

Before UI-01H is marked DONE, evidence must show:

- a complete v1alpha8 schema → decoder → session → reducer → writer → reopen
  path, while v1alpha1–v1alpha7 stay compatible;
- catalog-lock-bound, stable-order, bounded descriptor projection with no raw
  catalog/schema maps to React;
- unchanged published manifest/catalog v1alpha1 contracts, compatible
  `ui.x-referenceKind: TLS_PROFILE` projection and old-bundle read-only
  behavior;
- deployment and member setting set/reset, final-state draft interactions and
  exact preservation of unrelated/unsupported configuration;
- exact editable/read-only matrix coverage, including no name/shape inference,
  no raw unsupported payload in React and no generic schema engine;
- TLS-profile assignment/clear/reference deletion behavior without PKI
  calculation or materialization;
- local Save with zero Core/Execution Node/target calls, plus a separate
  target-free Verify of the saved revision;
- no plaintext secrets in desired files, views, review, diagnostics or tests;
- mockup reconciliation repeated at acceptance; and
- focused commits per completed slice, clean worktree and no UI-01I work.

## 10. Explicit non-goals and deferred decisions

UI-01H does not edit provider/VIP relations, endpoint-group ownership,
deployment identity/mode/placement, external/advanced opaque Ansible
variables, runtime secrets, certificate material, or execution plans. It does
not make a locally valid form proof that an infrastructure configuration is
valid.

UI-01H supports only the approved closed descriptor shapes. It does not design
service-specific rich panels, a recursive form framework, arbitrary
JSON-Schema pattern execution or a generic YAML/JSON editor. If a concrete
future requirement cannot be represented, it returns to the owner as a
separate contract/design decision. Any new manifest metadata, reference kind,
shape or SecretRef grammar requires a separately approved contract change.
