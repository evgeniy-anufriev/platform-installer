# SERVICE-INSTALL — последовательная приёмка установки

Статус: SERVICE-INSTALL-01 DONE; SERVICE-INSTALL-02 DONE; SERVICE-INSTALL-03 DONE;
SERVICE-INSTALL-04 DONE; SERVICE-INSTALL-05 DONE; SERVICE-INSTALL-06 DONE.
SERVICE-INSTALL-07 Redis standalone и Sentinel HA; SERVICE-INSTALL-08 — Vault
(1/1, 3/1, 3/3), SI08-A DONE, SI08-B NOT STARTED;
SERVICE-INSTALL-09 — общий план для восьми сервисов. Исторический UI-02E
тест Kafka (три экземпляра на одном target) остаётся завершённым и не заменяет
SERVICE-INSTALL-05 (три target).

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
его замена требует отдельной scoped cleanup-проверки. После SERVICE-INSTALL-08
SERVICE-INSTALL-09 строит один fresh DeploymentPlan именно из накопленного
project, а не из повторно собранного аналога. Runtime-only project и рабочие
артефакты очищаются только после финальной фиксации evidence и безопасного
scoped teardown.

## Общие условия каждого milestone

- Зафиксировать конкретный QA project, deployment ID, Execution Node, target
  hosts, активный digest runtime release и источник артефактов. Убедиться, что
  план построен из текущей сохранённой ревизии, одобрен и запущен по
  `CreatePlan -> ApprovePlan -> Start`.
- Перед установкой составить read-only карту существующих установок этого
  сервиса на выбранных target hosts: deployments, systemd units, порты,
  процессы, конфиги, каталоги данных, PKI-материал и зависимости. Снять
  исходное состояние соседних QA deployments.
- Старую установку выбранного сервиса, принадлежащую именно тестовому
  deployment, удалить до новой установки. Применять только подтверждённый
  service/deployment-scoped способ; не удалять данные, unit или пакет по
  одному лишь совпадению имени сервиса. Если ресурс общий, принадлежность
  не доказана или безопасного узкого удаления нет, остановить этот milestone
  и согласовать конкретный способ очистки. Не выполнять host-wide reset при
  наличии других deployments этого сервиса на хосте.
- Использовать изолированные идентификаторы и свободные адреса, порты и
  каталоги. Зависимые сервисы из предыдущих milestones могут использоваться
  как существующие предпосылки; новый milestone проверяет установку одного
  выбранного сервиса. Учитывать, что общий Core plan охватывает весь проект:
  зависимости и уже установленные сервисы могут также проходить idempotent
  apply/verify. Успех нельзя приписывать выбранному сервису лишь по общему
  `SUCCEEDED` — проверить его действия и фактическое состояние отдельно.
- Первая установка: авторитетный terminal `SUCCEEDED`, apply/verify PASS,
  фактическая работоспособность. Второй запуск: новый свежий план,
  `SUCCEEDED`, repeat apply `changed=0`, verify PASS. Зафиксировать оба run ID,
  длительность, per-host recap, relevant task events и итоговое состояние.
- Проверить до/после, что сторонние QA deployments не изменились. Секреты,
  внутренние пути к ним и приватные payloads не выводить в проект, план,
  события, mirror, Result и отчёт. Временные QA workspaces очищать после
  фиксации безопасных свидетельств. Дефект продукта устранять отдельно,
  затем повторять затронутый milestone; не засчитывать прямой Ansible запуск
  вместо полного Installer lifecycle.
- Если публичная Wails UI может воспроизвести соответствующий edit flow, её
  acceptance обязательна наряду с Go/Core evidence. UI не заменяет
  protocol-mediated execution; она доказывает лишь транспорт typed intent в
  тот же canonical Save lifecycle.

## SERVICE-INSTALL-01 — Keepalived

Один service package `keepalived`: выделенный host-scoped deployment на
выбранных трёх QA hosts. После очистки только принадлежащих ему старых
ресурсов проверить план, apply/verify, выбранного VIP owner, адреса и
read-only состояние всех участников; повторная установка `changed=0`.
Проверить, что VIP и VRID не конфликтуют с соседними QA deployments.

### Evidence (2026-09-23)

- Cumulative project: `.runtime/qa/service-install-cumulative-project`; its
  immutable runtime lock and active Execution Node runtime were both rebound to
  `sha256:6d85afb53c6994f2f1b152e29b39a329ed35a9af7ed3e9c802be0e888993dca0`.
- The read-only preflight found no active Keepalived unit, test VIP or
  deployment-scoped configuration on node1, node2 or node3.
- Fresh lifecycle runs `installer-5bd04f686b8b5f5f3f936e91a95c6130`
  (3m07s, `changed=6`) and `installer-0f8a485c5b62ff59edd481e3a02bdb0b`
  (2m50s, repeat `changed=0`) both completed `SUCCEEDED`; each recorded
  Keepalived apply and verify success.
- `keepalived.service` is active on all three nodes. The isolated VRID is 61;
  the test VIP `192.168.56.121/32` is currently owned by node2, while node1
  and node3 correctly remain non-owners. The generated configuration declares
  priorities 150, 120 and 100 respectively.
- The authoritative plan contained only the isolated Keepalived deployment;
  no unrelated service deployment was launched.

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

### Evidence (2026-09-23)

- Immutable QA runtime `sha256:5c3188765226fbae6c7de563a1545e613b5970c1a3cd229d48cc21bec763e4e3`
  was activated on the READY Execution Node and bound to the cumulative project
  before the lifecycle runs.
- The Execution Node owns
  `projects/project-64791354ab381f68/generated/platform-state.yml`; it is a
  regular `0600` file keyed by stable project identity, outside archived
  project copies and ephemeral run workspaces.
- Fresh run `installer-05b9e466943edcb5036297d81d418f04` completed
  `SUCCEEDED` in 5m37s with BIND apply/verify success and one real change:
  initial generated-state publication.
- Fresh repeat `installer-3f66123f69d0f83d4e5b6b6c3ae009c6` completed
  `SUCCEEDED` in 5m24s. It loaded and schema-validated the same persistent
  state before reconciliation; BIND apply/verify succeeded and the complete
  plan recorded `changed=0`.
- Keepalived remained part of the cumulative plan and its apply/verify also
  succeeded without changes. No separate project or direct Ansible substitute
  was used.

## SERVICE-INSTALL-03 — dns-client

Один service package `dns-client` с `dnsServerRef` на прошедший проверку BIND
deployment. Удалить старый resolver drop-in тестового deployment при
доказанном владении. Проверить маршрут split DNS, разрешение нужных записей
через BIND и сохранение unrelated DNS; apply/verify и repeat `changed=0`.
При невозможности различить владельцев resolver state не удалять его
без отдельного согласованного механизма.

### Evidence (2026-09-23)

- The dns-client catalog descriptor declares the trusted closed
  `SERVICE_DEPLOYMENT` reference kind for `dnsServerRef`; the cumulative
  project therefore added `service-install-03-dns-client` through typed Go
  EditSession → Review → local Save, referencing only the accepted
  `service-install-02-bind` deployment.
- The initial lifecycle failure was a YAML parse defect in the NetworkManager
  branch of the read-only verify task. It was corrected, syntax-checked on
  RED OS and delivered in immutable runtime
  `sha256:4fd2c1c1f9b876cde9ee7b2b8ae0918b35ecd984aedfa783426e53b578eda0e2`.
  The cumulative project was rebound to that exact runtime and catalog lock
  pair by the QA-only resumable CAS promotion helper.
- Fresh runs `installer-6264b96222b402c24a7d77929bc99d92` (7m12s) and
  `installer-1f0bfd7a8b86592037c15c215bb10a07` (7m02s) both completed
  `SUCCEEDED`. Each recorded DNS-client apply and verify success; both complete
  cumulative plans recorded `changed=0`.
- On node1, node2 and node3, `systemd-resolved.service`, `named.service` and
  `keepalived.service` remained active. The managed resolver drop-in contains
  the three authoritative DNS addresses and route-only `~scada.local`; the
  effective resolver state matches it. No unrelated resolver ownership was
  overwritten.

## SERVICE-INSTALL-04 — HAProxy

Один service package `haproxy` с уже проверенными сетевыми/PKI
предпосылками. Удалить только принадлежащую тестовому deployment прежнюю
HAProxy конфигурацию. Проверить candidate/active barriers, HTTPS routing,
TLS hostname validation, фактические backend ответы, apply/verify и repeat
`changed=0`. Проверить, что работа Keepalived, BIND и dns-client не нарушена.

### Evidence (2026-09-23)

- Cumulative project added `service-install-04-haproxy` solely through the
  typed Go EditSession → Review → local Save lifecycle. It uses the existing
  three target hosts, isolated priorities 150/120/100, and the managed TLS
  profile `service-install-haproxy-tls`; no inventory or host-vars file was
  hand-authored.
- The immutable runtime
  `sha256:ecb5342cf4a1000d72c0a792bf56f48569fd198447700e98941170485401df7f`
  binds Core-derived PKI materialization plans into the digest-protected
  private ExecutionManifest and controller-only runtime projection, and makes
  the HAProxy role project its one local deployment's configured TLS profile.
  Neither change adds PKI plans, SecretRefs or passwords to the portable
  project, public plan, events or UI.
- Fresh Go-mediated `CreatePlan → ApprovePlan → Start` runs
  `installer-12b577ff3cd57e17a6a69e61560b88a7` (14m04s) and
  `installer-3dfe62bccd8a15dcbb9893b268a41fd2` (15m44s) both reached terminal
  `SUCCEEDED`. Each recorded HAProxy apply and verify success; the repeat
  complete cumulative lifecycle recorded real `changed=0`.
- `haproxy.service` is `active` on node1, node2 and node3. Keepalived, BIND
  and dns-client stayed part of both cumulative plans and completed without
  regression. `TASK_EVENT_STREAM_TRUNCATED` late in verify was
  observability-only and did not alter either terminal result.
- RED OS Core suite passed (284 tests, 4 expected skips), HAProxy syntax check
  passed, and fixture catalog plus service configuration schemas remained
  reproducible.

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
Архитектура: [SERVICE-INSTALL-07](service-install-07-redis-sentinel-architecture.md).

## SERVICE-INSTALL-09 — все восемь сервисов из одного плана

После PASS milestones 01–08 подготовить один canonical project,
содержащий все восемь services: Keepalived, BIND, dns-client, HAProxy, Kafka,
PostgreSQL `pg_auto_failover`, Redis/Sentinel и Vault. Зафиксировать placement,
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
