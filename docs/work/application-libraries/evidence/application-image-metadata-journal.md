# Application image metadata — implementation evidence

2026-10-20. Owner approved the image/registry plan and implementation in a new
worktree, preferring built-in Ansible tasks and avoiding unnecessary restrictions
or abstractions. Worktree `application-image-metadata`, branch
`codex/application-image-metadata`, base930d5f71a83e3be99901ea40e2af6464394526f5.
The original main checkout was not edited.46 inherited dirty paths were copied
with before/after SHA verification; they are separate from the owned delta.

## Passing supplementary checks

- `go test ./...` and `go vet ./...` PASS. Two initial SDKU import failures were
  caused by checkout LF bytes versus source CRLF package digests. The two
  application.yml files were restored to byte-equivalent original line endings
  after verifying identical normalized contents; no package behavior/catalog
  digest changed. Final full Go checks PASS.
- Frontend265 tests PASS, typecheck/lint/build PASS. Existing React act warning
  and bundle-size advisory remain warnings. Generated browser HTML line endings
  normalized; git diff --check PASS.
- Fixture catalog and service configuration-schema reproducibility PASS.
  SDKU27 schemas/digests,2 prepared jobs,26 Compose renders and one shared base
  PASS. No real application execution was performed by these checks.
- Focused RED OS14 tests PASS326.109s on snapshot
  `/var/tmp/platform-installer-qa-fb113f6af8d24d5da4b90480f0b60349`:
  index/hash4, preparation/lease/descriptors4, real local TLS registry5
  (Basic/Bearer/anonymous/corrupt config/dedup), production auth/pull cleanup
  success and failure in one two-subcase test. HTTP fixture downloads no layers.
- Final network-isolated `sudo -n unshare -n`10 tests PASS170.418s on
  `/var/tmp/platform-installer-qa-8414b4ad435043faa0be725dc56292e4`:
  pure8, production transient-auth cleanup on both outcomes and actual Core
  protocol override→synthetic bundle→DESCRIBE/PREPARE→EXECUTABLE plan7 plus stale
  metadata digest rejection. No target SSH contact or external registry access
  occurs in this offline fixture. Synthetic pull commands are supplementary
  cleanup evidence, not real Docker delivery acceptance.
- Actual offline controller validate.yml on the application-runtime fixture:
 64ok/changed0/failed0/skipped16 on the same final snapshot.

Python/Ansible ran only on RED OS192.168.56.101 as platform-automation, with the
established SSH identity, IdentitiesOnly and noninteractive sudo. Sources were
transferred through scripts/qa-sync.ps1. No Internet acquisition, runtime bundle
publication/activation or application installation occurred.

## Failed/incomplete attempts

The initial protocol test timed out90s while observed node load was about50;
no unrelated processes were stopped and the test timeout was not increased.
Later fixture fixes corrected three placements and the existing project.yml
schema (identity, compatibility contract version and catalog pins). The current
protocol fixture subsequently passed, including the offline run above.

An initial offline validate.yml attempt against the existing kafka-single fixture
blocked on selected definition alpha.2 versus catalog/lock alpha.3. That unrelated
fixture was not modified. The affected application-runtime fixture passed.

Full Core regression was started on the earlier snapshot
`/var/tmp/platform-installer-qa-f89b447d910145759e081d5f7c9e4f8e`. It displayed an
initial F from the subsequently corrected protocol fixture and an E whose
traceback was not yet available. After the independent BLOCK, the still-running
suite was stopped rather than continuing automatic implementation/acceptance.
The exact owned SSH process group was checked by PID/PGID and current directory
before termination. This is **not a full regression PASS**; the E remains
unclassified. The partial log is retained under local ignored
`.runtime/image-metadata-qa/core-regression-incomplete.log`.

## Historical FULL review and gates before owner decision

[FULL DIFF review](../reviews/application-image-metadata-diff-review.md): **BLOCK**,
five unresolved findings AIM-D01–05. Frozen manifest F8A6D132F478BE68EEAA17A7104EF4E68350E26CAF39E2C1F251CDF695C83D62,
owned diff7EEEAEE83A484435735E20C371CC4BCAD179EAAFD578D394B87D4D3BC8197486.
Reviewed implementation bytes were unchanged during review. Only this report
and the current-state entry were added/updated after BLOCK; no implementation
corrections were made. Confirmed unnecessary mechanisms:0; concrete source and
secret defects still require correction.

Actual React/Wails/Core assignment→Review/Save/reopen→runtime session inputs→
Create Plan has not been performed. Visual inspection has not been performed.
Updated QA runtime publication/preparation requires separate owner authorization;
mocked frontend/native protocol checks do not replace the real bridge gate.
No plan was approved or execution started. Work remains uncommitted in its
separate worktree. Follow the review procedure: owner decision, bounded corrections
for the blocker IDs and at most one owner-approved TARGETED_RECHECK.

Temporary QA sources are cleaned with the standard qa-sync helper. Root-owned
bytecode generated by unshare checks was reassigned only inside the verified
isolated QA directories before cleanup. Safe validation/partial regression logs
and frozen local review before-images remain under ignored .runtime for evidence.

## Owner-directed corrections, 2026-10-20 (QA and scoped targeted review completed)

Owner rejected AIM-D01 and AIM-D03; their implementation is retained. AIM-D02
removes redundant private secret values from add_host: the original private
extra-vars already supply them. AIM-D04 validates registry assignment keys as
host[:port] at the existing portable schema and managed writer boundaries.
No registry resolver or extra desired-state store was added.

Focused RED OS preparation/native registry tests:12 PASS, including -vvv
standalone success/failure redaction and invalid registry authorities. Go full
tests/vet and frontend build/typecheck PASS. Catalog/schema reproducibility and
SDKU27 package schema/digests,26 synthetic Compose renders PASS.

The earlier regression E was classified: registry suggestions attempted to read
an absent image in an intentionally partial member projection. Suggestions now
skip that absent optional image. Final-source offline13 tests PASS. Full Core
regression completed:734 tests in2865.932s,712 PASS/22 explicit skips, zero
failures/errors. qa-sync source verification passed before exporting the log
and cleaning the isolated source tree. Skips:14 root filesystem,4 isolated root
acceptance,2 explicit native gates,1 SSH target and1 local root permission proof.

QA bundle application-image-metadata-20261020-02, digest
sha256:ebc1d3fca218b35cf0bb656d7a3625bfbd107d7854b2e9d90578db4cd6b32003,
was built on trusted node2, verified and published using the standard publisher
in this worktree's cache. Main checkout cache/services were not changed.
Real React/Wails opened the managed QA project, accepted independently matched
SSH fingerprints and prepared node2 to READY. Image and registry runtime refs
were saved via actual Review/Save. Session-input/plan/reset/reopen acceptance is
completed below. Only the target can reach the localhost TLS registry fixture;
Execution Node connection returned HTTP000. Synthetic values remain runtime-only.
No application plan has been approved or started. Visual inspection not performed.
The one permitted TARGETED_RECHECK is pending with final evidence now available.

Real UI found APPLICATION_REGISTRY_RUNTIME_SECRET_REQUIRED after successful
session input: preparation read only attached Broker values, while the form
stores pending values. The existing Broker promotion now runs after current
Core descriptor/scope checks and before the metadata-only payload is copied.
A new regression reproduced the failure before correction and passes afterward;
unrelated application secrets are excluded and a foreign library scope rejected.
Full Go test/vet PASS after this fix. Only Go changed: bundle02 and the tested
Ansible Core bytes remain unchanged. Owned QA Wails03 was rebuilt; original main
Wails was not stopped. Actual registry plans are now EXECUTABLE, and target
registry counters prove manifest/config requests while Execution Node HTTP000
remains independently recorded. Auth-failure/retry/reset and synchronized reopen subsequently passed, as recorded below.

## Final real React/Wails/Core acceptance (2026-10-20)

Current Go/Wails03, final Core bundle02 ebc1d3fc and the same saved QA project:

- Image override plus registry runtime references were saved through actual
  React Review/Save. A later current-code roundtrip repeated override/reset
  Review/Save/reopen and proved project.yml SHA-256 unchanged.
- Saved registry revision:
  sha256:428babe55b7b5e21b4ea187cdda6f469faab25929c8753d9fea00c7cd562e6c0.
  Runtime username/password were entered via the real session form. Fresh plan
  plan-f9f1520ba8377bab44457b39 returned PLAN_REVIEW / Core EXECUTABLE.
- Registry was reachable only at target localhost:45257. The Execution Node
  connection produced HTTP000. Target fixture observed manifest/config requests.
  Expected immutable config/imageId:
  sha256:b091a0ad63d887bde24bcdaa9c46fb026b000b0d35c2ef80a8637b0b906ae3b8,
  matching the indexed Docker-save fixture.
- Incorrect session password produced BLOCKED /
  APPLICATION_IMAGE_PREPARATION_FAILED and one registry auth rejection. No
  executable plan or silent offline fallback resulted. A new plan was requested
  using normal composition/skip-Verify controls; none was approved or started.
- Normal server-key confirmation restored the dynamic node binding. Correct
  session inputs and another Create Plan returned EXECUTABLE. The semantic
  plan ID remained f9f1520b because saved state/content identity were unchanged;
  actual Wails calls and additional manifest/config requests prove a fresh read.
- Reset to package default, Review/Save and Verify produced EXECUTABLE offline
  plan plan-6340d8fe7b73106db6ff02eb at revision
  sha256:c74e2613ceba6d639b2074f2ac8f595435558337b1c0f3a870a9cff0041cc803.
  Counters: before bad auth3 manifests/3 configs/0 rejected; after bad auth3/3/1;
  after retry4/4/1; after offline planning unchanged4/4/1.
- The cycle's final navigation raced with asynchronous OpenProject and timed
  out on the Project screen. Raw failure is retained. A separate synchronized
  real React reopen PASS and the current-code Save roundtrip PASS confirmed
  exactly the same offline-plan revision, default image and persisted registry
  references. This driver failure is not presented as a product PASS.
- Scan of50 public project/evidence/log files:0 matches for synthetic username,
  password, invalid password or encoded Basic credentials. Private runtime
  secret files were excluded. No manual imageId/manifestDigest/archiveRef or
  x-container-images metadata was persisted in group_vars.

Ignored local evidence: acceptance-summary.json (aggregate assertions),
ui-cycle-with-reopen-race.json (raw plan cycle and final navigation failure),
ui-reopen.json, ui-save-roundtrip.json, core-regression-final.log,
core-final-source-verify.log, go-final.log and go-final-vet.log under
.runtime/image-metadata-qa/. The raw earlier missing-pending failure remains in
ui-prepromotion-failure.json. Core734:712 PASS/22 skips; new Go regression failed
before correction and passes afterward; full final Go/vet PASS. Visual
inspection not performed. Application Approve/Start and real pull/load execution
were not authorized/performed in this acceptance.

The single owner-approved TARGETED_RECHECK approved D02/D04/D05. D01/D03
are owner rejections, not source corrections or newly accepted review defects.

## Scoped review closure and cleanup

[Independent TARGETED_RECHECK](../reviews/application-image-metadata-targeted-recheck.md):
APPROVE exclusively for AIM-D02/D04/D05,0 unresolved BLOCKING in that scope.
Manifest7AE2B734EA276DBF81E73775625844D1894464A5FFE47C93D1F353379EC5EA79,
diff0C3873D1F940014E9F11ECA2E4A92E616F9AE3B0AC396CA6F3534C405B11BADE,
acceptance summary8A58B8E902A38A4635D47997D481ADE48FD806107D42319ABA00221A560F19CA.
All82 frozen current files matched before/after independent review. D01/D03 remain
REJECTED_BY_OWNER; no technical reapproval or secret-safety waiver is claimed.
Original FULL verdict remains historical. Only evidence/status reports changed
after this recheck; implementation bytes remain frozen. Review budget consumed;
no additional review was initiated.

Actual CloseProject cleared the owned QA session. Owned Wails/Vite processes and
the target registry fixture were stopped; all five additional remote QA/source/
build trees were removed through qa-sync after verification/export. Original
main Wails remains running. Local public evidence, frozen review snapshots,
verified short-path QA bundle sources and published worktree bundle remain.

Automatic approval review rejected deletion of the local synthetic credential
.runtime/secrets/image-metadata-registry.json with 'blocked by policy', without
additional reason. It remains under the previously restricted runtime-secret
ACL. The registry for that synthetic credential has been stopped and removed;
the file was not copied to desired state, public artifacts or source. Cleanup
was split into exact-PID/path actions after an earlier combined command was
rejected; those process/remote cleanup actions succeeded. No attempt was made
to bypass the credential deletion rejection.

This closes the approved code and plan-only acceptance scope. Changes remain
uncommitted in codex/application-image-metadata; inherited SDKU work is preserved.
Application execution/real pull/load, visual acceptance and another milestone
are not claimed or started.

## Owner-authorized commit/master integration, 2026-10-20

The owner requested committing this work and integrating master. origin/master
was fetched; local master fast-forwarded00604e60 to b33a425e (portable-source
refresh). The image branch was advanced from930d5f71 to b33a425e before applying
only the AIM-owned diff against its recorded before-images. Full original WIP
is preserved in stash7da56e08da9f26c5d3020f93166caed04ae09b06; inherited SDKU
configuration was not replayed over newer Kafka/SDKU commits. Source merged
without conflicts. Two documentation conflicts retained both current master
records/sections and AIM content. Original owner plan files are included.

Post-integration checks:

- Core application regression139 tests:138 PASS/one existing explicit skip,
  93.871s on the primary RED OS VM; actual source bytes transferred by qa-sync.
- Full Go test/vet PASS. Initial SDKU import check exposed two preexisting import
  digest records computed from Windows CRLF application.yml bytes. Both package
  definitions are text-identical to canonical LF Git bytes. Their generated
  catalog records were corrected to canonical LF bytes; package settings were
  not changed. Raw main-file bytes reproduce the old hashes and prove the cause.
- Frontend build/typecheck,266 tests and lint PASS. Existing active-run test was
  aligned with the new busy-button label and still asserts disabled=true.
- Final canonical SDKU catalog:28 package schemas/digests,26 Compose renders and
  one shared-base variant PASS on RED OS. A separate fresh transfer included
  the corrected catalog. No real target execution occurred.

Earlier frozen-snapshot734 and real Wails plan-only acceptance remain recorded
above. No new bundle was published and no new UI/installation acceptance is
claimed for combined master; integration checks do not replace that evidence.
Scoped review dispositions D01/D03 and D02/D04/D05 are unchanged. Main's unrelated
uncommitted Kafka documentation edits are preserved separately and restored
outside the AIM commit. No runtime-secret or QA .runtime file is staged.
