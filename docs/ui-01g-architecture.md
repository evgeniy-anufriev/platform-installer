# UI-01G — Certificates: managed PKI intent editor architecture

Status: **UI-01G1 through UI-01G3 DONE; UI-01G4 NEXT**. This document remains the governing
architecture for the remaining slices. UI-01G1 added only the additive command
contract, bounded local desired-state projection, final-state references and
guarded local Save; it did not authorize certificate issuance, reissue,
materialization, service apply, or a change to standalone Ansible/Core PKI
behavior. Evidence: [ui-01g1.md](ui-01g1.md).

Prerequisites: UI-01F and UI-NET-01 are DONE. UI-NET-01 precedes this
milestone because a provider VIP can contribute to a certificate SAN only when
Core resolves `sanPolicy.includeEndpointVip=true`.

## 1. Goal and scope

UI-01G makes the existing Installer-owned PKI desired-state subtrees editable
on the global **Certificates** page, between **Topology** and **Services**:

```text
certificateAuthorities
  -> certificateProfiles
       -> tlsProfiles
       -> certificateScopes
```

It uses the one existing EditSession -> structural Review -> guarded local Save
-> reopen lifecycle. A new additive `project-edit/v1alpha7` is the active
edit-command version for new sessions. It carries the complete unchanged
v1alpha6 operation set plus the four existing PKI operation families, with the
exact entity shapes referenced from
`project/v2alpha1/desired-state.schema.json`:

| Entity | Create / update | Delete |
| --- | --- | --- |
| certificate authority | `CreateCertificateAuthority`, `UpdateCertificateAuthority` | `DeleteCertificateAuthority` |
| certificate profile | `CreateCertificateProfile`, `UpdateCertificateProfile` | `DeleteCertificateProfile` |
| TLS profile | `CreateTLSProfile`, `UpdateTLSProfile` | `DeleteTLSProfile` |
| certificate scope | `CreateCertificateScope`, `UpdateCertificateScope` | `DeleteCertificateScope` |

`v1alpha1` through `v1alpha6` remain immutable compatibility inputs. The
historical PKI operations in v1alpha2/v1alpha3 remain compatibility-only and
are not promoted into the current structural Save authority. New Installer
sessions emit only v1alpha7 after this milestone; no published version is
retroactively widened or otherwise changed.

Out of scope:

- private keys, certificate PEM/PKCS12/JKS bytes, passwords, password files,
  secret submission or secret discovery;
- imported/external CAs, renewal, rotation, global JVM trust, mTLS and JKS;
- PKI materialize, reissue, verify playbook dispatch, target contact, or an
  Execution Node workflow;
- direct editing of service `configuration.tlsProfile` (UI-01H owns that
  catalog-declared setting);
- local resolution of effective Ansible variables, certificate identity,
  Common Name, SAN, consumer set, PKI impact or
  `CERTIFICATE_REISSUE_REQUIRED`.

The `runtime:<name>` `storePasswordSecretRef` is a stable reference only. The
form may validate and persist that reference exactly as allowed by the desired
state schema; it never accepts, persists, resolves, displays, or tests the
password value. Runtime secret provisioning remains outside UI-01G.

## 2. Existing authority and mockup reconciliation

The canonical desired-state schema owns the accepted fields and constraints:

- a CA is currently `MANAGED` with a common name and optional display name /
  validity override;
- a certificate profile references a CA and has a required `sanPolicy`, plus
  optional policy overrides, usages and subject DN fields;
- a TLS profile references a certificate profile, has optional `HOST`,
  `MEMBER` or `DEPLOYMENT` scope, and a runtime-only-secret reference;
- a certificate scope references a certificate profile and may carry a display
  name, optional `HOST`/`MEMBER`/`DEPLOYMENT` scope, and explicit deployment,
  host, deployment-scoped member, DNS-name and IP-address sources.

Role defaults remain the authority for omitted PKI policy. The UI shows an
omitted field as **Inherited** and does not write an apparent default merely
because it is displayed. It offers only the schema's `MANAGED` CA mode.

`docs/ui-design-01.md` describes a materialized-state section and mentions
Materialize/Verify in its aspirational normal flow. The parent UI-01G plan and
PKI boundary are narrower: this milestone renders only safe, read-only Core
evidence and Project Verify state. It exposes no Materialize/Reissue action.
That is an intentional mockup/contract discrepancy recorded here; a future
execution milestone must own any runtime action.

## 3. Contract, decode and bounded local projection

### 3.1 v1alpha7 command contract

`contracts/project-edit/v1alpha7/schema.json` is additive and composes the
unchanged v1alpha3 session/plan/commit envelopes. Its operation-specific
definitions reference the existing desired-state entity definitions, retain
the existing Installer identifier grammar, use `unevaluatedProperties:false`,
and preserve only schema-authorized `x-*` extension fields inside entities.

The existing Go `EditCommand` remains the sole internal command model. Its
existing `entityId` and `entity` transport fields are reused; no parallel
public PKI command DTO is introduced. The v1alpha7 decoder accepts only the
four operation families above and their appropriate fields. Before a candidate
is changed it applies a narrow, operation-specific bounded entity validator
equivalent to the referenced schema:

- object shape, required fields, grammar, enum, numeric, list and nested
  collection bounds are checked;
- known fields are closed; only `x-*` extension members permitted by the
  existing desired-state schema survive untouched;
- `entityId` is the map key and cannot disagree with a nested identity;
- `certificateScopes.sources.members` always uses the existing composite
  `(deploymentId, memberId)` identity, never a globally assumed member ID.

This is deliberately not a generic YAML/JSON validation framework: it is one
closed adapter for the four schema-defined desired-state entities. The writer
continues to preserve unrelated nodes in its managed document according to the
existing semantic round-trip policy.

### 3.2 Read model and freshness

`ReadManagedProjectView` is extended only with a bounded `PKI` section derived
from the direct Installer-owned `platform_desired_state` document. It contains
stable IDs and direct desired fields needed to reopen and edit the four entity
families. It contains no raw YAML, generated PKI state, secret values, runtime
paths, material, or derived SAN/identity calculation.

The projection follows the F1 managed-document safety/bounds policy and is
all-or-nothing: malformed PKI roots or any consumed entity produce the existing
safe managed-document error and no partial PKI view. Absence of the four roots
means four empty collections; it does not create them until a successful
candidate Save needs a changed subtree. The reader preserves unsupported
schema-authorized `x-*` fields during a typed update but React does not expose
them as editable controls.

A fresh `ProjectSnapshot.pki` is separate evidence. Go owns one private,
in-memory, read-only and deterministic-copy `VerifiedPKIView` projection at
the Core-to-Wails boundary. It is not portable desired state, persisted state,
an input to Save, a replacement Core contract or a generic snapshot DTO. React
receives only this narrow view, never a raw `pki` map.

`VerifiedPKIView` has the closed presentation status vocabulary `CURRENT`,
`INVALID`, `STALE`, `NOT_VERIFIED` and `UNAVAILABLE`. Its decoder accepts only
the existing `pki.status` and `certificateIdentities` fields, validates exact
known primitive types and identifier grammar, applies the existing managed
entity/placement limits to identity and consumer/source collections, applies
the existing 4 MiB per-document / 64 MiB aggregate safety budgets to copied
presentation data, and enforces bounded safe DNS/IP value lengths. Unknown raw
PKI members are discarded, never forwarded.

The application binds `VerifiedPKIView` to the exact saved canonical project
revision and the exact Execution Node plus immutable runtime evidence returned
by the existing `BuildProjectVerificationSnapshot` protocol. A late or
mismatched revision/node/runtime result, malformed or incomplete evidence, or
Core-invalid evidence exposes only an appropriate safe status/findings and
clears identity/SAN preview rather than mixing it with the current managed
view. Identity/SAN preview is present only for `CURRENT` evidence with the
complete exact binding. The projection never calculates CN/SAN, provider VIP
effects, consumers or PKI validity and never downgrades Core findings.

## 4. Candidate reducer, reference integrity and local Save

The v1alpha7 reducer operates on the one desired-state candidate document and
uses the established revision/digest guards, owner/path checks, atomic
transaction, rollback/recovery and post-commit local reopen. It does not call
Core or contact an Execution Node for Save.

Create fails on a duplicate ID. Update fails on an absent ID; it is a complete,
closed entity replacement rather than a generic patch. Delete fails with the
existing generic `REFERENCE_IN_USE` guard when a final-state reference exists.
The generic PKI graph is evaluated over the candidate final state and includes:

```text
certificateProfile.authorityRef              -> certificateAuthority
tlsProfile.certificateProfileRef             -> certificateProfile
certificateScope.profile                     -> certificateProfile
certificateScope.sources.hosts               -> host
certificateScope.sources.serviceDeployments  -> deployment
certificateScope.sources.members             -> (deployment, member)
deployment configuration.tlsProfile          -> tlsProfile
```

The final edge is a declared generic desired-state reference, not a
service-specific Go branch. Existing server/deployment/member deletion guards
must continue to traverse certificate scopes. Deletes therefore never leave a
dangling authority, profile, TLS profile, scope source or service TLS-profile
reference in an Installer-managed candidate.

Structural Review preserves the existing maximum of 16 commands. It displays
only safe entity IDs, reference IDs, field names and document digests; it never
includes certificate material or secret values. A successful semantic Save
makes Project Verify evidence stale/unverified under ADR-027. It is not an
authorization to materialize or execute.

## 5. Certificates page UX

The page is available for an open Installer-managed project without a READY
Execution Node. It has four compact sections in dependency order:

1. **Managed CA** — list, add/edit/delete a `MANAGED` authority.
2. **Certificate profiles** — authority selector, usages, explicitly set
   policy/subject overrides and an inherited-fields summary.
3. **TLS profiles** — certificate-profile selector, optional scope and masked
   stable runtime SecretRef label. The label is not a secret field.
4. **Certificate scopes** — profile selector; optional display name and scope;
   multi-select sources for current hosts, deployments and deployment-scoped
   members; and bounded direct-input lists for explicit DNS names and IP
   addresses. These are canonical source values, not a calculated SAN preview.

Controls use the shared draft and Save/Discard flow. A local structural error
is shown beside the form. A `REFERENCE_IN_USE` delete error identifies only
safe dependent IDs and offers navigation to the affected managed section; it
does not implement cascade deletion.

Below the editor, a read-only **Core verification** area has the existing
Project Verify action/state and shows only revision-bound identity/SAN evidence
when current. It states that provider VIP influence is determined by Core after
Save and Verify; no checkbox predicts or overrides it. A blocker such as
`CERTIFICATE_REISSUE_REQUIRED` is displayed as a Core finding, never hidden,
downgraded, auto-confirmed or bypassed.

UI-01H consumes saved TLS-profile IDs through its existing catalog-declared
`tlsProfile` setting. UI-01G neither assigns a profile to a deployment nor
creates a TLS consumer by merely creating an authority/profile/TLS-profile.

## 6. Milestone slices

### UI-01G1 — v1alpha7 PKI contract and managed reopen

- additive schema, decoder and narrow validators;
- managed PKI projection/read bounds and direct owned-state reopen;
- candidate reducer, generic reference graph and guarded local Save tests.

**DONE (2026-09-17).** The post-review schema-parity correction is recorded
as owner-authorized DIFF-002 evidence in `ui-01g1.md`; it did not alter a
published schema or introduce another review cycle.

### UI-01G2 — Certificates page and shared draft

- four compact editor sections, typed intents and Review/Save/Discard;
- inherited/omitted treatment, runtime SecretRef reference-only UX and safe
  delete/error states;
- no Materialize/Reissue navigation or service TLS assignment.

**DONE (2026-09-17).** The Wails/React Certificates page uses only v1alpha7
typed intents over the shared structural draft. Scope references are selected
from final draft hosts/deployments/member placements; explicit DNS/IP remain
direct inputs. Evidence: `ui-01g2.md`.

### UI-01G3 — verified Core evidence and cross-page hand-off

- revision-bound typed PKI projection, freshness/invalid rendering and finding
  navigation;
- UI-01H selector seam only, without implementing the Services editor;
- explicit stale state after PKI semantic Save.

**DONE (2026-09-17).** `VerifiedPKIView` is an in-memory, bounded, typed
projection of the existing revision/node/runtime-attested Core snapshot. It
never exposes raw `pki`, and displays identity/SAN values only for `CURRENT`
evidence. Saved TLS-profile IDs remain the existing managed desired-state
selector seam for UI-01H; no Services editor or service TLS assignment was
introduced. Evidence: `ui-01g3.md`.

### UI-01G4 — Windows/RED OS acceptance and regressions

- built desktop flow, close/reopen and shared-draft behavior;
- target-free Core Verify evidence, RED OS regression/race and hygiene gates.

Every slice requires a separate owner start request and mockup comparison.

## 7. Acceptance and non-negotiable safety checks

Focused tests must prove:

- v1alpha7 is closed/additive and older versions remain compatible;
- valid/invalid CA, profile, TLS profile and scope shapes, duplicate IDs and
  bounded source/member collections are handled safely;
- a complete scope Update preserves/edits display name, scope, all source
  forms and schema-authorized extensions without loss; reopen and update tests
  cover explicit DNS/IP sources;
- all seven generic reference edges block unsafe deletion, including
  deployment-scoped member identity and service `tlsProfile` references;
- create/update/delete -> structural Review -> local Save -> close/reopen
  preserves the direct PKI desired state without a Core/Execution Node call;
- canonical bytes remain unchanged before Commit, and guarded rollback remains
  intact on a failed Commit;
- Verify reads the saved revision through Core target-free only; a PKI Save
  makes previous evidence stale; `INVALID` does not roll back saved files;
- `VerifiedPKIView` rejects malformed/raw/oversized Core PKI data and late or
  mismatched revision/runtime evidence without a partial preview;
- fresh Core evidence reflects a provider VIP/SAN change only through Core;
  React/Go never infer it, and `CERTIFICATE_REISSUE_REQUIRED` remains blocking;
- no private key, certificate, password, password-file content, runtime path
  or secret value reaches project files, command DTOs, views, review text,
  findings, frontend state or logs;
- no target contact, materialization, reissue, apply or verify playbook is
  caused by UI-01G editing or Project Verify.

Final gates: focused Go/frontend tests; `go test ./...`; `go vet ./...`;
frontend lint/test/build; Wails build if bindings change; affected RED OS race
tests; target-free Core validation/ProjectSnapshot evidence; catalog/schema
reproducibility; secret audit; `git diff --check`; and the risk-appropriate
architecture review specified by repository rules.

## 8. Design constraints and completion

UI-01G is complete only after all slices and final gates pass, the Core/PKI
boundaries above remain intact, documentation/state/roadmap are synchronized,
a focused commit exists and the worktree is clean. UI-01H does not start as part
of UI-01G.
