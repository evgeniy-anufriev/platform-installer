# Подготовка и установка — черновик

Контекст: консолидированное проектное предложение с уточнениями разных этапов.
Scope конкретного контракта и evidence выбирайте по [индексу](contract-index.md);
примеры будущих этапов не подтверждают реализацию или разрешение работ.

## Общие provider hooks

Граница вызова едина для всех следующих hooks: один resource batch на библиотеку,
один account/grants/secret/endpoint hook на логический экземпляр приложения.
Не объединять разные библиотеки и экземпляры в provider-wide mutation batch.
Общий read-only discovery provider можно переиспользовать в одном invocation.
Docker placements не размножают logical resource/account hooks; host materialization
и host-specific endpoint targets сохраняют необходимую привязку к хостам.
Правило уточнено владельцем 2026-10-10; benchmark сравнения отменены.

Перед подготовкой подключений Core определяет serviceType каждого binding
deployment и применяет `connection_defaults` библиотеки с overrides.
Kafka требует явный connectionRef; остальные providers допускают отсутствие
selector только для единственного интерфейса, подходящего назначению и протоколу
connection приложения. Разрешение использует существующие effective listeners,
адреса, ports и TLS; неоднозначность или несовместимость блокирует validation.
Выбор общий по serviceType внутри библиотеки, не отдельный для каждого deployment.
См. [конфигурацию](configuration.md#выбор-интерфейса-подключения-по-servicetype).

Общее условие для любого provider hook — наличие соответствующей ссылки
на инфраструктурный сервис в effective конфигурации. Отсутствующий service ref
(в том числе отсутствие deploymentRef через library binding) означает SKIP
соответствующего hook. Не подбирать сервис автоматически и не требовать весь
набор инфраструктуры для каждого приложения. Заданная, но неразрешимая ссылка —
ошибка validation, а не SKIP. Hook вызывается только при наличии также декларации
нужного действия: resource, account, secret или endpoint. Ссылка сама по себе
не является командой создания ресурса.

Если объявлено действие, требующее отсутствующего service ref, validation
блокирует выполнение с точным полем: нельзя молча пропустить обязательную
зависимость. Для HAProxy и DNS условия проверяются отдельно; включённый endpoint
проверяется по требованиям выбранного режима публикации. Account hooks требуют
соответствующего account и provider ref, Vault hook — Vault ref и secret demand;
Agent требуется при непустом effective secret_bindings.

Шаги account provisioning и Vault Agent условные: если effective `accounts`
отсутствует или пуст, hooks создания УЗ/grants и credential-секретов пропускаются.
Непустой secret_bindings требует Vault ref и включает policy/AppRole/RoleID,
Agent файлы/volumes, включая shared-only без accounts. При пустом bindings
контейнер запускается напрямую штатной командой приложения. Library resources
и endpoint hooks сохраняют независимые условия. Каждая source выбирает один
источник: account+field либо library_secret; разные bindings могут использовать оба.

Приложение или библиотека объявляет типизированный ресурс, например
`postgresql.database`, `postgresql.account`, Kafka principal/ACL, Redis ACL user.
Core разрешает binding и вызывает объявленный capability provider package.
Все приложения используют один PostgreSQL entrypoint и общие tasks, без веток
по имени приложения. SQL/выбор writable primary/permissions принадлежат PostgreSQL.
Для каждого другого provider действует тот же принцип; универсального SQL/command
движка для всех сервисов нет. Неподдерживаемый capability блокирует запрос.

Обычный env `DB_USER` не вызывает мутацию: нужна явная декларация account/resource.
Общие addresses не означают общие УЗ. Создание БД отдельно от УЗ и grants.
Подключение existing resource не даёт права его менять или захватывать.

## Порядок

В общем плане сначала выполняются Apply/Verify **всех включённых в план
инфраструктурных сервисов**, затем отдельный этап «Библиотеки приложений».
Это глобальный барьер, а не только ожидание непосредственных dependencies
конкретной библиотеки. Ошибка/отмена/незавершённость первого этапа блокирует
library mutations. План и approval общие; отдельного скрытого запуска нет.
Подробнее: [подэтап A8 общего плана](implementation-plan.md#a8-интеграция-библиотек-в-общий-план-выполнения).

1. Target-free resolve/validate: пакеты, references, capabilities, placement,
   port conflicts, TLS, DAG, required runtime credential references.
2. Fresh authoritative plan фиксирует revision/runtime, операции и provider hosts.
   Нет registry/target probes и выбранного live source в target-free плане.
3. После approval execution preflight проверяет фактические условия и ownership.
4. Завершается инфраструктурный этап: Apply/Verify всех его deployments,
   включая выбранные runtime/providers; проверяется image closure. Только после
   успешного барьера разрешён переход к следующим действиям библиотеки.
5. Выполняются общие ресурсы библиотеки: БД, схемы, topics, общие Vault-секреты.
6. Барьер: все обязательные действия библиотеки выполнены и проверены.
7. Для экземпляров: credentials, provider accounts/grants, Vault policy/AppRole.
8. Для каждого выбранного Docker-хоста: materialization base Compose, `.env`
   с `${SERVER_ID}` из его inventory ID, instance Compose и agent/config files.
9. На каждом хосте: Compose validation и запуск; Vault Agent получает секреты
   и запускает процесс.
10. Readiness каждого размещения и проверка фактических подключений.
11. Общий endpoint-hook публикует готовые host targets в HAProxy/DNS;
    проверяется внешний endpoint.

Общие ресурсы библиотеки и provider accounts не создаются повторно для каждого
Docker-хоста. Отказ одного размещения виден отдельно и не превращает частично
готовую библиотеку в успешную; автоматический failover/rollback не предполагается.

Provider hooks БД/УЗ/endpoint во втором этапе используют уже установленную
инфраструктуру, а не повторно устанавливают её. Для standalone с ранее
установленными providers обязательна явная readiness проверка. Это не разрешает
новый selective-plan scope Installer.

Фазы входят в существующий DAG, не во второй orchestrator. Миграции, создающие
таблицы, должны предшествовать grants на эти таблицы. Если миграции требуют УЗ,
нужен явный отдельный migration identity/порядок, а не циклическая зависимость.
Readiness не может ждать собственный ещё не опубликованный публичный DNS.

## Secrets и повторы

Общая библиотечная подготовка и instance credentials используют
[секретный контракт](secrets.md). Generated-static пароль не генерируется заново
на каждом запуске. Подготовленная версия должна переживать прерывание защищённо,
а instance запускается только после проверки всех обязательных credentials.
Нет общей транзакции между PostgreSQL/Kafka/Redis/ClickHouse/Vault/Compose.
Частичный успех сохраняется как безопасное evidence; retry сверяет реальное состояние.
Изменение grants/rotation/revocation должно иметь явную семантику плана.

Удаление экземпляра не удаляет БД библиотеки, УЗ или volumes автоматически.
Проверки ownership не основаны лишь на совпадении имени. Ограничения существующего
endpoint partial/full reconcile сохраняются, в том числе неизвестные прежние hosts.

## Endpoint и источники

### Доставка образов

Отдельная фаза перед Compose startup обеспечивает образы на **каждом** Docker-хосте
библиотеки. Если выбран настроенный approved registry — выполняется явный
`docker compose pull`; при offline source архив доставляется из verified bundle
и загружается через `docker load`. Команды обращаются к выбранному rootless daemon
целевого хоста. Затем проверяются image identity/platform и соответствие lock;
`compose up` использует уже подготовленный локальный reference без неявного pull
или build. Bundle архив и загруженный образ имеют разные identities, их нельзя
сравнивать как один digest. Подробный scope: [A2.1](implementation-plan.md#a21-доставка-образов-на-docker-хосты).

### Публикация endpoint

Публикация расширяет существующий apply-endpoint pipeline источником application.
Новые source IDs не пересекаются со старыми service IDs; старые FQDN/ownership
prefixes должны сохраняться. Backend использует доступный HAProxy host published
port, не недостижимый bridge IP. DNS указывает на frontend/VIP.
Missing-provider поведение не меняется скрыто: текущая диагностика/skip сохраняется,
проверка endpoint отдельно сообщает непубликацию; running container не доказывает URL.

Образы фиксируются digest/platform. Execution source policy: совместимый approved
node repository/registry, иначе verified immutable offline artifact, иначе BLOCK.
Archive digest не приравнивается image digest. Нет неявного pull/build/download;
DEV acquisition — отдельное разрешение. Untrusted mounts, privileged/socket/host
namespace требуют явного policy-контракта, не молчаливого исполнения raw Compose.

## Будущая приёмка

- Ручной Ansible без Go/UI/project.yml, стандартные vars и одинаковое разрешение.
- СДКУ/ЦСПА с общим application definition, разными bindings и независимыми IDs.
- Два экземпляра на одном хосте; отсутствие утечки параметров между экземплярами.
- Одна библиотека на двух Docker-хостах: `SERVER_ID` из существующего host ID,
  два локальных Compose-запуска, readiness обоих targets и общий endpoint.
- Барьер библиотеки, общие provider hooks, least privilege, чужие resources.
- Repeat changed=0, interrupted create, retry, rotation, сохранение данных.
- Offline images, digest mismatch, port/TLS conflicts, safe paths, отсутствие secrets в output.
- Реальный Agent bootstrap/restart, инфраструктурные подключения и внешний endpoint.
- Последующая реальная React/Wails Save → plan → approval → Start → terminal/repeat.

Это перечень проверок, не выполненные тесты. QA и target mutations требуют
действующих процедур и разрешённого этапа.

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
