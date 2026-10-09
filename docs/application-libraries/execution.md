# Подготовка и установка — черновик

## Общие provider hooks

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
8. Материализация base Compose, env, instance Compose, agent/config files.
9. Compose validation и запуск; Vault Agent получает секреты и запускает процесс.
10. Readiness приложения и проверка фактических подключений.
11. Общий endpoint-hook публикует HAProxy/DNS; проверяется внешний endpoint.

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
- Барьер библиотеки, общие provider hooks, least privilege, чужие resources.
- Repeat changed=0, interrupted create, retry, rotation, сохранение данных.
- Offline images, digest mismatch, port/TLS conflicts, safe paths, отсутствие secrets в output.
- Реальный Agent bootstrap/restart, инфраструктурные подключения и внешний endpoint.
- Последующая реальная React/Wails Save → plan → approval → Start → terminal/repeat.

Это перечень проверок, не выполненные тесты. QA и target mutations требуют
действующих процедур и разрешённого этапа.
