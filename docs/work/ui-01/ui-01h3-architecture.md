# UI-01H3 — Member configuration and TLS-profile selection

Document scope: the original milestone contract/design. Historical status, review
and QA checkpoints are collected separately; current status and authorization
are recorded only in [CURRENT_STATE](../../../CURRENT_STATE.md).

Recorded status and review scope: [historical checkpoint](evidence/documentation-checkpoints-20261012.md#ui-01h3-architecture-checkpoint-002).

## Goal and scope

H3 completes the next closed part of the Services editor:

- safe member-scoped configuration for existing typed topology members;
- selection of a managed TLS profile only for the exact catalog descriptor
  whose trusted `ui.x-referenceKind` projects as `TLS_PROFILE`;
- a contextual navigation hand-off from Services to Certificates and back to
  the same selected Services detail.

It reuses immutable `project-edit/v1alpha8`, the existing single Go
`EditCommand`, shared App EditSession/Review/Save/Discard and guarded local
writer. No Go, Core, Ansible, schema, catalog, writer, Execution Node, PKI
semantics, service runtime or target behavior changes. New sessions remain
v1alpha8; older contracts remain immutable compatibility inputs.

## Mockup and ownership reconciliation

The reviewed mockup shows a distinct Services detail, deployment/member TLS
selection and a Certificates entry. H3 preserves the global navigation order:
Project → Servers → Topology → Certificates → Services → Installation.
Topology still opens the exact same Services detail. The mockup's listener
rows and example effective values are not H3 data: listeners, effective
configuration, source/origin and SAN remain Core/service derived and are not
calculated or displayed as authoritative local facts.

The portable project remains the desired-state authority. `ManagedProjectView`
is only the bounded direct-owned local reopen projection. `ProjectSnapshot`
and `VerifiedPKIView` remain read-only Core evidence and are not inputs to
Save. React never parses Ansible documents or catalog/schema maps.

## Existing contracts reused

H1 already provides the exact required command grammar:

```
SetServiceConfigurationValue(
  deploymentId, scope=MEMBER, memberId, setting, primitive value)
RemoveServiceConfigurationOverride(
  deploymentId, scope=MEMBER, memberId, setting)
```

The backend validates the exact READY catalog descriptor, mode, scope,
primitive value and target member. The local candidate finds the canonical
member document through the existing bounded managed-document set. The same
generic final-state reference graph validates a trusted TLS profile reference
against managed TLS profiles. H3 neither adds a command nor alters those
guards.

The App adapter extends its existing H1 `ManagedMemberPlacement` TypeScript
projection to include its already-published bounded
`ManagedConfigurationOverride[]`; it does not create a parallel member DTO.
For presentation, it also joins current acknowledged typed placement intents
to the saved member placements. This is a deterministic in-memory final draft
view only; it does not inspect `host_vars`, infer Ansible precedence or write
anything locally.

## Member identity and final draft state

A member target is always the canonical composite identity:

```
(deploymentId, memberId)
```

`memberId` is not assumed globally unique. H3 derives the member list from
the union of saved `ManagedProjectView.memberPlacements` and acknowledged
`ReconcileDeploymentPlacement` intents for the selected deployment. A
reconcile replaces that deployment's member list; a Delete deployment clears
its rows. Host-scoped deployments have no member editor. A member must exist
in that final typed draft before H3 offers an editor.

This admits a member configuration command only through the pre-existing
backend reducer, which remains the authority for whether the final candidate
has the corresponding canonical member target. If acknowledgement fails, no
local overlay is created. A selected member that disappears through a later
acknowledged reconcile/delete is cleared locally; no stale member target is
reused.

Configuration overlays and acknowledgement locks use the full target:

```
(deploymentId, scope, memberId-or-empty, setting)
```

Thus a deployment override never locks a member override, and one member never
locks another. A successful Set or Remove locks only its exact target until the
existing shared Save or Discard. The Review limit remains 16; H3 adds no
coalescing, undo or command rewrite.

## Safe descriptor and form boundary

H3 preserves H2's closed editability boundary. A control is enabled only when
all conditions hold:

1. the project catalog is exact `READY`;
2. the descriptor is `MANAGED`;
3. the descriptor explicitly admits the selected scope;
4. its shape is one of `BOOLEAN`, `INTEGER`, `NUMBER`, `ENUM`,
   `BOUNDED_STRING`, or trusted `TLS_PROFILE`.

`TLS_PROFILE` is admitted only when the projected descriptor has both
`editorShape=TLS_PROFILE` and `referenceKind=TLS_PROFILE`. H3 never infers
TLS/secret/reference behavior from setting ID, service ID, labels or values.
All advanced, protected, unsupported, unknown, arbitrary object/map,
credential/secret-shaped and untrusted reference settings remain read-only and
writer-preserved. H3 never exposes arbitrary raw values, plaintext credentials
or secret references.

The member panel is an explicit local selection in the existing Services
detail. It shows stable member ID, host ID and copied roles. It does not offer
member creation, deletion, movement or role editing; those remain Topology.
Deployment-scoped controls retain H2 behavior.

## TLS selector and Certificates return flow

The selector's options are only stable IDs from the direct managed
`pki.tlsProfiles` projection, joined with acknowledged current-session
Create/Update/Delete TLS-profile intents. H3 does not expose raw TLS profile
entities, secrets, certificate profile data, derived certificate identity,
SAN, VIP impact or effective service configuration.

The selector may set a non-empty TLS profile ID through the normal H1 Set
command; **Reset to inherited** issues the normal H1 Remove command. It does
not create a TLS profile or edit PKI desired state itself. The existing generic
final-state reference integrity remains authoritative for missing/deleted
profiles and `REFERENCE_IN_USE`.

**Manage certificates** switches to the existing Certificates page with an
application-local return context of `(selected deployment, selected member if
any)`. It neither starts a session nor writes state. Returning via the explicit
Services action restores the same Services detail and focus, provided the
deployment/member still exists in the final typed draft; otherwise it safely
falls back to Services list. Certificates continues to own PKI CRUD and its
own active panel; H3 does not create a second PKI editor or make the selector
depend on Core verification.

When the catalog is not exact READY, or no managed TLS profile exists, H3
shows the controlled prerequisite/read-only state and disables mutation. It
does not fabricate a profile, call an Execution Node or contact targets.

## UX and accessibility

- Detail retains an explicit back-to-services action; a contextual return from
  Certificates restores the Services detail as above.
- Member selector has an accessible label and clearly identifies host/roles.
- Detail/member changes move focus to their headings; returning from
  Certificates focuses the restored detail heading, while an invalid return
  focuses the Services list heading.
- Safe backend errors remain a single `role=alert`; disabled controls explain
  whether catalog, descriptor scope, unsupported shape, final-state absence,
  exact lock or shared command capacity is the prerequisite.

## Acceptance and non-goals

Focused frontend/component acceptance must prove:

- member composite identity and saved-plus-draft placement display;
- Set and Remove member commands carry exact v1alpha8 scope/member fields;
- deployment/member and member/member acknowledgement locks are independent;
- disappearing selected members clear safely;
- trusted TLS-profile selection and Reset use only the typed profile-ID list;
- deleted/missing profile reaches the existing safe backend finding, with no
  local bypass;
- Certificates round-trip preserves selected context and shared draft without
  creating a session merely by navigating;
- no-READY catalog, host-scoped deployment, unsupported/secret-shaped values
  and absent profiles are read-only; raw values never render;
- no Core, Execution Node or target call occurs.

Run affected Go tests plus frontend lint/test/build, Wails build, catalog/schema
reproducibility, relevant RED OS race/target-free checks, secret audit and
`git diff --check` after implementation.

H3 explicitly excludes listener panels, effective/origin display, complex
settings, service-specific UI, member topology CRUD, certificate issuance,
SAN/VIP computation, generic schema evaluation, secret input and H4 work.

## Implementation evidence

See [historical checkpoint](evidence/documentation-checkpoints-20261012.md#ui-01h3-architecture-checkpoint-001). Current status: [CURRENT_STATE](../../../CURRENT_STATE.md).
