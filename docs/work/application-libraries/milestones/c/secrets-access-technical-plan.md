# Экран «Секреты» и доступ к БД

Дата: 2026-10-16. План согласован владельцем, реализация разрешена отдельным
сообщением. Текущий результат реализации и review — в CURRENT_STATE.md и журнале;
согласование плана не является QA PASS или разрешением инфраструктурного Apply.

## Уточнения владельца после FULL DIFF (2026-10-16)

SEC-D01 отклонён как блокер: пользователь вправе назначить УЗ владельцем объектов.
Не запрещать собственную роль-создателя, не менять ownership автоматически и не
обещать, что REVOKE DML отнимает полномочия владельца. UI поясняет это; Verify
сохраняет owner authority. Утверждения ниже об отсутствии ownership/DDL относятся
к выдаче прав этим механизмом, а не к запрету уже назначенного владельца.

SEC-D02 принят: реализовать снятие прямых SELECT/INSERT управляемой ClickHouse УЗ
в managed БД её библиотеки с существующим UUID/marker witness. Прямые назначения
этого ограниченного scope — управляемая политика, а не независимые внешние grants.
Назначения вне scope, membership, column/partial/grant-option ACL — конфликт без
мутаций; соседние УЗ не затрагиваются. Нельзя убрать GRANTS_DRIFT целиком или
выполнять безусловный глобальный REVOKE. Владелец разрешил один TARGETED_RECHECK
SEC-D01/SEC-D02 и QA после исправлений, без нового полного review.

## 1. Цель и решения владельца

Компактная вкладка экземпляра приложения: deployment → настройки подключения
и таблица доступов. Максимум два уровня группировки. Учётная запись задаётся
один раз для подключения и используется в нескольких БД. Добавляется «доступ»,
а не ещё одна УЗ. В таблице только БД, права и действия; колонок схем/объектов нет.
Права охватывают существующие и будущие пользовательские схемы, таблицы и
последовательности в выбранной БД. Функции, DDL, ownership и обход RLS этим
выбором не выдаются. Redis имеет отдельную компактную форму ACL.

Минимализм обязателен: расширить существующий provider pipeline, writer и
редакторы. Не добавлять resolver в React/Go, новую БД состояния, ACL-daemon,
event triggers, polling, собственный SQL execution framework или параллелизм.

## 2. Проверенная база и расхождения

* `settings.schema.json`: аккаунт имеет один `databaseRef`, credentials и grants.
* `application_providers.py`: один claim УЗ на provider; PostgreSQL grants
  нормализуются в конкретные схемы/таблицы/последовательности. Один аккаунт
  сейчас включается только в accounts одной БД.
* PostgreSQL `application_provider/templates/accounts.sql.j2`, `database.sql.j2`,
  `verify.sql.j2`: уже есть ownership markers, advisory locks, безопасное SQL
  quoting, создание LOGIN один раз, CONNECT и проверка прав.
* ClickHouse grants уже содержат databaseRef и tables; `['*']` покрывает БД.
  Redis уже принимает commands/keys/channels; Sentinel имеет отдельный allowlist.
* UI: `ApplicationCredentials`, `ApplicationSecretBindings`,
  `ApplicationSecretInputs`, существующие EditCommand/Review/Save и runtime lease.
* Макет `docs/design/application-editor-production-mockup.html` и раздел UI design
  содержат прежний дизайн редактирования KV-ключей. Он остаётся design-only:
  этот план НЕ меняет Vault paths/username/password и не реализует KV rename.

Предыдущая UI-only граница расширяется только после согласования этого плана:
версионированный контракт PostgreSQL access, Core Apply/Verify и тонкая проекция
через существующие adapter/writer. Старые UI изменения не переписываются.

## 3. Семантика будущих объектов

PostgreSQL default privileges относятся к роли, реально выполняющей CREATE,
а не ко всем её участникам и не ко всем будущим владельцам автоматически.
Применять их без IN SCHEMA в текущей БД: это покрывает будущие таблицы и
последовательности в новых схемах; отдельно ON SCHEMAS выдаёт будущий USAGE.
Это уточняет прежнее обсуждение: отдельный механизм наблюдения за новыми
схемами не требуется на поддерживающей ON SCHEMAS версии PostgreSQL.

Поддерживаемая гарантия: объекты создают Core-derived owner библиотеки и
явно объявленные роли миграций. Owner включается автоматически. Дополнительные
роли задаются в расширенных настройках доступа, проверяются Core на существование,
полномочия оператора и допустимую принадлежность; неизвестная роль — ошибка.
Членство в owner не считается SET ROLE. UI показывает, для каких создателей
настроено наследование. Для новой неуказанной роли требуется изменение проекта
и Apply. Нельзя обещать «любой будущий создатель» или молча включать всех LOGIN.

Версия/способность ON SCHEMAS проверяется по существующему provider capability
и preflight. На несовместимой версии явная ошибка, без деградации гарантии.
Согласование плана означает принятие этой границы ролей-создателей.

## 4. Контракт и совместимость

Добавить в существующий account PostgreSQL поле `databaseAccess` (предлагаемое
имя; закрепить в canonical schema, не создавать параллельную DTO):

```yaml
databaseAccess:
  - databaseRef: main
    privileges: [SELECT, INSERT, UPDATE]
    additionalCreatorRoles: [gateway_migrator]
  - databaseRef: reports
    privileges: [SELECT]
```

`databaseRef` — ключ ресурса библиотеки, не пользовательское SQL выражение.
privileges: непустой уникальный набор SELECT/INSERT/UPDATE/DELETE.
Политика all-user-schemas/current-and-future фиксирована для этого поля:
никаких свободных scope/type/plugin флагов. Пустой databaseAccess разрешает
отсутствие управляемого доступа к объектам без удаления аккаунта; удаление последней строки требует
подтверждения. Лимиты списков взять из существующих контрактных ограничений.

Legacy `databaseRef` + grants остаются без изменения семантики. Для PostgreSQL
запретить одновременно legacy grant-политику и databaseAccess. Обновление старого
проекта не расширяет доступ автоматически. UI показывает legacy правила только
в прежнем/расширенном редакторе и предлагает явный переход с Review: переход
с конкретных объектов на всю БД — существенное расширение, не косметическая миграция.
Сохранённые package defaults и overrides проверяются после обычного Core resolve;
невозможность убрать унаследованное legacy поле — BLOCK перехода, не удаление
пакетного поля через самодельный UI merge. Перед кодом проверить reset/delete
семантику writer; если её недостаточно, добавить одну типизированную атомарную
операцию смены grant-политики в существующую edit session.

Один account claim/credential/passwordRef/Vault document остаётся один раз;
Core распределяет ссылки доступа по БД. Не дублировать УЗ для каждой БД.
Указанные БД должны принадлежать тому же provider. Новый управляемый режим
ограничить managed account + managed БД с существующими markers. Для existing
account/БД сохранить прежнюю проверочную семантику, не присваивать ownership.

ClickHouse UI переиспользует существующие grants `{databaseRef, tables:['*'],
privileges:[SELECT,INSERT]}`. Redis — существующий объект ACL. Не унифицировать
все сервисы новым ACL DSL. Расширение версии capability/контракта и блокировку
старого runtime выполнить существующим способом; старый bundle не должен
игнорировать databaseAccess. Обычный manual inventory остаётся поддержан.

## 5. PostgreSQL Apply

1. Существующий preflight проверяет все ссылки/markers/создателей до изменений.
   Имена quote существующими фильтрами; privileges только из allowlist.
2. Создать/проверить LOGIN существующим accounts.sql, без password rotation
   из-за изменения доступа. Захватить прежние locks в стабильном порядке.
3. В каждой БД выбрать пользовательские схемы через pg_namespace: исключить
   pg_*, information_schema, временные/TOAST; public включать. Проверить
   принадлежность объектов и отсутствие конфликтов с охраняемыми объектами
   других библиотек. Конфликт — отказ с идентификатором БД/схемы, не пропуск.
4. Выдать CONNECT; пакетно USAGE на схемы и выбранные права ON ALL TABLES IN
   SCHEMA. Использовать существующее SQL выполнение, один проход/транзакцию
   на БД, без SSH/Ansible задачи на каждую таблицу. Учитывать views/foreign tables
   согласно PostgreSQL GRANT; отдельно проверить поддерживаемые relkind.
5. Для INSERT добавить USAGE последовательностей (nextval); SELECT/UPDATE
   таблицы сами по себе не дают UPDATE последовательности/setval.
6. Для каждого разрешённого создателя выполнить database-wide default privileges:

```sql
ALTER DEFAULT PRIVILEGES FOR ROLE owner_role
  GRANT USAGE ON SCHEMAS TO app_user;
ALTER DEFAULT PRIVILEGES FOR ROLE owner_role
  GRANT SELECT, INSERT, UPDATE ON TABLES TO app_user;
ALTER DEFAULT PRIVILEGES FOR ROLE owner_role
  GRANT USAGE ON SEQUENCES TO app_user;
```

7. Перед GRANT сравнить ACL/default ACL и выполнять только недостающее.
   Повтор неизменного проекта — changed=0; сохранить прежние role/DB OIDs.
   Параллельный DDL не считать атомарно охваченным catalog scan: на время
   первоначальной сверки миграции должны быть остановлены. Между БД нет
   общей транзакции: ошибка оставляет честный partial result, повтор безопасен.

## 6. Изменение и удаление доступа

Удаление строки должно убирать управляемые grants/default privileges, не БД,
УЗ или данные. Снижение INSERT снимает также управляемый sequence USAGE, если
он больше не требуется. Смена создателя снимает его прежние default grants.

До реализации проверить имеющуюся provenance/reconcile опору. Ownership marker
роли не доказывает происхождение каждой ACL записи. PostgreSQL не различает
два одинаковых GRANT от одного grantor. Поэтому нельзя обещать одновременно
произвольные внешние назначения той же УЗ и их точное автоматическое отделение.
Минимальная политика: для нового managed режима Installer владеет прямыми
назначениями этой УЗ в охваченных managed БД; внешние назначения/членства,
расширяющие policy, — конфликт, без автоматического REVOKE чужих ролей/PUBLIC.
Legacy/existing аккаунты такой политике автоматически не подчиняются.

Удалённую из desired state строку нельзя обнаружить только по новому списку:
существующий managed account marker используется для сверки всех owned БД
того же provider/library и default ACL для этого grantee. Не создавать ACL ledger.
Список создателей для снятия прежних default grants брать также из pg_default_acl.
Если доступные markers не позволяют однозначную сверку, это блокер реализации,
а не разрешение на глобальный REVOKE/DROP OWNED/CASCADE. Отозванный прямой grant
не гарантирует запрет через PUBLIC/членство/ownership: Verify обязан это учитывать
и сообщать конфликт эффективных прав, а не ложный PASS удаления.

Policy удаления означает отсутствие управляемых schema/table/sequence grants
и default grants, а не запрет подключения: стандартные PUBLIC CONNECT/TEMPORARY
не изменяются и сами по себе не являются ошибкой удаления. Лишний эффективный
DML через membership/PUBLIC является конфликтом. Отдельный запрет соединения
не входит в этот экран; если он потребуется, PUBLIC CONNECT — явная предпосылка,
а не повод автоматически менять общую политику БД.

В существующем `split_provider_jobs` instance/account hook должен сохранять
полный ограниченный reconcile scope owned БД своей library/provider, включая
БД без текущих строк доступа. Иначе удалённая строка исчезнет до SQL REVOKE.
Расширить существующую job projection, без отдельного discovery API или ledger.

## 7. Verify

Только чтение: CONNECT, schema USAGE, table DML, необходимый sequence USAGE,
pg_default_acl для каждой роли и всех трёх классов объектов; отсутствующая
default ACL не означает default deny без проверки PostgreSQL baseline ACL.
Проверить запрещённые лишние прямые и эффективные права согласно managed policy.
Пустая БД не должна давать PASS при отсутствующих default privileges.
Verify не создаёт пробные таблицы; такие проверки выполняет только QA fixture.
Безопасные findings: provider/database/account ID, фаза, код; не пароль/SQL payload.

## 8. UI и transport

* Заголовок deployment + connection alias. Несколько подключений к одному
  deployment остаются различимыми, без слияния разных credentialRequirements.
* Две строки Username/Password: переменная приложения, источник, значение,
  reset. Переиспользовать CredentialSourceEditor/secret_bindings/runtime inputs.
  Новый alias не удаляет прежнюю переменную пакета; явно сохранить это поведение.
* PostgreSQL/ClickHouse таблица БД | Права | Изменить/Удалить; кнопка «Добавить
  доступ». Диалог выбирает ресурс БД, фильтрует по provider и исключает повторы.
  PostgreSQL четыре DML checkbox; ClickHouse только SELECT/INSERT.
* Общая подпись current/future + компактное «Создатели объектов» в расширенных
  настройках PostgreSQL. Core-derived owner readonly; роли миграций — явный список.
* Redis/Sentinel commands/keys/channels, add/remove. Owner amendment2026-10-17:
  явно указанные команды, включая административные, задаются оператором;
  Core проверяет typed format, без command allowlist/denylist. Произвольные ACL
  строки не вводятся; см. [план](../../redis-command-policy-plan.md).
* Draft/Review/Save/reset/dirty/navigation существующие. Удаление доступа не
  выполняет target mutation до обычного утверждённого Apply.
* Runtime password скрыт, ввод inline; runtime values не попадают в Review,
  проект, audit, события. После смены источника Save → новые descriptors →
  существующий lease. Не менять Vault paths, stored username/password и Agent.
* Go только transport/writer структуры. SQL/семантика/списки разрешённых прав —
  Core/provider capability, не независимый React resolver.

## 9. Последовательность работ и QA

S1: контракт + нормализация + совместимость/negative fixtures, затем provider.
S2: Apply/Verify/reconcile существующими шаблонами, тест manual inventory.
S3: тонкий adapter/writer при необходимости + компактный UI/обновление макета.
S4: independent FULL DIFF, owner-approved targeted recheck только при blockers,
затем focused/regression/real acceptance по QA и runtime-bundle процедурам.

| Проверка | Ожидаемый результат |
| --- | --- |
| Legacy fixture без нового поля | Прежний plan/Apply/Verify, без расширения grants |
| 1 PG УЗ, 4 БД; 1 CH УЗ, 2 БД | Один credential/account claim, корректные разные права |
| Повтор Apply | changed=0, OIDs/пароли/KV versions/контейнеры/endpoint metadata стабильны |
| Существующие схемы/таблицы/sequence/public | Пакетные grants и реальная операция под app LOGIN |
| После Apply создать схему/таблицу/sequence как owner и migration role | Доступ без повторного Apply; DELETE/UPDATE запрещены там, где не выбраны |
| CREATE через членство без SET ROLE / новая неизвестная роль | Нет ложного обещания inheritance; отрицательный тест |
| Удалить БД-доступ, право, creator role | Отзыв owned grants/default ACL; чужое не затронуто |
| Удалить последнюю строку при стандартном PUBLIC ACL | БД остаётся в reconcile job; DML/default grants сняты, PUBLIC CONNECT не изменён |
| Чужая ownership/ACL, PUBLIC/role membership, cross-provider ref | Безопасный отказ/конфликт, не скрытая эскалация |
| Existing mode, RLS, system schemas | Прежние guards; нет BYPASSRLS/DDL/admin rights |
| Redis и Sentinel | Реальные разрешённые/запрещённые команды, keys/channels отдельно |
| Runtime secret | Provider создаёт УЗ; Vault хранит username/password; Agent materializes существующие binding variables |
| Реальный React/Wails | Add/Edit/Delete/reset/Save/reopen, dirty guard, скрытые passwords; visual 1024/1440 |

Python/Ansible проверки только на RED OS из current tree через qa-sync.
Target QA ограничить owned fixture: реальные library Apply→Verify без infrastructure
Apply и параллелизма; базовые сервисы не переустанавливать. Замерить весь Apply,
provider phase и количество SQL/SSH вызовов; не создавать benchmark framework.
Свежий verified bundle стандартно publish перед зависимым Wails QA.
После QA безопасные evidence/hash, аудит известных secret values (только counts/
paths), удаление только owned временных ресурсов после проверки ownership/данных.
Не удалять чужие схемы, данные, PKI, runtime cache или bootstrap credentials.

## 10. Gate и документация

Independent FULL PLAN review: APPROVE_WITH_CHANGES, 0 blockers. Проверенный
исходный SHA256 A57EB9298A53A860FA79C4A0DDEA9CFC7A8F122A7B6E4AE8CE48AD29D5505CC1,
HEAD adc491da19f44802389a3aa5eb127081522c3ed7. Неблокирующие SEC-P01
(границы effective ACL/PUBLIC CONNECT) и SEC-P02 (reconcile job scope) уточнены
в разделах 6 и 9 после review; повторный review не проводился и не требуется
для этих ограниченных уточнений. Это не DIFF review и не QA PASS.

HIGH-RISK: версия контракта и управляемые права. Один independent FULL PLAN
review до представления владельцу; approval плана отдельно от DIFF/QA acceptance.
Обновить существующие project/Core contracts, capability/schema fixtures,
UI design/mockup, ADR/roadmap при изменении границы и текущую строку CURRENT_STATE
при авторизации реализации. Не объявлять текущую UI-only работу Core PASS.

Официальная SQL опора: [GRANT](https://www.postgresql.org/docs/15/sql-grant.html),
[ALTER DEFAULT PRIVILEGES](https://www.postgresql.org/docs/15/sql-alterdefaultprivileges.html).
SQL примеры иллюстративны: production использует существующие identifier/literal
фильтры, текущую выбранную версию сервиса и provider capability.
