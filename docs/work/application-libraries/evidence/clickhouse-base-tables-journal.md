# ClickHouse library base tables — implementation evidence

Date: 2026-10-17. Base master 08a8395e. Core/UI plan-only acceptance PASS;
server table creation/HA/repeat acceptance not performed. Owner disposition: CHBT-D01 not applicable
to database-wide grants; CHBT-D02 explicitly rejected. Original FULL DIFF BLOCK
is retained in the review report alongside this disposition; no code correction.
See ../reviews/clickhouse-base-tables-diff-review.md.

## Implemented scope

File-only resource_defaults in library package and library deployment group_vars;
standard Ansible recursive merge/list replacement and DDL template; ordered SDKU
records/alarm_message specs; target-free engines and isolated Keeper paths per
selected deployment/database/table; existing protected provider create/verify;
raw Go transport only, no table structure controls in UI. No new production Python
file, ownership store, migration/ALTER/DROP path or lock.

## Executed checks

Current-tree sources transferred with scripts/qa-sync.ps1 to RED OS node2.
Last source workspace /var/tmp/platform-installer-qa-ef6da46f1a2c416dab495a094ce5fc44.
Last two test-only edits copied into that workspace before focused final runs.

- Core application libraries unit suite: 20 PASS.
- Provider projection suite: 18 PASS (final 0.016s), including physical schema conflict.
- Existing ClickHouse test file, ONLY two new fake-client metadata/retry tests: 2 PASS.
  Full native service test file deliberately not run because it creates tables.
- Real Ansible defaults merge/reset and Jinja four-DDL rendering, native
  clickhouse format parsing, SELECT-only clickhouse local normalization/settings:
  1 PASS (final 26.018s). No server connection or table DDL execution.
- go test ./... PASS; go vet ./... PASS. Final affected adapter/installer rerun PASS.
- Frontend 23 files / 256 tests PASS; build, lint and bindings generation PASS.
- Real React/Wails/Core Save/reopen/Verify/Build: PASS, five cases. Two existing-mode databases selected through Resources UI; file-only override retained through UI Save; schema absent from UI; standalone/Replicated tables resolved independently; external file change updates Core and plan identity. No visual PASS claimed.

Ignored local logs: .runtime/clickhouse-tables-{provider-final,native-final,
go-all,go-final,go-vet-final,ui-all,ui-build,ui-lint,wails}.log.
UI evidence/progress: .runtime/qa/application-design/clickhouse-tables-*.json.

## Runtime preparation and non-execution

Standard builder/validator/publisher produced runtime12:
artifact sha256:53bcc9ad40da856b8d792bb7360046fbdda3c481b488417a534b9a69e26b9227;
catalog sha256:6b87cd3eb49b1229ebfd21dd1e24c71e100d7dc5b38f790046762a52f773c28a.
Verified existing artifacts reused, no acquisition/download. Local candidate
.runtime/qa/clickhouse-tables-bundle12 retained. Standard qa-runtime-promote prepared
the runtime on node1 and updated the isolated QA fixture locks; resumed checkpoint
reported PreparationChanged=false. Initial lock update failed because the temporary
fixture's catalogLock followed artifactLock; canonical fixture order fixed, no
production lock-update change. Temporary runtime secret reference corrected to
catalog-declared reference; no secret value was written.

No application installation/start, Approve/Start execution, server CREATE/ALTER/DROP,
account/grant mutations or HA table acceptance performed. Remaining native acceptance
requires separate owner authorization. Owner dispositions are recorded in the review report; no D01/D02 code change.
QA cleanup status follows below.

Cleanup: all four owned qa-sync workspaces removed with the standard helper.
Root-owned /dev/shm input12/bundle12 staging removed with sudo -n after exact
canonical path and non-symlink checks; absence confirmed. Local ignored evidence,
QA fixture/runtime candidates and prepared Execution Node runtime retained.

## Completed real React/Wails/Core acceptance

2026-10-17 owner authorized continuation of Core/UI verification only. No production
source changed during this QA. Real bindings and React handlers used; existing
chooser-only seam selects the isolated project. Node1 READY on runtime12.

- File override 4096: plan-7d9b42b14f76062ec3680019, EXECUTABLE; revision sha256:2a2586e9a761b8e66edc8b28591a093640d208b5771f8cf7124d64b567246d55; fingerprint sha256:7d9b42b14f76062ec3680019ee3f2d11d55f82941e9e0ddfbb3ae72397568bde. Execution mode APPLICATION_LIBRARIES_ONLY; explicit Infra Verify skip true; approved false.
- External file override 2048: plan-6df79be144cb81fe7f65efa0, EXECUTABLE; revision sha256:512502bb1484f82524b0b0e3129a1e0a067c0b0d8943a6a818b64a92ae36bc12; fingerprint sha256:6df79be144cb81fe7f65efa07235b77d3a5bdd9967f5845d5ba205e43a0dafd5. Execution mode APPLICATION_LIBRARIES_ONLY; explicit Infra Verify skip true; approved false.

Both plans are unapproved and unstarted. Explicit Infra Verify skip is a plan-only
QA selection, not evidence of installed infrastructure health. Both selected DBs
are mode=existing; both tables are projected without account references.

The first Verify returned RUNTIME_SECRET_REQUIREMENT_DUPLICATE when two QA
deployments explicitly declared the same service runtime-secret requirement.
For this library-only planning fixture, the second declaration was omitted. Its
admin credential remains unconfigured for execution; this project is not certified
for infrastructure/service Apply. No Core guard was changed or bypassed. The
multiple-deployment credential limitation is outside the table-schema scope.

The earlier selector failure was in QA automation: nested label/select option text
prevented an exact-label match. The existing form controls were selected directly;
no product/UI code changed. Independent review disposition remains owner-accepted
D01 non-applicability and D02 rejection, not an independent APPROVE.

Reset acceptance: actual file override subtree removed, Core Verify VERIFIED, both
selected databases restore records.settings.index_granularity=8192 from the package.
Fresh plan plan-2cd96ffcf3bd06e2a6e79c4e, EXECUTABLE; revision sha256:3d80e0d373d14f87dc3e6d149b8ac7517f577a326fd01a967f64e4c2bed1a48a;
fingerprint sha256:2cd96ffcf3bd06e2a6e79c4ef35e1ecac4c4d2a4cfd2d9cdeafc840ce0b026cc; approved false, unstarted.
Supplemental evidence .runtime/qa/application-design/clickhouse-tables-reset-wails.json.
Seven cases PASS in total. No application or server table mutation occurred.

Final QA cleanup: runtime credential session cleared and isolated project closed
through existing Wails methods. No new remote source workspace or bundle staging
was created during this continuation. Persistent QA identity and local evidence retained.
