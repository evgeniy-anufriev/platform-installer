# SERVICE-INSTALL — последовательная приёмка установки

Current status and authorization: [CURRENT_STATE](../../../CURRENT_STATE.md).
Earlier recorded status and test runs are retained in [evidence](evidence/service-install-initial-evidence.md).
The plan below retains the cumulative project and per-service scenarios.

## Общий накопительный QA project

Вся последовательность использует один контролируемый Git-ignored
Installer-managed project под `.runtime/qa/service-install-cumulative-project`.
SERVICE-INSTALL-01 создаёт его пустым из проверенного immutable bundle и
сохраняет Keepalived через публичный Go/UI edit lifecycle. Каждый следующий
milestone открывает эту же canonical revision, добавляет только тестируемый
service через typed EditSession → Review → local Save и доказывает, что ранее
принятые services сохранены. Нельзя подменять это отдельным fixture или
создавать новый project для отдельного сервиса.

Если root уже существует перед первым milestone, создание останавливается:
его замена требует отдельной scoped cleanup-проверки. После SERVICE-INSTALL-09
SERVICE-INSTALL-10 строит один fresh DeploymentPlan именно из накопленного
project, а не из повторно собранного аналога. Runtime-only project и рабочие
артефакты очищаются только после финальной фиксации evidence и безопасного
scoped teardown.

## Общие условия каждого milestone

See [the dedicated document](../../agent-procedures/service-acceptance.md#общие-условия-каждого-milestone).

## SERVICE-INSTALL-01 — Keepalived

Один service package `keepalived`: выделенный host-scoped deployment на
выбранных трёх QA hosts. После очистки только принадлежащих ему старых
ресурсов проверить план, apply/verify, выбранного VIP owner, адреса и
read-only состояние всех участников; повторная установка `changed=0`.
Проверить, что VIP и VRID не конфликтуют с соседними QA deployments.

Historical results: [evidence](evidence/service-install-initial-evidence.md#service-install-01--keepalived).

## SERVICE-INSTALL-02 — BIND

Один service package `bind`: primary и secondary на выбранных hosts.
Предварительно удалить только старое BIND состояние тестового deployment.
Проверить authoritative записи, передачу зоны secondary, serial/fingerprint,
apply/verify и repeat `changed=0`. Не очищать зоны или файлы других BIND
deployments. Если fixture включает ранее установленный Keepalived, он должен
остаться работоспособным.

Для Installer lifecycle BIND serial/fingerprint state является
machine-owned Execution Node state, ключуется стабильным `projectIdentity` и
не может жить в одноразовой копии проекта run workspace. Первый apply создаёт
его до target-role mutation; новый fresh repeat обязан прочитать тот же state
и вернуть реальный `changed=0`, а не маскировать запись через `changed_when`.

Historical results: [evidence](evidence/service-install-initial-evidence.md#service-install-02--bind).

## SERVICE-INSTALL-03 — dns-client

Один service package `dns-client` с `dnsServerRef` на прошедший проверку BIND
deployment. Удалить старый resolver drop-in тестового deployment при
доказанном владении. Проверить маршрут split DNS, разрешение нужных записей
через BIND и сохранение unrelated DNS; apply/verify и repeat `changed=0`.
При невозможности различить владельцев resolver state не удалять его
без отдельного согласованного механизма.

Historical results: [evidence](evidence/service-install-initial-evidence.md#service-install-03--dns-client).

## SERVICE-INSTALL-04 — HAProxy

Один service package `haproxy` с уже проверенными сетевыми/PKI
предпосылками. Удалить только принадлежащую тестовому deployment прежнюю
HAProxy конфигурацию. Проверить candidate/active barriers, HTTPS routing,
TLS hostname validation, фактические backend ответы, apply/verify и repeat
`changed=0`. Проверить, что работа Keepalived, BIND и dns-client не нарушена.

Historical results: [evidence](evidence/service-install-initial-evidence.md#service-install-04--haproxy).

## SERVICE-INSTALL-05 — Kafka, три экземпляра на трёх target hosts

Сначала идентифицировать текущую изолированную QA Kafka установку UI-02E
`kafka@kafka-ui02e-{1,2,3}.service` на одном target и её точные data/config
paths. Удалить только этот deployment через ограниченный clean-install /
cleanup путь после проверки его guard и acknowledgement. Не применять
`reset_kafka_host.yml`: он удаляет все Kafka units и runtime с выбранного
хоста. После очистки проверить отсутствие только старых QA ресурсов и
неизменность других Kafka deployments.

Установить один новый Kafka deployment: три logical members, по одному на
каждом из трёх distinct target hosts. До запуска подтвердить точные адреса
узлов, отсутствие конфликтов портов, путей и node IDs, а также PKI/TLS SAN.
Проверить три active units, quorum, TLS handshake, apply/verify и repeat
`changed=0` на всех трёх hosts. Старый UI-02E one-target PASS не засчитывать
как доказательство этой новой топологии.

## SERVICE-INSTALL-06 — PostgreSQL / pg_auto_failover

Один `postgresql` deployment в каталожном режиме `pg_auto_failover`: один
monitor и два database member на трёх distinct hosts. После scoped cleanup
старой тестовой установки проверить monitor membership, два database узла,
TLS/PKI и подключение клиента к согласованному endpoint, apply/verify и
repeat `changed=0`. Проверить отсутствие регрессии уже установленных
сетевых сервисов и Kafka. Старые database directories удалять только после
точной проверки deployment ownership и отсутствия нужных данных.

Приёмка завершена 2026-09-24: monitor node1 (`192.168.56.101`), database
members node2 (`192.168.56.102`) и node3 (`192.168.56.103`). Первый lifecycle
`installer-45943379628ebee4a28716d85b571916` завершился `SUCCEEDED` за 17m45s
с 65 изменениями; repeat `installer-4fcc0cd5afc8689509aea2e2a49935e6`
завершился `SUCCEEDED` за 17m9s с `changed=0`. В обоих циклах PKI apply,
PostgreSQL apply и verify прошли успешно.

## SERVICE-INSTALL-07 — Redis и Redis Sentinel с TLS

Service package поддерживает два режима. `redis/standalone`: один Redis member
на одном host, TLS-only client port, без Sentinel. `redis/sentinel-ha`: три
парных members (Redis и Sentinel) на одном host по умолчанию, с раздельными
портами, units и persistent state; размещение на трёх hosts тоже обязательно.
TLS-only транспорт
для Redis, репликации, Sentinel→Redis и Sentinel↔Sentinel. Реализовать оба
режима через самостоятельный Ansible, Core, Go и Wails/React. По решению
владельца один canonical project может содержать не более одного Redis
deployment: standalone проверяется в отдельном изолированном QA project, а
HA становится единственным Redis deployment накопительного проекта.
Для каждого
режима провести два свежих полных lifecycle run: `SUCCEEDED`, apply/verify
PASS, repeat `changed=0`; для HA это требуется отдельно в 3/1 и 3/3.
Однохостовый quorum не означает отказоустойчивости к потере сервера.
HA дополнительно проверяет три Redis units, три
Sentinel units, один active master, две replicas, Sentinel quorum и сохранение
текущего master после failover. Старый Redis QA state очищать только после
доказательства принадлежности конкретному deployment.
Архитектура: [SERVICE-INSTALL-07](../redis/service-install-07-redis-sentinel-architecture.md).

## SERVICE-INSTALL-09 — ClickHouse

Архитектура и условия приёмки: [SERVICE-INSTALL-09](../clickhouse/service-install-09-clickhouse-architecture.md).
Один ClickHouse server без Keeper для 1/1; три пары server+Keeper для 3/1
и 3/3. HTTPS endpoint обязателен для этого QA этапа. Установка и повтор
проводятся через общий standalone/Core/Go/React-Wails gate из этого документа.

## SERVICE-INSTALL-10 — все девять сервисов из одного плана

После PASS milestones 01–09 подготовить один canonical project,
содержащий все девять services: Keepalived, BIND, dns-client, HAProxy, Kafka,
PostgreSQL `pg_auto_failover`, Redis/Sentinel, Vault и ClickHouse. Зафиксировать placement,
provider/consumer links, VIP, endpoint groups, PKI scopes, secret inputs и
отсутствие конфликтов ресурсов. До запуска удалить только прежнее состояние
этого интеграционного QA проекта, если оно есть и безопасно атрибутировано.

Выполнить один `CreatePlan -> ApprovePlan -> Start` с одним authoritative
DeploymentPlan/ExecutionManifest, а не отдельные Start по сервисам. Core определяет
порядок зависимостей и допустимый параллелизм. Проверить успешные apply и
verify для каждого сервиса, реальные сетевые и TLS интеграции, terminal
`SUCCEEDED` и отсутствие изменений в сторонних deployments. Затем построить
новый план того же проекта и повторить полный запуск: все сервисы
`changed=0`, verify PASS. Сохранить оба run ID, per-service/per-host evidence
и итоговый отчёт; только после этого SERVICE-INSTALL overall можно объявить
DONE.
