# A5 — Redis, Sentinel, ClickHouse и Kafka SSL

Дата: 2026-10-11. Ветка: `codex/application-libraries`; исходная ревизия
`054668d36fdaab14d9012dba8f45337bbd5cbd04`. Статус: технический план для
реализация разрешена владельцем 2026-10-11. A1–A4 standalone завершены;
Go/UI остаются вне scope.

## 1. Результат и границы

Один экземпляр приложения получает через уже работающий Vault Agent credentials
для PostgreSQL, Redis, Sentinel и ClickHouse, открывает PKCS12 stores и проверяет
подключения на `/status`. PostgreSQL/Vault остаются существующими A3/A4 hooks.
Redis и ClickHouse получают provider-owned hooks, одинаковые для всех приложений.

Разделить работу на три последовательные части:

| Часть | Результат |
| --- | --- |
| A5.1 | Redis ACL accounts, отдельные Sentinel accounts, permissions, сохранение ACL и authenticated probes |
| A5.2 | ClickHouse library databases, SQL accounts/grants, HTTPS probes |
| A5.3 | Реальный Kafka protocol probe на явно выбранном SSL listener без аутентификации |

Раннее решение владельца для текущего QA: Kafka SSL без УЗ/ACL. Поэтому A5.3
не создаёт фиктивный Kafka account, не пишет Kafka password в Vault и не считает
TLS соединение пользовательской аутентификацией. Полный SASL/principal/ACL hook,
упомянутый в общем roadmap, остаётся отдельным расширением A5.3-security с
отдельным планом/решением владельца. Указание Kafka account при неподдерживаемой
security capability блокирует выполнение; anonymous fallback отсутствует.

В A5 не входят создание таблиц приложений, миграции схем, password rotation,
удаление accounts/resources, Redis Cluster, Kafka SASL/ACL/topic provisioning,
публикация application endpoint (A6), общий installation plan (A8), Go и UI.
Доставка образа и library `.env` остаются A2, Agent/AppRole/KV — A4.

## 2. Что уже есть и что необходимо расширить

| Место | Факт исходного кода | Изменение A5 |
| --- | --- | --- |
| Core `application_providers.py` | Принимает только PostgreSQL resources/accounts | Добавить Redis/Sentinel и ClickHouse jobs в существующую проекцию |
| Core `application_libraries.py::resolve_connection` | Kafka требует selector; Redis с несколькими members блокируется; CH HTTPS работает с ограничениями allocation | Использовать одну общую service-owned member/listener projection для infrastructure и приложений |
| `application-libraries-provider-stage.yml` | Явные library/instance barriers, PostgreSQL/Vault | Добавить явные Redis/CH role includes внутри этих фаз |
| Redis `acl_files.yml` | Existing ACL должен содержать одну строку `default` | Сохранять остальные валидные users; проверять `default` отдельно |
| Redis `acl_runtime.yml` | `ACL USERS` должен быть ровно `default` | Проверять обязательный `default` и его текущую политику, разрешать дополнительные accounts |
| Redis `normalize.yml` | Расчёт member slots, Redis/Sentinel ports и owned paths | Вынести только этот существующий расчёт в переиспользуемую service projection, без второй формулы в Core |
| ClickHouse `users.xml.j2` | `default` имеет `access_management=1` и password verifier | Оставить XML admin user; создавать app users средствами SQL access storage |
| ClickHouse `server.xml.j2` и tests | Private `access/`, HA cluster `default`, TLS native transport | Использовать существующий SQL storage и native client; не создавать второй users XML |
| `docker/application-connection-probe/main.go` | Redis/Sentinel делают AUTH/PING; CH SELECT 1; Kafka ApiVersions | Добавить содержательные permissions/Sentinel discovery probes; текущие проверки недостаточны для grants |

Канонические источники: inventory, `group_vars`, `host_vars`, role defaults,
service manifests, library/application packages. Native provider jobs — derived
runtime; отдельный desired-state store, Go resolver или provider framework не нужен.

## 3. Нагрузка и число действий

Сохранить общий принцип A1–A9:

- Discovery один раз на provider deployment в invocation.
- Library resources — один logical hook на библиотеку и задействованный provider.
- Accounts/grants — один logical hook на экземпляр и задействованный provider.
- Несколько Docker placements не создают дополнительные logical accounts/hooks.
- Физические Redis members требуют ACL fan-out на каждый обслуживающий member.
  В ClickHouse HA user/grants распространяются одним `ON CLUSTER default` batch,
  затем результат проверяется на всех server members; это не новые instance jobs.
- Не объединять accounts разных экземпляров в общий deployment-wide batch.
- Не делать task на command/key pattern/SQL privilege/Vault binding.
- Использовать пакетное чтение actual state и один ограниченный mutation batch
  внутри scope/member. Verify только читает и подключается.
- На чистом repeat нет ACL SETUSER/ACL SAVE, DDL, password resets, KV writes,
  AppRole изменения, image delivery и container restart без фактической причины.

Для Redis библиотечной resource mutation нет: key namespace — правило доступа,
не создание БД/ключей. Для Sentinel нет отдельного «создания master» в app hook.
Для CH databases создаются library hook до всех instance accounts.
Отсутствующий connection/binding означает skip optional hook; если существующий
binding указан ошибочно или объявлен account без connection — BLOCK. Отсутствие
accounts не отменяет явно объявленные library resources и shared-secret bindings.

Фиксировать task/module/provider call counts и обычное elapsed time first Apply,
repeat и Verify. Дополнительные benchmark-серии и сравнение batching вариантов
отменены владельцем. Нет обещания общего числового SLA без наблюдения.

## 4. Defaults приложения и пользовательские overrides

Ниже дополнения к существующему `platform_application_definition` в
`roles/application_apigateway/defaults/main.yml`; остальные A2/A4 поля сохраняются.
Это проектируемые A5 defaults, а не уже поддержанный runtime пример.

```yaml
platform_application_definition:
  name: apigateway
  version: "1.0.0"
  connections:
    redis: {library_binding: redis, purpose: client, protocol: tcp}
    sentinel: {library_binding: sentinel, purpose: sentinel, protocol: tcp}
    clickhouse: {library_binding: analytics, purpose: client, protocol: https}
    kafka: {library_binding: messaging, purpose: client, protocol: tcp}
    # postgres/vault сохраняются из A3/A4.
  defaults:
    parameters:
      redis:
        user: "{{ application_instance_id }}"
        password_ref: "{{ application_instance_id }}-redis-password"
      sentinel:
        user: "{{ application_instance_id }}"
        password_ref: "{{ application_instance_id }}-sentinel-password"
      clickhouse:
        user: "{{ application_instance_id }}"
        password_ref: "{{ application_instance_id }}-clickhouse-password"
    accounts:
      redis:
        mode: managed
        credentials:
          username:
            source: {kind: literal, value: "{{ application_parameters.redis.user }}"}
          password:
            source: {kind: runtime_secret_ref, ref: "{{ application_parameters.redis.password_ref }}"}
        grants:
          commands: [ping, get, set, del]
          keys: ["{{ application_library_id }}:*"]
          channels: []
      sentinel:
        mode: managed
        credentials:
          username:
            source: {kind: literal, value: "{{ application_parameters.sentinel.user }}"}
          password:
            source: {kind: runtime_secret_ref, ref: "{{ application_parameters.sentinel.password_ref }}"}
        grants:
          commands: [ping, "sentinel|get-master-addr-by-name"]
      clickhouse:
        mode: managed
        databaseRef: application-analytics
        credentials:
          username:
            source: {kind: literal, value: "{{ application_parameters.clickhouse.user }}"}
          password:
            source: {kind: runtime_secret_ref, ref: "{{ application_parameters.clickhouse.password_ref }}"}
        grants:
          - {databaseRef: application-analytics, tables: [events], privileges: [SELECT, INSERT]}
    provisioner:
      # type/auth/approle и PKI shared bindings — существующие A4 defaults.
      secret_bindings:
        REDIS_PASSWORD: {source: {account: redis, field: password}}
        SENTINEL_PASSWORD: {source: {account: sentinel, field: password}}
        CLICKHOUSE_PASSWORD: {source: {account: clickhouse, field: password}}
```

`account_id` совпадает с connection alias, как в A3. Redis и Sentinel — два
accounts на разных listener targets одного Redis deployment; одинаковое username
между ними допустимо, credentials и права независимы. В A5 один serviceType
`redis` не должен автоматически применять один global `connectionRef` ко всем
purposes: client и sentinel уже однозначно выбираются по `purpose`. Неподходящий
явный selector — ошибка, не silent skip.

```yaml
# Фрагмент inventory/group_vars/all/platform-installer.yml.
# Пример для Redis sentinel-ha; прочие platform_desired_state поля сохраняются.
platform_desired_state:
  applicationLibraryDeployments:
    sdku:
      libraryRef: sdku@1.0.0
      runtimeRef: docker-apps
      vault_ref: {binding: secrets}
      bindings:
        redis: {deploymentRef: redis-sdku}
        sentinel: {deploymentRef: redis-sdku}
        analytics: {deploymentRef: clickhouse-sdku}
        messaging: {deploymentRef: kafka-shared}
        secrets: {deploymentRef: vault-shared}
        # database/pki — прежние A3/A4 bindings.
      resources:
        application-analytics:
          kind: clickhouse.database
          binding: analytics
          mode: managed
          parameters: {name: sdku}
      applications:
        apigateway:
          overrides:
            parameters:
              redis: {user: test-user, password_ref: my-redis-password}
              sentinel: {user: test-user, password_ref: my-sentinel-password}
              clickhouse: {user: test-user, password_ref: my-clickhouse-password}
```

Application package/version уже задаётся library definition; override alias
`apigateway` соответствует её объявлению, нового поля `applicationRef` в
deployment нет. В полном примере сохранить schema-defined placement/runtime host
selection и PostgreSQL resources. Идентичность `apigateway-sdku` выводится Core,
host ID берётся из inventory/host_vars. Тестовый `test-user` показывается как
пользовательский override; default остаётся уникальным instance username.

Sentinel connection выбирает только members с ролью `sentinel`; Redis data
connection — members с ролью `redis`. Пример выше требует `sentinel-ha`.
В standalone библиотека не задаёт optional binding `sentinel`: из effective
scope согласованно исключаются connection, соответствующий account и его Agent
secret bindings; desired defaults не переписываются. Если binding присутствует,
но Sentinel targets отсутствуют, это BLOCK. Account без объявленного connection
alias тоже BLOCK. Добавить проверки mixed roles и отсутствующих optional bindings.

`connectionDefaults.kafka.connectionRef` хранится в library defaults на уровне
serviceType, как принято в A1. Значение — имя client listener из deployment
effective settings, например `EXTERNAL_SSL`; оно должно быть явно задано. В
library deployment пользователь меняет только deployment binding при переносе
на другой provider. Не добавлять per-deployment selector map.

Пароль передаётся через существующую private reference→file карту A3/A4;
plaintext не появляется в `group_vars`, `.env`, Compose или desired project.
`source.kind=vault_ref` сохраняет existing-secret семантику A4: прочитать нужное
поле из Vault, передать его provider через invocation-only file и удалить в
`always`. AppRole identity и связывание Vault field с Agent env остаются A4.
`mode: existing` означает только authentication/grants verification, без создания,
смены пароля, записи ownership или выдачи прав.

## 5. Общие contract изменения и порядок выполнения

Расширить существующую `project_providers`, сохранив её статус/findings и
libraryJobs/instanceJobs. Добавить provider discriminator к существующим jobs и
строгие service-specific validators. Не заводить вторую модель deployment или
новую dispatch registry. Для трёх service types достаточно явных role includes.

Объявить `service.redis.account`, `service.redis.sentinel.account`,
`service.clickhouse.database`, `service.clickhouse.account` в service manifests
только вместе с рабочими provider roles. Пересобрать catalog существующим
генератором на Execution Node; не редактировать generated catalog вручную.

Сделать shared member projection Redis/CH доступной target-free resolver и ролям
инфраструктуры. Она получает effective settings/members и возвращает реальные
ports/paths/roles. Не копировать slot arithmetic в application Core. Для CH
client HTTPS и internal admin native connection — две проекции одного member;
admin transport не подменяет пользовательский `connectionRef`.

Расширить existing credential map общим alias, сохранив backward-compatible
`platform_postgresql_application_credential_files`; не сбрасывать extra-vars
через set_fact. Runtime credentials всех providers проходят A4 guard и cleanup.

Полный standalone Apply:

1. Обычный A1/A2 resolve один раз; schema, refs, collisions, capabilities и
   connection selectors проверяются до изменения target.
2. A4 читает existing Vault source credentials в private invocation custody.
3. Provider discovery/preflight один раз на deployment: реальные members,
   TLS/admin access, storage/ownership, существующие accounts/resources.
4. Все library resource hooks: PostgreSQL A3 и ClickHouse A5.2; Redis — skip.
5. A4 library hook публикует shared PKI secrets.
6. На каждый logical instance: PostgreSQL, Redis/Sentinel, ClickHouse account
   hooks проверяют/создают accounts и применяют явно заявленные grants.
7. Только после успешных provider hooks A4 публикует instance credentials,
   policy/AppRole и RoleID. Не публиковать в Vault кандидат, который не прошёл
   provider login. До failure допустимы уже успешные provider mutations; общей
   транзакции между сервисами нет, automatic rollback/delete нет.
8. A2/A4 доставляют config, Agent, PKCS12 и RoleID на Docker placements;
   библиотечный `.env` содержит несекретные пользовательские значения, base
   Compose — общие projections подключений. Agent запускает executable приложения.
9. Один `docker inspect` на экземпляр; затем содержательные provider probes,
   предпочтительно одним `/status` request на размещение. Endpoint — только A6.
10. `always` удаляет invocation-derived credential/temp files; события содержат
    только безопасные IDs/status/error codes и изменённые scopes.

Отдельные existing provider Apply/Verify playbooks должны оставаться пригодны
для обычного manual inventory. Target-free resolve не открывает сетевых соединений.

## 6. A5.1 — Redis и Sentinel

### 6.1. Accounts и права

Redis ACL grants ограничены списками commands, key patterns и channels. Provider
формирует native tokens из валидированных полей; arbitrary ACL text не принимается.
Начальный default: deny all commands, затем явно перечисленные permissions;
key/channel selectors только объявленные. Не выдавать `+@all`, `~*`, `&*`, ACL,
CONFIG, FLUSHALL или Sentinel administration по умолчанию. AUTH/HELLO/CLIENT
подкоманды добавлять только если они нужны конкретному client profile и проверены.
Redis ACL не изолирует ключи по номеру logical DB: library namespace задаётся
prefix patterns; SELECT DB не выдаётся как обещание безопасности.

Sentinel account разрешает discovery (`get-master-addr-by-name`) и нужные
connection commands; monitor/peer credentials инфраструктуры остаются отдельными.
App hook не меняет `sentinel auth-user/auth-pass` или `sentinel-user/pass`.

### 6.2. Ownership без takeover

Redis ACL не имеет A3-подобного COMMENT. Детерминированное username само по себе
не доказывает ownership. Минимальный witness — приватный machine-owned companion
file рядом с существующим member ACL: `application-accounts.json`, owner service
user, mode 0600. Он хранит только scope marker, listener kind и username; никаких
passwords/verifiers/grants/желаемых settings. Желаемое состояние остаётся vars.

Существующий Redis `.platform-redis-mode` сохраняется без изменения его формата.
Witness не является cache фактов и не восстанавливает ACL самостоятельно.
Он не защищает от внешнего администратора, который удалил и заново создал
одноимённый Redis user: без native immutable account ID такой гарантии нет.
Existing account без совпадающего witness в `managed` — BLOCK; `existing`
может проверять такой account без присвоения. `default`/admin/peer users запрещены
для managed application accounts. Конкурирующие mutations сериализуются native
member-level file lock, а не новым scheduler. После успешной проверки create
записывается witness атомарной заменой. Если процесс упал между create и witness,
retry видит немаркированный account и останавливается для ручного разрешения;
не присваивает его автоматически.

Один per-member lock используют все затронутые infrastructure и application
ACL writers, включая ACL-file replacement и ACL SAVE. Timeout ограничен role
default (начально 15 секунд); actual ACL и witness повторно читаются под lock.
Check → mutation → persistence → witness publication выполняются внутри одного
bounded invocation, lock не передаётся между отдельными Ansible processes/tasks.
Witness/lock paths требуют owned regular file, no symlink и owned private parent;
проверять открытый descriptor, использовать no-follow open и атомарную публикацию.
Для CH такой же member lock охватывает check → mutation → witness publication
library/instance hooks. Эти правила требуют concurrent app/app и infra/app tests;
новый scheduler или transaction framework не нужен.

### 6.3. Применение и persistence

Один provider-specific execution на `(instance, member, listener)` читает actual
ACL, проверяет witness/password/permissions, применяет только delta и делает
`ACL SAVE` лишь после изменений. Проверяет ответы каждой команды; pipeline сам
по себе не означает транзакцию. При необходимости safe compare/batch стандартный
`redis-cli` дополняется одним небольшим service-owned RESP/TLS helper на Python
stdlib; общий Redis client/framework и новый pip dependency не вводятся.
Конкретный выбор CLI/helper фиксируется A5.1 подготовкой по pinned Redis версии.

Дополнительные permissions аддитивны, как принято в A3. Сужение/удаление
grants не реализуется как silent revoke: explicit change требует отдельной
операции/согласования; новое unexpected широкое право вызывает finding.
Пароль owned existing account сначала проверяется AUTH; несовпадение — BLOCK,
automatic reset/rotation не выполняется. При создании передавать SHA256 verifier
native `#hash` по private channel, не plaintext через process argv.

`existing` Redis accounts поддерживает только канонический profile, который
проверяет этот hook: включённый user с ожидаемым паролем, положительные
индивидуальные команды без категорий ACL, и только запрошенные key/channel
patterns. Более широкие права (например `+@all` или `~*`) и selectors завершаются
`REDIS_APPLICATION_GRANTS_DRIFT`, даже если запрошенная операция тоже разрешена.
Категории и glob-права не интерпретируются универсально; расширение профиля
требует отдельного решения.

В Sentinel HA локальные ACL необходимо применить ко всем Redis members и ко
всем Sentinel members, включая replicas. Redis replication не заменяет ACL
fan-out. Возобновление после частичного результата обрабатывает каждый member
по его actual state/witness; общий PASS только когда все требуемые members PASS.

Infra Apply/Verify исправить узко: сохранять все корректные дополнительные ACL
users, exact текущий `default` и его hash/policy, выполнять прежние path/owner/mode
guards. Не переписывать ACL целиком с одной строкой. Повтор инфраструктуры,
service restart и последующая установка второй библиотеки сохраняют accounts
первой. Не отключать существующий `default` и не выполнять `ACL SAVE` в Verify.

## 7. A5.2 — ClickHouse

Library `clickhouse.database` resource поддерживает managed/existing database
name, без raw SQL/engine overrides. Managed account ссылается на databaseRef
своей библиотеки. Создание таблиц/миграции не входит в ресурсный hook; grants на
конкретные таблицы требуют их наличия. В initial QA подготовить fixture tables
отдельно. Database-wide `*` допустимо лишь как явный opt-in grant.

Initial privileges: `SELECT`, `INSERT` на объявленные database/table scopes.
Не выдавать ALL, GRANT OPTION, access management, SYSTEM или global `*.*`.
Provider quote identifiers/values сам; application manifest не содержит SQL.
Existing mode только подтверждает права. Managed grants аддитивны; removal и
rotation не выполняются автоматически.

Использовать уже установленный `clickhouse-client` для native TLS
`--multiquery`; HTTP API не объявлять batch-SQL transport. HTTPS остаётся
application connection. Один resource execution на библиотеку/member и один
account execution на экземпляр/member; reads и mutation SQL группируются внутри
соответствующего scope. Admin credential приходит защищённым runtime файлом;
эфемерный client config 0600 создаётся/удаляется в одном bounded invocation.
Passwords, hashes и SQL bodies не попадают в argv, Ansible output или events;
проверить redaction server query/error logs на pinned версии до native QA.

ClickHouse SQL users живут в существующем private access storage; user XML и
`default` остаются инфраструктуре. Для foreign account/database защиты использовать
тот же минимальный private witness принцип в service-owned directory (с привязкой
user ID из `system.users`, где доступен), не считать `IF NOT EXISTS` ownership.
Потеря witness/UUID mismatch — BLOCK; не создавать role только ради marker.

Standalone — один server, SQL без `ON CLUSTER`. По прямому уточнению владельца
2026-10-11 в `raft-ha` создание пользователей и выдача grants выполняются через
`ON CLUSTER default`: один batch на logical instance с одного server member.
Повторная рассылка тех же user/grant DDL на остальные members отсутствует.
Library database resources сохраняют отдельный предшествующий library hook.
До DDL проверяются ownership/accounts на всех server members; keeper-only
targets исключаются. Distributed DDL не является общей транзакцией: завершение
и per-member account login/grants проверяются на всех серверах, к которым может
подключиться приложение, до публикации credentials в Vault. Cluster topology,
ownership custody, concurrent execution и partial retry проверяются native QA;
свидетельство успеха одного инициатора не заменяет подтверждение всех members.
Решение владельца 2026-10-11 по A5-C01: риск позднего выполнения предыдущего
queued DDL при повторном запуске принят; специальная обработка этого случая
не входит в A5. Не добавлять pending-operation marker, native-task correlation
или отдельную блокировку повторного запуска после неопределённого результата.
Обычный timeout/error завершает текущую установку ошибкой и не разрешает
публикацию credentials в Vault. Проверки actual ownership и результата на всех
servers сохраняются; гарантия исключения overlap с оставшимся queued DDL
не заявляется. Закрытие C01 — принятие риска владельцем, не reviewer APPROVE.
Partial failure retry использует actual per-member state; foreign/неподтверждённые
объекты не присваиваются. Engine selection и multi-node DDL гарантии подтвердить
на выбранной версии; неподдерживаемый режим блокируется явно.

## 8. A5.3 — Kafka SSL и содержательные probes

Kafka connection берётся из existing named-listener projection: client-purpose,
явный library-default connectionRef, все broker advertised targets, SSL.
Controller/interBroker port, bootstrap catalog port и anonymous fallback не
используются. SSL listener не создаёт authenticated user.

Текущий probe выполняет ApiVersions: это уже protocol check, но не чтение темы
и не проверка ACL. A5 сохраняет такой безопасный check и проверяет доступность
advertised broker addresses; topic produce/consume добавлять только при явном
QA scope. Accounts.kafka при текущем пакете дают capability-unsupported BLOCK.

Усилить другие `/status` checks:

- Redis: AUTH/PING, записать/прочитать/удалить уникальный QA key внутри разрешённого
  namespace; negative ACL probe на запрещённый prefix без сохранения данных.
- Sentinel: AUTH, `SENTINEL get-master-addr-by-name`, сравнить результат с
  deployment targets, затем подключиться к master с Redis account. PING один
  не доказывает discovery permission. Runtime master адрес не сохранять в vars.
- ClickHouse: login плюс разрешённый SELECT на fixture table и запрещённый
  чужой scope; SELECT 1 один не подтверждает table grants.
- PostgreSQL/PKCS12/Agent — сохранить уже проверенные A3/A4 assertions.

Destructive/mutating permission probes используют только QA fixture data и
явные test keys/tables. Production Verify не пишет тестовые records: использует
read-only login/permissions и metadata; ошибка probe не меняет grants.
Probe не возвращает credentials, connection strings с passwords или SQL bodies.
Если образ требует изменения, использовать existing approved delivery и отдельное
QA build/publication prerequisite; не скачивать образ автоматически.

## 9. Карта файлов и подэтапы

| Подэтап | Изменения | Выход |
| --- | --- | --- |
| A5.0 | shared member projections, validators, provider job discriminator, capability manifests/schema tests | Target-free resolve всех заявленных connections, old infra-only/A1–A4 fixtures работают |
| A5.1a | Redis infra ACL compatibility, strict preservation default, witness/persistence rules | Named users переживают infra Apply/Verify/restart |
| A5.1b | `services/redis/.../roles/application_provider/{defaults,tasks}`, минимальный provider helper при необходимости | Redis и Sentinel authenticated permissions/repeat |
| A5.2a | `services/clickhouse/.../roles/application_provider`, scoped templates/client invocation | Library database до app user, protected SQL execution |
| A5.2b | CH per-member authenticated grants/retry, infra compatibility | Standalone и supported HA targets PASS |
| A5.3 | Existing probe package/defaults/Agent bindings, Kafka SSL connection | Один контейнер проверяет все providers; Kafka отражён как SSL-only |
| A5.4 | Provider stage/Verify integration, representative fixture, docs/journal/cleanup | Сквозной standalone Apply/Verify/repeat и закрытая evidence matrix |

Минимальный Core набор: `application_providers.py`, existing action/filter adapters,
`application_libraries.py` connection resolution, provider-stage и standalone
provider entrypoints; A4 credential/secret logic переиспользуется. Service-owned
member projection вызывается также существующими infrastructure roles. Public
schema расширяется только typed resource/grants полями, где они реально нужны.
Сервисные defaults, witnesses и private admin runtime inputs документировать для
manual inventory. Generated catalog/schema reproducibility — existing generators.

## 10. QA и критерии завершения

Before target QA прочитать `docs/agent-procedures/qa.md`; Core/Python только RED OS
Execution Node, current-tree sync, EXEC-01 `platform-automation`, persistent key,
`IdentitiesOnly=yes`, `sudo -n`. Deployed full-services не изменять в планировании.
Для implementation использовать isolated owned fixture/явно одобренный scope;
не изменять global admin passwords или shared production records ради теста.

| Case | Обязательная evidence |
| --- | --- |
| Defaults и маленький overrides | Пользователь задаёт user/password_ref; refs/grants/bindings из defaults |
| Нет libraries/accounts/optional binding | Infra-only прежний путь; отсутствующие hooks не запускаются |
| Broken declared binding / unsupported Kafka account | BLOCK до provider mutation |
| Redis standalone | AUTH, allowed key operation, forbidden scope denied, ACL persisted |
| Redis Sentinel HA | Реальные allocated ports, ACL на Redis/replicas/Sentinels, master discovery |
| Infra repeat/restart | Точный default сохранён, app users сохранены, peer auth не сломан |
| CH standalone/HA | Library DB раньше account; allow/deny grants на всех server targets |
| Existing account/DB | Read-only verification, отсутствие DDL/ACL/Vault takeover |
| Redis existing ACL profile | Exact supported canonical rights pass; broader categories/key patterns fail closed |
| Foreign same-name / witness missing | Managed BLOCK, без присвоения существующего объекта |
| Two libraries/two Docker hosts | Logical hooks не размножены, library identities/scopes изолированы |
| Partial member failure/retry | Не объявляется full success, successful scope не перезаписывается |
| Wrong password/CA/PKCS12 | Fail closed до публикации неподтверждённых credentials |
| Kafka named SSL listener | ApiVersions PASS, advertised targets доступны; без заявления auth/ACL |
| Clean repeat | changed=0 и реальные нулевые mutation counts; без container recreate |
| Verify | Один inspect + bounded read-only providers/probes; без ACL SAVE/DDL/write |
| Secret hygiene | Project/.env/Compose/events/client argv/logs не содержат secrets |

Сначала focused projection/schema/service tests, затем native каждой части,
потом один сквозной container Apply/Verify/repeat. A3/A4 targeted regression
проверяет прежние PG/Vault hooks, existing-source custody и cleanup, без новых
benchmark series. ALT QA требуется только при ALT-specific scope. Изолированный
HA fixture имеет явные границы очистки; не удалять чужие users/databases/networks.

План требует одного independent FULL PLAN review до согласования. Реализация
меняет credential/ACL и public contract boundaries: один FULL DIFF review после
native evidence; at most один owner-approved TARGETED_RECHECK конкретных blockers.
При BLOCK остановиться и передать findings владельцу. Отдельные части могут быть
частично готовыми, но A5 COMPLETE требует всех принятого scope cases; Kafka
SASL/ACL при выбранном SSL-only scope не считается выполненным.

Статус реализации: текущий A5 scope реализован и проверен на RED OS.
Независимый FULL DIFF первоначально BLOCK по A5-D01/D02; единственный
owner-approved TARGETED_RECHECK APPROVE, оба finding закрыты. D03 закрыт
документацией и native negative test. C02 остаётся неблокирующим ограничением:
доступ/retention policy производственной Keeper DDL queue отдельно не проверялись;
защищённая private TLS Keeper инфраструктура остаётся prerequisite. Исходный
FULL review и окончательный targeted verdict: [отчёт](a5-diff-review.md).

## 11. Источники и связанные документы

- [Общий план главы](implementation-plan.md), [A3](a3-technical-plan.md),
  [A4](a4-technical-plan.md), [секреты](secrets.md).
- [Redis ACL](https://redis.io/docs/latest/operate/oss_and_stack/management/security/acl/):
  command/key/channel restrictions и external ACL persistence.
- [Redis Sentinel](https://redis.io/docs/latest/operate/oss_and_stack/management/sentinel/):
  отдельные client ACL и master discovery API.
- [ClickHouse access control](https://clickhouse.com/docs/concepts/features/security/access-rights):
  SQL access storage и admin account prerequisites.

Официальные docs не заменяют тестирование pinned artifact. Текущий проект
поставляет ClickHouse 26.8.14.3; Redis/client version и поддержанные ACL tokens
проверить по выбранному artifact до реализации. Решения реализации, native
evidence и timings вести в отдельном `a5-test-journal.md`.
