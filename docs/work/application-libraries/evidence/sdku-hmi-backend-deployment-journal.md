# SDKU HMI backend — deployment continuation

Owner requested data-manager + hmi-backend in the existing SDKU instance on the
three established test nodes (101/102/103). Existing project:
.runtime/qa/sdku-data-manager-project, identity project-b46aa3f5f57a495f, library sdku-dm.
Before-edit portable backup: .runtime/qa/sdku-hmi-before-20261017.

Use ordinary APPLICATION_LIBRARIES_ONLY plan; no infrastructure Apply. Preserve
installed DM and existing account grants. Four managed Kafka topics, partitions
omitted (default1), RF/minISR derived from selected deployment:

| Topic | cleanup.policy |
| --- | --- |
| sdku-main | delete |
| sdku-main-compact | compact |
| alarms-main | delete |
| alarms-main-compact | compact |

HMI declares Kafka topic bindings, MAIN_TOPIC=sdku-main-compact,
ALARM_TOPIC=alarms-main-compact. Other alarm subscription variable spelling corrected
from ALARM_TOPIC_CAMPACT. All HMI settings derived from source_variables.MAIN_TOPIC use sdku-main-compact.
Owner confirmed ALARM_SERVICE_URL and GRANT_ACCESS_AUDIT_URL stay empty.

HMI ClickHouse connection uses qa-clickhouse via analytics, selected managed DB
sdku_dm, dedicated managed user sdku_hmi with SELECT/INSERT ON sdku_dm.*. Password
is generated only in established runtime secret inputs. SDKU base tables records
and alarm_message are included by library defaults in that DB. Kafka binding reuses
qa-kafka-structure / SSL. Existing Redis/Sentinel and Vault bindings remain.

DATA_MANAGER_URL_ROOT is an ordinary Ansible parameter template using the same
library instance and selected DM endpoint group/domain; no Go/UI endpoint resolver.
HMI uses its own port10101 and endpoint in the existing qa-shared-endpoint group:
hmi-backend-sdku-dm.evoscada.internal. Readiness/probe /actuator/health, native HTTP;
published HTTPS handled by existing endpoint provider. Vault Agent retained.

Source image unchanged:
evoscada-docker.artifacts.tn.tngrp.ru/hmi-backend:1.2.11-45c5e804-redos,
imageId sha256:0cee526e3146085af904efba8b31b9db54326d0e1760ab1e908b70eef60353cc,
linux/amd64, image size1137559607. Read-only inspect on .107 PASS. Offline export
in progress; source load average approximately60, no source containers modified.
A redundant diagnostic export was terminated by exact command/PID; main export
retained. No target install/plan Start performed yet.

Current source QA workspace node2:
/var/tmp/platform-installer-qa-ddf6993f596c49f69363d2208ca465ef.
Repository master fast-forwarded to origin/master61e75659 (portable source automation).
Changes bounded to SDKU package/configuration; no new Core schema/lifecycle feature.
Next: target-free validation; verified image archive/runtime build and publication;
normal real React/Wails trust/Verify/Build/Approve/Start; per-node health/endpoints.

## Preparation completed / owner skip decision

Archive received and local SHA256 verified:
sha256:26925ffda298f5c1f5f660ab72054eeae43bbabfbb86580cca6b24685ae6e43b,
1148246528 bytes. Exact image reference and imageId retained.

Target-free current-tree Core snapshot PASS, zero findings, two applications / three
placements each. Topic projection1 partition / RF3 / minISR2 for all four resources.
HMI MAIN_TOPIC and ALARM_TOPIC match requested compact resources; DM root URL resolves
to https://data-manager-sdku-dm.evoscada.internal; two optional URLs remain empty.

Ansible parameter bootstrap bug found: reading the entire application defaults
namespace before initializing application_parameters can erase parameter defaults
when dependent ENV is required. Added one standard set_fact seeding step using the
validated raw namespace before the original resolved precedence sequence. No new
production Python script or precedence implementation. Native regression PASS.
Broader native22 run completed with3 failures in2 old secret-name negative tests;
the same2 methods reproduce the identical3 failures with the baseline unmodified
role. Existing nonsecret_values policy accepts arbitrary operator names/values;
no policy change was made in this task. Other tests include default/reset, table
parser, topics and placement/isolation. Logs retained locally, synthetic canaries
only. Focused Go SDKU/package tests PASS before and after JDBC correction.

Standard builder on node2 produced sdku-dm-hmi-20261017-13. Standard full validation
and publication PASS:
artifact sha256:4ba96d36f0b919fb6e311d069377dbfb261bc8205ffc76452931a11ca93b2f06;
catalog sha256:6b87cd3eb49b1229ebfd21dd1e24c71e100d7dc5b38f790046762a52f773c28a.
Local .runtime/qa/sdku-dm-hmi-bundle13 retained. Identical existing payload bytes
reused locally, new source/manifest copied from the standard builder, full validator
confirmed exact candidate. Corrected Ansible role hash matches validated payload:
ead6f47d953deec157813a4922e4ccd8b36455f6ee6f5b878e563888fa644e3b.
Standard qa-runtime-promote prepared node3 and updated project manifest locks;
native artifact lock aligned afterward. No infrastructure Apply.

Owner explicitly requested skip_verify. Actual UI driver now selects
APPLICATION_LIBRARIES_ONLY + skipInfrastructureVerify=true before the first Build;
guard permits only APPLICATION_LIBRARIES_APPLY/VERIFY and refuses SERVICE actions.
Project Verify, provider preflight, readiness and endpoint verification remain.

Pre-Start inspection of source hmi-backend-01 showed a JDBC ClickHouse URL, while
package template incorrectly emitted HTTPS. Own automation stopped before Start;
no run was started in that attempt. HMI template corrected to jdbc:clickhouse://
with selected database sdku_dm and original TLS flags; project package updated.
A fresh actual React/Wails flow is running. No image/Core bundle change required
for this project-owned template correction. DM package refreshed to current shared
connection/base-compose layout, retaining local Sentinel account connection and
multi-host PostgreSQL primary selection.

## Space and temporary-work cleanup

Node2 old owned a15/bf8 source/bundle03 workspaces removed with qa-sync cleanup;
current ddf source/build/input workspace removed with the same helper after verified
local runtime/evidence preservation. Root-owned directories reassigned only for
cleanup; public payload hardlinked files were not modified. Node2 free6GiB.
Node3 inactive runtime03/04 releases and stale DM bundle01 bootstrap stage removed
after exact canonical-path/non-symlink/current-runtime/no-active-run checks.
Local runtime03/04 standard revalidation PASS before removal; active release and
runtime07 rollback retained. Node1 inactive 53b140da release removed after its local
retained bundle revalidated; active runtime12 preserved. Node1 free2.7GiB before HMI.
No service/container data or active runtime directory removed.

Source107 cleanup: two owned export archives removed; source containers unchanged.
Automatic tool approval rejected deletion of the temporary local source-password
and askpass files (blocked by policy, no more specific reason supplied). Files
remain only under .runtime/secrets, ignored/unpublished; no further deletion attempted.

## Runtime14 and explicit infrastructure skip

Owner requested skip_verify. Real React checkbox sets skipInfrastructureVerify=true;
plan guard permits exactly APPLICATION_LIBRARIES_APPLY/VERIFY, no infrastructure
Apply/Verify. Application resources/readiness/endpoint checks remain enabled.

First real run installer-c37ac2f5313253eb5224a49b7d427f58 failed before target
resources/container mutation: standalone runtime preparation still rejected
kafka.topic (APPLICATION_RUNTIME_DEFERRED_FEATURE). Added that implemented kind
to the existing supported-kind set; no new Python script. Existing runtime
contract suite17 PASS; baseline with new test reproduces exact deferred error.
Actual-project read-only Ansible authority preparation also found missing HMI
account databaseRef; corrected to analytics. Final authority run58 tasks,
changed0, failed0, including Vault/provider/runtime preparation.

Standard runtime14 builder, local validator/publisher and node3 preparation PASS.
Artifact sha256:1a89fecbcd2a940067814215de2593714dee1b1e846af4c3a9ea4ae9acafb58b;
catalog sha256:6b87cd3eb49b1229ebfd21dd1e24c71e100d7dc5b38f790046762a52f773c28a.
Native inventory lock aligned with promoted manifest. Retained validated local
candidate; removed only remote bundle14 build output to recover node2 disk space,
preserving current source/runtime input. Go focused SDKU/library/package tests PASS.

HMI ClickHouse URL uses jdbc:clickhouse, selected database and materialized CA path.
MAIN_TOPIC directly defaults to sdku-main-compact, including derived HMI settings;
ALARM_TOPIC resolves alarms-main-compact. No redundant compact parameter.

Retry driver uses its own reusable runtime-only output encryption password file.
The copied initial driver had overwritten the old DM QA output-password file;
runtime application credentials were unaffected. Project runtime contains no
published secret-output packages; earlier encrypted-output recovery is not proven.
Preserve this limitation rather than claim all historical output keys retained.

Actual React/Wails retry Project Verify VERIFIED; node READY, all three host keys
independently matched and confirmed. Approved plan plan-91e804c98be2e1083dee0636,
saved revision sha256:afe7fbcd907ffa91f7d6a09716c2856752c68245e2a971be66431ccc8b3ca0d6,
skipInfrastructureVerify=true, exactly APPLICATION_LIBRARIES_APPLY and
APPLICATION_LIBRARIES_VERIFY. Run installer-53630238c0f2e2dca5b7f9918f6889f5
started; standard execution-watch retains public task events separately in
runtime-only QA evidence. Terminal FAILED before container start. Kafka topics
created/read back; ClickHouse resource batch created the database and both
tables, then failed metadata verification. Public diagnostic omitted the closed
provider code; bounded read-only Ansible preflight reproduced
CLICKHOUSE_APPLICATION_TABLE_EXPRESSION_DRIFT, sdku_dm.records.

Read-only native metadata showed declared columns/codecs/keys match. Native
formatQuerySingleLine preserves scalar parentheses (SELECT parameterId differs
from SELECT (parameterId)); verifier added them unconditionally to observed keys.
One-line existing comparison correction wraps only when desired expression starts
with parentheses. No DDL/schema change, no new script or weakened metadata check.
Focused unit regression PASS; same real ClickHouse preflight64 tasks changed0
failed0 with correction. Initial broad provider test invocation lacked configured
Ansible collection environment: two isolated native cases failed at preflight;
configured-suite repeat6/6 PASS172.590s, including isolated standalone and three
native TLS servers/cluster, account/grant/repeat/Verify. Those tests create only
isolated temporary servers, not application deployment targets.

Standard runtime15 built and locally validated, artifact
sha256:bf0fdd4a0d3bbb538efb4b9553bef061b24b1046364b8c81d7059e889e145a23.
Publication/preparation PASS on103. Local validated13 retained before removing only
inactive node3 release13; current14 preserved. Remote build15 output removed after
local validation to preserve node2 capacity for Docker delivery.

Native lock aligned with runtime15 manifest, owned Wails restarted, and fresh
real React/Wails Project Verify/Build/Approve/Start retry initiated with the same
explicit infrastructure skip. Prior failed run evidence retained separately.

Retry plan plan-f4fdc5610d1026f7f91801d1; saved revision
sha256:60805a02000b69594e361af562e4d190737e209586a43af20e2cbffa887641ed;
skipInfrastructureVerify=true, exactly library Apply/Verify. Started run
installer-2ba49008905a7da2d159a2625467705d. Library resources/account stages PASS;
DM node1 reconciled healthy, direct HTTP health200. HMI node1 image loaded and
started, but Spring/JDBC failed with java.io.IOException: Magic is not correct -
expect [-126] but got [65]. No raw log emitted; diagnostic extracted only root
cause after runtime credential/URL/high-entropy redaction.

ClickHouse JDBC legacy HTTP-compression compatibility issue and client compress=0
workaround documented by upstream maintainer:
https://github.com/ClickHouse/clickhouse-java/issues/2636 . Added compress=0 to HMI
JDBC URL only; TLS strict verification, image reference and server unchanged.
Readiness-waiting execution cancelled through real Wails CancelInstallationRun;
terminal CANCELLED confirmed before retry. Supplemental new-page React Cancel
attempt timed out; no React-cancel acceptance claim. Existing real React start
driver stopped only after terminal confirmation, previous evidence retained.
New package-owned-template retry underway; runtime15 unchanged.

Fresh real React/Wails Verify VERIFIED, plan plan-b110045de1e641add3491246
approved for saved revision
sha256:bd10d0da35913e269546e6322a968cc7e8d96efc1381a385cb3e36280e83f5bb.
Skip=true, exactly library Apply/Verify. Started run
installer-97c4b72ee21771739b6d73dea6f5be4c on runtime15; FAILED before Compose
application on APPLICATION_LIBRARY_HOST_LOCKED. Cancel of previous run terminated
Ansible cgroup before its always cleanup; empty .apply-lock directories persisted.
No concurrent execution existed: previous CANCELLED, latest FAILED, no active
execution units. Each lock uid1002, nonsymlink, empty, timestamp21:38:37/38 matching
previous run; library owner marker matched project/library/host. Removed only
those exact empty directories with rmdir as platform-docker on101/102/103.
No new lock, no production recovery bypass; automatic Cancel cleanup remains a
known defect. Owner asked why; root cause and bounded recovery explained.
Fresh standard UI retry started after terminal confirmation and cleanup.
History cross-check after owner question: same abandoned library-lock failure
already recorded in sdku-data-manager-deployment-journal.md for
installer-9267ce690549c5f456efc7d906629380. Previous manual recovery did not fix
Cancel cleanup. This known defect was missed before current retry; infrastructure
Cancel/replan evidence must not be presented as library-stage cleanup coverage.

Retry installer-22c7553d624dda46c5dd94c30d7a6f1d uses the same unchanged desired
revision/plan-b110045de1e641add3491246, freshly approved, skip=true. Current result:
node2 and node1 HMI/DM healthy, direct HMI health HTTP200. Live node2 HMI whitelist
ENV confirms MAIN_TOPIC=sdku-main-compact, ALARM_TOPIC=alarms-main-compact,
DATAMANAGER_ROOT_URL=https://data-manager-sdku-dm.evoscada.internal; docker-init,
Vault Agent and Java observed without command arguments. Node3 and endpoint/final
Verify pending. No full application workload/visual UI acceptance claim.

Owner explicitly deferred lock cleanup implementation until successful HMI test;
no lock source change now. Conditional thread reminder lock-cancel created for
10:00 daily: stays quiet until HMI success, reminds once only if work not started,
then pauses. This is a reminder, not authorization for automated implementation.

Owner asked why DM node2 restarted despite unchanged instance parameters. Compared
preparation backup to current project: this deployment also refreshed library/DM
templates to earlier approved shared-connection corrections and new ~/sdku-dm
root. Live unchanged node3 mounts used old .local/share/platform-installer path;
updated node1 mounts use /home/platform-docker/sdku-dm. Base ENV and config-digest
also changed. Those effective Compose changes triggered recreation; adding HMI
alone did not require it. This impact should have been explained before Start.

Run installer-22c7553d624dda46c5dd94c30d7a6f1d installed all6 healthy containers
and direct HMI health200 on all3, then FAILED in endpoint preparation. Safe
public diagnostic: DM192.168.56.101:10041 expected200 actual-1 timeout10s TIMEOUT
from all3 provider hosts. No TLS expectation on HTTP backend. Publication did
not proceed past failed readiness. Ordinary apply-lock cleanup already completed.

Read-only investigation: direct curl from each host, including same Host header
and Ansible User-Agent, returned200 in0.04–0.15s. Standard Ansible URI task
reproduction also timed out once for DM102; fixed-target default/direct URI modes
then all200, root user and no proxy environment keys. Repeated complete production
HTTP task sequence24 requests (six backends from three providers plus controller)
all200, changed0 failed0. Persistent network/TLS/proxy error not established;
underlying cause of intermittent delays remains unproven, not silently reclassified.

For repeat publication changed only both desired endpoint probe timeouts10→30 in
instance group_vars; still require HTTP200, no skipped check or runtime code change.
Recorded each current container ID/start time before retry to prove whether this
endpoint-only setting causes any recreation. Fresh real UI skip=true plan underway.
Focused Go SDKU/library/package tests after final template change PASS5.903s.

Owner requested the exact installed Ansible task with the failed request variables.
Executed unchanged runtime15 check_http_target.yml from Execution Node103 using
its Core ansible.cfg/pipelining, become root on node1/2/3. Exact consumed variables:
HTTP192.168.56.101:10041/actuator/health, Host=data-manager-sdku-dm.evoscada.internal,
expected_status200, timeout10. Every provider returned status200, elapsed0,
msg="OK (unknown bytes)"; changed0 failed0. Follow-up debug selected only url,
status, elapsed and msg; raw response/body/cookies remain suppressed.
Evidence: .runtime/sdku-http-exact.log; QA play .runtime/qa/sdku-http-exact.yml.

Read-only diagnostic probes with no_log=false and suppressed raw successful module
results: first90 requests all200/elapsed0, subsequent270 all200. Two responses to
DM103 from node1/node2 took5/6 seconds at20:17:44/45Z; no request exceeded10s.
Public projections/TCP control and socket counters: .runtime/qa/http-debug103/.
Separate packet-header-only observation recorded72 request/response pairs with
maximum first response403ms in its bounded window; this window ended before the
5/6-second responses, so it cannot explain those delays. No payload was captured.
DM logs19:35–19:43Z yielded76/66/66 lines without WARN/ERROR or exception classes.
Severe earlier node1 memory/CPU pressure is an observation, not a proven cause.
Original failed request's detailed msg was suppressed and cannot be reconstructed.
Underlying timeout cause remains unproven; no repeated installation was started.
Reverted both provisional endpoint probe timeouts30 back to10 in desired group_vars.
Fresh UI preparation was stopped before Build/Start; final publication still pending.

Owner decision: remove the HTTP backend pre-publication check completely after
repeated unexplained timeouts. Deleted check_http_target.yml and its include from
check_targets.yml. Removed the obsolete HTTP diagnostic integration test; existing
candidate preparation regression now asserts success against a503 HTTP fixture
and zero received requests. HTTPS identity/response checks remain existing behavior.
This is a source change; active immutable runtime15 has not been modified.

Focused current-tree RED OS QA: HTTPS positive/negative test1 PASS20.023s;
candidate/partial runtime tests2 PASS24.760s under sudo-n (fixtures require root
ownership). Initial unprivileged run failed only on fixture chown permissions.
No application deployment, endpoint publication or active-runtime changes performed.

2026-10-18 owner authorized runtime update and same-project skip=true continuation,
and then explicitly requested removal of the container/library lock from code.
Removed all .apply-lock acquisition/assert/held-list/always-release from library
Apply; kept shared-projection/ownership and all-selected Compose validation before
activation. No replacement lock or Go/UI lifecycle changes. Updated A2/ADR-045.
Independent FULL DIFF APPROVE_WITH_CHANGES, zero blockers; LOCK-R01 documentation
finding resolved. Review: ../reviews/library-lock-removal-diff-review.md.
Current-tree RED OS syntax-check PASS; runtime contract17 PASS3.387s.

Runtime16 (HTTP pre-publication check removed) built on trusted102, validated,
standard-published and prepared103, digestbf2d4f5dfeefb74b5848829a7202d8e23a49a850f35a7f5643a7a60282452b6e.
Runtime17 additionally removes library lock, digestba4b171648837417b0932b94e55701f0034e15413a02a720abb1f80aaa0b155e;
standard validation/publication PASS, promotion17 underway before app Start.
Catalog remains6b87cd3eb49b1229ebfd21dd1e24c71e100d7dc5b38f790046762a52f773c28a.
Unchanged payload bytes reused from verified local bundles; changed files and
manifest came from authoritative102 build. Full resulting bundle validated.
Inactive remote14/15 removed only after current-release/active-run checks and
retained local verified copies; fresh102 build workspaces cleaned via qa-sync.
Automatic approval rejected removal of incomplete local bundle16 transfer;
kept it and assembled fresh complete candidate without deletion.
Saved current per-host application container IDs in .runtime/qa/sdku-hmi16-before-*.txt.
Runtime17 standard promotion PASS, active103 ba4b1716. First actual UI Project
Verify failed before Start: APPLICATION_ARTIFACT_LOCK_CONFLICT, surfaced as generic
PROJECT_SNAPSHOT_INPUT_INVALID. Exact cause: promotion updated project.yml to17,
native platform_artifact_lock.digest remained15; operator synchronization omitted.
Readonly Ansible replay and exception-type/line-only tracing identified resolve_image_lock.
Updated only native digest to the verified17; actual React/Wails Project Verify PASS.
No Core/Python production diagnostic change or extra runtime needed.

Actual run installer-4636b6778f27b6f147bd7357e88ac07e,
plan-ea327e09f66ef8efd6057e98, revision245afdac81e059bc1a17b6f7d9dd6b64b76303a8357c78b26409f85ec20b864e,
skipInfrastructureVerify=true, exactly APPLICATION_LIBRARIES_APPLY/VERIFY.
Preflight/resources/Vault/Compose validation passed; FAILED at Compose up on101,
seq1318,10:38 MSK. No endpoint activation. Diagnostic found all3 RootlessKit
lxc-user-nic DHCP renewal panics about10:34 MSK:101 .174->.175,102 .60->.61,
103 .230->.231. docker.service Restart=on-failure, RestartUSec=5s; systemd restarted
it after main process exit2 (counter5). Daemon lost task state; five selected apps
were exited128 with OCI runc "container with given ID already exists". HMI102 healthy.
No OOM on101 in that window; Linger=yes. This confirms this Compose failure, not
the root cause of older HTTP timeouts. DHCP allocation cause remains unproven.
Authoritative upstream code confirms panic on changed renewed IP:
https://github.com/rootless-containers/rootlesskit/blob/v2.0.2/pkg/network/lxcusernic/lxcusernic.go
Earlier no-restart assertion based on preserved IDs was incorrect:101 StartedAt
showed09:53/09:54 process starts despite same IDs. Reported correction to owner.

Recovery checked exact project/library/instance labels, status exited and exact
runc error, then removed only five stopped selected container records via Docker
without force or volumes. Running HMI102 retained. No Docker/network/lease setting
changed; application restart uses a fresh approved plan, not direct compose bypass.
Fresh real React/Wails skip=true run installer-86fa21b90a35d6f9a84460e139e6f94f started.
Evidence: .runtime/qa/sdku-hmi-watch18/, sdku-hmi-rootlesskit-panic-run.json,
.runtime/sdku-hmi-driver-runtime17-recovery.log and .runtime/qa/sdku-hmi-watch19/.
Final acceptance — 2026-10-18

Actual React/Wails run installer-86fa21b90a35d6f9a84460e139e6f94f SUCCEEDED
at08:34:45Z /11:34:45MSK. Approved plan plan-ea327e09f66ef8efd6057e98,
saved revision sha256:245afdac81e059bc1a17b6f7d9dd6b64b76303a8357c78b26409f85ec20b864e.
Runtime17 sha256:ba4b171648837417b0932b94e55701f0034e15413a02a720abb1f80aaa0b155e.
skipInfrastructureVerify=true; actual actions ONLY APPLICATION_LIBRARIES_APPLY and
APPLICATION_LIBRARIES_VERIFY. Apply SUCCESS then Verify SUCCESSseq2989, controller
completedseq2990. No Infra Verify or infrastructure service Apply executed.
Public mirror .runtime/qa/sdku-hmi-watch19/executions/<run>/events.jsonl;
real driver .runtime/qa/application-design/sdku-hmi-backend-run.json.

Independent final readonly checks .runtime/qa/sdku-final-{101,102,103}.log:
all6 Running/healthy, direct host HTTP200 and trusted HTTPS200 for both names on
each host. DNS for both resolves192.168.56.111. Curl output body discarded, TLS
validated using existing application CA (no -k). Vault Agent/java confirmed by
PID/comm only. Original DM image fa4f2f14 and HMI0cee526e exact references retained.
All3 HMI ENV: MAIN_TOPIC=sdku-main-compact; ALARM_TOPIC=alarms-main-compact;
DATAMANAGER_ROOT_URL=https://data-manager-sdku-dm.evoscada.internal.
Kafka topics/config/RF/minISR, ClickHouse library tables and application grants,
PostgreSQL/Redis/Sentinel and Vault scopes passed standard library Verify.

Final containers (short IDs; full IDs/times in readonly evidence):
101 DM2eb535a28153, HMI2e940dd66393;
102 DM1159a9a61d97, HMI5bbb5fe014c6 (retained existing container);
103 DMd98fec3873e0, HMIc818369fc711.
Five old stopped objects were recreated after confirmed RootlessKit failure;
this was recovery, not a desired application parameter or image-reference change.
Library .apply-lock absent all3. Source HTTP pre-publication task removed.
All3 Docker NRestarts=5, ExecMainStart10:34:08–12MSK, unchanged at final check.
RootlessKit DHCP address-change cause remains unproven and was not repaired;
current successful deployment does not claim long-duration network stability.
Public endpoint: https://hmi-backend-sdku-dm.evoscada.internal/actuator/health.
DM endpoint retained: https://data-manager-sdku-dm.evoscada.internal/actuator/health.
No business-workload or visual UI PASS claim.

Fresh unstarted post-run plan EXECUTABLE with skip=true and only library actions.
Prior infrastructure proof remains INFRA_VERIFY_STALE after runtime upgrade;
no claim of current infrastructure PASS and no infrastructure recheck performed.
Reminder lock-cancel PAUSED after owner-requested lock removal implemented.
Temporary103 snapshot diagnostic project/scripts cleaned, old102 copied QA SSH/CH
credential files removed. Existing approved runtime inputs/backups retained.
Policy-rejected removal of incomplete local bundle16 staging was not retried;
that ignored runtime-only partial directory remains outside active cache.
### HMI Kafka topic diagnosis, 2026-10-18

Owner authorized manual HMI manifest testing. On node1 only, temporary
logging.level.org.apache.kafka.clients.admin=DEBUG exposed the actual request:
08:47:01Z TopicRequest(name='sdku-main-compact-compact'), immediately followed
by KafkaUtil Get partitions error / UnknownTopicOrPartitionException.
The image kafka-manager-1.7.17.jar TopicsManager contains the `%s-compact`
name decoration, used by KafkaManagerListenerContainer.

Manual node1 manifest correction: CSPA_TOPICS, CSPA_TOPIC_ROUTE_ROOT,
EVO_MANAGER_HOT_TOPICS and tn-scada.cspa.topic-route.*.topic use sdku-main.
MAIN_TOPIC=sdku-main-compact and ALARM_TOPIC=alarms-main-compact stay intact.
At08:49:19-22Z AdminClient successfully requested partitions and offsets for
sdku-main and sdku-main-compact, partition0; repeated KafkaUtil errors stopped.
No extra topic was created. DM and Kafka configuration were not changed.
Debug setting subsequently removed and only node1 HMI recreated again.
Node2/node3 manifests and portable project/package defaults have not been
changed in this diagnostic task; the proven correction must be carried into
the desired package/project before a normal deployment overwrites node1.
A separate SSL PKIX trust-chain error appeared during warm-up; this diagnosis
does not claim full business readiness or that this TLS error is resolved.

### Shared Java TLS defaults and topic correction, 2026-10-18

PKIX root cause confirmed in Schema Registry HTTPS registration from
KafkaProtobufSerializer -> CachedSchemaRegistryClient -> RestService.
The broker SSL truststore did not configure the separate Confluent HTTPS client.
Registry targets are https://192.168.56.101:8082, .102:8082, .103:8082.
Set kafka.{producer,consumer}.schema.registry.ssl.truststore.type=PEM and
.location=/opt/application/pki/ca-chain.pem. Certificate verification remains on;
no passwords in Compose and no JVM trust-all workaround.
Manual HMI testing on101/102/103: all healthy, producer warm-up and service start
confirmed, zero PKIX and zero Get partitions error in recreated container logs.

Canonical SDKU package and project package copy now distinguish MAIN_TOPIC_BASE
(sdku-main, CSPA/routes/hot subscriptions) from MAIN_TOPIC(sdku-main-compact).
ALARM_TOPIC remains alarms-main-compact. Library defaults own shared Kafka store
paths/types, Redis store paths and Schema Registry PEM settings. HMI no longer
owns the four Registry TLS properties. ClickHouse CA path is a library default
CLICKHOUSE_SSL_ROOT_CERT consumed by its JDBC template. Project library overrides
own repeated TLS-enable/protocol settings formerly duplicated in DM/HMI overrides.
All apply through existing backend base-compose rendering; frontend stays on base.
Package digest/import test PASS; exact project package bytes synchronized.

Real React/Wails Project Verify VERIFIED. Standard application-only skip=true
run installer-f372052a54982e394aa3d4d19d4e73cc started on runtime17 to materialize
shared settings. A separate owner request removes the project-ID prefix from
containerName only; Compose project and ownership labels retain their identities.
Existing Core naming projection changed to app_id-host, with focused assertion.
Fresh RED OS source QA: 22 tests, three assertions fail in two pre-existing
secret-marker projection tests. An isolated copy restoring only the old naming
line reproduces the exact same three failures in those two tests (14.095s).
Naming, library defaults inheritance/reset and remaining QA tests pass; do not
claim the full suite PASS. No new secret restrictions were introduced.
Runtime18 full bundle validation PASS, digest
sha256:949df91f63f919b9d47317f49b45fd8659d819197bb48347b0121628fee2251a.
Publication/preparation and name-change execution pending current run completion.

### Correction during shared-defaults Apply and runtime18 preparation

Run installer-f372052a54982e394aa3d4d19d4e73cc was CANCELLED through the normal
Wails CancelInstallationRun method after DM node1 exposed WRONGPASS against
6379/6380/6381. The deployment's library Redis declaration had purpose=sentinel;
copying generic source defaults into the project had overwritten it with client.
This was an implementation regression, not a password/ACL change. Preserved
project library settings were recovered from the existing staged project and
only the seven shared TLS defaults merged. Redis purpose remains sentinel;
source generic library remains client for its standalone default. HMI package
contains the proven topic correction; project-local custom library settings
are deliberately preserved instead of asserting whole-library byte equality.
After cancellation the real bridge produced a fresh EXECUTABLE skip=true plan;
no lock was manually removed. The separate browser Cancel button attempt could
not navigate because its editor was not initialized; cancellation evidence is
normal Wails method, not a React cancel-handler acceptance claim.

First runtime18 preparation failed at StageVerifiedBundle while disk was tight.
Verified local runtime16 backup was revalidated with the standard CLI, digest
bf2d4f5dfeefb74b5848829a7202d8e23a49a850f35a7f5643a7a60282452b6e.
Only its inactive server release was removed after exact resolved-path,
current-runtime17 and manifest-hash checks. Other releases and runtime17 retained.
Free space rose to7.5G; standard resumed preparation then succeeded, current18,
4.1G free after staging cleanup. No application image/tag or infrastructure
installation changed during preparation. Native and compatibility artifact locks
aligned to18. New real React/Wails skip=true application-only plan in progress.

### SQL connections and Java application defaults, owner clarification

Added postgres(database/tcp) and clickhouse(analytics/https) to the library's
connections in source and project; project Redis purpose=sentinel preserved.
Base-compose emits POSTGRES_ADDRESS(all projected database members) and
CLICKHOUSE_ADDRESS(first HTTP target, retaining existing ClickHouse selection).
Library defaults own JDBC/HTTP endpoint prefixes, PostgreSQL SSL options,
ClickHouse SSL options/CA path and common legacy Kafka/Redis store-path aliases.
Project library TLS overrides also enable the legacy Kafka/Redis aliases.

Updated main.yml and Compose templates for17 Java application packages.
App defaults select the shared connection and database name; Compose templates
no longer build SQL endpoints or hardcode JDBC SSL paths/options. Existing
application connection declarations identify usage and credential/resource scope.
Legacy CLICKHOUSE_SSL_URL inputs and hardcoded8443 suffixes removed. Source image
references/tags unchanged. Project package updates preserve its custom library
settings and DM's separate Sentinel account/connection definitions.
Spring ENV references use Compose escaping ($$), verified against real Docker
Compose config output and the existing Core equality check; no new Core escape
normalizer or parser was added. Root CA/password validation was not disabled.

Go SDKU package import/digest test PASS. Focused standard Ansible QA on fresh
RED OS sources: all17 Java Compose documents rendered/parsed, common base rendered,
shared PostgreSQL/ClickHouse address assertions and Registry PEM assertion PASS
(ok8, failed0). Synthetic fixture initially lacked port-2/library_instance_id;
fixture completed and checks rerun. No containers started by this render QA.
The final actual application-only skip=true plan is being prepared on runtime18.

### Final actual acceptance, 2026-10-18 13:39:01 MSK

Run installer-a712f791ce9bc3db6221d27b0b5914dd SUCCEEDED on runtime18.
Fresh plan plan-68aaee40e34be8fbf07d7ad8, saved revision
sha256:98206271262e710dbc14f59d1f1740932701df607a0f442555fd8bc06cb16e75.
Actual React/Wails Build/Approve/Start; skipInfrastructureVerify=true, exactly
APPLICATION_LIBRARIES_APPLY and APPLICATION_LIBRARIES_VERIFY. Apply SUCCESS
seq2269 at10:33:53Z, Verify SUCCESS seq2981 and controller terminal seq2982
at10:39:01Z. No infrastructure Apply or Infra Verify. Fresh post-run unstarted
skip=true plan EXECUTABLE; prior infrastructure evidence remains stale/BLOCKED,
not a claim of infrastructure PASS. Public mirror: .runtime/qa/sdku-sql-watch18-final.

Preceding run installer-a0748cfe94aa82cbbb28cd0da680612f failed before activation:
Require new published ports to be free before file writes. New Core names did
not yet identify the old-name containers occupying their own ports. All six
exact old names were checked against project/library/instance/host labels and
renamed once with docker rename, without stopping their processes. No migration
subsystem, new lock, weakened port check or extra Core helper was introduced.
Fresh normal plan then passed port ownership/preflight and Compose validation
for every selected placement before activation. Compose project/ownership labels
retain project identity; only containerName omits the project-ID prefix.

Observed after Apply, with Verify subsequently PASS:
-101: data-manager-sdku-dm-node1 and hmi-backend-sdku-dm-node1 healthy.
-102: data-manager-sdku-dm-node2 and hmi-backend-sdku-dm-node2 healthy.
-103: data-manager-sdku-dm-node3 and hmi-backend-sdku-dm-node3 healthy.
All six original image references and original image IDs verified unchanged.
Twelve checks returned200: directHTTP10041/10101 and trusted publicHTTPS for
both apps from each server. Curl discarded bodies and verified CA; no -k.
HMI logs for all new containers: producer warm-up and HmiEvoService start,
zero PKIX path-building failures and zero KafkaUtil Get partitions error.
Vault Agent/java processes confirmed without command arguments or environment dumps.

Base-compose contains shared paths/types/SSL settings and SQL connection inputs.
Observed PostgreSQL addresses102:5432,103:5432 (database members;101 is monitor),
ClickHouse101:8443 (original single HTTP target choice), Sentinel26379/26380/26381,
Registry HTTPS URLs on all three nodes. Individual Compose documents contain
zero duplicated shared Kafka/Registry SSL keys. Actual Docker DB_CONNECTION_STRING
contains Spring references to POSTGRES_JDBC_ENDPOINT/POSTGRES_SSL_OPTIONS or
CLICKHOUSE_JDBC_ENDPOINT/CLICKHOUSE_SSL_OPTIONS, plus its own sdku_dm database;
HMI retains client-specific compress=0. Successful startup proves the nested
Spring references work after Docker Compose dollar escaping.

Source/project audit:16/17 main.yml files byte-equivalent ignoring line endings,
all17 Compose templates equivalent. DM custom defaults retain its separate
Sentinel connection/account definitions; shared connection settings updated.
SDKU .j2 files now use explicit LF through .gitattributes so raw-byte import
hashes remain stable across checkouts. Standard package import/digest test PASS;
final diff whitespace check PASS. Standard Ansible render QA:17 Java templates
plus shared base, SQL address/TLS assertions PASS (ok8 failed0). Existing Core
suite's three marker assertions in two tests remain failing on both old and new
naming baselines; no full Core-suite PASS claim. No visual or business-load PASS.
Independent read-only evidence: .runtime/qa/sdku-final18-node1.log through node3.log;
original-image/HTTP proof script reports6/6 images and12/12 HTTP200 checks.
RootlessKit DHCP address-change cause remains outside this task and unrepaired.
