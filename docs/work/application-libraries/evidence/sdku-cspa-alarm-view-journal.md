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
