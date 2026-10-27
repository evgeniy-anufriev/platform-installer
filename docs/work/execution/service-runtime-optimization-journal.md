# SERVICE-RUNTIME-OPTIMIZATION — QA journal

2026-10-26. Branch `codex/service-runtime-optimization`, base `4236abaf`.
Implementation is in the separate worktree. Active runtime bundle07 and the
ongoing full installation were not replaced or restarted.

## Changes

- Kafka Apply enters Schema Registry with already prepared facts, without a
  second run of Kafka main. Defaults are loaded by the existing include_role.
- One all-ACL read serves the infrastructure security guard and all principals.
  Application account batches use the same read task. Missing ACL writes remain
  additive and resource-scoped; no new Java helper or daemon was introduced.
- Certificate principals are computed once and shared explicitly with hosts;
  native reverse-host-order coverage protects the source-host selection.
- Ordinary service Verify retains health, protocol, configured TLS/auth and
  cluster readiness. Repeated file/configuration audits and data-path guards are
  excluded. Vault configuration readback remains after Apply; explicit provider
  Verify and explicit PKI Verify remain available.
- BIND and HAProxy Verify are unchanged, as requested by the owner.
- Endpoint preparation reuses the existing controller application rows in the
  same Ansible process. The normal resolver remains the fallback when rows are
  absent. There is no persistent or cross-process cache, precedence resolver,
  extra public setting, Go/UI change or additional desired-state authority.
- The proposed first-member-only `_schemas` read was reverted after review;
  every participant retains the original resource prerequisite before startup.

## Baseline from the ongoing old-bundle run

Run `installer-680e7daae6c8379c42f6ec2044de2842`, plan
`plan-7a7a974ea497c18a5410fde9`, runtime07
`sha256:a7503b52c12d07f43bc40978bea8ecf4024937fc291b0aa13e9d8e89ac17158d`.
The timing snapshot was taken while PostgreSQL Apply was still running, after
8417 seconds (2:20:17), not at terminal completion.

| Operation | Wall time | TASK_STARTED |
| --- | ---: | ---: |
| Kafka Apply | 37:20 | 2021 |
| Kafka Verify | 14:09 | 845 |
| ClickHouse Apply | 19:50 | 1128 |
| ClickHouse Verify | 5:24 | 452 |
| Redis Apply | 9:01 | 1003 |
| Redis Verify | 1:16 | 151 |

ClickHouse Apply breakdown: actual ClickHouse role 5:03; application resolver
7:23; HAProxy 3:00; artifact delivery 1:19. Across the snapshot, application
resolution consumed about 43:25 and 5360 of 10753 task starts. The UI had 25542
events, which is not a count of unique tasks: starts and host completions are
separate events.

Times are nonoverlapping intervals between task starts within each operation,
including orchestration/waiting overhead. Parallel host times are not summed.
This is a recovery/repeat installation, not a pristine cold-install benchmark.
No measured acceleration or 30% target achievement is claimed yet.

## Native RED OS QA

Source transferred by `scripts/qa-sync.ps1` as platform-automation to node102;
no Python/Ansible was installed or run on Windows. All native task fixtures use
isolated paths/endpoints. No production service was changed by these tests.

| Check | Result |
| --- | --- |
| Kafka service suite | Final complete rerun: 38 PASS, 25.467 seconds |
| Kafka native account/ACL/admin/bootstrap suites | 46 PASS across seven isolated processes |
| Vault service suite | 62 total, 56 PASS / 6 gated skips |
| Redis service suite | 19 PASS |
| PostgreSQL service suite | 34 PASS |
| ClickHouse service suite | 11 PASS, including native tests; obsolete PKI assertion corrected and rerun |
| Docker service suite | 11 total, 9 PASS / 2 gated skips |
| BIND suite, unchanged final source | 26 PASS |
| HAProxy suite, unchanged final source | 31 total, 18 PASS / 13 gated skips |
| Keepalived suite | 13 PASS |
| DNS client suite | 8 PASS |
| Real Ansible health/TLS/auth tasks | 8 PASS: Registry healthy/repeat/missing CA/untrusted CA; Vault health/auth/Raft, bad token, sealed; PostgreSQL command/auth/TLS environment and repeat |
| Native non-seed `_schemas` prerequisite | 1 method / 3 cases PASS; incompatible and missing never reach activation |
| Native endpoint reuse | 1 method / 3 cases PASS; two-host real endpoint action, controller rows/fallback/prepared sources; changed=0 |
| Endpoint projection unit cases | 8 PASS |
| Execution runtime bundle | 7 PASS |
| Execution bundle artifact sources | 2 PASS |
| Syntax | 10 service Verify entrypoints + Kafka Apply PASS |

The PostgreSQL health tests use a substitute psql executable to check invocation,
password environment and failures; they are not a live PostgreSQL acceptance.
Registry/Vault health fixtures use an actual isolated TLS HTTP server. Kafka
CLI fixtures are isolated substitutes invoking actual production Ansible tasks;
they are not a live cold Kafka installation benchmark.

Initial failures are retained in runtime QA logs. Corrections: fixture defaults
for the Kafka normalizer; old Keepalived phase-name selectors; missing
project_root in a provider action fixture; obsolete endpoint import paths; tests
updated to distinguish Apply configuration readback from health Verify.
The authorization-status case passes in its own process; the combined discovery
process had an Ansible collection loader collision. No production loader bypass
was added. A negative `_schemas` fixture initially used retries=0, which bypasses
Ansible until evaluation; it now uses retries=1, production retries unchanged.

## Review and acceptance limits

[Independent FULL DIFF and owner-approved D01 recheck](service-runtime-optimization-review.md).
D01 RESOLVED, blocking findings0; N01 remains nonblocking. The later bounded
endpoint reuse has separate native evidence and is not claimed as part of the
D01 recheck. BIND/HAProxy exceptions and existing topic checks are preserved.

No updated bundle, real React/Wails installation, cold benchmark or repeat
installation acceptance of these new sources has been performed. The running
old-bundle installation cannot demonstrate the new implementation's speed.
These acceptance items remain open. No new installation run was started.

## Source identity and cleanup

Final tested workspace on node102:
`/var/tmp/platform-installer-qa-a0bd92e1cb274e5e9613bf7bb7f942c8`.
All 50 changed/new Core and service source/test files matched the local working
tree byte-for-byte. Digest of sorted path:SHA256 entries:
`9c0eb3848f8467f3ec7681e23f50f655468ca339db84835192cc3f331cb5a4eb`.
Safe runtime reports/logs are retained locally under
`.runtime/qa/service-runtime-optimization/`; all nine temporary source copies
were removed with standard qa-sync cleanup after evidence capture.

## Профиль «Подготовить ресурсы и провайдеров» текущего run

Тот же old-bundle run680e7daa; child action `applications:prepare`, начало
sequence26793. Окончен успешно: 15:13:05–16:10:37 UTC
(18:13:05–19:10:37 MSK), **57:32**, 1739 TASK_STARTED. Безопасные отчёты:
`.runtime/qa/service-runtime-optimization/results/preparation-profile.json` и
`preparation-kafka-statuses.json`. Время — непересекающиеся интервалы журнала,
включая ожидания и Ansible overhead, без суммирования параллельных хостов.

| Область | Время |
| --- | ---: |
| Kafka resources/accounts/ACL | 25:36 |
| Подготовка размещений/конфигурации приложений | 13:04 |
| Resolver библиотек | 4:04 |
| PostgreSQL provider | 3:54 |
| ClickHouse provider | 3:31 |
| Vault provider | 2:48 |
| Redis provider | 1:02 |
| Оркестрация и проверка архивов | 3:33 |

Kafka: пакетное исходное описание/конфигурация уже есть. Выполнено10 созданий
топиков, затем10 индивидуальных describe и10 config readbacks;10 записей ACL,
2 установки SCRAM-паролей и2 аутентификации. Для индивидуальных describe/config
журнал содержит20 starts каждого имени, но10 SKIPPED и10 SUCCESS — это не20
выполненных CLI. Описания заняли3:40, config readbacks3:32, create3:08, ACL add3:03.
Каждый CLI-вызов стартует отдельную JVM;20–23 секунды относятся ко всему
вызову/подключению/обвязке, не к отдельно измеренному CPU startup.

Runtime preflight.yml —10:20 из13:04, много небольших проверок на11 размещений.
Docker discovery уже переиспользуется, повторный «кеш» не требуется.
Наибольший одиночный интервал — проверка уникальных offline archives1:44.
Ошибок в TASK_COMPLETED нет; этап не завис в одном часовом таймауте.

Дополнительные кандидаты, пока без изменения реализации: пакетный readback
всех созданных топиков перед потребителями, группировка совместимых ACL writes,
проверка уникальных общих путей по узлу с сохранением изоляции каждого placement,
сокращение независимых мелких resolver tasks. Этот этап действительно нуждается
в расчёте приложений; инфраструктурный shortcut не устраняет его целиком.
Первоначальные чтения SCRAM/ACL уже пакетные.

## Этап2 общей оптимизации — результаты

Владелец принял расширение области; [план](service-runtime-optimization-phase2-plan.md).
FULL PLAN blocking0 и FULL DIFF APPROVE/blocking0 записаны в
[ревью](service-runtime-optimization-review.md). Scoped validation и обе endpoint
точки не вычисляют приложения для service-only операций; полный Validate и
mixed/app/full-reconcile пути сохранены. DNF batch использует authority names и
прежний exact filter; неуспешный общий запрос возвращается к раздельным запросам.
PostgreSQL объединяет выбранные repository packages без смешения источников и
семейств. PKI integrity не меняется; повторный keytool probe нужен лишь после
неуспешного первого. Исправлено затенение include_vars старым set_fact в общей
подготовке legacy manifest, подтверждён сброс при исчезновении файла.

RED OS native/unit результаты:

- scoped/full validation и metadata:5 PASS, включая full→infra→full;
- endpoint orchestration:2 PASS, service-only/mixed/full/invalid scopes и fallback;
- PostgreSQL:36 PASS, включая7 source/family и4 binary-reprobe сценария;
- HAProxy:31 PASS под sudo в изолированных временных фикстурах, без пропусков;
- source authority:4 PASS; batch source playbook:3 PASS;
- project validation:24 PASS;
- service integrations8, service endpoints9, application endpoints8,
  application integration batches11 PASS;
- runtime bundle7 и artifact-source bundle2 PASS;
- PKI service contract13, keytool1 method/4cases, single-pass4 и
  single-pass-resolution16 PASS. Последние16 завершились за1254.311s; это
  длительность регрессии с временными сертификатами, не текущей установки;
- syntax:10 service Apply + полный Validate + infrastructure Validate PASS;
- git diff --check PASS.

Итоговая source copy node102:
`/var/tmp/platform-installer-qa-9c240d5389544280a811f1742809e7a0`.
Все73 изменённых/новых Core/service source/test files совпали с локальными bytes.
Digest sorted path:SHA256:
`0a0fc7fe7d6518d66405afce8c6f698c61135ec4bdbd2e4544d7322c312bf5ff`.
PostgreSQL transaction проверена подменой package action в фикстуре; реальная
RPM-установка и updated-source React/Wails/cold benchmark не проверены.
Новый bundle не опубликован, текущий old-bundle run не прерывался.
Сохранены11 безопасных QA logs; все5 временных source copies этапа2 удалены
стандартным qa-sync cleanup. Для root-owned pycache после sudo-фикстур сначала
восстановлено владение только точного QA workspace, затем повторён cleanup.

### 2026-10-26 — сокращение topic readback и preflight

Решение владельца: после успешного создания топика не выполнять отдельные
`describe` и чтение конфигурации. Начальные два пакетных чтения сохранены;
существующие топики проверяются на drift, ошибки CLI создания блокируют Apply.
Удалены неиспользуемые ветки индивидуального readback. Это не гарантирует
отсутствие конкурентного создания другим оператором при `--if-not-exists`;
следующий Apply проверит фактическое состояние обычным пакетным чтением.

Preflight: три задачи сборки пар config/archive digest заменены одним set_fact
через стандартные map/zip/sort; отдельная задача платформы образа объединена
с независимой подготовкой Docker environment. Порядок зависимых вычислений,
файловые проверки, user namespace, владельцы и Docker discovery не изменены.
Для каждого размещения устранены три верхнеуровневые задачи и цикл set_fact
по конфигурационным файлам. Новых кешей и модулей нет.

RED OS node102, текущие источники через qa-sync:
- native Kafka batch: 11 PASS, 25.461s; fresh + repeat = 5 CLI вместо7,
  единственный create; нет post-create reads; create failure блокирует выполнение;
- native preflight pairs: 1 PASS / 3 cases, 1.009s: empty, configs+archive,
  Unicode и удаление stale pairs; итоговый digest совпадает с ожидаемым;
- runtime contract: 25 tests, 24 passed / 1 skipped, 2.290s;
- дополнительный старый live discovery test FAILED: его фиксированный аккаунт
  platform-docker отсутствует (getent rc2). Первые две production routing tasks
  не изменены. Это не PASS и не проверка новой установки.

Активный bundle/run и целевые сервисы не менялись. Реальный выигрыш времени
после обновления bundle пока не измерен; группировка ACL остаётся отдельным
неисполненным пунктом принятой оптимизации.

### 2026-10-26 — совместимые записи ACL: реализация и QA

Per-account collector группирует точную missing delta по resource type,
pattern и canonical operation set. Case-sensitive resource names deduplicated.
Один общий writer: scoped batch flag только в include, прямые callers по-прежнему
немедленные, ошибка блокирует последующие группы. Нет новых секретов в argv,
изменения private cleanup, удаления ACL или атомарной гарантии.

RED OS current-source native:
- новые stateful CLI/Ansible ACL9 PASS (финальный повтор31.044s);
- существующие accounts12 PASS90.167s, ACL5 PASS4.410s, topic/batch11 PASS23.040s;
- Kafka service38 PASS59.632s;
- реальный installed Kafka4.3.1 parser принимает повторные topic selectors;
  проверка обращалась только к недоступному127.0.0.1:1, не рабочим brokers.
- FULL DIFF APPROVE, blocking0; N01–N03 закрыты, см. review journal.
- Все82 изменённых/новых Core/service files byte-equal remote/local:
  digest348017519fa8d4d8c4cd01a83b6b4e61f3c0a9c1c3c50a6a2a6ce05877793756.

Новый bundle/run не создавались; реальная установка updated-source pending.

### Профиль СЗИ текущего старого bundle07

Run installer-680e7daae6c8379c42f6ec2044de2842, child applications:library:szi:
19:10:48–20:06:33 МСК, **55:45**, ACTION_COMPLETED SUCCESS.
Run перешёл к applications:library:sdku без известных FAILED events.

Подробные TASK events достигли normal capacity32512 в19:56:20 МСК;
marker task-observability.json: degraded=true / TASK_EVENT_LIMIT.
Поэтому полная разбивка есть лишь для первых45:32; последние10:13 нельзя
приписывать последней видимой задаче. Critical ACTION markers сохранены.

Неперекрывающиеся интервалы TASK_STARTED с overhead, округлённо:
- runtime16:53, включая image_delivery9:48, verify3:15, apply_instance1:59;
- package_script11:31: 18 вызовов, фактический command5:11, обвязка6:20;
- Vault provider6:31 /245starts;
- HAProxy4:33 /102starts;
- playbook/orchestration5:21; BIND0:31; settings/resolver0:11.
Общее количество записанных TASK_STARTED967. Это не точный profiler чистого
CPU/SSH и не сумма параллельных длительностей хостов; после cutoff данные
неполные. Безопасный JSON profile сохранён в ignored QA results.

### 2026-10-26 — этап4: пакетные hooks и доставка Vault

Package v1alpha4 добавляет opt-in batch только для provider_prepare и
connection_apply / execution=once. Старые схемыv1–v3 неизменны. Соседние
совместимые hooks группируются по order/target/runOn/id/sourceSHA/exact secret
references; зависимости вычисляются до группировки. Приватный JSON исходных
argv поступает по PLATFORM_SCRIPT_BATCH_FILE, generic runner не знает продукта.
Timeout300×N, прежний kill/cleanup. integration.sh получает admin token один раз
на пакет (существующий401 refresh сохранён), выполняет исходные операции
последовательно и суммирует changed. Bootstrap/accounts границы сохранены.

Решение после SRO4-D01: source delivery cache **полностью удалён**, каждый вызов
выполняет штатные file/copy. Source SHA нужен только opt-in grouping. В Vault
остались invocation-only факты exact provider/route/host/bridge discovery, но
ownership/KV/CAS/policy/role по-прежнему читаются перед изменением. Дублирующий
внешний instance preflight убран; standalone instance выполняет полный preflight.
Generated password сохраняется из существующего protected runtime file, уже
использованного для account, вместо повторной генерации при404 до KV delivery.

Endpoint/image audit: независимые endpoints уже публикуются пакетом, ранняя
публикация Keycloak нужна потребителям; image inspect уже исключает повторную
доставку присутствующего locked image. Дополнительных механизмов не добавлено.
Safe metadata исходного run подтвердила clients9/groups3/group-roles3/accounts1
(16 integration.sh invocations) плюс2 bootstrap =18 generic command calls.

QA RED OS из текущих source copies:
- финальный root native runner6 PASS38.937s, в том числе D01 root A→nobody B→A:
  B действительно подменяет соседний first, третий вызов восстанавливает bytes,
  UID0/mode0700 и даёт A,A; cache-переменных нет;
- contract/projection10 PASS0.089s: old schema rejection, phase/once restrictions,
  actual prepare_script_jobs→prepare_integrations, SHA и оба consumer endpoints;
- Keycloak batch native4 PASS23.765s после удаления cache: direct и реальный
  Ansible role, fresh/repeat changed0, один admin token, partial failure/recovery;
- Vault native4 PASS86.805s: actual deliver-ready на изолированном HTTPS fixture,
  fresh/repeat, по одному KV read на документ, CAS race и сохранение соседнего
  поля, foreign owner без записей, provider/route/host/bridge key isolation;
- Vault action/filter16 PASS; legacy runner2, SZI accounts3/role recovery4 PASS;
- integration11, script selection3/input availability2, callback9/library27/
  post_install26/runtime bundle7+2 PASS; stage1 11PASS/1 отдельный fixture skip;
- SDKU catalog28 schema/digest checks и26 Compose renders PASS;
- Go test ./... и go vet ./... PASS. Первый Go run выявил ожидаемые устаревшие
  catalog digests после редактирования manifests; каталог обновлён и полный
  повтор PASS. Первый TLS fixture использовал literal password в job и не прошёл
  leak assertion: исправлен fixture на штатный runtime_secret_ref, assert сохранён.

Финальный source proof104 Core/service/contract/example files mismatch0:
96f7979ee6af9107442133878e3f60d65a43c61b8cf33b3cc9a32405cb5af73f.
FULL DIFF BLOCK/D01 и owner-approved TARGETED_RECHECK APPROVE записаны в review.
Обновлённый bundle не собирался/не публиковался, новый run не запускался,
updated-source React/Wails и измерение реального ускорения не выполнялись.
Предел TASK-журнала диагностирован и остаётся отдельным вопросом.
Все 9 временных QA source workspaces этапа4 удалены стандартным qa-sync cleanup; безопасные результаты и source proof сохранены локально.

### Выпуск optimized runtime и новый run — подготовка

Владелец разрешил bundle + новый полный run. Из текущего worktree через qa-sync
собран на trusted node102 runtime service-runtime-optimization-20261026-01 из
approved runtime-input07, без новых загрузок. Bundle3.5ГБ перенесён, validate /
standard publish-bundle / validation project staging PASS:
sha256:ca1ff310c7dbdfa3d20d7162cd07eac41940ae70f514f281428175c134f7228e.
Active worktree cache опубликован, прежний original-repo cache/bundle07 сохранён.
SCP в deep worktree сначала выявил Windows MAX_PATH; повтор через temporary R:
alias того же QA directory завершён успешно, после чего весь bundle проверен.

Отдельная QA-копия project с прежним ID project-b46aa3f5f57a495f подготовлена
в .runtime/qa/service-runtime-optimization/project. Пакеты keycloak/szi/sdku/cspa
скопированы patch1.0.1 с новыми v4 hooks, исходными binary assets и рабочими QA
defaults; новые path refs/version definitions согласованы. Сохранённые libraryRefs
ещё1.0.0: подготовленный actual React helper изменит их в draft/Review/Save перед
Project Verify/Plan/Start. Это повторный Apply без удаления текущих ресурсов.

Go dev EXE собран, Vite5180 running. Два инструментальных запуска Wails отклонены
автоматической проверкой: blocked by policy, конкретный reason не сообщён.
Новый run НЕ НАЧАТ. Ручной launcher start-release-wails.cmd подготовлен, но через
инструменты не выполнялся. После ручного Wails34122 следует выполнить существующий
bounded UI helper scripts/install-release-ui.cjs: реальный Open/Rebind/Prepare,
package refs edit+Review/Save, runtime secrets и full Plan/Approve/Start.
Не подменять React/Wails прямым Ansible и не обходить инструментальный запрет.

Ручной Wails34122 запущен владельцем; actual React flow продолжен. Первое
OpenProject выявило MANAGED_DOCUMENT_INVALID: в QA patch-копиях SDKU/CSPA
manifest.version1.0.1 не совпал с defaults.version1.0.0 (4-space YAML indent
не покрывался исходной заменой). Исправлены только подготовленные package
1.0.1 definition versions; Core/guards не менялись. ReadManagedProjectView
подтвердил MANAGED_VIEW_OK для original и новой копии. Rebind UPDATED на ca1ff310,
SSH trust101/102/103 подтверждён; идёт подготовка Execution Node нового runtime.

Повторная подготовка optimized runtime: передача остановилась при 3 ГБ
свободного места на101. По явному разрешению владельца удалены только три
неактивных runtime/releases (6176ee8e,4f28eb70,9fc176c7); active a7503b52
сохранён, выполняющихся Core/Ansible процессов не обнаружено. После удаления
свободно14 ГБ. Реальный React/Wails helper повторно запущен, SSH trust101/102/103
подтверждён; передача нового bundle через штатную подготовку выполняется.
Новый установочный run пока не начат.

Новый full React/Wails run STARTED: installer-6e8bcfed3e54fc55e8e40d9872552e08,
активный runtime ca1ff310, пакеты szi/sdku/cspa/keycloak1.0.1. Scope FULL_PROJECT,
skipInfrastructureVerify=false, skipApplicationLibraries=[], порядок szi→sdku→cspa;
размещение szi103/sdku101/cspa102. Remote status RUNNING/sequence181 подтверждён.
В подготовке исправлены только QA-helper шаги: после Save переподтверждены SSH
ключи для новой ревизии; секреты повторно переданы штатным session API/полями.
Библиотечный Vault token загружен из того же защищённого инфраструктурного файла
через существующий descriptor-bound SetDeploymentRuntimeSecretValues, без вывода.

По запросу владельца срок действия плана отображается с явной Europe/Moscow,
датой/секундами и МСК. ISO/RFC3339 значение API и TTL не менялись. Реальный DOM
React/Wails: 26.10.2026, 23:39:29 МСК. InstallationPage31 PASS, typecheck PASS.
Выявлен отдельный UI-дефект preview: неудачный фоновый запрос Core не повторяется
при возврате в Сервисы с тем же binding/revision/runtime; исправление ещё не внесено.

### Анализ Project Verify / Plan / Start (26 октября, МСК)

Повторных установок для замеров не запускали; источник — текущий код,
mtime фиксированных артефактов четырёх staging-каталогов и локальных QA-логов.
Интервалы mtime обозначают фазы между публикациями результатов, а не CPU-time.

| Staging | archive→image inputs | inputs→images | images→plan |
| --- | ---: | ---: | ---: |
| installer-239552843… (первый Plan) |59.72с|2.15с|57.57с|
| installer-270879127… (повтор при Start) |51.13с|1.87с|53.99с|
| installer-191835670… (следующий Plan) |59.04с|1.69с|55.65с|
| installer-6e8bcfed… (успешный Start) |58.10с|1.85с|56.07с|

Успешный Start: archive.digest22:50:47 → inputs22:51:45 → images22:51:47
→ plan22:52:43 → metadata22:52:51. Plan→metadata8.28с. От публикации
archive.digest доmetadata124.30с. Локальный approve-token-attached.log создан
22:49:02, последний ответSTARTED22:52:56: весь helper Approve+Start234с.
Остаток109.70с не разделён на таймеры: approval, descriptor query, staging,
capability/binding/protocol и возврат UI. Не приписывать весь остаток одной фазе.
Для Project Verify отдельный надёжный wall-clock/подэтапные тайминги в текущем
логе отсутствуют; оценка по общим ожиданиям не выдается за измерение.

VerifyProject: hash saved revision → read-only node inspection → archive/hash/
SCP/extract project → project-snapshot.yml (project settings + application
resolver + snapshot) → revision/runtime checks. UI затем отдельно запрашивает
CurrentProject/PKI/endpoint projections, что увеличивает ожидание кнопки.

Plan: capabilities + project staging → PrepareApplicationImages.DESCRIBE
(Ansible inputs/snapshot/resolver) → PREPARE (inspect/acquire images; в этих
замерах около2с) → deployment-plan-machine.yml (resolver+snapshot+plan).
Approve при неизменном режиме локально проверяет план/acknowledgements/секреты;
смена executionMode может вызвать новый Plan из React.

Start: ещё раз Core runtime-secret-descriptors.yml со staging/snapshot/resolver,
protected output capability → authoritative rebuild Plan со всеми image phases
→ fingerprint comparison → target trust staging → private credential leases/
local durable run record → async controller dispatch. Полного повторного
runtime bundle transfer в этой цепочке нет. InspectExecutionNode читает state,
OS/sudo/free space; он не хеширует заново весь bundle.

Риск/возможная оптимизация для отдельного согласования: повторные resolver/
snapshot в descriptors, image DESCRIBE и final Plan; archive/revision/staging;
editMu удерживается на длительных synchronous Verify/Plan/descriptor операциях.
Ни одна проверка или поведение Start в рамках анализа не менялись.
Remote execution installer-6e8bcfed RUNNING/sequence539 подтверждён.

### 27 октября: причина отсутствия Vault inputs и исправление повторного SSH approval

Run installer-6e8bcfed terminal FAILED 26.10 23:20:29МСК на apply:qa-vault-consumer.
Bootstrap assert VAULT_BOOTSTRAP_CREDENTIALS_REQUIRED, no_log скрывает payload.
В events типизированные входы Vault, назначение admin token и unseal shares
SKIPPED на всех3 узлах. Пакетные изменения Vault не меняли resolve_runtime_inputs,
execution_controller или execution_secret_lease.

Причина подтверждена Go-overlay тестом без SSH target контакта: Probe/Approve
Execution Node раньше безусловно invalidated dynamic binding. Цепочка
invalidateDynamicBindingLocked → clearRuntimeSecretDescriptorEvidenceLocked →
Broker.ClearRuntimeSecretValues удаляла pending/attached typed inputs и Plan.
Во время прошлой QA-подготовки после загрузки файлов повторно подтверждался
ключ node1, затем повторно заполнены обычные пароли/application token, но не
восстановлены typed SERVICE_ADMIN_TOKEN/SERVICE_UNSEAL_SHARES для самой роли.
Это объясняет одновременно потерю плана и последующий Vault assert.

По прямому запросу владельца Probe больше не заменяет binding до результата.
Same-key approval сохраняет binding, plan, pending/attached inputs только при
совпадении node/address/port/user/credential generation/runtime и прохождении
existing trusted pin/command guard. Новый ключ и tampered pin заменяются штатно.
Focused4 PASS (включая prepared/unprepared подслучаи), Go all/vet PASS.
По запросу владельца review остановлен; последующий review не вызывается.

Новый Wails reapproval.exe34123 собран/запущен, active bundle прежний ca1ff310.
Незавершённые изменения Core phase5 в bundle не публиковались. Full retry
готовится через actual React handlers; finite protected file-picker queue.
До Plan helper проверит secretsInstalled до/после реального same-key recheck.
Нового run ID пока нет; прежние окна не закрывались.

Повторный FULL_PROJECT run после исправления SSH reapproval:
installer-c14d36d0500efb8a3f5a3ac61bb0040c STARTED 27.10.2026 09:27:46МСК,
plan-1277f48e179590eea1b1a3e0, bundle ca1ff310; Wails34123/actual React.
Scope no skips, порядок szi→sdku→cspa, размещение103/101/102. Go all/vet PASS;
реальный before/after same-key reapproval: typed inputs true/true.
Native Vault resolve_runtime_inputs twice: ok10 changed0 failed0/unreachable0.

Дополнительно на101 существующим execution_secret_lease.runtime_secret_inputs_for_operation
проверен реально attached runtime lease нового run, без вывода значений:
SERVICE_APPLY: SERVICE_ADMIN_TOKEN=true, SERVICE_UNSEAL_SHARES=true;
SERVICE_VERIFY: SERVICE_ADMIN_TOKEN=true (unseal по контракту только Apply).
Это подтверждает доставку до контроллера/фильтра операции, не только наличие в UI.
Run продолжает выполняться; observer и окно оставлены открытыми.
Исходники незавершённой phase5 resolver reuse не публиковались в active bundle.

## Phase5 — Verify/Plan/Start reuse, 2026-10-27

Владелец принял реализацию и запретил остановку текущего run и новое ревью.
Изменения остаются в worktree; активный bundle ca1ff310 не заменён.
Private Core artifact хранит resolved snapshot/configuration/connections/PKI
intent/image lock и application rows. Identity проверяет фактическую closure
документов (включая revision-excluded inputs), ownership context и immutable
runtime. Атомарная замена одного файла на project ID; protocol lock сериализует
первое разрешение. Runtime secrets и mutable target observations не кешируются.
Unsupported external Jinja inputs используют fresh resolve и не публикуют base.

Проверка реального протокола выявила и закрыла три ошибки прототипа:
runtime evidence не передавалась DESCRIBE/Plan; cache hit терял application rows
из Ansible facts; prepared images нельзя отключить task var поверх extra_vars.
Теперь desired_only action строит чистую базу, enrichment выполняется отдельно,
а image DESCRIBE получает private rows явно. Фильтр новых DTO/Go precedence
не добавлялся. Start сохраняет авторитетную пересборку и сравнение плана.

RED OS node102, source workspace273828ab: focused Core regression123 PASS,
включая native семь независимых Ansible calls, unknown-version miss,
corruption rejection, concurrent atomic writes, изменение источника между
load/store и external lookup fresh fallback. Real protocol2 PASS: отдельные
readonly snapshot и descriptor requests удаляют свой staging, DESCRIBE/Plan
используют shared base; повторная авторитетная сборка даёт равный plan;
selection/preparation mutation и stale digest отклоняются. Fresh-vs-reused
golden comparison также PASS в финальном прогоне protocol2 (44,818с).
Go test ./... и go vet ./... PASS; App80 и полный frontend321 (27 файлов)
PASS, typecheck/lint PASS. Три временные source-only QA-копии на102 удалены
штатным qa-sync cleanup; действующие runtime/bundle/run не затронуты.

Восстановление просмотра текущего запуска: CURRENT теперь содержит run ID;
существующий GetInstallationRun восстанавливает display-only сохранённый Plan.
React предлагает «Открыть выполнение» без нового Approve/Start. Actual Wails
recovery.exe34124 подключён к тому же installer-c14d36d0; события/27 действий/
процент видны, окно оставлено открытым. Vault Apply/Verify SUCCESS; на последнем
наблюдении Kafka Apply SUCCESS, Verify RUNNING,14/27 (51%).

Acceptance boundary: phase5 пока не опубликована в runtime bundle. Реальные
React/Wails Verify→Plan→Start с обновлённым Core и равный benchmark ещё не
проведены; текущая установка использует предыдущую оптимизацию. PASS здесь
означает перечисленные тесты, не полный deployment acceptance или замер экономии.

## Kafka health-only Verify — owner-authorized correction, 2026-10-27

Исходный Verify в текущем installer-c14d36d0 завершён SUCCESS:
10:27:37–10:35:17 МСК,7мин40с,285 TASK_STARTED/814 событий. Общий main роли
продолжал выполнять подготовку и проверки Apply; TLS resolve вызывался11 раз.

По запросу владельца main теперь направляет Verify в отдельный verify_entry,
а прежний вход установки сохранён в apply.yml. Verify использует существующие
project_runtime/normalize_member для единых endpoint/unit identities, но не
проходит проверки установки, владения, коллизий, конфигурации, пакетов и
артефактов. Сохраняются active/MainPID, listeners, реальные TLS-handshake с
проверкой CA и hostname/IP, аутентифицированный CLI кворума и регистрации
unfenced brokers, HTTPS /subjects каждого локального Schema Registry.

TLS-проекция вычисляется один раз на локальный экземпляр и сохраняется только
в facts текущего Verify. CLI повторно использует эту проекцию; Apply всегда
выполняет штатный resolve независимо от оставшихся facts. При SCRAM два
health CLI используют одно рассчитанное admin-соединение. Без SCRAM кворум
проверяется на одном детерминированно выбранном контроллере, а не на каждом.
Runtime credentials читаются существующим run_cli_command, temporary config
удаляется в always. Межзапускного кеша или новой credential persistence нет.

QA выполняется из source-only workspace на102, без изменения установленных
сервисов. Новый native fixture вызывает фактический main роли, настоящий
OpenSSL и HTTPS API; systemd/Kafka CLI имеют явные синтетические ответы.
Проверяются повтор changed=0, один TLS resolve при трёх listeners, runtime
SCRAM credential plumbing/no-log, inactive node, недоверенный CA, неправильная
TLS identity, неверный кворум, отсутствующий broker, Schema Registry503.
Это не проверка реального SCRAM authentication сервером Kafka.
Полный service/native и affected repair regression58 PASS (233,849с);
дополнительный native тест единого выбора контроллера при отличающемся локальном
участнике1 PASS (3,128с). Итого59 уникальных тестов. Восемь новых native
health-сценариев PASS; положительный Verify повторён с changed=0 и одним TLS
resolve на три listeners. Syntax-check standalone Apply/Verify2 PASS.
Исходники проверены в workspace f348e1ec на102. Новая версия Verify не
публиковалась в bundle и не запускалась против рабочего Kafka-кластера;
реальный трёхузловой benchmark новой версии остаётся pending.
Текущий run/active bundle не менялись, ревью по указанию владельца не вызывается.

## HAProxy partial hook optimization — 2026-10-27

Владелец разрешил оптимизацию hook с обязательным сохранением haproxy -c,
без остановки текущего run и без ревью. В этом run HAProxy-часть Vault Apply
заняла около2:20, ClickHouse Apply около5:10 при одинаковых106 TASK_STARTED.
Копирование прежних backend на node1:24,875с против45,665с; четырёх базовых
конфигов:7,982с против18,601с. Разница не сводится к одной команде: заметна
общая стоимость task dispatch на загруженной Execution Node101 (1CPU).
Исторический CPU-профиль этих интервалов не собран; load22 измерен позднее.

Одиночный infrastructure integrate.yml и общий пакетный apply-source.yml
теперь используют partial_prepare → activate → partial_reload через штатный
tasks_from. Settings/scope/projection рассчитываются один раз перед prepare;
activate/reload не входят повторно в общий main/lifecycle, package/PKI gate.
Разделение подготовки и активации на всех участвующих хостах сохранено.
Полный lifecycle обычной роли остаётся доступным; standard start использует
тот же общий partial_reload task.

По последующему запросу владельца cp заменён двумя штатными copy с
remote_src:true: каталог conf.d рекурсивно одним вызовом и основной конфиг
отдельно. Затем find/file оставляют только рассчитанный сохраняемый состав
кандидата. Имена берутся из существующей доказанной inventory/third-party find;
выбранные source fragments создаются существующими templates. Используется
mode:preserve. Нет command/shell, rsync, Docker или нового Python helper для
копирования. Активная публикация по-прежнему затрагивает
только выбранные backend и frontend через штатный idempotent copy.
Проверка полного кандидата haproxy -c до activation и активного графа после
публикации, digest equality и archive/recovery proof не удалялись.

RED OS102: первоначально HAProxy33/Core45 PASS; после замены cp на native copy
финальный isolated root-owned workspace6d33f115: HAProxy35 и affected Core45,
итого80 PASS (66,529с), syntax-check hook/ClickHouse Apply2 PASS. Native сценарий
использует настоящий haproxy -c,40 соседних backend и сторонний filename с
пробелом; проверяет сохранение соседних файлов, точный набор имён кандидата,
повтор changed=0, отказ невалидного кандидата до публикации и неизменность
активных файлов. Отдельный native состав проверяет удаление выбранного backend,
невыбранного подкаталога и ссылки только из кандидата, сохранность источника и
повтор changed=0. Старый partial fixture приведён к реальному порядку: template
выбранного source выполняется после копирования сохраняемого состава.
Рабочие службы стенда не изменялись. Runtime bundle не обновлялся; реальный
hook benchmark и новая bundle/Wails acceptance остаются pending.

## Kafka Apply — serial TLS/task optimization, 2026-10-27

Владелец разрешил пункты1/3/4 анализа, исключив параллелизм. Последующими
указаниями полностью удалены повторный describe политики _schemas и
kafka-broker-api-versions перед Schema Registry. Текущий run/bundle не меняются.

Подготовка resolve/stat/copy/PEM экземпляра выделена в prepare_member_tls и
вызывается один раз перед циклом listeners. listener_tls_settings меняет только
параметры listeners по готовым путям. validate_ssl_listener остаётся совместимым
прямым wrapper. Порядок member.yml, bootstrap/finalization и перезапусков прежний.
Списки копируемых PKI-файлов выбираются по формату до loop, без PKCS12-итераций
в PEM-режиме. Нет межзапускного cache, новых credentials или публичных контрактов.
Для структуры этого стенда: broker material preparation9→3, общий PEM13→7,
TLS resolve16→10. Это расчёт количества вызовов по структуре, не замер нового run.

Каждый участник читает _schemas один раз и проверяет существующие параметры.
Отсутствующий топик создаётся прежним выбранным брокером. Для missing non-seed
или verify-only возвращается SCHEMA_REGISTRY_TOPIC_REQUIRED без дополнительных
сетевых чтений; создание с ошибкой по-прежнему останавливает Apply. Повторного
describe после создания нет по явному решению владельца. Schema Registry API
readiness и отдельный Kafka Verify сохраняются.

RED OS102 workspace e7709a99: focused35 PASS, полный Kafka/repair61 PASS,
Apply syntax PASS. Native one-materialization test проверяет три listeners,
PEM и explicit PKCS12, одинаковые пути, client.auth, повтор changed=0 и no-log.
Topic test доказывает describe+create на seed, один describe/changed=0 при
повторе, один describe и отказ на missing/incompatible non-seed.
Четыре реальных JVM PEM/PKCS12 теста PASS (231,865с), итого65 уникальных тестов.
Старые qa_pem_tls фикстуры согласованы с ранее принятой health-only Verify:
сверка server.properties не возвращается в Verify; material custody проверяется
прямым helper, health/TLS/API — существующим native health fixture. Пустой
account-custody fixture использует явный synthetic CLI вместо живого кластера.

По новому явному запросу владельца выполнен один FULL DIFF independent review,
scope зафиксирован десятью SHA256 в runtime review manifest. Предыдущий запрет
ревью снят только для этого явно запрошенного шага. APPROVE_WITH_CHANGES,
blockers0. KAS-N01 (nonblocking rotation flag coverage) закрыт расширенным native
тестом: same-path certificate/key rotation даёт pki_changed=true, следующий
повтор false/changed=0; тест PASS42,185с. Production scope после ревью не менялась,
повторное ревью не вызывалось. Другие dirty изменения не включены в scope.
См. service-runtime-optimization-review.md для hashes/вердикта и ограничений.
QA workspace e7709a99 удалён штатным qa-sync cleanup; новый bundle/реальный
updated-source Apply/benchmark не выполнялись. Текущий run продолжает77%
resource/provider preparation на исходном bundle.

## Общая подготовка ресурсов и провайдеров: serial optimization

Закрытый baseline applications:prepare11:16:02–12:05:22МСК =49:20;
1547 started tasks. Owner approved current scope; PG/Redis/Vault excluded.
Implemented: raw defaults include once per library/host (semantic templating still
per placement); parent stat observations reused only in reset read-only preflight,
manual role fresh; Kafka aggregate selected-provider jobs, response parsed once;
ClickHouse existing template lookup batched in controller action, accounts does
not render unused table SQL. No new parallelism/public contract/persistence.

QA fixed Jinja whitespace causing list to become a string before loop. Native
Kafka fixture collection discovery and Templar DataLoader corrected. Frozen scope
and independent review recorded in service-runtime-optimization-review.md;
blockers0; PREP-N01 HA SQL coverage closed by native test-only addition.
RED OS focused-final83 cases OK (82PASS/1 explicit SSH-target skip), syntax PASS;
HA/standalone SQL equality PASS; provider selected-library create/repeat with both
skipInfraVerify values PASS. Exact baseline/current applicationLibraries projection,
status and safe findings equality PASS for2 libraries.

Legacy resolver suite is not reported PASS: baseline replay of5 failures on prior
resolver shows same missing adminCredential/runtime reference and database
parameters schema failures. Corrected synthetic fixture9 PASS533.047s (only missing admin reference added
in temporary test input). Final native48:34PASS/14FAIL,1067.995s; Kafka12,
project-resolution1 and ClickHouse7 all PASS, including real standalone/3server
HA resource/account/repeat/Verify. Full legacy regression is not PASS:12 tests
lack required Kafka admin reference, one additionally uses schema-invalid empty
PostgreSQL parameters, one synthetic topic CLI rejects aggregated topic selector
(also fails with prior Kafka tasks). Baseline witnesses5 resolver+1topic and
exact two-library application projection/status/findings equality PASS.
Logs under runtime QA preparation-*.log. Three QA workspaces cleaned by qa-sync.
No PG/Redis/Vault source diff. No commit, bundle publication, new installation or
stopping active installer-c14d36d0 performed for this scope.

## Подготовка библиотек и универсального раннера: второй serial scope

Owner requested a checkpoint commit before further optimization:629dbb9d89f745c91827802f5e822791c957f601
(75files, previous Verify/Plan/Start, Kafka/HAProxy/provider preparation and
related evidence). Worktree was clean after the commit; no master integration or
push requested. New work uses that exact commit as its review baseline.

SZI current-run baseline12:05:32–12:54:15МСК=48:43;1158 task starts,
1684 target results (545 skipped). Approximately31:17 in1077 short-task
intervals. HAProxy12:13 already addressed in committed earlier scope. Runner
7:13 includes about3:05 actual scripts; the rest is staging/orchestration.

New implementation: placements selected once per library/per instance; empty
phase/scope skips the handler include. package_script transient paths/environment
are ordinary role vars instead of host facts. Script/secret inputs/batch JSON use
one standard copy loop, with an explicit internal loop_var. Stale cleanup, fresh
copy, modes, source failure behavior, always cleanup, argv/timeouts/safe error and
changed protocol retained. Provider target context is lazy task vars. Runner
remains generic; no product/container knowledge, cache or new contract.
Runner task entries14→11; no end-to-end timing saving claimed before a new bundle.

QA on RED OS current167317ca source: focused30 OK/1 root-only skip (88.138s),
root ownership witness separately PASS15.180s. After naming the internal loop,
final native12 OK/1 root-only skip86.662s and exact final-source root ownership
witness PASS. Added outer default-item caller compatibility and actual ordered
selection fixture (two libraries/three instances; external container actions are
observations, production task selection/vars/ordering preserved) PASS5.071s.
Terminal/post_install/progress46 PASS7.250s; standalone Apply syntax PASS.
Distinct affected cases78 covered including the skipped root case separately.
No new legacy resolver broad run; prior baseline failures remain recorded above.
Safe synthetic argv/secret/batch tests prove no expansion/leak and failure cleanup;
repeat changed=0, neighbor source replacement, skipped-provider integrations and
Execution Node callback without target contact remain covered.

FULL DIFF independent review requested for final6file scope:
script-dispatch-review-scope.json SHA256
5a0cbf92338290e0c418f4e21e31802853f54d6791950a8265955757c70e4ca6.
Final independent FULL DIFF APPROVE/blocking0, SDR-N01 test coverage resolved before final verdict; no recheck. Production scope frozen; existing run installer-c14d36d0
continues on old bundle (UI85%/SDKU at observation); no runtime/bundle switch,
PG/Redis/Vault provider edit or new run. Updated-bundle real acceptance/benchmark
remain pending. This new scope is not included in the checkpoint commit.

## Owner follow-up: lightweight per-library completion check

Explicit owner request removes configuration-tree and Vault identity/AppRole/read
checks only at the end of each library. ordered-library now calls the existing
container-state task through verify_container.yml; the identical inspect/image/
labels/Running/healthcheck predicate is shared with verify.yml. No duplicate
container predicate, optional flag, new schema or provider rule introduced.
Startup and standalone Verify keep their existing directory/Vault policy.

Current-source RED OS28 tests PASS83.711s: library completion succeeds with missing
configuration destinations and agentTemplate=true without Vault credentials;
unhealthy container still fails; normal Verify, activation and multi-host
Compose recovery, ordered selection and progress remain covered. No new run or
bundle activation; source-only acceptance. This owner-authorized follow-up is
outside the preceding frozen script-runner FULL DIFF manifest; no additional
review invoked or previous verdict claimed for the added boundary policy.

## Owner policy: omit global library Verify from new installation plans

Explicit owner request removes the entire repeated global library Verify pass:
resolver/snapshot/provider projections, container/config checks and endpoint
HAProxy/DNS/HTTPS checks. Keep readiness at startup, per-library container health
and endpoint publication/probes inside Apply. Emit only APPLICATION_LIBRARIES_APPLY
and optional post_install depending on applications:apply. The standalone Verify
playbook and saved Apply/Verify manifests remain supported; existing in-flight
plans/bundles are immutable. Existing schema versions already allow Apply-only
operations and do not require new fields, versions, flags or Go/UI domain logic.
Use one shared admission suffix check for Apply-only and exact legacy Apply/Verify;
keep infrastructure coverage, scope matching and terminal failure/cancel gates.

Affected native/unit/schema/controller tests125 OK/2 explicit native gates;
the two real action/controller gates independently enabled:2PASS6.089s. Controller
fixture fails if the global Verify playbook is invoked. UI32PASS shows only Core-
declared actions while retaining old-plan display. New tests cover FULL_PROJECT,
libraries-only with/without SkipInfraVerify, legacy manifests with/without terminal,
invalid order/duplicates/scope and terminal dependency. Updated-bundle real Wails
acceptance/benchmark pending. Independent FULL DIFF APPROVE/blocking0, no findings, for changed admission;
9file source manifest c673a9d7497d298fd1dc2ca4e2c1bca507c762b61b22c7b9ac55556b41cb5984.

Final9file identity confirmed; native source QA and UI fixture checks above completed. Current installer-c14d36d0 observed88%/CSPA, old immutable plan retained. Temporary f43070fb QA workspace cleaned with qa-sync; bundle/runtime acceptance pending.

## Clean optimized restart and pre-plan service directories — 2026-10-27

Owner-authorized restart: cancelled installer-c14d36d0500efb8a3f5a3ac61bb0040c
at13:46:38MSK. Its execution unit was inactive before cleanup. Reused the prior
full-stack cleanup scripts, adapted to platform-automation and /data/docker.
Removed project containers/images, service packages/accounts/configuration/data,
application directories, PKI and Installer runtime workspaces on101/102/103;
retained OS prerequisites and the established automation identity. Final proof
reported empty=true, remaining=[], processes=[] on all three nodes. Subsequent
Execution Node preparation intentionally recreated the runtime on101.

Bundle service-runtime-optimization-20261027-02, digest
sha256:80e67f1c1375cec5c7b810e912d6194898b16c73e5cc839f13bc719e9e143bb6,
built from07391701, validated and published through the standard publisher.
Fresh QA project project-runtime02 retains project-b46aa3f5f57a495f and packages1.0.1;
placements remain szi103, sdku101, cspa102. No library/infrastructure skips.

Fixed a presentation request invalidating the trusted SSH binding when an edit
session was active: reject that request before transport revalidation. React
does not fetch a saved projection while commands are pending and retries after
save/discard. No path calculation was added to Go/React. Desktop/executionnode
Go tests and frontend App80 tests, lint/typecheck PASS; the new regression proves
that a draft preview leaves the binding and READY context intact.

Real React/Wails34126 with Execution Node101: saved revision
sha256:909643ebfd4a8c447350529f900fcefb9a60be06f67bbcdfbb80eb5314aea25e.
Before any plan (plan count0), all five textboxes displayed the Core values:
ClickHouse /data/qa-clickhouse; Kafka /data/qa-kafka-structure;
PostgreSQL /data/qa-postgresql/postgres; Redis /data/qa-redis;
Vault /data/qa-vault-consumer. Screenshots and exact textbox assertions captured.
All18 active application account password sources were saved and verified as
managed/generated; no manual application account password input is permitted by
the automation. Library provider/shared runtime credentials keep their existing
contract. Full run preparation continues through the real React/Wails handlers;
Start/terminal acceptance is not implied by these checks.

Local evidence under .runtime/qa/service-runtime-optimization/results/:
runtime02-empty-proof.json, runtime-binding.json, runtime03-data-root-preview.json,
runtime03-data-root-ui.json and runtime03-install-ui-evidence.json. Browser remains
open; runtime preparation and UI use the fresh bundle.

Owner amendment: Keycloak PostgreSQL password must remain a runtime input.
The first executable plan plan-6e31e9af1007f6042d2ba78b was not approved or started:
bootstrap still requires keycloak-postgres-password. The UI reset removed the
credential override and exposed an inherited templated reference rejected by
schema validation; an explicit runtime_secret_ref was therefore authored in the
ordinary QA project group_vars and reread through React/Wails. No schema rule was
weakened. Fresh Project Verify PASS and projection assertions confirm17 generated
passwords plus exactly one Keycloak runtime password. The latter uses the same
keycloak-postgres-password reference as bootstrap. A fresh plan is required;
the rejected plan is not reused. Evidence: runtime03-keycloak-refresh.log.

Owner-approved navigation gate: fetch the existing Core service projection as
soon as the selected Execution Node is ready, independently of the Services
page. Services, Applications and Installation links and their content stay
blocked until the observation matches the saved revision, root, runtime and node.
Save invalidates it; successful observations are reused across page navigation.
Stale/error responses do not unlock navigation. Retry uses the existing node
check; waiting/errors appear within the existing node status and header badge.
The intermediate separate projection panel/button was removed per owner request.
No new Core operation, contract, desired-state store or bundle change was needed.

Final App suite82 PASS, lint/typecheck PASS; existing desktop/executionnode Go
tests/vet PASS. Tests cover pending/failed/stale responses, explicit retry through
node check, valid release, reuse, node/runtime changes and no implicit Plan.
Real React/Wails34126, project-runtime02, confirms disabled=true for all three
links before Core, disabled=false after Core, all five data paths rendered before
Project Verify or any plan (plansBeforeCoreCheck0). Password policy17 generated
plus Keycloak runtime source confirmed; all runtime inputs set through real UI
before fresh full plan. Full-project plan preparation continues without skips.
Evidence: runtime04-install-ui-evidence.json, runtime04-full-run.log,
core-gate-final-tests.log, core-gate-final-ready.png under the same local QA root.

Full run started through actual React Plan/Approve/Start: plan-89ad688c2a57a43c77d3bdc1,
revision sha256:65d6eb13ef0520f9c71418e14f27f773116db36554d805e6e71e4c665297e2e5,
run installer-aa746f3e5b21e169cdc2665485a07078, confirmed STARTED15:32:16MSK.
Runtime80e67f1c, FULL_PROJECT,23 actions, no skips; szi103/sdku101/cspa102;
CURRENT_RUN_BOOTSTRAP for application Vault access. Keycloak runtime password
was entered through its actual inline application secret field;17 other account
passwords remain generated. Plan approval reported no missing inputs.

Owner follow-up: show pending Start as "Запускается выполнение…" until Core
returns. Implemented a client-only pending flag for header/plan status/button;
typecheck/lint PASS, affected App/InstallationPage/presentation120 tests PASS and
the pending display function directly asserted. This edit triggered React HMR
after Start and reset local UI observation. The Wails process stayed43388 and
the remote systemd execution unit remained active; no run restart/cancel occurred.
Recovered via real Servers SSH confirmation -> Inspect previous run (FOUND,
same run/revision) -> Attach. Reconnected UI and original observer show RUNNING;
verify:qa-dns-client SUCCESS observed15:37:29MSK. Screenshot runtime04-reconnected.png.
Owner instruction: no more UI edits/reloads until terminal. Terminal acceptance
and benchmark remain pending; the browser stays open.

Terminal observation: FAILED16:31:49MSK,65%, same installer-aa746f3e5b21e169cdc2665485a07078.
Docker Apply failed on101/102/103 at the subordinate UID/GID allocation assertion
(DOCKER_SUBID_ALLOCATION_REQUIRED). The current /etc/subuid and /etc/subgid had
only the admin entry. Root cause is the adapted QA cleanup, not the password
check: it retained platform-automation but removed its subordinate ID entries.
The existing-account Docker role correctly refused to proceed without them.

Original entries survived in /etc/subuid- and /etc/subgid- on all three nodes:
platform-automation:589824:65536. Restored those exact non-overlapping allocations
using usermod and verified both files on every node. Corrected the adapted QA
cleanup to preserve subordinate IDs of the retained automation account while
still removing its Docker-specific LXC network configuration. Account passwords,
UID/GID and SSH authorization were not changed. No new run or Docker Apply was
started. Evidence: runtime04-terminal-diagnosis.json and terminal observer log;
the failed run/window remain available. Full installation acceptance is FAILED,
not PASS; PostgreSQL and application-library installation were not reached.

Owner authorized another complete cleanup/repeat. Fresh runtime05 inventory and
manifests used; old cleanup receipts were not reused. Removed20 service RPMs per
node and all inventoried service accounts/configuration/data. Fresh proof on
101/102/103: empty=true, remaining/processes/serviceAccounts=[], exact automation
subuid/subgid589824:65536 preserved on every host. Removed an empty recreated
Ansible tmp directory on101 and repeated proof successfully. Corrected both the
cleanup and its generator to retain subordinate IDs of the retained identity.
Prior terminal reference resolved through actual UI before removing remote state.

New full React/Wails preparation uses the same immutable80e67f1c bundle,
project-runtime02/packages1.0.1, szi103/sdku101/cspa102,17 generated application
passwords and Keycloak runtime input. Execution Node101 is being prepared again
after removal of its runtime. Prior screenshots copied to runtime04-specific
names before reuse of the original generic screenshot destinations. New evidence:
runtime05-inventory.json, runtime05-cleanup-all.log, runtime05-empty-proof.json,
runtime05-install-ui-evidence.json and runtime05-full-run.log. No new UI source
changes or runtime bundle rebuild in this repeat.

Owner follow-up accepted in sequence only: service installation checkboxes,
analogous to library skips, are to be implemented after this repeat run. All
services remain selected now. Existing deploymentOrder is full-set ordering,
not a subset selector; a service skip must preserve provider connections and
consumer resource/account provisioning. Implementation has not begun.

Repeat launched through actual React/Wails34126: installer-c16023470ddfd063c5cba83edda390aa,
STARTED17:02:56MSK, RUNNING. Fresh authoritative plan-89ad688c2a57a43c77d3bdc1
(same deterministic plan identity for unchanged desired inputs), revision65d6eb13,
runtime80e67f1c. Full infrastructure and all three libraries selected, no skips;
17 generated account passwords and Keycloak runtime input confirmed. Actual
pending Start UI assertion PASS: pending text present, old approved-ready text
absent, repeated Start disabled. This run has had no UI source changes/reloads
since Start. Standalone observer continues recording events and terminal result;
full-install acceptance remains pending.

Repeat terminal: installer-c16023470ddfd063c5cba83edda390aa FAILED17:07:27MSK.
PKI and BIND Apply completed; BIND Verify failed on node2 at the authoritative
SOA query for evoscada.internal (17:07:26). Read-only journal evidence: secondary
started17:07:10, initial primary192.168.56.101:53 connection was refused; first
successful transfer occurred17:08:03, serial1, after Verify/run failure. Current
exact SOA queries on all three nodes return NOERROR/qr aa/serial1. This proves a
cold-start readiness race, not an invalid zone configuration or missing subids.
Verify has no wait/retry on that query; Apply must not finish before secondary
zone readiness. No source correction, service restart, UI change or new run was
performed for this diagnosis. Evidence: runtime05-terminal-diagnosis.json and
canonical remote events.jsonl/result.json. Full installation remains FAILED.

Owner said stop and redirected work to the installation error: service-skip
planning stopped. Follow-up automation is PAUSED (confirmed from its configuration).

Owner authorized the BIND readiness correction, new bundle and full repeat.
Added one standard included command/until loop at the end of BIND start, after
service start/reload and base record reconciliation, for every local resolved
zone/participant. Require dig rc0, NOERROR and authoritative qr aa. Defaults:
platform_bind_readiness_retries60, delay2s; query time2s/tries1. Ready zones finish
on the first attempt with changed=false. Verify is byte-for-byte unchanged.

Final RED OS102 QA from fresh source0f0ee0b4d6e745f3975d8be7711ca71e:
three tests PASS, including two native cases with real BIND primary/secondary in
a private network namespace. Delayed primary forces retries before successful
zone transfer; immediate repeat has attempts1/changed0; an active secondary with
an unavailable primary fails after a bounded wait. Live stand DNS was untouched.
Fixture initially lacked an explicit second loopback address/source binding;
corrected the isolated fixture and reran successfully (31.801s). DNS regressions20
PASS, Apply/Verify syntax2 PASS. Production change is confined to the BIND role;
no Core protocol, plan, Go or UI source change was introduced for this fix.

Built on trusted node102 from current source and approved bundle02 runtime input.
Bundle service-runtime-optimization-20261027-03, digest
sha256:ae72b11a2b2cd01abb6ffc7b484993743c31024f365d39a2ae249f2febcdaad8,
verified and published by the standard CLI; approved image identities unchanged.
Transferred new source payload and reused byte-identical approved runtime files
in the local QA stage; complete bundle integrity validation passed before publish.
Production BIND component hashes match the edited worktree. Tests/docs remain
excluded from distribution by the existing builder policy.

Fresh project-runtime03 copied from runtime02 preserving desired configuration,
project ID, packages1.0.1,17 generated passwords and Keycloak runtime input; imported
bundle03 and confirmed rebind UPDATED through actual React/Wails34126. Repreparing
Execution Node101 for the new immutable runtime; new full plan/Start still pending.
No cleanup of installed BIND/PKI was requested or performed in this retry.
Evidence: bind-readiness-tests.json, runtime03-build.log, runtime03-published.json,
runtime06-install-ui-evidence.json/runtime06-full-run.log in the existing QA root.

Actual React/Wails full repeat STARTED17:56:37MSK:
installer-e8ab7170a9f9202572d0c6bf433ee95a / plan-4ba95795a0b4f7018aa8ce16,
bundle03 ae72b11a. All infrastructure and szi103/sdku101/cspa102 selected,
CURRENT_RUN_BOOTSTRAP,17 generated passwords and Keycloak runtime source retained.
RUNNING; BIND Apply SUCCESS 18:01:03 MSK and Verify SUCCESS 18:01:14 MSK. Authoritative SOA readiness SUCCESS on node1/node2/node3 (events1229–1231); subsequent DNS client Apply/Verify SUCCESS, progress19%. Full terminal result pending. No UI reload
or source edit after Start. Temporary source0f0ee0b4d6e745f3975d8be7711ca71e cleaned
with qa-sync after repairing ownership of its root-created native-test pycache;
approved build input and verified bundle retained on trusted node102.
