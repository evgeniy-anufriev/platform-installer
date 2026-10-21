# SDKU/CSPA alarm-view-service isolation test

Owner-authorized 2026-10-19 after commit b7d53034. Deploy two library instances
on101/102/103 through real React/Wails fresh plan/approval/start; accounts, grants,
topics and databases only through the plan. Keep diagnostics enabled. Owner also
authorized necessary space cleanup and requested project folder/path before plan.

Project: `.runtime/qa/sdku-cspa-alarm-view-project`, same established project
ownership project-b46aa3f5f57a495f, separate desired-state copy; original project
preserved. Folder/path shown in commentary before any plan. Sources include the
26 shared application packages and SDKU/CSPA library packages. The subsequent
owner-approved Redis bindings change includes bounded Core/UI implementation.

Preparation: copy the existing effective SDKU connection/TLS baseline into its
test package, retaining shared provider bindings. Copy that library to CSPA;
only package name/role paths and resource_defaults differ. Both use the same
alarm-view-service package. Shared test application defaults select distinct
Redis client/Sentinel accounts. Redis names derive from library resource defaults;
the final client grants retain the owner's original wildcard keys/channels and
+@all -@admin commands. This test proves separate resource names, not cross-library
Redis ACL isolation. Actual Kafka names use declared topic keys.
Initial preparation incorrectly classified alert-class/alert-hdl as Kafka topics;
owner corrected this before any installation plan/start. Removed both Kafka
definitions/selections; owner also identified metadata as Redis, removed it from
Kafka definitions/selections too. ALERT_CLASS_TOPIC/ALERT_HANDLER_TOPIC and
metadata ENV derive Redis names despite their TOPIC suffix. No server topics
were created by those preparation mistakes.
No raw secret values in desired state.

## Current acceptance result — 2026-10-20 14:38 MSK

Owner subsequently requested stopped containers and promotion/commit. Scope
explicitly confirmed: SDKU/CSPA library packages plus the shared alarm-view-service
application only; other25 application QA copies not promoted. Docker ps confirms
no running alarm-view containers on101/102/103; no subsequent plan started.
Promoted10 declared files, text identical to QA after LF normalization, into
examples/sdku. CSPA added to the common import catalog; all28 digest/import checks
PASS. Selected package defaults intentionally retain the tested SSL listener,
separate Sentinel account/connection and Vault secret mount; canonical other
application SCRAM configuration preserved. Instance group_vars/credentials,
runtime/project artifact locks, image archives and diagnostic overrides not copied.

Promotion QA from current-tree qa-sync workspacead69... on primary RED OS101:
package schemas/digests28, prepareJobs2, synthetic Compose26/sharedBase1 PASS;
five focused Redis Core tests PASS (1+3+1). Local Go TestSDKUImportPackageBytes
PASS; frontend ApplicationLibraryResources14 PASS and production build PASS
(existing chunk-size warning retained). No new installation/plan/bundle/visual
acceptance. Native source workspace cleaned with qa-sync after verification.

Owner subsequently authorized a normal plan again, requesting that all six
alarm-view containers first be stopped to release resources for the installer.
Exact project/library/host guards checked; Docker stop confirmedall6, no image,
volume, restart policy or infrastructure change. Corrected shared app protocol
SSL retained. Existing real React/Wails preparation READY on runtime47; fresh
Project Verify VERIFIED and two-library resource projection checked. New plan
plan-1af848456ada3e22fd51d932, saved revision
sha256:32cc54e3c0cafd2f9f39cbce020b81c44037fed913fbc204c7cac0df4de0567c,
approved and Start returned STARTED run
installer-aa2969d23674a9d29e86b24808fcec01. Exactly Library Apply/Verify,
skipInfrastructureVerify=true, no infrastructure operations. Runtime47 unchanged.
Current normal-run completion/public endpoint acceptance pending. UI evidence:
.runtime/qa/application-design/sdku-cspa-alarm-view-corrected-plan.json/log.

Runaa2969d2 FAILED2026-10-20T12:36:29Z /15:36:29MSK, after all6 readiness
checks and before HAProxy activation. Failed task2592-2594 onall3: Capture exact
prior Platform HAProxy backend inventory before candidate reset. Generic event
redaction hid the module message; isolated identical native read-only capture
proved HAPROXY_PRIOR_GRAPH_INVALID. Active conf.d has exactly one extra file:
30-backend-alarm-view-service-sdku-dm-qa-shared-endpoint.cfg, absent in retained
.candidate/conf.d. All other files and main config match. Do not claim the
historical writer/cause of that incomplete retained snapshot is established.

Each host has8 native activation archives containing an identical owned copy,
SHA256 da75c65d3eac72c04368701d1a887966be98e20e31df98b426485df297412414.
Standard Ansible recovery checked root ownership/regular/single-link archive
source, exact active/source hash, absent candidate destination, matching main
and exactly the one missing fragment. It copied only that archived fragment to
the derived retained candidate, validated haproxy -c and reran native capture.
No active config/process/reload/Core code/runtime bundle change. Recovery first
helper accidentally targeted inventory localhost too: localhost failed its
undefined source check before any write; all3 target hosts8ok/changed1/failed0.
Original exit2 retained, not presented as a whole-play PASS. Corrected read-only
capture restricted node1:node2:node3: exit0, each1ok/changed0/failed0. Source/repair
evidence under .runtime/qa/sdku-cspa-haproxy-{recovery-sources,recovery,capture}.json.
All6 normal-plan startup logs before next stop show ERROR/OOM/PKIX0; safe
evidence sdku-cspa-first-corrected-plan-startup.json. Owner then explicitly
instructed not to launch a fresh plan. No retry plan/Start was performed after
candidate recovery. Already-started exact-ownership stop completedall6 to free
RAM. Final CSPA public endpoint acceptance remains incomplete. Candidate recovery
is complete; no further plan execution is authorized by this continuation.

Owner-directed Docker-only startup/read-only acceptance PASS. The last normal
plan run6977054d is CANCELLED, not SUCCEEDED; no further plan was started after
the owner instruction. Resource/account provisioning came from the previous
approved plan executions. Docker continuation changed only rendered application
parameters and reconciled containers; no manual accounts/grants/DDL/topic writes.

| Server | SDKU alarm-view | CSPA alarm-view | Restarts | Direct HTTP |
| --- | --- | --- | --- | --- |
| 192.168.56.101 | running / healthy | running / healthy | 0 / 0 | 200 / 200 |
| 192.168.56.102 | running / healthy | running / healthy | 0 / 0 | 200 / 200 |
| 192.168.56.103 | running / healthy | running / healthy | 0 / 0 | 200 / 200 |

SDKU direct port10021, CSPA10022. Original image/reference b433d144 unchangedall6.
The shared test application's KAFKA_SECURITY_PROTOCOL is SSL in its defaults
and all six rendered manifests/actual environments. Canonical source packages
retain SASL_SSL for their canonical listener. No blanket heap increase: test
instance JAVA_OPTS/JAVA_TOOL_OPTIONS remain-Xmx768m. Original image healthchecks
remain enabled (30s interval/15s timeout). One CSPA102 health command timed out
during startup; later repeated checks succeeded. This was retained as an observed
startup failure, not classified as a stable container failure.

Current-start logs all6: started=true, ERROR0, OOM0, PKIX failures0, NOPERM0,
NOAUTH0, UnknownTopic0, FATAL0. Five WARN per container retained, including startup
Kafka TimeoutException on101/102. Stable window since2026-10-20T11:36:00Z through
11:38Z: all6 ERROR0/WARN0/exceptions0. Literal PKIX in Kafka's normal
ssl.trustmanager.algorithm=PKIX config is not a certificate validation failure;
the QA signature now matches actual path-building/validation failures only.
No diagnostic logging disabled and no business event data generated.

Read-only DB checks PASS: each own PG user connects over TLS to its own DB on
102/103, public USAGE, six successful Flyway versions and user_prefs visible;
each own CH user over TLS sees records/alarm_message in its own DB onall3.
Redis own-user TLS probes PASSall6 for the three declared names; no empty data
keys created (all three absent in this fresh dataset). Wildcard ACL intentionally
preserved; strict cross-library permission isolation is not claimed.

Observed resource names differ as intended:

| Resource | SDKU | CSPA |
| --- | --- | --- |
| Kafka | sdku-main / sdku-main-compact / sdku-alarms / sdku-alarms-compact / sdku-ack-alarm | cspa-main / cspa-main-compact / cspa-alarms / cspa-alarms-compact / cspa-ack-alarm |
| Redis dm-meta / alert-hdl / alert-class | sdku-dm-meta / sdku-dm-alert-hdl / sdku-dm-alert-class | cspa-meta / cspa-alert-hdl / cspa-alert-class |
| PostgreSQL | sdku_alarm_view | cspa_alarm_view |
| ClickHouse | sdku_dm | cspa |

Actual consumer subscriptions now include the respective ACK/alarms topics and
assigned partitions after SSL correction. Three replicas with a single partition
can have idle consumers; no successful business-message processing is claimed.

Public endpoint acceptance remains incomplete: SDKU HTTPS200 observedall3;
CSPA hostname absent from authoritative DNS and system lookup, curl exit6.
The normal run was cancelled before endpoint publication completed. Owner's
Docker-only scope respected: no manual DNS/HAProxy edits and no further plan.
CSPA direct HTTP200 does not imply published HTTPS endpoint PASS.

Safe local evidence under .runtime/qa/: sdku-cspa-smoke.json (Docker-only PASS),
sdku-cspa-logs.json (full current-start counters), sdku-cspa-logs-stable.json,
sdku-cspa-resource-projection.json, sdku-cspa-db-check.json,
sdku-cspa-redis-check.json and sdku-cspa-docker-health.json. Earlier public smoke
failure retained in sdku-cspa-endpoint-observation.json. Application protocol
correction in project application-packages/alarm-view-service/1.0.0 defaults.
Final Docker evidence per-host sdku-cspa-docker-ssl-{101,102,103}.json.

Cleanup: original restart=always restored for all9 previously paused old
HMI/scheduler/status containers with exact original ID/ownership checks; all
remain stopped. Unused sentinel diagnostic overrides101/102 and exact empty
diagnostic network102 removed. CSPA103 retains its used .qa-kafka-protocol.yml
override, equivalent to the corrected base manifest; its Compose config hash
already matched, so it was not restarted solely to alter config_files labels.
Temporary CH diagnostic private key/password files removed from failed run103;
safe logs retained. Owned qa-sync workspace23bd... on102 cleaned using qa-sync.
Verified local47 and published runtime preserved; shared acquisition input and
current Vault generation4 recovery custody untouched. No visual/UI business
acceptance claim and no accumulated changes committed in this continuation.

Owner then requested common Redis ENV in library defaults and identified
TN_SCADA_METADATA_TOPIC as another alias. Preparation source changes move these
shared variables out of three application packages into library defaults and
refresh catalog digests. Current-tree RED OS package validation PASS:27 schemas/
digests,26 Compose renders, one shared base. This does not validate the later
Redis binding extension.

Runtime44 verified907 components, standard publication/preparation digest
`sha256:7f4362070a3a7ec07be9dd9eaf0de607f7b3703a12912c18ca83fc920adbd8be`.
Original alarm-view image b433d144/reference unchanged. Also validated retained
runtime42 locally, removed only its inactive node3 release, preserving active44.
Owned build/source workspaces ec5fb720... and d66f1d76... cleaned by qa-sync.

Actual React/Wails created/saved cspa identity with cspa@1.0.0. Pre-plan Verify
VERIFIED, but the additional prototype REDIS_ISOLATION assertion failed before
any deployment plan/approval/start. No alarm-view container/resources were
deployed. KNP stopped101/102/103 with exact project/library label checks to free
RAM; images, volumes and diagnostics retained. Do not claim server acceptance.

Latest owner steering requests Redis name bindings like database bindings:
dm-meta, alert-hdl, alert-class. Further deployment held for this new contract,
[plan](../redis-key-bindings-plan.md) and its independent review/owner approval.
Original two-library test remains the intended post-implementation acceptance.

Independent Redis FULL PLAN BLOCK: RKB-P01 requires owner approval to remove
early shared-default templating from existing prepare action and evaluate it in
Ansible after identity/resource normalization. RKB-P02 asks explicit mode omission
for Redis name references. [Review](../reviews/redis-key-bindings-plan-review.md).
Owner approved the corrections; the single TARGETED_RECHECK PLAN approved the
revised sequence and mode omission. Original deployment test remains pending;
no alarm-view Start has occurred in this test.

SDKU: existing sdku-dm library identity. CSPA identity was created through UI.
ClickHouse history names derive from library identity; PostgreSQL alarms_db and
Kafka names differ in resource_defaults. Instance-only differences: CSPA port,
memory/pool limits needed for simultaneous operation. Runtime and server
acceptance pending; no success claim yet.

Space: validated retained local runtime40; removed only its inactive node3
release after exact digest/manifest/current-symlink checks. Active43 retained;
node3 free space4.1GiB. No images, volumes, databases or diagnostic logs removed.

## Redis bindings implementation and QA, 2026-10-20

The three logical Redis references are dm-meta, alert-hdl and alert-class.
They project names only; Core creates no key data, ownership markers, TTL or
delete jobs. Source application wildcard ACL defaults remain unchanged. The
portable two-library test package explicitly binds its own grants to these
three resource names; future server ACL results concern that project only.
Frontend-only libraries without these references are outside this acceptance.

Standard Ansible tasks own resource-default precedence and fresh library_resources.
The existing sanitized prepare-action templar is reused for upstream defaults and
late shared ENV only. No new Python script or parallel desired-state store.
Built-in lookup alternatives did not preserve both deferred evaluation and the
existing raw-host isolation. Initial full Core run:84 PASS, one existing skip,
one diagnostic-visibility failure (86 total). Rejection itself worked; a public
static Ansible assert now reports PROJECT_SNAPSHOT_INPUT_INVALID without values.
Final focused44 PASS; SDKU27 schemas/digests,26 Compose renders and shared base
PASS; frontend263 tests/build/lint and Go tests/vet PASS. Final full87 finished
in449.153s:86 PASS, one existing skip, no failures.

Runtime45 digest
`sha256:c8cfe4fd72724366e96c4579af9e3dfa2096263a1812dc20b0c7c3c1fcab90dc`
verified907 components, published by standard publisher and prepared by real UI.
All five affected runtime component hashes match current source. Frozen26-code
fingerprint `4d39777f06259e835bf5a423dbb50b73872bed49c3312479fbe108e556794f90`.
FULL DIFF static pass has no new proven blockers; terminal verdict awaits final
Core87 and real React/Wails CRUD/fresh-plan evidence. No deployment approval/start.
Inactive node3 runtime43 was locally verified before exact release removal;
runtime44 retained. Obsolete owned source/build root48824e9a was cleaned through
qa-sync after local runtime45 validation; current c55145cb source retained for QA.

Real React/Wails Redis add-from-default, name override, reset, Save and reopen
PASS. Default/reset revision
`sha256:3eb14093b18ea991bdfbd4025f84e5b0d8df3194b91124bc65b3ed2542b3c184`;
override revision
`sha256:ceb1b2164bcc1a8084efd5f8372370c929e551d081e6ab3365582d8e133bb7a0`.
Effective names sdku-dm-meta -> custom-meta -> sdku-dm-meta; both ENV aliases and
test application's own ACL agree. CSPA stays cspa-meta; no authored mode or
reset name remains. No context rebind required in this run. This is real handler/
bridge acceptance, not visual inspection. Fresh plan
`plan-f6034750a521ef5aa5d22896` EXECUTABLE for reset revision3eb14093b18e;
only APPLICATION_LIBRARIES_APPLY/VERIFY, skipInfrastructureVerify=true,
approved=false. Plan-only driver cannot Approve/Start. Both library/three-host
projections have distinct Kafka/DB/Redis names and matching ENV. Runtime45 is
the prepared execution runtime. Independent [FULL DIFF](../reviews/redis-key-bindings-diff-review.md)
APPROVE, zero unresolved blocking findings. Final source fingerprint unchanged.
Final c55145cb QA source cleaned with standard qa-sync after terminal87; shared
acquisition input remains intact.

## Authorized deployment

Final project path/folder tree and resolved resource-name table shown to owner
again before execution. Read-only comparison confirms library definitions differ
only in name/resource_defaults, no library overrides/connection_defaults; both
have10 resources and one shared application package. Actual real React/Wails
fresh Plan/Approve/Start with skipInfrastructureVerify=true, exactly Library
Apply/Verify. Plan plan-f6034750a521ef5aa5d22896; revision3eb14093b18e;
run `installer-d8e1f4bf1643318ecf966eead3ba8c08` STARTED. No Infra Apply/Verify.
First run FAILED before target resource/container work at Require successful
standalone authority preparation (sequence348). Public event preserved only
ANSIBLE_ASSERTION_FAILED. Separate target-free Ansible reproduction of the same
saved run project/projection reported provider_status=PASS, runtime_status=BLOCKED,
runtime_code=APPLICATION_RUNTIME_DEFERRED_FEATURE; changed0, failed1.
Cause: application_runtime.prepare_runtime retained the pre-Redis resource-kind
allowlist. Added redis.key to that existing allowlist and one runtime-preparation
regression with all three references. Current-tree RED OS runtime/provider suite:
39 total,38 PASS/one existing skip,1.214s. No new resolver, lifecycle or authority.
This is a bounded correction within the already approved reference contract;
review procedure's LOW-RISK bounded-fix rule applies, not a new architecture
review cycle. Initial FULL DIFF evidence remains specific to its recorded hash;
this later two-file correction is recorded separately. Runtime46 validated907
components and standard-published digest
`sha256:26fdbfb766ce9b7b3a8b09b973d597501985231e3cfb9f6fdd03525459ff7d78`.
Only one bundle component changed relative to45; source hash9c56f66adc7ca9387cca367870a8b30c10ad54d33ecbc6927c83eee7f0b2aecf
for application_runtime.py; regression file hasha9a17c19c8b9b1abfef9775672bd8ff5a315800db9bc38572120ae40e8793af3.
Initial UI attempt before session restart returned PROJECT_VERIFY_FAILED with no
plan/start; retained before-restart evidence. Restart loaded the new published
runtime, real preparation/Verify PASS. Target-free reproduction with corrected
runtime and identical first-run inputs: provider/runtime PASS, code NONE,
184ok/changed0/failed0. Fresh plan plan-a9f75f194efb00a2f6444b1c, revisiona3d7b5de;
real UI Approve/Start run `installer-a572694d80d8ddcff31b4a60ca45c37e`, RUNNING.
Exactly Library Apply/Verify, skip=true. Owned d69f3d33 QA build/source cleaned.
Second run a572694d FAILED before mutations at Vault document preflight,
sequence910. Actual provider sys/mounts read with TLS returned200: secret/ is
KV v2, applications/ absent. The original working project used installation
override mount=secret; test package preparation had retained package mount
applications. Corrected the shared test application package default to secret
for both libraries; canonical SDKU package/source and both library definitions
unchanged. No manual mount, user or grant creation. Failed evidence retained as
sdku-cspa-alarm-view-run46-vault-mount-failure.*. Fresh real UI Verify and
Core-isolation PASS; new approved plan/start preparation in progress.
Terminal/container/endpoint/database/ACL acceptance remains pending.

Owner requested local .runtime disk cleanup during deployment. Automatic command
policy rejected both bulk and single explicit recursive delete; agent performed
no deletion through an alternate tool. Generated fixed41-path cleanup script,
corrected PowerShell5.1 nested-array reading after user's report. User ran it;
read-only confirmation: all41 obsolete bundle directories absent, C: free101.2GiB
versus10.7GiB, approximately90.55GiB freed. Active45/46, desired projects,
source images, secrets/identities and diagnostic evidence retained. Cleanup list
is .runtime/qa-cleanup-20261020.json (runtime-only metadata).

Further preflight attempts and owner clarification:
- Run9e91982b failed at Redis/Sentinel preflight (sequence1046), before provider
  mutations. The test had introduced an unrequested three-name ACL restriction;
  existing SDKU account had wildcard keys/channels. Source preflight rejects
  broad-to-narrow changes. Raw hidden module output was not obtained; read-only
  ACL inspection and the matching source guard establish this mismatch.
- Run504707ef, prepared with isolated usernames, was CANCELLED and confirmed
  through the existing Wails CancelInstallationRun API before resource work.
  This is not a React Cancel acceptance claim. After the owner's question,
  restored original usernames, wildcard keys/channels and +@all -@admin client
  policy; Sentinel retains its explicit command set. No cross-library Redis
  denial policy is required. Distinct configured Redis names remain required.
- SDKU ClickHouse sdku_dm already exists under the earlier analytics ownership
  identity; this test references it as existing history instead of re-owning it.
  Run391e3984 failed at authority preparation (sequence350): Core currently
  rejects a managed SQL account for an existing database resource. For this
  test the already-created SDKU ClickHouse account is also existing; CSPA DB
  and account remain managed. No Core account-mode redesign or manual grant.
- Two project Verify attempts rejected incorrectly located/incomplete account
  overrides. Correct portable location is application.accounts.clickhouse,
  with mode=existing and required credentials={} merged with package defaults.
  Neither rejected attempt reached Plan/Start.

Owner instructed continuation after the account-mode explanation. Real React/
Wails Project Verify VERIFIED, fresh plan plan-3c32e1941278db3394bd2fa6,
revision814f67bc6ca4921dbfc40bd32f23981bc78bd4ee3417a99622159788a1b660d9,
run installer-73fd8e8ea51e5b07e23e2d75f305f268 STARTED on runtime46.
Exactly Library Apply/Verify, skipInfrastructureVerify=true. Terminal and
six-container acceptance pending. Failed/cancelled attempt evidence retained
under .runtime/qa/application-design/sdku-cspa-alarm-view-run46-*.

Run73fd8e8e FAILED, terminal sequence614. Task Discover the selected Docker
account on node2 timed out after10113ms (sequence538,
ANSIBLE_CONNECTION_TIMEOUT). Account-mode authority preparation passed.
Read-only diagnosis: 102 responds to ping but SSH banner exchange times out
from Windows and through101; ClickHouse HTTPS also times out. VirtualBox reports
RedOS-8.3-2 running,5246MiB/one CPU; console screenshot clock stopped at10:34.
No reboot/reset performed without owner response. On101/103, unexpectedly
running old HMI/evo-scheduler/status-calculation test containers were stopped
to reserve memory for the two alarm-view instances. Available memory afterward
1375MiB/2044MiB respectively. No images, volumes or infrastructure services
removed. Evidence retained as run46-node2-timeout.*, console screenshot in QA.
Owner asked whether to authorize VM102 recovery; deployment acceptance pending.

Owner explicitly authorized reboot, including reset if hung. ACPI power button
did not recover102 after approximately40s; approved VirtualBox reset completed.
SSH recovered, uptime1min. Old KNP/HMI/scheduler/status containers auto-started
on boot and were stopped; existing SDKU alarm-view retained for plan reconcile.
Node102 available3419MiB afterward, swap4095MiB/used0. Previous-boot kernel
journal query returned no matching OOM/hung-task lines; root cause of the VM
freeze is not established. No claim that account-mode configuration caused it.
Fresh real UI attempt continues with unchanged desired revision/runtime46.
Real UI fresh Plan/Approve/Start after recovery: run
installer-02fa30f6c18e6d5200fab391e39cff8c STARTED. Same revision814f67bc,
runtime46; Library Apply/Verify only, skip=true. No Infra Verify performed.

Run02fa30f6 FAILED sequence904 at Vault endpoint mount/auth discovery,
sequence902, after Docker preflight passed. Repeated original Ansible uri
settings on103 (same runtime46, saved provider CA, TLS validation, no redirects,
timeout10, token only in runtime environment): sys/mounts200, sys/auth503.
Only paths/status/classified cause emitted; no response body/cookies/token.
Direct health:101 initialized/unsealed/standby,102 initialized/SEALED,
103 initialized/unsealed/active. Thus the reboot left102 sealed and public
endpoint requests intermittently reach that backend. No TLS failure in probe.
Evidence: sdku-cspa-vault-ansible-diag.log; run46-vault-after-reset.*.

Recovery custody: original project/deployment-matching output package39842c41
on101 has a different admin token from current accepted Vault credential;
guard stopped before any unseal API call. Delivered encrypted package1e2ed53b
under full-services matches project/deployment and both receipt ciphertext
digests, but known QA passwords cannot decrypt it. No shares were applied,
printed or copied to project. Owner asked to unseal102 or supply the export
password through .runtime/secrets/vault-recovery-password (never chat).
No containers/endpoints accepted yet. Further deployment awaits this prerequisite.

Owner supplied export password through the conversation; value retained only in
runtime secret input, never in this journal/project. Generation2 export decrypted
and receipt digests matched, but its token differed and one bounded unseal attempt
was rejected; it belongs to a former initialization. Existing current-bootstrap
QA evidence points to generation4 protected custody under the preserved98352733
QA workspace on101, package78545e51/source rune957af66. Standard Ansible tasks
verified projectId, generation4 and exact equality with the current accepted
admin token before using its shares. Unseal102 succeeded; sealed=false asserted.
No Vault reinitialization, policy/grant/user changes or new Python scripts.
Repeated original Ansible uri probe now sys/mounts200 and sys/auth200, timeout10,
TLS validated. Old decrypted temporary shares file removed locally/remotely.
Current generation4 custody retained for future reboot recovery. New real UI
fresh Plan/Approve/Start attempt continues with unchanged revision/runtime46.
Fresh real UI retry: installer-dbb9d29b9bed7e05e734c81210f4c745 STARTED
2026-10-20T08:13:26Z; revision814f67bc, runtime46, Library Apply/Verify only,
skipInfrastructureVerify=true. Actual container/resource acceptance pending.

Rundbb9d29b FAILED sequence1786 at ClickHouse resource verification. Kafka
topic stage passed; CSPA DB and both tables created on all3. Read-only system
distributed_ddl_queue shows both table DDL jobs Finished/exception_code0 on
all3. Original provider preflight reproduced without writes using the failed
run's project/projection and protected QA SSH identity: exact code
CLICKHOUSE_APPLICATION_TABLE_SETTINGS_DRIFT, changed0. Cause: copied CSPA YAML
resource_defaults encoded two integer settings as scientific-notation floats.
SHOW CREATE preserves 161061273600. and 1048576.; existing comparison converted
expected integral floats to integer strings and rejected equal numeric values.
SDKU settings are integer-encoded and its existing table has integer spelling.
No actual setting values differ. Fixed existing comparison to allow zero-only
decimal suffix for integral numeric values; unequal/fractional changes still
reject. No new Python script/desired-state store/provider rule. Bounded
behavioral fix within approved table contract, LOW-RISK; no new FULL review.
Regression includes three equal encodings and three unequal values. Source
synced with standard qa-sync to23bd8c6f on102. Initial suite5 unit PASS/two native
failed solely because the launch omitted service collection paths; evidence
retained. Rerun with explicit current-tree collection paths is in progress.
Final current-tree provider suite: all7 PASS,315.633s, including standalone and
three-server isolated native cases. Source application_sql.py hash
e3b1746a767e6fdedc51cf73f35f1bdb9b0ad874573f2db5f1ed3c88ff6d3608.
Runtime47 built on trusted102, all907 components verified;906 match46 and only
that existing runtime file changed. Validated/published digest
sha256:a3687b81dd71cd34b5e4fc8deb7dacc0dea0da4a05cf51c1522e8fa32a429b76;
publisher digest matches. Same original alarm-view image/archive retained.
Test native and compatibility artifact locks updated together; no application
configuration changes. Exact owned Wails restarted to load published cache.
Runtime45 full local copy revalidated before deleting its exact inactive remote
release after realpath/current-link/manifest-hash checks;103 free5.9GiB,
active46 retained. Actual UI47 preparation in progress. Before Start, the QA
driver requires the read-only ClickHouse library preflight with47 to pass.
Runtime47 actual UI preparation PREPARED; active link matches a3687b81.
Real Project Verify VERIFIED. Exact standalone provider preflight for both
libraries now PASS under47:188ok/changed0/unreachable0/failed0/skipped24.
No table changes; diagnostic codes empty. Read-only failure reproduced under46
and resolved under47 with identical table definitions/observations.
Fresh real UI Library Apply/Verify/skip=true plan approved, Start pending.
Real UI Start confirmed: installer-001b0038e1f70b57f0bb59cf3b499a15,
plan-89475a9b2c3a313dea57dae7, saved revision
9d2b0546b63e9e32be239c0bfdcc889f9d88a8d0d645c8291827d4e88709f2aa.
Exactly Library Apply/Verify, skip=true, runtime47. Deployment RUNNING.
Run001b0038 FAILED at container readiness, sequence2064. All library resources,
Vault roles and provider account stages passed. First CSPA placement on102
restarted twice, no OOM. Safe current container log cause:
java.lang.IllegalArgumentException: Master address must not be null or empty.
Actual ENV has REDIS_SENTINEL_MASTER=redis-1 but
TN_SCADA_REDIS_SENTINEL_MASTER empty: obsolete application default overrides
the shared library value. Removed only this empty duplicate from canonical
alarm-view package and the shared test package; import digests refreshed.
No new library divergence/instance override. Package files are project inputs,
not runtime bundle components, so runtime47 remains valid.

Separate bounded diagnostic start on102 reused the exact existing Compose
project/directory/library .env and image, with a temporary override setting
only TN_SCADA_REDIS_SENTINEL_MASTER=redis-1. No DB/user/grant modifications.
Container healthy/restart0, direct HTTP10022/actuator/health200; safely projected
health statuses db/history-datasource/kafka/redis/evo UP. Initial startup503
settled to200. No response body/cookies/credentials emitted. Diagnostic override
is temporary and will be superseded by the next normal plan reconciliation.
Fresh actual UI Verify/Plan/Approve/Start retry in progress with fixed package.
Package import-byte regression PASS (TestSDKUImportPackageBytes); actual UI
Project Verify VERIFIED, two-library projection valid; exact CH read-only188ok/
changed0/failed0. Real UI fresh approved plan plan-f60e3ef1730c53fceb7143af,
revision835dd1c116cb08f292b2f4d373819b4fb400579d1109a060ae194078bd98ee73,
run installer-7829c2cdf6bd51ee8cb49299dd6b3349 STARTED. Runtime47,
Library Apply/Verify only, skip=true. Six-placement/endpoint acceptance pending.
Run7829c2cd FAILED readiness on node1 (sequence2064,125437ms), not node2.
CSPA101 has correct node1 name/labels/image and restart0. Its first successful
Docker health arrived about177s after start, beyond the previous wait; later
checks alternated success/failure. No host-placement bug established.
Safe Actuator component sampling isolates the transient OUT_OF_SERVICE to
Kafka TimeoutException; PostgreSQL/ClickHouse/Redis stay UP. Binary inspection
of existing alarm-view image's evo-services-1.7.44 KafkaHealthCheckConfig shows
evo-services.consensus-service.health-check-timeout default250ms.
Only test instance group_vars overrides updated for both libraries:
EVO_SERVICES_CONSENSUS_SERVICE_HEALTH_CHECK_TIMEOUT=5000, readiness healthcheck/
retries90/delay2. No library differences or global timeout/default changes.
Separate bounded diagnostic Compose override on CSPA101 confirms all3 sequential
health samples UP with5000ms; CSPA102 still on250ms shows one Kafka timeout in
the same sample sequence. Health checks remain enabled. New normal UI plan
retry in progress to reconcile all selected placements with these test settings.
Project Verify rejected retries90 before Plan/Start because published settings
schema maximum is60; no target execution from that rejected attempt. Corrected
only test group_vars to retries60/delay5 (nominal300s plus command execution).
Actual Project Verify VERIFIED; two-library projection valid; CH read-only188ok/
changed0/failed0. New real UI Plan/Approve/Start run
installer-9df9297e36d41ae592cc64fd259a1114 STARTED2026-10-20T09:50:44Z,
runtime47, Library Apply/Verify only, skip=true. Acceptance still pending.
Run9df9297e FAILED at later SDKU101 readiness, sequence2244. Preliminary
readiness/AppRole scopes passed. Live observations initially looked inconsistent
with the event host; actual Ansible inventory has node1=101 and public Compose/
container labels are correct. No placement defect established. SDKU101 had
exit128/OOMKilled=false and explicit State.Error: runc create failed, container
with given ID already exists. Same pre-existing failure on stopped SDKU103.
Node101 briefly stopped answering new SSH, then recovered with load112.51,
5GiB RAM/no swap; no matching kernel OOM records. These observations do not
prove memory pressure caused the stale runc state.

Existing /dev/sda3 partitions on101/103 verified TYPE=swap and activated
explicitly (4GiB each); swapon -a had no effect because no fstab entry.
No new partition/file or persistent fstab change. Node102 already had4GiB swap.
Bounded recovery checked exact project/library/instance/host labels and the
specific failed-runc state, then Docker Compose force-recreated only stopped
SDKU101/103 from the desired Compose/.env already materialized by the plan.
Same original image, no pull/build/dependencies/resource/grant/user writes.
Old failed state captured in QA JSON; both recreate commands returned0.
New container readiness/normal-plan completion pending.
Further live inspection found the previous HMI/scheduler/status test containers
auto-started again on101 after the Docker runtime restart, causing five selected
and old app JVMs to compete for memory. Temporarily set restart=no and stopped
only those three exact project/library-owned containers on each host; original
IDs/restart policies recorded in sdku-cspa-paused-old.json for restoration after
test without starting them. No desired package restart setting changed.
Afterward all SDKU101/102/103 healthy/directHTTP200; CSPA101/102 healthy.
Node101 available1025MiB/swap1879MiB used,102 available880MiB/swap1414MiB,
103 available1268MiB/swap496MiB. No additional recovery/reboot required.
Fresh normal plan retry will create remaining CSPA103 and publish/verify endpoints.
Actual fresh UI Plan/Approve/Start confirmed for recovery: run
installer-6977054dcbab880701ddb2be5fedd9cf STARTED2026-10-20T10:34:06Z.
Same revision152c966e/runtime47, Library Apply/Verify only, skip=true.

### Owner-directed Docker-only continuation, 2026-10-20

Run6977054d reached all six container starts/readiness and endpoint preparation.
Independent current-start log inspection found Java heap space errors even while
the six Actuator endpoints were UP. Effective Kafka config shows Spring SSL and a
separate custom consumer PLAINTEXT against the same TLS9094 bootstrap servers.
OOM stacks allocate HeapByteBuffer in Kafka NetworkReceive; OOMKilled=false and
restart0. Do not classify this as kernel OOM or assume increasing heap fixes it.
Safe evidence: sdku-cspa-kafka-protocol.json and sdku-cspa-oom103.json.

Normal Wails CancelInstallationRun confirmed CANCELLED for6977054d. This is API
cancellation evidence, not React Cancel acceptance. Owner then explicitly directed
that no additional plan be launched: correct parameters and use Docker only.
The shared test alarm-view package's KAFKA_SECURITY_PROTOCOL corrected from
PLAINTEXT to SSL; both libraries continue using the identical application package.
Canonical source package already selects SASL_SSL for its canonical listener;
no blanket source conversion to the test environment's SSL listener is needed.
Library package differences remain name/resource_defaults; test instance heap
remains768m. No new runtime publication, accounts/grants/DDL/topic changes.

Bounded CSPA103 diagnostic Compose override changes only Kafka protocol, same
original image and normal instance project/PKI/credentials. Startup succeeds,
three sequential Actuator samples UP (DB/history/Kafka/Redis), no ERROR/OOM in
new logs. Remaining containers now being reconciled sequentially per host using
normal Docker Compose, updating the rendered protocol to SSL. Final acceptance
is pending. Diagnostic logs remain enabled. No terminal plan success is claimed.

Previous sequential alarm-view test's saved report has zero ERROR on all3 during
its sampled window. The preserved project package also has PLAINTEXT; the exact
historical effective custom-client protocol and why the old observation did not
show OOM are not established. Prior health/HTTP PASS alone cannot prove all custom
Kafka consumers worked. Do not retroactively invent a clean full-data-path PASS.

### Owner-authorized SASL plan retry, 2026-10-20

Owner selected the project from thread 01a1464e-676a-7f41-a0fc-12ee5aaa2350:
`.runtime/qa/sdku-cspa-alarm-view-project`, two alarm-view-service instances
(SDKU/CSPA), three placements each. Owner explicitly requested
`skipInfrastructureVerify=true`; execution scope must remain exactly Library
Apply/Verify. No infrastructure Apply or certificate reissue is requested.

Only this runtime project's desired configuration was adapted: Kafka SASL_SSL9096
and existing admin runtime reference; library Kafka connection defaults SASL_SSL;
per-instance managed SCRAM accounts and topic/group ACLs; producer/consumer JAAS
secret bindings through the existing Vault Agent supervisor; Spring/common/custom
Kafka factory properties select SCRAM-SHA-512. Existing image, resource isolation,
heap/readiness settings and PKI parameters retained. Original desired files backed
up under `.runtime/qa/alarm-view-sasl-before`; no production package changes.

Actual React/Wails Project Verify VERIFIED on runtime48. Initial library-only
plan BLOCKED on three missing offline service artifacts; not approved/started.
Full runtime49 built on trusted node2 from current qa-sync sources and preserved
runtime47 local inputs, without downloads, verified and published normally:
`sha256:470580863f6d418c73954534df75de75d5f378d1389f81038c885cd1c29c3c98`.
Source workspace: `/var/tmp/platform-installer-qa-f9b69d66c6ff4db5b05d78677239c340`.
Original compressed application archive/identity retained with its existing
legacy lock; optional new archive indexing attempt rejected compressed input
before publication. No image loaded/pulled by preparation.

Project runtime locks normalized consistently in project.yml/native inventory;
normal rebind requires catalogLock before artifactLock, so top-level blocks were
reordered without changing their values. Real UI rebind49 UPDATED. Five-minute
desktop Prepare returned BLOCKED/EXECUTION_NODE_UNAVAILABLE after staging the
large bundle; no library run started. SSH remained available; existing Kafka and
Registry active. Standard CLI preparation (existing 30-minute operation context)
returned READY/Changed=false on the exact digest; the runtime was already ready,
so no repeat activation was needed. The five-minute desktop context and elapsed
time make a timeout likely, but its original exception was sanitized and cannot
be stated as proven. This is not a claim of successful desktop preparation.
Public pre-run hash baseline:41 files,
`.runtime/qa/alarm-view-sasl-preserve-before.json`. Final execution acceptance
pending. Source/build workspace f9b69d66 cleaned with qa-sync -Cleanup after
verified bundle publication; prior runtimes retained outside the active cache.

Fresh actual React/Wails context READY and Project Verify VERIFIED on runtime49.
Plan `plan-5ae0b0bbc8cf02a17f31f932`, saved revision
`sha256:b7203cc870510b4dd73b0f66802e9695fe1801cfa457ba44af5dce56e3222866`,
approved and started through the real handlers. Exactly
APPLICATION_LIBRARIES_APPLY/VERIFY, skipInfrastructureVerify=true. Run
`installer-a8909032e442344d3b40a912d7f4d837` FAILED at sequence348/350,
2026-10-20T17:09:54Z, Require successful standalone authority preparation.
No account/resource/container/endpoint mutation phase was reached; all41 public
configuration/PKI hashes remain unchanged. Failure retained in runtime evidence.

Bounded corrections in the existing approved SCRAM path:

- `application_runtime.prepare_runtime` retained an obsolete account-provider
  whitelist excluding Kafka, despite existing snapshot/provider support. Added
  Kafka to that guard; resource/unknown-provider/TLS deferral guards unchanged.
  Runtime contract22 tests:21 PASS/one existing skip, including positive SCRAM
  and negative unsupported-provider cases, on primary RED OS.
- A native read-only probe of the exact application ACL task reproduced a false
  missing IdempotentWrite: YAML double-quoted backreference escaping corrupted
  CamelCase normalization. Changed only the expression's YAML scalar quoting.
  Native3 tests PASS for existing CamelCase operations, missing operations and
  rejecting other principals/hosts/DENY. No grant or security boundary widened.
  Other stock Kafka service Apply/Verify defects remain outside this correction.

Source workspace3d389748 synchronized and verified with qa-sync; native tests use
those exact current files. These are compatibility corrections to the approved
account/ACL contract, with no new owner/persistence/security architecture.
Runtime50 rebuild/publication completed and a fresh actual UI plan started as
recorded below; first plan is not reused. User-selected
skipInfrastructureVerify=true remains mandatory.

Runtime50 verified/published normally:
`sha256:d7c911caa3f435fc3cdc3933f2a6cf7548bc0271e7f2a5e06f0dd828892bd786`.
Same approved local inputs, unused probe image excluded; original alarm-view
archive retained. Standard CLI Prepare READY/Changed=true; actual React/Wails
rebind UPDATED, context READY, Project Verify VERIFIED. Source/provider23 and
native administrative provider4 additional tests PASS. qa-sync final source
verification PASS, workspace3d389748 cleaned with standard helper.

Additional raw-project standalone resolution probe on node2 failed at snapshot
before runtime preparation; safe diagnostic attempt also failed before exposing
its code. No target mutations, no PASS claim for those probes. Temporary QA-only
diagnostic instrumentation restored in finally; source verification afterwards
PASS. Actual saved-project UI/Execution Node validation on runtime50 VERIFIED.

Fresh plan `plan-184ca6dc279249763076d13e`, revision
`sha256:4afcb8ef15409f722a14fa9639b5cbc14a8076ca5ed753ddd092fe935d235895`,
approved/started via real handlers. Run
`installer-d9b527d605c09c3e97e270c27128255e` FAILED at sequence2542,
Check only Core-projected Compose values, after provider resources/accounts/ACLs
and Vault publication but before container activation. Exactly Library
Apply/Verify, skipInfrastructureVerify=true. Compose consumed unescaped JAAS
references before Agent startup. Four JAAS references in the runtime project now
use `$$`; no weakening of the Core Compose projection guard. Final normal
SASL/application/endpoint acceptance remains open.

### Owner-authorized single-container Agent demonstration, 2026-10-20

Owner requested direct startup without an Installer plan before further normal
execution. Scope is only `alarm-view-service-cspa-node2` on node2. No new plan
approved/started; this demonstration does not replace React/Wails acceptance.
Existing image loaded from the already approved local archive, exact image ID
`sha256:b433d1444aa820debe45e69c69b4e3ab7963d72d855df5b6e554788f2ca36b8f`;
no registry pull or acquisition. Existing SCRAM user/password and PKI retained.

Simple Ansible tasks read the owned existing account document over verified
HTTPS, generate complete producer/consumer JAAS in private provisioning memory
and add the two same-named Vault fields with CAS, preserving existing fields.
Agent env_templates now read those fields directly. The admin token uses a
private temporary runtime secret file removed by a shell trap; no token in argv
or public artifacts. Original instance Compose/Agent files preserved privately
on the host for recovery. Shared base-compose is not edited.

First startup exposed unsupported `spring.kafka.ssl.properties.*` and
`custom-kafka.ssl.properties.*`: SslProperties.getProperties() computes a map,
not a writable binding. Those six runtime-project values were removed. A second
startup became healthy but exposed a separate WS consumer using SSL/PLAIN on
9096. Read-only inspection of this exact JAR confirmed
KafkaListenerFactoryConfiguration.alarmMessageConsumerFactoryWS hardcodes those
values when the shared legacy SSL helper is enabled. Disable only
the shared legacy SSL flags and provide explicit truststore properties in both
Kafka maps; network protocol remains SASL_SSL and materialized PKI is unchanged.
Setting only the dotted property did not suppress the inherited true aliases;
the final service-specific overrides are KAFKA_ENABLE_SSL=false,
SPRING_KAFKA_SSL_ENABLE_SSL=false and spring.kafka.ssl.enable-ssl=false.
The original application JAR SHA256 matches the inspected JAR exactly:
`ac619895ab5ce125112c107cae689a4e38ada4a9d17065345e14addd510172e1`.

Final corrected container started at 2026-10-20T18:55:58Z, healthy/restarts0,
OOM=false. All9 logged producer/admin/consumer configurations, including WS,
use SASL_SSL/SCRAM-SHA-512 on9096. Six successful group joins and7 assignment
messages; application Kafka health reports true. No authentication/authorization
errors, no Kafka password in Docker inspect or logs, both Java JAAS values match
the existing protected credentials. Two startup ERROR lines concern the existing
3500ms committed-offset timeout; retained, not claimed error-free startup. Final
30-second observation:0 bootstrap disconnects,0 ERROR,0 TimeoutException.
Business message/WS semantics and normal six-container plan acceptance remain
open; only this single manual container has been started in this follow-up.

Public runtime evidence is under
`.runtime/qa/alarm-view-agent-manual-evidence/`: Compose, base-compose, Agent HCL,
sanitized Docker inspect ENV and boolean-only secret checks. Earlier failed
observations retained separately. Verified so far: Java receives both exact
JAAS credentials, Docker inspect contains references but neither JAAS ENV value
nor Kafka password. Kafka/Registry and neighbor public configuration/PKI hash41
comparison unchanged.

Owner additionally removed Kafka topic preflight from the library provider
stage; topic Apply and final Verify remain. Current-source provider23 and
provider-stage native syntax PASS on node2. This change is not yet bundled or
executed through a new normal plan. New runtime51 was not built/published.
The ready-JAAS provisioner source adaptation was not implemented. The owner
subsequently chose the original Agent-side assembly instead, as recorded below.

### Owner revision: Agent JAAS assembly and omitted legacy SSL flags

Owner requested username/password-only Vault storage and no explicit ssl=false
configuration. The existing `format: kafka_scram_jaas` implementation already
supports this: restore its two original env_templates with JAAS quoting, keeping
all other Agent bindings/supervisor settings identical. Fifteen current-source
Vault/Agent projection tests PASS on node2 in qa-sync workspace3d261613.

The selected SASL library defaults in the runtime project (SDKU/CSPA) no longer
declare KAFKA_ENABLE_SSL or SPRING_KAFKA_SSL_ENABLE_SSL. Alarm-view no longer
declares either alias or spring.kafka.ssl.enable-ssl. For this single manual
CSPA placement, remove the same keys from shared base-compose and instance
Compose; explicit Kafka SASL_SSL/SCRAM-SHA-512 and truststore properties remain.
No empty/null flag substitutions, hidden false flags or JAR/image modifications.
The four excluded application default files are SHA256-unchanged.

Simple Ansible tasks preserved the previous working files and restored exact
existing Agent formatting bytes after checking all other nonblank content.
The first comparison rejected only added blank separators and stopped before
configuration/Vault mutations; normalized comparison retained identical content
outside the two expected JAAS blocks. CAS then removed only the two derived
JAAS fields: current KV v2 version3 has username, password and owner; existing
credentials unchanged. Earlier KV history is preserved. Only the selected
container was recreated; no Installer plan or infrastructure Apply launched.
Final single-container check PASS: healthy/restarts0, no authentication,
authorization, heap or ERROR messages in this corrected start. All9 logged
client configurations use SASL_SSL/SCRAM-SHA-512, the existing PKCS12 truststore
and ssl.endpoint.identification.algorithm=https. Six group joins and6 assignment
messages observed. The three legacy flags are absent from Compose, base-compose,
Docker inspect and Java ENV; no SSL=false ENV variables remain. Both Java JAAS
values match the unchanged protected credentials; no Kafka password in inspect,
the public files or logs. Agent reads username/password and formats both values;
it does not read ready-JAAS Vault fields. No source provisioner adaptation is now
required: the originally implemented format is reused. Secret current shape is
recorded redacted beside the refreshed runtime configuration evidence.
Final qa-sync source verification PASS; workspace3d261613 cleaned with the
standard helper. Final Kafka/Registry/neighbor public hash41 comparison unchanged;
four excluded application-default hashes unchanged. No commit or bundle build.

### Fresh normal retry authorized after the accepted Agent/SSL correction

Owner requested removal of topic preflight and a fresh normal plan. The existing
working-tree removal is exactly the nine-line Kafka topic preflight include;
topic Apply/Verify and account credential/ACL preflight remain. Current-source
provider23 and provider-stage native syntax PASS on node2, qa-sync identity
verification PASS. Runtime51 built on trusted node2 from the same approved local
inputs and published through the standard publisher:
`sha256:6978cd89ce7ec135a0aa2437ab24db2b48788434caa19d2c44197c77408c1b94`,
version `alarm-view-sasl-20261020-51`. Source/build workspacee71c552e cleaned
through the standard helper after verified transfer. Prior runtime50 preserved.
Standard CLI Prepare READY/Changed=true for the exact published digest. Actual
React/Wails rebind UPDATED, Project Verify VERIFIED, all6 placements assert
SASL/SCRAM/truststore and omitted legacy flags. Fresh plan
`plan-d3869c2dee3e6094bd7c720b`, saved revision
`sha256:206153d0dfaa1bf20326c8400a69f6f8566a5ed5036aa280bfc6d4f5e380dff6`,
approved/started by the real handlers. Run
`installer-8b1d1f65df08e5ea7b9392361f3e7ede` terminal FAILED at endpoint Verify
on 2026-10-21T06:10:26Z; details below.
The retry is restricted to Library Apply/Verify, skip=true, same two
instances/six placements, original image and PKI, Agent username/password JAAS
formatting and omitted legacy SSL flags.

### Runtime51 terminal and owner-authorized optimization, 2026-10-21

Apply SUCCESS: 2026-10-20T19:34:25Z–20:44:32Z, 70m07s including preflight.
Stage intervals from the public event journal (sequential, no nested sums):

| Stage | Duration |
| --- | --- |
| Preparation and preflight | 18m06s |
| Ten Kafka topics | 9m25s |
| Other provider resources/accounts and library secrets | 1m42s |
| Kafka instance users/ACL in Apply | 8m54s |
| Instance Vault/AppRole and Compose preparation | 2m30s |
| Six-container image delivery, activation and readiness | 24m14s |
| HAProxy/DNS/HTTPS publication and checks | 5m16s |

Within container activation: exact image/ownership/readiness tasks 11m56s;
archive copies 2m52s; docker load 4m56s. Preflight16 ACL reads total373s;
preflight+Apply32 ACL reads total716s. Ten topic descriptions and ten effective
config reads total484s. These are measurements of runtime51, not predictions
of optimized performance. Night workstation/VM suspension interrupted Verify;
its raw wall-clock duration is not a valid performance benchmark.

Final Verify FAILED: event5088 reports SDKU endpoint actual503/expected200;
event5090 fails `Require a routed HTTP response other than HAProxy unavailable
statuses`; result EXECUTION_OPERATION_FAILED at 2026-10-21T06:10:26Z. All10
topics, both SCRAM logins and16 final ACL checks had passed before this failure.
The original browser observer froze at seq4341 across the workstation pause;
terminal/status/result and public events were independently read from the same
Execution Node run (seq5092). No replacement plan/start was issued.

Independent six-container observation before the pause: six healthy/restarts0;
54 logged client configurations all SASL_SSL/SCRAM-SHA-512 with expected truststore
and HTTPS hostname validation. Exact Agent JAAS values/identities matched; no
legacy SSL flags, Kafka password in inspect or logs. This did NOT prove full
application acceptance: five containers logged topic authorization errors;
CSPA node2 requested sdku-ack-alarm. Both libraries use the same fixed ACK group
alarm-view-service-ack-alarm-listener despite separate users/topics; group
collision is a suspected cause, not an independently proven root cause.

Owner then observed SDKU node1 Exited128. Read-only Docker inspection confirmed
stopped at 2026-10-21T06:01:59.768Z, OOMKilled=false; State.Error is
`failed to create task for container: failed to create shim task: OCI runtime
create failed: runc create failed: container with given ID already exists`.
CSPA node1 stopped at the same second and restarted at06:02:13Z, later healthy.
The restart initiator and cause of stale runc state are not established. The
earlier six-container healthy observation is not current readiness acceptance.
No container/runtime repair was performed during this observation.

Post-run Kafka/Registry/neighbor public hashes41 unchanged; initial public
evidence scan2/0 findings PASS. Four excluded applications remain out of scope.
Owner authorized after terminal: batch ACL reads in preflight/Apply, batch
topic discovery/config reads, and narrowing library Verify to container
identity/running/healthcheck and endpoint only. Implementation and isolated QA
are recorded below; no new deployment or bundle activation is implied.

### Batch discovery and bounded library Verify: source/isolated QA complete

Implementation uses builtin Ansible command/set_fact/assert/include tasks;
no production Python helper was added. Library Verify no longer imports the
provider verification stage and disables the runtime role's Vault verification
only for this entrypoint. Exact image/ownership/running/configured healthcheck
and endpoint checks remain. Apply/direct role use defaults to Vault verification;
explicit provider Verify tasks remain available. No infrastructure Verify change.

ACL inventory is read once per principal in each invocation, including the
existing compatibility-principal helper. Grants select exact resource type/name/
pattern before matching principal, wildcard host, ALLOW and operations. Additions
remain per missing declared resource; unrelated ACLs are not removed. Kafka topic
metadata is read once with an escaped anchored union of declared names; configs
are read once including inherited defaults and isolated by exact topic header.
Required topics retain readiness retries. Missing managed topics are created
individually and freshly described/config-read; existing-topic drift still fails
without mutation. The creation decision is frozen before read-back updates the
observed metadata, avoiding inherited block conditions skipping validation.

RED OS node2 current-tree workspace
`/var/tmp/platform-installer-qa-c295a258911242359fdac9a413e91dd5`:
7 native batch/entrypoint checks +4 native ACL predicate checks +23 provider
projection tests +4 admin-provider tests +22 runtime-contract cases:
59 PASS/one pre-existing skip. Additional native Agent-enabled lean-container
Verify check PASS without Vault/provider credentials, total60 PASS/one skip.
Two playbook syntax checks PASS. Native CLI stubs run in private temporary
directories; no Kafka/target resources are mutated. Successful matching-topic
batch uses exactly2 commands; two ACL grants use exactly1 inventory command;
new-topic creation includes both fresh metadata/config reads and repeat is
read-only. Negative cases cover failed metadata, missing existing topic,
neighbour-topic config drift and resource/pattern/principal/host/DENY isolation.
Earlier failed native runs (type normalization and inherited creation condition)
are retained in local QA logs, corrected before the passing run.

For these two libraries, existing-topic Apply discovery drops from20 to4 CLI
calls; ACL preflight+Apply reads drop from32 to4. Separate library Verify no
longer performs these provider reads. These are verified command counts, not
measured new deployment durations. No updated bundle build/publication/rebind,
fresh React/Wails execution, live performance benchmark, restart or container
repair was performed. HTTP503/Exited128 and ACK-group/application authorization
acceptance remain open; source optimization does not repair them retroactively.
Final qa-sync source identity verification PASS; the temporary node2 workspace
was removed with the standard cleanup helper. Public evidence scan6/0 findings,
four excluded application-default hashes unchanged, git diff --check PASS.

### Owner-authorized recovery and fresh optimized retry preparation, 2026-10-21

Owner requested recovery of SDKU node1, ACK-group isolation and a fresh optimized
Library Apply/Verify plan with skipInfrastructureVerify=true. A direct Docker
start reproduced the stale-runc-ID failure. The affected container alone was
recreated through its existing Compose project
`project-b46aa3f5f57a495f-sdku-dm-alarm-view-service-sdku-dm-node1`, existing
image, env file, volumes and manifests. A preliminary Compose invocation used
the short project name and failed on the existing container name without replacing
it; its newly created empty network was removed. No other container or daemon
was restarted. Final direct status healthy; strict-CA HTTPS SDKU endpoint returned
403 rather than503. This proves routing recovery, not an authenticated business
response.

Exact original JAR SHA256
`ac619895ab5ce125112c107cae689a4e38ada4a9d17065345e14addd510172e1`
contains `AckAlarmMessageListener` with annotation groupId literal
`alarm-view-service-ack-alarm-listener`. It contains no configuration placeholder
for this groupId. General consumer ENV group settings cannot override this
annotation. Choice requested from owner: a derivative local image parameterizing
the ACK group, or an application-supplied corrected image. No image/JAR change
or fresh plan start before that choice. Runtime52 source staging and independent
current-source QA proceed on node2 in temporary qa-sync workspace
`/var/tmp/platform-installer-qa-8e036ea7535341c9bb84f401e8ba0cfc`; original
approved offline input50 is reused, no online acquisition.
Fresh current-source native repeat8 batch/container +4 ACL tests PASS; qa-sync
identity verification PASS. The1.4G offline input transfer completed. Workspace
is retained for the pending runtime build after the image choice; no runtime52
bundle has been built/published and no fresh plan has been approved/started.

Owner superseded the image choice with an explicit ACL solution. Live Docker ENV
and actual subscription logs were read for all6 placements: SDKU subscribes only
to sdku-ack-alarm, CSPA only to cspa-ack-alarm. The topics are not swapped. Logs
show both cross-topic metadata authorization failures, including SDKU node2 on
cspa-ack-alarm and CSPA nodes on sdku-ack-alarm, with the same fixed group.
Project group_vars now explicitly retains the8 original grants for each account
and adds only Describe on the other ACK topic (no cross-topic Read/Write).
The shared group and original image remain; consumer-group isolation was
superseded by owner-approved metadata visibility. No direct ACL mutation occurred
before the fresh plan.

Runtime52 built from current source, same approved input and original archive;
an initial optional image reindex rejected the compressed archive (the inspector
accepts plain tar). The normal builder path used by runtime51 was then reused,
retaining the existing native x-container-images lock. Full standard publisher
verification PASS, digest
`sha256:6da92a23e78692a220b1c90bbf6ea6657860b7d08ec1c640d09e98dd59dd9bd6`,
version alarm-view-sasl-20261021-52. Standard node1 preparation is in progress;
new Plan/Approve/Start still pending at this checkpoint.

### Owner stopped execution preparation; ACK prefix default revision

Runtime52 preparation failed at staging before Plan/Start; node1 had about1.7G
free when inspected. Low space is observed, not a confirmed root cause of the
sanitized staging failure. Owner stopped work; no new plan or live ACL changes
were executed. The diagnostic command was stopped; no disk cleanup was performed.

Owner subsequently chose common-prefix ACK names instead of cross-library grant
overrides. Source SDKU/CSPA library defaults and the same two working-project
library defaults now use ack-alarm-sdku and ack-alarm-cspa respectively. In the
working SASL application's existing Kafka account defaults, one prefixed topic
grant ack-alarm- provides Describe only; Read/Write still come from the exact
ack_alarm topicRef. Both pending cross-topic grant lists in project group_vars
were removed, preserving the unrelated existing ClickHouse account selection.
Main example application defaults do not yet declare a Kafka account, so no
new SCRAM account or listener migration was introduced there by this name edit.

Current-source RED OS read-only validation PASS: four library YAML definitions,
prefix grant normalized by the existing provider resolver, two inventory grant
overrides absent, and KAFKA_ACK_ALARM_TOPIC still references the resolved topic.
Four excluded application-default hashes unchanged; git diff --check PASS.
No Kafka connection, topic creation/deletion, data migration, live grant mutation,
bundle rebuild, rebind or installation was performed for this revision. Existing
stand topic names and messages remain unchanged until an explicitly resumed plan.

### Fresh owner-authorized ACK-prefix run, 2026-10-21

Owner resumed execution for SDKU/CSPA alarm-view only, new ACK topics, optimized
runtime and skipInfrastructureVerify=true. Prior runtime52 staging failure was
resolved before execution: no running installer controller referenced runtimes49/50;
both exact full local bundles passed standard validate-bundle, manifest digests
matched their remote copies, and only those two obsolete chat-owned releases
were removed from node1 after guarding the unchanged active runtime51. Free
space increased1.7G to4.9G. Current release/data/run journals were preserved.
Normal Prepare then returned READY/Changed=true for exact runtime52 digest
6da92a23e78692a220b1c90bbf6ea6657860b7d08ec1c640d09e98dd59dd9bd6.

Prior project bundle51 preserved separately; project imported the verified
runtime52 bundle. Actual React/Wails Rebind UPDATED, fresh SSH fingerprint
confirmation on3 hosts and Project Verify VERIFIED. Core snapshot asserts all6
placements use SASL_SSL/SCRAM, explicit truststore and no legacy SSL flags;
ACK ENV resolves to ack-alarm-sdku / ack-alarm-cspa on the intended libraries.
Fresh real-handler approved plan
`plan-8d80364c2eff8715772ff473`, saved revision
`sha256:4db17c3d100833786cb298b10b8340dca6d2b6eea7933081073b526ece83d85e`.
Exactly APPLICATION_LIBRARIES_APPLY + APPLICATION_LIBRARIES_VERIFY;
skipInfrastructureVerify=true, no infrastructure Apply/Verify or PKI reissue.
Start returned STARTED, run
`installer-bbc4aca2bfd5a29db7800643fc96f540`, Apply started
2026-10-21T07:12:10Z, terminal SUCCEEDED at2026-10-21T08:11:54Z.

### Runtime52 terminal and six-placement bounded acceptance PASS

Same real React/Wails run bbc4aca2 completed SUCCEEDED, result.error=null;
remote public result/status/events independently confirmed terminal at seq4428.
Apply SUCCESS 07:12:10Z–08:06:54Z (54m44s); Verify SUCCESS
08:06:55Z–08:11:54Z (4m59s); full observed run59m44s. No workstation sleep
interruption during this run. Source/runtime/protocol guards were not changed.

| Apply interval | Duration |
| --- | --- |
| Preparation/preflight | 12m26s |
| Kafka topics (including creation/read-back of two new ACK topics) | 6m35s |
| Other provider resources/accounts | 2m15s |
| Kafka instance accounts/ACL | 5m56s |
| Vault/Compose preparation | 2m42s |
| Six-container activation/readiness | 19m23s |
| Endpoint publication/checks | 5m27s |

Live event evidence confirms4 ACL inventory reads total (two preflight, two
Apply),2 batch metadata reads and2 batch effective-config reads,2 fresh metadata
read-backs for the new ACK topics (with fresh configs), and4 missing ACL resource
additions (prefix Describe and exact own new-topic grants for each principal).
There were zero provider/SCRAM/ACL/topic/Vault-secret-read probes during separate
Library Verify. Existing old ACK topics and their data were not deleted or moved.
Runtime51 timing had matching topics already present; these two observations
are evidence from different runs/states, not a controlled performance benchmark.

Endpoint probes in both Apply and Verify returned actual200/expected200, reasonOK:
CSPA events3703/4405, SDKU events3722/4424. Strict HTTPS/CA policy retained.
Initial post-activation and final post-terminal independent observations both
PASS:6 running/healthy, restarts0/OOM0, all54 logged client configurations
SASL_SSL/SCRAM-SHA-512 with PKCS12 truststore and HTTPS hostname validation.
SDKU subscribes to ack-alarm-sdku, CSPA to ack-alarm-cspa; all6 log successful
ACK-group joins/syncs/partition assignments. Auth errors0 and ERROR lines0 in
the fresh containers, with no extra recovery restart needed after this plan.
Both exact JAAS values/identities match the unchanged protected credentials;
legacy SSL flags absent, no Kafka passwords in Docker inspect or logs.

Final Kafka/Schema Registry/neighbor public configuration and PKI hashes41
unchanged; four excluded application-default hashes unchanged. Public evidence
scan10files/0findings PASS. Current-source qa-sync verification PASS and node2
workspace8e036ea7 removed by the standard cleanup helper after runtime activation.
Full prior bundles49/50 and prior project bundle51 remain preserved locally;
active target runtime is52. No Git commit/push or infrastructure service Apply/
Verify/PKI reissue. Other Java apps, business alarm/ACK message transactions,
visual inspection, cold-start and failure-path acceptance are not claimed.

### Follow-up: remove repeated post-readiness Vault probe

Owner requested removal of the additional Vault check after each container and
inspection of other repeated tasks. Container activation now disables the
optional Vault probe in its included Verify, as the final Library Verify already
does. Preflight, Vault publication/ownership/CAS and container readiness remain.
The previous run spent 138s across six placements in this removed segment.
No deployment/restart or runtime52 replacement was performed for this follow-up.

[Repeated-action audit](application-repeat-audit-20261021.md) records remaining
Kafka, ClickHouse, Docker image and projection candidates, measured command
counts/durations and guards that must be preserved. Other candidates have not
been changed. Native RED OS node2 current-source checks:4 PASS/26.767s,
including Agent activation without probe credentials and unhealthy rejection;
Apply syntax and git diff --check PASS. Changed-runtime real React/Wails/target
acceptance has not been repeated; prior runtime52 PASS remains historical.

### Follow-up: Kafka checks only in Apply, without cache

Owner rejected preflight-result caching and requested the simpler single-pass
flow. Removed the Kafka account preflight include from the standard provider
stage; topic preflight was already removed earlier. Apply retains SCRAM metadata,
creation of missing managed users, credential authentication, one ACL inventory
per principal and missing managed-grant additions before Vault instance
publication and container startup. Direct role preflight/Verify remain available.
The unfinished cache implementation, its flags/facts/fingerprints/cleanup and
its failing interrupted test file were removed; no cache was deployed.

For two existing principals with grants, expected metadata/login/ACL CLI calls
are6 instead of12. The removed preflight calls took167.794s in runtime52; actual
changed-runtime speedup has not been measured. Credential conflicts now fail in
Apply, after possible library-resource creation, as accepted by owner.

Current-source RED OS node2 QA:41 PASS in79.034s (native batch10, ACL4,
provider23, admin-provider4); Apply/Verify syntax checks PASS, source-sync
verification and git diff --check PASS. QA ran isolated fake CLI/container
checks without accessing deployed Kafka/Vault/containers. Temporary source
workspaces from this and the stopped cache attempt cleaned with qa-sync.
No new runtime publication, React/Wails execution, deployment, restart,
commit/push or changes to the four excluded applications.

### Follow-up: deployment-wide SCRAM metadata and ACL inventory

Owner requested common reads for all users. Account Apply and explicit provider
Verify now consume Core's existing `application_provider_inputs.jobs` Kafka
deployment jobs with nonempty accounts, rather than one invocation per instance.
Inside each role invocation, one `kafka-configs --describe --entity-type users`
and one `kafka-acls --list --resource-pattern-type any` precede the account loop.
Each account selects its exact metadata header; the existing exact resource and
principal ACL predicate is retained. Partial/failed inventory blocks mutations.
New managed users still authenticate after creation; existing credentials are
never reset. Standalone invocations read fresh state, without preflight caches.
Compatibility ACL hooks keep their separate explicit-principal scope.

Two existing users in one deployment now require4 read/login CLI calls instead
of6: shared metadata1, shared ACL1, separate logins2. Runtime52 Apply logins took
24.349s and23.829s (48.178s total); obsolete preflight logins took27.195s and
27.425s (54.620s total). These are logical-user CLI tasks, not per-placement
checks, and include JVM/Ansible/SSH overhead; no handshake-only timing or cause
of the24s task duration is established. Full breakdown is in the repeat audit.

RED OS node2 current-source focused QA: new native8 PASS/95.255s, ACL/provider/
admin-provider31 PASS/15.176s, Apply and explicit provider Verify syntax PASS,
source-sync verification and git diff --check PASS. Initial native8 run had2
fixture failures: fake login read the first administrative JAAS entry rather
than the application override. Fixture corrected; final8 PASS, production code
unchanged by that correction. Tests cover shared command counts/two logins,
exact user/resource isolation, new-user creation/login/grants, wrong password,
metadata command/partial-output failures, ACL failure and read-only Verify.
Temporary QA workspaces cleaned with qa-sync. No runtime publication,
React/Wails/target acceptance rerun, stand changes, commit/push or excluded-app
edits. The previous runtime52 results remain historical; new timing unmeasured.

### Runtime53: common offline archive barrier — full-plan acceptance PASS

Owner authorized one verification per unique selected offline archive and a full
alarm-view SDKU/CSPA plan with `skipInfrastructureVerify=true`. Target preflight
now selects sources without repeating the archive hash; a common Execution Node
barrier verifies unique full records before Vault/provider stages. Direct role
preflight retains immediate validation by default; target copy hash/size checks
before Docker load remain. No persistent verification cache.

Source QA on current qa-sync node2:28 tests/61.387s, OK(one existing skip):
native6 PASS plus runtime contract21 PASS/one skip; Apply syntax, source sync and
git diff --check PASS. [Independent FULL DIFF](../reviews/offline-archive-diff-review.md)
APPROVE_WITH_CHANGES, blocking0; OAR-D01 remains a nonblocking instrumentation/
mutation-sentinel coverage recommendation.

Runtime53 built on trusted node2, standard validate/publish/prepare PASS:
`sha256:babc408943933b6dc1dd30d043295ded963d1df6d59ba72cbc985d3747bf16a1`,
version `alarm-view-sasl-20261021-53`. Node1 READY. Local bundle52 and previous
project bundle52 preserved; node2 build/test workspace876dc5c9 cleaned.
Fresh neighbor/PKI public-hash baseline41 retained.

Initial real React/Wails rebind UPDATED, Project Verify VERIFIED and all six
SASL/ACK/TLS assertions PASS. First Build returned EXECUTION_NODE_UNAVAILABLE
before Apply. Direct SSH remained available, credential session PRESENT and
node1 free disk2.2GB; underlying transport failure cause unconfirmed. Backend
invalidated dynamic binding and cleared runtime inputs. A partial-resume QA
driver could not navigate its fresh frontend without loading the project; it
did not execute an installation.

Full UI reopen/trust/context/input flow restored READY and VERIFIED. Next Build
took70.381s and produced approved plan `plan-0c460d1f472fd27eff988518`, revision
`sha256:be3c233e9156e3040fbe69ca917b223dd54bcb9c1a45a9cfc6eb4875b18d395f`.
Only Library Apply/Verify, skip=true. QA driver held before Start because its
explicit start environment flag was absent; this plan did not execute.

Final full real React/Wails flow with the existing QA start flag enabled:
fresh Build71.756s, plan `plan-0c460d1f472fd27eff988518`, same saved revisionbe3c233e
above, actual Approve/Start PASS. Run
`installer-85ecd43062556b60ffbecc5e32f3f350` RUNNING; Library Apply started
`2026-10-21T09:44:28Z` /12:44:28MSK. Exactly Library Apply/Verify, skip=true.
Second Kafka login assertion failed before Vault/container activation. Terminal success acceptance is pending. Evidence prefix:
`sdku-cspa-alarm-view-sasl53-run`; prior first/resume/retry evidence preserved
separately. No commit/push or infrastructure service Apply/Verify in this scope.

Live archive checkpoint PASS: six original per-placement integrity tasks SKIPPED;
common unique-record integrity task SUCCESS at seq926,09:51:03Z, elapsed14.158s.
The actual execution project's native image lock contains one image and one
unique archive record(ref/sha256/size), bundle digest matches runtime53.
This source-lock observation plus the successful nonempty unique-record loop
confirms one shared archive verification. Resolved Ansible facts are not stored
in runtime-projection.json; the safe metadata proof reads the actual copied
project lock instead, never emits private projection or credentials.
This is a call-count proof, not a controlled cold/warm performance benchmark.

Follow-up diagnostics: both live Kafka credentials authenticate successfully (CSPA13.416s, SDKU12.882s); existing six containers healthy/restarts0/authErrors0, JAAS inputs match protected local runtime inputs. Public neighbor/PKI hashes41 unchanged. No password reset or production change. Cause of the single login failure remains unconfirmed. Fresh full React/Wails retry uses the same runtime53 with a QA-only equality audit of the two Kafka input payloads before forwarding unchanged to the real binding: both match. Build76.233s, same plan/revision, Library Apply/Verify only, skip=true; Start/terminal pending.

Additional distinct-password single-batch native test PASS21.413s. Full nine-test repeat: seven PASS, two subprocess timeouts60s (354.392s total); retained as FAILED, no production timeout changed. Repeat the two timed-out tests after the active installation to avoid concurrent QA load.

Fresh full UI retry actual Start PASS: installer-f217c7d0abb725c01d4f32bc31e930ef, Apply started2026-10-21T10:31:10Z /13:31:10MSK. Same plan0c460d1f/revisionbe3c233e/runtime53, only Library Apply/Verify, skipInfrastructureVerify=true. Terminal acceptance pending. Evidence prefix sdku-cspa-alarm-view-sasl53-confirm.

Confirm-run checkpoints: archive barrier one SUCCESS37.744s; both Kafka login assertions SUCCESS; first-run login failure not reproduced. Shared SCRAM metadata and ACL inventory completed before Vault instance publication. No existing credentials reset. Terminal acceptance remains pending.

Final actual React/Wails confirm run `installer-f217c7d0abb725c01d4f32bc31e930ef` **SUCCEEDED**, completed2026-10-21T11:15:26Z /14:15:26MSK. Fresh Build/Approve/Start used plan0c460d1f/revisionbe3c233e/runtime53 identified above. Exactly Library Apply and Library Verify, skipInfrastructureVerify=true.

| Stage | Duration |
| --- | --- |
| Apply | 37m36s |
| Preparation/preflight and preceding ownership checks, until Kafka topics | 11m35s |
| Kafka topics | 4m44s |
| Other library resources | 2m24s |
| Kafka users and ACL | 6m35s |
| Vault instance publication and Compose validation | 3m20s |
| Activation/readiness of six placements | 2m38s |
| Endpoint publication/checks | 6m20s |
| Final Library Verify | 6m39s |
| Total Apply + Verify, including transition | 44m17s |

Stage boundaries use public TASK_STARTED timestamps, action boundaries use ACTION_STARTED/COMPLETED; elapsed sums are not isolated service latency. The preparation row includes ownership checks after placement preflight.

Observed archive behavior: six deferred placement checks; one shared integrity task SUCCESS37.744s for the single locked image/archive, before all provider mutations. Target-side delivery integrity remains enabled. Topic metadata/config inventories2+2, topic mutations0. SCRAM metadata1/63.439s, global ACL inventory1/84.421s, two login commands69.876s+32.917s, both login assertions SUCCESS. No password reset. Container readiness SUCCESS6 in Apply and6 in Verify; post-readiness Vault login/read probes0; provider audits in final Verify0. Both endpoint HTTP200 in Apply and Verify.

Post-run read-only observation: six containers running/healthy, restarts0/OOM0; all54 observed Kafka client configurations SASL_SSL/SCRAM-SHA-512 with TLS validation. Producer/consumer JAAS match protected runtime inputs; no Kafka password in docker inspect ENV or logs, legacy SSL flags absent, ACK subscriptions ack-alarm-sdku/ack-alarm-cspa. All41 public Kafka/Registry/neighbor configuration/PKI hashes unchanged; four excluded application defaults unchanged.

Limitation: Kafka timeout/disconnect ERROR events occurred during the run; auth/ACL/heap errors0. The successful plan and current health do not prove error-free business message delivery. First-run second-login failure remains unconfirmed and was not reproduced; no guard bypass or credential change. This repeat reused existing deployments, whereas runtime52 created topics/recreated containers: total-duration difference is not a controlled speedup measurement. Visual, other applications, cold-start/failure-path and business-message acceptance are not claimed. No infrastructure installation, PKI reissue, commit or push.

Final diagnostics: all six containers show successful consumer-group join/sync after their last observed ERROR. Timeout/disconnect events and one node2 CSPA listener IllegalStateException remain recorded; auth/ACL errors0, no business-message proof. Additional two-test repeat initially failed due missing explicit Kafka collection path in the QA command (no production failure); corrected environment repeat: one PASS, distinct-password test timeout60s, total108.905s. Earlier distinct-password isolated PASS21.413s retained; full nine-test suite is not claimed PASS. Production timeouts unchanged. qa-sync final source verification PASS.

Final cleanup: node2 QA source workspaceffb79646 removed with standard qa-sync cleanup after source verification. Final public secret scan10 files/findings0; git diff --check PASS. Runtime53 immutable bundle and local evidence retained. No commit/push.

Commit preparation: ACK rename required refreshing only the sdku/cspa library package digests in examples/sdku/import-catalog.json from canonical LF package bytes. Initial TestSDKUImportPackageBytes failed for those two entries; after refresh all28 packages PASS via current local Go test. Documentation corrected to reflect omitted Kafka preflight and deployment-wide ACL inventory. No runtime source behavior changed.
