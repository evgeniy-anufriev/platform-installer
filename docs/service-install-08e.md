# SI08-E — real Vault acceptance

## Owner-approved transient lock recap — standalone repeat changed=0

Only Hold the shared Vault bootstrap lock and Stop only this invocation's
transient lock holder report changed_when:false. They coordinate an invocation,
not persistent desired state; lock ownership/readiness/nonblocking contention,
fail-closed busy admission and always-release are unchanged. Persistent lock
directory, package/configuration/PKI/data changes retain normal change reporting.
Fresh RED OS: 20 role tests PASS (2.061s); real isolated validate-lock.yml PASS,
including contention, ordinary release and failed-holder recovery. Exact transient
test units/directory and helper QA workspace removed. Syntax/catalog/schema PASS.

Immutable release qa-si08-vault-20260927-14 activated:
sha256:e80e44d23c8c61a1be3f6a2e970e6d7da218bb1aed917fddb75774fe2174c325.
Actual React/Wails command: node .runtime/qa/vault-wails.cjs; READY check,
encrypted inputs, fresh plan/approval/Start, live observer and Result/output list.
Plan plan-6240efc2d7659001c91933c5 at saved revision
sha256:63dc5e487a0406782b37457cf5955393cbba3e0088504d56b5b8c0a1f573c21d.
Run installer-d58d310393ae11ca56d6ff26c7dbd619 SUCCEEDED after 1508s
(25m08s), seq 902; PKI/apply/verify SUCCESS at seq 149/721/901.
Authoritative task stream: 341 SUCCESS, 105 SKIPPED, 0 CHANGED, 0 FAILED.
Sequence gap count 0; no task-observability degradation/truncation diagnostic.
Final Go suite/vet and diff check PASS; tracked runtime secret files 0.
Fresh repeat changed=0 achieved, not inferred from timeout or masked service tasks.
No active transient Vault lock units remain. Read-only health HTTP 200,
initialized/unsealed/leader, canonical unit ACTIVE. No reset/reinitialization;
existing encrypted custody unchanged, pending output list READY/NO_NEW_PACKAGE.
Owned dev/harness stopped, exact temporary RSA removed.
Standalone repeat acceptance closed; HA 3/1, HA 3/3/failover and final full
milestone gates remain. Known dev overlay exception is not a clean UI claim.

## Shared PKI verify correction — standalone full plan PASS (2026-09-27)

Vault omitted the shared pki-verify.yml import already used by Kafka/PostgreSQL.
Added it after validate.yml and before Vault verify-only. Existing Core resolver
reconstructs derived requests/plans for this independent Ansible process;
pki_verify checks deployed files, chain and materialization fingerprint read-only.
No new persistence, protocol, path guessing, TLS bypass or Go PKI calculation.
Fresh RED OS: Vault 19 PASS (1.859s), consumer selection 3 PASS (8.255s),
PKI resolution 12 PASS (0.048s), verify syntax/catalog/schema PASS.
Exact helper QA workspace cleaned.

Supported immutable release qa-si08-vault-20260927-13 activated:
sha256:31ef6e223a6c76330b179cc7629094232f6b7e15807ee33090caf1d686c92569.
Saved revision sha256:57a71854492b2f7e23fe9b718996692e9d99a0c5159eb5fddef108f7ebdb9612.
Actual React handlers/Wails Go: open existing project, READY check, encrypted
input import, fresh plan plan-1229e0c17b8d70e3ca1c8e6f, approve, Start,
observe to terminal, Result pending-output list READY/NO_NEW_PACKAGE.
Run installer-a31ff651ccf90db5d83d5acbb75494f8 SUCCEEDED in 1312s (21m52s),
seq 902. PKI/apply/verify action SUCCESS at seq 149/721/901.
Task evidence: 339 SUCCESS, 105 SKIPPED, 2 CHANGED, 0 FAILED; only transient
lock hold/release changed (372/712). This is NOT strict repeat changed=0.
Verify action reports no changed tasks; existing PKI/audit/config/data unchanged
by verification. Initialized Vault did not emit a new bootstrap package.
Final read-only health HTTP 200, initialized/unsealed/leader, canonical unit ACTIVE.
No reset/reinit/custody replacement. Owned dev/harness stopped, exact RSA removed.
Known Wails dev overlay exception remains; clean visual acceptance not claimed.
SI08-E overall is not DONE: strict repeat, lock bookkeeping disposition,
HA 3/1, HA 3/3/failover and remaining final gates are still outstanding.

## Owner-authorized audit correction: real apply PASS, verify blocked

New audit API requests use string 'false'. Existing '0' false representation
admitted by exact membership alongside the previous false case-folded form;
absent option retains Vault default false. No arbitrary bool coercion, existing
device rewrite, disable/re-enable or secret exposure. Vault formatter uses
strconv.ParseBool for log_raw (audit/entry_formatter_config.go); '0' is false.
Tests execute actual Ansible Conditional/Templar guards for configure and verify:
40 positive/negative cases, plus wrong type/local/path audit guard negatives.
Fresh RED OS suite: 18 PASS, 2.347s; source helper verification PASS;
apply/static-verifier syntax and catalog/schema reproducibility PASS.
Go full suite/vet and diff check PASS. Exact helper QA workspace cleaned.

Supported immutable qa-si08-vault-20260927-12 activation:
sha256:1fbe82af9044d93cc68a898e7be8bda84b351f2ca671173bec5dcb0ecbcc98b6.
Real React/Wails READY, encrypted imports, fresh plan approval/Start accepted.
Plan plan-519730a358b82c118cda6130; saved revision
sha256:00c1bc110338d41c79c16a672d9887e00f32c344369fdd69b92de60e7a5a2cd8.
Run installer-5f3974b945758ad381f9dee706351b7d FAILED after 1309s, seq 826.
PKI action SUCCESS; Vault apply SUCCESS (seq 721), including built-in verifier.
Separate verify action fails Require one exact PKI consumer plan (seq 824):
Core-owned materialized selector evidence absent for this independent action.
No TLS bypass/path guessing or redesign performed. Full acceptance still blocked.
Observed changed=2 tasks are transient lock hold/release; strict repeat changed=0
not claimed. Existing audit/KV2/userpass unchanged, no reinitialization.
Owned dev/harness stopped and temporary RSA removed; custody/data preserved.

## Existing audit-option representation blocker (2026-09-27)

React/Wails run installer-bd14ba46f1db62f80dbba808cb45988e FAILED after
921s, terminal sequence 690. READY, encrypted input imports, fresh plan approval
and Start accepted. Reboot recovery unseal SUCCESS, PKI tasks SUCCESS; existing
audit compatibility assertion FAILED at sequence 684, generic redacted error.
Bounded read-only Vault API inspection: file audit enabled at expected path;
log_raw returned as string "0"; KV2/userpass enabled. Configure and verify
currently require textual "false". Do not treat this as successful verification.
Next correction must prove Vault's exact false-option representations, emit the
canonical string form, and accept only proven false representations on read-back;
unknown/true values must remain rejected. No arbitrary bool coercion, audit
disable/re-enable, data reset or custody replacement.
Always cleanup released the run's lock; health 200, initialized/unsealed/leader,
canonical unit ACTIVE. Full standalone/repeat/HA acceptance still pending.

## Power-loss recovery observation (2026-09-27)

After owner restarted .101, the actual React/Wails observer returned terminal
INTERRUPTED, sequence 102, for installer-be9d767e41344a215fc2c9ef54877945
(564s). Vault unit ACTIVE/initialized/sealed, HTTP 503; encrypted custody inputs
remain intact. Next fresh plan must reuse them for unseal, not initialize again.
No terminal success or repeat/HA acceptance asserted.

## Dynamic verifier parser defect: exact correction

Real run installer-faf5ea3d4b99ee18aefb692fa25d27a2 FAILED after 1618s.
Token API/configuration tasks now all SUCCESS. Dynamic verify include completed,
then Ansible aborted before first verifier task: fail_msg was incorrectly a task
sibling, not an assert argument in verify.yml. YAML parsing and dynamic apply
syntax-check did not cover Ansible's action parsing of that included file.
Corrected indentation; added validate-verify-syntax.yml static import_role and
focused task-shape test. Fresh RED OS static syntax PASS, role suite 16 PASS.
Failed parser left transient lock-holder: removed only after exact failed-run,
time-window and flock command/path proof. Canonical Vault remains ACTIVE,
initialized/unsealed, health HTTP 200. No reinit/data cleanup/secret disclosure.
Harness/dev stopped; exact temporary RSA removed. New immutable runtime retry
pending; no terminal success/verify/repeat/HA claim.

## Full verification resumed with corrected immutable runtime

Independent current-worktree QA sidecar completed without service mutation:
Go 584 PASS/29 SKIP test/subtest events (38.221s), vet PASS (2.908s);
frontend lint PASS (12.694s), 67/67 tests PASS (24.452s), build PASS (3.101s).
Fresh helper-synced RED OS full Core: 397 total, 378 PASS/19 SKIP, 1003.475s;
Vault contracts 15/15 PASS (4.344s), catalog/schema reproducibility PASS;
native-dialog helper 3/3 PASS. Secret audit 0 signatures/tracked runtime secrets;
diff --check PASS. Exact QA workspace cleaned and absence confirmed.
Formatting gate is not clean in six pre-existing dirty files under
internal/executionnode: remote_acquisition_workspace.go,
service_install_redis_e2e_test.go, candidate_archive_test.go, remote_builder.go,
run_observer.go, run_observer_test.go. Sidecar preserved these unrelated changes.
These regression results do not establish real runtime/React acceptance.

Supported QA promotion, not in-place mutation: qa-si08-vault-20260927-10,
sha256:3cc0a48f9722f344fd14103b199dd1137b482c1bfa56a723fbf46d09a53af9d5.
Catalog unchanged; guarded isolated-project lock update yields revision
sha256:46c94b17520915df19939b6661b8a108295bff67131ae15617464e0f51d34e9c.
Real React/Wails READY/import/fresh plan approval PASS; plan
plan-705a4c74638ef4e22f497d86, run installer-faf5ea3d4b99ee18aefb692fa25d27a2
RUNNING. Terminal verification/repeat/HA evidence pending. Existing Vault is
preserved, no reset/reinit. .102/.103 read-only SSH accessible with no loaded
Vault units observed. Wails dev overlay ipc.js exception remains separate.

## Owner-authorized exact token format correction

The configure API failure was caused by LF appended to producer admin-token.
Raw token import preserved that byte; HTTP headers rejected it before contacting
Vault. Read-only control removing exactly one LF in memory returned HTTP 200 for
sys/audit, sys/mounts, sys/auth. No token/response body was printed.
Producer now writes exact token bytes without a line terminator. Raw/JSON/age
import rejects CR/LF safely, never trims or rewrites accepted values. Tests cover
raw LF/CRLF/embedded CR/LF, JSON strings and encrypted files plus actual App import
rejection; invalid sources remain unchanged. Synthetic delivery fixture now uses
the producer's exact bytes. RED OS real Ansible recovery proves emitted bytes:
6 tests PASS (367.718s); role contracts 15 PASS (1.104s).
Owner-authorized QA repair writes a separate admin-token-corrected.age after exact
single-LF admission; original ciphertext and receipt are preserved. Corrected
encrypted readback PASS, API GETs all HTTP 200, actual React/Wails encrypted token
and shares import STORED / READY PASS. No new Start/reset in that focused probe.
Go full suite/vet/diff check PASS; catalog/schema reproducibility and syntax-check
PASS; production Wails build PASS (13.813s). Scoped independent DIFF APPROVE,
0 blocking/overengineering; fingerprint
14af436a811bf8e8f37a780d3e07290e56b3b01119d953541adb95f286dcbcaa.
RED OS CGO race PASS (internal/secretfiles, 238.390s); exact QA workspace removed
through qa-sync cleanup. Dev/harness
stopped; exact temporary RSA removed. Existing dev ipc.js exception remains.
Producer correction is not yet published into the immutable runtime; no existing
release mutation. SI08-E terminal apply/verify/repeat/HA PASS still not established.

## New blocker: protected configuration API read after unseal

Run installer-f53a30142211d7456a8a4b76c28937b3 terminal FAILED, sequence 682.
The seed unseal and cluster identity tasks succeeded. The next include enters
configure.yml, whose first protected task reads sys/audit, sys/mounts, sys/auth.
That task failed before configuration mutation. Diagnostic is bounded/redacted:
ANSIBLE_OPERATION_FAILED (ANSIBLE_FAILURE_REDACTED); exact endpoint HTTP status,
TLS/module error and token validity are not proven by this evidence.
Read-only health probe after failure proves HTTP 200, initialized=true,
sealed=false, standby=false, cluster identity present; canonical unit ACTIVE.
Lock release succeeded. No reset/reinit or raw-secret logging was performed.
Required smallest next diagnosis: use existing protected credential flow for
read-only API calls and emit only endpoint/status/error class, never token/body.
Do not treat health as service verify PASS; repeat and HA acceptance remain open.
Harness/dev stopped, exact QA RSA removed with confirmation, helper-synced race
workspace cleaned. SI08-E BLOCKED, implementation uncommitted; unrelated dirty
work preserved. No clean-worktree claim.

## Owner-authorized broker correction: real Start admitted

Password promotion and typed binding retain separate consumption in the existing
pending bucket. An empty pending password map is a no-op after binding/TTL/Core
requirement checks. Promotion consumes password entries only; typed inputs stay
available to BindPendingServiceSecretInputs, with unchanged expiry and exact
descriptor admission. No alternate Start, new persistence or protocol change.
TestPasswordPromotionPreservesTypedInputsForCoreBinding covers typed-only/mixed
inputs, refresh/rebind and missing descriptor rejection.
TestAppDescriptorRefreshAndStartPreparationPreserveTypedInputs exercises the
actual App descriptor seam in clearing and Start non-clearing order.
Focused tests/full Go/vet PASS. Fresh helper-synced RED OS CGO race PASS:
broker 1.208s, App 1.323s; exact QA workspace removed with qa-sync cleanup.
Scoped independent DIFF APPROVE_WITH_CHANGES, 0 blocking/overengineering.
Fingerprint: 4946e0acf241e1e1b9b6c4678bda1c59ec6292a2153bf5f5cc8d7a55ff177571.
PBT-01 nonblocking test hardening applied afterward without a review rerun:
unchanged pending TTL/generation, consumed password and expired typed buffers
wiped; focused regression PASS. Production correction bytes unchanged.
Real React/Wails Start admitted run installer-f53a30142211d7456a8a4b76c28937b3
after READY, encrypted import, fresh planning/approval; now FAILED at the new
configuration API blocker above. Revision unchanged:
sha256:a75031b7d1fb1d54273c8781fc5e4ceb100443f1c72f2038ac56f920e646e73b.
Terminal apply/verify/repeat and HA gates are still pending; dev ipc.js error
remains separate. The previous Start blocker below is historical evidence.

## Fresh-plan Start blocker: typed pending promotion

Real React/Wails READY and encrypted token/shares imports PASS. Fresh plan
plan-a09964168cc5a40c97429e9d for revision
sha256:a75031b7d1fb1d54273c8781fc5e4ceb100443f1c72f2038ac56f920e646e73b
rendered/approved; encryption and PKI passwords PRESENT. Start BLOCKED with
RUNTIME_SECRET_DESCRIPTORS_STALE, no runId returned. A separate real descriptor
query returns RUNTIME_SECRET_INPUT_INVALID. Broker password promotion rejects
the empty password map in a typed-only pending bucket; its normal success cleanup
also clears typed pending inputs before the subsequent typed binding step.
Fix must preserve separate password/typed consumption within the existing broker
and keep exact Core descriptor checks; no new secret store or Start bypass.
No target installation/reset/reinit occurred. Harness/dev stopped, temporary
QA RSA admission removed with confirmation. SI08-E remains BLOCKED, not DONE.

## Real nonvisual encrypted input import PASS

Owner-approved dev-only path selection seam replaces only native picker output.
Existing React handler/Wails method/read/decrypt/descriptor/binding/broker path
executes unchanged; no new exported method or payload from React. Production
ignores QA selection configuration. Actual encrypted admin-token.age and
unseal-shares.age both returned STORED after READY. No Computer Use, new Start,
Vault init/reset/unseal or deployment in this focused probe.
This closes file-input automation, not full SI08-E acceptance. Known dev ipc.js
renderer exception remains and is not reported as clean WebView acceptance.
Focused production/dev import/selection guards and full Go/vet PASS; Wails build
PASS (8.592s), temporary QA RSA admission removed with confirmation.
Independent scoped DIFF review APPROVE_WITH_CHANGES, 0 blocking; NFS-01
nonblocking test strengthened and PASS without another review cycle.
RED OS normal-build CGO race PASS (1.119s); dev-build race unavailable because
GTK3/WebKit2GTK development packages are absent. No QA host package changes.

## Continued import: Computer Use input boundary

Real React/Wails credential PRESENT / READY PASS and the separately targetable
secret picker were reached. No Wails focus crash with the headless-owner helper.
Computer Use set_value failed with UIA cache-property error 0x80070057;
re-observed keyboard/activation attempts did not move focus from the search field.
No blind typing, successful file import, Start, reset or reinit was performed.
Acceptance remains blocked on automation input, not proven Vault failure.
Initialized state, encrypted custody and committed journals preserved.
Temporary QA RSA key removed (confirmed); harness/dev servers stopped.
Dev output contains WebView2 ProcessFailed kind 6 plus existing ipc.js exception;
this attempt is not clean WebView acceptance.

## Supported headless-owner workaround

scripts/qa-native-dialog.cjs temporarily hides the otherwise unused desktop
owner using Wails WindowHide, invokes the unchanged native flow and restores
the window via WindowShow in finally. Native dialogs then appear as independently
returned Computer Use Windows. Three helper tests PASS; real secret-free folder
cancel -> NO_PROJECT -> real GetApplicationConfig READY proves bridge survival.
No production/dependency modification or secret-import bypass. The Vault React
file-selection flow now uses this helper; full import/execution evidence remains
separate. Earlier missing-modal caveats below describe the owner-visible case.

## Native-dialog targeting guard and remaining limitation

QA must select exactly one actual Computer Use Window by both Installer app and
native dialog title. Missing/ambiguous dialog -> NATIVE_DIALOG_WINDOW_UNAVAILABLE;
never activate the disabled owner or synthesize a handle. Runtime-only selector
tests cover exact-object selection and missing/foreign/ambiguous rejection.
Actual target-free, secret-free ChooseProject probe confirms list_windows and
list_apps return only the owner; accessibility exposes the modal as a nested
element beneath the disabled main window. The current API therefore cannot
implement separate modal targeting. No unsafe input was retried. This prevents
repetition of the automation fault but does not close SI08-E import acceptance.
No production/dependency bypass is authorized by this evidence.

## Continuing acceptance — native picker blocker (2026-09-27)

Actual React/Wails Open/credential/READY/Services/Secrets flow reached the first
native file picker for encrypted admin-token input. Accessibility observation
confirmed the standard dialog. Attempting filename entry failed to activate its
captured owner; Wails logged WebView2 `The parameter is incorrect` from
Chromium.Focus/onFocus. The process disappeared and bridge port closed.
One unchanged dev restart recovered READY, but repeated file-selection did not
produce a usable native dialog. No input import success or Start was observed.
No target reset, reinit, unseal or new deployment occurred; custody is retained.
SI08-E BLOCKED at the native Wails file-input/focus boundary, not Vault execution.
Harnesses/dev servers stopped; temporary RSA admission removed with confirmation.
Do not substitute a mock or bypass the supported import method to claim PASS.

## Secrets descriptor wire correction — 2026-09-27

The owner-authorized transport defect is corrected with explicit lower-camel
JSON tags on RuntimeSecretDescriptorOperation/View and regenerated Wails models.
Two exact wire tests cover closed field names, complete data round-trip and safe
UNAVAILABLE output. No Core, secret payload or Vault semantics changed.
Actual React handlers navigate Services -> vault-qa-standalone -> Secrets against
real Wails Go methods: READY, two descriptors, two file-input controls (PASS).
This focused probe did not import files or Start/init/reset/unseal; full Vault
apply/verify/repeat acceptance is still pending, not PASS.
Focused/full Go tests and vet PASS; frontend lint/67 tests/build PASS; Wails
production build PASS (11.257s). Current-source RED OS CGO race tests covering
wire descriptors and pending-output concurrent binding guards PASS (1.080s).
SSH recovered. Exact temporary RSA admission removal confirmed QA_KEY_REMOVED;
the previously pending qa-sync workspace was cleaned through the same helper.
Historical caveats below describe previous attempts, not current gate results.

## External output-list correction and real recovery evidence

Remote race gate did not complete: SSH connection closed, and a fresh 8-second
probe timed out during banner exchange. Do not count race as PASS. Temporary
RSA-key cleanup was issued but not confirmed; qa-sync workspace
/var/tmp/platform-installer-qa-fa6f3340b14d40e69747697502478238 needs cleanup after
SSH recovery. Local dev servers stopped. No target restart/reset was attempted.

Owner-authorized app guard uses the supported private binding resolver after
ListPending, comparing binding/node/runtime/READY and retaining project and
generation checks. No synthetic project host ID is assigned to external nodes.
Focused positive external-context test and 9 concurrent-change cases PASS;
full Go tests/vet and diff check PASS.
Actual React/Wails Result/ListPending returned READY package
805b1d37fb4b8c901369d2901dc8f41d for
installer-6989b0f2fb6c2609515170ece9c9eeb7. Existing delivery flow completed;
only admin-token.age, unseal-shares.age and complete receipt were observed in
secrets/vault-qa-standalone. Contents were not exposed.

Next real Services/Secrets flow failed before opening the native picker.
Actual Wails response keys are Status, ProjectRevision,
DescriptorSetFingerprint, Descriptors, while React expects lower-camel names.
The operation and descriptor structs in app.go have no JSON tags. This is a
separate concrete transport defect, not a secret-input or Vault failure.
Proposed minimal correction: explicit existing lower-camel DTO tags and wire
serialization tests, without changing semantics or revealing raw values.
No correction of this new blocker, import, Start, init or reset was performed.
SI08-E is not DONE.

## Recovery acceptance blocker — external-node list guard

The corrected unseal implementation was published/activated in immutable runtime
sha256:169d75bc64933c0f871efe26f2da36652776025bf9c1e4a9b72b8d8961c7735d,
isolated project revision
sha256:a75031b7d1fb1d54273c8781fc5e4ceb100443f1c72f2038ac56f920e646e73b;
catalog unchanged. Real nonvisual React/Wails opens the project, confirms READY,
sets session-only output encryption password, selects Result and requests pending
outputs. ListPendingSecretOutputs returns PROJECT_CHANGED, reproduced by another
actual binding call with the same EXPLICIT_EXTERNAL/READY context.

app.go post-list guard incorrectly compares SelectedHostID with binding.node.ID.
External selection deliberately omits SelectedHostID; the existing private
binding resolver uses execution.external.hostID. This is not evidence of an
actual project change. Proposed bounded fix: re-resolve and compare private
binding identity while retaining project revision/generation/selection guards;
test external selection success and concurrent changes rejecting results.

No Go fix, output delivery/import, Start, target reset or reinit was performed.
Saved custody and journals remain intact. Development servers stopped. SI08-E
is BLOCKED pending this concrete application-boundary correction. Native file
picker automation was investigated but not reached; no secret contents read.

## Seed identity ordering correction — 2026-09-27

After owner authorization, unseal_member.yml no longer reads cluster_id from
sealed health. It first confirms initialized/unsealed health, requires a
nonempty cluster_id string, then captures seed identity and applies the existing
exact follower identity check. no_log, API TLS, Shamir threshold and custody
semantics are unchanged. No reinit, reset or target unseal was executed.

Focused current-source RED OS: 4 real-Ansible tests PASS (9.358s), each exercising
both native modes. External health/unseal API boundaries use synthetic responses;
production ordering, guards and set_fact/assert tasks execute unchanged. Cases:
sealed seed with absent pre-unseal identity, already-unsealed seed, matching and
mismatching follower without seed replacement, missing/empty post-unseal identity.
Synthetic shares do not leak. Vault contract 15 PASS (0.425s), apply/verify syntax,
catalog/schema reproducibility, full Go tests/vet and diff check PASS.
qa-sync workspace cleaned. This is focused correction evidence, not real
React/Wails acceptance. New runtime publication and retry with existing custody
inputs remain pending; do not reinitialize the seed. SI08-E is not DONE.

## Latest real retry — 2026-09-27

Explicit owned clear PASS (changed=4), focused commit
`72a199143df4c7acb50d0ce77cf439398b32ada6`. Config/PKI/audit/unit identities,
member root/marker and committed journal bytes were preserved.
Bootstrap FULL DIFF APPROVE (zero blockers), fingerprint
`49bb289d7427879f45cc3dcfe3d01f13efcc3bc51f8b6a3cac440277b66a0571`.
Immutable runtime `sha256:e53df4e66364ebbb7fde8653219da12dc77bff92ea527d347a02ed5205291531`
was published/activated through the supported Go path; isolated project revision
`sha256:b48ed2e93df6669c230052a83b7fdf333ba977b141da7f2bd8a3d83504f4702e`.
Catalog identity unchanged.

Actual nonvisual React/Wails readiness, fresh plan, approval and Start passed.
Run `installer-c77432c312f53ac251fc5635ff559915` terminated FAILED, sequence 570.
First failed task creates `/var/log/platform-vault-audit`; init/unseal and
encrypted output delivery were not reached. Post-failure read-only inspection
finds root:root 0755, no immutable attribute, adequate space/inodes and inactive
selected unit. Elevated local Ansible check-mode on that exact directory returns
SUCCESS changed=0. This does not explain the original failure or replace real
acceptance. Exact execution-context error remains to be recovered through bounded
diagnostics. No new full-plan retry or production correction was made.
Temporary RSA QA admission removed; previous unrelated changes preserved.
SI08-E remains BLOCKED; no repeat/HA success is claimed.

Status: IN PROGRESS, owner authorization 2026-09-27. SI08-C/D baseline:
`3e1f711`. Preserved prerequisite work was restored from stash without dropping
the stash. No acceptance success is claimed before actual execution.

## Scope and gates

Use the existing Ansible role, Core plan, generic Go execution service and
Wails/React flow; no new service contracts or infrastructure rules in Go.
Compare the Secrets and Installation/Plan/Result mockup before acceptance:
service inputs remain session-only; encryption password belongs to Plan;
output is fixed at `secrets/<deploymentId>/` in the current project.

1. Verify the current catalog/schema, source bundle and READY runtime;
   publish/activate a new immutable QA release using the supported Go path.
2. Read-only inventory of existing Vault units/data on all targets. No removal
   of unknown Vault state or destructive cleanup without proven ownership and
   the required owner authorization.
3. Standalone 1/1, Raft 3/1, then Raft 3/3: saved authoring, fresh Go/Core plan,
   approval/Start, terminal SUCCEEDED, PKI/apply/verify, encrypted output
   delivery/receipt/ACK, Installer event stream, fresh repeat changed=0.
4. Prove TLS API, audit, KV v2, userpass and three healthy voters; HA leader
   failover, persistent QA KV marker, explicit unseal after restart and healthy
   restoration. Three-host failure must not take down the Execution Node.
5. Standalone Ansible compatibility and mandatory nonvisual React/Wails
   authoring/secrets/Start/event/result evidence using real backend bindings;
   final affected tests, full Core/Go/vet/race, frontend/Wails, reproducibility,
   secret/security audit, applicable independent DIFF gate and cleanup.

## Safety and evidence

Runtime credentials remain ignored and are not logged. No root token/unseal
shares in project, events or reports. Retain recovery material until confirmed
encrypted delivery. Do not run the eight-service final plan here.

Record exact commands/durations, release digest, project revision, run IDs,
terminal results, repeat recap, TLS/mount/voter/failover proofs and cleanup.
On a new contract/security blocker, stop and report the smallest correction;
do not weaken guards or report a timeout as success.

## Current preparation evidence

Supported Go build/publication/activation completed in 1m46.6128876s:
runtime `sha256:d84df0dc93eee8673276981fa94a2d7a20bd6373fa7cffea3a4271fd3216e89d`,
catalog `sha256:a460d77a38b7134f9a1639871eeb925a3ce8d673df3bfa5dcc1a40a22ada86d3`;
Execution Node .101 READY. No Vault units or standard Vault data roots were
observed on .101/.102/.103. No Vault installation/cleanup occurred.

Prepared ignored project: `.runtime/qa/vault-qa-standalone-20260927`, identity
`project-8367edbb5fd3b8cd`. It contains standard inventory/hosts.yml,
inventory/group_vars/all/platform-installer.yml,
inventory/host_vars/node1/platform-installer.yml, ansible.cfg and project.yml.
Desired state: node1 (.101), standalone deployment vault-qa-standalone, member
vault-1, managed CA/profile/scope and deployment-scoped TLS with serverAuth and
clientAuth. No plaintext credentials/token/shares. The existing Go structural
Save committed this state; fresh Core plan `plan-d475ff6fc5697a9651311c21`
returned EXECUTABLE. This is not Start/apply/verify evidence.

Windows Wails production build PASS (25.588s). Current-source offline QA:
Core 351 PASS/4 opt-in skips, contracts 31 PASS, Vault 15 PASS and both
catalog/schema reproducibility checks PASS. UI creation was observed; opening
the fully prepared project through the native picker is still pending because
the automation repeatedly detected concurrent physical user input/window loss.
The owner subsequently confirmed project import and waived visual/manual UI
acceptance. Nonvisual React/Wails integration is mandatory for every service
under the updated common acceptance policy; direct Go execution is supplementary.

## Current Start blocker and correction

The imported project acquired an additional unplaced Kafka deployment `asd`.
It is preserved unchanged. A separate Vault-only QA project
`.runtime/qa/vault-qa-isolated-20260927`, identity `project-76b046511af5faed`,
was created through the existing Go structural Save lifecycle. Fresh plan
`plan-a51259aa498254191869f4f8` is EXECUTABLE. Start stopped before lease/launch
with `PKI_STORE_PASSWORD_RUNTIME_UNSUPPORTED`: the v4-only capability was
incorrectly required to advertise legacy payload v2 for PKI. The owner approved
the bounded Go gate correction admitting the closed typed v4 payload, which
already carries pkiStorePassword. No public protocol/schema change. Focused
regression covers successful v4-only PKI plus conditional typed input admission
and missing PKI rejection before lease/Start; existing v2 tests are preserved.

Current correction gates: focused PKI/typed Start tests PASS; full
`go test ./...`, `go vet ./...` and `git diff --check` PASS. Production
`wails build -nopackage -clean` PASS (12.686s).

Acceptance BLOCKED at real React/Wails automation prerequisite: the existing
`frontend/e2e/ui-01e4.spec.ts` runs the Vite `?qa=e4` mock and is not a real
Wails bridge test. The rebuilt desktop application launches, but no localhost
CDP endpoint is exposed when using WebView2 remote-debugging environment flags,
including debug/native-loader builds and explicit child environment injection.
No mock/direct-Go result is substituted for the new mandatory gate. A bounded
real-bridge automation setup is required before continuing this acceptance;
no production IPC/debug endpoint or bypass was added. Vault Start has not
been retried after the correction and no Vault installation occurred.

### Real bridge enabled; new rendering blocker (2026-09-27)

The preceding automation prerequisite is resolved using standard Wails dev
server on loopback with headless installed Edge, without production changes or
dependency edits. See `qa-react-wails.md` and `scripts/qa-wails-bridge.cjs`.
The real React credential form saved the SSH key in session; React readiness
returned READY; React CreatePlan reached PLAN_REVIEW with fresh authoritative
plan `plan-a51259aa498254191869f4f8`. The native picker alone was substituted
with a fixed QA root calling the actual App.OpenProject.

SI08-E now BLOCKED on Plan rendering: Go `installationPlanView` copies empty
`DependsOn` with `append([]string(nil), ...)`, serializing it as JSON null.
React `InstallationPage.tsx` reads `action.dependsOn.length` unconditionally,
throwing `Cannot read properties of null (reading 'length')` and blanking the
page. The smallest correction is consistent empty-array presentation for
action dependency/target lists with real-bridge/JSON regression, not a Core
plan rule change. Start was never invoked. An additional startup error from
the Wails development runtime (`reading 'nodes'` in `/wails/ipc.js`) was
observed; the real bridge remained callable, so it is recorded separately and
not claimed resolved. No service installation or acceptance PASS is claimed.

### Plan rendering resolved; v4 lease serialization blocker

Owner-approved presentation correction copies Targets/DependsOn to non-nil
arrays. New Go JSON regression covers both empty fields; focused tests, full
Go suite/vet and diff check PASS. Real React/Wails now renders all PKI/apply/
verify phases, saves/acknowledges the output encryption password, approves the
plan and admits the PKI password. Runtime-only RSA PEM QA identity is used
because the credential form deliberately does not admit OpenSSH ED25519; the
original established Execution Node identity is unchanged.

Actual React Start returns BLOCKED / LEASE_PAYLOAD_INVALID, with no runId.
Go v4 lease serialization assigns a nil map to an interface and then compares
that interface to nil, so `runtimeSecretValues` remains a typed nil and is
serialized as JSON null. Python's closed v4 payload correctly requires an
object (`dict`) and rejects it. The minimal follow-up is a typed nil-map check
before serialization and a JSON wire-shape regression for v4 with no password
requirements. No runtime schema or secret validation should be relaxed.
SI08-E remains BLOCKED here; no Vault install/init occurred.
The owned Wails/Vite servers were stopped and the exact temporary RSA public
key entry was removed from the .101 QA account; other authorized keys and the
established transport identity were preserved. Ignored QA inputs remain local
for a subsequent owner-authorized retry.

### v4 wire shape resolved; private manifest blocker

Owner authorized the exact nil-map correction. Go now checks the typed
RuntimeSecretValues map directly and emits an empty JSON object when nil.
The existing v4 regression asserts `{}` and rejects a `null` wire value.
Focused lease/PKI tests, `go test ./...`, `go vet ./...` and
`git diff --check` PASS. No public contract or Python payload rule changed.

Actual React/Wails retry: session PRESENT, readiness READY, Plan rendering and
approval PASS, output encryption and PKI inputs admitted. Start returns
BLOCKED / EXECUTION_MANIFEST_INVALID without runId. No Vault install/init.

Read-only diagnosis against active immutable runtime d84df0dc confirms that
Core's private runtimeSecretInputs includes presentation field displayLabel.
The closed execution_secret_lease typed-requirement validator excludes it.
The same bounded synthetic descriptor produces EXECUTION_MANIFEST_INVALID
with displayLabel and is accepted without it. No secret payload was printed.
Recommended minimal correction: omit the presentation-only field from the
private producer projection and add producer-to-consumer regression proof;
retain the public display label and all private identity/reference fields.
This new blocker requires owner direction; no correction or review was run.

### Private descriptor correction accepted; controller ownership blocker

Owner authorized omitting displayLabel from private runtimeSecretInputs only.
Public descriptors retain their labels. The focused producer-to-real-consumer
regression admits both generated requirements and rejects reintroduced extra
displayLabel. Focused plan tests 21 PASS; Core 351 PASS/4 skips; full Go/vet,
catalog/schema reproducibility and diff check PASS. No schema widening/review.

Supported QA promotion built/published/activated immutable runtime
sha256:a668dca34624ba39bc289efbe577b6b1665488d9e7ce416c8c910d65d0139c96;
catalog digest unchanged. Guarded lock-set update touched only the isolated
Vault QA project, revision
sha256:4a72ae597dff33eb1a7471f178e97e9a1fb6a9a61d2d09cbd281362da7147745.
Original imported project was not rewritten.

Actual React/Wails credentials, READY, fresh Plan rendering/approval and Start
PASS admission. Run installer-7c88e83cb1124ca91cfce021861d4b01 was created, but
terminal result is INTERRUPTED, sequence 2 (CONTROLLER_INTERRUPTED).
Exact systemd unit reports EXECUTION_CONTROLLER_FAILED: OUTPUT_ACCESS_DENIED.
Read-only stat proves execution root mode 0700/UID 1001, while its new run
directory is mode 0700/UID 0. Detached controller runs as root; output storage
validates the existing root's owner against its effective UID before creating
secret-outputs. No Ansible Apply/Vault init occurred. New ownership blocker
requires owner direction; do not relax owner checks or mass-chown runtime state.

### Owner-approved execution storage ownership correction

SSH remains platform-automation; sudo launches the privileged controller. Root
SSH/password login is not required. Supported runtime activation prepares storage
with the existing no-follow `_directory` helper under that same effective UID,
mode 0700. Foreign ownership still fails closed; no automatic chown/chmod repair.
On .101, no running/activating owned run units existed. A held-directory fchown
corrected only execution root from UID 1001 to root:root; descendants untouched.
Controller preparation failures now publish FAILED only after manifest/run
identity checks, retaining the committed run and invoking normal lease cleanup.

Focused lifecycle 39 PASS; output storage 25 PASS (creation/idempotence, foreign
owner rejection); activation ordering test PASS. Full Core 353 PASS/4 skips,
Go suite/vet, frontend 67/lint/build and catalog/schema checks PASS.
New immutable runtime
sha256:c1727d16eca98bcb054bbe4665275776df5d0adc8ecbd202961346143455de09
activated with unchanged catalog; isolated QA project revision
sha256:53b5f7190c696541e03ff4a13d2f9cec79541c121fd491e7aad4be2f518db709.
Real React/Wails run installer-95d2c1f3ad92343e09ae8da684a1ef78 reaches RUNNING
and PKI task events. Terminal FAILED at sequence 338 on Vault closed-input
validation, not controller startup. PKI Apply completed; Vault install/init,
Vault Verify and output delivery did not complete.

New blocker proof (read-only, no target SSH): manifest role variable apiPort
is Python int 8200; all 21 expressions pass against directly typed defaults and
Core variables. A local Ansible play reproducing runtime_role_variables set_fact
fails expression index 6: platform_vault_api_port is integer. The generic fact
transport templates numeric values as strings on this Ansible runtime.
Keep Vault's integer validation strict; correct generic typed fact admission
with focused native-type and real Ansible regression after owner authorization.
No autonomous change to global templating semantics or service validation.
Production Wails build PASS (11.33s); generated bindings formatted using the
repository command; final diff check PASS. Owned Wails/Vite/browser QA stopped,
the exact temporary RSA authorized-key entry removed, and the current-source
remote QA workspace cleaned. Run journals/output custody remain preserved.

### Typed fact correction experiment: additional coercion boundary

Owner authorized generic Core-to-Ansible type preservation. Local-only RED OS
probes show whole-mapping set_fact args preserve integer/number/nested types,
unlike the original scalar loop. However the built-in action in non-native mode
also converts string "false" to boolean. The new actual-role regression covers
integer, number, boolean, numeric string, boolean-shaped string, list/map/null,
empty mapping and invalid/missing-host mapping. Native=True case PASS;
native=False case BLOCK on string identity; empty and invalid-input cases PASS.
This prevents claiming a universal typed fix from the numeric-only probe.

Experimental production task modification reverted; focused regression remains
uncommitted. No global Jinja option, new plugin, bundle publication, target SSH
or service execution was introduced. Owner decision needed for a narrow typed
fact action adapter if exact scalar types must be retained independently of
Ansible native mode. Global native mode would be a wider compatibility change.

### Owner-approved typed fact adapter

platform.core.apply_runtime_role_variables is an action-only adapter. It reads
the trusted current-host mapping and returns a deep copy as facts without
scalar templating or boolean-string coercion. No service rules, Go dependency,
target call, module transfer or file writes. Input mapping guards retained;
task arguments and names outside valid platform_* identifiers fail closed.
no_log applies on success/failure; changed=false; no cacheable opt-in.
Global Jinja configuration and Vault validators unchanged.

Real local-only Ansible regression 3 PASS with native=False/True, including
integer/number/bool, numeric/boolean-shaped strings, nested list/map/null, empty
mapping and invalid/missing host/name guards. Service/PKI contracts 11 PASS;
full Go suite/vet PASS. Full Core 356 PASS/4 skips and catalog/schema checks PASS.
Supported promotion published/activated immutable runtime
sha256:0c0248c19a457d647a060c8c72b1ca1fa5999099f02a0e43b55239b563b15f1a,
catalog unchanged; isolated QA project revision
sha256:a0a0d1d3b100cd3883bc7baff833b9c7f9d679119af31c8ed8e1288e83c948bc.
Actual React/Wails credentials, READY, fresh Plan/approval and Start admitted run
installer-2e83aa4e51d88886abc0827217e6abae. PKI and the previously failing
Vault closed-input guard passed. Repository package installation completed
after a long active download; no plan interruption/fallback was introduced.
Partial package/account/PKI/config provisioning occurred. Terminal FAILED at
sequence 586; no active Vault units observed after failure. Vault bootstrap,
verify, protected delivery and repeat acceptance remain unproven.

New blocker: provision.yml configuration and systemd template loops declare
loop_var vault_member, but changed-member tracking reads item.item.id. Ansible
register entries expose item.vault_member.id instead. Local-only synthetic
template loop proof PASS: ansible_loop_var == vault_member, vault_member.id
exists and item is absent. Failure task: Record members whose Vault
configuration changed. The systemd tracking task has the same latent defect.
Owner-approved correction: retain item.item.id in tracking and normalize the
configuration/systemd/audit template loops to default item. vault_member remains
only a task-local template alias. Real local-only Ansible regression renders all
three actual templates for three members: first render tracks all three, repeat
tracks none, one-member configuration/systemd change tracks only that member
without duplication. Both registered result collections prove item.id identity.
Focused regression PASS on RED OS (1 test, 13.340s).
The PKI copy loop uses default item and must retain its existing item.item[0].
No generic lifecycle/service branch or additional architecture review was added.

## Owner-authorized standard loop correction acceptance

Core suite: 357 PASS / 4 skips (361 total, 36.166s). Full Go tests/vet,
catalog/schema reproducibility and diff check PASS. Temporary RED OS source
workspace was removed. Supported promotion activated immutable runtime
sha256:66ed3423ed150cb8fa46af19c0bdcd120a4066a4ffcd78c3367d28b76ac24e67;
catalog unchanged. Only isolated QA project lock changed; saved revision
sha256:7e46eb26b4fa9e569a8670c11f98413d91f575b9c8609a182faa59bb4e34062b.
Actual React/Wails credentials, READY, fresh Plan/approval and Start admitted
installer-ff1844b73c5fd429dbf4c7b0c9243cbe. Both corrected tracking tasks passed;
systemd tracking SUCCESS at sequence 586, seed start CHANGED at sequence 592.
Terminal FAILED at sequence 600 during verified TLS API readiness.

New independent blocker: Vault unit auto-restarts with ExecMainStatus=1 and
permission denied. The installed unit points at
/etc/platform-vault/vault/vault-1/vault.hcl. Parent deployment directory is
root:root 0750; member directory is platform-vault:platform-vault 0700 and
configuration is platform-vault:platform-vault 0600. Read-only test as the service
account cannot read configuration (exit 1): parent traversal is denied.
provision.yml currently creates deployment-level config/data/log directories
root:root 0750. No permission guard was weakened and no new correction was made.
Vault init/unseal, verify, encrypted output delivery and repeat remain unproven.
React/Wails automation was stopped and its temporary QA authorized key removed.

## Owner-authorized service parent traversal correction

Deployment config/data/log parents retain root ownership and mode 0750, with
group platform_vault_group instead of root. Member directories and private
files retain their existing ownership and 0700/0600 bounds. Existing no-follow
and owner preflight guards are unchanged; no public access or service write to
the deployment parents is granted. This remains ordinary standalone Ansible.
Focused RED OS root/local-only tests: 2 PASS (10.088s), including actual file
tasks, service-account reads of configuration/private key, denial of parent
write, exact owner/group/mode, and unchanged repeat changed=0. Vault suite 15
PASS; Core 358 PASS/5 skips (363 total, 36.581s). One permission test requires
root and skips in the non-root full suite; its separate sudo run passed.
Full Go suite/vet, catalog/schema reproducibility and diff check PASS.
Supported promotion activated immutable runtime
sha256:c8952a109ac1774cc896e5d195a5908e95d371f385ec5891317436eef38789df;
catalog unchanged. Isolated project revision:
sha256:a0715ee26c2ef8475562a26545fe3859f4dec112860560ce3ffb04862672cc78.
Actual React/Wails credentials, READY, fresh Plan/approval/Start admitted
installer-b095002168ac83f7fb1aa9289f7120cb. The corrected parent is UID 0,
GID 976, mode 0750; service account reads configuration (exit 0). Unit ACTIVE /
running with ExecMainStatus=0. Previous permission blocker is resolved.

Terminal FAILED at sequence 612; redacted bootstrap assertion failed at 606.
Local-only synthetic execution of the two active bootstrap tasks reproduces
the failure with a valid token/list response (exit 2). Changing only synthetic
dictionary accesses from .keys to ['keys'] makes the same test PASS (exit 0).
This identifies a dictionary attribute/method collision in bootstrap.yml;
no production bootstrap correction was made in this permission change.
Verified TLS GET /v1/sys/init returns initialized=true. Existing output identity
loader resolves the exact run/deployment custody package; existence-only checks
show init-response.json/admin-token/unseal-shares all absent. No credential
contents were read or logged. Initialization succeeded but custody persistence
was not reached. Do not blindly retry or reset the initialized QA member.
SI08-E is BLOCKED on this new bootstrap/custody defect. A next bounded fix must
use explicit dictionary indexing for the keys field, with focused regression;
restarting acceptance also requires owner-authorized cleanup/reset of the exact
owned QA member because required bootstrap material is unavailable through the
approved custody path. Other services/projects must remain untouched.
Temporary QA source workspace/key and React/Wails automation were cleaned.
No verify, protected output delivery or repeat acceptance PASS is claimed.

## Bootstrap correction plan review

Initial independent FULL PLAN review returned BLOCK on SI08-E-PLAN-01:
first-init persistence ordering/durability was not concrete enough. Owner
accepted correction. Revision 2 is documented in
[bootstrap correction plan](service-install-08e-bootstrap-correction.md), with
immediate minimal recovery persistence, explicit durability, validated pair
before cleanup and a declared pre-durability operator-recovery boundary.
The single independent targeted recheck returned APPROVE: SI08-E-PLAN-01
OPEN -> RESOLVED at PLAN level, zero blocking findings, zero overengineering
findings. Reviewed plan SHA256:
bc65e56c6fea4455edbc8209ffdef39bfb749ed90b935587755e5c8e8165c39c.
Implementation/fault-injection/acceptance evidence remains required; this is
not a DIFF or runtime PASS. SI08-E-PLAN-02 remains the
separate identity/safe-mechanism prerequisite for reset; no reset is authorized
by review. No production bootstrap implementation changed during plan review.

## Bootstrap correction implementation — local/synthetic gates

Owner authorized implementation of approved revision 2. bootstrap.yml now
copies the minimal response immediately after init using explicit ['keys'],
verifies private regular bounded files and readback, and synchronizes recovery
before validation. Existing token/shares conflicts are checked before completing
the pair. Both saved files are checked/read back/synchronized before recovery
removal; the directory is synchronized after removal. Existing file-input paths
also use explicit keys indexing. No schema/protocol, generic lifecycle, provider
or helper-plugin changes. Coreutils sync support is checked before init.

Final focused real-Ansible synthetic suite: 6 PASS (213.153s), covering both
native modes, minimal-only persistence, interruption/reopen and partial pair,
malformed/missing fields, conflicts/no overwrite, readback/sync/cleanup failures,
no reinitialization on recovery, unchanged repeat changed=0 and synthetic secret
non-leakage. Vault contract suite 15 PASS (0.953s), including exact task ordering.
Independent QA full Core suite: 364 PASS/5 skips, 369 total, 238.129s; no failures.
Full Go tests/vet, catalog/schema reproducibility, standalone apply syntax-check
and git diff --check PASS. Syntax-check used a localhost inventory and reported
the expected unmatched platform_targets warning; no target service was invoked.

No actual Vault bootstrap values were inspected. Temporary source workspaces
and QA logs were cleaned. The approved plan remains the reviewed revision 2;
these are implementation/test facts, not a new architecture review verdict.
No new runtime was published, no isolated project lock changed and no real
React/Wails retry was performed during this correction. SI08-E acceptance is
still BLOCKED on its already-initialized QA seed without custody material.
SI08-E-PLAN-02 identity reconciliation and a concrete safe quarantine/reset
mechanism, with separate owner authorization, remain prerequisites. No reset,
run-journal/package cleanup or mutation of unrelated services was performed.
Implementation remains uncommitted with preserved earlier/unrelated changes;
SI08-E is not marked DONE.

## 2026-09-28 HA 3/3 completion and recovery acceptance

The subsequent owner-authorized corrections and immutable QA release
`qa-si08-vault-20260928-16` (`sha256:fd43413180b166e3bd439eb5916d5d98094cf2e98d6e15c2b6320ba8fc66c3e4`)
resolved the follower-loop and cluster-wide mount races without changing the
service contract. Catalog digest remained
`sha256:a460d77a38b7134f9a1639871eeb925a3ce8d673df3bfa5dcc1a40a22ada86d3`.
The HA 3/3 project's saved revision was
`sha256:78e13c9ebc0663e13ad59cb38af108300e917a5276cf185e95effc8be3d77b7e`.

Real React/Wails bridge exercised project open, READY check, encrypted input
selection, fresh plan, approval, Start, event observation and Result. First
successful 3/3 run: `installer-d47eaabb277d6ae029eaa4bcd45a1d79`, 1879s,
SUCCEEDED, PKI/apply/verify SUCCESS at event sequences 175/1057/1365,
697 SUCCESS, 163 SKIPPED, 0 CHANGED, 0 FAILED, terminal sequence 1366.
Fresh strict repeat: `installer-bc5136d6f92f24e8b28ab57ea25dff4a`, 2335s,
SUCCEEDED, identical PKI/apply/verify sequences and task counts, terminal
sequence 1366. Both journals had zero sequence gaps and no task-observability
degradation; neither repeat produced a new protected output package. The
earlier HA 3/1 strict repeat `installer-6bc5e5fccb90d4eb458c926decc8026b`
also completed SUCCEEDED with 0 CHANGED and 0 FAILED.

Validated HTTPS health on node1/.101, node2/.102 and node3/.103 showed the
same Raft cluster ID, all initialized/unsealed, and one active/two standby.
Authorized TLS API checks proved file audit, KV v2, userpass and exactly three
voters. A fixed nonsecret QA KV marker was written and read. Vault's supported
`POST /sys/step-down` transferred leadership from node1 to node2 (HTTP 204);
the marker remained readable. Only the identity-proven node1 `vault-hb-1`
systemd unit was restarted. Its post-restart health was initialized and sealed
(HTTP 503). The already protected two shares explicitly restored unsealed
health. Afterwards node2 remained active, node1/node3 standby, all three
healthy; the marker was readable through both leader and restarted node1;
membership still showed 3/3 voters. No reinit, Raft data reset, or unrelated
Vault unit restart occurred.

Final local gates: `go test ./...`, `go vet ./...`, frontend 67 tests, lint,
build, and `wails build -nopackage -clean` PASS. RED OS Vault role 22 tests,
catalog/schema reproducibility and standalone Ansible apply/verify syntax-check
PASS. Sequential full Core suite: 397 tests OK, 19 skipped, 458.414s. A bounded
journal allow-list audit of both 3/3 runs and HA 3/1 repeat found zero forbidden
raw result/secret fields. RED OS race remains a separate resource gate: initial
parallel test and first sequential `internal/secretfiles` test were killed by
Linux OOM while other accepted services remain active on .101. A bounded
`GOMEMLIMIT=512MiB GOGC=20 GOMAXPROCS=2 -p 1 -parallel 1` retry still reduced
available host memory to 36 MiB at ~1.6 GiB test RSS and was explicitly
stopped before another OOM. Focused Vault-input race PASS; `runtimesecret` and
`executionnode` race PASS, but full `secretfiles` race is NOT PASS. No swap was
enabled and no neighboring service was stopped for QA. Temporary QA SSH
admission was removed from all three hosts; Wails/Vite were stopped. The
exact temporary source QA workspace was removed and post-test TLS health still
shows three initialized/unsealed members with node2 active.

The final race gate was completed without changing target services or swapping.
The largest individual age test also OOM-killed on .101 at about 1.67 GiB RSS,
confirming that its available memory was insufficient. Instead, the
current-source `internal/secretfiles` package was compiled on .101 with
`CGO_ENABLED=1 go test -p 1 -c -race -o secretfiles-race.test
./internal/secretfiles`. The one Linux ELF test binary was copied to .103;
source and destination SHA-256 matched. Both hosts report RED OS 8.0.3 x86_64,
and .103 had 3.2 GiB available memory. Its full package test run used
`GORACE=halt_on_error=1 ./secretfiles-race.test -test.parallel=1
-test.count=1 -test.timeout=10m` and returned `PASS`, exit 0. No Go, compiler,
source tree or dependency was installed on .103. The binary and both exact QA
workspaces were removed after the test; post-test TLS health on .103 remained
initialized/unsealed/standby. The full affected RED OS race gate is PASS, not
waived, and SI08-E technical acceptance is DONE. Repository cleanliness and
earlier shared-worktree changes are separately tracked in CURRENT_STATE.md.
# Current acceptance interruption: QA VM powered off (2026-09-27)

Release qa-si08-vault-20260927-11, artifact
sha256:41c8d8a6e287dc69da063cba2f4dacfe081832ee38a6d02c52b4715f1cf6701d,
activated through supported QA promotion. React/Wails accepted both encrypted
inputs and started plan-d773b7fc52a8168128fad5c4 at saved revision
sha256:0632608cc975dda517e1d7dfa3da12fad0fd9332194542962a577a6c17def598.
Run installer-be9d767e41344a215fc2c9ef54877945 last observed RUNNING at
sequence 101 (PKI persistent directory preparation). VirtualBox reports .101
powered off at 17:58:17 UTC. .102/.103 remain accessible. No terminal result
is asserted; reconnect/recovery must inspect the same authoritative run before
any fresh Start. No reset/reinit or deletion of Vault data/custody/journals.
File audit/KV2/userpass read-only checks passed before outage; log_raw=false
not yet proven. Standalone complete/repeat and HA acceptance remain pending.
