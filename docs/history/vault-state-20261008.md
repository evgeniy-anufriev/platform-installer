# Historical state snapshot — 2026-10-08

Historical evidence only. Statements such as NEXT, NOT STARTED and DONE below
describe their original checkpoint and may be superseded. Read
[CURRENT_STATE.md](../../CURRENT_STATE.md) for current status and authorization.
Original section text is preserved; relative Markdown destinations are relocated.

## SI08-F Vault endpoint HA technical acceptance DONE (2026-09-29)

New managed 3-host project `project-e74f53b99dd648d4` pinned to immutable
runtime `sha256:9b0beb40e91b1a1beb20d14096ecd6a45c09274053b6f0bdf412a8424e7a6e3c`.
Canonical project revision stayed
`sha256:5e9c6fc52f0c760a15083b797831f4122ca87d17426f14c277dea07f0a65e6cb`.
Real nonvisual React/Wails opened the project, imported protected Vault inputs,
built/approved plan `plan-7ef0fd3def229115d95c955f`, started and observed
both runs through the supported Wails Go methods. Initial run
`installer-56f9aa6637457b0bcf119b6b3abfa0f4` SUCCEEDED in 35m55s;
strict repeat `installer-06510ac6068d9b7a695599d14850d32e` SUCCEEDED
in 40m54s, with all nine actions SUCCESS, 0 CHANGED, 0 FAILED and no event
sequence gaps. Repeat task counts: 1564 SUCCESS, 427 SKIPPED.

Post-initial-run audit found that new project BIND serial 1 equaled the old
served zone's serial 1; secondaries had not transferred the new content. The
explicit audited `recover_dns_lifecycle` operation used prior fingerprint and
three observed SOA serials to advance the persistent new-project serial to 2.
All three DNS nodes then answered the endpoint FQDN with VIP 192.168.56.121,
SOA serial 2. No manual zone file edit or automatic cross-project state
adoption was used. This is an explicit QA migration, not normal apply behavior.

Three current Vault units are active and unsealed. HAProxy has identical
three-target backend fragments on all nodes, validates with `haproxy -c`,
and uses `ssl verify required` with endpoint `verifyhost`. File audit, KV v2,
userpass, three Raft voters, authenticated KV through DNS/VIP, leader
step-down, active-node loss, marker continuity and restored/unsealed 3/3
cluster all PASS. Core full 416 OK (19 skips); affected BIND/HAProxy/Vault,
Windows Go/vet/frontend/Wails, RED OS affected race, catalog/schema and
secret-event audit PASS. Six exact remote QA workspaces removed. Full evidence:
[SI08-F](../work/vault/service-install-08f-vault-endpoint-ha.md). SI09 has NOT started.
The SI08-F source, runtime, Installer and QA changes are recorded in focused
commits `f23fb9a`, `d1c0612`, `d1df02d`, `c6f066b`, `2b67ed8` and
`9773413`. SI09 still requires a separate owner request.

## SI08-E Vault technical acceptance PASS (2026-09-28)

Initial real React/Wails 3/3 run installer-810aa4cf27d26af17702df266bcf9959
FAILED after 1674s, terminal sequence 1040. PKI PASS; bootstrap started three
members, but cluster-wide file audit enable ran concurrently on three hosts.
One POST succeeded and two FAILED at task sequence 1000/1002 after all three
had read the mount as absent. No Raft reset or data deletion occurred.
The failed-run bootstrap package was delivered/ACKed encrypted through real
React/Wails into secrets/vault-qa-ha33/ and retained for safe recovery.

Owner-authorized bounded correction: configure.yml admission now runs only on
the canonical seed inventory host under the existing deployment lock. No new
cluster state model, protocol or TLS bypass. Fresh RED OS Vault suite 22 PASS
(3.078s), including real Ansible Conditional 1/1 and 3/3 host gating.
Catalog/schema reproducibility, verifier syntax, Go full suite/vet PASS;
helper QA workspace cleaned. Immutable release qa-si08-vault-20260928-16
published/activated READY with digest
sha256:fd43413180b166e3bd439eb5916d5d98094cf2e98d6e15c2b6320ba8fc66c3e4;
catalog unchanged. HA 3/3 project advanced through guarded CAS, revision
sha256:78e13c9ebc0663e13ad59cb38af108300e917a5276cf185e95effc8be3d77b7e.
Fresh real React/Wails READY/encrypted imports/plan/approval/Start:
plan-a15dd43ccacbf164e776c818,
run installer-d47eaabb277d6ae029eaa4bcd45a1d79 SUCCEEDED in 1879s
(31m19s), terminal sequence 1366. PKI/apply/verify SUCCESS at 175/1057/1365.
Task journal: 697 SUCCESS, 163 SKIPPED, 0 CHANGED, 0 FAILED, no sequence
gaps or observability degradation. Cluster-wide configure ran on seed only;
followers skipped it. No new bootstrap package. Validated TLS health on
.101/.102/.103: initialized and unsealed, one active/two standbys, same
cluster ID; authorized API shows file audit, KV v2, userpass and 3/3 Raft
voters. A distinct fresh React/Wails strict-repeat run
installer-bc5136d6f92f24e8b28ab57ea25dff4a SUCCEEDED in 2335s
(38m55s), terminal sequence 1366. PKI/apply/verify SUCCESS at 175/1057/1365;
697 SUCCESS, 163 SKIPPED, 0 CHANGED, 0 FAILED, no sequence gaps or
observability degradation. Result NO_NEW_PACKAGE.

Protected installer-side token was used transiently for bounded TLS QA. File
audit, KV v2, userpass and 3/3 voters PASS. Fixed nonsecret KV marker was
written/read, leader stepped down from node1 to node2 via Vault API (HTTP 204),
and marker remained readable. Exact node1 vault-hb-1 unit restarted; health
observed initialized/sealed HTTP 503. Two protected shares explicitly unsealed
it (progress 1 then sealed false). All three returned unsealed/healthy, node2
active and node1/node3 standby; marker persisted, including read via restarted
node1; 3/3 voters remained. No other Vault deployment unit was restarted.

Temporary QA SSH admission removed exactly once on .101/.102/.103; owned
Wails/Vite stopped. Windows Go suite/vet, frontend 67/lint/build, production
Wails build, RED OS Vault role 22, catalog/schema reproducibility and standalone
Ansible apply/verify syntax-check PASS. Full RED OS Core suite 397 OK with 19
skips (458.414s). Journal allow-list audit for both 3/3 runs and 3/1 repeat:
0 forbidden fields. Initial parallel Core/race attempt overloaded .101;
sequential race still hit OOM (test process killed at ~1.65 GiB RSS with
other services active). A `GOMEMLIMIT=512MiB`, `GOGC=20`, one-worker retry
also reached only 36 MiB host memory available and was explicitly stopped
before another OOM. Focused RED OS race for Vault input parsing PASS;
`internal/runtimesecret` and `internal/executionnode` race PASS. The single
highest-memory age test also OOM-killed on .101 (~1.67 GiB RSS), confirming
that node cannot safely run the package while neighboring services stay active.
The current-source `internal/secretfiles` race binary was built on .101 with
`CGO_ENABLED=1 go test -c -race`, transferred as one ELF artifact to .103,
and SHA-256 matched before execution. Both nodes are RED OS 8.0.3 x86_64;
.103 had 3.2 GiB available and no Go/toolchain install was needed there.
The complete package test binary ran on .103 with `-test.count=1` and the race
detector enabled: PASS, exit 0. This closes the full affected RED OS race gate
without touching other deployments, enabling swap or waiving any test.
Both exact temporary QA workspaces were removed. Post-test TLS health still
shows the HA node on .103 initialized/unsealed/standby. SI08-E technical
acceptance is DONE. Pre-existing unrelated worktree changes remain; do not
claim a clean repository or start SI09 automatically. Runtime swap masks on
QA hosts remain only until reboot to keep active Vault nodes compliant; no
permanent host policy change was made.

## SI08-E HA 3/1 strict repeat PASS (2026-09-28)

Fresh real React/Wails plan/approval/Start/observe/result run
installer-6bc5e5fccb90d4eb458c926decc8026b SUCCEEDED in 2081s (34m41s),
terminal sequence 942. Saved revision and release -15 unchanged.
PKI/apply/verify action SUCCESS at 149/761/941. Authoritative task journal:
361 SUCCESS, 105 SKIPPED, 0 CHANGED, 0 FAILED; zero sequence gaps and no task
observability degradation. Result READY/NO_NEW_PACKAGE. No reset/reinit.
HA 3/1 strict repeat acceptance is closed. HA 3/3 and final failover/restart,
service/full regression gates remain pending; SI08-E overall is NOT DONE.

## SI08-E follower recursion corrected; HA 3/1 resumed (2026-09-28)

Owner-approved narrow correction removes the redundant self-referential
vault_member vars mapping in bootstrap_follower.yml; nested unseal inherits
the existing outer loop member. RED OS Vault role suite 21 PASS (2.535s),
including real Ansible Templar identity/endpoint checks for co-located and
distributed followers. Catalog/schema reproducibility and verifier syntax PASS.
Go full suite/vet PASS; helper QA workspace cleaned; diff check PASS.
New immutable release qa-si08-vault-20260928-15 published/activated READY:
sha256:c6a54fca6cede1c53b935f828accb75bf5413e97c167e083674603efc7fc4f03.
Catalog unchanged. HA 3/1 lock advanced through guarded promotion CAS;
saved revision sha256:ddf3f1e2c8248810ae69c30b08a963f3b00a7061f71a72d89fa434a9004f70e4.
Previous failed-run bootstrap package delivered/ACKed through real React/Wails
into secrets/vault-qa-ha31/ as encrypted admin-token.age/unseal-shares.age.
Both files imported through actual React handlers into the runtime-only session.
Fresh plan plan-c0ccd228d15b7c1481d0b0f1 approved; real React/Wails Start:
installer-1fc2dacbcb428c7ebf2375f981086e12 SUCCEEDED in 2160s (36m),
terminal sequence 942. PKI/apply/verify SUCCESS at 149/761/941.
Task counts 367 SUCCESS, 98 SKIPPED, 1 CHANGED, 0 FAILED; no sequence gaps
or observability degradation. Single change starts previously unstarted follower.
Three HA units ACTIVE; TLS health initialized/unsealed, one leader/two standbys,
same cluster identity. Standalone remains ACTIVE. No reset/reinit.
Result READY/NO_NEW_PACKAGE. Correction evidence:
docs/work/vault/service-install-08e-follower-unseal-fix.md. Strict changed=0 repeat and
HA 3/3 still pending. Narrow correction committed as a3e58ab. Owned dev/harness
stopped and temporary session RSA admission removed. Other existing worktree
changes remain outside that focused commit; no overall clean/DONE claim.

## SI08-E HA 3/1 retry blocked by recursive follower variable (2026-09-28)

Owner-authorized swapoff alone did not persist even within the boot:
systemd reactivated dev-zram0.swap on all three QA hosts. Applied reversible
runtime masks for dev-zram0.swap, systemd-zram-setup@zram0.service and
dev-sda3.swap, then swapoff; /proc/swaps header-only verified on all hosts.
No fstab/vendor zram configuration change; reboot removes runtime masks.
First retry bridge was missing explicit bundle binding; no run was created.
Relaunched with the established trusted QA binding and immutable release -14.
Actual React/Wails READY/fresh plan/approval/Start accepted:
run installer-10817d1d0930fd2a6836bd49f7083c00 FAILED after 1757s,
plan-f42ff4c2a085d32a8102c50b, revision unchanged from the HA 3/1 project.
PKI stage complete; swap preflight SUCCESS at sequence 464. Follower start
and initialized join check passed; first nested unseal task FAILED at 684,
terminal sequence 690. bootstrap_follower.yml passes a self-referential
vars mapping vault_member: "{{ vault_member }}" into unseal_member.yml.
Real RED OS Ansible Templar reproduced AnsibleError/recursive=True for that
mapping. Narrow proposed fix: remove the redundant mapping and inherit the
existing outer loop variable. No production correction made during acceptance.
No terminal HA PASS claimed. Seed initialized; first follower started;
data/bootstrap custody and committed run evidence preserved, no reset/reinit.
Owned Vite/Wails/harness stopped; temporary session RSA admission removed.
HA 3/3 remains NOT STARTED pending this role defect correction and HA 3/1 PASS.

## SI08-E HA 3/1 blocked by host swap; HA 3/3 prepared (2026-09-27)

Owner authorized sequential HA 3 nodes/1 server, then 3 nodes/3 servers.
Separate managed QA projects preserve the accepted standalone deployment.
HA 3/1 project project-216b2b909b937158 uses vault-ha-1..3 on node1 and
API/cluster ports 8300..8305. Real React/Wails fresh plan approval/Start:
plan-f42ff4c2a085d32a8102c50b, saved revision
sha256:4cd738232e51d472a1aa5530501bf9926c4aecc04ee013d691db40c48790ac14,
run installer-6b3a3e1ee1ffac82ee36167cc207bde9 FAILED after 639s,
terminal sequence 470. Vault preflight task failed at sequence 464:
VAULT_SWAP_ENABLED; node1 has active /dev/zram0 and /dev/sda3 swap.
Release -14 remains unchanged. No HA PASS claimed; no bootstrap occurred.
HA 3/3 project project-62473d1453874107 prepared through the existing local
EditSession/writer, Core plan plan-a2396817cf2a0cff99520cfc EXECUTABLE.
It uses vault-hb-1..3 on node1..3 and API/cluster base ports 8500/8501.
HA 3/3 execution NOT STARTED; waits for HA 3/1 acceptance.
All three QA hosts accessible with the established execution identity.
Temporary session RSA admission removed; owned Vite/Wails dev processes stopped.
Standalone unit remains ACTIVE. No standalone clear/reset or host swap change.
Owner authorized disabling swap on all three QA hosts. Executed swapoff -a
on .101/.102/.103; /proc/swaps header-only and Swap=0 verified on each host.
Available memory after disabling: approximately 1899/2337/3293 MiB.
This is current-boot state only: fstab/zram boot configuration is unchanged,
so reboot can reactivate swap. HA retry remains pending; no preflight bypass.

## SI08-E standalone repeat full plan PASS, changed=0 (2026-09-27)

Owner-approved transient lock recap correction real-proven. Actual React/Wails
run installer-d58d310393ae11ca56d6ff26c7dbd619 SUCCEEDED after 1508s
(25m08s), terminal sequence 902. Fresh plan plan-6240efc2d7659001c91933c5;
saved revision sha256:63dc5e487a0406782b37457cf5955393cbba3e0088504d56b5b8c0a1f573c21d.
Immutable release qa-si08-vault-20260927-14:
sha256:e80e44d23c8c61a1be3f6a2e970e6d7da218bb1aed917fddb75774fe2174c325.
PKI/apply/verify SUCCESS at sequences 149/721/901; task journal has 341 SUCCESS,
105 SKIPPED, 0 CHANGED, 0 FAILED. Hold/release now SUCCESS, lock readiness and
always-release still execute. No active transient Vault lock holder remains.
Vault ACTIVE/initialized/unsealed/leader, health HTTP 200; no reinit or data reset.
Result output list READY/NO_NEW_PACKAGE, appropriate for initialized repeat;
original encrypted custody preserved. Owned dev/harness stopped, temporary RSA
removed. Helper QA workspace cleaned. Standalone repeat gate is closed;
SI08-E overall still pending HA 3/1, HA 3/3/failover and final acceptance gates.

## SI08-E owner-approved lock recap correction under acceptance (2026-09-27)

Only transient lock hold/release now reports changed_when:false; ownership,
readiness/contention, fail-closed admission and always release unchanged.
Persistent directories/config/PKI/packages/data keep real change reporting.
Fresh RED OS role suite 20 PASS (2.061s); real isolated lock contention,
ordinary release and failed-holder recovery PASS, exact test artifacts cleaned.
Apply syntax/catalog/schema PASS, helper QA workspace cleaned.
New immutable release qa-si08-vault-20260927-14 activated:
sha256:e80e44d23c8c61a1be3f6a2e970e6d7da218bb1aed917fddb75774fe2174c325.
Saved revision sha256:63dc5e487a0406782b37457cf5955393cbba3e0088504d56b5b8c0a1f573c21d.
Fresh full React/Wails repeat underway; changed=0 not claimed until terminal.

## SI08-E standalone full React/Wails plan SUCCEEDED (2026-09-27)

Exact PKI verify correction real-proven: Vault verify imports existing shared
Core pki-verify.yml, reconstructs derived PKI requests/plans in its own process,
checks chain/fingerprint read-only, then verifies Vault TLS health/audit/KV2/auth.
Run installer-a31ff651ccf90db5d83d5acbb75494f8 SUCCEEDED after 1312s,
terminal sequence 902. Plan plan-1229e0c17b8d70e3ca1c8e6f; saved revision
sha256:57a71854492b2f7e23fe9b718996692e9d99a0c5159eb5fddef108f7ebdb9612.
Release qa-si08-vault-20260927-13:
sha256:31ef6e223a6c76330b179cc7629094232f6b7e15807ee33090caf1d686c92569.
PKI/apply/verify action SUCCESS at sequences 149/721/901. Real React flow:
open -> READY -> encrypted input import -> fresh plan -> approve -> Start ->
observe -> Result/output list READY, NO_NEW_PACKAGE for initialized repeat.
Task results: 339 SUCCESS, 105 SKIPPED, 2 CHANGED, 0 FAILED. CHANGED only
transient lock hold/release (372/712); strict repeat changed=0 NOT achieved.
Vault ACTIVE, initialized/unsealed/leader, health HTTP 200. No reinit/data reset,
TLS bypass or new evidence persistence; existing custody preserved.
Owned dev/harness stopped; exact temporary RSA removed, helper QA workspace
cleaned. Full SI08-E remains incomplete: lock recap semantics, fresh repeat,
HA 3/1 and 3/3/failover, remaining final acceptance gates. No overall DONE claim.

## SI08-E shared read-only PKI verify import correction (2026-09-27)

Vault verify missed the existing pki-verify.yml import used by Kafka/PostgreSQL.
Added that shared import after validate.yml, before Vault verify-only role.
Core resolves PKI requests/plans anew on the controller and verifies target
chain/fingerprint read-only; no new persistence, transport or Go-derived paths.
Fresh RED OS: 19 Vault tests PASS (1.859s), 3 consumer selection tests PASS
(8.255s), 12 PKI resolver tests PASS (0.048s); verify syntax/catalog/schema PASS.
Exact helper workspace cleaned. Supported immutable release -13 activated:
sha256:31ef6e223a6c76330b179cc7629094232f6b7e15807ee33090caf1d686c92569.
Saved revision sha256:57a71854492b2f7e23fe9b718996692e9d99a0c5159eb5fddef108f7ebdb9612.
Real React/Wails READY/encrypted imports accepted; full plan retry underway.
Terminal success and strict repeat/HA acceptance not yet claimed.

## SI08-E audit fix proven; separate verify PKI selector blocker (2026-09-27)

Run installer-5f3974b945758ad381f9dee706351b7d on release -12 completed
FAILED after 1309s, terminal sequence 826. Plan plan-519730a358b82c118cda6130;
saved revision sha256:00c1bc110338d41c79c16a672d9887e00f32c344369fdd69b92de60e7a5a2cd8.
PKI action SUCCESS, Vault apply action SUCCESS (sequence 721), including
existing audit admission and in-apply health/audit/KV2/userpass verification.
Owner-requested log_raw representation defect is corrected and real-proven.
Separate verify action fails selecting exact materialized PKI consumer plan:
select_consumer_plan.yml Require one exact PKI consumer plan FAILED at 824.
No TLS bypass/path guessing introduced; next correction must use existing
Core-owned PKI evidence in read-only verify across independent action processes.
Changed-task evidence is 2, both transient lock hold/release, not changed=0.
No unrelated idempotency fix made as part of log_raw correction.
Owned dev/harness stopped, exact temporary RSA removed; data/custody preserved.
Full standalone/repeat/HA acceptance remains blocked; no DONE/clean/commit claim.

## SI08-E audit false representation correction validated (2026-09-27)

Owner-authorized narrow fix: new audit requests use string 'false'; configure
and verify accept only false/'false' (existing case folding) or legacy '0',
preserving absent-option default. Unknown/true/null/collection values rejected;
no broad bool coercion, no existing audit rewrite or disable/re-enable.
Fresh RED OS role suite 18 PASS (2.347s), including 40 real Ansible conditional
positive/negative cases; apply/static verify syntax and catalog/schema PASS.
Go full suite/vet PASS, helper QA workspace cleaned. Supported immutable release
qa-si08-vault-20260927-12 published/activated:
sha256:1fbe82af9044d93cc68a898e7be8bda84b351f2ca671173bec5dcb0ecbcc98b6.
Saved revision sha256:00c1bc110338d41c79c16a672d9887e00f32c344369fdd69b92de60e7a5a2cd8.
Real React/Wails READY/encrypted imports PASS; new acceptance underway.
Full terminal apply/verify/repeat/HA success remains pending.

## SI08-E existing audit-option representation blocker (2026-09-27)

Fresh actual React/Wails run installer-bd14ba46f1db62f80dbba808cb45988e
FAILED after 921s, terminal sequence 690. Same current saved revision/runtime;
READY, encrypted imports, fresh plan/approval/Start all accepted.
Existing Vault unseal after reboot SUCCESS; no reinitialization. PKI tasks
SUCCESS. Configure read SUCCESS, incompatible-existing-configuration assert
FAILED (redacted ANSIBLE_TASK_FAILED at sequence 684). Bounded read-only API
proves file audit expected path, KV2, userpass; audit options.log_raw is string
"0", not "false". Current configure/verify guards accept only textual "false".
Exact representation mismatch blocks apply; do not weaken to arbitrary bool
coercion or silently mutate existing audit. Need bounded producer/read-back
parity correction and positive/negative proof before another acceptance run.
Normal always cleanup released this run's transient lock. Health HTTP 200,
initialized/unsealed/leader, canonical unit ACTIVE. Full verification not DONE.

## SI08-E QA node restored after power loss (2026-09-27)

.101 SSH restored. Actual React/Wails observer returned INTERRUPTED:102 for
installer-be9d767e41344a215fc2c9ef54877945 after 564s. No successful terminal
apply/verify claimed. Vault canonical unit ACTIVE, initialized=true, sealed=true
(Shamir restart behavior), health HTTP 503. Existing encrypted token/shares
preserved; next fresh plan uses them to unseal, never reinitialize.
Restarted owned Wails dev process to replenish bounded file-selection queue.
Full standalone/repeat/HA acceptance remains pending.

## SI08-E QA Execution Node powered off during acceptance (2026-09-27)

Supported immutable release qa-si08-vault-20260927-11 published/activated:
sha256:41c8d8a6e287dc69da063cba2f4dacfe081832ee38a6d02c52b4715f1cf6701d.
Saved revision sha256:0632608cc975dda517e1d7dfa3da12fad0fd9332194542962a577a6c17def598.
Real React/Wails READY, both encrypted inputs STORED, fresh plan
plan-d773b7fc52a8168128fad5c4 approved; Start returned STARTED for
installer-be9d767e41344a215fc2c9ef54877945. Last authoritative observation:
RUNNING, sequence 101, persistent PKI directory preparation.
QA VM RedOS-8.3-1 (.101) powered off at 2026-09-27 17:58:17 UTC;
VirtualBox confirms poweroff, TCP/22 unavailable, peer .102 cannot reach it.
.102/.103 remain SSH-accessible. Terminal result cannot currently be observed;
do not classify this run as PASS/FAILED from the transport failure.
Read-only API before outage confirmed file audit, KV2 and userpass enabled;
audit log_raw=false was NOT confirmed and needs exact safe inspection.
No data reset/reinitialization, journal cleanup or duplicate Start performed.
Full standalone/repeat/HA verification remains pending. SI08-E is not DONE.

## SI08-E dynamic verify parse defect corrected (2026-09-27)

Run installer-faf5ea3d4b99ee18aefb692fa25d27a2 FAILED after 1618s. Corrected
token/API configure tasks all SUCCESS; next dynamic include of verify failed
before any verifier task event. Exact source defect: verify.yml had fail_msg as
a task action sibling instead of an ansible.builtin.assert argument. Fixed that
indentation only; added static import_role tasks_from=verify syntax playbook and
focused module-shape regression. Fresh RED OS static verifier syntax PASS,
16 role-contract tests PASS (1.179s). No infrastructure rule/schema redesign.
Parser abort left a transient lock-holder. Exact unit ownership proved by failed
run state, event timestamps, active-enter time and fixed flock path/command;
only that helper stopped. Canonical Vault ACTIVE/unsealed/health HTTP 200,
no reset/reinit or data loss. Harness/dev stopped, temporary RSA removed.
New immutable runtime promotion/retry underway; full verification still pending.

## SI08-E full verification resumed (2026-09-27)

Supported QA promotion built/published/activated qa-si08-vault-20260927-10:
sha256:3cc0a48f9722f344fd14103b199dd1137b482c1bfa56a723fbf46d09a53af9d5.
Catalog unchanged: sha256:a460d77a38b7134f9a1639871eeb925a3ce8d673df3bfa5dcc1a40a22ada86d3.
Guarded lock-set update of the isolated QA project produced saved revision
sha256:46c94b17520915df19939b6661b8a108295bff67131ae15617464e0f51d34e9c.
Actual React/Wails: READY, corrected token/original shares STORED, fresh plan
plan-705a4c74638ef4e22f497d86 approved, Start STARTED;
run installer-faf5ea3d4b99ee18aefb692fa25d27a2 currently RUNNING.
No terminal apply/verify/repeat success yet. Known Wails dev overlay exception
persists; not clean UI acceptance. Read-only SSH to .102/.103 succeeds, no loaded
Vault units observed there. No reset/reinit or target cleanup performed.

## SI08-E header-token defect corrected (2026-09-27)

Cause proven: producer appended LF to admin-token; raw import preserved it and
HTTP header construction failed before requests. Read-only exact-LF control
returned HTTP 200 for sys/audit, sys/mounts and sys/auth. Owner-authorized fix:
Ansible writes exact token bytes without LF; raw/JSON/age import rejects CR/LF
without trimming or normalization. Existing custody no-overwrite/no_log retained.
Explicit QA correction created secrets/vault-qa-standalone/admin-token-corrected.age,
removed exactly one trailing LF in memory, verified encryption/readback and
unchanged original admin-token.age. Original receipt/ciphertext not overwritten.
Corrected-file API probe: all three HTTP 200, no CR/LF; actual React/Wails import
of corrected token and original shares STORED, READY PASS. No new Start in probe.
Full Go/vet/diff check, production Wails build (13.813s), catalog/schema
reproducibility, Vault apply syntax-check PASS. RED OS bootstrap/recovery:
6 tests PASS (367.718s); Vault role contracts 15 PASS (1.104s).
Independent scoped DIFF APPROVE, 0 blocking/overengineering;
fingerprint 14af436a811bf8e8f37a780d3e07290e56b3b01119d953541adb95f286dcbcaa.
Affected RED OS CGO race PASS (internal/secretfiles, 238.390s); exact temporary
QA workspace removed through qa-sync cleanup.
Dev/harness stopped, temporary RSA removed (QA_KEY_REMOVED). Known dev ipc.js
error persists; clean UI acceptance not claimed. Active immutable runtime remains
unchanged; producer fix needs a new immutable release for future new deployments.
SI08-E apply/verify/repeat/HA acceptance remains pending, not DONE. No commit or
clean-worktree claim; previous unrelated changes preserved.

## SI08-E new blocker after successful unseal (2026-09-27)

Real React/Wails run installer-f53a30142211d7456a8a4b76c28937b3 terminal FAILED.
Former pending-secret Start blocker is fixed and tested. Seed unseal and exact
cluster identity checks succeeded. Failure is sequence 682, first protected task
in configure.yml: read sys/audit, sys/mounts, sys/auth before any configuration
mutation. Diagnostic ANSIBLE_OPERATION_FAILED (ANSIBLE_FAILURE_REDACTED) does not
retain the HTTP/TLS/module detail; token failure is NOT established.
Safe read-only post-run probe: HTTP 200, initialized=true, sealed=false,
standby=false, cluster identity present, exact canonical unit ACTIVE.
Deployment lock release succeeded. No reset/reinit, key/custody removal or secret
disclosure. New minimal prerequisite: bounded read-only API diagnosis through
existing protected credential flow, outputting only endpoint/status/error class,
before another apply. Do not disable no_log or print response bodies/tokens.
Owned harness/dev servers stopped; exact temporary RSA removal QA_KEY_REMOVED.
QA race workspace cleaned. Journals/custody/canonical project preserved.
SI08-E BLOCKED; verify/repeat/HA/final gates not PASS, no milestone commit/clean claim.

## SI08-E broker correction: real Start admitted (2026-09-27)

Owner-authorized narrow correction separates pending password consumption from
typed input binding in the existing Broker. Empty password promotion no longer
rejects a typed-only bucket; successful password promotion preserves typed inputs
for exact Core descriptor binding. No new store, protocol, guard bypass or reset.
Focused broker tests cover typed-only/mixed inputs and descriptor rejection;
App regression covers clearing/non-clearing descriptor refresh in Start order.
Focused tests, full Go suite and vet PASS. Current-source RED OS CGO race PASS:
broker 1.208s, App 1.323s. Scoped independent DIFF APPROVE_WITH_CHANGES,
0 blocking/overengineering; PBT-01 nonblocking test hardening applied and focused
PASS (TTL/generation unchanged, consumed password and expired typed buffers wiped).
Actual React/Wails: READY, both ciphertext inputs STORED, fresh plan approved,
Start STARTED -> installer-f53a30142211d7456a8a4b76c28937b3, now terminal FAILED
on the new configuration API blocker documented above.
Saved revision remains sha256:a75031b7d1fb1d54273c8781fc5e4ceb100443f1c72f2038ac56f920e646e73b.
This supersedes the Start blocker below, not full Vault acceptance: terminal
apply/verify/repeat and HA acceptance remain pending; dev ipc.js error remains.
Initialized Vault/custody/history preserved. No SI08-E DONE or clean-worktree claim.

## SI08-E Start blocked by pending-secret promotion (2026-09-27)

Actual React/Wails retry: READY, both encrypted files STORED, fresh plan
plan-a09964168cc5a40c97429e9d rendered/approved, output password and PKI password
PRESENT. Revision sha256:a75031b7d1fb1d54273c8781fc5e4ceb100443f1c72f2038ac56f920e646e73b.
Start returned BLOCKED / RUNTIME_SECRET_DESCRIPTORS_STALE, no runId returned.
Subsequent real target-free GetRuntimeSecretDescriptors returned UNAVAILABLE /
RUNTIME_SECRET_INPUT_INVALID. Concrete broker defect: the shared pending bucket
contains typed token/shares but an empty password values map; password promotion
requires a nonempty map, and its success path clears the entire pending bucket
before the following BindPendingServiceSecretInputs can bind typed inputs.
App invokes password promotion before typed binding; Start wraps descriptor
failure as STALE. No guard bypass, new run, target apply or reinitialization.
Smallest correction pending owner direction: separate consumption of password
entries from typed entries in the existing bucket, allow empty password promotion
without dropping typed inputs, and prove the combined App/Start sequence in tests.
Owned dev/harness stopped, exact QA RSA removal confirmed QA_KEY_REMOVED.
Custody/canonical files and historical run journals retained; SI08-E BLOCKED.

## SI08-E native secret picker / WebView2 blocker (2026-09-27)

Continued real React/Wails flow after the DTO correction: project opened,
session credential PRESENT, Execution Node READY, Vault Secrets form rendered.
First native admin-token.age picker opened. Computer Use returned its actual
accessibility tree. Setting the filename failed to activate the captured window;
Wails logged WebView2 `The parameter is incorrect` in Chromium.Focus/onFocus,
then the application process disappeared and bridge port 34115 closed.
One unchanged supported dev restart restored the bridge and READY; the repeated
React file-selection action did not expose a usable native dialog. No import
success, new Start/run, init/reset/unseal or deployment was observed.
SI08-E remains BLOCKED on the desktop native-file-input boundary; this is not
evidence of a Vault failure. No dependency or production bypass was introduced.
Both attempt harnesses and dev servers stopped; exact temporary RSA admission
removal confirmed QA_KEY_REMOVED. Existing custody and run journals preserved.
Next bounded action: diagnose native dialog ownership/focus in the supported
Wails bridge before retrying the already-initialized Vault with retained custody.

## SI08-E recovery blocked by external-node list guard (2026-09-27)

Corrected unseal runtime published/activated through supported promotion:
sha256:169d75bc64933c0f871efe26f2da36652776025bf9c1e4a9b72b8d8961c7735d.
Isolated revision sha256:a75031b7d1fb1d54273c8781fc5e4ceb100443f1c72f2038ac56f920e646e73b;
catalog unchanged. No target reset/init/unseal or new Start was performed.
Actual React/Wails recovery flow opens project, proves READY, sets session-only
output encryption password and invokes Result/ListPending. Repeated real binding
calls return PROJECT_CHANGED with unchanged EXPLICIT_EXTERNAL/READY selection.
Concrete defect: app.go ListPendingSecretOutputs post-call guard compares
SelectedHostID to binding.node.ID; external selection deliberately has no
SelectedHostID (execution_node_context.go selectInitial). Existing private
binding resolver correctly checks external.hostID instead. Do not weaken guard
or substitute a mock/direct secret export. Smallest proposed correction: recheck
the current supported private binding identity after the remote call together
with existing project/generation guards; add external-selection and race tests.
No Go correction made without owner direction. Custody/journals retained,
dev servers stopped. SI08-E remains BLOCKED; no output delivery/import claimed.

## SI08-E new blocker: seed identity read before unseal (2026-09-27)

Diagnostic runtime sha256:9752977101218636e21af54fc8ca38fc2689b6b04218cf598a2258874b1bd0db
published/activated; isolated revision
sha256:1b5ac63e9dec173990ef8b063df15c9540d8e18e3a50318d957590fc8fb13c79.
Real React/Wails fresh plan/approval/Start run
installer-6989b0f2fb6c2609515170ece9c9eeb7 FAILED, sequence 670.
Original audit task SUCCESS; init custody files exist, recovery record absent.
Unseal include starts at sequence 659; initial health succeeds, then capture
seed cluster identity fails. Safe read-only health proof: HTTP 503,
initialized=true, sealed=true, cluster_id absent. No token/shares inspected.
New classifier emitted ANSIBLE_FAILURE_REDACTED for the no_log failure, as required.
Smallest proposed correction: capture seed identity after confirmed unseal,
then retain exact follower identity guard. No correction/reset/retry performed.
Core 393 total / 374 PASS / 19 SKIP; privileged clear 18 PASS; reproducibility PASS.
QA workspace/RSA admission cleaned; dev servers stopped; custody/journals retained.
SI08-E remains BLOCKED pending owner authorization of this bounded service fix.

## SI08-E real React/Wails retry: new provisioning blocker (2026-09-27)

Guarded Vault clear committed as 72a199143df4c7acb50d0ce77cf439398b32ada6.
Exact owned QA reset passed (changed=4); member root/marker, config, PKI,
audit/unit identities and committed journal bytes were retained. No active run
or deployment lock existed before reset.
Bootstrap correction received independent FULL DIFF APPROVE, zero blockers;
reviewed fingerprint 49bb289d7427879f45cc3dcfe3d01f13efcc3bc51f8b6a3cac440277b66a0571.
Supported immutable publication/activation produced runtime
sha256:e53df4e66364ebbb7fde8653219da12dc77bff92ea527d347a02ed5205291531.
Only the isolated QA project's guarded lock was promoted; catalog unchanged.
Real React/Wails readiness, fresh plan, approval and Start proceeded, but run
installer-c77432c312f53ac251fc5635ff559915 became FAILED at sequence 570.
First failed task: Create the fixed audit mountpoint used inside each unit
namespace (/var/log/platform-vault-audit), before init/unseal.
Read-only inspection proves root:root 0755, no immutable flag, adequate disk
and inode capacity, selected unit inactive. Separate elevated local Ansible
check-mode inspection passes changed=0; it is not production-run acceptance.
Exact production task error/cause is not yet established; do not guess or
retry the full plan. SI08-E remains BLOCKED, not DONE. Temporary QA public-key
admission was removed; prior unrelated worktree changes remain preserved.

## SI08-E QA reset authorized; safe mechanism prerequisite unresolved (2026-09-27)

Owner authorized reset of the owned QA Vault instance. Read-only recheck on
.101 confirms Vault is initialized, while `init-response.json`, `admin-token`
and `unseal-shares` are absent from the exact failed run's output package.
Scoped inspection found no existing suitable identity-safe Vault data reset or
quarantine mechanism. Existing project publication rename helpers do not prove
the identity of a Vault source directory and are not reused as a reset tool.
The approved bootstrap correction plan explicitly requires stopping on this
mechanism gap. No unit was stopped, no data was deleted/moved, no journal or
output package was changed, and no new runtime or acceptance run was started.
SI08-E remains BLOCKED pending an owner-approved bounded reset mechanism.

Owner requested analogous Kafka/PostgreSQL Ansible clear tasks. Concrete plan:
`docs/work/vault/service-install-08e-clear.md`, explicit standalone playbook, exact
deployment acknowledgement and existing flock; a narrow Vault-only held-fd
reset preserves member root/marker, config, TLS, audit and controller custody.
Independent FULL PLAN review APPROVE_WITH_CHANGES, zero blocking findings;
two nonblocking mount/revalidation clarifications were incorporated. Concrete
helper design was subsequently approved and implemented (see latest entry).
No destructive target mutation has occurred.

## SI08-E acceptance preparation started (2026-09-27)

Owner authorized SI08-E after C/D commit `3e1f711`. Required preserved
prerequisite work was restored from stash (stash retained). New immutable QA
runtime `sha256:d84df0dc93eee8673276981fa94a2d7a20bd6373fa7cffea3a4271fd3216e89d`
is activated on .101 and READY. Standalone QA project
`.runtime/qa/vault-qa-standalone-20260927` has saved inventory/PKI/Vault desired
state; fresh Go/Core plan is EXECUTABLE. Native UI import of the prepared
project was confirmed by the owner. Visual/manual UI acceptance is waived;
nonvisual React/Wails integration through real backend bindings is now mandatory
for all services and affected application flows (see AGENTS/common acceptance).
The imported project now includes unplaced Kafka `asd`, preserved unchanged.
Isolated Vault QA project `project-76b046511af5faed` has an EXECUTABLE plan.
Start was blocked by the Go PKI capability gate requiring legacy payload v2
from a v4-only runtime. Owner-approved bounded correction and focused tests
are implemented; focused/full Go tests, vet, diff check and production Wails
build PASS. The real React/Wails automation prerequisite is resolved via the
standard loopback Wails dev server and headless Edge; no production debug
endpoint or dependency edits. React session credentials/readiness PASS and
fresh Plan reaches PLAN_REVIEW. Owner-approved Plan presentation correction
now serializes empty Targets/DependsOn as arrays; JSON regression/full Go/vet
PASS and actual React Plan rendering/approval/PKI input PASS. Real React Start
previously returned BLOCKED / LEASE_PAYLOAD_INVALID before run creation. The
owner-approved typed nil-map correction now serializes runtimeSecretValues as
{}, with focused/full Go tests, vet and diff check PASS. Actual React/Wails
retry passes lease admission but returns EXECUTION_MANIFEST_INVALID before run
creation. Active runtime proof: Core emits displayLabel in private
runtimeSecretInputs; the closed consumer rejects that field. The same bounded
descriptor without displayLabel is accepted. SI08-E is BLOCKED on this new
producer/consumer mismatch was then corrected with owner authorization: private
displayLabel omitted, public label preserved, real consumer regression PASS.
Core 351 PASS/4 skips, Go full suite/vet and catalog/schema checks PASS.
New immutable runtime sha256:a668dca34624ba39bc289efbe577b6b1665488d9e7ce416c8c910d65d0139c96
activated; only isolated Vault QA project locks advanced through guarded API.
Real React/Wails Start admitted run installer-7c88e83cb1124ca91cfce021861d4b01,
then terminal INTERRUPTED at sequence 2. Controller reports OUTPUT_ACCESS_DENIED:
execution root is mode 0700 owned by UID 1001, detached controller runs as UID 0;
output storage requires owner == effective UID. SI08-E is BLOCKED on this new
ownership mismatch before Ansible Apply was corrected with owner authorization.
Supported activation now creates/verifies private execution storage through the
existing no-follow output directory helper under sudo; foreign owner fails closed.
QA root alone was corrected by fchown on its opened directory after no active runs
were confirmed; descendants/journals/leases were untouched. Startup projection
failure after verified durable identity now records FAILED with lease cleanup.
Core 353 PASS/4 skips, lifecycle 39, output storage 25, Go suite/vet, frontend
67/lint/build and catalog/schema checks PASS. Runtime
sha256:c1727d16eca98bcb054bbe4665275776df5d0adc8ecbd202961346143455de09
activated; React/Wails admitted run installer-95d2c1f3ad92343e09ae8da684a1ef78.
It reached RUNNING and PKI Apply completed. Terminal FAILED at sequence 338:
Vault closed-input assertion rejects apiPort type after generic
runtime_role_variables set_fact. Manifest apiPort is an integer; local-only
Ansible reproduction of the same set_fact conversion fails assertion index 6
(platform_vault_api_port is integer). SI08-E is BLOCKED on this new typed
Core-to-Ansible boundary defect; no type/safety check was weakened.
Owner authorized a narrow generic correction. Local-only RED OS experiment
proved mapping args preserve numeric types, but Ansible set_fact with native mode
disabled still converts string "false" to boolean. New focused real-Ansible
regression: native=True PASS; native=False BLOCK on string identity; empty and
malformed/missing-host guards PASS. The experimental production task change was
reverted; regression retained. No new runtime publication or Vault retry.
A fully typed correction now requires an explicit choice of a narrowly scoped
fact action adapter versus global native-mode policy; the latter was not changed.
Owner approved the narrow adapter. platform.core.apply_runtime_role_variables
now copies only current-host platform_* values into facts without scalar
templating/coercion, target transport, or file writes. Existing mapping guards
and no_log retained; arguments/invalid names rejected. Real Ansible regression
PASS in native=False/True, including numeric and boolean-shaped strings,
list/map/null, empty mapping and malformed/missing host. Focused tests 3 and
service/PKI contracts 11 PASS; Go suite/vet PASS; full Core 356 PASS/4 skips,
catalog/schema reproducibility PASS. Runtime
sha256:0c0248c19a457d647a060c8c72b1ca1fa5999099f02a0e43b55239b563b15f1a
activated; only isolated QA project lock updated. React/Wails run
installer-2e83aa4e51d88886abc0827217e6abae reached PKI/apply and passed the
previously failing Vault typed-input guard. Pinned Vault repository installation
completed; terminal FAILED at sequence 586 on changed-member restart tracking.
provision.yml used loop_var vault_member for configuration/systemd templates,
while tracking expected item.item.id. Owner authorized retaining item.item.id:
template loops now use default item with task-local vault_member alias.
Real local-only Ansible regression PASS: three-member first render, unchanged
repeat, and single-member change track the exact expected identities without
duplicates. Target now has
partial package/account/PKI/config provisioning; no active Vault units observed.
No Vault init/unseal, verify or output-delivery success is claimed. SI08-E is
BLOCKED on a new independent service-directory access defect after this
owner-authorized loop correction passed real acceptance. Core 357 PASS/4 skips,
Go suite/vet, catalog/schema and diff check PASS. Immutable runtime
sha256:66ed3423ed150cb8fa46af19c0bdcd120a4066a4ffcd78c3367d28b76ac24e67
activated. React/Wails run installer-ff1844b73c5fd429dbf4c7b0c9243cbe passed both
tracking tasks and started the seed; terminal FAILED at sequence 600.
Vault auto-restarts (exit 1, permission denied). Deployment parent directory
/etc/platform-vault/vault is root:root 0750; service-owned member config 0600
cannot be read as platform-vault because parent traversal is denied. No new
permission correction was made. QA source workspace/key and local automation
were cleaned; original imported project and unrelated services unchanged.
Owner authorized the next bounded permission correction: deployment parents
now retain root owner/0750 with platform_vault_group. Private member/file modes
and no-follow/owner guards are unchanged. Focused root/local Ansible 2 PASS,
including service read/no-parent-write and repeat changed=0; Vault 15 PASS,
Core 358 PASS/5 skips; Go suite/vet, catalog/schema and diff check PASS.
Runtime sha256:c8952a109ac1774cc896e5d195a5908e95d371f385ec5891317436eef38789df
activated. React/Wails run installer-b095002168ac83f7fb1aa9289f7120cb proves
configuration readable and Vault ACTIVE, closing the permission blocker.
Terminal FAILED at sequence 612 on a new bootstrap response validation defect:
dictionary .keys resolves a method rather than the Shamir shares collection.
Synthetic active-task proof fails; ['keys'] variant passes. Production bootstrap
was not changed. TLS API confirms initialized=true; exact custody package has
no init-response.json/admin-token/unseal-shares (existence-only proof).
SI08-E remains BLOCKED. No blind retry or QA state reset was performed; required
next actions are explicit dictionary indexing correction and owner-authorized
reset of only the exact owned initialized QA member before repeat acceptance.
QA source workspace/key and local automation cleaned; no other service mutation.
Owner accepted the bootstrap plan correction. Revision 2 is in
docs/work/vault/service-install-08e-bootstrap-correction.md: immediate minimal recovery
copy, explicit readback/sync durability, strict validation and confirmed durable
pair before recovery deletion. Independent single targeted recheck APPROVE:
SI08-E-PLAN-01 RESOLVED (PLAN), zero blocking/overengineering findings.
SI08-E-PLAN-02 remains the separate reset identity/mechanism prerequisite.
This closes only the plan gate; production bootstrap implementation, fault
injection and real retry have not been performed. No QA reset occurred.
Owner subsequently authorized implementation. bootstrap.yml now uses explicit
keys indexing, immediate minimal recovery copy, metadata/readback/sync checks,
strict validation and pre-publication conflict checks, synchronized pair and
directory synchronization after recovery cleanup. Native modes/interruption/
reopen/partial pair/malformed/conflict/sync/cleanup regression: focused 6 PASS
(213.153s), Vault contracts 15 PASS. Independent QA full Core 364 PASS/5 skips
(369 total, 238.129s); Go suite/vet, catalog/schema, standalone syntax and diff
check PASS. QA source workspaces/logs cleaned; no actual secret reads.
No runtime promotion or real retry in this correction; no QA reset. Existing
initialized seed without custody still blocks SI08-E acceptance. PLAN-02 exact
ownership reconciliation, safe reset/quarantine mechanism and separate owner
authorization remain required. Implementation uncommitted; SI08-E not DONE.
See docs/guides/qa-react-wails.md and SI08-E evidence. No mock substitute is used.
Vault Apply partially completed and seed init occurred as above; unseal, verify,
protected delivery and repeat acceptance have not passed. See
`docs/work/vault/service-install-08e.md`. Earlier NOT STARTED statements below describe
the historical C/D gate, not the current E authorization.

## SERVICE-INSTALL-08 Vault implementation started (2026-09-26)

SI08-D owner clarification: the common output encryption password is entered
on Installation → Plan. No folder selection is provided. The workstation
uses `<project-root>/secrets/<deploymentId>/` automatically. This behavior is
implemented with safe opened-directory publication and tests for the default
path, no overwrite, symlink rejection and exclusion from Core staging/revision.
Go full test/vet, frontend 67 tests/lint/build and Windows Wails build PASS.
Initial FULL DIFF review returned BLOCK with six findings SI08-D-DIFF-01–06.
The owner accepted all six blocking and two nonblocking corrections. Final QA
PASS: Core 341 PASS/4 opt-in skips, contracts 31 PASS, Vault role 15 PASS,
Windows full Go/vet, frontend 67/lint/build, Wails and affected RED OS race PASS.
The single targeted recheck resolved DIFF-01–05 but returned BLOCK on DIFF-06:
protected pre-publication packages lacked reservation/terminal recovery handling.
The owner subsequently authorized this exact correction. DIFF-06 is now
RESOLVED BY OWNER-AUTHORIZED EXACT CORRECTION, with private durable reservations,
full-pair terminal publication, empty completion/next-run admission and explicit
partial-material recovery status. No further architecture review was run;
the automatic review budget remains exhausted. Final current-source offline
QA: lifecycle 38 PASS, storage 24 PASS, Core 351 PASS/4 opt-in skips,
contracts 31 PASS, Vault role 15 PASS, catalog/schema checks PASS; affected
Go race, Windows full Go/vet and frontend 67/lint/build PASS.
SI08-C/D are recorded in a focused implementation commit; unrelated work remains
outside it. No Vault execution occurred. See `docs/work/vault/service-install-08d.md` and
`docs/work/vault/reviews/service-install-08d-review.md`. SI08-E remains NOT STARTED.

SI08-B is DONE. SI08-C implementation and QA gates PASS in the current
worktree and are recorded with SI08-D in a focused implementation commit.
Unrelated in-progress changes remain outside it. SI08-D is implemented; SI08-E
remains NOT STARTED. D has implemented the workstation age file crypto base at
`internal/secretfiles`, pinned to filippo.io/age v1.3.2, Scrypt work factor 18,
and the approved encrypted-file size bound. It also strictly extracts only the
approved Vault token/share fields and projects closed `x-secretInputs` from the
locked catalog as safe metadata. Focused tests, `go test ./...` and `go vet
./...` pass. D now includes no-follow selected-file reading, broker/lease
integration, output delivery and generic Secrets/Plan UI in the worktree.
The DIFF-06 reservation/recovery correction is implemented and tested; real
Vault service acceptance remains SI08-E. The mockup shows the common Plan encryption
password and fixed default output path. The SI08-C implementation and QA evidence are recorded in
[`docs/service-install-08c.md`](../work/vault/service-install-08c.md). It adds Core
typed-secret descriptors and manifest binding, Execution Node capability and
lease admission, scoped Ansible forwarding, and interruption-safe cleanup of
temporary typed-input files. Vault unseal shares are Apply-only; the admin token
is available to Apply and Verify. The immutable runtime was not published or
activated, and no Vault deployment or target mutation occurred.

SI08-B is DONE. The owner-authorized targeted recheck passed SI08-B-DIFF-01 and
SI08-B-DIFF-03 after the lock/path execution evidence was supplied;
SI08-B-DIFF-02 is resolved by the owner decision to match
the established services' two-mode artifact-source behavior: authority/resolved
source mode uses the common gate; direct Ansible-only mode without those inputs
continues using the configured package repository without a new mandatory gate.
All three B findings are resolved with zero blocking and zero overengineering
findings. No real Vault deployment or target mutation occurred.

Latest focused evidence on RED OS: Vault role contract 14 PASS; lock contention
proved exactly one READY holder and reacquisition after normal stop and failed
holder; seven symlink cases across config/data/log deployment/member and config
PKI boundaries rejected before outside writes; standalone, 3-member/1-host and
3-member/3-host role validation plus read-only preflight and apply/verify syntax
checks PASS. The prior B Core suite had 322 tests PASS, 4 skipped. Latest C
regression: Core 337 PASS, 4 skipped; contracts 31 PASS; Vault role 15 PASS;
catalog and service schema reproducibility, apply syntax-check and
`git diff --check` PASS. No Vault package, init, or target data mutation has
been performed.

Owner authorized implementation after the exact SI08-PLAN-02 terminal-evidence
correction. SI08-A is DONE; pinned artifact acquisition blocker is resolved.
The architecture is
`docs/work/vault/service-install-08-vault-architecture.md`: standalone and three-member
Raft (1/1, 3/1, 3/3), API TLS and Vault cluster TLS, audit, KV v2, userpass
enabled without managed accounts; configurable unseal defaults 2-of-3.
Workstation encryption uses its session password; protected temporary
plaintext on Execution Node is retained until confirmed delivery.

Initial additive SecretOutputDelivery/v1alpha1 request/control-response/safe
metadata schemas and a bounded Go Fetch-frame decoder are implemented but not
wired into an active runtime or advertised. Existing published execution
contracts are unchanged. Closed Go control-request decoder and Python
request/Fetch codec are added; neither performs target contact or storage.
RED OS contract suite: 21 PASS; Python codec: 3 PASS; `go test ./...` and
`go vet ./...` PASS. Owner-authorized DEV acquisition of
`vault-1.21.2-1.red80.x86_64` from RED OS `updates` completed. RPM signature and
repository/remote/local SHA-256 equality PASS:
`sha256:11db853f514625835ed4516876311057b7021fbaf39a53040e5e13d111bc41dd`.
Artifact is Git-ignored under `.runtime/artifacts/vault/`; extracted binary
reports Vault v1.21.2. No Vault package has been installed.
Private Linux protected package publication/Fetch foundation is implemented,
not wired or advertised: no-follow held descriptors, restricted ownership/modes,
durable exact binding, no overwrite and READY publication after entry flush.
RED OS storage tests 10 PASS; Core suite 320 tests, OK (4 skipped).
SI08-D exact DIFF-06 correction and focused/regression gates are complete in
the focused C/D implementation commit. SI08-E
owns real Vault deployment acceptance. SI08-B and SI08-C status/evidence are
recorded above.
Redis completion must not be inferred from this entry.
Artifact metadata license BUSL-1.1; intended distribution/license notices must
be addressed before offline publication. No runtime release was published or
activated. Exact artifact evidence and remaining A contract gates are recorded
in `docs/work/vault/service-install-08a.md`.

Initial implementation DIFF review: BLOCK, one blocking finding. Canonical
deployment IDs containing dots/underscores are rejected by output identity
admission (SI08-A-DIFF-01). Exact metadata-key case is NON_BLOCKING
(SI08-A-DIFF-02). Callback error leakage is RESOLVED (SI08-A-DIFF-03), with
independent focused QA PASS. Latest full Go test/vet and RED OS wire race PASS;
contracts 31 PASS, Core 320 tests OK (4 skipped), reproducibility/offline PASS.
This initial BLOCK is historical. Owner-approved corrections passed the one
TARGETED_RECHECK: DIFF-01/02 RESOLVED, DIFF-03 remains RESOLVED, 0 blocking
and 0 overengineering findings. Final Windows Go test/vet PASS; RED OS Core
321 tests OK (4 skipped), contracts 31 PASS, wire race and reproducibility
PASS; diff-check PASS. SI08-A contract foundation is DONE, not runtime or
Vault deployment acceptance. New additive input/output contracts are defined
but not advertised; existing published contracts are unchanged.

