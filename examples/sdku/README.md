# SDKU: пакеты из действующей установки

Источник: `192.168.56.107:/data/manifests/scada`, прочитан по SSH 2026-10-16.
Пароль SSH и значения секретов в комплект не включены. Исходные контейнеры не
изменялись. Core/UI и проверенный runtime поддерживают library defaults.
Текущее состояние установки описано в [CURRENT_STATE](../../CURRENT_STATE.md),
результаты последовательных запусков на101/102/103 — в
[журнале SDKU](../../docs/work/application-libraries/evidence/sdku-sequential-applications-journal.md).
По указанию владельца frontend исключён из текущего прогона.

## Состав

- `application-packages/<name>/1.0.0/` — 26 независимых пакетов приложений.
- `library-packages/sdku/1.0.0/` — рецепт библиотеки с необязательными слотами.
- `import-catalog.json` — kind/name/version и SHA-256 каждого пакета для импорта.
- `source-inventory.json` — соответствие исходным манифестам, образам и известные
  незаполненные параметры. Image ID — наблюдение источника, не offline image lock.
- `configuration/` — примеры обычных Ansible group_vars и host_vars.

Исключены cadvisor, gitlab-runner, iperf, pgadmin, portainer, cspa-impexp,
hydro-calculation, hydro-history-and-model, hmi-frontend-hydrocyclone.
Общие HMI-компоненты сохранены, в том числе их прикладные имена ENV с префиксом CSPA.
`ham-backend` и `hmi-frontend-viewer-noszi` сохранены как отдельные альтернативные
пакеты. Не включайте альтернативы одновременно без проверки портов и назначения.
Исправлено имя пакета `kafka-ch-replicator`; ссылка на исходный образ с именем
`kafka-ch-replicatior` сохранена буквально.

## Структура и переопределения

Владелец уточнил: общие defaults принадлежат библиотеке, собственные — приложению,
переопределения экземпляров находятся только в group_vars.
[План расширения Core/UI](../../docs/work/application-libraries/library-common-defaults-plan.md)
описывает реализованные library defaults и library instance overrides.

```text
application-packages/hmi-backend/1.0.0/
  application.yml
  roles/application_hmi-backend/defaults/main.yml
  roles/application_hmi-backend/templates/compose.yml.j2
  roles/application_hmi-backend/templates/agent.hcl.j2
library-packages/sdku/1.0.0/
  library.yml
  roles/library_sdku/defaults/main.yml
  roles/library_sdku/templates/.base_compose.yml.j2
```

Последовательность Core:

1. Defaults библиотеки: общие environment/parameters.
2. Defaults приложения: собственные ENV/parameters, образ, команда, ports, readiness, secret bindings.
3. `group_vars`: общие `applicationLibraryDeployments.<library>.overrides`.
4. `group_vars`: индивидуальные `applications.<slot>.overrides`.
5. Вычисляемая Core identity. Размещение — membership в host_vars.

В `platform_library_definition.defaults.environment` находятся 48 общих ENV.
В 26 slots нет overrides; 8 frontend-слотов явно задают inherit_defaults=false.
Собственный JAVA_OPTS сохраняется в defaults соответствующего приложения.
Base Compose получает общую карту через Core projection
`library_runtime.defaults.environment`, без чтения любого application slot.
Backend Compose наследует `backend` и записывает отличия. Frontend использует
отдельный сервис `base`, без backend ENV и Vault Agent.

Общие и индивидуальные переопределения находятся прямо в group_vars, без YAML-якорей.
Пример в
[`configuration/group_vars.yml.example`](configuration/group_vars.yml.example).
UI содержит вкладку «Общие параметры» библиотеки. Наследуемые значения приложения
берутся из свежего Core snapshot; при изменениях/Reset требуется новая проверка
сохранённого проекта. React не вычисляет precedence или Ansible expressions.

Перенос библиотечных defaults меняет digest пакета. Для другой установки лучше
сохранить пакет неизменным и добавить overrides в её group_vars. ID экземпляра
приложения вычисляет Core: `<application>-<library-id>`.

## Vault Agent

Backend entrypoint: `/usr/bin/vault agent -config=/opt/vault/agent.hcl`.
Пакетный `agent.hcl.j2` использует штатный фильтр `platform.core.application_agent_config`.
Agent получает AppRole/политику/путь KV и CA из Core и запускает исходную команду
образа в режиме process supervisor. Frontend сохраняет исходную команду образа.

Секретные переменные передаются дочернему процессу через Agent. Их значений нет
в Compose, package defaults и исходном `.env`. Каждый backend объявляет собственные
managed accounts и grants для используемых БД и Redis client.
Для развёртывания с Sentinel экземпляр дополнительно задаёт его connection alias,
managed account/grants и привязки Sentinel ENV в group_vars; standalone не требует Sentinel.
Secret bindings ссылаются на account/field. УЗ создаёт штатный утверждённый план;
индивидуальные пароли runtime_secret_ref вводятся только через runtime lease.
Имя УЗ по умолчанию выводится из имени экземпляра приложения; параметры экземпляра
можно переопределить в group_vars. Общим остаётся пароль Java stores из PKI binding.

## Импорт в UI

Для Core Verify требуется runtime с новой поддержкой. Старый bundle отклоняет
defaults/inherit_defaults; локальные импорт и Save сами по себе его не обновляют.

В существующем импорте пакета выбрать каталог **`examples/sdku`** как корень
источника, затем kind/name/version и digest из `import-catalog.json`.
Сначала импортировать необходимые приложения, затем `sdku@1.0.0`.
Создать экземпляр библиотеки, выбрать Docker deployment, размещение и bindings;
включать только нужные слоты. Сохранение и Project Verify используют штатные
Core/Go/UI контракты. Никакого специального SDKU-кода в React нет.

## Перед будущим запуском

- Для `ham-backend`, `hmi-frontend-viewer-noszi`, `iec60870`, `sdku-knp` точная
  команда указанной версии образа не найдена. Указать **argv-массив** в
  `overrides.command` после проверки именно этого образа. Заглушка намеренно
  требует `sdku_start_commands`, без выдуманной команды и автоматического pull.
- Заполнить пустые `parameters.source_variables`: внешние URL, Schema Registry,
  адреса приложений и другие исходные `${VAR}`. Пустое обязательное значение
  останавливает разрешение, а не возвращает адрес старого стенда.
- Заполнить `parameters.mount_sources` для файлов/данных. Для frontend нужны
  корректные существующие TLS-файлы; приватные ключи с источника не переносились.
- Выбрать bindings `database`, `analytics`, `cache`, `messaging`, `secrets` и
  `application-pki`. Создание БД/прав не выводится автоматически из ENV:
  ресурсы и accounts надо объявить через существующие формы/vars, либо явно
  выбрать существующие credentials.
- Проверить TLS-профили приложений: исходный base имел SSL=false, JKS/cacerts,
  а Core материализует PKCS12. Пути адаптированы к Core; поддержку формата и
  правильные SSL/type параметры конкретных образов ещё предстоит подтвердить.
  Выбор Kafka CLIENT_SSL в bindings сам по себе не меняет эти параметры.
- Проверить Redis connection type/Sentinel, ClickHouse HTTPS и клиентские URL,
  доступность Schema Registry, внешние приложения, порты и права пользователя
  контейнера на runtime PKI/Agent файлы.
- Образы не скачаны и не упакованы в offline bundle. Реальные UI Import/Save,
  Project Verify всего проекта, Compose render на целевом runtime и запуск
  приложений в текущей работе не подтверждались.

Подробности структурной проверки: [validation.md](validation.md).

Shared Kafka/Redis/Registry addresses are rendered once into the library base
Compose from Core-resolved bindings. Registry lists all enabled HTTPS targets.
Application Compose retains only own ENV and explicit differences. Generated ENV
keys and values use double quotes. Compose preserves the original image name;
its delivered and running image IDs remain locked and verified.

Existing generated `SERVER_ID` is passed from `.env` through base-compose.
Kafka client IDs include the application instance and `SERVER_ID`; alarm-service
static `group.instance.id` also includes `SERVER_ID`. Consumer `group.id` and
Streams `application.id` remain shared by replicas of the same application.
`tn-scada.kafka.listener.store-id` uses `SERVER_ID` to separate manually assigned
compact loaders from the main consumer group; their offset commits must not
reuse the active subscription group's membership.
HTTP container healthchecks use `curl --fail`, so an HTTP503 response cannot
pass merely because one component in its JSON body has status UP.

Library runtime_directory can be overridden in group_vars; by default it is
~/<library instance ID> under the target Docker account. Empty resets to package
default. Existing directories are not moved or removed automatically.

Evo user inputs use the application's «Файлы» / `config_files` list. Source paths
are relative to the package allowlist; destination `imitator/lib/user.jar`, for
example, is delivered under the instance's `config/` and mounted read-only at
`/usr/local/app/imitator/lib/user.jar`. No manually prepared host directories are
required. Set the matching main class and source/JAR paths for the chosen inputs.
The QA-only `qa/evo-manager/src/qa/sdku/StartupMock.java` logs
`SDKU_EVO_MOCK_STARTED` through `main(Evo)` without accessing tags or Kafka data.
It does not replace the original Evo image or production scripts.
