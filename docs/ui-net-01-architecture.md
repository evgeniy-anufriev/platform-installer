# UI-NET-01 — Endpoint provider and virtual address editor architecture

Status: **UI-NET-01A DONE; UI-NET-01B NEXT**.

Owner decision: UI-NET-01 precedes UI-01G because Core may include provider
virtual addresses in certificate SAN when `sanPolicy.includeEndpointVip=true`.
UI-01G remains the Certificates/PKI editor.

Prerequisites: UI-01F1 through UI-01F6 are DONE. Baseline revision:
`6d4f079930dec68a8f5621986d155130c441549b`.

## 1. Goal

UI-NET-01 makes the existing provider side of the canonical endpoint model
editable in the *Topology → Entry points** view:

```text
consumer deployment.endpointGroup
                    │
                    ▼
              endpointGroups[id]
                    ▲
                    │
provider deployment.endpointGroupRef
                  + virtualRouterId
                  + virtualAddresses[]
```

The milestone adds no networking database, provider-specific UI, local DNS/PKI
resolver or second save path. It extends the existing typed `EditSession`,
structural Review, guarded local Save and optional Project Verify lifecycle.

## 2. Scope

### 2.1 Included

- edit provider `endpointGroupRef`, `virtualRouterId` and
  `virtualAddresses[{address,interface}]` as one coherent desired-state unit;
- clear all three provider fields as one explicit structural cleanup intent;
- catalog-driven provider eligibility through the existing
  `ProjectCatalogService.EndpointProvider` flag;
- direct-owned local Save/reopen projection for provider fields;
- final-state generic references and endpoint-group delete protection;
- reuse the existing typed/bounded Core endpoint/provider preview;
- honest preview freshness after Save and Verify;
- neutral local provider-change presentation; any actual PKI impact remains
  derived Core evidence and is not inferred by Go or React;
- Windows/RED OS acceptance and regression evidence.

### 2.2 Excluded

- endpoint-group CRUD and consumer assignment already completed in UI-01F5;
- creating/deleting deployments or placement editing already completed in F;
- certificate authority/profile/TLS-profile editing — UI-01G;
- service configuration, HAProxy health tracking, BIND settings or other
  package settings — UI-01H or a separately approved integration milestone;
- service-specific `if keepalived`, BIND, HAProxy or Kafka branches;
- automatic VIP/interface discovery, allocation, conflict probing or target
  facts;
- DNS reconciliation, certificate issue/reissue/materialization, service apply,
  target contact or execution;
- IPv6 provider support, because the published desired-state provider address
  contract currently accepts IPv4 only;
- provider deployment rename, mode change, clone or implicit creation.

## 3. Existing authoritative contract

The portable `project/v2alpha1` deployment model already owns:

- consumer `endpointGroup`;
- provider `endpointGroupRef`;
- provider `virtualRouterId` in range 1..255;
- one or more IPv4 `virtualAddresses`, each with an interface name.

The service manifest declares provider capability through the closed empty
object `endpointProvider: {}`. `ProjectCatalogView` already projects that as a
boolean. React and Go do not infer provider capability from service ID or
capability strings.

Core already owns the semantic checks and derived effects:

- all provider fields are required together for an endpoint-provider
  deployment;
- referenced endpoint group must exist;
- non-provider services may not use provider fields;
- virtual addresses may not be duplicated across provider deployments;
- endpoint/provider projection, DNS provider addresses and PKI SAN inclusion
  are derived from canonical state;
- Keepalived/HAProxy/BIND package behavior remains outside the editor.

UI-NET-01 does not change those Core semantics.

## 4. Command contract evolution

Introduce additive `platform.installer/edit-command/v1alpha6`.
V1alpha1 through v1alpha5 remain immutable compatibility contracts. New
Installer sessions emit v1alpha6 only.

V1alpha6 contains the complete v1alpha5 operation set unchanged and adds two
closed intents:

```text
ReconcileEndpointProvider(
  deploymentId,
  endpointGroupId,
  virtualRouterId,
  virtualAddresses[{address, interface}]
)

ClearEndpointProvider(deploymentId)
```

`ReconcileEndpointProvider` is full replacement of the three provider fields
for one deployment. It is not a generic deployment patch. Omitted and empty
addresses are invalid for reconcile. `ClearEndpointProvider` removes all three
fields together; it exists so unavailable catalog evidence never traps an
existing reference and prevents safe cleanup.

The public schema deliberately preserves the existing v1alpha5 Installer ID
shape for every inherited and new command field:
`^[a-z0-9][a-z0-9-]{0,62}$`. UI-NET-01 does not adopt the broader
`project/v2alpha1` identifier grammar and does not expand the managed
read/reduce/write boundary to 128-character, dotted or underscored IDs. Such an
expansion would require a separate owner-approved migration of all command,
managed projection and reference seams.

The schema reuses the canonical VRID and IPv4 value shapes. Its command/UI
interface value is additionally bounded to 128 characters so every value that
can be saved through this editor remains representable by the existing bounded
Core preview projection. It closes unknown fields, rejects duplicate identical
address/interface pairs, and applies a maximum of 64 address rows, matching the
existing bounded endpoint preview envelope. Existing projects with an
interface longer than 128 characters or more than 64 address rows are
projected as `UNSUPPORTED`, remain read-only and are never truncated,
normalized or lost on Save.

Go normalizes all versions into the existing `EditCommand` model. Add one
small typed `VirtualAddress` value used by command and managed view; do not add
a parallel session/plan/result DTO. The common Review limit remains 16.

## 5. Catalog dependency by operation

`ReconcileEndpointProvider` requires the exact pinned READY catalog because it
must prove the selected deployment's service declares `endpointProvider`.

`ClearEndpointProvider` is catalog-independent structural cleanup. It remains
subject to project revision, ownership, path, transaction and final-reference
guards. This matches the existing F2 rule that unavailable catalog must not
trap safe clear/delete operations.

Neither operation calls Core or contacts targets during local Save. Optional
Verify subsequently supplies authoritative infrastructure findings.

Clearing the tuple from an endpoint-provider deployment is intentionally a
structural cleanup, not a valid provider-disable operation. Local Save and
reopen succeed, but the saved project remains or becomes `INVALID` when
verified because Core requires the complete provider tuple. Recovery is to
reconcile a complete tuple or delete the deployment; the UI must not describe
Clear as making that deployment READY.

## 6. Managed local projection

Extend the existing `ManagedDeployment` with directly owned fields:

```text
endpointGroupRef?: string
virtualRouterId?: integer
virtualAddresses?: [{address, interface}]
providerEditState: NONE | EDITABLE | INCOMPLETE | UNSUPPORTED
```

The projection reuses F1's handle-bound/no-follow read, duplicate-key
rejection, per-file/aggregate bounds and coherent project revision. It does
not parse service semantics or Ansible precedence.

The three provider fields are projected without equating structural
incompleteness with a malformed project:

- all absent: no provider configuration;
- all present, structurally valid and inside editor bounds: editable provider
  configuration;
- a safe partial tuple: `INCOMPLETE`; every present typed value remains visible
  and the project opens so the operator can complete the form with one full
  reconcile or clear the tuple;
- a complete or partial legacy tuple outside the editor's 64-row/128-character
  command bounds, but still inside the existing F1 managed-document safety
  envelope: `UNSUPPORTED`; all directly owned typed values and canonical array
  order are projected read-only without truncation or loss;
- malformed field types, duplicate keys, unsafe paths or values exceeding the
  existing managed-document safety envelope still fail safely as
  `MANAGED_DOCUMENT_INVALID`.

Stable deployment ordering is by deployment ID. `virtualAddresses` retain
canonical array order in the managed projection and writer. The UI must not
sort and then round-trip legacy values or rewrite unchanged bytes merely to
reorder rows.

## 7. Reducer, references and preservation

The structural reducer writes only the fixed Installer-owned desired-state
document through the existing candidate/transaction writer.

For reconcile it validates structural command shape, applies the complete
provider tuple, and preserves unrelated deployment fields and `x-*`
extensions. For clear it removes exactly `endpointGroupRef`,
`virtualRouterId` and `virtualAddresses`.

The generic reference graph retains:

```text
provider deployment.endpointGroupRef -> endpointGroups[id]
```

Endpoint-group deletion remains blocked by `REFERENCE_IN_USE` until consumer
and provider references are cleared or moved in the same final-state Review.
There is no cascade deletion.

Go may reject missing final-state deployment/group identities and a reconcile
intent whose pinned catalog service is not an endpoint provider. It must not
enforce cross-provider VIP uniqueness, host/interface existence, routing,
placement suitability, VRRP topology or PKI SAN rules; those remain Core-owned.

Each effective reconcile/clear reports `ENDPOINT_CHANGED` and the neutral local
change classification `PROVIDER_CONFIGURATION_CHANGED`. Local Review/Save does
not claim that PKI changed. A semantic Save makes prior Verify and endpoint
preview stale; only subsequent Core evidence may establish an actual PKI/SAN
impact. Failed Review/Save leaves canonical bytes unchanged.

## 8. UX in Topology → Entry points

UI-NET-01 extends the existing Entry points tab rather than adding a new global
page.

The minimal layout remains:

1. endpoint-group list and consumer assignments from F5;
2. provider deployments declared eligible by catalog;
3. selected provider editor and fresh Core preview/findings.

Provider editor fields:

- provider deployment (existing deployment, immutable ID);
- endpoint group;
- VRID;
- repeatable IPv4 address + interface rows.

`INCOMPLETE` pre-fills every present field and allows only a complete reconcile
or explicit clear. `UNSUPPORTED` shows the exact safe typed legacy values
read-only and explains the 64-row/128-character editor bounds. It offers Clear
or an explicit **Replace with supported configuration** action that starts a
separate empty bounded form; it never copies, truncates or normalizes the
legacy tuple into an editable command. Apply becomes available only for a new
complete tuple within the bounds.

Actions are **Apply to draft** and **Clear provider settings**. They append one
typed intent to the shared structural draft. The existing global Review/Save
flow remains authoritative; the tab gets no independent Save button,
transaction, undo stack or hidden auto-save.

Clear shows an explicit warning that an endpoint-provider deployment without
the tuple is saved locally but cannot verify successfully. After Save, Verify
shows the authoritative provider-required finding; the offered recovery is a
complete reconcile or deployment deletion.

The UI may validate required fields, IPv4/interface grammar, VRID range and
duplicate rows for immediate feedback. Backend schema/reducer remains
authoritative. React never decides provider capability, cross-deployment VIP
uniqueness or placement validity.

When catalog is unavailable, existing direct-owned provider values remain
visible read-only and Clear remains available. Reconcile/create is disabled
because provider capability cannot be proven.

## 9. Core preview, provider change and PKI authority

The existing `EndpointPreviewProvider` projection already provides bounded,
typed provider deployment, group, VRID and virtual addresses from fresh Core
evidence. UI-NET-01 reuses it; no second preview DTO or snapshot parser is
introduced.

The page distinguishes:

- local saved/draft provider intent;
- fresh verified Core provider preview;
- neutral local `PROVIDER_CONFIGURATION_CHANGED` state;
- actual PKI/SAN impact only when supplied by matching fresh Core evidence.

Before fresh Verify, the UI says only that provider configuration changed and
verification is stale. React and Go do not inspect certificate profiles or
infer whether certificates, identities or SAN changed. Exact PKI impact and
SAN remain Core-derived evidence presented by UI-01G.

Preview states remain `CURRENT`, `INVALID`, `STALE`, `NOT_VERIFIED` and
`UNAVAILABLE`. INVALID exposes safe findings but no authoritative provider
preview. Save stales the previous preview. Verify never mutates project files
or authorizes execution.

`CERTIFICATE_REISSUE_REQUIRED` is not bypassed, downgraded or auto-confirmed.
UI-NET-01 performs no materialization/reissue and does not claim certificate
material remains usable after a VIP change.

## 10. Error and recovery behavior

- presentation validation never replaces backend validation;
- draft survives validation, Verify or availability failure;
- `REFERENCE_IN_USE` shows safe canonical reference context;
- `EDIT_COMMAND_CONFLICT` keeps existing Save-or-discard recovery;
- `COMMITTED_REFRESH_FAILED` means bytes are committed, consumes acknowledged
  draft and recovers only through existing read-only reopen;
- safe partial provider tuples reopen as `INCOMPLETE` and remain repairable;
- safe legacy tuples outside editor bounds reopen as `UNSUPPORTED` read-only
  without truncation or loss;
- malformed/oversized command or local document returns a bounded finding;
- no diagnostic includes runtime credentials, raw project payloads or secret
  values.

## 11. Milestone slices

### UI-NET-01A — contract and managed provider model — DONE

- additive v1alpha6 schema/decoder;
- typed provider command value;
- direct-owned managed projection and reopen coverage.
- Until UI-NET-01B installs the reducer, direct provider commands fail with
  `EDIT_OPERATION_UNAVAILABLE`; a published decoder must never permit a silent
  no-op Save.

### UI-NET-01B — reducer and guarded local Save — NEXT

- reconcile/clear final-state reducer;
- catalog-dependent reconcile and catalog-independent clear;
- generic reference guard, preservation and transaction tests.

### UI-NET-01C — Entry points provider editor

- catalog-driven eligible provider list;
- provider modal/panel and shared draft integration;
- unavailable catalog/read-only and clear behavior.

### UI-NET-01D — preview and PKI-impact UX

- reuse `EndpointPreviewProvider` freshness states;
- draft-vs-verified presentation;
- neutral provider-change state with PKI impact reserved for Core evidence.

### UI-NET-01E — acceptance and regression

- built Windows desktop flow;
- RED OS target-free Core and affected race tests;
- contract/catalog/schema reproducibility, security and transaction gates;
- docs/state/roadmap update and one focused implementation commit only after
  all acceptance passes.

Each slice requires a separate owner start request and mockup comparison.
UI-01G does not start as part of UI-NET-01.

## 12. Acceptance matrix

Positive behavior:

- configure one eligible provider with one and multiple VIPs;
- move provider to another existing endpoint group;
- change VRID/address/interface as one complete intent;
- clear provider configuration with and without READY catalog;
- clear provider reference and delete endpoint group in one final-state Review;
- local Save and reopen with zero Execution Node/Core/target calls;
- Verify saved revision and render the existing bounded provider preview;
- subsequent Save marks preview stale and reports only the neutral provider
  configuration change;
- preserve unrelated deployment fields and extensions.
- clear-only Save/reopen succeeds locally, then target-free Verify returns the
  safe provider-required finding until reconcile or deployment deletion;
- partial tuple opens as `INCOMPLETE`, preserves present values and can be
  repaired by complete reconcile or explicit clear;
- legacy tuples outside editor bounds open as `UNSUPPORTED` read-only and
  survive unrelated Save without truncation or loss;

Negative/safety behavior:

- non-provider service, missing deployment/group, malformed ID;
- Installer ID boundary parity: 63 characters accepted, 64 and 128 characters
  rejected, and `.`/`_` rejected for v1alpha6 exactly as in v1alpha5;
- reconcile command with a partial tuple, empty addresses,
  invalid/duplicate IPv4/interface row, VRID outside 1..255, interface length
  129, oversized list or unknown command field is rejected; interface lengths
  128/129 have explicit accept/reject boundary tests;
- duplicate VIP across providers is saved structurally but Verify returns the
  authoritative Core finding and no current preview;
- endpoint-group delete while consumer/provider references remain;
- stale revision, command conflict, malformed managed document,
  symlink/reparse/path replacement and interrupted transaction;
- unavailable/mismatched catalog blocks reconcile but not clear;
- no service-specific branch, target probe, DNS/PKI apply or secret handling.

Required gates include focused schema/decoder/reducer/managed-view/frontend
tests, `go test ./...`, `go vet ./...`, frontend lint/test/build,
`wails build -nopackage -clean`, affected RED OS race and target-free Core
tests, catalog/schema reproducibility, secret/security audit and
`git diff --check`.

## 13. Overengineering check

The smallest implementation is one additive command revision, one typed
provider value in the existing command/view model, two reducer operations and
an extension of the existing Entry points UI. It reuses the existing catalog
boolean, transaction, reference graph and preview projection.

Explicitly rejected:

- network/VIP allocation database, IPAM integration or discovery daemon;
- generic deployment patch, raw map, YAML path or service-specific commands;
- separate provider session, Save flow, transaction or preview protocol;
- local endpoint/DNS/PKI resolver in Go or React;
- automatic Keepalived/BIND/HAProxy creation or placement;
- certificate editor, service settings or execution work in this milestone;
- speculative IPv6/provider schema expansion before the portable contract.

## 14. DONE criteria

UI-NET-01 is DONE only when:

1. v1alpha6 is closed, additive and backward compatible;
2. provider state saves/reopens through the one guarded local lifecycle;
3. reconcile admission is catalog-driven and clear cannot be trapped by an
   unavailable catalog;
4. endpoint-group references are final-state, generic and non-cascading;
5. Core remains sole authority for provider validity, derived endpoints, DNS
   and PKI SAN effects;
6. Windows and RED OS acceptance/regression gates pass;
7. architecture/safety review has zero blocking findings;
8. docs/state/roadmap are updated, one focused commit exists and worktree is
   clean.

UI-01G is NEXT only after UI-NET-01 is complete.

Because UI-NET-01 publishes a new versioned edit-command contract and changes
canonical writer behavior, implementation completion also requires one bounded
FULL DIFF architecture review with zero blocking findings. Review does not form
an automatic correction loop.
