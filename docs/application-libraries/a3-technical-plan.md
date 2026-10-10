# A3 — ресурсы библиотеки и общий PostgreSQL provider hook

Статус: технический план для согласования; реализация и target mutations не
разрешены этим документом. Основа: master `ae3002907842bcdf8700bfb78305fe64d7c7e3c9`,
A1 resolution и A2 standalone runtime. Текущий статус — только CURRENT_STATE.md.

## 1. Результат и границы

Уточнение владельца при реализации 2026-10-10: один resource batch на библиотеку
и отдельный account/grants hook на каждый logical application instance. Ниже
первоначальные предложения provider-wide batching заменяются этим правилом:
общий discovery переиспользуется, но mutations разных libraries/instances не
объединяются. Benchmark сравнения отменены владельцем и не запускаются.

A3 добавляет самостоятельный Ansible/Core путь подготовки PostgreSQL для
библиотеки: БД → схемы → УЗ экземпляров → grants → authenticated Verify.
Два разных приложения вызывают один provider-owned entrypoint с разными inputs.
Одна библиотека на двух Docker-хостах создаёт одну БД и одну УЗ каждого
логического instance, а не по одной УЗ на host.

Поддерживаются PostgreSQL standalone и pg_auto_failover; в HA работают только
database members. Monitor не является кандидатом для application SQL.
Patroni и другие deferred modes блокируются до любых записей.

Не входят: Vault writes/AppRole/Agent, generated passwords, чтение vault_ref,
Redis/ClickHouse/Kafka hooks, PKI выдача, HAProxy/DNS, миграционный движок,
удаление ресурсов, автоматическая смена паролей, Go/UI, общий execution DAG,
release bundle и инфраструктурная переустановка.

Это provider end-to-end, а не запуск контейнера с паролем. После A3 контейнер
с accounts/secret_bindings всё ещё блокируется A2 guard до реализации A4.
Доставка пароля в .env/Compose ради временного QA запрещена. Сценарий A2 без
секретов сохраняется. A7/A8 позднее подключат эти же tasks к общему плану.

## 2. Что уже есть и что нужно добавить

| Механизм | Переиспользование / изменение |
| --- | --- |
| resolve_application_libraries, instance.yml | Ansible include_vars/combine, defaults → slot → instance → host overrides; без Python precedence |
| application_libraries.py | Те же resolved rows, resource refs, account descriptors и connection_defaults по serviceType |
| resolve_connection | PostgreSQL client targets уже исключают monitor; не копировать расчёт effective ports/TLS |
| PostgreSQL role variables | platform_postgresql_instances, user, paths, secret_files, PKI plans; не запускать install main.yml ради hook |
| PostgreSQL main.yml | Образец native psql, local socket, pg_is_in_recovery, no_log и runtime credential input; существующие admin/replication tasks не расширять приложениями |
| service.yml capabilities | Сейчас только service.postgresql.client; добавить явные типизированные capabilities provisioning |
| application runtime A2 | Сохранить package/image/path guards; provider-only playbooks не вызывают Docker |
| runtime_role_variables | Установленный механизм проекции переменных provider на правильный host |

Готового общего account/database hook в текущей роли нет. Добавляется небольшой
provider role с обычными vars и явными tasks; без plugin registry, произвольных
команд от приложения, SQL DSL, второго desired-state store или scheduler.

## 3. Desired state: defaults приложения и overrides пользователя

Обычный пользователь задаёт только username и защищённую password reference.
Ни username, ни env сами по себе не создают УЗ: действие объявляет accounts.
Имена resources относятся к библиотеке, databaseRef связывает УЗ с её ресурсом.

Фрагмент defaults приложения после штатного Ansible merge:

```yaml
platform_application_definition:
  connections:
    postgres: {library_binding: database, purpose: client, protocol: tcp}
    vault: {library_binding: secrets, purpose: client, protocol: https}
  defaults:
    parameters:
      postgres:
        user: "{{ application_instance_id }}"
        password_ref: ''
    accounts:
      postgres:
        mode: managed
        databaseRef: application-database
        credentials:
          username:
            source: {kind: literal, value: "{{ application_parameters.postgres.user }}"}
          password:
            source:
              kind: runtime_secret_ref
              ref: "{{ application_parameters.postgres.password_ref }}"
        grants:
          - schema: api
            privileges: [USAGE]
    provisioner:
      type: vault-agent
      mode: process-supervisor
      secret_bindings:
        DB_PASSWORD:
          source: {account: postgres, field: password}
```

Последний binding показан как совместимость с будущим A4: A3 его валидирует,
но не создаёт Agent/Vault и не начинает контейнер. source.field — существующее
поле credential descriptor; нового поля назначения binding в A3 нет.

Пример group_vars (фрагмент с application deployments):

```yaml
platform_desired_state:
  applicationLibraryDeployments:
    sdku:
      libraryRef: sdku@1.0.0
      runtimeRef: docker-apps
      bindings:
        database: {deploymentRef: postgres-sdku}
        secrets: {deploymentRef: vault-main}
      resources:
        application-database:
          kind: postgresql.database
          binding: database
          mode: managed
          parameters: {name: sdku}
        api-schema:
          kind: postgresql.schema
          binding: database
          mode: managed
          databaseRef: application-database
          parameters: {name: api}
      applications:
        gateway:
          overrides:
            parameters:
              postgres:
                user: apigateway-sdku
                password_ref: sdku-apigateway-pg-password
```

gateway — существующий recipe slot, instance ID автоматически apigateway-sdku.
Для второго приложения отличаются defaults/package и username/ref, hook тот же.
host_vars включает библиотеку на выбранных Docker-хостах штатным membership A1.
Account/resource definition должна совпадать на всех placements; host-specific
username/passwordRef/grants/resources запрещены для одного logical instance.

mode у resources и databaseRef у schema — предлагаемые узкие расширения схемы.
Отсутствующий resource.mode означает managed для совместимости с A1 examples.
Account.mode остаётся существующим обязательным полем.
Resources берутся сейчас из deployment.resources; A3 не переносит их неявно
в library defaults и не меняет precedence.

## 4. Типизированный PostgreSQL контракт

| Сущность | Обязательное содержание | Семантика |
| --- | --- | --- |
| postgresql.database | binding, mode, parameters.name | managed ensure или existing read-only |
| postgresql.schema | binding, mode, databaseRef, parameters.name | databaseRef только на БД той же библиотеки/provider |
| accounts.postgres | mode, databaseRef, username descriptor, password descriptor, grants | УЗ логического instance, не Docker placement |
| schema grant | schema, privileges=[USAGE] | Без CREATE/ownership у app |
| table grant | schema, tables=[явные имена], privileges из SELECT/INSERT/UPDATE/DELETE | Таблицы должны существовать до hook |
| sequence grant | schema, sequences=[явные имена], privileges из USAGE/SELECT/UPDATE | Отдельный тип, без угадывания sequences таблицы |

Каждый grant выбирает ровно schema-only, tables либо sequences. Нельзя wildcard,
ALL, GRANT OPTION, arbitrary SQL, role membership, SUPERUSER, CREATEDB,
CREATEROLE, REPLICATION, BYPASSRLS. Неподдерживаемый privilege/resource kind
блокирует всю выбранную подготовку до первой записи.

Managed login: LOGIN, INHERIT без членства, без административных флагов.
Владелец БД/схемы — отдельная машинно вычисленная NOLOGIN роль библиотеки;
application login не получает ownership. Managed БД создаётся закрытой для PUBLIC
CONNECT/TEMP, managed schema — без PUBLIC CREATE/USAGE. App получает CONNECT
и только объявленные schema/object privileges. Не изменять template databases,
public schema чужой БД, HBA, admin/replication роли или соседние deployments.
Новую БД создавать из TEMPLATE template0: не копировать локальные application
objects, добавленные оператором в template1; сами templates не изменять.

existing БД/схема: только проверка существования и доступности, без owner/comment,
PUBLIC ACL, DDL или grants mutations. Managed account внутри existing DB с
новыми grants в A3 блокируется: нельзя выдать себе управление чужими объектами.
Existing account проверяется authenticated, без ALTER PASSWORD/GRANT/REVOKE.
Его объявленные grants — требования к фактическим правам, не команды изменения.

Конфликты по (provider, database name), (provider, username),
(provider, database, schema name) обнаруживаются между всеми выбранными
библиотеками, включая совпадение разных logical instances. Default usernames
не разделяются; сознательно общая существующая УЗ требует existing mode.
Системные имена postgres, template0/template1, pg_* и provider admin/monitor/
replication usernames запрещены для managed application resources.
Идентификаторы A3 ограничены ASCII [a-z_][a-z0-9_]*, максимум 63 байта:
автоматический instance ID с дефисами допускается как username через точное
SQL identifier quoting; итоговый username допускает дополнительно дефис.
Не обрезать длинные имена: при превышении лимита ошибка поля.

## 5. Runtime secrets и совместимость A1/A4

A3 поддерживает для account password только runtime_secret_ref, username —
literal после Ansible projection. Пароль читается на Execution Node через
существующий secretRef → protected file механизм; provider получает обычный
platform_postgresql_secret_files, включая admin reference при необходимости.
Это input map путей, не новая база паролей. Ни sample, ни vars проекта не
содержат значения. Runtime пути не принимаются из application parameters.

Проверить файл: принадлежность разрешённому runtime root/session identity,
regular file без symlink/path escape, private directory и ожидаемый owner/mode,
непустое значение. Пользователь вручную подаёт ref→file обычными Ansible vars
через защищённый runtime ввод; файл живёт по уже существующему lifecycle владельца.
Не переносить credential files на Docker hosts. SQL password input — stdin,
не argv/URI/temporary SQL file; no_log на lookup, stdin, result, asserts.
Ошибки наружу — только фиксированный code и desired-state field.

generated, vault_ref и pki_credential как account password в A3 дают явный
APPLICATION_PROVIDER_CREDENTIAL_SOURCE_DEFERRED до mutations. Нет временного
генератора или прямого Vault API пути. Secret bindings/shared secrets не
исполняются и не ослабляются; A1 требование Vault ref/provisioner для accounts
сохраняется. Provider-only hook не проверяет live Vault, так как его не использует.

Пароль managed УЗ: сначала проверить authenticated connection с предоставленным
значением. При существующей owned УЗ неверный пароль блокирует PASSWORD_CHANGE_REQUIRED;
не выполнять ALTER PASSWORD как «исправление повтора». Новая УЗ создаётся сразу
с данным паролем. Явная rotation и координация с Vault относятся к A4/следующему
scope. Ни пароль, ни его hash не становятся plan/snapshot/config-digest.

## 6. Target-free projection и capability dispatch

Расширить текущий resolver небольшой PostgreSQL projection:
library resource actions + account actions + secret requirements + safe findings.
Deduplicate по project/library/resource и project/library/instance/account,
не по host. Все rows одной библиотеки сравнить: resources, bindings, accounts,
grants и выбранный provider должны совпадать. Current A1 credential check недостаточен
для host-specific resource/binding/grants conflicts: явно дополнить сравнение.

service.yml PostgreSQL объявляет capabilities service.postgresql.database,
service.postgresql.schema, service.postgresql.account. Подключение остаётся
service.postgresql.client. Проверять возможности exact versioned package, не
выводить mutation capability только из наличия client listener. Dispatch для A3
фиксирован на доверенный platform.postgresql.application_provider, без строки
tasks/playbook/SQL, которую мог бы передать package приложения.

Объявлено действие без обязательного ref — BLOCK с точным полем. Нет действия
и ref — нет job, SKIP. Задан неизвестный ref — BLOCK. accounts={} не создаёт
УЗ и credential requirements, но не мешает library resources.
Unknown resource/provider capability — BLOCK, а не успешный пропуск.
connection_defaults по serviceType и connectionRef остаются A1 контрактом.

Target-free операции не подключаются к PostgreSQL/Vault/Docker и не читают
значения runtime secrets; выводят только refs, identities, candidate members,
порядок действий и prerequisites. writable primary — discovered fact исполнения,
никогда новый desired-state параметр или сохранённый host override.

## 7. Preflight провайдера и выбор writable primary

До первой мутации всех выбранных библиотек проверить prerequisites каждой:
валидный resolved project/package identity, refs/capabilities, credential files,
existing objects, ownership conflicts, grants targets и доступный PostgreSQL.
Если tables/sequences отсутствуют, миграции должны быть выполнены отдельно до A3;
hook их не создаёт. Для новой БД table grants пока невозможны без явного
последующего migration шага: сценарий A3 новой БД ограничен CONNECT/schema USAGE.

Для standalone кандидат один database member. Для pg_auto_failover проверить
всех database candidates из effective projection по local socket на нужном
provider host, правильному effective port, от имени platform_postgresql_user.
Запросы pg_is_in_recovery и transaction_read_only должны дать ровно одного
готового writable кандидата; ноль/два/недоступный обязательный candidate блокируют.
Monitor не опрашивать application SQL и не использовать как fallback.
Не создавать клиента по первому элементу targets/HAProxy roundrobin endpoint.

Provider readiness выполняется read-only. Local admin SQL использует установленные
socket/user/path vars; remote account probes используют выбранный client port,
effective TLS и существующие явные PKI materialization plans с verify-full.
Отсутствие CA/SAN/auth/HBA prerequisites блокирует; hook не понижает TLS и не
добавляет HBA автоматически. На каждом SQL write повторно подтвердить writable
состояние в той же сессии. Смена primary во время операции — остановка и fresh
preflight при retry, без автоматического promotion/failover или второй записи.

## 8. Ownership, повтор и конкуренция

PostgreSQL хранит фактическую ownership identity через NOLOGIN library owner
role и exact managed comments. Комментарий содержит version/project/provider/
library/resource либо instance/account, без secrets; имена генерируются
детерминированно с bounded digest при необходимости и не задаются пользователем.
Это metadata существующих объектов, не новый control database/store.

NOLOGIN owner role и login role создаются вместе со своим comment/безопасными
flags в одной SQL transaction. Schema create+comment — также atomic. Существующая
роль/схема без точного marker или с чужим marker блокируется, даже если совпали
имя/пароль. Никакого adoption по username или автоматической смены ownership.

CREATE DATABASE нельзя поместить в transaction block. Поэтому библиотечная owner
role должна быть уже committed и проверена. БД создаётся с этой exact owner role.
Идентичность managed БД: exact requested name + owner role с marker текущей
библиотеки + совместимые database attributes. DB comment дополнительно проверяется:
чужой comment блокирует; отсутствие comment после create допускает ограниченный
retry, если вся комбинация owner/name/attributes доказана. Это явное исключение
только для managed DB crash gap, не для существующих чужих DB/roles/schemas.
Если ownership доказать нельзя, остановиться без cleanup/takeover.

Новую БД создавать с ALLOW_CONNECTIONS=false. Из maintenance DB после проверки
owner/name/attributes удалить default PUBLIC CONNECT/TEMP, затем разрешить
connections; schema ACL и grants reconcile выполняются после ownership.
При interrupted create соединения остаются закрыты; bounded retry сначала
проверяет identity и ACL, затем открывает owned БД. Это не обещание общей
транзакции DB+schema+account; чужую/недоказанную БД hook не открывает.

Одновременные invocations защищаются PostgreSQL session advisory lock на
обрабатываемый объект в фиксированной coordination DB: roles/database — postgres,
schema/grants — соответствующая БД. Lock охватывает inspect/ownership/write/verify
в одной psql session; отдельный Ansible command «взять lock» его не удержит.
Bounded timeout → BUSY без удаления объектов; завершение session освобождает lock.
Одинаковый объект всегда использует одинаковый lock key/domain независимо от
library caller. Между DB sessions нет обещания глобальной транзакции.
Привилегированные внешние writers, игнорирующие advisory locks, остаются
операторским ограничением; после каждого шага проверить реальное состояние.

Grants managed УЗ: добавить недостающие явно объявленные privileges на схемы, таблицы и sequences. Существующие дополнительные права и удалённые из YAML grants не отзывать. Проверять владельца объявленного управляемого объекта и принадлежность аккаунта; не обходить необъявленные объекты и PUBLIC ACL. Existing account проверяется на требуемый доступ без изменений. Verify never repairs, CREATE/ALTER/GRANT/REVOKE/DROP в Verify запрещены.

## 9. Standalone последовательность и барьер библиотеки

Предлагаемые entrypoints:

1. application-libraries-providers-preflight.yml: обычный resolve/snapshot,
   provider-only projection, все read-only prerequisite/ownership проверки.
2. application-libraries-providers-apply.yml: импорт preflight, library resources,
   проверка resources всех выбранных libraries, затем instance accounts/grants.
3. application-libraries-providers-verify.yml: тот же projection и read-only
   object/ownership/access/account проверки, без Apply и генерации secrets.

Provider operations выполняются делегированно на выбранных PostgreSQL hosts
один раз для logical library/instance. Не полагаться на run_once внутри serial
Docker play: иначе операции повторятся на каждом batch. Явная controller play
на Execution Node строит список unique jobs, trusted includes делегируют targets.
Прямой manual inventory остаётся поддержан через обычные provider role vars.

Порядок Apply: глобальный read-only preflight → owner roles/DB/schema всех
libraries → read-only verify library resources → accounts → grants → проверка
authenticated connections/permissions. Failure library phase блокирует все
dependent account jobs; barrier не сохраняется как reusable файл успеха.
Retry заново инспектирует provider. Provider failure не запускает Compose.

При отсутствии library actions все plays завершаются без provider connections.
При resources без accounts выполняется только resource phase. Existing inputs
проверяются read-only. Failures сохраняют уже созданные owned objects; нет DROP
rollback/автоудаления при удалении библиотеки из vars. Операции удаления отдельные.

## 10. Verify и доказательства

Verify проверяет actual DB/schema/role ownership, безопасные role flags, наличие заявленных grants и password login предоставленным runtime ref. Дополнительные права не считаются drift. Production Verify read-only: SELECT, каталог ACL, privilege functions,
authenticated SELECT 1. Не выполнять INSERT даже с ROLLBACK: sequences/triggers
могут иметь побочные эффекты. Реальные INSERT/UPDATE/DELETE negative/positive
пробы нужны в изолированном QA fixture, не на пользовательских таблицах.

Provider-host login не доказывает доступность с Docker-хоста. Для A3 добавить
read-only psql TLS probe с Docker placement hosts, только если trusted client уже
доступен; не устанавливать tools и не запускать credential-bearing контейнер
автоматически. Missing client — явный QA prerequisite, а full rootless-container
connection/Agent path остаётся A4/A9. Отчёт различает эти уровни доказательств.

Safe output: operation/resource IDs, provider/member/host, status, changed,
фиксированный finding code и field. Пароли, SQL stdin, pg_authid/password hashes,
raw stderr и содержимое secret files не выдаются в events/review/journals.
No production test-only bypass. Infra-only planner guard A1/A2 сохраняется.

## 11. Файлы реализации

| Путь | Изменение |
| --- | --- |
| contracts/application-libraries/v1alpha1/settings.schema.json | PostgreSQL typed grant validation через provider schema; сохранить existing descriptor/binding contract |
| contracts/application-libraries/v1alpha1/deployments.schema.json | resource.mode/schema.databaseRef, PostgreSQL resource parameters; без нового top-level model |
| application_libraries.py, resolve_application_libraries | consistency/capability checks, provider jobs и безопасные findings; Ansible precedence неизменен |
| services/postgresql/service.yml | явные provisioning capabilities |
| services/postgresql/ansible_collections/platform/postgresql/roles/application_provider/ | defaults; validate, preflight, resources, accounts, grants, verify; trusted SQL templates с корректным identifier/literal quoting |
| ansible-core/playbooks/application-libraries-providers-*.yml | standalone три entrypoints и library barrier |
| services/postgresql/tests/ | SQL quoting, privileges, native PostgreSQL fixtures, HA primary selection/monitor exclusion |
| ansible-core/tests/ | projection, dedup/host conflicts, guards, отсутствие secret output и infra-only regression |
| examples/valid/application-providers/ | одна библиотека, два разных app packages, два Docker placements, standalone/HA варианты; только refs |
| docs/application-libraries/a3-test-journal.md | создаётся при реализации: exact revision, reviews, tests, cleanup, limits |

Сначала inspect schema владельца resource declarations и generator service catalog,
затем расширить их минимально. Не редактировать generated catalog вручную.
SQL templates доступны только provider role; application package не передаёт SQL.
Новая PostgreSQL Ansible collection/psycopg dependency не требуется: использовать
installed psql и built-in Ansible command, как текущий provider. Не вводить
универсальный SQL executor или большой Python database client.

## 12. Подэтапы реализации

### Обязательное требование владельца: минимальная стоимость hooks

Уточнение 2026-10-10: десятки контейнеров и последующие providers не должны
превращать deploy в цепочку медленных мелких Ansible tasks. Минимизировать число
tasks, SSH/module invocations, psql launches и повторных запросов; измерять
реальное время, а не только считать YAML tasks.

- Resolve/dedup — один раз на execution; infrastructure installation/PKI/runtime
  discovery не вызываются из account hook.
- Provider readiness/primary discovery — один раз на deployment для всех
  библиотек, а не на приложение/placement. Перед mutation остаётся короткая
  writable/identity проверка в исполняемой SQL session.
- Считать P — providers, B — уникальные БД, N — logical accounts. Увеличение
  числа Docker placements не увеличивает количество provisioning jobs.
- Catalog inspection читать пакетно в одном SQL вызове по набору имён; не
  делать отдельный psql/task на exists, owner, flags, comment и каждый privilege.
  Statements передавать в trusted provider script через stdin, ON_ERROR_STOP.
- Resource/role операции объединять только внутри одной библиотеки, schema/grants
  только внутри её resource scope либо одного экземпляра приложения; object locks
  брать в стабильном порядке в той же сессии. CREATE DATABASE
  выполняется в autocommit части той же session, без фиктивного DO/transaction.
  Граница группирования не меняет object ownership/partial failure semantics.
- Account writes и grants объединять только внутри одного logical instance,
  никогда между instances, даже если provider/БД совпадают. Один hook-вызов
  экземпляра выполняет его SQL batch, затем необходимую authenticated probe.
  Не создавать task на table, privilege или field.
  Ansible loops нужны для unique provider/DB и независимых authenticated probes,
  не для каждой строки декларации. Избегать include_role/include_tasks per grant.
- Existing account password probe неизбежно проверяет конкретную identity:
  максимум одна такая проверка на account в успешном Apply, если пароль/роль
  не изменялись. Её результат используется в этом же invocation, не хранится
  между runs; вновь созданная УЗ проверяется после create. Verify как отдельный
  invocation проверяет credentials заново. Нельзя заменить login hash-сравнением.
- Чистый повтор читает состояние и выполняет login probes, но не повторяет DDL,
  ALTER PASSWORD, GRANT/REVOKE, service restarts и искусственные sleeps.
  Важно: changed=0 само по себе не доказывает отсутствие лишних вызовов.
- Read-only preflight snapshot используется только в текущем execution;
  race-sensitive ownership/writable facts перепроверяются внутри write session.
  Не вводить persistent cache, worker pool, daemon или новый scheduler ради скорости.
- Целевая структура provider role — небольшое число phase tasks, ориентир
  8–12 содержательных task definitions (без validate assertions/cleanup wrappers),
  а не отдельный набор tasks для каждой сущности. Это ориентир, не основание
  объединять несовместимые security boundaries в небезопасную shell команду.

Первоначально предлагавшиеся benchmark QA отменены владельцем. Функциональная QA
проверяет отсутствие повторного discovery и logical hooks на Docker placements.
Длительности обычных функциональных прогонов являются диагностикой, не benchmark.
Ниже исходная benchmark matrix не является разрешением её запускать.

QA фиксирует количество module/SSH/psql invocations, SQL writes и duration отдельно
для provider preflight/resources/accounts/grants/Verify. Сравнить 1, 10 и 30
logical instances, чистый повтор, 1 и 2 Docker placements; проверить, что на
каждый дополнительный account приходится только необходимая account/login
работа, а discovery/library work не повторяется. Для A3 не приписывать сюда
Docker pull/start время. Итоговый performance budget согласовать по замеру
на RED OS перед acceptance; пока числовой SLA не доказан и не обещается.

1. A3.1: типизированные resources/grants/capabilities, validation, dedup и safe
   secret requirements; focused target-free tests. Defaults/override example.
2. A3.2: provider-only preflight, runtime credential validation, exact member
   role/port/socket/TLS и writable selection; read-only tests.
3. A3.3: owner role/database/schema ensure + ownership/retry guards; repeat,
   interrupted create и foreign-resource fixtures.
4. A3.4: account creation/password no-rotation, выдача недостающих заявленных grants,
   existing read-only, authenticated Verify, concurrency fixture.
5. A3.5: standalone entrypoints/barrier + две app сущности/два placements;
   negative provider failure и infrastructure-only regression.
6. A3.6: независимый FULL DIFF review и согласованные corrections по процедуре,
   focused/native/regression QA, cleanup и evidence. Без автоматического A4.

## 13. QA и критерии выхода

QA на RED OS из current source, platform-automation persistent SSH identity,
IdentitiesOnly=yes и sudo -n; перенос/cleanup scripts/qa-sync.ps1. Перед target QA
прочитать процедуру qa.md и подтвердить отдельный scope providers/fixtures.
Документ не разрешает мутировать уже развернутый full-services project.

| Сценарий | Требуемое доказательство |
| --- | --- |
| no libraries / no actions | прежние Core/infra semantics; нет provider calls |
| resources without accounts | DB/schema готовы, account/Vault/Docker calls отсутствуют |
| два приложения, два Docker hosts | одна DB/schema, две разные УЗ; hook общий, без host duplicates |
| defaults/instance override | user/password_ref проецируются штатным Ansible merge |
| конфликт host values/refs/names | precise BLOCK до любых SQL mutations |
| standalone / pg_auto_failover | correct writable data member; monitor untouched |
| zero/two writable, missing candidate, TLS failure | BLOCK; нет fallback/promote/HBA change |
| managed repeat | changed=0, OIDs/ACL/role flags сохранены, пароль не переустановлен |
| чужие DB/schema/user и marker mismatch | no adoption/no writes, даже при совпавшем пароле |
| interrupted owner/role/schema/DB create | atomic marker либо bounded DB retry; foreign gap не присваивается |
| existing | identity/login/grants Verify; no DDL/ACL/password writes |
| bad/missing/ref source/unsafe file/SQL input | redacted failure before mutation; quote/injection cases |
| least privilege | read/write allowed только по декларации; чужие objects/admin flags denied |
| стандартный PUBLIC baseline / extra application PUBLIC grant | дополнительный PUBLIC доступ не блокируется и не изменяется; соседние ACL неизменны |
| grants removal/drift | удалённые grants сохраняются; недостающие выдаются; membership/foreign ownership block |
| missing migration table | prerequisite BLOCK, таблицы не создаются |
| simultaneous hook / primary switch | BUSY/unique identities либо safe failure+fresh retry, без двойных writes |
| 1/10/30 instances, 1/2 placements | timings и counts; общая работа не повторяется, SQL пакетный, чистый повтор без writes |
| library phase failure | account phase и Compose не начались |
| Verify after drift | failure без repairs/DDL/DML; secret canary отсутствует в output |

Focused A1/A2/PostgreSQL tests + native standalone/HA acceptance + affected broad
Core regression на RED OS. Runtime A2 повторять только если его production files
изменены; scope guard и infra-only tests обязательны. Нет UI milestone в A3:
standalone PASS не означает React/Wails acceptance будущего Installer flow.
Cleanup удаляет только exact QA-created resources после проверки identity,
reverse dependencies, без production DROP entrypoint; evidence сохраняет failures.

Выход A3: весь provider-only путь PASS, два приложения используют общий hook,
multi-host dedup, existing read-only, ownership/retry/least privilege доказаны,
чистый повтор changed=0 и Verify без мутаций. Нет секретов в проекте/логах;
A2 deferred Agent guard остаётся; implementation review blockers закрыты и
неблокирующие ограничения явно записаны. Следующий этап — отдельное решение A4.

## 14. Review gate и SQL основания

Независимый FULL PLAN review обязателен до согласования реализации. HIGH-RISK
DIFF: provider credentials, database mutations, ownership и public contracts.
Один FULL + не более одного owner-approved TARGETED_RECHECK; BLOCK возвращается
владельцу, без автоматического redesign/re-review цикла.

PostgreSQL 16: [CREATE DATABASE](https://www.postgresql.org/docs/16/sql-createdatabase.html)
не выполняется в transaction block; [session advisory locks и recovery state](https://www.postgresql.org/docs/16/functions-admin.html)
используются как native provider механизмы. Provider-specific quoting/privileges
проверяются native fixtures; эти ссылки не заменяют test evidence.

### Упрощение хука, принятое владельцем 2026-10-10

Актуальный контракт заменяет описанные выше exact ACL reconcile и полный аудит
прав аккаунта. Хук обрабатывает только явно объявленные БД, схемы и grants.
Managed ресурсы проверяются по владельцу и marker; чужие объекты не присваиваются.
Managed аккаунты создаются без административных прав, существующие пароли не
меняются. Apply добавляет недостающие заявленные права; дополнительные права,
PUBLIC ACL и права на необъявленные объекты не сканируются и не нормализуются.
Удаление grant из YAML не отзывает ранее выданное право. Existing остаётся
read-only. Verify проверяет принадлежность и наличие заявленных прав без ремонта.
Один SQL batch на библиотеку и один на экземпляр сохраняются; benchmark отменён.

Уточнение структуры 2026-10-10: отдельный preflight_objects.sql.j2 удалён.
Проверки объявленных объектов находятся в preflight.sql.j2 и включаются
application_provider_check_objects=true только в preflight task. Resources и
accounts используют общую проверку БД/ролей без повторного обхода объектов.

### Исправления FULL DIFF, одобренные владельцем 2026-10-10

A3-D01: existing-account preflight подключается к объявленной БД; managed
recovery probe может использовать postgres, но Apply после grants и Verify
обязательно выполняют authenticated SELECT 1 для каждого аккаунта в его БД.
A3-D02: discovery ищет ровно один writable master среди database members
выбранного deployment, monitor исключён. Ноль/два writable либо недоступный
кандидат блокируют запись. Native primary/standby и полный Core entrypoint
проверяются функционально, без benchmark.
A3-D03: openssl prerequisite ограничен timeout 10s, kill-after 2s.
A3-D04: неиспользуемая candidate.roleVariables проекция удалена.

PKI access correction: read-only TLS/login probes reuse platform_pki_owner (otherwise platform_execution_technical_user/root). Administrative socket SQL continues as the PostgreSQL OS user; PKI directory permissions are not relaxed.
