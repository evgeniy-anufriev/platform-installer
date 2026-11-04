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

## Registry availability planning, 2026-11-03

Owner requested at least 2x faster Create Plan, no offline image preparation,
and only registry availability checks from every target. Owner emphasized real
work reduction rather than merely postponing it. Review was not invoked per
owner instruction. Current contracts are extended additively: runtime request9,
capabilities15, plan12, manifest9; existing versions retain their meaning.

Create Plan now probes one HTTPS `/v2/` per host/registry (200/401). It neither
reads image manifests/configs nor requests registry secrets. The immutable
manifest binds private image intents; exact identity is resolved before Apply.
Anonymous metadata contexts and identical explicit credential-source contexts
share results within one invocation. Distinct node logins/platforms/policies
remain separate. Verify reuses the run result without another registry query.
The existing runtime credential lease, transport, Ansible role and parsers are
reused. Empty anonymous secret maps were corrected to nil in Go admission; this
prerequisite correction was present in both measured binaries.

Measurement: actual full-App React handlers -> Wails
`CreateInstallationPlanForMode` -> Execution Node .101, same two public image
references (busybox1.36/alpine3.20), one library, all three RED OS target hosts.
No layers were pulled and no container/service Apply, Approve or Start occurred.
Each sample opened the saved fixture, set runtime-only SSH credentials, probed
and explicitly approved the established host fingerprints, checked the node,
ran Verify, then invoked Create Plan. Only the full synchronous Create Plan
call was timed. Each returned PLAN_REVIEW/EXECUTABLE. Reopen cleared the prior
session plan; no cached UI plan result was used as another timing sample.

| Variant | Full Create Plan, seconds | Median |
| --- | --- | --- |
| Before, metadata at Plan | 122.2869 / 130.4560 / 130.6174 | 130.4560 |
| After, availability at Plan | 21.1921 / 18.7909 / 19.1776 | 19.1776 |

Median acceleration **6.80x**, exceeding the requested 2x. The final sample used
the final source bundle and combined Go transport fixes from origin/master.
To separate postponement from actual work reduction, a supplementary real Go ->
Execution Node compatibility-v7 plan retained full metadata-before-Plan work:
47.2898s and final48.8401s, six resolved placements, EXECUTABLE. The final run was
`installer-225708537413784313568194913219555650473`, plan
`plan-f7ebf98dc3f07d90bd82766a`. Even this path is **2.67x** faster than the old
median. It includes fresh public host-key discovery in the credential provider;
it is supplementary Core evidence, not a substitute for the React/Wails gate.

Fixture identity `project-2026110300000031`; references, placements and native
configuration stayed the same. Saved revisions changed only as bundle binding
changed:

- Before revision `sha256:0f5ab7702a44dded9c29517d7ede040ea783c300b1e9e11a641975789c09b20e`,
  bundle `sha256:8af34a285138d61745dbd4250d694c4d15ff37a7ed682b1177b9b75198c0c29a`,
  plan `plan-76c6ffa1cbad0c81face65ed`. Staging runs:
  `installer-231327343489178516514229704181463922146`,
  `installer-179367423509237543953974826307878697100`,
  `installer-67567772514452038619969374881204551489`.
- Initial after revision `sha256:0e183e6d8c063b9fab3ceb472ad280f112d6713647db850bb8d4b73d08ad0082`,
  bundle `sha256:fc254be435576aca25c16c27c3cf17ac1adbb9a3274f3ed8febe5124f3a54f5d`,
  plan `plan-d12a67c8fc74d6e1f25fb157`. Runs:
  `installer-290353611859461754769663439092450402500`,
  `installer-161894316807220236271743010099979235236`.
- Final revision `sha256:027fe555a2b7bc9111f4bae5c8182353012d09920ea2bac006c88c79fdef60e4`,
  bundle `sha256:aaef188bfefd8655cd0a83e298504ffc5da29e27fb82c4d90e81d2dbef599311`,
  plan `plan-b05743b6a815f6e35d4d0796`, run
  `installer-68228882367848811826548731991767135237`.

An initial five-image/three-target baseline exceeded the old preparation lease
and failed; excluded from timing. Automation retries without a new React plan
invocation and a duplicate test dialog handler were also excluded. Actual
before/after timings above are successful full calls only. No production
registry credentials, operator private keys or secret payloads were recorded.

Validation: eight new RED OS tests PASS, including actual native Ansible TLS
registry probe, two manifest/two config reads for six placements, no queries
when reusing the result, native fresh offline execution preparation, all three
plan/manifest execution modes, reference binding and credential-context
isolation. Existing image preparation7, image parsing5 and application plan17
PASS. Full Go tests/vet PASS; InstallationPage38/typecheck/lint/frontend build
PASS; production Windows Wails build PASS. Fresh worktree QA needed the existing
ignored SZI themes archive from the original checkout; no artifact acquisition
or source package change was made.

One existing Core protocol test remains failing at its earlier candidate
BuildRuntimeSecretDescriptors fixture with CORE_OPERATION_FAILED; the exact
same failure was reproduced in the untouched baseline workspace before this
change. It was not hidden or reported as PASS. Actual new-protocol and legacy
compatibility planning above passed. Full service installation, image pull/load,
visual inspection and ALT acceptance are outside this measurement scope.

Bundles were built on trusted node2 from qa-sync current sources, verified and
published with the standard publisher before UI use. Raw timings and bounded
automation helpers remain ignored under `.runtime/qa/plan-registry-availability`.

Final entry-point check moved image result loading into shared
`stages/resolve-runtime.yml`, covering Apply, Verify and post_install equally.
The native offline test also executes that shared stage with the desired-state
technical image lock removed; it consumes the saved run result successfully.
All eight tests and syntax checks of Apply/Verify/post_install PASS after this
wiring correction. Release bundle
`sha256:1b8537ad8d0c879ba394678495dad9d77bbbe3df0c6460c222c41ed09fb98ec9`
was built and validated. The timed aaef bundle has the same Plan/preparation
code; the final shared execution-entry wiring was not used for another timing
sample or claimed as service installation acceptance.

Cleanup complete: previous c97e77d7 runtime restored to READY through real
React/Wails preparation; both touched caches restored with the standard
publisher. Owned Vite/Wails processes stopped. All four temporary node2 source
workspaces removed through qa-sync cleanup. Twelve unstarted synthetic benchmark
plan staging directories were removed only after exact project identity,
containment and absence of execution status/metadata were checked. No real run
or installed service was removed.

### Owner-requested SZI installation follow-up (2026-11-03)

Real full-App React/Wails integration uses the existing three RED OS QA VMs,
SZI with all five current application packages on node3, and the installed
PostgreSQL/Redis/Vault/Docker infrastructure. This is an Apply over an existing
scene, not a clean install. Infrastructure Apply is disabled; the infrastructure
Verify risk bypass is not selected. Unused ClickHouse/Kafka definitions were
removed from this isolated fixture; no installed service was removed.

Initial Verify exposed a package defect: Nginx read
`application_connections.sso.parameters.realm` while declaring no SSO client
connection. Declaring it would incorrectly request the Keycloak client callback
and fail `APPLICATION_CONNECTION_CALLBACK_INVALID`. The one-line correction
reads this library's already resolved provided SSO realm instead, leaving Nginx
without an extra client to provision. A native Ansible regression exercises the
real instance context and a non-default realm. RED OS stage1 tests: 12 PASS,
one existing Docker CLI SKIP; native Keycloak script tests: four PASS. The latest
delegation transport tests also pass (four tests). No review invoked, per owner.

Current-source bundle includes the separately published delegated SSH fixes
through `e142b089`; digest
`sha256:597e79fc14bd722d3c28a841e33265c8fd5175b1f41ed32c2843df2309961264`.
Built on node2, verified and published with the standard publisher, then
activated through real React/Wails Prepare. The actual server `runtime/current`
was checked independently. Due to limited node1 disk space, a small current-Core
transition bundle was activated first; only the inactive owned preliminary SZI
release `747cded6...` was then removed after containment/current/no-nonterminal-run
checks. Prior unrelated runtime releases and installed data were retained.

Vault had been sealed after the VM restart. Existing generation2 outputs for
this same project/deployment were delivered into the established private runtime
secret directory and used to unseal all three nodes. No initialization, key
rotation or data reset occurred; values are absent from evidence and source.

First actual Plan -> Approve -> Start:

- Revision `sha256:bca83132c95dca91486a1f82362a3a24cd42452093e49cacfaf803a987459cdb`.
- Plan `plan-bf5df040fd7a426cbe7eaf57`, EXECUTABLE, 46.0271 seconds.
- Mode APPLICATION_LIBRARIES_ONLY; only APPLICATION_LIBRARIES_APPLY action.
- Run `installer-3f8d6ab3030668b8b2cc918edf80524b`, terminal FAILED.
- 1797 public events: all application parameter/connection resolution,
  deferred-image preparation, five local image identity/platform checks,
  Vault CA/trust discovery, generated shared-secret delivery, PostgreSQL
  account authentication and runtime file preparation passed. Existing images
  were reused; fresh archive load/pull is not claimed.
- Failure: Keycloak/node3 image/owner/readiness wait, event1793,
  ANSIBLE_FAILURE_REDACTED. Container restarted, Docker OOMKilled=false,
  memory limit2GiB, heap1GiB. An initial diagnostic incorrectly matched the
  printed JVM flag ExitOnOutOfMemoryError; OOM is NOT confirmed. The diagnostic
  now excludes flag lines. No unredacted logs or secret values were recorded.
  Final library Verify was not reached.

A second full React/Wails attempt uses fixture-only heap512MiB as a resource
experiment and Keycloak verbose startup for the 5GiB QA VM. This does not prove
memory caused the first failure. Production package defaults are unchanged.
The new revision is
`sha256:80a3a546a23c59dfd5eb475ba72950ba5f308f07d1467d7c8ea49843ac44785d`;
plan `plan-cb34e089540d7b2481095764` is EXECUTABLE (42.693 seconds), approved.
Run `installer-082448038293309b4282c99e6de423c5` also ended FAILED at the
Keycloak readiness wait. Verbose startup identifies
`org.keycloak.policy.PasswordPolicyConfigException`: password policy provider
not found. The worktree fixture omitted nine Git-ignored provider JARs that are
present in the original working package. Those existing approved files were
copied into the fixture (nine files, 174483 bytes), without downloading anything
or changing database policy/data. The temporary heap override was removed.

Third attempt uses standard package heap defaults, complete providers, and
fixture-only verbose startup. Revision
`sha256:70c2e9b396ed271c6d27e890e6450293f2cb3ff893fd6b0d1aa83038c4480e92`.
Plan `plan-17e413277e46c5b948033631` is EXECUTABLE in 42.6682 seconds;
approval 42.7825 seconds, authoritative Start 92.9332 seconds. Run
`installer-c2b66d432e689f277142bf170f715100` completed **SUCCEEDED**, 3071 public
events and zero FAILED events. Safe event summaries/raw selected metadata are
retained under ignored `.runtime/qa/szi-plan-install-20261103`; actual run
results remain on the Execution Node.

Affected-path results:

- Core resolution and inherited parameters for all five applications PASS,
  including the corrected Nginx realm and no extra Nginx SSO client callback.
- Deferred image preparation and five local image identity/platform checks
  PASS. The run result is stored for shared execution stages; already installed
  images are reused. Fresh archive load/pull is outside this acceptance.
- Vault CA read/trust, generated shared-secret delivery, PostgreSQL account
  authentication, AppRole login and protected secret reads PASS.
- Keycloak starts with the original heap1GiB and all nine provider JARs,
  RestartCount0, health=healthy. The earlier failure was an incomplete fixture,
  not demonstrated insufficient memory or a database policy defect.
- Exact package scripts, Keycloak administrator/consumer integration, HAProxy
  candidate/render/activation checks, DNS updates and HTTP endpoint checks PASS.
- Final per-container verification: grant-access event3026, audit3028,
  frontend3030, Keycloak3032 and Nginx3034, all SUCCESS/node3. Final library
  post-install script also succeeds. Docker observation: Keycloak/grant-access/
  audit healthy; frontend/Nginx running (their selected readiness is container).
- Final current-source native SZI13 PASS, Keycloak role scripts4 PASS,
  consolidated application entrypoints6 PASS. No independent review or visual
  inspection was invoked/claimed. This is existing-scene application acceptance,
  not clean infrastructure installation or full SI11 acceptance.

Follow-up cleanup: node2 source/build workspace removed through qa-sync;
owned Wails/Vite processes stopped and temporary drive mapping removed. Active
verified SZI runtime and actual run results retained. Terminal run has zero
`.runtime-secret-*` and zero `.runtime-application-secret-*` files. Automatic
policy review rejected deletion of the two local copied Vault input files
(`blocked by policy`); those copies remain only under the established
`.runtime/secrets/szi-plan-install-20261103` directory, with no value disclosure.

### Approval / Start profiling and proposed optimization (2026-11-03)

Analysis only; no production implementation or new installation. Same saved SZI
revision70c2e9b3 and active/published runtime597e79fc as the successful run above.
QA uses the established PEM identity. Actual React/Wails handlers performed
Verify, Plan and Approve, then stopped before Start. Fresh UI Plan41.6435s,
Approve41.0634s. The prior complete, successful Start remains92.9332s; a new
full Start was deliberately not invoked for this analysis.

An ignored Go profiler delegates to the unchanged OpenSSHTransport and real
Execution Node Core. Its runner records only operation/phase/process names,
durations, counts and failure flags; no argv, stdin, stdout, stderr or secret
values. These are isolated transport/component measurements, not a new
end-to-end Start acceptance run.

| Measured component | Wall seconds | SSH | SCP |
| --- | ---: | ---: | ---: |
| Local ProjectRevision | 0.0396 | 0 | 0 |
| Core secret descriptors including candidate staging | 23.6411 | 9 | 1 |
| Additional snapshot for pending application-secret bindings | 16.7212 | 4 | 0 |
| Fresh executable plan, same service/library order as UI | 41.1404 | 16 | 0 |

The latter three isolated operations total81.5027s,29 SSH and one SCP. They
must not be added again to UI Plan/Approve timings: those are enclosing flows.
Descriptor plus binding snapshot40.3623s closely explains actual Approve41.0634s.
Start currently repeats that preparation unconditionally despite a valid recent
approval, before its mandatory fresh plan rebuild.

Within fresh planning, protocol child wall times: inputs DESCRIBE17.4816s,
PREPARE0.7854s, BuildDeploymentPlan16.3872s, two capability responses1.7377s,
ten runtime path/state SSH probes4.1959s and archive-cache lookup0.4927s.
Thus DESCRIBE's name must not be mistaken for expensive image downloads: it
resolves the project again. No offline pull/load took place here. The single
SCP in descriptor staging is0.9130s. Across all three components, sixteen
runtime path/state probes cost7.2843s. Standalone capability repeats cost
1.5348/2.0163/1.7331s, each three SSH connections.

Corresponding Core timings: descriptors15.1062s (resolve12.1107s), snapshot
14.2615s (resolve12.1094s), image inputs16.1259s (resolve12.4452s), plan
15.2391s (resolve12.4311s). All four report cacheHit=false/reusable=false;
lock wait is3-4 microseconds. This sample is repeated computation, not observed
Core lock contention. The conservative existing cache/path/template guards must
not simply be disabled. Production's reported >5 minutes is not reproduced on
this QA scene; project scale, SSH/PAM/password costs and contention need the
same breakdown on that environment before assigning its exact cause.

One initial isolated plan used an empty service order and failed with
CORE_OPERATION_FAILED. It is excluded. Repeating with the actual UI order
produced an EXECUTABLE plan and the successful measurement above. Safe raw
profiles remain under ignored `.runtime/qa/start-profile-20261103`.

Proposed order, retaining the existing authority/lifecycle:

1. Reuse current Core-attested secret descriptors and binding evidence after
   approval, with exact project/revision/node/runtime checks and current Broker
   input bindings. Re-attest only when evidence or bindings are absent/stale.
   Preserve latest-value replacement, expiration/missing-input checks and the
   mandatory fresh Core plan/fingerprint comparison. Reuse existing functions
   and private state; no second persistence or infrastructure rules in Go.
   This removes the measured ~40s duplicate branch from the unchanged case.
2. Execute runtime path resolution, active digest read and the fixed protocol
   entrypoint through one SSH invocation per RPC. Retain strict host-key and
   command guards, bounded/private streams and runtime identity validation.
   Reuse capability negotiation within one operation for the same runtime;
   avoid a new persistent SSH/session daemon or global stale-capability cache.
3. Share one authoritative Core resolution between image-input description and
   fresh plan construction, scoped to that exact preparation. Likewise derive
   pending-secret source bindings from the same Core evidence as descriptors.
   Evolve the closed protocol if needed; do not weaken cross-request cache
   eligibility or recreate template/source rules in Go.
4. Instrument queue wait, descriptors/bindings, staging, image inputs, plan,
   trust/lease, remote Start and subscription separately. UI "starting" also
   currently awaits subscription and state refresh after run acceptance; fixing
   that presentation is separate from reducing actual Start work.

Estimate for phases1-2 on this QA scene: ~40-55s instead of92.9s. This is a
target, not a measured improvement. Validate on the same project/runtime with
at least three samples and one real fresh-plan -> Approve -> Start -> terminal
run. Required regressions: current proof avoids duplicate queries; changed
revision/runtime/node, changed or expired input, pending file/password
replacement, template-bound sources and stale plan retain correct failure or
reattestation. Fresh authoritative plan, trust and idempotent lease/retry guards
must remain. No review invoked per owner's continuing instruction.

Profiler cleanup: UI browser/Wails/Vite stopped; production generated runtime
files restored. Two owned, unstarted plan-stage directories removed only after
exact run-id, containment, project identity and absence of execution status/
metadata checks; candidate/snapshot cleanup had already removed the others.
Existing successful installation results and installed services remain intact.

### Start optimization implementation and owner stop, 2026-11-03

Owner authorized items1-2 above, then explicitly prohibited commit/push and
requested stopping the SZI installation. Changes remain uncommitted:

- Start reuses exact project/revision/node/runtime descriptor evidence and
  Core-attested editor-source mappings, rebinding current Broker values/files.
  Missing/stale evidence and unmapped pending locations retain fresh discovery.
- Each ordinary runtime RPC resolves the immutable release and active digest
  in a fixed, quoted node-side launcher and execs the existing protocol through
  one SSH call. Private stdin, strict trust, bounded streams and command guards
  remain. Plan capability negotiation is reused only inside that operation for
  the exact bundle/Core/catalog identity; missing/mismatched identity re-probes.
- Existing functions/files were amended; no Core rules, protocol version,
  persistent credential/capability cache or production testing bypass added.

Full Go tests and vet PASS; frontend typecheck/production build PASS. Focused
regressions cover fresh authoritative plan rebuild, descriptor/mapping reuse,
project/revision/node/runtime changes, pending password/token replacement,
expired inputs, unmapped locations, one SSH/private stdin, private-flag bounds,
and operation-local capability reuse/fallback. RED OS node2 exercised the exact
launcher source in an isolated temporary root: valid/private flag, oversized or
missing state, invalid digest/UTF-8, outside-root and whitespace release cases
PASS; temporary root removed. Live node1 capability smoke PASS with one SSH.

Before sample used unchanged Wails backend at bff08196, real React handlers,
same project `project-b46aa3f5f57a495f`, saved revision
`sha256:70c2e9b396ed271c6d27e890e6450293f2cb3ff893fd6b0d1aa83038c4480e92`,
runtime `sha256:597e79fc14bd722d3c28a841e33265c8fd5175b1f41ed32c2843df2309961264`:
Plan41.414s, Approve42.2302s, Start92.168s, plan
`plan-17e413277e46c5b948033631`, run
`installer-f5460522867a2ca89d9be8241e3293da`.
Owner-requested cancellation used real Wails `CancelInstallationRun`; observer
confirmed terminal CANCELLED, last observed event2241. This is not successful
installation acceptance. New-code Wails Approve/Start timings and full changed
flow acceptance remain NOT RUN; no speedup claimed. No new installation will
start without the owner's renewed instruction. Evidence is under ignored
`.runtime/qa/start-optimization-20261103/`. Owned browser/Wails/Vite stopped;
generated frontend/runtime changes restored. Existing runtime, results and
installed services preserved; no commit/push or review performed.

### One approval and Start action, 2026-11-04

After the owner renewed authorization to start SZI, the Plan action
«Одобрить и начать установку» used one real React/Wails call to Go
`ApproveAndStartInstallation`. It uses the existing approval and Start,
stops on failed approval, reuses current secret evidence with current values,
and preserves the fresh authoritative plan and start/lease guards. An already
approved plan retains the existing Start retry. No Core bundle change.

Same saved revision, runtime, plan ID and APPLICATION_LIBRARIES_ONLY scope as
the before sample above. First combined Wails attempt timed out without a
recorded new run; the node confirmed the previous run remained CANCELLED.
Fresh Wails session with verified host keys and current secret inputs:

| Measured Wails operation | Before | Combined implementation |
| --- | ---: | ---: |
| Create Plan | 41.414 s | 34.414 s |
| Approval + Start | 42.2302 + 92.168 = 134.3982 s | 73.3523 s |

One paired timing sample; separate post-change stage durations not measured.
Combined call saved 61.0459 s (45.4%, 1.83x). Actual single bound method
returned STARTED; separate approval and Start bindings were not invoked by
React. Run `installer-9033c2323e5158d2d02c4546a37a82ba` reached SUCCEEDED at 09:52:10 MSK. The complete node journal contains 3071 events. Preparation, SZI library installation and application Apply each completed with SUCCESS. No FAILED, ERROR or UNREACHABLE events. Safe evidence:
`.runtime/qa/start-optimization-20261103/after-combined-retry.json`.

Full Go tests/vet, frontend build/lint and affected React tests169 PASS.
Combined approval regression covers missing acknowledgement, blocked/unknown
plans and the mandatory fresh plan. Wails dev build and real dispatch PASS.
No commit/push/review.
