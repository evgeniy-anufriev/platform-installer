# A9 — журнал приёмки

2026-10-13. Владелец принял технический план командой «Выполни комит и приступай
к А9». Исходная версия: codex/application-libraries, commit1db6604.
А9 COMPLETE в owner-amended standalone Core/Ansible scope: Apply/Verify, live status, repeat, failure/retry, cleanup и secret hygiene PASS. Mixed14 остаётся FAILED; отдельная инфраструктурная acceptance принята владельцем. Go/UI вне scope.

## Подготовка

Current sources transferred стандартным qa-sync:

- node1: /var/tmp/platform-installer-qa-189d7aef53f048739ab03761fc5715f2;
- node2: /var/tmp/platform-installer-qa-1ea44f042fa94620be034b9d6f7d34e4.

QA-копия содержит только inventory исходного full-services, без копирования
secrets/runtime/bundle. Базовый проект не изменён. Safe metadata audit подтвердил
10 infrastructure deployments, отсутствие library deployments, endpoint domain
evoscada.internal и qa-tls-profile. Это metadata, ещё не полный Core snapshot.

## Focused tests

- Application Core suites: **100 PASS**, 13.219s.
- Vault application provider: **14 PASS**.
- Redis application ACL: **2 PASS**.
- ClickHouse application provider: начальный запуск не нашёл collection из-за
  отсутствующего ANSIBLE_COLLECTIONS_PATH. После исправления окружения:
  **3 PASS**, 52.109s. Production/test sources не изменялись.

## Rootless Docker prerequisite

UID platform-docker на обоих hosts=1002, получен через getent.
Node1 Docker API29.7.2 доступен; probe image ID совпал с планом:
sha256:caa73a170e7bc73ffc6a44a37360163ceb3939f6a986abba3c867094256c0f0d.
На обоих lxcbr0 фактический IPv4=10.0.3.1/24.

Node2 первоначально: docker.service running, socket отсутствует; rootlesskit
PID1142, дочерний процесс defunct. Владелец отдельно разрешил штатный restart
существующего пользовательского docker.service без изменения данных/настроек.
Restart сначала не завершил остановку: stop timeout/watchdog. Затем systemd
завершил остановку и запустил новый MainPID104545, Result=success, socket появился.
Повторный Docker API запрос подтвердил29.7.2. Удаление images/volumes не выполнялось.

## Bundle

Approved A8 final11 archive перенесён на node2 только как источник existing
runtime payload. Новый bundle application-a9-20261013-01 собран standard builder
из текущего commit1db6604. Интернет acquisition не выполнялся.
Стандартная валидация, digest и source equality записываются после завершения.
Публикация/активация и live Apply пока NOT RUN.

## Existing Kafka SSL и текущий snapshot

Владелец исключил добавление CLIENT_SSL и требует существующий SSL listener.
Application connection declaration остаётся purpose:client, library serviceType
default connectionRef=SSL. Core resolver принимает явно выбранный broker
interBroker listener, не принимает controller и не выбирает fallback.
Независимый FULL APPROVE_WITH_CHANGES, zero blockers; документационный D01 исправлен.
После production predicate correction: current-source RED OS **100 PASS**,11.346s.

QA generator qa_a9_fixture.py создаёт только копию desired state, не мутирует
providers/Docker/endpoints. Два library packages используют один application package;
SDKU=node1/node2, CSPA=node1. Base Compose получает connections через Core projection,
пользовательский .env библиотечный; image authority зафиксирована existing probe archive.
Поправлены fixture prerequisites: explicit v3alpha1, явный localhost inventory,
совпадение artifactLock в compatibility project.yml и group_vars.
Core snapshot: **PASS**, findings=[], validation/applicationLibraries PASS,
changed0. Recorded intermediate revision
sha256:bcba9f34f6dcf8965a6f6c8908a5efe4bb2d6eb2d32ea32050b6a18d6b050e34;
последующие fixture changes требуют нового frozen revision.
Source workspace4529246306e448018efdb6d8db14191f используется для current Core.

Bundle02 включает Kafka correction, собран на node2 из standard qa-sync source
0c449ab6074443618fa13e4e2b33be38. Standard validate-bundle **PASS**:
sha256:7dcca96faa3068b468a5ffcc91eea95a68ee35e9a6fd030eb2dabc79fc248bc1.
Bundle01 validation тоже PASS (a10c1ff95cd5742c11a7740e9cd2396a15544063c140eee0cba85e66cafa4ddb),
но он предшествует Kafka source correction; не использовать для final execution claim.

## Read-only target preflight и HAProxy TLS prerequisite

Все три placements прошли preflight: node1 ok66/node2 ok36, changed0, failed0;
node3 без application placement, skipped. Первая попытка fixture не задала
правильный platform_execution_bundle_root; исправлены только runtime inputs.
Vault discover остановился на проверке sys/mounts через
https://qa-vault-consumer.evoscada.internal:443, DNS=192.168.56.111.
Strict TLS verification failed code19 (self-signed certificate in certificate chain).
Не проверялся admin-token посредством непроверенного TLS.

Публичный CA fingerprint Vault/Kafka/Redis/ClickHouse на node1 совпал с canonical
PKI authority project-b46aa3f5f57a495f/qa-root-ca:
95def9fa2c8d53093bce0489184d471dfac3b45f34f19c5ae544818af0abf306.
HAProxy frontend предъявлял другую CA chain с тем же CN, что недостаточно для trust.
Владелец отдельно разрешил восстановление frontend certificate existing PKI,
с сохранением SAN/wildcard, backends/DNS.

Existing admin-token.age расшифрован только Go internal/secretfiles.ReadVaultInput
в protected runtime holder; ни token, ни пароли не выводились. Старый local QA
password file оказался неподходящим; применён ранее предоставленный владельцем
пароль. PKCS12 password дополнительно подтверждён keytool на всех трёх canonical
HOST requests без вывода значений; shared runtime ref не ротируется.

PKI restoration resolver PASS, selected HOST requests:
qa-tls-profile--node1/node2/node3, canonical CA сохранена.
Первая native попытка завершила explicit reissue (localhost ok270 changed46),
но pki_deploy failed до HAProxy activation: controller process platform-automation
не читал root-owned canonical sources. Повтор выполняется sudo -n controller,
с явным trusted UserKnownHostsFile и без повторного explicit reissue.
Это runtime privilege prerequisite; production PKI код не менялся.
Backend baseline:6 conf files на каждом HAProxy host, hashes сохранены до activation.
Restoration пока RUNNING; успех, reload/Verify и сохранность records не заявляются.

### Prerequisite restoration completed

Root-controller HAProxy Apply/Verify PASS: localhost ok231 changed0;
node1/node2/node3 ok87 changed5 failed0. Native existing PKI generated wildcard
SAN requests against original canonical CA; HAProxy activated validated certificate.
Backend hash comparison: **6/6 identical on each of three hosts**.
DNS playbooks не запускались при restoration; DNS changes не выполнялись.

Strict TLS health through endpoint200. Исходный exported admin-token.age оказался
устаревшим (403). По metadata обнаружен exact current project/deployment bootstrap:
package39842c415451127fac8b99b9bb6745ac, generation3,
sourceRunId installer-06905b81b980496402595748b7dfefc6, READY. Использована защищённая
копия его plaintext admin-token через штатный standalone input; canonical output
не изменён/не ACKed, значения не выводились.

Direct verified health: node1 active, node3 standby, same clusterID;
node2 sealed503. Владелец отдельно разрешил только unseal node2.
Existing vault_tls/tasks/unseal_member.yml выполнен с generation3 protected shares:
native role PASS, подтвердил тот же seed clusterID. Без reset/data/config changes
или restart. URI tasks recap changed0 не означает отсутствие изменения seal state.
После unseal: endpoint sys/mounts **3 consecutive200**, secret/ engine KV version2.

Default mismatch discovered before hooks: application ClickHouse role still used
legacy /etc/platform-clickhouse + platform-clickhouse, while current service role
derives path/user from platform_name_prefix. Application defaults aligned with same
existing naming formula; Redis user also derives existing platform_redis_name.
Manual ClickHouse workaround removed. No new mechanism/contract fields introduced.
Current-source regression: **Core100 / ClickHouse3 / Redis2 PASS** (12.071/56.972/0.359s).
Current source node1=72b50fe96cc44d30bd80dc670d09b319,
node2=84c85a4cf41143eda1d7cfe821aaf780. Bundle03 build completed; standard validation
pending. Repeated full target + Vault preflight PASS: localhost ok64,
node1 ok66/node2 ok36, all changed0 failed0.

QA fixture tightened: Redis key namespace derives logical application_instance_id,
distinct per library. Ordinary probe leaves fixture writes/table queries disabled;
permission/table tests remain separate owned QA scope. Fixture copies inventory
and compatibility metadata only, never baseline secrets/bundle/runtime.

## Remaining acceptance

Q01–15 из технического плана остаются открытыми; результаты focused tests
не заменяют три live placements/status200, два endpoints, repeat/isolation/retry,
structured mixed execution и cleanup. Temporary source/build workspaces пока
активны для продолжения QA; их удаление не заявляется заранее.

## Final bundle03 and PostgreSQL TLS prerequisite

Standard bundle03 validation PASS; digest
`sha256:8581c632fcda4ea928e1788f71309df8ac9be8db869bd256596608e698c783a0`.
Native initial Apply returned 2 after 109.811s, all hosts changed0:
PostgreSQL verified TLS preflight stopped execution before application mutations.
Installed PostgreSQL CA fingerprint DBBC2D46F6A14BBE1B11864BC04C364F9AF1D62440C0D2712C687B1892156C6D
is different from current project CA 95DEF9FA2C8D53093BCE0489184D471DFAC3B45F34F19C5AE544818AF0ABF306.
All three PostgreSQL listeners validate with installed old CA; current projected
CA produces verification code19. Owner explicitly approved restoring PostgreSQL
TLS through existing role tasks and reload/Verify. Bounded restoration running;
no database/account/configuration reset is included.

PostgreSQL bounded TLS restore completed using resolve_binary_directory,
resolve_tls, install_tls and existing Reload PostgreSQL TLS material handler.
PKI materialization changed0; each database host copied changed TLS files and
reloaded. Read-only verified network handshake against current project CA PASS
on node1/node2/node3. Initial supplementary probe timed out (124) despite valid
TLS because s_client waited for input under Ansible. Explicit s_client quit
command `Q` yields all-host PASS changed0; negative mismatched IP remains rejected
(rc1, verify64). Provider preflight now uses Q, retaining timeout, CA and verified
identity. Bundle04 being built for corrected native Apply.

Bundle04 standard validation PASS:
`sha256:8c32393aa4f9fad4d1d44035e07be2aa3cb81021e82cdd50891857af989406e6`.
First corrected invocation rejected stale fixture bundle binding before mutations
(10.994s, changed0). Explicit QA rebind verified archive size/SHA256 unchanged,
then updated matching native/compatibility artifactLock digest. Corrected full
standalone Apply is running from immutable bundle04.

## Native initial partial result and live AppRole evidence

Corrected initial04 Apply: rc2, 410.741s; localhost changed24/node1 changed20/
node2 changed11/node3 changed3. Provider/resources/AppRole/container steps ran;
HAProxy backend readiness blocked publication due to SDKU node2 PostgreSQL status.
Direct status node1 SDKU/CSPA HTTP200, all eight checks ok. SDKU node2 HTTP503:
seven checks ok, PostgreSQL failed. Existing database member address .102 is local
for node2 container; PostgreSQL sees LXC source10.0.3.127 and rejects HBA access.
Existing role generates hostssl all/all 192.168.56.0/24 SCRAM only. No LXC HBA
rule/configuration knob exists. Owner decision requested: ordinary overrideable
client CIDRs in PostgreSQL, or explicit remote-member QA with limitation retained.
No password/RoleID/token was printed. Scratch image intentionally has no shell;
bounded diagnostic used existing psql and an ephemeral private tmpfs pgpass file,
removed after read-only SELECT1 attempt. TLS passed, HBA rejected.

Live AppRole metadata: SDKU/CSPA bind_secret_id=false;
token_bound_cidrs=[10.0.3.0/24,127.0.0.1,192.168.56.0/24]. All three Agent
status checks ok. LXC CIDR correction live update/login evidence now PASS.

Structured Build staging installer-a9-1791907991202000 EXECUTABLE, zero findings.
Operations: PKI_APPLY, Apply/Verify keepalived, bind, dns-client, docker, haproxy,
postgresql, redis, clickhouse, kafka, vault; then APPLICATION_LIBRARIES_APPLY and
APPLICATION_LIBRARIES_VERIFY. First provisional order was safely rejected for
HAProxy dependency order (no Start); corrected order follows Core requirements.
Structured trust/lease/Start NOT RUN; pending native readiness and delta checks.

## Owner-approved PostgreSQL client CIDRs extension

Owner selected ordinary additional PostgreSQL client CIDRs rather than hiding
local-container path through remote QA member selection. Added role default[] and
canonical service configuration.clientCidrs (deployment/member); declared IPv4
CIDRs supplement observed network with deduplication, only hostssl+SCRAM.
No hook HBA mutation, no inferred LXC policy, no new provider framework.
RED OS source00a9: HBA4 PASS, library17 PASS, service-configuration39 PASS.
Generated catalog+20 compatibility project locks synchronized by standard RED OS
builder, digest08cd1f4c1b77104b32d11841c8eab105b14099a636a3577fdfb26b7e7009ccaa.
Independent scoped FULL DIFF requested before target application.

A3 evidence boundary reconfirmed: isolated PostgreSQL clusters and provider-host
psql login/SELECT1. A3 plan explicitly keeps full rootless container/Agent network
path for A4/A9. A9 newly exercises container-to-service on same host. Live node2
RootlessKit --net=lxc-user-nic; nftables LXC masquerade is POSTROUTING, local input
keeps10.0.3.127. Remote clients use host-network source. No Docker network change.

PostgreSQL CIDRs scoped FULL **APPROVE**, no findings; report
../reviews/a9-postgresql-client-cidrs-diff-review.md. QA desired state explicitly
sets configuration.clientCidrs=[10.0.3.0/24]. Bounded application reused actual HBA
template/task and native reload handler, with existing Core-derived PG variables.
First attempt interrupted by node2 disk exhaustion and incomplete manual QA
execution context (missing serviceDeployment gave default data path); production
role logic unaffected. Completed source workspaces node2 0c449/84c85/815 cleaned
using standard helper; shared Docker images/volumes/services preserved. Corrected
context qa-postgresql applied successfully; pending reloads on node1/node3 issued
with same existing pg_ctl command and observed deployed data directory.
All3 direct status HTTP200/all8 checks ok after HBA, without container restart.
Final bundle05 includes canonical setting/catalog changes; package transfer pending.

Bundle05 standard validation PASS:
`sha256:de75b45f7aaeecd8e7ee45c2cd434aa28ba36f66e43c247e24e992e4a39d3c0d`.
Native final05 Apply running after verified artifact/catalog rebind in QA copy.
Structured final05 Build installer-a9-1791910052951840 EXECUTABLE, zero findings;
no PKI_REISSUE, same approved ten-service scope then application phases.
Core projects clientCidrs=[10.0.3.0/24] to all3 PostgreSQL role-variable maps.
No structured Start yet.

Read-only PostgreSQL ownDB SELECT1 + foreignDB rejection PASS both directions.
Redis initial host CLI lacked required mTLS, not treated as ACL evidence;
corrected trusted client certificate probe own GET / foreign NOPERM PASS both
libraries. Vault own path200/foreign403 PASS both, temporary tokens revoked.
ClickHouse created only a9_{sdku,cspa}.qa_isolation on CLUSTER default; app own
INSERT/SELECT PASS and foreign SELECT403 PASS both directions. Tables remain
owned QA objects for final cleanup. No /status writes were enabled.

## HAProxy readiness retry correction

Native final05 rc2 after326.263s, all changed0. Ownership capture correctly
rejected incomplete retained candidate produced by earlier readiness failure.
Active graph had7 files: owned CSPA had published before SDKU failure; prior SDKU
and all shared backend/stats hashes preserved. Workaround did not bypass capture.
Scoped fix moves existing Reset/Create/Stage tasks after readiness; no new tasks.
Independent FULL APPROVE, no findings: ../reviews/a9-haproxy-readiness-diff-review.md.
RED OS runtime2 PASS (503 preserves prior candidate; 200 retry), archive11 PASS.
Host-scope fixture still referenced pre-A6 main.yml location; corrected to current
lifecycle.yml, native3 PASS. Complete current application contract100 PASS30.433s.

Derived candidate recovery verified exact allowed seven filenames, preserved
baseline hashes except owned updated frontend, matched CSPA retained/proven file,
matched active main against native activation archive, validated active graph.
Only candidate replaced; active configs/process unchanged. Failed candidate kept
under .a9-incomplete-candidate-* on all3 hosts for owned cleanup.

Protected original PostgreSQL service-install inputs reused (admin/monitor/
replication): verified TLS SELECT1 PASS admin all3, monitor and replication.
Known operator generic password was not valid for these distinct infrastructure
accounts; no password reset. Existing QA Docker input reused from protected
custody. Values transferred only via stdin into root600 files, never printed.
Bundle06 standard validation PASS:
`sha256:f51403684a13295450ddd051d73d219436fb62afda8628ca19ba44ebf6411ab7`.
Completed transfer archives04/05 removed on Execution Node to avoid disk pressure;
verified local packages/extracted releases retained. Node2 finished source05
workspace cleaned via standard helper; acquisition payload remains for build06.

## Native final06 and structured start

Native Apply PASS rc0, 434.19s: localhost changed0; node1/node2/node3
changed3 each (endpoint publication), failed0. Native Verify PASS rc0,
120.16s, changed0 on localhost and all3 hosts. Protected logs remain in the
QA secret holder; safe recaps are native-apply06-summary.json and
native-verify06-summary.json under its qa-trace directory.

A9-Q05 PASS: both HTTPS /status endpoints on443 validate current CA/SAN and
return200 with all8 checks ok. Both SDKU direct targets and CSPA direct target
also return200/all8. Safe evidence: a9-endpoint-final06.json.

Structured staging06/07 rejected SSH trust before lease/Start because standalone
inventory repeats ansible_ssh_common_args under both all.hosts and target-group
hosts. This is a QA setup mismatch, not relaxed in production. A fresh staged
copy recursively removes those standalone overrides and uses protocol-owned
approved known_hosts; original standalone fixture remains unchanged.
Staging installer-1791914206874917: EXECUTABLE, all3 targetConnections have
unsupportedOptions=false; trust STAGED. Authoritative mixed run started:
installer-bbccb047d5d2b66257d4963501b13d4e, bundle06, initial pki:apply RUNNING.
Terminal result/barrier acceptance remain pending.

The first mixed run was explicitly cancelled by the agent during PKI preparation
because of an incorrect assumption about the separate protocol state root.
Subsequent inspection proves PKI uses the existing canonical execution PKI root;
CA fingerprint remains95def9fa2c8d53093bce0489184d471dfac3b45f34f19c5ae544818af0abf306,
CA/key timestamps unchanged. Vault and SDKU HTTPS still200 with trusted TLS.
This cancellation is not a product failure or a PKI state-binding defect.
Owner explicitly requested a fresh full run and completion of remaining QA.
Fresh staging installer-1791914588581043 EXECUTABLE, trust STAGED; run
installer-e84d33a1670daaf77f800a8f7177ea9a STARTED, bundle06, pki:apply first.

Additional bounded evidence during the mixed run:
- Fresh equivalent builds08/09 have identical project revision
  sha256:b83f1f6db4b6a197571f2879b33cc38fe0eb3567c7643a23ef61d6b8087ae6ba
  and plan fingerprint
  sha256:53ace86bd12fcf419aa7b3fcd9a64fa014ef1608824e71e1a69f2f0a505c3c2b.
- Actual EVO_MANAGER_APP_ID/KAFKA_APPLICATION_ID_CONFIG equal apigateway-sdku
  on both SDKU placements and apigateway-cspa on CSPA. SERVER_ID equals node1/node2;
  actual image ID matches approved caa73a17... on all3.
- Redis trusted mTLS authenticated PING returns PONG for both users on all3
  declared members (6 checks). This supplements /status, whose Redis check uses
  the first target and whose Sentinel check discovers/validates the master.
  Kafka probe code traverses all advertised SSL targets with ApiVersions.
- Vault own shared read200/foreign shared403 in both directions; temporary
  AppRole login tokens revoked. Existing account-path isolation remains PASS.
- Current-source execution-secret-lease27 tests PASS; runtime values were not printed.
- Secret-value audit of22 project/events/native-log files and9 materialized
  Compose/.env/agent files PASS, no leaking paths. Terminal events will be audited again.
- CSPA-only missing-binary fixture prepared; target-free plan EXECUTABLE,
  revision sha256:c444f7b67a70325f4a311095ef673d08adf9d09ebdfa4a1165344e62643b2efc.
  No failing Apply launched while the common run is active.

Offline Build under unshare -n PASS, EXECUTABLE with the same fingerprint as
the ordinary build. This proves current mixed/library planning needs no target
or registry contact. During common PostgreSQL Apply, observed node2 becomes
standby; library provider/cleanup must discover the writable member, not pin it.
Both QA databases contain zero user tables; owner roles match library ownership.

## Mixed Kafka preflight failure and bounded type correction

Mixed run installer-e84d33a1670daaf77f800a8f7177ea9a FAILED at Kafka Apply,
2026-10-13T18:53:53Z. All8 preceding deployments completed Apply/Verify SUCCESS;
applications never started, correctly preserving the infrastructure barrier.
The safe public diagnostic is ANSIBLE_OPERATION_FAILED; protected scoped native
reproduction identifies SCHEMA_REGISTRY_PORT_INVALID before Kafka broker mutation.
Contract validation and Kafka metadata discovery are read-only PASS.

Ordinary project_runtime.yml scalar set_fact converts integer default REST ports
8081/8082 to strings in classic Jinja. Removed only the two redundant global port
assignments: existing project_deployment_host.yml already resolves member,
deployment and ordinary role-default ports directly. Shared Registry filter stays
strict; no casting of invalid boolean/float inputs and no new mechanism/tasks.
Risk classification: bounded internal type preservation, LOW-RISK; existing
independent Kafka selector/PostgreSQL/HAProxy review scopes remain unchanged.
Current-source native regression PASS:1 test,8 subcases (classic/native Jinja,
defaults, integer overrides, boolean/float rejection). Pure Registry16 PASS.

Baseline qa-kafka-structure has no Registry units on any host. Other Registry QA
units on node2 belong to different deployments and are preserved. QA fixture now
explicitly sets schemaRegistryEnabled=false, keeping the deployed Kafka component
scope instead of adding Registry from newer role defaults. Listener configuration
and original full-services project files remain unchanged. Bundle07 built on node2;
Standard bundle07 validation PASS, archive identity verified on Execution Node. Scoped Vault Verify PASS (83.80s): localhost50/node1 55/node2 53/node3 53, changed=0/failed=0 everywhere. Scoped manual Kafka input now explicitly points to the already approved offline archive/checksum; Vault uses the existing Core-derived role-variable map. These are QA input corrections, not new production mechanisms. Kafka Apply PASS (485.43s): localhost290 changed0; node1 253/node2 250/node3 250, changed2 each, failed0. Kafka Verify PASS (114.86s): localhost19/node1 165/node2 150/node3 150, changed0/failed0 everywhere. Fresh bundle07 staging installer-1791920742131584 Build EXECUTABLE; project revision sha256:a18f21e3da41fe6839c6ed69a8fae5b9d54d002a8cfb09e96b56a69e397949e1. Fresh bound trust and typed runtime lease staged; full mixed run installer-769ab17af4b08aeba306c3b4b8995f6c STARTED on bundle07. All23 operations retained, PKI first and applications after all10 infrastructure Verify operations. Run terminated FAILED at apply:qa-vault-consumer, 2026-10-13T21:03:02Z (2026-10-14 00:03:02 Moscow). All9 prior infrastructure Apply/Verify operations, including Kafka, succeeded. Neither application operation started: infrastructure failure barrier preserved. Public diagnostic ANSIBLE_OPERATION_FAILED; scoped reproduction of the exact Vault operation is running with the frozen Core projection and protected current inputs, keeping already-completed PKI materialization skipped. No second general Start or cancellation issued. Scoped protected log identifies node2 failure at Require host swap disabled for Vault Raft (VAULT_SWAP_ENABLED). Live read-only swapon confirms node2 /dev/sda3 active ~4GiB, ~1.17GiB used; node1/node3 have no active swap. General run events retain operation and generic ANSIBLE_OPERATION_FAILED but no precise failed task/code. No swap change performed; Scoped reproduction terminal FAILED (228.04s), solely node2 VAULT_SWAP_ENABLED; all changes0, node1/node3 passed. Owner on 2026-10-14 explicitly removed swap preflight while retaining disable_mlock=true. Only two tasks deleted, no target swap change. Independent narrow FULL DIFF APPROVE, zero findings: reviews/vault-swap-removal-diff-review.md. Current source synced to RED OS b9f234eb798240da8732fbeda89f9ff5. AppRole3/provider14 and Apply/Verify syntax PASS. Role contract suite 28/29 PASS; one existing unrelated Kafka gate string-equality assertion fails because Kafka now adds phase exclusion. No unrelated production correction introduced. Separate current-source Vault Apply launched with frozen Core projection, approved artifacts/protected inputs and completed PKI skipped; current-source Vault Apply PASS (278.11s), including internal cluster verification and public HTTPS endpoint probe. Recap localhost97 changed0/node1 255 changed1/node2 181 changed4/node3 179 changed0, failed0 everywhere. Protected log vault-noswap-apply.log; safe trace vault-noswap-apply-summary.json. This is scoped standalone acceptance, not a successful full mixed run; immutable bundle07 still contains the old swap check and must be rebuilt before a fresh mixed plan.


## Owner-authorized shared Vault reset for fresh bootstrap (2026-10-14)

Owner explicitly selected qa-vault-consumer on node1/node2/node3 for reset before the full-service bootstrap. Initial native Clear check failed VAULT_CLEAR_PATH_UNSAFE with no mutation: /data is platform-automation UID1001/0755, accepted by Apply but rejected by Clear. Added the same exact custom-root owner exception to Clear, retaining every member/marker/config/unit/mount/FD guard. Independent narrow FULL APPROVE (reviews/vault-clear-custom-root-diff-review.md); post-review projection narrows optional arguments to applicable custom roots, preserving default/manual path behavior. RED OS path9 and projection12 PASS. Retire-member historical suite 4 PASS/1 skip/1 error because its pinned 2026-09 release is absent; no production error claimed. Final check PASS (5.86s) all3, predicted changed1 each, no actual mutation. Native Clear PASS (24.00s): node1 ok33/node2 ok19/node3 ok19, changed2 each, failed0. Safe trace vault-clear-summary.json / vault-clear-audit.json. Actual audit: all3 exact units inactive/disabled/MainPID0; /data/qa-vault-consumer contains only .vault-member.json. Shared /data ownership unchanged; old canonical bootstrap generation3 audit preserved. This is Raft reset, preserving software/configuration/PKI for the next bootstrap. Old admin token/unseal inputs are no longer valid for this reset cluster; next mixed run must select CURRENT_RUN_BOOTSTRAP and supply no stale Vault typed inputs. Bundle08 was built before the Clear compatibility fix and will not be used as final QA runtime; Bundle09 application-a9-20261014-09 built on node2 5bd31fcdd883476b87d7be19c03ca6c5. Standard Go validate-bundle PASS, digest sha256:56722e4cc8d7e08974ea38fb6ca6c399719347661d758c6e4f2ca6c297d3ab64; archive SHA256 6d56496d2c119c4244ab38e81f42356465680ed001e040e10d182543bd022698 (1053426329 bytes), local and Execution Node identity verified. Fresh staging installer-1791958355002797 EXECUTABLE, project revision sha256:75bb8c502a3f12d0f03d75c28deb0294645cefa1139a1d33b29c1274874db3f3, execution manifest digest sha256:d0be4e586d7fa3c9da2d2e1e14040fec28baa0fd957c213dba3159566165d222. Trust staged and typed lease bound; no old Vault admin token/unseal inputs supplied, application provider selects CURRENT_RUN_BOOTSTRAP. Full mixed run installer-e957af662422c17c1b994d42ebcea233 STARTED; all23 operations retained. Fresh mixed run FAILED at applications:apply, 2026-10-14T07:30:05Z. All10 infrastructure Apply/Verify SUCCESS, barrier satisfied before applications:apply at sequence46 (2026-10-14T07:21:40Z). No applications Verify ran. New bootstrap generation4, package78545e51926c2cbff661cab50eaebc4a, sourceRunId matches current run; protected outputs preserved. New root token authenticated via trusted public Vault HTTPS endpoint (200) and copied only to protected QA runtime input. Application runtime projection was cleaned by terminal hygiene. Public diagnostic ANSIBLE_OPERATION_FAILED. Scoped standalone full-library Apply reproduction running with bundle09/current desired state and fresh token; Exact scoped reproduction FAILED (256.26s) on node1 at Reconcile exact instance with no pull build or dependency startup; localhost provider hooks changed0, node2 own placement started successfully. Read-only inspect of both stopped owned node1 QA containers reports exit128 and engine error: OCI runtime create failed: runc create failed: container with given ID already exists. This is target runtime state, not Vault authentication/configuration. Verified project/library/instance/host labels and approved image ID before recovery; only the two stopped A9 containers on node1 force-recreated through their existing exact Compose context, no daemon restart or foreign container mutation. Both commands rc0. All3 direct /status and both CA/SAN-verified HTTPS endpoints returned200 with8 checks after recovery. Safe trace a9-oci-recovery.json / a9-after-oci-recovery-status.json, raw Docker diagnostics protected. Scoped native full-library Apply after recovery PASS (428.51s): localhost198/node1 321/node2 185/node3 114, changed0/failed0 everywhere, including trusted public endpoint probes. Read-only identity comparison confirms previous/current container names and Compose service/project identical; only internal IDs changed by recovery, safe trace a9-oci-name-check.json. All3 direct and2 HTTPS status200/overall ok/all8 states ok, current trace refreshed. Mixed run11 remains FAILED and is not retroactively PASS. Fresh equivalent bundle09 plan12 EXECUTABLE (same project revision75bb8c50..., manifest digest sha256:3aa009a9b4b4257ce9dcce29d24591a48d491bc5ba3236b73724af0d836ca022). Vault now initialized: explicit RUNTIME_INPUT using protected valid generation4 token/shares, not CURRENT_RUN_BOOTSTRAP and not old generation3 material. Fresh full mixed run installer-7e3b40ba3d11601244801190389e3975 STARTED, fresh bound trust/lease/Start, all23 operations retained; terminal acceptance pending. Previous local verified artifacts retained; obsolete node2 source/build07 and08 workspaces cleaned with qa-sync after normalizing permissions of their owned public files.


## New owner-directed clean Docker cycle with Schema Registry (2026-10-14)

Owner explicitly requested a new A9 cycle: ensure Docker QA containers and conflicting resources absent before full-services; enable Schema Registry; reuse bootstrap credentials of installed Vault. Previous mixed run12 installer-7e3b40ba3d11601244801190389e3975 cancelled through CancelExecution, terminal CANCELLED at2026-10-14T08:05:26Z before cleanup, controller/cgroup stopped and lease cleanup performed by existing protocol. No overlapping install mutation.

Read-only inventory all3 daemons: only3 A9 containers (2 node1,1 node2), no volumes; node1 also had2 orphan A8 Compose networks. Exact ownership/image labels verified, three containers gracefully stopped/removed; five empty QA networks removed, retaining builtin bridge/host/none and approved cached image. Owned application runtime root project-b46aa3f5f57a495f removed after exact canonical-path/marker validation; absent all3. Unexpected additional runc entry on node1 exactly matched old SDKU ID b91370235398c91020af937431e2cf49ab7f3c30a13fd9169f1f9822d748d9ac from prior failure. Recorded PID no longer existed; native runc state reported stopped/pid0. Only that confirmed owned entry deleted with native runc delete (no force, no process kill). Final audit all3: zero Docker containers/volumes, only builtin networks, zero containerd tasks and zero runc/v2-task directories. Ports28480/28481 and Registry8081/8082 free all3. Raw inspections avoid secret/environment contents; safe records a9-clean-cycle-before-docker.json, a9-clean-cycle-cleanup.json, a9-clean-cycle-after-docker.json, a9-clean-cycle-runtime-before.json, a9-clean-cycle-runc-delete.json, a9-clean-cycle-runtime-audit.json. This confirms stale OCI metadata existed; it does not establish a cause involving Compose source-directory changes.

QA native desired state now explicitly schemaRegistryEnabled=true, schemaRegistryKafkaListener=SSL; ordinary role API defaults8081/8082, existing SSL9094 retained. No unrelated Schema Registry deployment/unit changed. Same verified immutable bundle09 already includes approved Registry archive closure; no new download/build required. Installed Vault data preserved. Current protected admin token and unseal shares match published bootstrap generation4/package78545e51926c2cbff661cab50eaebc4a, root token lookup-self through trusted HTTPS200. New plan selects RUNTIME_INPUT and supplies exactly current bootstrap values, not generation3.

Fresh staging installer-1791965500226439 EXECUTABLE, project revision sha256:b91043caa9cd56e86cb387a68b18d7a54d1bc38c2e52989c478bc7b10ee96fd9, execution manifest digest sha256:e000703218895e121d124db02d40cac2e32f06e7bc96de86e7089a1df516591d. Registry artifact requirement present, full23 operations retained. Bound trust/lease/Start accepted: new run installer-53e7dace16407a4a3ef87a3706be7648 STARTED on bundle09 digest56722e4c..., PKI first. Terminal/bootstrap reuse/Registry acceptance and remaining repeat/failure-retry/cleanup pending. Prior runs remain historical FAILED/CANCELLED, no retrospective PASS.

Cycle13 terminal: FAILED at2026-10-14T09:18:12Z. PKI and Keepalived/BIND/DNS Client/Docker/HAProxy/PostgreSQL/Redis/ClickHouse Apply+Verify SUCCESS. Kafka Apply started09:07:03Z and failed09:18:11Z (ANSIBLE_OPERATION_FAILED); Kafka Verify, Vault and applications not reached. Infrastructure barrier not satisfied; no application acceptance claimed. Safe events13 preserved. Native Kafka diagnostic reproduction started after terminal, using bundle09/current fixture and protected output; exact failing task pending. No full Start repeated.

## Ansible task diagnostics correction (2026-10-14)

Owner requested task/host/error code without secrets. Controller now passes the actual journal root to the existing callback (custom A9 state root previously received no task events). Failed tasks retain static name, host, closed reason code/summary and numeric rc/HTTP status. Arbitrary msg/stdout/stderr/assertion/traceback never enters events; no_log/censored results remain opaque. Unknown reasons stay generic. No Go/UI changes or immutable bundle mutation.

RED OS current-tree: classifier4 PASS; task-observability22 PASS/4 isolated acceptance SKIP. Additional real Ansible local /bin/false through callback/custom owned journal root PASS: task Probe command failure, host node1, exit code1. Independent FULL DIFF APPROVE, no findings. Base1db6604488525eb04125630789361e4042665b99; tracked patchSHA256 0B08F28DA69C8475A52663D70084CD130B1DE2E665FA34401BFCE823EAC47BCF; new classifier2BD2EA96080A6AADD8DB81F0E4AC3B0E804F3C63424E57F7B025C052DCCFAF1B; new tests35C49C332C31161C9601CA50152250335F51770B1A561231512C35B52D8D5A39. Not yet present in bundle09; new verified bundle required before dependent full runs. Kafka diagnostic reproduction remains separate/in progress; no claim of Kafka repair or A9 completion.

Owner requested Kafka reproduction with new diagnostics. Initial native13 rc2/706.44s at Require the pinned Registry artifact bytes, SCHEMA_REGISTRY_ARTIFACT_MISSING_OR_CHECKSUM_MISMATCH. This reproduction omitted artifact-source authority and is NOT equivalent to failed mixed run13; cannot establish its cause. Immutable bundle archive439047802bytes has expected dc4d6234e0f7e1a91b369f9cf1d27d7c9885edb9f6440170c3a6f00ba68fcc81. Native14 callback QA stopped deliberately rc99 after incomplete context was identified; no task failures. Its initial diagnostic-only journal unit metadata was corrected to canonical ownership tuple; no production journal altered. Corrected native15 uses current-tree source4175a789..., exact artifact authority copied from mixed run13 operation projection into protected runtime inputs, authorityactive=true, normal existing Kafka Apply. Sequential start only after prior Ansible workers exited. New callback confirms real task/host events in .runtime/a9-kafka-diagnostics/runs/a9-kafka-diagnostic15. Exec session16332; raw output protected .runtime/qa-trace/a9-kafka15-diagnostic.log, safe summary after completion. Original mixed run13 remains FAILED; actual cause pending equivalent reproduction.

## Kafka run13 root cause confirmed with structured diagnostics

Corrected native15 current-tree Apply FAILED rc2/781.02s at platform.core.artifact_delivery / Copy selected offline artifacts to the target on node1,node2,node3. New callback persisted2232 task events. Archived stdout privately shows missing source /var/lib/platform-installer/runtime/current/runtime/artifacts/kafka/confluent-community-8.3.2.tar.gz on Execution Node. Run13 operation projection contains exact platform_execution_bundle_root but does not supply platform_execution_runtime_root; delivery uses latter default. Bundle09 archive is present and sha256dc4d6234e0f7e1a91b369f9cf1d27d7c9885edb9f6440170c3a6f00ba68fcc81 matches. Kafka broker checks passed before Registry artifact delivery.

A bounded follow-up corrected closed diagnostic classification for one-level failed loop results; parent/child no_log preserved, no raw values emitted, nested depth not followed. Added regression test: classifier5PASS on RED OS currenttreee03240a5373543539dae083d7fabb868. This bounded correction follows prior APPROVE; not a new independent review claim for its new hash.

Paired native test through unchanged source gate and artifact_delivery role, exact original artifact authority:
- default runtime root: rc2/16.14s, all3 hosts failed same copy task with structured ANSIBLE_FILE_NOT_FOUND / Required file or executable not found;
- only platform_execution_runtime_root explicitly changed to exact bundle09: rc0/48.43s, no failed tasks; ordinary target SHA256 verification passed all3.
Safe evidence .runtime/qa-trace/a9-registry-delivery-root-comparison.json; raw logs protected0600. This proves wrong runtime-root selection rather than archive corruption, Kafka SSL or broker startup. No production root-selection correction or immutable bundle mutation performed in this diagnosis. Original full run13 remains FAILED; full Registry installation/Verify and A9 remain pending.

Owner approved runtime root correction and continuation. artifact_delivery role default now follows existing platform_execution_bundle_root, explicit manual runtime_root wins, previous current-path fallback retained when bundle_root absent. RED OS node2 current-tree native tests2PASS, including bundle/manual/fallback3cases. Independent narrow FULL DIFF APPROVE zero findings at patchSHA25657229030693369DE6C0566B1ADB08A12FA22C395862B46482110F3BF6524722D. Same reviewer separately inspected immediately affected loop-classifier delta, no findings; no second FULL of diagnostic gate. New immutable bundle10 built on trusted node2 workspacecddb3772d44148328f3a533bbc09486f using existing approved runtime inputs only. Archive1053439567bytes/SHA256bae1040190b64a545b22b0933f01742ad57380c805ba9dfc2bbc96e582655a61; standard validation/transfer and native Kafka Apply/Verify pending.

Bundle10 standard Go validate-bundle PASS: sha256:ff20edef88f895077b1f4a2cf1287dcd2b919b54feaa5aaa4860b44659346e96, catalog08cd1f4c... unchanged. Local+ExecutionNode archive checksum verified. Both native QA project.yml and groupvars artifactLock digest updated10 (initial inconsistent copy correctly rejected PROJECT_SNAPSHOT_INPUT_INVALID/APPLICATION_ARTIFACT_LOCK_CONFLICT; no target mutation; corrected both). Fresh Build EXECUTABLE staginginstaller-1791972126528050/projectrevisiond3fa0b35e150be61fb294d59b374e5f5207ae68c8e04b10e5f66277f38a3534e/manifest522cab5210960fda30040028a179c0cd28e10eabfdaa56593535d366ec1f67c7. No Start from this staging; native mutation requires fresh Build before full retry.

Native Kafka bundle10 Apply then Verify started sequentially(exec9907); journal .runtime/a9-kafka-diagnostics/runs/a9-kafka-bundle10, protected logs .runtime/qa-trace/a9-kafka-bundle10-apply.log/verify.log, safe summary a9-kafka-bundle10-summary.json. Exact newplan artifactauthority used; platform_execution_runtime_root override absent to exercise corrected default. Source bundle immutable, no cache/UI publication claim. Full mixed run14 not started; old13 remains FAILED. Existing generation4 Vault credentials preserved.

Bundle10 native Kafka+SchemaRegistry Apply PASS rc0/1250.04s, failures0. Final Apply trusted HTTPS peer checks SUCCESS on node1,node2,node3. Automatic standalone Verify follows in the same sequential QA wrapper; terminal Verify still pending. Safe summary a9-kafka-bundle10-summary.json. No full mixed retry started yet.

10:30Z follow-up audit: no active Ansible process and no Verify log; previous foreground SSH QA wrapper ended after persisting Apply summary, so the prior statement that Verify was already running was premature. Apply PASS remains valid. Did not repeat Apply. Started only existing Kafka Verify from bundle10 as detached native-QA process with protected script/log and current structured journal. No production execution lifecycle changed; no overlapping target operation. Verify pending.

Bundle10 native Kafka+SchemaRegistry Verify PASS rc0/501.73s, failures0. Detached Verify completed with terminalSUCCEEDED in scoped journal. Bounded /subjects probes on192.168.56.101/.102/.103 HTTP8081 and HTTPS8082 all returned200 and JSONlist; HTTPS checked certificate chain/identity using project authority CA. Safe trace a9-registry10-http-https.json.

After native completion fresh full Build staginginstaller-1791974557947351 EXECUTABLE; revision sha256:d3fa0b35e150be61fb294d59b374e5f5207ae68c8e04b10e5f66277f38a3534e; manifest sha256:522cab5210960fda30040028a179c0cd28e10eabfdaa56593535d366ec1f67c7; all23ops. Current Vault root token lookup-self via trusted HTTPS200 before Start. Fresh target-trust approval and typed lease bound to exactplan; Start accepted runinstaller-1b841ff0be0df5899fefe37f13482969 /attempta3fc34f4fc1648e0a62e5cfbbca3ec74 at2026-10-14T10:43:05Z. Existing initialized Vault gen4RUNTIME_INPUT, no reset/stalegen3. Full plan startsPKI, not skipping infrastructure. GetExecution/GetEvents monitor retained at holder/.runtime/qa-trace/a9-monitor14.py, safe replayevents a9-structured-events14.json; supports pagination for new task stream. Terminal/barrier and application acceptance pending. No commits/master/Go/UI.

Run14 terminal FAILED2026-10-14T12:08:09Z, actionVaultApply. All nine prior infraApply/Verify pairs SUCCESS including Kafka/Registry; VaultVerify/appsnotreached, barrier notsatisfied. Structured failed task events:12313node1/12314node2 Require space for one current and fourteen rotated audit files (ANSIBLE_ASSERTION_FAILED);12451node3 Read seed initialization state over verified API TLS(no_log/ANSIBLE_FAILURE_REDACTED). No arbitrary raw failure published. Follow-up diskbytes node1=1086976000,node2=1553412096,node3=25373958144, node1/2 below1600000KiB required. VerifiedTLS sys/init200/initializedtrue all3 at follow-up; no persistent API failure established.

Bounded own-QA cleanup, no service data changes: local archive09 SHA6d56496d2c119c4244ab38e81f42356465680ed001e040e10d182543bd022698 reverified, only obsolete holder/final09 removed after exact canonicalpath/nosymlink/manifestcheck; node1 freebytes3632476160 afterward. Node2 obsolete build09 workspace5bd31fcdd883476b87d7be19c03ca6c5 cleaned viaqa-sync; first permissionfailure resolved only for exact public QA workspace with ownership/mode restoration then standardcleanupPASS. Current bundle10/acquisition source/canonical PKI/Vaultdata/bootstrap/holdersecrets preserved.

Detached native VaultApply thenVerify startedPID415674 via protected QA script holder/.runtime/secrets/qa-vault-bundle10.py. Uses bundle10,currentgen4 token/shares, exact authority of run14, no reset. Journal .runtime/a9-vault-diagnostics/runs/a9-vault-bundle10-space-retry, protected raw .runtime/qa-trace/a9-vault-bundle10-apply.log/verify.log, safe summarya9-vault-bundle10-summary.json. Original mixed14 remainsFAILED. No overlapping mutations or duplicate fullStart; new fullBuild required after scoped retry.

Owner acceptance/scope amendment2026-10-14: explicitly no more full infrastructure reruns because of elapsed time and already exercised infrastructure/barrier. After in-progress native VaultApply/VerifyPASS run ONLY libraryApply/Verify, then remaining accepted repeat/CSPA failure-retry/boundedcleanup. Do not interpret prior automation fullretryinstruction as currentauthorization; schedulerupdated. Mixed14 remainsFAILED, infrastructure acceptance assembled from nine mixed successful servicepairs and separately completedVaultpair; barrier denial beforeinfra completion documented, notfull23opterminalPASS. CurrentVaultApplystillRUNNING12:15Z/noerrors.

Native Vault space-retry Apply FAILEDrc2/246.03s at node1 Require the explicit output parent to be an existing controller-owned directory. This is native QA input custody, not production guard regression: explicit outputdir holder/.runtime/secrets(root0700) had parent holder/.runtime UID1001, while controller rootUID0. Existing mixed execution uses its own protected custody, unrelated. Corrected only native protected extra vars to outputdir holder/.runtime/secrets/vault-native-output with root-owned0700 parent. No guard weakened/no canonicalbootstrap overwritten/noVaultreset. New detached native Apply/Verify output-retry PID429981, journal .runtime/a9-vault-diagnostics/runs/a9-vault-bundle10-output-retry; safe summary .runtime/qa-trace/a9-vault-bundle10-output-summary.json; protected raw a9-vault-bundle10-output-apply.log/verify.log. Prior failed summaries preserved. Owner no-fullinfra-rerun instruction remains: libraries only after VaultPASS.

Native Vault output-retry Apply PASSrc0/649.13s and Verify PASSrc0/98.00s, failures0, final healthy configured voting-members checksSUCCESS. Existing data/bootstrapgen4retained. Owner-amended acceptance combines nine servicepairs frommixed14 and separateVaultpair; originalmixed14FAILED not rewritten. No further full infrastructure run.

Started only existing application-libraries-apply.yml then application-libraries-verify.yml fromimmutablebundle10/currenta9-project, detachedPID469241, protectedscript .runtime/secrets/qa-libraries-bundle10.py. Journal .runtime/a9-application-diagnostics/runs/a9-libraries-bundle10; safe summary .runtime/qa-trace/a9-libraries-bundle10-summary.json (with bounded recap hostcounts), protectedraw a9-libraries-bundle10-apply.log/verify.log. Ordinary standalone extra.json, no Go/UI/productionbypass/newfullStart. LibraryApply/Verify terminal and real/status checks pending.

Library-only bundle10 Apply PASS835.26s: localhostok198changed0,node1ok317changed16,node2ok183changed8,node3ok114changed0; failures/unreachable0. Verify PASS228.25s: localhostok70/node1ok106/node2ok44/node3ok34, changed0/failed0/unreachable0 everywhere. Scoped journal terminalSUCCEEDED. No fullinfra rerun. Five actual /status checks (SDKUdirectnode1+node2,CSPAdirectnode1,SDKU+CSPA publicHTTPS) all200/overallok/all8checksok: clickhouse,kafka,pkcs12,pkcs12Client,postgresql,redis,sentinel,vaultAgent. PublicHTTPS validated projectCA and hostname. Evidence a9-libraries10-status.json and librarysummary. Remaining approved cleanrepeat with metadata, CSPAfailure/newrevision/retry,boundedcleanup; notfullA9DONE.

Owner requested completion of remaining tests. Q06 read-only before snapshot .runtime/qa-trace/a9-repeat10-before.json saved: all3 exact container IDs/image/StartedAt/Running, live HAP/BIND files SHA256+mtimeNs, service start/restart state and SHA256 of systemd ExecReload state, PostgreSQL DB/role OIDs+ACL discovered on sole writable database member node3:5432 (monitor excluded),10 Vault KV metadata versions. No secret values or RoleIDs stored. Reusable safe helper .runtime/qa-trace/a9-snapshot-repeat10.py, requires exact3containers/1writableDBmember.

Unchanged full library scope Apply then Verify repeat started detachedPID526556, protectedscript .runtime/secrets/qa-libraries-repeat10.py, summary .runtime/qa-trace/a9-libraries-repeat10-summary.json, journal .runtime/a9-application-diagnostics/runs/a9-libraries-repeat10. Samebundle10/currentdesired/runtimeinputs; no infra rerun/no benchmark. After terminal snapshot a9-repeat10-after.json and compare before/after stable metadata. Failurefixture not yet started. Current CSPA override location group_vars/all/platform-installer.yml: platform_desired_state.applicationLibraryDeployments.cspa.applications.gateway.overrides.command (currently inherited/default). Failure must use fresh copy currenta9-project and only CSPA command change, full libraryscope retained.

Q06 PASS: unchanged repeat Apply853.80s/Verify229.29s, every host changed0/failed0/unreachable0. After snapshot a9-repeat10-after.json: exact full metadata equality withbefore; comparison a9-repeat10-comparison.json identicaltrue/changedMetadataPaths[]. Thus all3 containerID/StartedAt/image/running unchanged, all10KVversions unchanged, PostgreSQL writable node3 DB+roleOID/ACL unchanged, liveHAP/BINDhashmtime and service/reload metadata unchanged.

Q08 fresh fixture a9-failure10-project copied currentbundle10/Registrytrue desired. Only CSPA overrides.command=['/usr/bin/a9-missing-binary']; baselinea9-project untouched. Target-free Build with deploymentOrder=[] returned CORE_OPERATION_FAILED; no targets contacted. Existing full projection order accepted same candidateEXECUTABLE revisionaf0d43cf97510f83e07089bee51dfcb560e5c189577c3829fab7bfa54eb6a426 staginginstaller-1791984106785548; no trust/lease/Start/full infrastructure execution. Plan files a9-failure10-plan.json and a9-failure10-plan-full-projection.json preservebothoutcomes. Uses existing planner projection forrevision only; actual ownerapproved test remains ordinary standalone full-library Apply.

Failure-before metadata a9-failure10-before.json saved. Detached Apply-onlyPID581780 script .runtime/secrets/qa-libraries-failure10.py started; journal .runtime/a9-application-diagnostics/runs/a9-libraries-failure10, safe summary .runtime/qa-trace/a9-libraries-failure10-summary.json; protected rawlogs. No Verify will run on this failing revision, no infrastructureoperations, fullSDKU/CSPAscope retained. Await actual failure, proveSDKUunchanged/status/sharedinfrastructure healthy, then repairednewrevision/freshprojection/retry.

Q08 deliberate failure observed: Applyrc2/654.42s, noVerify. Failedtask Require reachable HTTP targets before candidate publication (HAProxy,all3,no_log). CSPAownedcontainer recreated, VaultAgent supervisor remainsRunning but missing application binary confirmed by bounded log classification(no rawlog published); publicCSPAHTTPS503. SDKUbothcontainerID/StartedAt/image/Running exactly unchanged; two direct+trustedHTTPSstatus200/overallok/all8checksok. All10KVversions unchanged, all3liveHAPBINDhashmtime andExecReloadstate unchanged. Safe traces a9-failure10-isolation.json,a9-failure10-cause.json,before/after snapshots. This proves failure stayedlocal and candidatepublication blocked, not rollback of alreadychangedCSPAcontainer.

Only CSPA commandoverride removed fromsame isolatedfailurefixture; baselinea9-project untouched. Fresh targetfreeCoreprojection EXECUTABLE staginginstaller-1791985135494023 restoredrevisiond3fa0b35e150be61fb294d59b374e5f5207ae68c8e04b10e5f66277f38a3534e differsfromfailingaf0d43... (returnsoriginalhealthycontent). Safeplan a9-retry10-plan.json. No infrastructureexecution. Detached full-libraryApply/VerifyretryPID616902, script .runtime/secrets/qa-libraries-retry10.py, journal .runtime/a9-application-diagnostics/runs/a9-libraries-retry10, safe summary .runtime/qa-trace/a9-libraries-retry10-summary.json. Awaitrecovery/SDKUstability, postretryrepeat andownedcleanup.

Q08 recovery PASS: repaired full-library Apply882.97s, localhost/node2/node3changed0,node1changed3 (CSPA restoration), failures0; Verify235.85s changed0/failed0 allhosts. Snapshot a9-retry10-after.json provesSDKU IDs/StartedAt/image/running unchanged acrossfailureandretry and all10KVversionsunchanged. Five actualdirect+CAverifiedHTTPS/status probes200/overallok/all8checksok; safe a9-retry10-recovery.json. Isolatedfixture restoredhealthyrevision; baselinefixture nevermodified. Deliberatefailure remainsFAILED/noVerify; recoveryterminalSUCCEEDED.

Required post-retry unchanged full-library Apply/Verify repeat started detachedPID672545 script .runtime/secrets/qa-libraries-postretry10.py. Usesrepairedfailurefixture and samefailure10-extra inputs. Beforemetadata copiedfromretry-aftersnapshot to a9-postretry10-before.json; originalQ06 before/afterevidencepreserved. QA-onlysnapshothelperallowlistextended for a9-postretry10-after.json. Newjournal .runtime/a9-application-diagnostics/runs/a9-libraries-postretry10; safe summary a9-libraries-postretry10-summary.json. Awaitchanged0/metadataequality thenboundedcleanup/secret-hygiene/finalevidence. Noinfraexecution/benchmark.

## Final closure — 2026-10-14

Owner explicitly requested remaining owned-resource cleanup, secret verification,
final record and observation stop. No further infrastructure execution was run.

Final post-retry unchanged library Apply **875.29s PASS** and Verify **244.08s
PASS**, changed0/failed0/unreachable0 on localhost and all three nodes.
The entire stable before/after metadata JSON is identical: three container IDs,
StartedAt/image/Running, ten Vault KV versions, PostgreSQL database/role OIDs/ACL,
live HAProxy/BIND hashes/mtime and systemd start/restart/ExecReload state.
Original Q06 and Q08 failure/recovery evidence is retained separately; deliberate
failure and mixed14 remain historical FAILED.

### A9-Q15 — owned cleanup PASS

- Rechecked exact Docker project/library/instance/host labels, image and per-scope
  .owner.json markers. Removed three owned containers gracefully, their three
  empty Compose networks and exact project runtime tree. All three daemons now
  have zero containers/volumes and only bridge/host/none networks. Approved probe
  image retained on node1/node2; node3 originally had no image.
- Reused existing HAProxy ownership capture/archive/activate and partial reload
  tasks for exact pre-A9 SDKU backend bytes (SHA256
  1d2252f2c1626fc1b45155f2de780302941e3e5029b308a1bc7bfe7a1f40d475),
  removed only the new CSPA backend, and preserved current infrastructure
  ClickHouse/Vault/stats/public fragments. The pre-A9 synthetic SDKU node2:18081
  target was already unreachable; no unrelated listener was started to manufacture
  readiness. This is baseline restoration, not a post-cleanup A9 application
  availability claim. The cleanup wrapper accidentally included localhost and
  node1 aliases of one physical host: duplicate candidate unlink failed and
  wrapper rc2 is retained honestly. Localhost and other two hosts completed the
  guarded activation; independent physical-host hash/service audit proved exact
  owned rollback and unchanged shared fragments on all three nodes.
- Removed only CSPA A record through local BIND nsupdate; SDKU A192.168.56.111
  retained. Direct authoritative queries on all three hosts confirm this state.
- Discovered writable PostgreSQL database member node3:5432, rechecked exact
  database/role ownership comments and zero user tables. Dropped only a9_sdku/
  a9_cspa databases, their two login and two owner roles, without CASCADE.
  Other database/role inventories unchanged.
- ClickHouse ownership witness UUIDs matched actual objects on all three members.
  Only owned qa_isolation Memory tables existed, with no retained rows.
  Dropped the two A9 users/databases ON CLUSTER default; all three members confirm
  absence and unchanged unrelated object inventories. Removed only their four
  witness entries.
- Redis/Sentinel exact ownership markers and password verifiers matched on all
  three members. Removed only a9_sdku/a9_cspa ACL users, persisted ACL SAVE and
  removed matching witness entries. Unrelated ACL definitions unchanged.
- Vault policy owner headers, AppRole policies and all ten KV _platform_owner
  fields matched A9 identities. Revoked matching application token accessors,
  removed two AppRoles/two policies and ten KV metadata documents. Independent
  audit confirms zero matching tokens and all owned paths absent; default/root
  policies retained and current admin token remains valid. Initial post-delete
  wrapper assertion incorrectly required200 from an empty AppRole LIST; actual
 404 is expected. This wrapper assertion is not a service failure.
- Bounded preservation audit: 11/13/11 selected infrastructure units active on
  node1/2/3, authoritative DNS rollback PASS, trusted HTTPS Vault health and
  ClickHouse ping200. Shared infrastructure data, PKI and images preserved.
- Standard qa-sync cleaned 19 confirmed source/build workspaces, then one bounded
  retired-public holder workspace containing 28 source/fixture/bundle children.
  Trusted pre-existing acquisition input and unrelated workspaces preserved.
  Existing Journal and lease cleanup mechanisms removed terminal transient
  inputs/transport credentials; zero lease payloads/private run keys remain.
  Removed102 native-QA private files. Holder now retains only its audit/evidence
  namespace. Canonical generation4 bootstrap outputs remain at their original
  protected location; contents matched current inputs before deleting QA copies.
  Persistent workstation execution identity was preserved.

### A9-Q14 — secret hygiene PASS

Literal-value checks loaded credentials only from protected runtime files:
21 current/retained historic values checked against1383 local source/doc files,
627 protocol files and268 public runtime/project/event/log/evidence files,
with zero matches. A prior materialization scan checked15 .env/Compose/config
files on actual application hosts, zero matches. Immutable bundle source scan
also returned zero matches. These bounded checks do not claim discovery of
unknown credentials. No secret values were copied to documentation/evidence.

Automatic approval review rejected both recursive and empty-directory removal
of local .runtime/secrets/a9. It contains zero credential files and is retained
as an explicit harmless cleanup exception; no alternate deletion mechanism
was used after the second rejection.

### Result / custody

A9 is COMPLETE for the owner-amended standalone Core/Ansible scope.
Infrastructure acceptance combines nine successful mixed14 pairs, separate
successful Vault Apply/Verify and already exercised barrier evidence. Mixed14
is not relabeled SUCCESS; owner explicitly prohibited another full infra run.
Go/Wails/React and visual acceptance remain outside this A9 claim. No commit,
master modification or next milestone implementation performed.

Safe export:163 JSON/structured-event files preserved locally at
.runtime/qa/a9/final-evidence; every file matches its SHA256 manifest.
Verified local bundle10/prior bundles retained. Compact public result:
[a9-final-qa-summary.json](a9-final-qa-summary.json).
No active QA wrappers remain. Observation is stopped after final state recording.

## Commit and master synchronization authorization — 2026-10-14

Owner explicitly requested the A9 commit and synchronization into master after QA closure. Preserve historical failures and the owner-amended acceptance scope. This authorizes Git integration/publication and focused post-merge regression, not another infrastructure installation or a Go/UI milestone.
