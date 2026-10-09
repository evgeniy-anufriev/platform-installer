# Vault, AppRole и общие секреты — черновик

## Связки приложения

Пакет объявляет точные имена переменных, которые ожидает приложение:

```yaml
platform_application_definitions:
  apigateway:
    defaults:
      provisioner:
        type: vault-agent
        mode: process-supervisor
        auth: {method: approle}
        secrets: {mount: applications}
        secret_bindings:
          SPRING_DATASOURCE_USERNAME:
            source: {account: postgres, field: username}
          SPRING_DATASOURCE_PASSWORD:
            source: {account: postgres, field: password}
          KAFKA_PASSWORD:
            source: {account: kafka, field: password}
          TN_SCADA_REDIS_ACL_PASSWORD:
            source: {account: redis, field: password}
          CLICKHOUSE_PASSWORD:
            source: {account: clickhouse, field: password}
          JAVA_KEYSTORE_PASSWORD:
            source: {library_secret: java_keystore_password}
```

`account` связывает credential output provider с переменной. В namespaced Vault
path учитываются project/library/instance/account. Никакого определения источника
по имени переменной или сканирования env. Обычный Compose environment и
secret_bindings не могут управлять одной переменной одновременно.

Дополнительные предлагаемые source kinds: `runtime_secret_ref` для внешнего
runtime-ввода и `vault_ref` для уже существующего секрета. Existing Vault secret
не перезаписывается: хук добавляет только нужный read access и Agent mapping.
Overrides меняют ссылки/настройки, не содержат plaintext values.

## Общие секреты библиотеки

```yaml
platform_library_definitions:
  sdku:
    defaults:
      shared_secrets:
        java_keystore_password:
          source:
            kind: pki_credential
            binding: application_pki
            credential: java_keystore_password
          destination:
            vault_binding: secrets
            mount: applications
            document: shared/java-keystore
            field: password
```

Binding `application_pki` из group_vars должен разрешаться к точному используемому
материалу и credential, не произвольному паролю другого PKI usage. Формат этой
ссылки ещё нужно согласовать с existing PKI materialization contract.

На этапе библиотеки пароль один раз публикуется в её shared path. Экземпляры,
объявившие `library_secret`, получают только read этого пути. Копий пароля в каждом
instance path нет. Другое приложение может связать тот же secret с другим env name.
Если runtime PKI credential уже истёк/недоступен, первоначальная публикация требует
его повторного предоставления; извлечение пароля из keystore не предполагается.
Reuse требует проверки связи с актуальным материалом; rotation согласует Vault
value и версию keystore. Один profileRef может быть недостаточен для разных usages.

## Общий Vault hook

При активных bindings включить в план: resolve sources; ensure managed secret
documents; policy минимального read; AppRole; bootstrap delivery. Vault admin
credential и app identity разделены. AppRole не получает provider admin passwords,
write access или wildcard read всей библиотеки. По каждой операции проверять ownership.

Generated-static mode: provider hooks создают постоянные УЗ, Vault хранит credentials.
Это не динамическое создание пользователей Vault database secrets engine.
Повтор/частичный сбой не должен незаметно менять пароль. Protected staging/version
и порядок ensure/verify нужно детализировать без обещания общей транзакции.

## Vault Agent внутри контейнера

Образ приложения содержит совместимый Agent. Generic provisioning формирует
agent.hcl и безопасные bootstrap references. Agent запускает приложение с env:

```hcl
env_template "JAVA_KEYSTORE_PASSWORD" {
  contents = "{{ with secret \"applications/data/project-01/sdku-main/shared/java-keystore\" }}{{ .Data.data.password }}{{ end }}"
  error_on_missing_key = true
}

exec {
  command = ["/opt/apigateway/bin/apigateway"]
  restart_on_secret_changes = "always"
}
```

Пример KV v2: logical path и API `data/` segment различаются. Agent template syntax
сохраняется при Ansible rendering: нельзя случайно интерпретировать его как Jinja.
`agent.hcl` содержит ссылки, не значения паролей. Token sink без потребности приложению
не добавляется. Secret environment доступен самому процессу: запретить dump env,
санитизировать diagnostics; отсутствие секрета в Compose не означает отсутствие в памяти.

RoleID/SecretID доставляются через защищённый runtime identity механизм. Одноразовый
wrapped bootstrap не решает restart/re-auth автоматически: expiry, reuse и повторная
доставка должны быть явно определены. Нельзя выдавать agent.hcl за полный bootstrap.

`.env`/base Compose содержит только несекретные настройки. `${...}` Compose
разрешается до запуска контейнера, Agent не заполняет его задним числом. Process
supervisor `env_template` и обычные file template blocks не смешивать без проверки
поддерживаемого Agent mode. Literal dotenv для приложения — отдельный вариант,
если оно не поддерживает environment процесса.

Справка: [Agent supervisor](https://developer.hashicorp.com/vault/docs/agent-and-proxy/agent/process-supervisor),
[AppRole auto-auth](https://developer.hashicorp.com/vault/docs/agent-and-proxy/autoauth/methods/approle).
