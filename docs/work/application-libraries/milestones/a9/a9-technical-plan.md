# A9 — полная приёмка standalone Ansible + Core

Дата: 2026-10-13. Статус: технический план для согласования.
Этот документ не разрешает запуск изменяющего QA и не утверждает PASS.
Текущие разрешения и состояние этапов находятся в CURRENT_STATE.md.

## 1. Цель и границы (Test Scope)

Доказать полный существующий путь A1–A8: native inventory/vars/defaults →
resolve → ресурсы библиотеки → общие секреты → accounts/grants → Vault
KV/policy/AppRole → доставка образа/файлов → Vault Agent → приложение →
подключения → HAProxy/DNS → Verify. Второй путь — тот же desired state через
structured Core planning/execution с инфраструктурным барьером A8.

А9 является приёмкой существующих контрактов, а не новой архитектурой.
Не добавляются scheduler, новые DTO, механизм отката, отдельный селектор
библиотеки, специальные QA-команды в production или второй источник состояния.
Обнаруженные дефекты оформляются отдельно; изменение security/ownership/trust
границы проходит процедуру review и решение владельца.

Go backend и UI не реализуются. Standalone/Core PASS не означает React/Wails
PASS и не закрывает будущие этапы B/C. Probe не доказывает функциональность
коммерческого apigateway. Kafka проверяется по SSL без SASL и ACL.

## 2. Предусловия (Environment Requirements)

Перед изменяющими действиями зафиксировать read-only аудит:

1. Ветка codex/application-libraries, commit и digest текущих исходников;
   source transfer стандартным scripts/qa-sync.ps1 с проверкой равенства.
2. RED OS Execution Node и отдельный trusted acquisition/build node.
   SSH platform-automation, установленный ключ, проверенные host keys,
   IdentitiesOnly=yes, sudo -n. Python/Ansible на Windows не используются.
3. Два Docker placement-хоста: реальные UID пользователя из getent,
   rootless daemon/socket и Compose доступны. Не предполагать UID=1000.
   Отсутствующий socket — prerequisite, а не повод переключиться на root Docker.
4. Текущий ProjectSnapshot full-services: реальные deployment IDs, версии,
   топологии, connection projections, DNS zone, endpoint group, VIP и TLS profile.
   Старые журналы не являются live inventory.
5. PostgreSQL writable master, Redis/Sentinel, ClickHouse и Kafka SSL доступны.
   Все advertised Kafka addresses достижимы с обоих Docker-хостов.
6. Vault через существующий HTTPS endpoint: порт по умолчанию 443,
   доверенная CA и SAN; direct-port fallback — только по существующему контракту.
   Проверить фактические peer addresses и AppRole CIDRs, включая подсеть
   LXC bridge каждого placement после отдельной согласованной корректировки роли.
7. PKCS12 plans соответствуют TLS profile на каждом placement; общий пароль
   storePasswordSecretRef однозначен. Не подменять отсутствующий plan ручным
   копированием чужих хранилищ или отключением проверки TLS.
8. Admin/runtime credentials доступны только через защищённые inputs или
   существующие plaintext bootstrap-файлы Execution Node. Значения не печатать.
9. Проверенный bundle соответствует текущей объединённой версии исходников.
   Bundle11 А8 предшествует последующим merge и сам по себе этого не доказывает.
   Сборка/валидация/публикация — по runtime-bundle procedure, без ручного cache copy.

Недоступность node2/rootless Docker фиксируется до Apply. Восстановление общего
Docker/Vault/PKI выполняется только в отдельно согласованном scope; shared services
не сбрасываются для удобства теста.

## 3. QA desired state и образ

Использовать QA-копию full-services, сохраняя project identity и существующие
infra refs/PKI namespace. Оригинальные пользовательские файлы не менять.
Перед запуском проверить отсутствие конфликтов новых library IDs, principals,
database names, портов и FQDN. Сохранить полный infrastructure endpoint source,
чтобы reconcile не удалил прежние backends/DNS записи.

| Сущность | Состав | Размещение |
| --- | --- | --- |
| sdku | Один slot gateway, общий applicationRef apigateway@QA-version | Docker host1 и host2 |
| cspa | Тот же пакет и slot; другие parameters/resources/bindings | Docker host1 |
| apigateway-sdku | Один логический экземпляр и AppRole | Два локальных Compose запуска |
| apigateway-cspa | Второй логический экземпляр и AppRole | Один локальный Compose запуск |

Итого: две библиотеки, два логических экземпляра, три placements.
Идентичность application + library вычисляет Core. SERVER_ID берётся из
inventory host ID; пользователь не задаёт его повторно в .env.

Пакет приложения содержит defaults с connections/accounts/secret bindings,
Compose template и roles/application_apigateway/templates/agent.hcl.
Library package содержит defaults, общий base Compose template и files/.env.
group_vars задаёт library deployments, infra bindings, ресурсы, понятные
parameters.user/password_ref, overrides портов/endpoint/backend settings.
host_vars задаёт placements. Один библиотечный .env на каждом хосте хранит
пользовательские несекретные значения; общие connections проецируются в base Compose.
Instance-specific credentials доставляет Agent, а не plaintext .env.

Использовать существующий docker/application-connection-probe:
локальный image ID sha256:caa73a170e7bc73ffc6a44a37360163ceb3939f6a986abba3c867094256c0f0d.
До запуска проверить наличие и соответствие approved artifact lock.
Image ID, registry digest и SHA256 Docker archive — разные идентификаторы.
Не объявлять этот image ID registry digest.

Образ доставляется существующим source policy: approved repository либо
проверенный bundle/docker load. Не загружать новый образ из Интернета автоматически.
Сборка нужна только при недоступности согласованного артефакта и отдельном DEV scope.

QA overrides: процесс /usr/bin/connection-probe, HTTP container port 8080;
явный Agent entrypoint /usr/bin/vault agent -config=/opt/vault/agent.hcl;
readonly PKCS12 material и tmpfs /run/probe. Не менять production binary convention.
Kafka connectionRef=CLIENT_SSL задаётся в library defaults для serviceType kafka;
прочие refs выводятся только при однозначном подходящем connection.

Разные database names/principals/secret refs библиотек позволяют проверить
изоляцию на общем provider. Не требуются два полных инфраструктурных стенда.
ClickHouse HA использует существующее ON CLUSTER default.

## 4. Подэтапы выполнения

### A9.1 — подготовка и фиксация scope

Создать safe scope manifest: source identity, project revision, runtime digest,
package refs, deployments, placements, новые ресурсы/порты/FQDN, cleanup ownership.
Зафиксировать baseline DNS/backend records и здоровое состояние общих сервисов.
Проверить accounts/grants и protected runtime inputs без вывода значений.
Target-free validate/snapshot должны завершиться до любых provider mutations.

### A9.2 — focused contract regression

Запустить на RED OS текущие application resolve/runtime/provider/Vault/endpoint,
structured planning и mixed execution suites. Не повторять весь репозиторий.
При повторном использовании результатов A1–A8 указать revision и неизменность
проверяемой границы; старое PASS не выдаётся за новый live run.

### A9.3 — ручной standalone Apply

Запустить существующие application-libraries-apply.yml и затем
application-libraries-verify.yml с manual inventory и защищёнными runtime inputs.
Не использовать Go или Installer для resolve/provider semantics.

Проверяемый порядок:

1. Общие preflight и runtime resolve; все provider prerequisites до mutations.
2. Library resources: databases/owner resources; batch на логическую библиотеку.
3. Library shared secrets, включая существующий PKCS12 store password.
4. Accounts/grants каждого логического application instance; один вызов
   provider hook на instance, без объединения разных instances в общий batch.
5. KV put/patch, policy/AppRole и выдача RoleID; одна identity на logical instance.
6. Материализация библиотечного .env/base Compose и локальных instance files.
7. Образ из утверждённого источника, Compose up, Agent login/render/exec.
8. Готовность placements и общие существующие endpoint hooks.
9. Минимальный Verify и содержательная проверка connections/endpoint.

Не считать роли/УЗ по числу хостов: два placements СДКУ не создают две logical УЗ.

### A9.4 — полный status и endpoints

На всех трёх placements /status возвращает 200 и ok=true для vaultAgent,
pkcs12, pkcs12Client, postgresql, redis, sentinel, clickhouse и kafka.
Проверить все Redis members и Kafka advertised SSL targets из resolved projection.
Kafka успех означает TLS + ApiVersions, не авторизацию или права на topics.

СДКУ и ЦСПА имеют разные FQDN/backends при существующей endpoint group/VIP модели.
Через штатный DNS и HTTPS/443 получить /status=200 с проверкой CA и hostname.
Отдельно подтвердить оба СДКУ backend targets и их readiness: один успешный
ответ балансировщика не доказывает здоровье второго placement.
Сравнить сохранность прежних DNS/backend records и endpoint общих сервисов.

Обычный /status/Verify не выполняет QA writes. PROBE_REDIS_KEY_PREFIX выключен.
Проверки разрешённых/запрещённых операций при необходимости идут отдельным
ограниченным сценарием только на собственных QA keys/tables/databases.

### A9.5 — repeat и изоляция

Повторить Apply/Verify без изменения desired state или inputs.
Требуется changed=0 и отсутствие лишнего container recreate, reset паролей,
новых KV versions, DDL и HAProxy/BIND reload. Сравнивать безопасные metadata,
не читать/сохранять passwords, RoleID или токены.

Проверить разные УЗ/DB/ACL/Vault paths, запрет чтения чужой библиотеки,
разные автоматически проецируемые app IDs и SERVER_ID двух placements СДКУ.
Shared-secret доступ остаётся только к явно объявленным paths/fields.

### A9.6 — targeted failure/retry

В отдельной revision испортить только QA command ЦСПА на отсутствующий binary.
Не отключать общий Vault, Redis или HAProxy. Apply должен завершиться ошибкой,
не выдавая успешный Verify; СДКУ и общие сервисы продолжают работать.
Исправить command новой revision, построить свежий план и выполнить retry.
После восстановления все status/endpoints 200, повтор changed=0.

Использовать существующий полный scope; не придумывать CLI selector библиотеки.
Проверять, что неизменённая СДКУ не пересоздаётся даже если её jobs снова вызваны.
Частичные результаты provider mutation фиксируются честно: автоматический
транзакционный rollback всей библиотеки не обещается.

### A9.7 — structured Core и общий план

Из того же native desired state выполнить существующий structured путь:
snapshot → validate → authoritative Build → trust/typed runtime lease →
Start → events → terminal result. Без Go adapter и без обхода approval binding.
Зафиксировать план, revision, runtime digest, run ID и полную последовательность.

Общий mixed план: selected infrastructure Apply/Verify, затем applications.
Все необходимые infrastructure Verify завершаются до первой library mutation.
Этот сценарий действительно вызывает infra операции: нельзя обещать, что он
не трогает инфраструктуру, либо вручную убрать SERVICE_APPLY из manifest.
До Start проверить отсутствие несогласованных изменений общих services/PKI.
Если delta требует переустановки общих сервисов — остановиться и согласовать scope.

Для existing Vault использовать защищённый RUNTIME_INPUT.
CURRENT_RUN_BOOTSTRAP уже имеет отдельную A8 live evidence. Повторять её только
при изменении затронутой bootstrap границы либо непригодности прошлой evidence;
использовать собственный изолированный Vault unit/data/ports, без reset shared Vault.
Infra-only/no-library и cancel/failure barrier проверить focused contract suites;
ранее доказанные live cases не повторять автоматически без нового основания.

### A9.8 — cleanup и итог

Удалить только test-owned containers/configs и новые library-owned resources
согласно заранее зафиксированному ownership. Перед удалением DB проверить,
что в них нет чужих данных. Общие accounts, infra units, PKI, images и bootstrap
audit не удалять. Endpoint rollback выполняется существующим reconcile полного
desired source с сохранением infrastructure records.

Очистить private inputs, временные source/fixture workspaces стандартным helper,
временные API tokens и локальные защищённые файлы. Канонические audit records
и безопасную evidence сохранить. Не создавать отдельный cleanup framework.

## 5. Матрица (Required / Negative / Contract Scenarios)

| ID | Сценарий | Ожидаемый результат |
| --- | --- | --- |
| A9-Q01 | Snapshot двух libraries / трёх placements | Детерминированные IDs, bindings, plans; нет target contact |
| A9-Q02 | Image delivery на оба Docker hosts | Approved image identity, existing source policy |
| A9-Q03 | Native Apply полного пути | Library resources раньше accounts/containers; success |
| A9-Q04 | /status каждого placement | 3 × HTTP200, все восемь checks успешны |
| A9-Q05 | DNS + TLS endpoint двух libraries | Разные backends, оба SDKU targets здоровы, CA/SAN valid |
| A9-Q06 | Повтор без изменений | changed=0, нет реального recreate/KV/DDL/reload |
| A9-Q07 | Межбиблиотечная изоляция | Чужие DB/ACL/Vault paths недоступны; shared paths разрешены явно |
| A9-Q08 | CSPA failure → новая revision → retry | Ошибка не маскируется; SDKU сохранена; полное восстановление |
| A9-Q09 | Structured mixed execution | Один authoritative run; infra Verify barrier до libraries |
| A9-Q10 | Stale revision/runtime/scope/lease | Existing contract reject, без target mutation |
| A9-Q11 | Отсутствующие service refs / no-secret app | Optional hooks отсутствуют; dangling required binding rejected |
| A9-Q12 | Shared-only secrets без managed accounts | Agent/policy/shared reads работают, accounts hooks отсутствуют |
| A9-Q13 | Multi-listener ambiguity | Явный Kafka CLIENT_SSL; неоднозначные connection refs rejected |
| A9-Q14 | Secret hygiene | Нет plaintext credentials в проекте/.env/events/logs/evidence |
| A9-Q15 | Cleanup + сохранность baseline | Только owned QA delta удалена; shared records/services сохранены |

Q10–13 преимущественно используют существующие target-free/native fixtures.
Пустой override accounts={} не считается способом удалить inherited defaults:
использовать уже поддержанный no-secret/shared-only package fixture.

## 6. Скорость и риски (Regression Risks)

Главный принцип всего A: минимальное число действий и reuse существующих hooks.
Проверить job cardinality: resources на library, accounts/grants/AppRole на
logical instance, локальные файлы/Compose/inspect на placement.
Не добавлять N×M calls, повторное discovery per account или отдельные проверки
Compose/file hashes в обычный Verify. Readiness retries остаются ограниченными.

Записать длительность обычных Apply/Verify и число реально вызванных hooks из
events. Новые benchmark, sweep 1/10/30 контейнеров и SLA не вводятся.
ClickHouse late ON CLUSTER retry риск принят владельцем; pending/queue locks
не добавляются. TTL/CAS/failover chaos не повторяется без новых изменений.

Основные риски: потеря endpoint records при неполном source; общий PKI namespace;
неоднозначный PKCS12 plan; rootless peer/CIDR; неверный Kafka listener;
ложное changed=0; смешение логического instance и host placement.

## 7. Evidence и критерии завершения

В milestones/a9/evidence/a9-test-journal.md сохраняются scope, source/runtime
identity, revision/run IDs, команды без секретов, recap и terminal verdicts.
Дополнительные safe артефакты: scope manifest, test summary, event record,
redacted status checks и cleanup record. Журнал создаётся с реальными результатами,
не заполняется предполагаемыми PASS заранее.

А9 завершён, когда Q01–15 имеют проверяемую evidence, обязательные prerequisites
закрыты, оба standalone/structured пути работают, три placements и два внешних
endpoint дают полный status200, repeat changed0, isolation/retry/cleanup доказаны.
Неисполненные случаи имеют NOT RUN/BLOCKED с точной причиной.

## 8. Что здесь не проверяется (Not Testable Locally)

На Windows нельзя подтвердить Core/Ansible, rootless routing и реальные providers.
Mocked frontend и прямой Go harness не заменяют будущий React/Wails acceptance.
Нет claims по Kafka ACL/SASL, функциональности коммерческого apigateway, ALT или
новым версиям providers. Принятие этого плана не начинает Go/UI этапы.

Документ — bounded QA plan по существующим контрактам: самостоятельного нового
architecture FULL review не требует. Security-изменение LXC CIDRs рассматривается
отдельным diff gate и не получает разрешения или PASS от этого QA плана.
