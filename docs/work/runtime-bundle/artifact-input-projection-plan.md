# Bundle-local artifact metadata projection

Owner request, 2026-10-31: derive bundled service metadata/defaults from supplied
local artifacts; use --platform OS/architecture. Keep source/defaults and runtime
input unchanged during build. Supersedes removal of compatibility checks.
Owner also requests normalized source service.yml artifacts: local reference
plus policy only; artifacts.yml owns artifact identity/bytes metadata.

## Fixed implementation plan

1. Add authored service-manifest/v1alpha2 with artifacts entries containing only
   artifactRef (local metadata ID), requiredOffline and existing x-* activation
   policy. Normalize Kafka/ClickHouse source declarations without changing their
   existing values. Move name/version/OS/architecture into their artifacts.yml;
   sha256 remains there, digest is derived from it. Remove duplicated offline
   policy in metadata. Source role defaults are not changed.
2. Add a strict artifacts metadata schema. In the existing service_catalog
   generator validate authored v2 and fixed sibling artifacts.yml, reject
   missing/duplicate refs/IDs, paths/URIs, unknown versions and malformed values.
   Resolve references into existing expanded service-manifest/v1alpha1 catalog
   definitions and validate them. Policy comes solely from service.yml. Digest
   follows expansion/reference relocation. Keep safe x-source provenance.
   Reject authored v1 input per the later owner decision. Runtime catalog/project/plan/authority/bundle
   contract versions and Core/Go matching are unchanged.
3. In the existing offline bundle builder, after source/runtime copy and before
   catalog/defaults/components, inspect runtime/artifacts/<service>/ local files.
   Match RPM NAME to declared artifacts/runtimeRequirements; query only native
   RPM NAME/VERSION/RELEASE without executing package scripts. Require one unique
   explicit --platform OS/architecture pair for modified service metadata;
   repeated OS versions of that same pair are allowed. Extra dependency RPMs
   remain copied components, not invented requirements. Duplicate matched
   candidates fail before output publication. Empty input retains behavior.
4. Validate Kafka/Confluent tar headers without extraction/program execution:
   bounded member/path count, single safe root, contained links, no special
   entries/traversal. Recognize distribution version/root and expected launcher
   plus jar markers; do not guess from filename alone. Unsupported/ambiguous
   archive layouts fail. All work is confined to the staging directory.
5. Rewrite copied artifacts.yml version/file/platform/mediaType/sha256 from the
   supplied bytes. Discard stale acquisition URL for a replaced entry. Update
   corresponding copied role defaults actually consumed by the service:
   Kafka/Schema Registry versions, roots and command extension; ClickHouse
   package version and expected RPM hashes; Redis version-release. Other roles
   without pinned version defaults need only copied metadata changes.
   Supplied runtimeRequirement RPMs become copied v2 artifact refs with same
   id/name/requiredOffline and actual checksum; remove corresponding copied
   runtimeRequirement so there is one logical authority. Preserve other policy.
6. Supplied ClickHouse primary RPMs require a complete consistent trio. Apache
   Kafka plus a separate Confluent archive remain separate distributions. A
   single Confluent archive containing both launchers supplies both logical
   refs via the same immutable file/hash; set shared-distribution flag, matching
   install/archive roots and extensionless commands in copied Kafka defaults.
   Two candidate distributions for one ref are rejected.
7. Generate catalog/UI defaults/source index/components only after projection.
   Existing package source preference, checksums, requiredOffline, activation,
   publisher and path containment checks remain. No downloads, service installs,
   target changes or new Go/domain resolver. No runtime protocol revision.

## Review and validation

HIGH-RISK artifact-binding change: independent FULL PLAN then FULL DIFF review
under docs/agent-procedures/review.md; blocker stop and review budget apply.
Focused RED OS tests cover normalized refs/legacy rejection, compiled catalog schema,
Apache+separate Registry, shared Confluent, RPM changes, duplicate/incomplete/
conflicting inputs, malformed archives/platform, hash/index/defaults consistency,
no source/runtime-input mutation and deterministic repeat. Run existing affected
Core/builder tests through current qa-sync sources; no Python on Windows.
Build/validate representative QA bundle with existing trusted runtime and no
acquisition. Standard-publish before real React/Wails target-free Plan acceptance;
record digest/revision/plan; no approval/Start/service installation. Preserve and
restore prior cache. Record exact evidence and limitations here. Full Go test/vet
and frontend/Wails build for integration. Do not claim full install acceptance.

## Review decisions and current evidence

FULL PLAN APPROVE_WITH_CHANGES, baseline e6bf8b585d2b86c3aa3eb6d396ee71c550a2e3a9,
plan SHA77ff725e5ce88d3d8c7599045ffa4e017d4f171024980e9ee2fca0fc55cb375f.
AIP-P01 (reject ClickHouse RELEASE other than1) was superseded by the owner's
explicit instruction: parameterize the role; do not add release rejecting
checks. Per-package release and platform architecture now feed existing
install/preflight/Keeper/stock-unit checks; manual1/x86_64 remains compatible.
AIP-P02 metadata bounds are implemented without reading marker bodies.

FULL DIFF BLOCK, source fingerprint
4794a63992774437c9e889f4002c1dee2d8c507a6f6d9b7496e90ec9b5fa8f67
(14 paths and byte hashes in .runtime/qa/artifact-projection/review-manifest.txt).
AIP-D01 OPEN: legacy authored v1 is not schema-validated before constructing
the writable defaults path. A malicious absolute FQCN component can escape
staging. Required correction: validate v1, explicitly contain resolved defaults
path, prove external sentinel unchanged on rejection. Owner approval requested
for correction and one TARGETED_RECHECK; implementation/publication paused.
AIP-D01 owner decision: old authored service input is not required. Remove the
legacy v1 input branch, migrate all current authored manifests to v2, retain
only the expanded runtime v1 output contract. Explicit staging containment and
negative external-sentinel tests cover the writable boundary without a legacy
compatibility layer. Corrective QA and one targeted recheck follow this decision.
AIP-D02 NON_BLOCKING: existing repository probe compares VERSION, not RELEASE.
A repository with the same VERSION but another RELEASE can win and the native
exact-version-release install can fail. This task adds no rejecting assertion
and does not change repository source policy. Native release tests prove
template/ownership behavior, not cross-release repository selection.

Current sources tested on existing RED OS101 through qa-sync:
bundle/projection18 PASS; native ClickHouse release2 and manual1 tests2 PASS;
deployment-plan35 PASS; source authority7 PASS; fixture7 PASS and fixture
catalog reproducibility PASS; native shared Confluent7 PASS. Full Go tests and
vet PASS. Native rpm_identity read the real ClickHouse client RPM26.8.14.3-1.
No RPM installation or repository acquisition occurred.

An actual preexisting Confluent8.3.2 archive was built on the trusted existing
runtime without downloads. Standard validated/published bundle
54da7f2910479da4b7de628b754b287de41478f6f99e26d552d5372e55fc950d uses
explicit redos:8.0.3:x86_64. Both logical Kafka refs share its exact archive/hash.
Actual React handlers -> real Wails -> RED OS Core completed with ERRORS=[]:
project projection-ui2, saved revision
8163ca717a434525cdcb507b9e6a04db6d3e5c9095d5b4dce6cc99de4475a422,
plan-bfe645bd674de3a45365a2ed. No ARTIFACT_SOURCE findings; PLAN_BLOCKED only
for missing service-secret references. No approval/Start/service install.
Only the native Open picker was substituted by real OpenProject to the known
QA folder. Initial QA8.0 platform mismatch correctly blocked preparation;
rebuilt with actual8.0.3. An obsolete plan-id locator was corrected to the
rendered revision; final controller results-accepted.txt is PASS. Safe controller,
bundle and logs remain under .runtime/qa/artifact-projection. Visual/native-picker
and full install acceptance are not claimed. Owned Wails/Vite/browser stopped;
previous local cache restored through the standard publisher. QA runtime54da
remains installed on101; unrelated live services and runs were not modified.

### Final correction acceptance

TARGETED_RECHECK AIP-D01 APPROVE; current source fingerprint
59770b7557b58f66c3417c82a8b3d31db0225fbaf6c59dd6f38ec4d6cf788dcd
(.runtime/qa/artifact-projection/recheck-manifest.txt, 24 source/test/schema
files including ten authored-header migrations). Blocking findings0. AIP-D01
RESOLVED by strict v2-only input, resolved staging containment and sentinel
tests. One targeted recheck consumed; AIP-D02 remains nonblocking and unchanged.

Final current-source RED OS QA: bundle/projection20 PASS (including valid RPM
metadata during malicious FQCN tests, no outside writes/output and defaults
symlink escape), fixture7/reproducibility PASS, native ClickHouse2 PASS,
deployment-plan35 PASS and source authority7 PASS. Go full test/vet, frontend
production build/typecheck and Windows Wails production build PASS. Source
role defaults have no Git changes; build repeat/input immutability passed.

Corrected real-archive bundle
b64e552cb9d11a535ff4f6cb6ae7ba53212d70f010206a9434ee128fd0b62a93
was built from final qa-sync1398db67f364488095d18bab259c7d71, validated and
standard-published before UI. Final React/Wails/Core flow projection-ui3:
revision c892bd91564253958d24dd0541b5ab6000ccd89e9c9535e783ee7eb7d747d94f,
plan-ce0381094b341e7c492072cf, exact READY/runtime bundle binding b64e552c.
No ARTIFACT_SOURCE findings, PLAN_BLOCKED solely by missing service-secret
references, ERRORS=[], RESULT=PASS (results-corrected.txt). No approval, Start
or service installation; visual/native-picker acceptance not claimed. QA runtime
b64e remains on101; previous local cache restored with standard publisher and
owned QA processes/workspaces cleaned. No additional install assertions or
RELEASE restrictions were introduced.
