# Конфигурация — предлагаемый формат

Примеры не являются готовым к запуску контрактом. Имена полей должны быть
согласованы со схемами проекта и service packages до реализации.

## Defaults приложения

```yaml
platform_application_definitions:
  apigateway:
    version: "1.0.0"
    compose_template: apigateway.compose.yml.j2
    defaults:
      image: "registry.example/apigateway@sha256:<digest>"
      user: "1000:1000"
      restart: unless-stopped
      ports:
        http: {container: 10101, published: 10101}
      parameters:
        log_level: INFO
        request_timeout_ms: 30000
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

## Экземпляр в group_vars

```yaml
platform_desired_state:
  applicationLibraryDeployments:
    sdku-main:
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
        apigateway-sdku:
          applicationRef: apigateway@1.0.0
          overrides:
            ports:
              http: {published: 18081}
            parameters: {log_level: DEBUG}
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
              grants:
                - schema: api
                  tables: [requests, responses]
                  privileges: [SELECT, INSERT, UPDATE]
          credentials:
            mode: generated-static
            vault_binding: secrets
```

Размещение — в host_vars целевого хоста, предварительный формат:

```yaml
platform_application_libraries:
  sdku-main: {}
```

Ресурсы и экземпляры могут первоначально приходить из рецепта библиотеки;
group_vars хранит только нужные изменения. Форма привязки recipe slot к
пользовательскому ID экземпляра ещё требует детализации схемы.

## Композиция и идентичность

Ansible разрешает каждый вход штатно. Общая роль затем соединяет defaults
приложения, recipe overrides и instance overrides через явный
`combine(recursive=true, list_merge='replace')`. Словари объединяются, списки
заменяются. Скрытого удаления через null нет. `applicationRef` сам не выполняет merge.

`application_instance_id` берётся из ключа `apigateway-sdku`; все перечисленные
`identity_environment` автоматически получают этот ID. Нельзя независимо
переопределять их через environment. Проекции ограничены текущим instance,
чтобы значения не переходили к следующему элементу Ansible loop.

Шаблон пакета материализует service key через Jinja, а не `${...}` в YAML-ключе:

```yaml
services:
  {{ application_instance_id }}:
    extends:
      file: .base_compose.yml
      service: base-application
    image: {{ application_effective.image | to_json }}
    environment:
{{ application_environment | to_nice_yaml(indent=2) | indent(6, true) }}
    ports:
      - "{{ application_effective.ports.http.published }}:{{ application_effective.ports.http.container }}"
```

## Общий base Compose

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
Один вызов Compose не даёт отдельной области `${SERVER_ID}` каждому service.

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
