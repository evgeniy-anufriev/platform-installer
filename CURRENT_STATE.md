# Current state

Updated 2026-10-17. This file is the sole current milestone/status source.
Detailed historical checkpoints are archived under [docs/history](docs/history/si11-state-20261008.md).
Read the applicable plan and evidence for the task; an implementation or direct
Ansible PASS does not imply complete UI acceptance. A next gated milestone or
new destructive operation still requires explicit owner authorization.

## Active work and acceptance

| Work | Current status | Evidence and next step |
| --- | --- | --- |
| SDKU-POST-DEPLOYMENT-CORRECTIONS | Seven corrections implemented; D02/D03 RESOLVED; TARGETED_RECHECK APPROVE | [Plan](docs/work/application-libraries/sdku-post-deployment-corrections-plan.md). Shared connections/base-compose, all Registry targets, original image reference, uniform ENV quotes, configurable per-library runtime directory, infrastructure-stage evidence invalidation and explicit per-plan Infra Verify skip. Plan preserves Core authority and approval/trust/artifact/secret guards; no application installation. Owner-authorized QA runtime08 prepared on .103. [FULL PLAN review](docs/work/application-libraries/reviews/sdku-post-deployment-corrections-plan-review.md) found SDKU-PC-P01: original mutable image tag needs a target-side cross-project daemon/reference guard covering tag assignment through Compose start. Owner rejected SDKU-PC-P01: supported executions are sequential; no additional lock authorized. All seven corrections approved, Ansible tasks first, Python limited to necessary resolver/protocol changes. Source implementation present; independent [FULL DIFF review](docs/work/application-libraries/reviews/sdku-post-deployment-corrections-diff-review.md) BLOCK: D02 overlapping library roots in one sequential run; D03 positive new-protocol Wails/Core plan acceptance missing. Owner authorized D02 standard Ansible correction and D03 QA runtime acceptance. Overlap assertion and focused native tests PASS; real React/Wails/Core skip=false/true plans EXECUTABLE/PLAN_REVIEW PASS, actual INFRA_VERIFY_STALE retained; UI253/build/lint PASS. Independent [TARGETED_RECHECK](docs/work/application-libraries/reviews/sdku-post-deployment-corrections-targeted-recheck.md) APPROVE, D02/D03 RESOLVED, zero blockers; 104/104 fingerprints match. Source/plan-boundary closure complete; no final-source full Core-suite or visual PASS claimed. No additional lock or application installation. |
| HTTP-BACKEND-DIAGNOSTICS | Ansible tasks implemented; HTTP-D01 RESOLVED; TARGETED_RECHECK APPROVE | [Plan](docs/work/application-libraries/http-backend-diagnostics-plan.md). Owner requested safe address/status/timeout/reason in normal execution and explicitly rejected new Python scripts where tasks suffice. Builtin uri keeps raw request/response private; separate assert exposes closed diagnostics; existing callback projects these into DIAGNOSTIC events. Native HTTP200/503/redirect/timeout and existing HTTPS positive/negative PASS (2 tests); callback/journal PASS (27 tests, 4 isolated-root acceptance skipped). No new Python file; no bundle activation or deployment, existing SDKU runtime07 unchanged. Owner authorized HTTP-D01 correction: removed forced no_log:false; actual production tasks and real callback/private journal passed ordinary diagnostics and outer play/block suppression for HTTP200/503, preserving the failure barrier. RED OS native2 PASS22.253s; callback27 PASS1.582s (4 skips). [TARGETED_RECHECK](docs/work/application-libraries/reviews/http-backend-diagnostics-diff-review.md) APPROVE, zero blockers. Real Wails acceptance of the new packaged diagnostics remains pending. |
| SDKU-PACKAGES | Library defaults Core/UI implemented; SDKU DM installed on .101/.102/.103, plan SUCCEEDED | [Plan](docs/work/application-libraries/library-common-defaults-plan.md), [defaults journal](docs/work/application-libraries/evidence/library-common-defaults-journal.md), [deployment journal](docs/work/application-libraries/evidence/sdku-data-manager-deployment-journal.md). Defaults/inheritance/Reset and package checks passed as recorded; prior review limits preserved. Owner-authorized real React/Wails plan installer-68aefd2de64fd8196e3f9f3c10bbb478 SUCCEEDED on verified runtime07 (8a71ab48). All3 DM running/healthy, actuator UP, Vault Agent+Java, expected image. Redis client +@all -@admin; Sentinel explicit required commands; selected PostgreSQL CREATE includes public. Endpoint data-manager-sdku-dm.evoscada.internal resolves VIP .111 and trusted HTTPS returns200. Fresh unstarted authoritative plan reuses infrastructure PASS and contains only library Apply/Verify. Original HTTP publication failure exact reason was lost to no_log; unchanged repeat and safe diagnostic probes passed. Generic UI endpoint numeric serialization limitation remains documented; no application workload acceptance claimed. |
| POSTGRESQL-CREATE | Implemented; TARGETED_RECHECK APPROVE, zero blockers | [Plan](docs/work/application-libraries/postgresql-create-grant-plan.md), [journal](docs/work/application-libraries/evidence/postgresql-create-grant-journal.md), [review](docs/work/application-libraries/reviews/postgresql-create-grant-diff-review.md). Owner requested existing Go/UI grant CREATE for SDKU DM. Schema/Core/SQL/UI and generic Go writer tests implemented; Go test/vet, frontend249/typecheck/lint, Core17, schema compatibility1 and initial isolated PG CREATE PASS. Scalar ENV Go decoder fixed/tested against real SDKU snapshot. PGC-D01 RESOLVED by owner-authorized correction and TARGETED_RECHECK APPROVE: selected-account CREATE includes public; PUBLIC role guard retained. Real Wails Save/reopen/deselect/restore PASS, 1440/1024 visually inspected. Native PostgreSQL12 PASS plus final corrected-tree focused2 PASS/90.886s including PUBLIC regression. Corrected runtime04 verified/published (336abf2d), original uppercase SNAPSHOT tag supported/tested. Real SDKU Project Verify and library-only Build/Approve/Start exercised; DM installation and endpoint plan SUCCEEDED on all3, with native selected-account public CREATE check on .102 PASS (selected true, PUBLIC false, database CREATE false). |
| REDIS-COMMAND-POLICY | Implemented; FULL PLAN/DIFF APPROVE, zero blockers; target continuation pending | [Plan](docs/work/application-libraries/redis-command-policy-plan.md), [review](docs/work/application-libraries/reviews/redis-command-policy-review.md), [deployment journal](docs/work/application-libraries/evidence/sdku-data-manager-deployment-journal.md). Owner explicitly removed Core command policies on2026-10-17. Core and standalone module accept operator-selected named commands with no administrative denylist/Sentinel allowlist; same grants fields for both listeners. Typed validation/custody/ownership retained. RED OS providers17/native ACL3 PASS; frontend6/typecheck/lint and real React/Wails command/pattern Save/reopen PASS. Verified bundle06 (6dde6cd7) rebound. Owner extended scope to ordered +@category/-@category rules: Core/UI preserve order/duplicates, server metadata semantic comparison and owned command reconciliation implemented; native4/providers17/frontend6/typecheck/lint and real React/Wails Save/reopen PASS. [Category review](docs/work/application-libraries/reviews/redis-acl-rules-review.md) FULL DIFF APPROVE, zero findings. DM Redis client +@all -@admin, Sentinel explicit required commands. Bundle07 verified/published (8a71ab48); all3 DM containers healthy/UP with Vault Agent+Java. Saved Verify reuse/two-action plan proved; subsequent HAProxy HTTP backend publication failed and revoked infrastructure proof (owner requested stage-based correction; see SDKU-POST-DEPLOYMENT-CORRECTIONS). Owner-requested endpoint publication completed: plan68aefd2d SUCCEEDED, all3 healthy/UP, trusted HTTPS200. Fresh authoritative plan infrastructure PASS/two library actions. Original no_log result is not recoverable; no timeout/TLS cause claimed. |
| APPLICATIONS-PRODUCTION-UI | Secrets/Core implementation checkpoint; TARGETED_RECHECK APPROVE; automated regression PASS; revised UI parity PASS; target closure pending | [Access plan](docs/work/application-libraries/milestones/c/secrets-access-technical-plan.md), [access journal](docs/work/application-libraries/milestones/c/evidence/secrets-access-journal.md). Frontend247, Core680 PASS/21 SKIP, PG11/CH4/Redis2 PASS; real Wails access CRUD Save/reopen PASS; isolated PG existing/future/revoke/repeat and added negative QA PASS. Historical FULL BLOCK superseded by owner amendment and targeted APPROVE: ownership permitted/preserved; bounded CH revoke implemented, native standalone/three-server4 PASS. Final target/repeat/cleanup gates outstanding; new UI QA fixture/process cleanup blocked by automatic approval policy.  [Journal](docs/work/application-libraries/milestones/c/evidence/production-ui-journal.md). Five instance tabs (configuration parameters moved to Startup beside ENV), revised General with image/summary/typed readiness/ports/endpoint and read-only Core identity; instance Ports/Connections removed; real React/Wails Save/reopen/reset and 1440/1024 visual parity PASS; 1024px minimum width, explicit defaults/overrides, inline runtime inputs, library navigation and fixed draft footer reuse existing contracts. Universal parameters now use name-first addition and automatic new-value types with existing/package-type preservation; real Wails numeric/string/boolean Save/reopen PASS, frontend236 PASS; General image/readiness Save/reopen and reset PASS. Ports now show package/library-slot/instance/host/Core sources separately and support Add Host→Container; real empty-state/add/restore Save/reopen PASS. Library Connections includes Vault in one scrolling table, with saved vault_ref alias selection; real TLS-binding add/reset and Vault alias Save/reopen PASS, 1024/1440 layout inspected. New DBs use name-derived keys and type-filtered provider bindings; real name-only CRUD Save/reopen PASS. Library screen now combines Overview/Placement, selects Docker runtime, and edits provider-grouped database resources through existing resources CRUD; real React/Wails add/rename/delete Save/reopen PASS, compact 1440/1024 layout inspected. Secrets now edit username/password variable bindings via existing secret_bindings with source override, custom alias and reset; full frontend192 PASS, final focused18 PASS, real React/Wails Save/reopen PASS. Owner accepted editable library ID only at creation (package-name default/reset; saved ID immutable); writable KV document/key mapping deferred. No Go/Core or target changes. |
| EMPTY-PACKAGES-BOOTSTRAP-01 | Implemented; final automated checks PASS; TARGETED_RECHECK APPROVE_WITH_CHANGES, zero blockers | [Plan](docs/work/runtime-bundle/empty-packages-bootstrap-plan.md), [PLAN review](docs/work/runtime-bundle/empty-packages-bootstrap-plan-review.md), [DIFF review](docs/work/runtime-bundle/empty-packages-bootstrap-diff-review.md), [journal](docs/work/runtime-bundle/empty-packages-bootstrap-journal.md). Owner accepted download only when prerequisite is not installed and absent from offline bundle; node2 .102 authorized for QA. Owner permits DNF dependency updates and excludes actual React/Wails Prepare/READY from this stage. Empty input/platform inference, fixed pre-Core shell bootstrap, installed/local/repository ordering, root-owned recheck, no-tar SCP and separate activation added. RED OS builder7/bootstrap7 and four native Go cases PASS; all Go tests/vet and Windows build PASS. No fresh missing-package transaction or visual acceptance claimed. |
| RUN-RECONNECT-01 | Implemented; checks PASS; FULL DIFF blocker resolved by owner-approved TARGETED_RECHECK APPROVE; owner acceptance pending | [Plan](docs/work/execution/run-reconnect-plan.md), [journal](docs/work/execution/evidence/run-reconnect-journal.md), [review](docs/work/execution/reviews/run-reconnect-review.md). Previous-run inspection shows one run/revision/state and Attach restores existing Reconnect, events, Result and ordinary Cancel without another Start. RR-D01 unconfirmed-stop guards corrected and tested. Exact original project/node/account/key guards retained; no remote run list. Production app rebuilt; bundle run-reconnect-20261013-01 verified/published, digest 59b0d1aa…e19d3. Owner will perform real close/reopen/control QA. |
| APPLICATION-LIBRARIES-B | B0–B3 committed/synchronized; B4 COMPLETE within authorized nonvisual scope; final bundle08 target/saved-proof acceptance PASS; protected local credential-copy cleanup exception recorded | [Plan](docs/work/application-libraries/milestones/b/b-technical-plan.md), [review](docs/work/application-libraries/milestones/b/reviews/b0-diff-targeted-recheck.md), [journal](docs/work/application-libraries/milestones/b/evidence/b0-test-journal.md), [repair](docs/work/application-libraries/milestones/b/evidence/b0-regression-repair.md), [summary](docs/work/application-libraries/milestones/b/evidence/b0-regression-repair-summary.json). Full RED OS685:666 PASS/19 unchanged SKIP,0 failures/errors; no native PKI exclusions. All34 B0 cases PASS in full; fresh offline34 PASS. Corrected focused11 PASS/1 existing SKIP; affected root-native Vault permission proof2 PASS. Catalog/schema reproducibility and five real target-free validate.yml fixtures PASS. PKI test trust store isolated;840 system trust metadata/hash entries unchanged. No added skips/removed checks or production-logic changes; schema JSON key order only. Reviewed19-file B0 identity52683259…66defb1 unchanged; test/fixture20-file identitya51c8c36…3814ada.15 safe evidence files SHA-verified;QA workspace removed,0 owned processes. Historical BLOCK/FAILED runs retained. B0 committed2f148b28 and synchronized with master/origin. Owner authorized B1 on2026-10-14: typed adapter/application models, mode-plan transport and local observation primitives implemented in codex/application-libraries-b1; focused/full Go tests and vet PASS. [B1 journal](docs/work/application-libraries/milestones/b/evidence/b1-test-journal.md); [B1 FULL DIFF](docs/work/application-libraries/milestones/b/reviews/b1-diff-review.md) APPROVE_WITH_CHANGES,0 blockers; nonblocking B1-D01 image identity consistency corrected and focused tests/vet PASS. Go build PASS; B1 cache remains UNKNOWN/current admission stays Core-owned. B1 committed6cdeb8a1 and synchronized. Owner authorized B2 on2026-10-14: backend writer/package transfer COMPLETE within B2 scope; [journal](docs/work/application-libraries/milestones/b/evidence/b2-test-journal.md), [final independent review](docs/work/application-libraries/milestones/b/reviews/b2-slot-credential-recheck.md) APPROVE/zero blockers. Typed credential/shared-secret sources closed; slot.credentials only optional vault_binding. User parameters/environment/files accept arbitrary names and assignments per owner amendment. D01 RESOLVED,D02 SUPERSEDED,D03 RESOLVED; historical BLOCK reports preserved. Final Windows full Go test/vet/build PASS; RED OS affected writer/export/transaction/recovery/F2 and offline nine B2 tests PASS; applicable Core100/contracts4 PASS. Final identity6455eb0b…88ced1 unchanged. Safe QA logs SHA-verified; all owned temporary source workspaces cleaned. Two unchanged broader contracts/Linux Go baseline failures remain in journal; no global regression PASS or real UI/bridge acceptance claimed. Owner authorized B2 commit and master synchronization on2026-10-14; Git history is publication authority. B2 committed435cd74c and synchronized. Owner authorized B3: backend shared mode-aware lifecycle/presentation COMPLETE on codex/application-libraries-b3; [B3 journal](docs/work/application-libraries/milestones/b/evidence/b3-test-journal.md), [FULL DIFF](docs/work/application-libraries/milestones/b/reviews/b3-diff-review.md) APPROVE/zero findings. Windows full Go test/vet/build/browser-tag PASS; RED OS adapter and affected lifecycle/cache/recovery tests, race and offline B3 PASS. Nine-file identity9bfa3a11…10138432 unchanged. Full Linux desktop suite separately exposes unchanged Windows-only known_hosts test failure; no global Linux regression PASS claimed. Five safe logs SHA-verified, QA workspace cleaned. Owner authorized B3 commit/master synchronization; publication identity is recorded in Git history. Existing UI-design discrepancy remains deferred to B4/C as in approved plan. B3 committed2c3f9964 and synchronized. Owner authorized B4: post-plan Infrastructure checkbox inside services on Plan tab controls FULL_PROJECT/library-only; libraries fixed Apply/Verify. Previous plan stays visible, services muted, checkbox is local-only; changed-scope Core Build occurs on Approve before approving the returned plan. Production bindings/session allowlist/UI implemented on codex/application-libraries-b4; [B4 journal](docs/work/application-libraries/milestones/b/evidence/b4-test-journal.md). Focused/native/offline tests PASS; checkbox is presentation-only; scope-specific Core Build occurs on Approve and approval is limited to the returned plan. Final frontend checks passed; FULL DIFF BLOCK found acknowledgement reset gap and review identity changed during review. Fix and focused test added; corrected snapshot passed owner-approved targeted recheck (D01/D02 resolved, zero blockers). Actual React/Wails initial-plan prerequisite refusal verified, no targets contacted. Owner authorized bounded library-only target QA, but preflight BLOCKED before mutation: no project-bound saved infra Verify cache and actual Wails smoke had EXECUTION_NODE_READY_REQUIRED. B4/B positive target acceptance remains OPEN; infrastructure Apply was not run. The prior ServersPage.targettrust presentation failure was fixed: PREPARED now suppresses stale readiness findings. Full frontend regression 171/171 PASS. No new public execution mode was added. Latest owner amendment: when saved infrastructure Verify is absent or stale, the same library-only plan includes fixed infrastructure Verify before library Apply/Verify, never infrastructure Apply. With Services unchecked while the displayed plan belongs to the previous scope, the Plan tab locally filters SERVICE_APPLY rows without calling Core or mutating the source plan; once Core returns the selected-scope plan on approval, the UI displays it without filtering. RED OS focused Core/lease suite 141 passed/2 unchanged skips; native Ansible plan action and successful/failed controller fixtures passed. Independent targeted recheck APPROVE, findings B4-R01/R02 resolved, zero blockers. Bounded target continuation on2026-10-15 recovered the retained healthy A9 project snapshot. Real React/Wails preparation reached READY with bundle01; Start stayed blocked before mutation by project/candidate package transfer and capability version defects. Bounded corrections independently reviewed APPROVE_WITH_CHANGES/zero blockers; native regression finding resolved. Bundle02 ac7e1dff…8461b built on node2, standard validated/published; both QA locks match, updated runtime real React/Wails PREPARED/READY and exact Project Verify VERIFIED (revision ead61e4d…71689). Selected plan proves ten SERVICE_VERIFY plus library Apply/Verify and no SERVICE_APPLY. Positive target gate BLOCKED before Start with RUNTIME_SECRET_DESCRIPTORS_UNAVAILABLE. Actual target-free diagnosis: 10 infrastructure descriptors +9 application inputs exceed combined16 limit; Go response/session model also omits applicationInputs. Representative fixture unchanged, no target operations/run ID. Owner authorized correction2026-10-15: applicationInputs now reuse existing Broker/runtimeSecretValues lease with exact approved subset and unchanged byte/identity/expiry/scope guards; count limits removed. FULL DIFF APPROVE0 findings; full Go test/vet/build and frontend174 PASS; nativeCore176 run174 PASS2 existing SKIP. Bundle04 e7691c8a…5903b real React/Wails READY, exact Project Verify VERIFIED. Post-review contract-preserving fixes cover Verify-only typed subset and null optional PKI serialization; focused Go tests/vet PASS. First actual run installer-ea41d6ebf0ba9d03ab73dad9e72192aa FAILED on BIND SSH auth from obsolete A9 inventory key path; only owned fixture references removed, strict current-session PEM retained. Historical real React/Wails run installer-d3c0c55689c29f311e7cdbf1a988fc50 CANCELLED after four Verify successes and stale Redis input refusal. Approved scope10 SERVICE_VERIFY + library Apply/Verify; SERVICE_APPLY0. Latest full Go test/vet/build PASS; fullCore regression running, saved-proof reuse remains untested. No separate Verify-only approval or infrastructure Apply is required. Latest live checkpoint: d3c0c556…fc50 CANCELLED after four infrastructure Verify successes and stale Redis input refusal; no infrastructure Apply/library action. Redis/Sentinel current QA inputs recovered without service changes. Owner-provided ClickHouse input now matches installed verifier. Real React/Wails run997153a7…007c8 FAILED after6Verify successes at Registry installation-source preflight incorrectly reached in Verify-only. Bounded Apply-only guard corrected; native2/focused2PASS; bundle05 validated/published, realREADY/VERIFIED; e9f0a65e…0c23e FAILED at missing PKCS12 input; existing PKI credential requirement restored for Verify and library shared-secret use, Core144/native6PASS. Bundle07 validated/published and realREADY/VERIFIED; current PKCS12 input keytool-confirmed. Run a59f5b3c…923ad SUCCEEDED10:44:11Z seq6101: all10infraVerify+libraryApply/Verify SUCCESS,zeroSERVICE_APPLY;5statuses200/all8ok/CAhostname verified. Fresh realReact selected07plan uses savedCoreVerifyPASS10deployments and exact2appoperations (Startheld). Final provider-password scope correction tested144, finalfullCore691PASS21standardSKIP/Kafka23PASS; bundle08 published after07terminal, realREADY/VERIFIED. Final08 fab0fbfe…7355 SUCCEEDED; saved-proof actual React run9ba62439…c91f SUCCEEDED with exact2libraryops and noinfraoperations. All3container metadata identical;5statuses200/all8ok. Hygiene141files16values0matches;remoteQAworkspaces removed,ownedprocesses stopped. Local protected B4 credential-copy deletion BLOCKED by automatic approval review; cleanup not complete. Correct nonroot full Core690 PASS/21 standardSKIP. Final B4 nonvisual QA PASS; zeroSERVICE_APPLY. Visual inspection not claimed; protected local credential-copy deletion remains blocked by automatic approval review. Owner authorized B4 commit/master synchronization on2026-10-15; publication identity is Git history. |

| APPLICATION-LIBRARIES-C | COMPLETE: technical acceptance and target cleanup PASS; local retention owner-approved | [Plan](docs/work/application-libraries/milestones/c/c-technical-plan.md), [journal](docs/work/application-libraries/milestones/c/evidence/c-test-journal.md), [summary](docs/work/application-libraries/milestones/c/evidence/c-final-summary.json), [recheck](docs/work/application-libraries/milestones/c/reviews/c-diff-targeted-recheck.md). D01/D02 resolved; D03 owner-accepted. Actual editor/import/external-conflict flows PASS. Exact library Apply/Verify583s/197s and clean repeat607s/194s SUCCEEDED; entire selected metadata identical. Runtime inputs through existing lease/provider hooks/Vault/Agent11of11 and all5HTTP200/all8checks PASS. CSPA-only Agent restart/recovery PASS. Baseline restoration550s/198s succeeded; temporary C-QA users removed, five own remote workspaces cleaned; secret audit0 matches. Owner explicitly instructed to retain the nine local QA directories and protected C runtime-input copy; retention is an accepted cleanup exception. Installed P2 bundle04, infrastructure, canonical PKI/Vault/bootstrap, baseline users/data and journals retained. No infrastructure Apply/new bundle. Owner authorized C commit and master synchronization; Git history records publication identity. Earlier FAILED runs stay FAILED; production dark theme and raw recap changed counter not claimed. |
| APPLICATION-LIBRARIES-APPLY-PERFORMANCE | P2 functional/nonvisual QA PASS; no concurrency/infrastructure Apply; local obsolete-copy cleanup exception | [Plan](docs/work/application-libraries/apply-performance-plan.md), [journal](docs/work/application-libraries/evidence/apply-performance-journal.md). Final bundle04 b00ded90…29b165 real React READY/VERIFIED. Run c9ff…3d92 SUCCEEDED:10SERVICE_VERIFY+librarypair; saved-proof repeat ea019…9193 SUCCEEDED:exact2libraryops, noinfraops. Apply10:42/9:35 vsB4 28:47 (62.8–66.7% faster); Verify3:23/3:10. Both changed0/fullmetadataIDENTICAL/3containerspreserved; all5statuses200/exact8checksok/CAhostnameverified. BroadCore675PASS/21standardSKIP before bounded transport fixes; final affected188PASS/4standardSKIP+7SSH/native30connections10cleanupcyclesPASS. Ownsocketdirs0, remote4node2+1node1QAworkspaces/2diagnosticcredentialcopiesremoved; currentruntime/sharedinfra/PKI/bootstrap preserved. Hygiene16values230files0matches. Automatic approval blocked local oldQA bundle02/03 deletion; retained explicit exception. D01 independent targeted review APPROVE; historical FAILED/INTERRUPTED preserved. No visual/real30-container claim. Owner authorized P2 commit/master synchronization; Git history records publication identity. |

| APPLICATION-LIBRARIES-A9 | COMPLETE within owner-amended standalone Core/Ansible QA scope; cleanup and secret hygiene PASS | [Plan](docs/work/application-libraries/milestones/a9/a9-technical-plan.md), [journal](docs/work/application-libraries/milestones/a9/evidence/a9-test-journal.md), [final summary](docs/work/application-libraries/milestones/a9/evidence/a9-final-qa-summary.json). Bundle10 ff20edef88f895077b1f4a2cf1287dcd2b919b54feaa5aaa4860b44659346e96. Initial library Apply/Verify, five direct/trusted HTTPS status checks, unchanged repeat, isolated CSPA missing-binary failure/repair and post-retry repeat PASS. Final repeat Apply875.29s/Verify244.08s changed0 all hosts; entire metadata identical. Owned containers/networks/configs and provider objects removed; SDKU baseline endpoint restored, CSPA endpoint removed; shared infrastructure/PKI/images and current Vault generation4 canonical bootstrap audit preserved. Secret scans: 21 current/historic values, 1383 local source files, 627 protocol files, 268 public runtime files and 15 materialized .env/Compose files; zero matches. 163 safe evidence files copied locally and SHA256 verified; 20 QA source/build/retired-public workspaces cleaned via qa-sync; 102 native-QA private files removed. Empty local .runtime/secrets/a9 retained after automatic deletion review rejection; contains no credential files. Mixed14 remains FAILED on Vault space; owner accepts nine mixed service pairs plus separately successful Vault Apply/Verify and barrier evidence, explicitly excludes another infrastructure run. No full mixed terminal SUCCESS or Go/UI acceptance claimed. Observation stopped after closure. A9 committed as 1d1fc73e and integrated into master by owner request on 2026-10-14. Post-merge RED OS focused regression189 PASS/4 isolated acceptance SKIP, zero failures; temporary QA source cleaned with qa-sync. No next milestone implementation authorized. |
| REDOS73-SUPPORT-01 | COMPLETE (owner-directed closure for tested Ansible Core/service-role scope; TARGETED_RECHECK APPROVED; Go/Wails acceptance not applicable) | [Implementation](docs/work/redos73-support/implementation.md), [test journal](docs/work/redos73-support/evidence/test-journal.md). On RED OS 7.3, standalone Apply/Verify/repeat passed for ClickHouse, PostgreSQL, Redis, Vault, Docker Rootless, HAProxy and Kafka (single-host plaintext combined broker/controller); full BIND service Apply/Verify/repeat passed with one authoritative primary. BIND Apply changed the QA zone host record from stale `.104` to current `.105`, Verify passed, repeat Apply changed=0. Python 3.8 schema-validation, project-validation and BIND contract suites passed (7/24/21), and target-free validation of the single-host fixture returned PASS (`ok=12 changed=0 failed=0 skipped=2`). SELinux was configured disabled. After enabling `systemd-resolved` with the NetworkManager DNS plugin on all three nodes, BIND primary/secondary plus DNS-client three-host Apply/Verify/repeat all passed; DNS-client Apply changed the resolved configuration on each node, Verify passed with changed=0, and repeat Apply changed=0. The earlier DNS split-DNS block was resolved for this configured backend. Three-participant Keepalived Apply/Verify/repeat passed on `.104/.105/.106` in the 2026-10-12 run. Multi-host PostgreSQL `pg_auto_failover` Apply/Verify passed on `.104/.105/.106` with `pg_ctl` detected under `/usr/pgsql-16/bin`; the earlier repeat regenerated absent runtime-only PKI state (28 localhost changes, 5 per host); the cause of that state loss is unknown. After PKI state was present, current-tree PostgreSQL Apply was clean on localhost and all three nodes (`changed=0 failed=0`). The role now supports `/usr/bin` and versioned PostgreSQL binary paths while preserving explicit overrides; RED OS 8 was not retested in this correction run. Redis Sentinel Apply/Verify and final repeat Apply passed on `.104/.105/.106` (`changed=0 failed=0`); two preceding repeats reconciled TLS material and ACL attachment on `.105/.106`. Final Verify passed with `changed=0` on all nodes. Multi-host Vault Raft Apply/Verify/repeat now passed after temporarily disabling unused swap in RAM on the three QA nodes (no fstab change); Multi-host HAProxy and Docker Rootless Apply/Verify/repeat now pass on `.104/.105/.106` (changed=0 on Verify and repeat Apply); ClickHouse three-member Keeper and ReplicatedMergeTree Apply/Verify/repeat now pass on `.104/.105/.106`; verified TLS reads returned the inserted row from all three replicas. Multi-host Kafka KRaft plus Schema Registry Apply/Verify/repeat passed on 2026-10-12. PostgreSQL monitor-address and HAProxy exact-PKI-selector assertions plus exact Keepalived `ansible.builtin.systemd` checks pass on RED OS 7.3.7; independent targeted recheck APPROVED with zero blockers at fingerprint `sha256:fdee91010b78d766a712dba0523f4eb78ba78092609130555f39b832dd962201`. Owner closes this work for the tested Core/Ansible scope. Unverified service versions/topologies remain outside the support claim; the QA bundle was not published. |
| KAFKA-SCHEMA-REGISTRY-01 | IN PROGRESS; standalone React/Wails acceptance PASS | [Implementation](docs/work/kafka-schema-registry/implementation.md), [evidence](docs/work/kafka-schema-registry/evidence/test-journal.md), [targeted review](docs/work/kafka-schema-registry/evidence/sr-d01-targeted-review.md). Broker-bound Registry, default enabled/SSL/8081/8082 and pinned offline artifact implemented. Shared ownership guards and six production-task regressions PASS; focused 16+25+33 PASS. TARGETED_RECHECK APPROVE_WITH_CHANGES, zero blockers; SR-D02 remains nonblocking. Real Wails exposed and corrected listener editor bounds and Verify artifact-condition ordering. Final bundle -31 published; two actual React Plan/Approve/Start/Result cycles SUCCEEDED, PKI/Apply/Verify changed=0 in both. HTTP registration and CA-verified HTTPS retrieval PASS. Visual inspection not performed. Broader split-role/multi-host/colocated/Clear acceptance remains open; QA deployments and protected run state retained. |
| APPLICATION-LIBRARIES-A8 | COMPLETE within A8 Core scope; owner authorized commit/master synchronization | [Technical plan](docs/work/application-libraries/milestones/a8/a8-technical-plan.md). Owner accepted runtime-file/current-run-bootstrap contract; PLAN P01 resolved by approved targeted recheck. Implementation and corrections authorized. [FULL DIFF](docs/work/application-libraries/milestones/a8/reviews/a8-diff-review.md) and [TARGETED_RECHECK](docs/work/application-libraries/milestones/a8/reviews/a8-diff-targeted-recheck.md) remain historical BLOCK: D01 independently RESOLVED; D02 final QA evidence now fulfilled in [journal](docs/work/application-libraries/milestones/a8/evidence/a8-test-journal.md). RED OS affected250:246 PASS/4 skips, native6 PASS; final reporting correction mixed8/Vault-provider29 PASS. Final bundle11 standard validation/source equality PASS. Fresh bootstrap without operator token (bundle10, reporting-only delta to11), two-host Vault Agent/PKCS12/Redis content PASS; explicit-token final11 repeat SUCCEEDED changed0; active application Cancel CANCELLED and expected Apply failure FAILED with no Verify; infra-only Start/Verify/Cancel PASS. Full8-run event/custody records, all secret/lease cleanup PASS; owned QA resources and registered temporary source/build/input workspaces removed, shared services/image and canonical bootstrap audit retained. FULL plus one targeted DIFF budget consumed; no new independent APPROVE claimed. A8 committed as 2bbcb789; integrated master f8c5f46, post-merge RED OS216 PASS; owner authorized master synchronization; no cache publication/A9 work. |
| APPLICATION-LIBRARIES-A7 | COMPLETE within A7 scope; FULL DIFF blockers resolved by owner-approved TARGETED_RECHECK APPROVE | [Plan](docs/work/application-libraries/milestones/a7/a7-technical-plan.md), [historical FULL review](docs/work/application-libraries/milestones/a7/reviews/a7-diff-review.md), [targeted recheck](docs/work/application-libraries/milestones/a7/reviews/a7-diff-targeted-recheck.md), [QA journal](docs/work/application-libraries/milestones/a7/evidence/a7-test-journal.md). Owner accepted plan and authorized implementation/corrections/QA in codex/application-libraries. Structured application plans/descriptors and two fixed standalone operations implemented; production application plans remain BLOCKED without executable manifest until A8. A7-D01–02 RESOLVED, zero open blockers. RED OS initial 249 PASS/4 skip plus 42 PASS; corrected focused 120 PASS/4 skip and 17 PASS. Real native Docker Build/lease/Start/Apply/Verify SUCCEEDED, changed=0; separate active Cancel CANCELLED, changed=0; credential cleanup PASS. Remote temporary source/bundle/identity cleanup passed; nonsecret local verified QA bundle retained after automatic deletion rejection. Go/UI and mixed production execution remain later stages; A7 committed as 004a465 in codex/application-libraries; owner authorized synchronization into master. |
| APPLICATION-LIBRARIES-A6 | COMPLETE: standalone A6 accepted by owner on 2026-10-12; prior review BLOCK retained | [Plan](docs/work/application-libraries/milestones/a6/a6-technical-plan.md), [DIFF review](docs/work/application-libraries/milestones/a6/reviews/a6-diff-review.md), [QA journal](docs/work/application-libraries/milestones/a6/evidence/a6-test-journal.md). Real two-host image connections and verified HTTPS /status PASS; Apply/Verify and ordinary repeat changed=0 PASS. Full HAProxy reconcile/Verify/repeat changed=0 PASS; full BIND reconcile and subsequent application Verify PASS (445.760s). Existing DNS records preserved (9 before/10 after, none missing); Vault/ClickHouse HTTPS endpoints 200. Owner-approved ClickHouse sslVerify=none persisted in QA desired state and all proxies. Full selection no longer retains a partial filter; BIND generated-state validation now reuses the existing application snapshot/infrastructure schema boundary. HAProxy host-scope 3 and BIND regression 21 PASS; earlier D01–03 56, integration 10, D07 11 PASS. Synthetic negatives remain separate evidence. Original FULL/TARGETED_RECHECK BLOCK is retained as historical evidence; closure is by explicit owner acceptance. QA fixtures/containers/workspace and staged key cleaned; images/protected logs retained. Owner authorized the A6 commit on codex/application-libraries; Go/UI and master synchronization remain outside this acceptance. |
| PROJECT-RESOURCE-SETTINGS-01 | COMPLETE (owner-confirmed) | [Plan](docs/work/project-lifecycle/project-global-path-and-prefix-plan.md), ADR-037. Owner chose service-only data root, portable project settings, empty service-name prefix by default and underscore-capable prefix. Installer PKI paths stay fixed. FULL DIFF review: APPROVE_WITH_CHANGES, zero blockers. Earlier RED OS project copy with `/srv/service-data` and `qa` passed Validate, ProjectSnapshot and target-free DeploymentPlan (`EXECUTABLE`, all `changed=0`); five focused suites (67 test executions), catalog reproducibility, App.test.tsx (72), frontend typecheck/lint, `go test ./...`, `go vet ./...` and Wails production build passed. Owner's UI confirmed `/data` is saved and Core preview runs. Core preview accepts Ansible mapping proxies; focused RED OS regression passed (8/8). Ownership correction is in the existing `managed_data_path_guard` role: Apply reconciles only a non-default shared data root to the SSH technical user (`ansible_user`), mode 0755; Verify checks it without mutation; service data children remain service-owned and default `/var/lib` stays root-owned. Focused RED OS playbook passed (28 ok, 0 failed). Bundle `si11-full-service-20261011-24` includes the correction and validated with digest `sha256:dc34385210433e309578575e31e3a7a2093682dda7277e64c235a4f5beda8ee9`. The owner-authorized real UI PostgreSQL flow also completed Apply and Verify successfully using `/data/qa-postgresql/postgres`; the owner confirms this work item is complete. |
| APPLICATION-LIBRARIES-A5 | Current A5 scope implemented; initial FULL DIFF BLOCK resolved by owner-approved TARGETED_RECHECK APPROVE; A5-C01 closed by owner risk acceptance | [Plan](docs/work/application-libraries/milestones/a5/a5-technical-plan.md), [review](docs/work/application-libraries/milestones/a5/reviews/a5-diff-review.md), [journal](docs/work/application-libraries/milestones/a5/evidence/a5-test-journal.md). Redis/Sentinel TLS hooks and infrastructure account preservation PASS; ClickHouse standalone and three-server ON CLUSTER account/grant repeat/Verify PASS. Shared credential root/files remove PostgreSQL coupling, with legacy Core input compatibility; 67 application and 12 Vault tests PASS. Full A4 regression PASS after existing-Vault-source Verify correction. A5 common entrypoint/container Apply/Verify/repeat PASS, including Redis/Sentinel, ClickHouse and Kafka SSL ApiVersions without authentication; updated QA image built on RED OS rootless Docker. Core regression: 534 PASS/19 skip (553 tests, 16 unchanged native PKI recovery cases excluded). Final ClickHouse concurrent-repeat/witness checks PASS. Owner accepted late queued-DDL/retry overlap risk and excludes pending markers/task correlation/special retry gates; historical PLAN BLOCK remains, not reviewer APPROVE. C02 queue verifier hygiene is nonblocking. Owner-authorized D01/D02 native tests and targeted review APPROVE: Redis member failure/retry, ClickHouse HA fail-closed/retry, two-library/two-host projection with account preservation. D03 documented/tested. A5 current-scope implementation, RED OS QA and review are complete; C02 production Keeper queue policy proof remains nonblocking. Merged into master from codex/application-libraries; Go/UI remain out of scope. |
| APPLICATION-LIBRARIES-A4 | COMPLETE: standalone A4 accepted by owner; Go/UI remain out of scope | [Plan](docs/work/application-libraries/milestones/a4/a4-technical-plan.md), [journal](docs/work/application-libraries/milestones/a4/evidence/a4-test-journal.md). Two-host RED OS fixture passed HTTPS/443 endpoint routing, multi-host placement, AppRole renewal/restart and scope/CIDR. Latest native fixture passed live KV CAS retry with neighbor preservation, missing-field/unsafe-path fail-closed, Apply/Verify/repeat and standalone token/bootstrap; Vault provider tests 12 PASS and Apply syntax-check PASS. Owner confirms automatic Vault Agent AppRole reauthentication after `maxTTL` expiration was personally verified and works, closing A4-D01. Independent targeted-recheck BLOCK is retained as the reviewer’s finding on its evidence snapshot; closure is by owner acceptance, not a reviewer PASS. No Go/UI implementation, commit or master sync authorization. |
| APPLICATION-LIBRARIES-LIGHT-VERIFY | Owner-authorized implementation; focused standalone QA PASS | [Journal](docs/work/application-libraries/milestones/lightweight-verify/evidence/lightweight-verify-test-journal.md). One inspect task per instance: image ID, ownership, Running/configured healthcheck. Standalone skips target/source preflight; Apply retains full preflight. Independent FULL DIFF APPROVE_WITH_CHANGES, zero blockers; documentation corrected, negative identity coverage remains nonblocking. Two-container Apply/Verify/repeat and real healthy/unhealthy PASS; six supplementary predicate cases PASS. QA-found unhealthy condition corrected after review; no repeat review claimed. Remote QA cleaned. |
| APPLICATION-LIBRARIES-A1-A2-SPEED | COMPLETE: bounded standalone optimization PASS; FULL DIFF APPROVE_WITH_CHANGES, zero blockers | [Review](docs/work/application-libraries/milestones/a1-a2-speed/reviews/a1-a2-speed-review.md), [journal](docs/work/application-libraries/milestones/a1-a2-speed/evidence/a1-a2-speed-test-journal.md). Unit105, offline36 subset, standalone A1 14, native discovery isolation1 and six real runtime cases PASS; syntax and cleanup PASS. Sequential two-container Apply/Verify/repeat benchmark 305.317s → 263.973s (~13.5% in one measurement); clean repeat changed=0/IDs preserved. SPEED-D01 coverage added and passed. No native 10/30-container timing, A3 implementation, bundle or Go/UI acceptance claimed. |
| APPLICATION-LIBRARIES-A3 | Standalone implementation and focused acceptance PASS; TARGETED_RECHECK APPROVE, zero blockers | [Plan](docs/work/application-libraries/milestones/a3/a3-technical-plan.md), [PLAN review](docs/work/application-libraries/milestones/a3/reviews/a3-plan-review.md), [DIFF review](docs/work/application-libraries/milestones/a3/reviews/a3-diff-review.md). A3-D01/D02 RESOLVED by owner-approved TARGETED_RECHECK; full standalone and native primary/standby functional PASS. Owner-approved additive explicit grants; resource batch per library, account batch per instance; benchmark cancelled. Implementation is maintained on codex/application-libraries. Isolated RED OS only; no Vault/Go/UI/master authorization. D01–D04 corrections implemented. [QA journal](docs/work/application-libraries/milestones/a3/evidence/a3-test-journal.md): 528 Core cases (509 PASS/19 skip), 16 unchanged native PKI recovery cases excluded; native full entrypoint, account login and writable primary/standby PASS. All A3 source copies cleaned; no second FULL review. |
| APPLICATION-LIBRARIES-A2 | COMPLETE: standalone baseline PASS; no Go/UI acceptance implied | [Plan](docs/work/application-libraries/milestones/a2/a2-technical-plan.md), [DIFF review](docs/work/application-libraries/milestones/a2/reviews/a2-diff-review.md), [journal](docs/work/application-libraries/milestones/a2/evidence/a2-test-journal.md). D01/D02 resolved by owner-approved TARGETED_RECHECK: APPROVE_WITH_CHANGES, zero blockers; D03/D04 nonblocking limits remain. Focused/offline 32 PASS; six real public-image runtime cases PASS across node1/node2, including distinct images and healthcheck. Broad regression plus five PKI timeout-repair cases PASS; test-only limit 600s, production PKI unchanged. Cleanup verified. Owner decision 2026-10-10: Compose literals and additional package fields remain user-controlled; Core verifies only identity/image/command/labels/env and ports/mounts it projects, not the literal host bind address. See plan/journal. No Go/UI authorization. |
| APPLICATION-LIBRARIES-A1 | DONE for standalone contracts/read-only resolution; acceptance PASS on 2026-10-10 | Implementation branch codex/application-libraries. Independent recheck closed A1-D01–03; A1-D04 corrected and tested. RED OS: 15 focused + 14 standalone PASS. Core broad run: 517 cases, 19 root/isolated-acceptance skips; six PKI timeout errors and one stale Redis fixture failure corrected in tests, all seven failed cases then PASS. Combined regression evidence: 498 passed/19 skipped; original FAILED run retained, no claim of a second full run. QA copies verified and cleaned. See [review](docs/work/application-libraries/milestones/a1/reviews/a1-diff-review.md), [journal](docs/work/application-libraries/milestones/a1/evidence/a1-test-journal.md) for exact source identity and execution prerequisites. A1 review budget consumed; A2 separately authorized, Go/UI not authorized. |
| SERVICE-INSTALL-11 | CLOSED BY OWNER (2026-10-12) | Owner closed the overall S11 stage. Individual case verdicts and evidence remain as recorded in the [journal](docs/work/services/evidence/service-install-11-test-journal.md); open/failed cases were not retroactively marked passed. |
| ENDPOINT-HAPROXY-PLACEMENT-01 | Source implemented; FULL DIFF APPROVE; focused/standalone QA PASS, real acceptance pending | Owner approved narrow binding replacement and package backend defaults on 2026-10-09. Full Core 497-case run had one stale test assertion; corrected five-consumer test passed isolated recheck. Existing backend publication/reconcile reused; no new target store or transaction guarantee. Partial move/delete cannot discover former excluded hosts; explicit full reconcile remains necessary. See [plan](docs/work/endpoint-placement/endpoint-haproxy-placement-plan.md), [review](docs/work/endpoint-placement/reviews/endpoint-haproxy-placement-plan-review.md), [journal](docs/work/services/evidence/service-install-11-test-journal.md), ADR-033. No bundle release or real installation acceptance yet. |
| SERVER-INFORMATION-CHECK-01 | Implemented; real informational flow and targeted review passed | [Plan](docs/work/server-information/server-information-check-plan.md). One explicit SSH key confirmation supplies information and installation trust. Real React/Wails target and Execution Node checks, cancellation and changed-credential rejection passed; no installation started. |
| EXECUTION-NODE-PASSWORD-AUTH-01 | Implemented; targeted review APPROVE, sudo UI checks owner-confirmed | [Plan](docs/work/execution-node-password-auth/execution-node-password-auth-plan.md). Real React/Wails password checks passed for target node2 and Exec node1. Password hold survives lease expiry only for the exact active Start/run. Real Windows/RED OS password SCP passed; staging/cleanup and scoped sudo corrections reviewed. Owner confirmed the sudo correction works. Owner-confirmed correct/wrong/empty sudo cases accepted by independent EP-S04 recheck; zero remaining blockers. Full installation/Start with password remains separate. |
| PROJECT-VERIFY-PASSWORD-FIX-01 | Implemented; owner confirms Verify completes, FULL DIFF APPROVE | [Plan](docs/work/project-lifecycle/project-verification-password-fix-plan.md). Password archive transfer no longer requires PEM; ordinary Verify uses a private temporary directory. Transfer failures show unavailable with their own reason. Go checks and 64 App tests/build/lint pass; exact owner terminal status/revision not supplied. |
| PROJECT-SAVE-NODE-READINESS-FIX-01 | Implemented; FULL DIFF APPROVE_WITH_CHANGES, owner UI repeat pending | [Journal](docs/work/services/evidence/service-install-11-test-journal.md). Saving placement retains prepared node only for unchanged project/selected SSH endpoint/runtime bundle/catalog. Verification and installation approval still become stale. Go tests/vet pass; credential/pin guards unchanged. No blocking findings; actual Commit/Verify and expired-credential acceptance remain open. |
| PROJECT-EXPORT-SIBLING-FIX-01 | Implemented; FULL DIFF APPROVE, UI repeat pending | [Journal](docs/work/services/evidence/service-install-11-test-journal.md). Export overlap guard checks final destination rather than its parent; sibling export passes, same-root/nested destinations remain blocked. Go tests/vet and packaged export-fix build pass; zero review findings. |
| PROJECT-EXPORT-DISPLAY-NAME-01 | Implemented; FULL DIFF APPROVE, real UI repeat pending | [Plan](docs/work/project-lifecycle/project-export-display-name-plan.md). Export name updates only copied project.yml metadata.name; source and project ID remain unchanged. Original source revision and output digests/sizes are separate. Go checks and 65 App tests/build/lint pass; packaged export-name EXE rebuilt. No blocking findings. |
| SERVICE-UNIT-NAMING-01 | Implementation and focused QA complete; real naming acceptance pending | [Plan](docs/work/service-unit-naming/service-unit-naming-plan.md). Requires separately approved S11-00 baseline and real full-service UI naming checks. Prior I05 success does not prove new names. |
| SESSION-RUN-CREDENTIAL-01 | Implemented; real expiry-boundary acceptance pending | [Plan](docs/work/execution/session-active-run-credential-plan.md). Go tests/vet passed; exercise the real React/Wails flow at the lease-expiry boundary. Owner declined another review. |
| EXECUTION-ORDER-01 | Implemented with focused standalone evidence; remaining acceptance pending | [Plan](docs/work/execution-order/execution-order-01-plan.md), ADR-030. Keep source/provider dependency fail-closed; close interruption/recovery, stale-record deletion and real UI gaps. |
| SERVICE-INSTALL-09 ClickHouse | PARTIAL ACCEPTANCE, NOT DONE | [Plan](docs/work/clickhouse/service-install-09-clickhouse-architecture.md). Direct 1/1, 3/1, 3/3 and endpoint evidence passed; formal terminal real-bridge PASS and strict repeat remain unclosed. Owner previously declined another cumulative SI09 run. |
| EXEC-PLAN-SCOPE-01 | NOT STARTED / deferred by owner | [Acceptance sequence](docs/work/services/service-install-acceptance.md), [roadmap](docs/roadmap.md). Separate request required; current full plans are not selective provider reconcile. |
| BROWSER-REMOTE-01/02 | HTTP restricted to explicit dev; HTTPS deferred to version 1.0 | [Remote plan](docs/work/browser/browser-mode-remote-plan.md), ADR-028. Production transport/credential acceptance is not complete. |

## SI11 current evidence and open cases

The owner closed overall S11 on 2026-10-12. This is the current stage status;
case-level verdicts and their evidence below remain unchanged. Open or failed
cases are not retroactively marked passed, and missing run details are not
inferred. See the journal for the case record and historical evidence.

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

The [UI test cases](docs/work/services/service-install-11-ui-test-cases.md) and
[test journal](docs/work/services/evidence/service-install-11-test-journal.md) define detailed coverage.
The journal is evidence, not permission to perform a new run or reset.
S11-00 cleanup was repeated on 2026-10-11, then the `full-services` project was
installed again. On the latest target audit, only Redis/Sentinel deployment
`qa-redis` was removed from node1/node2/node3 at the owner's request; its data,
service configs/ACLs and per-member TLS copies, logs, custom units, Redis RPM,
and dedicated Redis user/group/home were deleted. Shared PKI and other services
were retained. See the historical
[cleanup record](docs/work/services/service-install-11-cleanup.md) for S11-00; the latest
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
acceptance remains pending. Evidence: [SI11 journal](docs/work/services/evidence/service-install-11-test-journal.md).

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
Evidence: [SI11 journal](docs/work/services/evidence/service-install-11-test-journal.md).

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
  boundary. See [defaults plan](docs/work/services/si11-ansible-role-defaults-plan.md).
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
