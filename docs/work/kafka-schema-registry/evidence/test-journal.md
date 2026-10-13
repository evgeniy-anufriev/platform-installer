# Schema Registry implementation evidence

2026-10-12; standalone Core runs on RED OS node2, 192.168.56.102.
Worktree base: bb32857280ba0238a1fc5a744b3226d8d3105f75.

## Acquisition

Official Confluent Community 8.3.2 archive acquired and checksum verified.
Standard bundle importer built and published bundle version
schema-registry-acquisition-20261012-27, digest
04a2b4a81927e975923e89f87c057ae81107a6ec7f5395fe2a36e9c8b8b22550.
This acquisition bundle predates the implementation; a current-source bundle and
real bridge acceptance are still required. The previous cache was preserved.

## Focused tests

On current synchronized source: Schema Registry projection/artifact tests 15 PASS,
configuration resolution 25 PASS, deployment planning 33 PASS. Package Apply and
Verify syntax checked earlier. Generated catalog and configuration schemas rebuilt.

## Native functional run

Workspace /var/tmp/platform-installer-qa-adb7e9a98d9a4cd98a8b1d2c55cd5f38.
Deployment qa-schema-registry-20261012, combined member srqa-1, node ID 1701.
Kafka ports 45992/45994/45993; Registry HTTP 48081 and HTTPS 48082.
Kafka 4.3.1, Schema Registry 8.3.2, Java 21.0.12.

Apply: ok=165 changed=2 failed=0. Verify: ok=144 changed=0 failed=0.
Repeat: ok=164 changed=0 failed=0. HTTP subject registration and trusted HTTPS
read of the same schema ID passed. Logs are protected remote QA output:
srqa-apply-2.log, srqa-verify.log, srqa-repeat.log; public functional summary
srqa-functional.json. Runtime credential values were not collected into evidence.

Earlier failures revealed restrictive inherited Kafka parent directories and
single-broker offsets replication factor 3. Registry now has its own protected
configuration/log roots and a capacity-bounded offsets default. The successful
native run includes these fixes. Subsequent Finding-format and exact topic-token
checks passed focused tests and final native Verify in workspace
/var/tmp/platform-installer-qa-5d1d70e9d66e42bb8401700e163d1a9e:
ok=144 changed=0 failed=0. Additional suites: configuration contract 5,
configuration preview 9 and artifact authority 4 PASS.

Independent [FULL DIFF review](full-diff-review.md): BLOCK, SR-D01 log-directory
ownership before mutation/removal; SR-D02 unused metadata is nonblocking.
Implementation and publication stopped pending owner-authorized correction.
Current git diff --check also reports one extra blank line at the end of
schema_registry.yml; this formatting issue remains uncorrected after the stop.

## SR-D01 reproduction — 2026-10-12

Owner authorized reproduction after asking whether the finding was hypothetical.
Current working-tree sources were transferred with qa-sync to
/var/tmp/platform-installer-qa-732f026e0c1f4722bbd502ddf1d6213f on node2.
[Reproduction harness](sr-d01-reproduction.py), SHA256
a6e449afc11348a296d24be0b33175eb657cdb162e54185b71d0d1429aa3069d.

The harness executes the complete unchanged production Registry preflight, the
exact directory-preparation task loaded from schema_registry_member.yml, and the
unchanged production schema_registry_clear.yml. Both fixture cases use temporary
config/log roots under that workspace, absent synthetic units and harmless files.
It does not exercise full Apply/Clear orchestration or service installation.

Both cases reproduced the defect:

| Case | Preflight | Directory preparation | Clear | Neighbor |
| --- | --- | --- | --- | --- |
| Config/unit absent | Accepted foreign logs | root/0755 became schema-registry/0700 | Foreign fixture file deleted | Preserved |
| Matching owned config marker, unit absent | Accepted foreign logs | root/0755 became schema-registry/0700 | Foreign fixture file deleted | Preserved |

Public results: [absent config](sr-d01-absent-config.json),
[owned config](sr-d01-owned-config.json). Final recap: ok=54 changed=14 failed=0.
Here PASS means the vulnerability was reproduced, not that ownership safety passed.
Two preliminary harness runs were inconclusive: vars_files precedence overrode
temporary roots, then the previous fixture's unmarked config correctly blocked.
The corrected final harness merged role defaults below fixture values and reset
only its two temporary fixture roots before execution.

Safe task output preserved locally at
.runtime/qa/schema-registry-20261012/sr-d01-probe-final.log. The new remote workspace
and fixtures were cleaned using qa-sync and absence was confirmed. Existing native
Registry QA deployment and its earlier workspaces were not changed. No secret
material was involved. Production code remains unchanged; SR-D01 remains OPEN.

## SR-D01 correction — 2026-10-12

Owner explicitly authorized correction. Shared schema_registry_ownership.yml
checks all directory ancestors without following symlinks and independently proves
config/log root markers (regular file, root-owned, mode 0644, exact SHA256).
Validation, member preparation and Clear all invoke the guard. New roots get
separate markers. Existing unmarked roots require an explicit owner-directed
cleanup/migration; production code does not silently adopt them.

Six production-task regression cases passed on current synchronized RED OS source:
foreign logs without config/unit, foreign logs with owned config and an inert owned
unit, wrong marker, marker symlink, log-root symlink, fresh owned preparation/clear.
Each negative also invokes Clear independently and checks unchanged uid/gid/mode
and file checksum. Neighbors survived all cases. Recap ok=217 changed=36 failed=0
rescued=10; rescues are the ten expected preflight/Clear refusals.
[Public results](sr-d01-correction-tests.json). Reusable generator:
services/kafka/tests/schema_registry_ownership_fixture.py.

Focused suites 16+25+33 PASS. Apply/Verify package syntax PASS; there is no package
clear.yml, so the attempted check of that nonexistent file is not a product failure.
Actual production Registry Clear tasks ran in the regression fixture. git diff
--check PASS after the extra trailing blank line was removed.

Full native run on fresh Registry roots /etc/schema-registry/sr-d01-fixed-native
and /var/log/schema-registry/sr-d01-fixed-native, using the existing isolated QA
Kafka deployment: Apply ok=166 changed=6 failed=0; Verify ok=150 changed=0 failed=0;
repeat ok=170 changed=0 failed=0. Original unmarked QA roots were retained without
adoption. Safe logs in remote workspace
/var/tmp/platform-installer-qa-54783671295443b79a3bccb92bc74e10:
sr-d01-native-apply.log, sr-d01-native-verify.log, sr-d01-native-repeat.log.
The safe logs were copied to .runtime/qa/schema-registry-20261012 locally.
The correction workspace and six temporary fixture roots were cleaned with
qa-sync; the inert unit and workspace absence were confirmed. The unused initial
source-only correction workspace was also cleaned. Existing native QA deployment
and prior PKI workspace remain retained for broader acceptance.

Independent [TARGETED_RECHECK](sr-d01-targeted-review.md) closed SR-D01;
APPROVE_WITH_CHANGES, zero blockers. SR-D02 remains nonblocking.

## Remaining acceptance after correction

Current-source bundle publication, multi-host,
colocated/split-role native cases, negative cases, clear, real React/Wails lifecycle
and QA cleanup remain open. The QA deployment and protected workspace are retained
for continuation. No complete service acceptance is claimed.

## React/Wails acceptance, 2026-10-12 (PASS, standalone scope)

Real React handlers use the Wails development bridge and real Go methods,
with the managed project folder chooser as the only substitution. This is
nonvisual service acceptance, not SI11 embedded WebView/native-dialog acceptance.

The UI exposed a metadata defect: the listener setting was UNSUPPORTED because
the generic bounded string editor requires both minimum and maximum lengths.
The manifest now specifies minLength=1 and maxLength=128. Core still validates
the selected broker listener. Catalog/schema regeneration on current RED OS
sources and the 16-case Schema Registry suite passed; qa-sync verification passed.

Standard importer/publisher produced bundle schema-registry-wails-20261012-30,
digest sha256:7d4a43976ca5c0d78d44655474e0dcc2e4d0ace569a14237baad2027f855de22,
catalog sha256:0821c2624196e04d9ccd28ee7ed4788152caf55f8b83afd20294f68779773db6.
The previous bundles were preserved through the standard publisher before
replacement. The project locks all eleven catalog definitions and the exact
published bundle. Execution Node preparation through React reached READY for
that digest. SSH trust, session credentials and PKCS#12 password were entered
through their actual UI controls; no secret values are recorded.

Project project-5343525741494c53, deployment qa-sr-wails, combined broker/controller
sr-wails-1 on node2: UI showed enabled=true and listener=SSL. HTTP/HTTPS ports
48881/48882 were saved through React. Saved revision:
sha256:0928ff13533bf6edb2a6ba5d6e5743c03839f085f91fa267976c5f445b2509c7.
Plan plan-74b0d1f5d2bc3c2d206b919d was EXECUTABLE with PKI_APPLY,
SERVICE_APPLY and SERVICE_VERIFY. React approval and Start returned STARTED:
installer-bbca900fd509baf2e0dba7f3204a4676. This run ended FAILED, sequence 1322,
in SERVICE_VERIFY. PKI_APPLY and SERVICE_APPLY completed successfully. Verify
failed at "Select delivered Kafka archive for offline installation": the
OFFLINE_BUNDLE condition accessed an absent Kafka requirement before the
verify-only guard could skip it. The guard is now evaluated first. An actual
Ansible regression on RED OS exercised both verify-only and Registry-only phases
with an empty artifact mapping: skipped=2, changed=0, failed=0.

The installed instance independently passed HTTP schema registration and HTTPS
retrieval with its CA chain and certificate validation enabled (schema id 1).
The failed terminal run is retained as failure evidence, not counted as acceptance.
The final replacement bundle is schema-registry-wails-20261012-31,
digest sha256:f0d9b5a4f8a6c563c1e198c8b80bf5e5b20f51e1bd0f15daf93f369ca26b3408.
It was verified and published through the standard importer/publisher into the
active cache; the preceding bundle was preserved through the same publisher.
The catalog digest is unchanged from bundle -30. Real React node preparation
reached READY for the exact final digest. The final saved project revision is
sha256:7dfaf161fd46f4201ab3c32a60e36441038a81971863aea1f6bf3d53877506cf.

Both complete React Plan → Approve → Start → Result cycles passed:

| Cycle | Plan | Run | Terminal | Sequence |
|---|---|---|---|---|
| Corrected complete cycle | plan-7aa4f2a76ef8de6d3302ce23 | installer-c7df766deadf5e431d4ed188738cc422 | SUCCEEDED | 1576 |
| Fresh-plan control repeat | plan-7aa4f2a76ef8de6d3302ce23 | installer-a7a152ab6a3f11d6110aa7adcfb29d9a | SUCCEEDED | 1576 |

The plan ID is deterministic for these identical inputs; the second cycle
explicitly invoked fresh planning and separate React approval/Start, rather than
reusing Start authorization. Both journals have identical completed task counts:
PKI 93 SUCCESS / 31 SKIPPED; Apply 346 SUCCESS / 63 SKIPPED;
Verify 197 SUCCESS / 53 SKIPPED. No CHANGED or FAILED task event exists in
either successful run: PKI, Apply and Verify each have changed=0. All three
actions completed SUCCESS and the real GetInstallationRun returned SUCCEEDED.

Safe evidence: [flow](wails-acceptance-result.json),
[first journal summary](wails-success-1-events.json),
[repeat journal summary](wails-success-2-events.json),
[REST check](wails-rest-result.json). REST registration/retrieval passed again
after both successful cycles, with certificate verification enabled. Catalog and
configuration schema --check and the 16-case focused suite passed on RED OS.

The Result tab was invoked through React in both cycles. The legacy text-count
probe searched "Выполнение завершено", whereas the current component uses
"Успешно завершено"; its visible=0 is not visual evidence or a terminal failure.
Terminal evidence comes from real Wails methods and authoritative journal events.
Visual inspection remains NOT PERFORMED. One existing /wails/ipc.js bootstrap
warning was observed; no other page error occurred. This is nonvisual standalone
acceptance only; split-role/multi-host/colocated cases and broader Clear gates
remain open. QA deployments and protected run/PKI state are retained for that
continuation. Temporary source/regression workspace
/var/tmp/platform-installer-qa-12e59935984c430c8449d75d7418f689 was cleaned with
qa-sync and absence was confirmed. The owned Wails/dev application and Vite
processes were stopped after exact image/script identity checks. git diff --check
passed. Unrelated working-tree changes were preserved; no commit was made.

Automation selector corrections for the current certificate dialog and approval
footer were harness corrections; they did not change production UI or bypass
approval. The listener metadata defect was a production manifest correction.
