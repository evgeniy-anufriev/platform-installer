# Architecture review — UI-01H

## Verdict

**BLOCK — UI-01H / PLAN / FULL**

The plan preserves the main ownership boundaries, but three architecture
blockers remain in versioned catalog metadata, the SecretRef contract and
reference-bearing service settings.

## Review identity

- Plan: `docs/ui-01h-architecture.md`
- Plan SHA-256: `B013A4C3E84728975B46690DC7A983FD7DA9ECD4E6937366531DCDEE8287BFE4`
- Base/HEAD: `beb626bb245740002dcd6d2d04cdd7a9ddf70587`
- Mode/context: `PLAN / FULL`
- Scope: Services editor, deployment/member overrides, TLS-profile assignment,
  catalog projection, v1alpha8 commands and shared local Save lifecycle.
- Worktree at review: one untracked plan file; reviewer made no changes.

The verdict was formed independently from the review envelope.

## Findings

### UI01H-PLAN-001 — BLOCKING / OPEN

**Published manifest/catalog metadata versioning is not closed.**

Location: `docs/ui-01h-architecture.md`, section 5.1, especially the proposed
`referenceKind` metadata.

Evidence: the plan adds `referenceKind` to service-manifest/catalog metadata,
while the current `service-manifest/v1alpha1` closes `configurationSetting`
with `additionalProperties:false`. The current catalog reader, project locks
and generator use `platform.installer/catalog/v1alpha1`. The plan versions only
the edit contract and does not define a new manifest/catalog version or a
compatible extension field.

Impact: changing published v1alpha1 in place can break old consumers or make
catalog compatibility ambiguous.

Smallest correction: use the existing allowed extension seam
`configuration.settings.*.ui.x-referenceKind` with a closed enum and treat old
bundles without the metadata as `UNSUPPORTED`/read-only. The larger alternative
is an explicit service-manifest/catalog v1alpha2 plus compatibility and lock
migration policy; that is not justified by the current scope.

Required verification:

- an old v1alpha1 bundle still opens;
- the annotated catalog passes schema/generator reproducibility;
- unknown `x-referenceKind` fails closed; and
- project locks remain bound to exact bundle/catalog digests.

### UI01H-PLAN-002 — BLOCKING / OPEN

**The SecretRef editor has no explicit trusted metadata contract.**

Location: `docs/ui-01h-architecture.md`, sections 3, 5.1, 7 and 8.

Evidence: the plan introduces a `SECRET_REF` editor shape, but current
PostgreSQL manifest/schema fields describe `passwordSecretRef` only as ordinary
strings with `minLength:1`. No manifest metadata identifies a nested property
as SecretRef or supplies the exact `runtime:` grammar.

Impact: implementation would either infer secret semantics from a field name,
creating a hidden second contract, or expose a credential object as ordinary
text and weaken the secret boundary.

Smallest correction: mark these object settings `UNSUPPORTED` in UI-01H until
explicit metadata exists. If the scope must include them, define a
schema-authorized property-path metadata such as `ui.x-valueKind: SECRET_REF`
and the exact existing grammar
`^runtime:[A-Za-z0-9][A-Za-z0-9._-]{0,127}$`. Secret semantics must never be
inferred from a field-name suffix.

Required verification:

- runtime references are accepted;
- plaintext, paths, malformed and non-runtime values are rejected; and
- secret values never enter commands, Review, projections, diagnostics or
  tests; old manifests without metadata remain read-only.

### UI01H-PLAN-003 — BLOCKING / OPEN

**Other reference-bearing settings become editable without reference
semantics.**

Location: `docs/ui-01h-architecture.md`, sections 4.2, 5.1 and 6.

Evidence: representable `MANAGED` settings become editable, but the proposed
metadata covers only `TLS_PROFILE`. Existing settings also include
`dns-client.dnsServerRef` and
`keepalived.haproxyHealthTracking.serviceDeploymentRef`. Under the current
plan they appear as ordinary string/object fields and do not join the generic
final-state reference graph.

Impact: the UI could save a reference to an absent deployment or allow deletion
of a referenced deployment without `REFERENCE_IN_USE`. A later Core Verify may
return INVALID, but that contradicts the plan's Go-owned structural reference
integrity.

Smallest correction: either extend the closed metadata to required reference
kinds/property paths, including `SERVICE_DEPLOYMENT`, or make every
reference-bearing setting other than the approved TLS selector
`UNSUPPORTED`/read-only in UI-01H. No service-specific branches are allowed.

Required verification:

- a set to a missing target returns `REFERENCE_NOT_FOUND`;
- deleting a referenced target returns `REFERENCE_IN_USE`;
- final-state clear/remove releases the target; and
- deployment and member scopes behave consistently.

### UI01H-PLAN-004 — NON_BLOCKING / OPEN

**The command-limit UX is unspecified.**

One command per setting, member overrides and a shared cross-page session can
reach the existing limit of 16. Keep the limit unchanged. Define coalescing for
repeated edits of the same `(deployment, member, setting)` and a safe
`EDIT_SESSION_LIMIT` state that preserves the draft. A bounded reconcile
command needs a separate owner decision only if acceptance proves a normal
Kafka workflow cannot fit. No re-review is required for this clarification.

### UI01H-PLAN-005 — NON_BLOCKING / OPEN

**Catalog-unavailable read-only behavior is contradictory.**

The plan says saved configuration remains visible without a READY catalog, but
also copies values only when a current consumed descriptor exists. Choose one
safe behavior: expose bounded setting IDs/presence without payload, or show a
single status that saved settings exist but values are unavailable. Editing
remains disabled. Also state that moving an existing member preserves its
configuration with canonical member identity, while deletion removes the
target and invalidates the open form.

## Mandatory overengineering review

- Unnecessary public metadata mechanism: **1 BLOCKING**, already represented
  by UI01H-PLAN-001. The existing `ui.x-*` extension seam is the smaller
  compatible mechanism.
- Duplicate contracts/DTOs: **0**. The plan extends existing
  `ProjectCatalogView`, `ManagedProjectView` and `EditCommand`.
- Persistence/lifecycle layers: **0**. Existing EditSession, Review, guarded
  Save and reopen are reused.
- Generic CRUD: **0 BLOCKING**. Set/Remove remain closed operations rather than
  JSON Patch.
- Premature scope: **1 NON_BLOCKING**. Speculative rich service-specific panels
  should be omitted until a concrete supported shape requires one; unsupported
  shapes can remain read-only.
- Descriptor projection: justified because raw catalog/schema maps cannot be
  sent to React.
- `CLOSED_OBJECT`/`MAP_OF_CLOSED_OBJECT`: acceptable only for current concrete
  shapes with explicit bounds; a universal recursive schema/form engine is not
  justified.

Overengineering total: **1 BLOCKING / 1 NON_BLOCKING**. The blocking item is
not additional to the three blocker count.

## Evidence and limitations

Inspected directly and read-only:

- `.codex/agents/architecture-reviewer.toml`, `AGENTS.md`, `CURRENT_STATE.md`;
- exact plan content, SHA-256, HEAD and worktree scope;
- UI-01 roadmap/design/mockup Services flows and UI-01G hand-off;
- historical configuration commands and active project-edit v1alpha7;
- Go EditCommand/session limits and current catalog projection/parser;
- service-manifest/catalog schemas;
- Kafka, PostgreSQL, DNS client, Keepalived and HAProxy setting declarations;
- current structural writer/member-placement preservation; and
- existing runtime SecretRef grammar and secret guards.

`git diff --check` was reported by the parent and was not implementation QA.
No Go/frontend/Wails/Core tests, RED OS actions or mutating commands were run;
this is a documentation-only PLAN review.

## Review validity

**CURRENT** for plan SHA-256
`B013A4C3E84728975B46690DC7A983FD7DA9ECD4E6937366531DCDEE8287BFE4`.

The review becomes stale if manifest/catalog metadata versioning, v1alpha8
operation semantics, SecretRef ownership/grammar, editable reference-bearing
scope, or the canonical writer/Save/Verify lifecycle changes. Wording, bounds,
test-matrix and UX clarifications that preserve these boundaries do not require
a new FULL review.

## Unresolved blocking count and next action

Exact unresolved blocking count: **3**.

- `UI01H-PLAN-001`
- `UI01H-PLAN-002`
- `UI01H-PLAN-003`

UI-01H implementation must not start. After owner-approved corrections, at
most one `TARGETED_RECHECK` is allowed for these three IDs. No automatic full
review or correction loop is authorized.

---

## Targeted recheck

Verdict: **BLOCK — UI-01H / PLAN / TARGETED_RECHECK**

Corrected plan SHA-256:
`E77402E9E8A150495746B3636E464F4A11A1F2F051FCA2466AAD8CD49DC50951`.

Base/HEAD remained `beb626bb245740002dcd6d2d04cdd7a9ddf70587` and no
production code changed. The recheck covered only `UI01H-PLAN-001`, `002`,
`003` and their immediately adjacent boundaries.

### Finding lifecycle

- `UI01H-PLAN-001`: **OPEN → RESOLVED**. The plan now uses only the existing
  schema-authorized `ui.x-referenceKind` seam, closes the application enum to
  `TLS_PROFILE`, leaves published manifest/catalog v1alpha1 unchanged, fails
  unknown values closed and keeps old unannotated bundles compatible/read-only.
- `UI01H-PLAN-002`: **OPEN → OPEN / BLOCKING**. SecretRef editing is correctly
  prohibited, but without trusted metadata the descriptor cannot distinguish
  a credential object from an otherwise supported `CLOSED_OBJECT` or
  `MAP_OF_CLOSED_OBJECT` without forbidden name/shape/service inference. The
  smallest correction within the owner decision is to classify all object
  editor shapes as `UNSUPPORTED` in UI-01H.
- `UI01H-PLAN-003`: **OPEN → OPEN / BLOCKING**. Unannotated `dnsServerRef` is
  structurally indistinguishable from a permitted free string without a
  hidden name/service denylist. The smallest conservative correction is to
  permit generic strings only when an explicitly safe closed descriptor exists
  (for example an approved enum or supported closed-pattern subset); free
  unannotated strings with only length bounds remain `UNSUPPORTED`.

Verification for the remaining findings would require PostgreSQL credential
objects, `dnsServerRef` and `haproxyHealthTracking` to become read-only without
examining service IDs, setting/property names or labels. The TLS selector
remains the only reference-aware exception and requires
`ui.x-referenceKind: TLS_PROFILE`.

### Adjacent checks

- Published-schema mutation: **PASS**.
- New DTO/persistence/lifecycle layers: **PASS**.
- Rich panels/recursive schema engine removed: **PASS**.
- Review limit 16 and acknowledged-target lock without backend coalescing:
  **PASS**.
- Catalog-unavailable IDs/presence-only projection: **PASS**.
- New overengineering findings: **0**.

### Recheck validity and next action

The targeted verdict is **CURRENT** only for corrected plan SHA-256
`E77402E9E8A150495746B3636E464F4A11A1F2F051FCA2466AAD8CD49DC50951`.

Exact unresolved blocking count: **2** (`UI01H-PLAN-002`,
`UI01H-PLAN-003`). The one allowed targeted recheck has been consumed. Stop
for an explicit owner resolution; no additional automatic correction, FULL
review or targeted recheck is authorized. UI-01H implementation remains not
started.

## Owner resolution after the targeted recheck

The owner resolved the remaining editability ambiguity by approving a
conservative closed subset without a new metadata contract:

- editable: `BOOLEAN`, bounded `INTEGER`, bounded `NUMBER`, closed `ENUM`,
  `BOUNDED_STRING` only when all validation semantics belong to the supported
  closed subset, and `TLS_PROFILE` only through
  `ui.x-referenceKind: TLS_PROFILE`;
- read-only/`UNSUPPORTED`: every arbitrary object/map, credential/SecretRef
  structure, unannotated free-form string, `dnsServerRef`, nested
  `serviceDeploymentRef`, Kafka/listener-style complex setting and any setting
  with incompletely represented semantics;
- classification may not inspect service IDs, setting/property names, labels
  or object contents;
- unsupported raw values never reach React and remain writer-preserved when a
  supported sibling is edited.

This owner decision applies the smallest corrections identified by the
targeted reviewer for `UI01H-PLAN-002` and `UI01H-PLAN-003`; it does not waive
their safety requirements or introduce an unreviewed metadata mechanism. The
historical FULL and TARGETED_RECHECK verdicts above remain unchanged evidence.
The automatic review budget is exhausted, so no additional review was run or
claimed. UI-01H remains not started pending separate implementation authority.

---

## Owner-authorized targeted recheck after safe-boundary correction

Verdict: **APPROVE — UI-01H / PLAN / TARGETED_RECHECK**

The owner explicitly authorized this additional targeted review after the
normal automatic budget had been exhausted. It reviewed only
`UI01H-PLAN-002`, `UI01H-PLAN-003` and the immediately adjacent safe
editability boundary.

Review identity:

- plan SHA-256:
  `3670003F79CD5873B5DAC215749CA6C26DF3C06827AA1AA8A78AF31DF1E3D949`;
- base/HEAD: `beb626bb245740002dcd6d2d04cdd7a9ddf70587`;
- production code unchanged; UI-01H1 not started;
- worktree at review: the two untracked architecture documents only.

Finding lifecycle:

- `UI01H-PLAN-002`: **OPEN → RESOLVED**. `SECRET_REF` is not an editor shape;
  every object/map, including credential objects, is `UNSUPPORTED`; no
  plaintext input or secret metadata/inference exists; raw unsupported values
  do not reach React and remain writer-preserved.
- `UI01H-PLAN-003`: **OPEN → RESOLVED**. Unannotated free-form strings are
  `UNSUPPORTED`; `dnsServerRef` and object-contained `serviceDeploymentRef`
  cannot become generic editors; `TLS_PROFILE` is the only reference-aware
  shape and requires trusted `ui.x-referenceKind: TLS_PROFILE`, with generic
  final-state integrity for deployment and member scopes.

Adjacent checks passed: the editable matrix is closed; patterns use only the
supported validator subset; no generic schema engine, backend command
coalescing, speculative metadata or rich service-specific panels exist; Review
remains limited to 16 commands; unavailable-catalog projection exposes only
safe IDs/presence; unsupported sibling values must survive a supported edit.

Mandatory overengineering result: **0 blocking / 0 nonblocking**. No new DTO,
persistence/lifecycle layer, speculative extension or missed simpler mechanism
was found.

Evidence was read-only. The reviewer directly checked the corrected plan/hash,
repository instructions/state, prior review evidence, relevant manifest and
catalog schemas, representative PostgreSQL/DNS/Keepalived/Kafka settings, the
existing TLS reference guard, UI design/mockup, HEAD and worktree.
`git diff --check`, SHA-256 and HEAD verification passed. No implementation,
Go/frontend/Wails/Core or RED OS tests were run because this was a PLAN review.

Review validity: **CURRENT** only for plan SHA-256
`3670003F79CD5873B5DAC215749CA6C26DF3C06827AA1AA8A78AF31DF1E3D949`.
Changing editable shapes, trusted metadata, secret/raw-value boundaries,
writer preservation, reference integrity, v1alpha8 semantics or Save/Verify
ownership makes it stale.

Exact unresolved blocking count: **0**. The architecture may be presented to
the owner for approval. This review does not start UI-01H1 and does not replace
separate implementation authorization.
