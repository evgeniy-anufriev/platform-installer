# Vault, AppRole и общие секреты — черновик

## Связки приложения

Account provisioning включается при непустом effective `accounts` из defaults
после overrides. Vault Agent включается при непустом `secret_bindings`: нужны
Vault ref, policy/AppRole, RoleID и Agent файлы. Поддерживаются одновременно
account- и shared-секреты, а также shared-only без accounts и без создания УЗ.
Каждая source выбирает ровно `{account, field}` либо `{library_secret}`;
пустые, неполные и смешанные источники блокируются validation.
Без secret_bindings приложение запускается напрямую;
см. [условие](configuration.md#приложения-без-секретов).
Общие секреты библиотеки обрабатываются на уровне библиотеки только при наличии
потребителей, а не автоматически для каждого приложения.

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

## Первоначальные значения секретов

Источник значения объявляется отдельно от связи «переменная приложения → account
field». Предлагаемый пример overrides слота `apigateway` библиотеки `cspa`
в `group_vars` (ID экземпляра автоматически получается `apigateway-cspa`):

```yaml
applications:
  apigateway:
    overrides:
      parameters:
        redis:
          user: test-user
          password_ref: my-redis-password
    accounts:
      postgres:
        mode: managed
        credentials:
          password:
            source: {kind: generated}
      clickhouse:
        mode: existing
        credentials:
          password:
            source:
              kind: vault_ref
              binding: secrets
              mount: applications
              document: existing/cspa/clickhouse
              field: password
    credentials:
      vault_binding: secrets
```

Для обычной настройки Redis пользователь задаёт только `parameters.redis.user`
и `password_ref` в overrides. Defaults приложения преобразуют их в username
и `runtime_secret_ref` account descriptor (см. [пример](configuration.md)).
Источник секрета, mode, grants и mapping Vault Agent остаются в defaults с
возможностью редкого явного `accounts` override. Пароль по `password_ref`
поступает через защищённый runtime-ввод, не через project YAML или `.env`.

`generated` создаёт пароль при первом provisioning; защищённый runtime-путь
обеспечивает сохранение результата в Vault и повтор без смены пароля. Interrupted
create/retry не должен генерировать другое значение после создания provider account.
`runtime_secret_ref` получает заданное оператором значение через существующий
runtime credential input. В UI оператор вводит plaintext в отдельном поле секрета;
portable project сохраняет только ref. Standalone передаёт ref через защищённый
runtime-ввод на Execution Node, не через plaintext `group_vars`, аргументы команды
или tracked defaults. Missing/expired ref блокирует provisioning.
`vault_ref` читает существующий документ; он не перезаписывается и не копируется
без необходимости. Для `mode: existing` provider account не изменяется; Agent
получает read на этот путь. Для managed account выбранное значение передаётся
provider hook как runtime credential и согласуется с Vault publication.

Admin credentials providers/Vault вводятся отдельно через существующий runtime
механизм и не попадают в application secret bindings. Общий PKI password использует
`pki_credential`, как в примере ниже. Plaintext поле в portable YAML не вводится.
Имена source/ref здесь — предлагаемый контракт; соответствие существующему
runtime credential API уточняется в A1/A4, новый secret store не создаётся.

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

Для managed документов используется KV v2: после проверки ownership хук читает
текущие данные и версию. Если путь ещё не создан — выполняет `kv put` с CAS=0.
Если документ существует и управляемые поля отличаются — выполняет `kv patch`
только этих полей с CAS текущей версии, сохраняя остальные поля. Одинаковые
значения не вызывают запись и новую версию. CAS conflict требует повторного
чтения и проверки, а не безусловного overwrite. Permission/transport errors и
deleted/destroyed версии не считаются отсутствующим новым секретом.
`vault_ref` остаётся read-only. Изменение account password согласуется с provider
rotation: один `kv patch` не является сменой пароля в Redis/PostgreSQL и других
сервисах. Agent получает только read; create/patch принадлежат provisioning hook.
Справка: [KV patch](https://developer.hashicorp.com/vault/docs/commands/kv/patch),
[KV v2 API](https://developer.hashicorp.com/vault/api-docs/secret/kv/kv-v2).

## Vault Agent внутри контейнера

### Шаблон agent.hcl в пакете приложения

Исходный файл пакета:
`application-packages/apigateway/1.0.0/roles/application_apigateway/templates/agent.hcl.j2`.
Ansible материализует его как `agent.hcl` в runtime volume экземпляра;
Compose монтирует конфигурацию и identity read-only. Defaults этим уточнением
не расширяются. Ниже черновик шаблона; `application_runtime` обозначает
единую производную проекцию, а не дополнительные пользовательские параметры:

```jinja
exit_after_auth = false

vault {
  address = {{ application_runtime.vault.address | to_json }}
  ca_cert = {{ application_runtime.vault.ca_cert_file | to_json }}
}

auto_auth {
  method "approle" {
    mount_path = {{ application_runtime.vault.auth_mount | to_json }}
    config = {
      role_id_file_path = {{ application_runtime.vault.role_id_file | to_json }}
    }
  }
}

{% for binding in application_runtime.vault.env_templates %}
env_template {{ binding.name | to_json }} {
  contents = {{ binding.contents | to_json }}
  error_on_missing_key = true
}
{% endfor %}

exec {
  command = {{ application_runtime.command | to_json }}
  restart_on_secret_changes = "always"
}
```

Адрес Vault и CA-файл берутся из разрешённого library binding/PKI;
auth mount — из конфигурации provider, RoleID file — из runtime identity layout.
`env_templates` строится из `secret_bindings`: имя переменной и Vault template,
например `{{ with secret "applications/data/project-01/sdku/shared/java-keystore" }}{{ .Data.data.password }}{{ end }}`.
Строка `contents` содержит ссылки на секреты, не их значения; подставленную
Vault template строку нельзя повторно рендерить как Jinja. `command` берётся
из разрешённых defaults приложения: для `apigateway-sdku` это
`["/opt/apigateway/bin/apigateway"]`. SecretID в этом режиме не используется.
Vault Agent получает PEM CA-файл; PKCS-хранилища остаются входами приложения.

### AppRole и материализованный файл

По уточнению владельца AppRole экземпляра использует `bind_secret_id: false`:
Agent входит только по RoleID, SecretID не создаётся и не доставляется. Параметр
принадлежит AppRole, а не policy; policy задаёт права чтения секретов. Обязательное
сетевое ограничение роли называется `token_bound_cidrs` (не `token_cidrs`) и
задаёт разрешённые адреса для входа и использования выданного токена. Core
автоматически вычисляет его из хостов размещения экземпляра; пользователь
не вводит CIDR в defaults/group_vars. Для прямого подключения используются
host CIDR: IPv4 `/32`, IPv6 `/128`. Для одной роли на нескольких хостах берётся
объединение адресов этих хостов, а не вся общая подсеть.

```yaml
# Предлагаемые defaults provisioner; token_bound_cidrs — производная проекция Core.
approle:
  bind_secret_id: false
```

При развёртывании общий Vault hook создаёт/проверяет policy и роль экземпляра,
затем читает её RoleID из `auth/approle/role/<role-name>/role-id`. Ansible безопасно
доставляет RoleID в runtime volume-папку каждого Docker-хоста до запуска Agent.
Папка закрыта от посторонних пользователей, файл доступен UID/GID Agent, mount
в контейнер — read-only. При таком режиме RoleID является credential: его
значение не включается в portable project, `.env`, Compose, snapshot или logs.
Файл сохраняется для restart/re-auth; повтор читает существующий RoleID, не
генерирует новый без явной rotation. Для нескольких хостов одной логической
AppRole файл доставляется на каждый хост. При изменении placement Core пересчитывает
`token_bound_cidrs`. При NAT/rootless Docker используется адрес выхода выбранного
хоста к Vault, который определяется из существующей сетевой runtime-проекции
и проверяется execution preflight. SSH-адрес не считается автоматически адресом
этого маршрута. Если источник нельзя достоверно определить, выполнение блокируется
до его разрешения; ошибка входа не приводит к расширению до подсети или `0.0.0.0/0`.

Образ приложения содержит совместимый Agent. Generic provisioning формирует
agent.hcl и безопасные bootstrap references. Agent запускает приложение с env:
`exec.command` получает разрешённый список аргументов из defaults application
package. Подстановка `application_name` использует имя определения приложения,
не ID экземпляра: `apigateway-cspa` с `applicationRef: apigateway@1.0.0`
запускает бинарный `apigateway`. Ниже показан уже материализованный agent.hcl.

```hcl
auto_auth {
  method "approle" {
    config = {
      role_id_file_path = "/run/identity/role-id"
    }
  }
}

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

RoleID доставляется через защищённый runtime identity механизм. Token renewal,
expiry, повторный вход по сохранённому RoleID и rotation должны быть проверены.
Нельзя выдавать agent.hcl за полный bootstrap.

`.env`/base Compose содержит только несекретные настройки. `${...}` Compose
разрешается до запуска контейнера, Agent не заполняет его задним числом. Process
supervisor `env_template` и обычные file template blocks не смешивать без проверки
поддерживаемого Agent mode. Literal dotenv для приложения — отдельный вариант,
если оно не поддерживает environment процесса.

Справка: [Agent supervisor](https://developer.hashicorp.com/vault/docs/agent-and-proxy/agent/process-supervisor),
[AppRole auto-auth](https://developer.hashicorp.com/vault/docs/agent-and-proxy/autoauth/methods/approle).
Параметры роли: [AppRole API](https://developer.hashicorp.com/vault/api-docs/auth/approle).
