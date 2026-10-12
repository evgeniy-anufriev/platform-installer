# Current state

Updated 2026-10-11. This file is the sole current milestone/status source.
Detailed historical checkpoints are archived under [docs/history](docs/history/si11-state-20261008.md).
Read the applicable plan and evidence for the task; an implementation or direct
Ansible PASS does not imply complete UI acceptance. A next gated milestone or
new destructive operation still requires explicit owner authorization.

## Active work and acceptance

| Work | Current status | Evidence and next step |
| --- | --- | --- |
| PROJECT-RESOURCE-SETTINGS-01 | IN PROGRESS; path preview and shared-root ownership correction implemented; focused RED OS ownership test passed; bundle -24 built/published and placed in full-services; UI rebind pending | [Plan](docs/work/project-lifecycle/project-global-path-and-prefix-plan.md), ADR-037. Owner chose service-only data root, portable project settings, empty service-name prefix by default and underscore-capable prefix. Installer PKI paths stay fixed. FULL DIFF review: APPROVE_WITH_CHANGES, zero blockers. Earlier RED OS project copy with `/srv/service-data` and `qa` passed Validate, ProjectSnapshot and target-free DeploymentPlan (`EXECUTABLE`, all `changed=0`); five focused suites (67 test executions), catalog reproducibility, App.test.tsx (72), frontend typecheck/lint, `go test ./...`, `go vet ./...` and Wails production build passed. Owner's UI confirmed `/data` is saved and Core preview runs. Core preview accepts Ansible mapping proxies; focused RED OS regression passed (8/8). Ownership correction is in the existing `managed_data_path_guard` role: Apply reconciles only a non-default shared data root to the SSH technical user (`ansible_user`), mode 0755; Verify checks it without mutation; service data children remain service-owned and default `/var/lib` stays root-owned. Focused RED OS playbook passed (28 ok, 0 failed). Bundle `si11-full-service-20261011-24` now includes the correction; its project import and active cache both validate as `sha256:dc34385210433e309578575e31e3a7a2093682dda7277e64c235a4f5beda8ee9`. Project lock unchanged; UI rebind/preparation and real installation acceptance remain pending. |
| APPLICATION-LIBRARIES-A5 | Current A5 scope implemented; initial FULL DIFF BLOCK resolved by owner-approved TARGETED_RECHECK APPROVE; A5-C01 closed by owner risk acceptance | [Plan](docs/work/application-libraries/milestones/a5/a5-technical-plan.md), [review](docs/work/application-libraries/milestones/a5/reviews/a5-diff-review.md), [journal](docs/work/application-libraries/milestones/a5/evidence/a5-test-journal.md). Redis/Sentinel TLS hooks and infrastructure account preservation PASS; ClickHouse standalone and three-server ON CLUSTER account/grant repeat/Verify PASS. Shared credential root/files remove PostgreSQL coupling, with legacy Core input compatibility; 67 application and 12 Vault tests PASS. Full A4 regression PASS after existing-Vault-source Verify correction. A5 common entrypoint/container Apply/Verify/repeat PASS, including Redis/Sentinel, ClickHouse and Kafka SSL ApiVersions without authentication; updated QA image built on RED OS rootless Docker. Core regression: 534 PASS/19 skip (553 tests, 16 unchanged native PKI recovery cases excluded). Final ClickHouse concurrent-repeat/witness checks PASS. Owner accepted late queued-DDL/retry overlap risk and excludes pending markers/task correlation/special retry gates; historical PLAN BLOCK remains, not reviewer APPROVE. C02 queue verifier hygiene is nonblocking. Owner-authorized D01/D02 native tests and targeted review APPROVE: Redis member failure/retry, ClickHouse HA fail-closed/retry, two-library/two-host projection with account preservation. D03 documented/tested. A5 current-scope implementation, RED OS QA and review are complete; C02 production Keeper queue policy proof remains nonblocking. Merged into master from codex/application-libraries; Go/UI remain out of scope. |
| APPLICATION-LIBRARIES-A4 | COMPLETE: standalone A4 accepted by owner; Go/UI remain out of scope | [Plan](docs/work/application-libraries/milestones/a4/a4-technical-plan.md), [journal](docs/work/application-libraries/milestones/a4/evidence/a4-test-journal.md). Two-host RED OS fixture passed HTTPS/443 endpoint routing, multi-host placement, AppRole renewal/restart and scope/CIDR. Latest native fixture passed live KV CAS retry with neighbor preservation, missing-field/unsafe-path fail-closed, Apply/Verify/repeat and standalone token/bootstrap; Vault provider tests 12 PASS and Apply syntax-check PASS. Owner confirms automatic Vault Agent AppRole reauthentication after `maxTTL` expiration was personally verified and works, closing A4-D01. Independent targeted-recheck BLOCK is retained as the reviewer’s finding on its evidence snapshot; closure is by owner acceptance, not a reviewer PASS. No Go/UI implementation, commit or master sync authorization. |
| APPLICATION-LIBRARIES-LIGHT-VERIFY | Owner-authorized implementation; focused standalone QA PASS | [Journal](docs/work/application-libraries/milestones/lightweight-verify/evidence/lightweight-verify-test-journal.md). One inspect task per instance: image ID, ownership, Running/configured healthcheck. Standalone skips target/source preflight; Apply retains full preflight. Independent FULL DIFF APPROVE_WITH_CHANGES, zero blockers; documentation corrected, negative identity coverage remains nonblocking. Two-container Apply/Verify/repeat and real healthy/unhealthy PASS; six supplementary predicate cases PASS. QA-found unhealthy condition corrected after review; no repeat review claimed. Remote QA cleaned. |
| APPLICATION-LIBRARIES-A1-A2-SPEED | COMPLETE: bounded standalone optimization PASS; FULL DIFF APPROVE_WITH_CHANGES, zero blockers | [Review](docs/work/application-libraries/milestones/a1-a2-speed/reviews/a1-a2-speed-review.md), [journal](docs/work/application-libraries/milestones/a1-a2-speed/evidence/a1-a2-speed-test-journal.md). Unit105, offline36 subset, standalone A1 14, native discovery isolation1 and six real runtime cases PASS; syntax and cleanup PASS. Sequential two-container Apply/Verify/repeat benchmark 305.317s → 263.973s (~13.5% in one measurement); clean repeat changed=0/IDs preserved. SPEED-D01 coverage added and passed. No native 10/30-container timing, A3 implementation, bundle or Go/UI acceptance claimed. |
| APPLICATION-LIBRARIES-A3 | Standalone implementation and focused acceptance PASS; TARGETED_RECHECK APPROVE, zero blockers | [Plan](docs/work/application-libraries/milestones/a3/a3-technical-plan.md), [PLAN review](docs/work/application-libraries/milestones/a3/reviews/a3-plan-review.md), [DIFF review](docs/work/application-libraries/milestones/a3/reviews/a3-diff-review.md). A3-D01/D02 RESOLVED by owner-approved TARGETED_RECHECK; full standalone and native primary/standby functional PASS. Owner-approved additive explicit grants; resource batch per library, account batch per instance; benchmark cancelled. Implementation is maintained on codex/application-libraries. Isolated RED OS only; no Vault/Go/UI/master authorization. D01–D04 corrections implemented. [QA journal](docs/work/application-libraries/milestones/a3/evidence/a3-test-journal.md): 528 Core cases (509 PASS/19 skip), 16 unchanged native PKI recovery cases excluded; native full entrypoint, account login and writable primary/standby PASS. All A3 source copies cleaned; no second FULL review. |
| APPLICATION-LIBRARIES-A2 | COMPLETE: standalone baseline PASS; no Go/UI acceptance implied | [Plan](docs/work/application-libraries/milestones/a2/a2-technical-plan.md), [DIFF review](docs/work/application-libraries/milestones/a2/reviews/a2-diff-review.md), [journal](docs/work/application-libraries/milestones/a2/evidence/a2-test-journal.md). D01/D02 resolved by owner-approved TARGETED_RECHECK: APPROVE_WITH_CHANGES, zero blockers; D03/D04 nonblocking limits remain. Focused/offline 32 PASS; six real public-image runtime cases PASS across node1/node2, including distinct images and healthcheck. Broad regression plus five PKI timeout-repair cases PASS; test-only limit 600s, production PKI unchanged. Cleanup verified. No A3, release publication or Go/UI authorization. |
| APPLICATION-LIBRARIES-A1 | DONE for standalone contracts/read-only resolution; acceptance PASS on 2026-10-10 | Implementation branch codex/application-libraries. Independent recheck closed A1-D01–03; A1-D04 corrected and tested. RED OS: 15 focused + 14 standalone PASS. Core broad run: 517 cases, 19 root/isolated-acceptance skips; six PKI timeout errors and one stale Redis fixture failure corrected in tests, all seven failed cases then PASS. Combined regression evidence: 498 passed/19 skipped; original FAILED run retained, no claim of a second full run. QA copies verified and cleaned. See [review](docs/work/application-libraries/milestones/a1/reviews/a1-diff-review.md), [journal](docs/work/application-libraries/milestones/a1/evidence/a1-test-journal.md) for exact source identity and execution prerequisites. A1 review budget consumed; A2 separately authorized, Go/UI not authorized. |
| SERVICE-INSTALL-11 | IN PROGRESS; overall acceptance remains open | I05 PASSED by explicit owner confirmation on 2026-10-08. Close remaining cases and strict repeat evidence separately; see [journal](docs/work/service-install-11/evidence/service-install-11-test-journal.md). |
| ENDPOINT-HAPROXY-PLACEMENT-01 | Source implemented; FULL DIFF APPROVE; focused/standalone QA PASS, real acceptance pending | Owner approved narrow binding replacement and package backend defaults on 2026-10-09. Full Core 497-case run had one stale test assertion; corrected five-consumer test passed isolated recheck. Existing backend publication/reconcile reused; no new target store or transaction guarantee. Partial move/delete cannot discover former excluded hosts; explicit full reconcile remains necessary. See [plan](docs/work/endpoint-placement/endpoint-haproxy-placement-plan.md), [review](docs/work/endpoint-placement/reviews/endpoint-haproxy-placement-plan-review.md), [journal](docs/work/service-install-11/evidence/service-install-11-test-journal.md), ADR-033. No bundle release or real installation acceptance yet. |
| SERVER-INFORMATION-CHECK-01 | Implemented; real informational flow and targeted review passed | [Plan](docs/work/server-information/server-information-check-plan.md). One explicit SSH key confirmation supplies information and installation trust. Real React/Wails target and Execution Node checks, cancellation and changed-credential rejection passed; no installation started. |
| EXECUTION-NODE-PASSWORD-AUTH-01 | Implemented; targeted review APPROVE, sudo UI checks owner-confirmed | [Plan](docs/work/execution-node-password-auth/execution-node-password-auth-plan.md). Real React/Wails password checks passed for target node2 and Exec node1. Password hold survives lease expiry only for the exact active Start/run. Real Windows/RED OS password SCP passed; staging/cleanup and scoped sudo corrections reviewed. Owner confirmed the sudo correction works. Owner-confirmed correct/wrong/empty sudo cases accepted by independent EP-S04 recheck; zero remaining blockers. Full installation/Start with password remains separate. |
| PROJECT-VERIFY-PASSWORD-FIX-01 | Implemented; owner confirms Verify completes, FULL DIFF APPROVE | [Plan](docs/work/project-lifecycle/project-verification-password-fix-plan.md). Password archive transfer no longer requires PEM; ordinary Verify uses a private temporary directory. Transfer failures show unavailable with their own reason. Go checks and 64 App tests/build/lint pass; exact owner terminal status/revision not supplied. |
| PROJECT-SAVE-NODE-READINESS-FIX-01 | Implemented; FULL DIFF APPROVE_WITH_CHANGES, owner UI repeat pending | [Journal](docs/work/service-install-11/evidence/service-install-11-test-journal.md). Saving placement retains prepared node only for unchanged project/selected SSH endpoint/runtime bundle/catalog. Verification and installation approval still become stale. Go tests/vet pass; credential/pin guards unchanged. No blocking findings; actual Commit/Verify and expired-credential acceptance remain open. |
| PROJECT-EXPORT-SIBLING-FIX-01 | Implemented; FULL DIFF APPROVE, UI repeat pending | [Journal](docs/work/service-install-11/evidence/service-install-11-test-journal.md). Export overlap guard checks final destination rather than its parent; sibling export passes, same-root/nested destinations remain blocked. Go tests/vet and packaged export-fix build pass; zero review findings. |
| PROJECT-EXPORT-DISPLAY-NAME-01 | Implemented; FULL DIFF APPROVE, real UI repeat pending | [Plan](docs/work/project-lifecycle/project-export-display-name-plan.md). Export name updates only copied project.yml metadata.name; source and project ID remain unchanged. Original source revision and output digests/sizes are separate. Go checks and 65 App tests/build/lint pass; packaged export-name EXE rebuilt. No blocking findings. |
| SERVICE-UNIT-NAMING-01 | Implementation and focused QA complete; real naming acceptance pending | [Plan](docs/work/service-unit-naming/service-unit-naming-plan.md). Requires separately approved S11-00 baseline and real full-service UI naming checks. Prior I05 success does not prove new names. |
| SESSION-RUN-CREDENTIAL-01 | Implemented; real expiry-boundary acceptance pending | [Plan](docs/work/execution/session-active-run-credential-plan.md). Go tests/vet passed; exercise the real React/Wails flow at the lease-expiry boundary. Owner declined another review. |
| EXECUTION-ORDER-01 | Implemented with focused standalone evidence; remaining acceptance pending | [Plan](docs/work/execution-order/execution-order-01-plan.md), ADR-030. Keep source/provider dependency fail-closed; close interruption/recovery, stale-record deletion and real UI gaps. |
| SERVICE-INSTALL-09 ClickHouse | PARTIAL ACCEPTANCE, NOT DONE | [Plan](docs/work/clickhouse/service-install-09-clickhouse-architecture.md). Direct 1/1, 3/1, 3/3 and endpoint evidence passed; formal terminal real-bridge PASS and strict repeat remain unclosed. Owner previously declined another cumulative SI09 run. |
| EXEC-PLAN-SCOPE-01 | NOT STARTED / deferred by owner | [Acceptance sequence](docs/work/services/service-install-acceptance.md), [roadmap](docs/roadmap.md). Separate request required; current full plans are not selective provider reconcile. |
| BROWSER-REMOTE-01/02 | HTTP restricted to explicit dev; HTTPS deferred to version 1.0 | [Remote plan](docs/work/browser/browser-mode-remote-plan.md), ADR-028. Production transport/credential acceptance is not complete. |

## SI11 current evidence and open cases

I05 is **PASSED**. The owner explicitly confirmed this in the current chat on
2026-10-08; the journal also records successful full-plan completion observed
in the UI. The successful run ID was not supplied in that confirmation.
Do not attach an older failed run ID to the success or downgrade I05 because
of an earlier failure. This confirmation does not mark overall SI11 DONE.

The current journal records:

- I01 and I04: PASSED.
- I05: PASSED by owner confirmation; exact successful run identity remains
  an evidence detail to correlate when available, not a reason to reverse PASS.
- I07: PASSED by explicit owner confirmation on 2026-10-10 after bundle -17.
  The earlier repeat with Redis/PostgreSQL `changed` remains historical failure
  evidence in the journal; the successful run ID and exact recap were not
  supplied with the confirmation.
- H06/H07 and S06: IN PROGRESS.
- I02: PASSED by owner confirmation on 2026-10-09.
- S04: PASSED by owner confirmation on 2026-10-09.
- I03: PASSED by owner confirmation on 2026-10-09; exact run/terminal and
  cleanup details were not supplied. This does not authorize another reset.
- L01: FAILED; catalog labels for Keepalived, Kafka and Vault still contain
  English, and remaining screens have incomplete coverage. Translate service
  manifest metadata and regenerate catalog/bundle; do not hardcode service
  translations in React.
- I05-R1 retains its historical Redis failure. The later owner-confirmed
  successful full plan is recorded in I05; do not replace either evidence.

The [UI test cases](docs/work/service-install-11/service-install-11-ui-test-cases.md) and
[test journal](docs/work/service-install-11/evidence/service-install-11-test-journal.md) define detailed coverage.
The journal is evidence, not permission to perform a new run or reset.
S11-00 cleanup was repeated on 2026-10-11, then the `full-services` project was
installed again. On the latest target audit, only Redis/Sentinel deployment
`qa-redis` was removed from node1/node2/node3 at the owner's request; its data,
service configs/ACLs and per-member TLS copies, logs, custom units, Redis RPM,
and dedicated Redis user/group/home were deleted. Shared PKI and other services
were retained. See the historical
[cleanup record](docs/work/service-install-11/service-install-11-cleanup.md) for S11-00; the latest
bundle and target state are recorded below. This targeted removal does not close
SI11 or authorize another installation run.

## SI11 source corrections and recorded runtime checkpoint

PostgreSQL automatic subnet HBA (2026-10-09), delivered in bundle -14: owner requested
hostssl all all with SCRAM for the current subnet, then automatic subnet
selection. Role derives network/prefix from observed interface IPv4 matching
the configured local PostgreSQL address; missing/ambiguous facts fail before
mutation. Specific HA rules stay first. RED OS 28 tests and syntax PASS;
live node2 facts resolve192.168.56.0/24 independently of default-route subnet.
FULL DIFF review APPROVE, CURRENT; real client acceptance pending.

Redis/Sentinel default-user ACL (2026-10-09), delivered in bundle -14: owner accepted
native password hashes, no extra encryption. Separate redis.users.acl and
sentinel.users.acl beside member configs, service owner/0600/UMask0077;
Apply ACL SAVE, read-only Verify, retained replication/Sentinel state preserved.
RED OS 14 tests PASS including native Redis/Sentinel8.6.4 repeat/negative fixtures;
Apply/Verify syntax PASS; FULL DIFF review APPROVE, zero findings. Bundle
validated/published as -14; real Wails installation acceptance pending; evidence in SI11 journal.

Redis Sentinel peer-authentication correction (2026-10-10), delivered in bundle -16:
the reported Verify failed because Sentinel ACLs require a password, but
sentinel.conf lacked sentinel sentinel-user/pass for Sentinel-to-Sentinel
connections. All three Sentinel services and TLS listeners were active and
mutual TLS handshakes passed; all nodes marked peers down. New and retained
configs now set the existing default ACL user and Sentinel runtime password;
password-bearing tasks use no_log and changed config restarts Sentinel.
RED OS Redis suite 15 tests PASS; Apply/Verify syntax PASS. Bundle -16 is
validated/published and matches the project import; real Apply/Verify
acceptance remains pending. Evidence: [SI11 journal](docs/work/service-install-11/evidence/service-install-11-test-journal.md).

Vault AppRole addition (2026-10-09), delivered in bundle -13: owner requested enabling
AppRole at approle/. Configure enables only absent mount, rejects a conflicting
method before writes and preserves existing settings; Verify requires AppRole.
No roles/policies/IDs created. RED OS 32 tests PASS, six unrelated legacy
cleanup fixtures skipped (root prerequisite); syntax checks PASS;
independent FULL DIFF review APPROVE, zero findings. Bundle
validated/published as -13; real Wails installation acceptance pending. Evidence in SI11 journal.

PostgreSQL repeat-install ownership correction (2026-10-09), delivered in bundle -12:
run `installer-b1b4a757c8898fcac402b71b5bed6662` FAILED on node1 because the
guard expected the managed marker on the first line while the existing role
template places it after `[Unit]`. Exact full-line ownership matching now
accepts the template without accepting another deployment/member. RED OS
26 tests PASS, including seven production-task ownership scenarios;
independent FULL DIFF review APPROVE, zero findings. Bundle
-11 predates this fix; -12 validated/published, real repeat acceptance pending.
Evidence: [SI11 journal](docs/work/service-install-11/evidence/service-install-11-test-journal.md).

Service runtime optimization (2026-10-09), delivered in bundle -11: source gates limited to
mutation preparation, batched BIND packages/ClickHouse RPM/Kafka systemd reads,
unused stat MIME/attributes/checksums disabled. Redis/Sentinel absent-unit
ownership bug fixed; exact foreign-file rejection retained. RED OS 20 syntax
checks, 131 service tests and five optimization tests PASS; final independent
DIFF review APPROVE (45-file security scope, zero blockers). [Analysis and evidence](docs/work/services/service-runtime-optimization.md).
Observed run `installer-7d4d76d9fa1972a4e74b30e68c2fe38e` FAILED at Redis apply;
nine prior services completed Apply/Verify. Redis verify was not reached.

PKI inspection optimization (2026-10-09), delivered in bundle -11: batch target metadata
and SHA256 checks while retaining ownership, modes, fingerprint and repair.
RED OS focused repeat/repair test PASS (corrupt, missing, mode, fingerprint);
independent FULL DIFF review APPROVE, zero blockers. Bundle -10 predates this
optimization; bundle -11 includes it. Real installation timing remains unmeasured. Evidence in SI11 journal.

Terminal subscription channel-drain correction (2026-10-09), source-only:
observed run `installer-c2fba5c0b70a16540cf1f305fdf915fb` SUCCEEDED,
Redis verify completed in remote events 10363–10365 while UI stopped at 10362.
Go forwarding now drains both closed buffered channels before ending;
context cancellation stays immediate. Focused installation/observer tests PASS;
independent FULL DIFF review APPROVE, zero findings;
desktop rebuild and real Wails replay acceptance pending. Evidence in SI11 journal.

Vault/HAProxy hook and terminal-event correction (2026-10-09): partial backend
integration reuses installed HAProxy without provider package acquisition under
source-service authority; PKI selects local provider identity. UI drains/replays
events through terminal sequence before unsubscribe. RED OS 3 regressions and
App 68 tests/typecheck/lint PASS; independent FULL DIFF review has zero blockers,
its requested race test added. Delivered in bundle -10 below; real retry
and Wails replay acceptance pending. Evidence in SI11 journal.

Kafka fresh-install ownership correction (2026-10-09) is source-only: skip
ownership assertions for slurp results explicitly marked skipped because the
unit file does not exist. Existing files still require the exact ownership
header. Production-task RED OS regression passed missing/owned/foreign cases;
released in bundle -09 below; real installation retry remains pending. See the journal.

Kafka normalization correction (2026-10-09) is source-only: separate fact
dependencies for runtime directory/environment path and compatibility/legacy
unit name. Real localhost Ansible normalization of four sequential members
and 21 Kafka contract tests passed on RED OS node2. Bundle -08 is released below; UI rebind/preparation and
real installation retry are pending; see the journal.

BIND dynamic A-record parsing correction (2026-10-09) is implemented in
source only. DNS comments containing `NXDOMAIN` are excluded before and
after updates; CNAME/foreign-owner rejection remains. Four production-task
Ansible regressions and 15 BIND contract tests passed on RED OS node2.
Bundle `si11-full-service-20261009-07` released below; UI rebind/preparation
and real Vault retry remain pending; see the journal.

Latest delivered project bundle: `si11-full-service-20261011-25`, built on
node2 from the current source, validated and published with digest
`sha256:0f84e55b0ba7f8e26609991f8ee2fb5672de3fea07d5ca52ed84ddecaf2c22c7`.
Its runtime contains the one-run raw Ansible failure-output marker for project
`project-b46aa3f5f57a495f`; captured diagnostics remain protected on the
Execution Node and must not be printed or copied into project files. The bundle
is in `.runtime/qa/full-services/bundle`; previous -24 is preserved at
`.runtime/qa/full-services/bundle.previous-20261011-before-25`. Project lock
is unchanged, so normal UI rebind and node preparation are required before a
dependent project flow. The Redis failure evidence supplied by the owner shows
`WRONGPASS` on node2 while authenticating to the master; no password value was
recorded. Redis has since been removed from all three targets. No new install
plan was started.

Previous project bundle: `si11-full-service-20261011-21`, built on node2 and
validated at `.runtime/qa/full-services/bundle` at the time, digest
`sha256:a24029d8a65fbc8327c1eae776bbea841235b6dbe122922f7aec9b6600418ec2`.
It includes the prior -15 changes plus Redis Sentinel peer authentication.
Version -09 also
includes endpoint-derived HAProxy placement/defaults and Kafka skipped ownership
handling. Version -10 includes partial HAProxy package/PКI-context correction
and persistent Docker shell environment. Version -11 includes HAProxy/PKI and
service runtime optimization plus Redis/Sentinel absent-unit ownership fix.
Version -12 also fixes PostgreSQL existing-unit ownership line matching.
Version -13 enables and verifies Vault AppRole without changing existing mounts.
Version -14 adds Redis/Sentinel default-user ACL files and automatic PostgreSQL
client-subnet TLS/SCRAM access. Version -15 adds ClickHouse
`remote_servers.default` configuration. Version -16 adds Sentinel peer
authentication using the existing default ACL user and runtime secret. Version
-17 fixes Redis/PostgreSQL repeat idempotence. Version -18 exposes safe absolute
data paths for Kafka, Redis, ClickHouse and PostgreSQL. Version -21 adds data
directory preview metadata and catalog/fixture-lock updates for Kafka, Redis,
ClickHouse, PostgreSQL and Vault.
Published with the standard publisher into `cache/`; project import
digest matched at the time. Previous -20 is preserved at
`.runtime/qa/full-services/bundle.previous-20261011-20`. Project lock unchanged;
its catalog digest still references the prior bundle, so use the normal UI
rebind before dependent project flows.
Target-free plan replay
on the failed staged project returned EXECUTABLE; real UI rebind/plan/Start
for this bundle is pending. See the journal; no installation was started.

Historical run `installer-90f2d8f56b6b4cf447c630d04bc56fd6` failed during Vault
endpoint integration at events 2922–2926 after earlier service actions passed.
The source used `(record_matches | first).values`, selecting a mapping method;
it now uses `(record_matches | first)['values']`. The production-task test
proves list/address types. Six endpoint, eight HAProxy and 15 BIND tests and
endpoint playbook syntax passed on RED OS. This historical failed run is not
the owner-confirmed successful I05 run.

HAProxy hook phases use the resolved source ID, including standalone inputs.
At that diagnostic checkpoint, `qa-vault-consumer` had no
`haproxy.deploymentRef`, so Core selected no provider and skipped that hook.
Review the current saved relation before claiming external Vault routing.

The last runtime checkpoint recorded in the former state file was bundle
`si11-full-service-20261008-03`, built on node2 and validated/published with
digest `sha256:e77842ff140d641ea80c4b131bb87a0b042e1c4c1985d3dd87fa7b3968e4d99f`.
The former project import and prior active digest were preserved as QA copies.
The project lock was observed changed without an identified rebind actor.
These are recorded checkpoints, **not a live cache/READY assertion**: confirm
the current project, published digest and selected-node preparation before
any newly authorized plan. I05 success does not identify its runtime digest.

After that historical failed run, owner-authorized Vault clear removed owned
member data on node1–node3 while preserving ownership markers, config, PKI
and audit directories. Old bootstrap shares/token became obsolete and must
not be reused. Read the [SI11 history](docs/history/si11-state-20261008.md)
for exact reset evidence; do not infer present target state from that reset.

Earlier controller-preparation failure diagnostics now expose only sanitized
tokens. The lifecycle suite passed 59 tests and independent DIFF approved;
see [diagnostics](docs/guides/execution-failure-diagnostics.md). Redis quoted-path
comparison, ClickHouse stock-unit and Keepalived participant corrections have
focused evidence in the SI11 archive; no new product QA was run for this
documentation reorganization.

## Execution ordering and active-run credential boundaries

EXECUTION-ORDER-01 implements the application priority list, ordered
BuildDeploymentPlan input and Core per-deployment Apply/Verify projection.
Recorded regression: RED OS Core 487 tests (19 skipped), Go test/vet,
frontend typecheck/lint/build and 128 tests passed.

ADR-030: ordinary BIND Apply preserves the existing zone and updates only
base-owned A records; source point updates do not delete records. Explicit
full reconcile is the sole deletion path and uses live SOA serial plus a
machine-runtime freeze/thaw recovery marker. Focused BIND tests (17/17),
node1/node2 Apply/Verify/reconcile and final repeat `changed=0` passed.
Injected interruption/recovery, stale-record deletion and complete source-hook
failure boundaries remain unproven. The earlier checkpoint prohibits a new
service plan under this ordering until those gates close; owner-confirmed
I05 completion alone does not establish which ordering was exercised.

The endpoint hook is wired for Vault, Redis and ClickHouse based on manifest
capability and saved assignment. Kafka/Docker have no endpoint hook;
PostgreSQL is excluded by owner decision. No assignment is synthesized.

SESSION-RUN-CREDENTIAL-01 reserves one Broker slot `STARTING -> RUNNING(runId)`
for approved SSH identity metadata; it survives ordinary lease expiry and
releases only on authoritative terminal state or proven non-dispatch.
Uncertain retries use the same pending plan/attempt. The observer repairs
accepted remote Starts whose local persistence failed. Credential replacement,
clear and host-key trust changes are blocked while the slot is occupied.
Real React/Wails expiry-boundary acceptance remains pending.


Owner-requested session TTL is now two hours for workstation credentials, PKI/service
secrets and output-encryption passwords. Go tests/vet and Wails build passed;
real two-hour-boundary UI acceptance remains pending. Plan expiry is unchanged.

## Other retained decisions and accepted baselines

- Remote Linux Browser HTTP requires `-browser-allow-insecure-dev-http` and
  is prohibited for production systems/data. HTTPS/external origin and secure
  credential/secret transfer are deferred to version 1.0. Local Windows
  Browser and Wails are outside this specific HTTP restriction.
- RUNTIME-BUNDLE-UX-01A has local real-UI rebind evidence; see
  [rebind plan](docs/work/runtime-bundle/runtime-bundle-project-rebind-plan.md) and
  [workflow history](docs/history/workflow-state-20261008.md). It does not
  prove a clean-node bootstrap or close overall SI11 acceptance.
- Service settings use ordinary Ansible defaults/desired overrides. UI/Core
  previews are derived; PostgreSQL TLS usages retain the explicit PKI plan
  boundary. See [defaults plan](docs/work/service-install-11/si11-ansible-role-defaults-plan.md).
- Managed Kafka/PKI projections are runtime-only. Local structural Save is
  node-free; Project Verify is revision/runtime-bound, target-free and does
  not authorize execution. Every execution needs a fresh authoritative plan.
- Application server-type IDs are metadata with no service/placement/source
  authority; unknown valid IDs are preserved without automatic backfill.
- At most one Redis deployment per project was owner-approved; cumulative
  QA uses Sentinel HA, while standalone QA uses an isolated project.

Accepted baselines include CORE-01–07/07A, EXEC-01/01A, PKI-01,
SERVICE-01A–01D/02A, POSTGRES-01, NET-01–04.2, UI-BE-01–04,
EXEC-OBS-01, UI-01 overall and UI-02 overall. Their dated evidence is in
[milestone history](docs/history/milestones-state-20261008.md) and linked
milestone documents. These baselines do not close later regression gates.
SI08-F Vault endpoint HA technical acceptance and SI10 Docker rootless/Compose
are DONE with real initial/repeat UI runs and `changed=0` evidence; see
[Vault history](docs/history/vault-state-20261008.md) and
[Docker evidence](docs/work/docker/service-docker-rootless-architecture.md).

## Next authorized work and maintenance

The owner authorized this documentation/context optimization and explicitly
confirmed I05 PASS. This does not authorize new service runs, S11-00 cleanup,
next gated milestones, credential/trust replacement or architecture changes.
Continue an existing product task only within its established authorization
and fresh prerequisites; consult the relevant plan/journal first.

Keep this file compact: update these entries, put detailed run evidence in
the relevant journal, and link it. Do not prepend execution narratives or
copy historical DONE/NEXT lists. Before gated work, verify the exact checkout,
saved revision and current runtime rather than treating archived facts as live.
Use [agent index](docs/agent-index.md) to choose the required reading and
[maintenance record](docs/agent-context-maintenance.md) for archive provenance
and documentation verification.
