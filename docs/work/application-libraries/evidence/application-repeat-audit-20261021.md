# Повторные действия Library Apply/Verify — 2026-10-21

Scope: owner requested removal of the post-readiness Vault probe and inspection
of other repeated actions. No new deployment, restart, bundle publication or
changes to the four excluded applications are authorized by this source change.

## Изменено

`application_runtime/tasks/activate_instance.yml` sets
`application_runtime_verify_vault: false` for its included container Verify.
Apply no longer performs AppRole login, declared-secret reads and probe-token
revocation after each container becomes ready. Container image/ownership labels,
Running and configured healthcheck checks remain. Library Verify already disables
this Vault probe. Direct role Verify retains its default opt-in-by-entrypoint
behavior (the role variable defaults to true).

Vault preflight, document ownership/CAS, policy/AppRole reconciliation, private
RoleID delivery and Agent secret retrieval remain unchanged. This change does
not introduce a replacement AppRole login probe at another stage.

Reference observation: runtime52, run
`installer-bbc4aca2bfd5a29db7800643fc96f540`, saved revision
`sha256:4db17c3d100833786cb298b10b8340dca6d2b6eea7933081073b526ece83d85e`.
The removed segment took 138s across six placements (30/32/20/26/16/14s).
This is a previous-run measurement, not a measured speedup of the changed code.
Runtime52 on the stand still contains the old behavior.

## Остальные повторы

Owner follow-up: Kafka account preflight removed from the standard provider
stage. SCRAM metadata, credential authentication and ACL inventory are checked
once in Apply; missing managed credentials/grants are then created as before.
The interrupted attempt to cache preflight observations and its unfinished tests
were removed. No cache/key/fingerprint mechanism remains. This moves credential
and principal-conflict discovery into Apply, after possible library resource
creation, but before Vault instance publication and container startup.
Standalone explicit Kafka preflight/Verify entrypoints are unchanged.
Other candidates below have not been changed.

Next owner-approved refinement: the standard Kafka account Apply and explicit
provider Verify now use Core's existing deployment job containing all selected
accounts. The role reads all SCRAM metadata with one `--describe --entity-type
users` and all ACLs with one `--list --resource-pattern-type any` before its
account loop. Exact principal/resource selection and per-account credential
authentication remain; failed/partial inventory blocks account mutations.
For two existing users in one deployment, expected reads/authentication calls
are now4 (1 metadata +1 ACL +2 logins), down from6 in the single-pass version
and12 in runtime52. This is batching within an invocation, without a cache.
The SCRAM output header used for exact selection follows
[Apache ConfigCommand](https://github.com/apache/kafka/blob/trunk/tools/src/main/java/org/apache/kafka/tools/ConfigCommand.java).

Runtime52 login timings (TASK_COMPLETED, including CLI/JVM/Ansible/SSH overhead):

| Phase | First user | Second user | Total |
| --- | --- | --- | --- |
| Former preflight | 27.195s | 27.425s | 54.620s |
| Apply | 24.349s | 23.829s | 48.178s |

These are two logical-user checks, not six application-placement checks.
Each CLI runs on the projected administrative broker and bootstraps against
the account's first SASL candidate. There is no internal timing breakdown of
JVM startup, TLS, SASL and Kafka requests; no specific cause of the24s duration
has been established, and the number is not a pure SCRAM handshake latency.

Shared-read follow-up QA: native8 PASS/95.255s, ACL/provider/admin-provider31
PASS/15.176s, Apply and explicit provider Verify syntax PASS; source-sync and
git diff --check PASS. An initial pair of fixture failures caused by selecting
administrative instead of application JAAS was corrected and the native8 suite
passed. No stand deployment/new runtime or measured changed-runtime timing.

Durations below are sums of public TASK_COMPLETED elapsedMilliseconds, including
Ansible/SSH overhead. They are not pure server processing times or guaranteed
savings. Shared-stage totals must not be added as independent speedups.

| Действия | Наблюдение runtime52 | Возможное сокращение и граница |
| --- | --- | --- |
| Kafka metadata, SCRAM login, ACL inventory | Для двух principals каждый из трёх запросов выполнен и в preflight, и в Apply: 12 CLI calls, 320.087s; preflight 167.794s, Apply 152.293s | Изменено по решению owner: удалён стандартный Kafka account preflight, все проверки сохранены в Apply. Для двух существующих пользователей с grants ожидается 6 CLI reads/login вместо 12. Удалённый preflight занимал 167.794s; новая стендовая длительность не измерена. |
| ClickHouse table declarations | `Render declared tables...` выполнен 8 раз, 47.059s: common scope вызывается для library/instance preflight и resources/accounts | Проверить повторное использование одинаковых SQL declarations внутри вызова; resource/account scopes выполняют разные проверки и mutations, удалять вызовы целиком нельзя. 47s — вся задача, не доказанная стоимость повторного шаблонирования. |
| Docker image inspect | На каждое размещение: preflight reserved-reference inspect; перед delivery ещё inspect той же ссылки; затем повторный inspect для image/platform; отдельно inspect исходного тега | Для уже имеющегося locked image первый delivery inspect может одновременно проверить ID/OS/architecture и заменить второй (его сумма 7.665s/6 calls). После pull/load свежий inspect обязателен. Исходный тег отличается от managed reference; его проверка не является тем же запросом. Preflight и активацию разделяет длинный provider stage. |
| Vault projection | `prepare_application_vault` вызывается в resolve-runtime и затем vault-preflight по тому же snapshot; второй вызов 1.927s | Переиспользовать уже подготовленную projection в этой цепочке; сохранить самостоятельный вызов preflight с явным входным контрактом. Небольшой приоритет, target contacts отсутствуют. |
| Vault policy/role GET | По одному чтению на instance в preflight и перед reconciliation: 4 задачи, 11.184s | Повтор перед записью защищает ownership от изменений после длинного provider stage; сохранить. Document CAS также сохранить. |
| Container readiness и endpoint probes в Apply и Verify | Container Verify: 881.660s в Apply против 23.691s в финальном Verify | Разные временные барьеры: Apply ждёт запуск, Verify подтверждает итог. Сохранить. Длительное ожидание запуска не означает повторную установку. |

Common library files are already written once per library/host; six writes in
this run are two libraries times three hosts. Image delivery checks the local
image before selecting pull/load; skipped task events do not prove repeated
archive transfer. Topic and ACL per-resource discovery has already been batched;
fresh metadata/config reads after new topic creation remain necessary.

## Проверка изменения

Focused native Ansible checks: 4 PASS in 26.767s on RED OS node2 using current
qa-sync sources; application-libraries-apply syntax check and git diff --check
PASS. Tests use fake
Docker output in private temporary directories, without contacting deployed
containers, Kafka or Vault. Cases cover direct lean container Verify, actual
activation with Agent and no Vault credentials, rejection of an unhealthy
container, and the existing library Verify scope. Live React/Wails execution follow-up is recorded below for runtime53.

Kafka single-pass follow-up: current-source RED OS node2 QA41 PASS/79.034s
(native batch10, ACL4, provider23, admin-provider4); Apply and Verify syntax,
source-sync verification and git diff --check PASS. Temporary source workspaces
cleaned with qa-sync. No target installation or new runtime publication.

## Runtime53 follow-up: full-plan result

Owner-authorized full real React/Wails alarm-view SDKU/CSPA repeat with skipInfrastructureVerify=true SUCCEEDED: runf217c7d0, runtime53 babc4089; [exact IDs, timing and limitations](sdku-cspa-alarm-view-journal.md#runtime53-common-offline-archive-barrier--full-plan-acceptance-pass). One shared archive integrity check37.744s replaces six per-placement checks, keeping target-copy integrity checks. Shared SCRAM metadata1/ACL inventory1 plus login2; post-readiness Vault probes0, final Verify provider audits0. Six healthy containers and both HTTP200 endpoints PASS. Source archive native/runtime QA27 PASS/one skip; independent FULL DIFF blocking0, OAR-D01 nonblocking coverage recommendation remains open. First runtime53 run failed at second-user login assertion; repeat both assertions PASS without password changes. Kafka timeout/disconnect events in logs remain an acceptance limitation, no auth/ACL errors. Apply37m36s/Verify6m39s are observed repeat timings, not controlled speedup evidence.
