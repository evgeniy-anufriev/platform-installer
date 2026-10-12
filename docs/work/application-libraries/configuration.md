# Конфигурация — предлагаемый формат

Примеры не являются готовым к запуску контрактом. Имена полей должны быть
согласованы со схемами проекта и service packages до реализации.

A1 формализует сокращённый standalone контракт в
[fixture](../../../examples/valid/application-libraries/README.md): package defaults
используют `platform_application_definition` / `platform_library_definition`,
деплойменты выбирают recipe slots (например `gateway`), serviceType — точный ID
существующего каталога. Остальные примеры этой главы описывают будущие этапы;
они не означают готовые apply hooks или поддержку UI.

## Defaults приложения

```yaml
platform_application_definitions:
  apigateway:
    version: "1.0.0"
    compose_template: apigateway.compose.yml.j2
    defaults:
      image: "registry.example/apigateway@sha256:<digest>"
      command: ["/opt/{{ application_name }}/bin/{{ application_name }}"]
      user: "1000:1000"
      restart: unless-stopped
      ports:
        http: {container: 10101, published: 10101}
      parameters:
        log_level: INFO
        request_timeout_ms: 30000
        redis:
          user: "{{ application_instance_id }}"
          password_ref: "{{ application_instance_id }}-redis-password"
      accounts:
        redis:
          mode: managed
          credentials:
            username:
              source:
                kind: literal
                value: "{{ application_parameters.redis.user }}"
            password:
              source:
                kind: runtime_secret_ref
                ref: "{{ application_parameters.redis.password_ref }}"
      environment:
        SERVER_ALLOWED_ORIGINS: "*"
      endpoint:
        enabled: false
        listener: http
        haproxy:
          backend:
            balance: roundrobin
            health_check:
              enabled: true
              type: http
              method: GET
              path: /actuator/health
              expected_status: 200
              interval: 5s
              fall: 3
              rise: 2
            connection:
              maxconn: 100
              connect_timeout: 5s
              server_timeout: 60s
            tls: {enabled: false}
    connections:
      postgres: {library_binding: database}
      kafka: {library_binding: messaging}
      redis: {library_binding: cache}
      clickhouse: {library_binding: analytics}
      vault: {library_binding: secrets}
    identity_environment:
      - EVO_MANAGER_APP_ID
      - KAFKA_APPLICATION_ID_CONFIG
      - KAFKA_LISTENER_ID_CONFIG
```

Дополнение `defaults.provisioner` описано в [секретах](secrets.md).
Образ/команда и необходимые runtime defaults принадлежат пакету, не schema/UI.
`application_name` берётся из определения, выбранного через `applicationRef`:
для `apigateway@1.0.0` это `apigateway`. Ansible материализует command из defaults
пакета; для экземпляра `apigateway-cspa` результат будет
`["/opt/apigateway/bin/apigateway"]`. Имя бинарного приложения не извлекается
разбором ID экземпляра. Пакет с другой структурой образа задаёт свой command,
поэтому путь `/opt/<name>/bin/<name>` не становится обязательным для всех образов.

## Экземпляр в group_vars

### Выбор интерфейса подключения по serviceType

`connectionRef` находится в defaults библиотеки, в `connection_defaults`,
ключом которого является существующий `serviceType` пакета инфраструктуры.
Bindings экземпляра выбирают deployment через `deploymentRef`, не повторяя
выбор listener для каждого deployment. Ниже сокращённые имена serviceType;
при формализации используются точные идентификаторы существующего каталога:

```yaml
# Library role defaults
connection_defaults:
  kafka:
    connectionRef: CLIENT_SSL
  postgresql: {}
  redis: {}
  clickhouse: {}
```

`CLIENT_SSL` — пример явно настроенного Kafka listener, не встроенное имя.
Он должен существовать в effective `configuration.listeners` deployment и
иметь `purpose: client`. Group_vars переопределяет выбор один раз для всех
deployments этого serviceType в данном экземпляре библиотеки:

```yaml
platform_desired_state:
  applicationLibraryDeployments:
    sdku:
      connection_defaults:
        kafka:
          connectionRef: EXTERNAL_SSL
      bindings:
        messaging: {deploymentRef: kafka-main}
```

Core определяет serviceType выбранного deployment, применяет library defaults
с overrides и разрешает интерфейс существующей runtime-проекцией сервиса.
Для Kafka effective `connectionRef` обязателен. Для других providers он может
отсутствовать, если есть ровно один подходящий клиентский интерфейс/порт после
фильтрации по назначению и протоколу, требуемым приложению. Несколько подходящих
интерфейсов требуют явного выбора в defaults соответствующего serviceType.
Неизвестный или несовместимый connectionRef блокирует validation; нет выбора
первого listener и нет fallback на другой порт. TLS и noTLS на одном порту
не различаются только connectionRef: используются effective TLS-параметры
сервиса и требования приложения. Фактические адреса/порты не дублируются в vars
библиотеки и не берутся безусловно из manifest defaultPort.

Назначения Redis и Sentinel различаются в описании connections приложения.
Одно значение connectionRef для Redis не переключает эти назначения; если
значение задано, оно должно быть совместимо с каждым использующим его
подключением. Одновременные Redis/Sentinel bindings без явного connectionRef
разрешаются отдельно по требуемому назначению. Не вводить отдельные defaults
по deployment и новый каталог интерфейсов.

Первоначальная поддержка: PostgreSQL `client`, Redis `client`/`sentinel`,
ClickHouse `client`, Kafka — точное имя клиентского listener. ClickHouse `native`
подключается только после реализации корректной effective проекции.

### Приложения без секретов

Все инфраструктурные hooks условные: отсутствие соответствующего service ref
в effective конфигурации означает пропуск hook. Ссылка через library binding
учитывается как service ref; весь набор сервисов не обязателен. Для вызова нужны
и ссылка, и декларация действия. Неверная заданная ссылка или действие с
обязательной, но отсутствующей ссылкой блокируются validation; подробнее
в [последовательности выполнения](execution.md#общие-provider-hooks).

Наличие непустого effective `accounts` — условие включения credential provisioning.
Исходное описание находится в defaults приложения; условие проверяется после
разрешённых overrides. Если `accounts` отсутствует или пуст, не выполняются
account/grants hooks и запись credential-секретов аккаунтов в Vault.
Непустой effective `secret_bindings` включает Vault Agent: нужны Vault ref,
policy/AppRole, доставка RoleID, `agent.hcl` и Agent volumes. Если bindings пусты,
Agent не нужен; контейнер запускает обычную команду приложения.
Ресурсы библиотеки, nonsecret подключения и endpoint HAProxy/DNS выполняются
по собственным декларациям и не зависят от наличия accounts.

Приложение может использовать account- и shared-секреты одновременно либо только
shared-секреты без accounts. Каждая запись `secret_bindings.*.source` выбирает
строго один вариант: `{account, field}` либо `{library_secret}`. Пустые,
неполные, смешанные и несуществующие ссылки блокируют validation. Для account
Core вычисляет путь документа Vault и проецирует credential field в поле секрета;
повторять путь в пользовательских parameters не требуется.

```yaml
platform_desired_state:
  applicationLibraryDeployments:
    sdku:
      libraryRef: sdku@1.0.0
      runtimeRef: docker-apps
      bindings:
        database: {deploymentRef: postgres-sdku}
        messaging: {deploymentRef: kafka-main}
        cache: {deploymentRef: redis-main}
        analytics: {deploymentRef: clickhouse-main}
        secrets: {deploymentRef: vault-main}
        application_pki: {profileRef: apps-pki}
      resources:
        applicationDatabase:
          kind: postgresql.database
          binding: database
          parameters: {name: sdku}
      applications:
        apigateway:
          overrides:
            ports:
              http: {published: 18081}
            parameters:
              log_level: DEBUG
              redis:
                user: test-user
                password_ref: my-redis-password
            endpoint:
              enabled: true
              endpoint_group: applications
              haproxy:
                backend:
                  health_check: {path: /ready, interval: 10s}
                  connection: {server_timeout: 120s}
          accounts:
            postgres:
              mode: managed
              databaseRef: applicationDatabase
              credentials:
                password:
                  source: {kind: generated}
              grants:
                - schema: api
                  tables: [requests, responses]
                  privileges: [SELECT, INSERT, UPDATE]
          credentials:
            vault_binding: secrets
```

Варианты начального значения password (`generated`, `runtime_secret_ref`,
`vault_ref`) приведены в [секретах](secrets.md#первоначальные-значения-секретов).

Обычная настройка Redis — только `overrides.parameters.redis.user` и
`password_ref`. Account descriptor, mode, source kind, права и secret bindings
принадлежат defaults приложения; редкие изменения разрешены через явный override
`accounts`. `application_parameters` обозначает итоговые parameters после merge;
ссылки descriptor разрешает Ansible после этого merge. Явный override descriptor
имеет приоритет над соответствующим значением defaults. `kind: literal` здесь
разрешён для nonsecret username, но не для пароля. `password_ref` — ссылка на
защищённый runtime-ввод, а не plaintext пароль.

Размещение библиотеки задаётся обычным inventory: хост включён, когда его
`host_vars` содержит `platform_application_libraries.sdku`. Существующий
ID хоста (`inventory_hostname`, имя записи `host_vars`) автоматически становится
`SERVER_ID` для исходного Compose. Предварительный формат для `node-app-1`:

```yaml
platform_application_libraries:
  sdku: {}
```

Такая же запись находится в `host_vars/node-app-2`. Core разрешает размещение
из inventory/host_vars и проверяет наличие Docker runtime на обоих хостах.
Повторять `SERVER_ID` в каждом приложении библиотеки не требуется.

Ресурсы и экземпляры могут первоначально приходить из рецепта библиотеки;
group_vars хранит только нужные изменения. Ключ `applications` выбирает slot
библиотеки; ID приложения автоматически вычисляется из имени определения и
ID экземпляра библиотеки. Повтор одного application definition в нескольких
slots в начальном scope запрещён из-за коллизии вычисляемого ID.

## Композиция и идентичность

Производное имя Compose project включает project/library/instance/host и
проверяется по `^[a-z0-9][a-z0-9_-]*$`. Точки в компонентах допустимы для общей
грамматики ID, но блокируют Compose projection с
`APPLICATION_COMPOSE_PROJECT_INVALID`. Скрытого преобразования ID нет.

Ansible разрешает каждый вход штатно. Общая роль затем соединяет defaults
приложения, recipe overrides и instance overrides через явный
`combine(recursive=true, list_merge='replace')`. Словари объединяются, списки
заменяются. Скрытого удаления через null нет. `applicationRef` сам не выполняет merge.

`application_instance_id` вычисляется как `application_name ~ '-' ~ library_instance_id`:
для приложения `apigateway` и библиотеки `sdku` это `apigateway-sdku`. Все перечисленные
`identity_environment` автоматически получают этот ID. Нельзя независимо
переопределять их через environment. Проекции ограничены текущим instance,
чтобы значения не переходили к следующему элементу Ansible loop.
Этот ID логический и одинаков для размещений на разных хостах. Отдельно Ansible
берёт `inventory_hostname` текущего хоста и добавляет `SERVER_ID`
в его несекретный `.env`. Если конкретному приложению нужен уникальный на хосте
application ID, его defaults должны явно задать правило формирования из
`application_instance_id` и `SERVER_ID`; нельзя молча добавлять суффикс ко всем
переменным, особенно к Kafka application/group ID.

Шаблон пакета материализует service key через Jinja, а не `${...}` в YAML-ключе:

```yaml
services:
  {{ application_instance_id }}:
    extends:
      file: .base_compose.yml
      service: base-application
    image: {{ application_effective.image | to_json }}
    hostname: {{ application_instance_id }}-${SERVER_ID}
    container_name: {{ application_instance_id }}-${SERVER_ID}
    environment:
{{ application_environment | to_nice_yaml(indent=2) | indent(6, true) }}
    ports:
      - "{{ application_effective.ports.http.published }}:{{ application_effective.ports.http.container }}"
```

## Общий base Compose

### Исходный пользовательский `.env`

Библиотека поставляется с общим `.env` в portable package, например
`library-packages/sdku/1.0.0/files/.env`. Этот файл — desired input библиотеки:
в нём сохраняются пользовательские несекретные параметры, которым не нужна
проекция из Ansible. Он включается в revision/package fingerprint и перенос проекта.
Файл не должен быть заменён целиком набором только вычисляемых переменных.

При materialization Ansible использует исходный `.env`, сохраняет пользовательские
ключи и добавляет/обновляет только явно объявленные projection keys, например
`SERVER_ID` и infrastructure bindings. Эти reserved keys контролируются Ansible;
конфликт с пользовательским значением выявляется явно, без случайного precedence.
Для instance-specific изменения обычных ключей служат documented vars overrides
в environment приложения; отдельный исходный `.env` экземпляра не создаётся.
Редактирование library package `.env` влияет на его consumers и меняет revision.
Runtime `.env` создаётся один на сочетание project/library/host и используется
всеми Compose-запусками экземпляров этой библиотеки на хосте; его ручное изменение
не становится новым desired state. Пароли и RoleID в исходном `.env` запрещены.
В A1 определить поддерживаемый dotenv syntax и тесты сохранения пользовательских
значений; не писать универсальный dotenv parser ради неподдерживаемых форматов.

По пользовательским примерам приложения наследуют `.base_compose_test.yml`.
Имя/имя базового service задаются контрактом пакета, без обязательного
переименования существующих исходников. Например, с сокращённым именем:

```yaml
# .base_compose.yml — производная общая конфигурация библиотеки
services:
  base-application:
    environment:
      SPRING_DATASOURCE_URL: ${PG_JDBC_URL}
      SPRING_KAFKA_BOOTSTRAP_SERVERS: ${KAFKA_SERVERS_SSL}
      TN_SCADA_REDIS_HOST: ${REDIS_HOST}
      DB_CONNECTION_STRING: ${CLICKHOUSE_JDBC_URL}
```

Core/Ansible проецирует общие bindings в этот файл и несекретный `.env`.
Исходный application manifest содержит только собственные настройки и extends.
Compose выполняет интерполяцию и наследование. Environment приложения может
перекрывать базовый: Core обязан выявить конфликт с заявленным binding.
Запуск использует явный `--env-file` и контролируемое окружение shell.
Для каждого Docker-хоста Ansible формирует общий библиотечный `.env` с его `SERVER_ID`
и локальный Compose project. Например, исходный `container_name:
apigateway-sdku-${SERVER_ID}` остаётся шаблоном Compose и даёт разные имена
на `node-app-1` и `node-app-2`. Один вызов Compose не даёт отдельной области
`${SERVER_ID}` каждому service. На одном хосте все приложения библиотеки получают
один SERVER_ID; различие логических экземпляров задаёт их instance ID.

## Endpoint

Backend defaults принадлежат приложению и переопределяются в instance overrides.
Не создавать второй renderer HAProxy: значения отображаются в существующий
provider contract. Host/port выводятся из placement и published port listener.
Client-to-HAProxy TLS и HAProxy-to-container TLS задаются раздельно.
HTTP backend не получает ssl=true лишь из-за defaults другого infra service.
При выключенном endpoint публикация не выполняется. Удаление ранее опубликованного
endpoint после выключения — отдельный видимый reconcile, не обещанный побочный эффект.

Справка: [Compose extends](https://docs.docker.com/reference/compose-file/services/#extends),
[interpolation](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/).
