# A4 — Vault endpoint, секреты и Vault Agent приложения

Статус: технический план для согласования. Реализация, обращения к QA targets,
коммит и синхронизация master этим документом не разрешаются.
База: `codex/application-libraries`, `c7dba6b1d80beab78fe797a792f94f4ed4fec298`.
Актуальный статус этапов — только `CURRENT_STATE.md`.

## 1. Результат и границы

A4 завершает standalone путь PostgreSQL → Vault → Agent → приложение:
библиотечные ресурсы создаются раньше УЗ экземпляра; подтверждённые credentials
и общий пароль PKCS12 публикуются в Vault; Agent внутри контейнера получает их
через AppRole и запускает приложение с нужными переменными окружения.

Решение владельца: **при наличии endpoint взаимодействие с Vault сервером проходит через
endpoint выбранного deployment; если endpoint не настроен — через адрес и порт
выбранного client connection**. Это относится к provider hook, чтению
vault_ref, получению RoleID, проверкам и Agent. Адрес/порт берутся только из resolved provider projection, без ручного Vault URL.
Обход существующего endpoint при ошибке запрещён. Создание endpoint приложения
относится к A6, включение библиотек в общий план — A7.

В A4 входят PostgreSQL accounts A3, KV v2, AppRole, shared PKI secret,
материализация Agent/RoleID и запуск существующего подготовленного образа.
Redis, Sentinel, ClickHouse и Kafka account hooks — A5; HAProxy/DNS приложения —
A6; Go/UI — следующие этапы. Generated passwords, автоматическая ротация
инфраструктурных паролей, удаление УЗ/секретов и PKI перевыпуск не входят.

Приоритет всех A-этапов — скорость: один library hook на логическую библиотеку,
один instance hook на логический экземпляр, общий read-only discovery один раз
за invocation. На нескольких Docker-хостах УЗ, KV document и AppRole общие для
логического экземпляра. Host materialization выполняется для каждого placement.
Не объединять mutations разных библиотек/экземпляров в provider-wide batch.
Benchmark не проводить.

## 2. Что переиспользуем

| Механизм | Применение в A4 |
| --- | --- |
| A1 schemas/defaults/group_vars/host_vars | Единственный desired state; производные ссылки без secret values |
| A1 secretBindings/credentialRequirements/sharedSecretRequirements | Решение, какие действия действительно нужны |
| A2 package allowlist и image lock | Проверка Agent template и подготовленного образа; прежняя доставка pull/load |
| A2 application_runtime | Существующие preflight, render, Compose Apply и один inspect в обычном Verify |
| A3 application_providers и PostgreSQL application_provider | Ресурсы, accounts/grants и проверка фактического пароля в объявленной БД |
| Vault service role | Существующие runtime admin credentials, TLS CA, uri и включённый approle/ |
| PKI runtime materialization | Точные material/request/credential bindings и реальные PKCS12 файлы |
| Runtime secret inputs / protected files | Значения существуют только во время выполнения, без нового secret store |

Не вызывать полный install/bootstrap/unseal Vault для каждого приложения.
Не вводить новый generic hook engine, daemon, очередь, registry секретов или
второй проектный DTO. Provider остаётся частью service package Vault.

## 3. Desired state и минимальные расширения контракта

Ниже целевой пример application defaults. Он показывает PostgreSQL и shared
secret; остальные настройки image/ports/healthcheck остаются из A2.

```yaml
platform_application_definition:
  name: apigateway
  version: 1.0.0
  defaults:
    image: example/apigateway:1.0.0
    command: ["/opt/apigateway/bin/apigateway"]
    parameters:
      postgres:
        user: "{{ application_instance_id }}"
        password_ref: "{{ application_instance_id }}-postgres-password"
    accounts:
      postgres:
        mode: managed
        databaseRef: application-database
        credentials:
          username:
            source: {kind: literal, value: "{{ application_parameters.postgres.user }}"}
          password:
            source: {kind: runtime_secret_ref, ref: "{{ application_parameters.postgres.password_ref }}"}
    provisioner:
      type: vault-agent
      mode: process-supervisor
      auth: {method: approle}
      approle: {bind_secret_id: false}
      secrets: {mount: secret}
      secret_bindings:
        PG_USER:
          source: {account: postgres, field: username}
        PG_PASSWORD:
          source: {account: postgres, field: password}
        JAVA_KEYSTORE_PASSWORD:
          source: {library_secret: java_keystore_password}
  connections:
    postgres: {library_binding: database, protocol: tcp}
    vault: {library_binding: secrets, protocol: https}
  identity_environment: [EVO_MANAGER_APP_ID, KAFKA_APPLICATION_ID_CONFIG]
```

`command` — команда приложения; Compose запускает Agent отдельной разрешённой
командой. Для реального apigateway путь определяется именем приложения, а не
`apigateway-sdku`. Тестовый образ сохраняет свою действительную команду probe.
Пользователь не задаёт одинаковый ID для каждой env variable.

Библиотечные defaults используют существующий `shared_secrets.<name>.source`:

```yaml
platform_library_definition:
  name: sdku
  version: 1.0.0
  # slots и resources остаются из A1/A3
  connection_defaults: {}
  shared_secrets:
    java_keystore_password:
      source:
        kind: pki_credential
        binding: application_pki
        credential: java_keystore_password
```

В group_vars пользователь сохраняет текущие deployment bindings `database`,
`secrets`, `application_pki`, placement и resources. Instance override — только
`parameters.postgres.user: test-user` и
`parameters.postgres.password_ref: my-postgres-password`. Поле connectionRef
остаётся в библиотечных connection_defaults по serviceType, с override;
для однозначного Vault HTTPS подключения его не требуется задавать.

Точные поля deployment/PKI binding берутся из действующего контракта, без
параллельного Vault address/password блока. profileRef выбирает профиль, но
доставка PKCS12 password требует однозначного resolved material/credential.

Единственное необходимое расширение package render — необязательный
`agent_template` для ApplicationPackage рядом с `compose_template`:

```yaml
render:
  compose_template: roles/application_apigateway/templates/compose.yml.j2
  agent_template: roles/application_apigateway/templates/agent.hcl.j2
```

Файл обязательно входит в package files/digest. LibraryPackage это поле не
получает. Старые packages без Agent работают без изменений. Agent binary/config
пути — документированные defaults prepared image, без shell snippets; если
необходим override, добавить небольшой typed contract, а не произвольный script.

### 3.1. Авторизация provider hook: библиотечный vault_ref

Пользователь не задаёт путь к admin-token.age и пароль шифрования в библиотеке.
Installer использует уже существующий механизм выбора Vault runtime credential:
Go расшифровывает выбранный .age встроенной библиотекой filippo.io/age и
передаёт SERVICE_ADMIN_TOKEN через защищённый runtime-secret lease. В standalone
Ansible администратор передаёт platform_vault_admin_token либо указывает
platform_vault_bootstrap_output_dir с защищённым plaintext bootstrap-файлом
admin-token. Эти варианты не становятся полями desired state библиотеки.
Целевой YAML задаёт только выбор Vault binding для hook:

```yaml
platform_desired_state:
  applicationLibraryDeployments:
    sdku:
      # libraryRef/runtimeRef/resources/applications — как выше
      bindings:
        secrets: {deploymentRef: vault-main}
      vault_ref:
        binding: secrets
```

vault_ref.binding ссылается на уже существующий библиотечный binding; не дублирует
Vault deployment, URL или endpoint. vault_ref — авторизация hook на уровне
библиотеки; source.kind=vault_ref в account credentials остаётся отдельной
ссылкой на существующее KV поле. У экземпляра нет собственной admin авторизации.

Standalone использует существующие переменные Vault: platform_vault_admin_token
(runtime-only) либо platform_vault_bootstrap_output_dir с защищённым файлом
admin-token без шифрования age. Файл читается на Execution Node один раз на
provider после проверки ownership, private permissions и отсутствия symlink.
Токен не записывается в portable project. platform_vault_unseal_keys и файл
unseal-shares используются ролью установки Vault; application hook не выполняет
unseal и не требует этих ключей. age CLI и расшифровка в Python/Ansible отсутствуют.

Полученный token передаётся только в памяти в X-Vault-Token запросов uri к
resolved endpoint/client port, с TLS CA validation и no_log. Не выполнять
vault login с сохранением ~/.vault-token. Контейнер получает только RoleID.
Protected temporary material очищается success/failure/cancel существующим
runtime cleanup; оригинальный bootstrap-файл admin-token не удалять.

UI использует существующий механизм Vault runtime secrets, а не доставку
локального пути в Ansible. В ServicesPage.tsx chooseSecretFile вызывает
onChoosePendingDeploymentRuntimeSecretFile; backend выбирает файл native dialog,
ReadVaultInput расшифровывает age в памяти, broker хранит pending
SERVICE_ADMIN_TOKEN, bound к проекту и Vault deployment. При execution token
передаётся существующим runtime-secret lease на Execution Node.

Для приложения библиотечный bindings.secrets выбирает этот же Vault deployment.
Повторно выбирать файл/вводить пароль для каждой библиотеки или экземпляра
не требуется, если соответствующий runtime credential действителен. В project
не записывается локальный Windows path. UI password очищается после import;
plaintext не сохраняется в project, файл не копируется ради повторного decrypt.

Standalone остаётся независимым: существующие platform_vault_admin_token и
platform_vault_bootstrap_output_dir предоставляют admin credential без Go.
Подходящий typed SERVICE_ADMIN_TOKEN имеет приоритет. Invalid typed input
блокирует операцию без скрытого fallback. Затем используется явно заданный
standalone token, затем защищённый bootstrap admin-token. При нескольких Vault
provider standalone переменные задаются для соответствующего provider через
обычные Ansible vars; один непомеченный typed input допустим только для одного provider.

Schema delta: optional typed library vault_ref содержит только binding.
Файловые admin_token_file/encryption_password_ref удалены по решению владельца:
расшифровка выбранного .age выполняется существующей библиотекой filippo.io/age
в Go до передачи SERVICE_ADMIN_TOKEN через защищённый runtime-secret lease.
additionalProperties=false; Vault deployment остаётся в bindings.
Target-free resolver проверяет формы/ref; источник runtime admin token выбирается
runtime preflight. Infrastructure-only/no-Vault applications не требуют file source.

Будущие Go/A7 этапы обязаны добавить существующий SERVICE_ADMIN_TOKEN requirement
для Vault provider, когда план включает application hook, даже если сам Vault
не переустанавливается. Existing purpose/lease/broker переиспользуются; текущие
operations и requirement binding расширять канонически по A7, не выдавать
неподходящий SERVICE_APPLY input за разрешение application hook. UI показывает
существующий file-import flow для этого requirement, без новой secret transport.

QA: standalone отсутствующий file/ref, неверный пароль/unsafe path; UI real
handler → native selection → pending broker → approved execution lease → Vault
hook, включая plan без Vault install, expired binding и отсутствие повторного
decrypt. UI acceptance относится к последующим этапам, не standalone A4.

Это уточнение credential input контракта сделано после проверенной редакции
bba6aacb…; прежний review не является проверкой этой новой части.

## 4. Источники и связь с полями Vault

| Источник | Обработка |
| --- | --- |
| literal username | Несекретное имя; связывается с field username account document |
| runtime_secret_ref | Прочитать защищённый runtime input; тот же пароль используют A3 и Vault |
| vault_ref | Читать указанные binding/mount/document/field через endpoint; исходный document не изменять |
| pki_credential | Только exact selected runtime PKI credential, подтверждённый соответствующим PKCS12 |
| generated | Owner amendment 2026-10-21: managed application passwords генерируются при Apply; опубликованное значение переиспользуется, до публикации retry может выбрать новый пароль |

Решение владельца по A4-P02: библиотека выбирает **Vault deployment** через
существующий binding `secrets`. Это общий Vault reference для всех её экземпляров.
Его нельзя смешивать с source.kind=vault_ref — ссылкой на конкретный KV field.
Account-specific sources остаются в defaults приложения; переносить все пути
секретов в библиотеку и вводить новую именованную source сущность не требуется.

Точный existing desired-state путь для выбора Vault в group_vars:

```yaml
platform_desired_state:
  applicationLibraryDeployments:
    sdku:
      libraryRef: sdku@1.0.0
      runtimeRef: docker
      bindings:
        database: {deploymentRef: postgres-sdku}
        secrets: {deploymentRef: vault-main}
      applications:
        gateway:
          overrides:
            parameters:
              postgres:
                user: test-user
                password_ref: my-postgres-password
```

Остальные required slots/resources сохраняются как в текущем fixture.
Application defaults из §3 дают точную цепочку: parameters.postgres.password_ref
→ accounts.postgres.credentials.password.source(runtime_secret_ref)
→ A3 authenticated account hook → managed KV document в библиотечном Vault
→ secret_bindings.PG_PASSWORD(account=postgres, field=password) → Agent env.
Ни пользователь, ни экземпляр не задаёт отдельный Vault deployment/URL.

Если пароль уже находится в Vault, существующий source contract в defaults
приложения задаёт account-specific document/field:

```yaml
accounts:
  postgres:
    credentials:
      password:
        source:
          kind: vault_ref
          binding: secrets
          mount: secret
          document: existing/postgres/application
          field: password
```

`binding: secrets` разрешается через библиотечный bindings.secrets, а не через
instance deployment ref. Другой account может ссылаться на другой document/field
в том же binding. Для shared-only остаётся library shared_secrets.<name>.source
и env binding library_secret. Новое schema поле для именованной ссылки не нужно:
используем действующие source и bindings, расширяется лишь runtime поддержка A3.

Для vault_ref расширить существующую доставку credentials A3 приватным runtime
file, не передавать plaintext в snapshot/job. По owner amendment 2026-10-21
несовпадающий пароль подтверждённого managed application account заменяется
переданным при Apply; existing account и infrastructure credentials не меняются.
Для Kafka declared managed principal + admin access заменяют прежнее доказательство
владения паролем. TLS/admin/ownership и reserved-name guards сохраняются.

Bindings указывают account+field либо library_secret. По owner amendment 2026-10-21
путь вычисляется из library ID, instance ID и account name в объявленном mount,
без id проекта. Shared document — library/shared; account document —
library/instance/accounts/name. Например, KV v2 read: secret/data/sdku-dm/shared.
Те же locations используют read/write/CAS, policy, sourceJobs и Agent templates.
Project ID остаётся в ownership, чужой документ блокируется. Старые prefixed
документы не удаляются и не используются как fallback. Явные vault_ref неизменны.
Коллизии, path traversal, wildcard и конфликт env имён блокируются.
Для vault_ref Agent читает оригинальный путь/field, без копирования документа.

KV destination не требуется пользователю в обычном сценарии. Нет plaintext в
.env, base Compose, compose.yml, project, inventory, plan, snapshot или events.
Конфигурация Agent содержит ссылки, но RoleID считается runtime credential.

## 5. Endpoint, TLS и egress

Core один раз разрешает Vault binding → deployment → выбранный client connection
→ endpoint при его наличии, иначе resolved адрес и порт client connection.
Производная проекция содержит effective URL/FQDN/порт, TLS mode,
server-name и CA material reference. Hook и Agent используют одну проекцию.
При отсутствии endpoint допустим только авторитетный адрес/порт из connection,
без выбора случайного placement. Неоднозначный connectionRef или отсутствующий
доступный client address/port — prerequisite BLOCK до mutations.

TLS проверяется всегда: доверенный PEM CA для Agent и uri, сертификат endpoint
соответствует его DNS имени. PKCS12 приложения не заменяет PEM trust Agent.
Проверить, что proxy endpoint поддерживает API methods PATCH/PUT и не мешает
renew/reauth. Перенаправление на чужой host запрещено.

Решение владельца по A4-P01: AppRole bind_secret_id=false;
token_bound_cidrs автоматически содержит IPv4 подсети **/24** выбранных
Docker-хостов и постоянный элемент **127.0.0.1/32** по решению владельца.
Разрешение localhost не меняет endpoint-first правило и не разрешает обход
настроенного endpoint. Вычисление: фактический host source IPv4 для выбранного Vault
connection → network address /24 → union placements + 127.0.0.1/32 → сортировка/удаление дублей.
Уточнение владельца 2026-10-13: дополнительно включить IPv4 подсети LXC bridge
каждого Docker placement. Читать `ip -json -4 address show dev lxcbr0`
(имя из host_vars `platform_docker_lxc_bridge`, default соответствует Docker роли).
Использовать фактический prefixlen bridge, без фиксированного 10.0.3.0/24;
пустой IPv4 bridge или /0 блокирует Apply. Повторный Apply обновляет существующую
AppRole; уже выданные токены сохраняют прежние CIDR до переавторизации Agent.
Не вводить SERVER_ID, ручной CIDR либо вычисление из management SSH адреса.
IPv6-only в этом scope блокируется: правило /24 является IPv4 политикой.

Владелец подтвердил deployment prerequisite: видимый Vault source IP всегда
попадает в вычисленную /24, в том числе при обращении через HAProxy endpoint.
Это сознательно разрешает доступ из всей подсети, включая proxy; изоляция по
отдельному host/container через CIDR не заявляется. RoleID и минимальная policy
остаются средствами разграничения экземпляров. Trusted XFF/PROXY protocol в A4
не добавлять: при принятой сетевой политике это ненужное расширение scope.

Подтвердить настоящий AppRole login и последующий KV read из каждого placement
через выбранный путь; оба действия нужны, поскольку CIDR ограничивает и token use.
Если реальная сеть нарушает подтверждённый prerequisite, execution блокируется,
CIDR не расширяется за пределы host /24, localhost и явно разрешённых владельцем
обнаруженных LXC bridge подсетей. Нельзя fallback на direct port при ошибке
существующего endpoint. Проверка не выдаёт временную широкую роль и не передаёт
admin token контейнеру. Negative case — source за пределами разрешённых host /24,
LXC bridge подсетей и 127.0.0.1/32;
клиент внутри разрешённой /24 намеренно не считается запрещённым по CIDR.

## 6. Последовательность Apply

1. Target-free Resolve: defaults/overrides, bindings, identities, package digest,
   secret requirements. Нет запросов к Vault и secret values.
2. Общий runtime preflight: existing Docker/image authority, endpoint/TLS,
   Vault admin credential, KV v2 и AppRole mount, sources, PKI password/material,
   egress и безопасная возможность private file materialization.
3. A3 read-only preflight всей выбранной операции. Несовместимые A5/A6 функции
   блокируются до первой записи, а не после создания БД.
4. Library stage: A3 resources batch, затем один Vault library hook для
   действительно используемых shared secrets. Невостребованный secret не писать.
5. Для instance: один A3 accounts/grants hook; подтвердить supplied password
   login в объявленной application database. Owner amendment 2026-10-21:
   Apply меняет только несовпадающий пароль managed application account.
6. Один Vault instance hook: согласовать account documents, минимальную policy,
   AppRole и получить стабильный RoleID. Не создавать сущности на каждый host.
7. Для каждого Docker placement: материализовать private RoleID, Agent config,
   PEM CA и требуемые PKCS12/certificate mounts; обычные .env/base Compose остаются
   на уровне библиотеки. Секретные файлы не идут через ordinary config renderer.
8. Существующий A2 Compose Apply запускает Agent; Agent ждёт initial secrets,
   затем запускает child command с secret environment.
9. Обычный Verify — один docker inspect: image, instance labels, Running,
   healthcheck. A4 дополнительно проверяет содержательный nonsecret статус
   подключения к PostgreSQL/Agent readiness, без повторного SHA обхода файлов.

Если secret_bindings отсутствуют, не создавать AppRole/policy/Agent files.
Shared-only bindings работают без accounts. Accounts без secret_bindings
запускают только соответствующий account hook, не навязывают Vault.
Отсутствующая optional service ref пропускает незаявленный hook; заявленное
действие с отсутствующей обязательной ref блокируется.

## 7. KV v2 и ownership

Перед write прочитать document/version по endpoint. Для нового документа PUT
с CAS=0; существующий — PATCH application/merge-patch+json с текущим CAS,
только отличающиеся поля. Неизменённый документ не создаёт новую KV version.
Соседние поля сохраняются. Deleted/destroyed document не восстанавливать молча.
CAS conflict: один bounded reread и reconciliation; повторный конфликт — BLOCK.

Managed document содержит reserved nonsecret owner marker в том же CAS write,
чтобы создание документа и ownership не имели отдельного промежутка.
Не присваивать чужой document при совпадении пути; marker нельзя задавать через
application credential field. Existing vault_ref всегда read-only.

Policy/role имена детерминированы project/library/instance с ограниченной длиной.
Ownership policy отмечается managed header; existing role принимается только
при owned policy и ожидаемой привязке, без неожиданных policies. Чужая сущность
блокируется, а не перезаписывается. API policy/AppRole не имеет KV CAS: повторное
чтение перед update и действующий execution serialization, без нового lock engine.

## 8. Policy, AppRole и lifecycle

Policy разрешает read только точных KV data paths, необходимых bindings; нет
wildcard на библиотеку, list, write, root или default policy как обхода.
Если token_no_default_policy=true, явно включить необходимые self lookup/renew
permissions Agent. Token service TTL/maxTTL — небольшие обычные provider defaults
с override, не новый параметр UI. Проверить реальные renewal/re-auth semantics
используемой версии Agent/Vault.

RoleID читать после create/reconcile роли и доставлять через защищённый runtime
канал. SecretID не создавать. Token не сохранять в project/host token sink:
Agent использует auto-auth token в памяти. RoleID файл сохраняется после старта
для перезапуска и re-auth; очистка временной controller копии не удаляет volume.

Изменение role CIDR не отменяет уже выданные tokens. План не обещает немедленную
revocation старого placement: срок ограничен token TTL/maxTTL; принудительный
revoke/RoleID rotation — отдельное явно согласованное действие, не общий scan.
KV изменение перезапускает child через Agent только после успешного чтения.
Смена provider password и PKI store password не выполняется автоматически.
Новый runtime password при несовпадении с действующей УЗ блокируется до KV write.

## 9. Host files и Agent template

```text
<existing library runtime root>/
  .env                           # обычные пользовательские параметры библиотеки
  .base-compose.yml              # общие nonsecret connection параметры
  instances/<instance-id>/
    compose.yml
    vault/agent.hcl
    identity/role-id              # private, постоянный, read-only mount
    pki/ca.pem
    pki/keystore.p12              # private material, если требуется приложению
```

RoleID/PKCS12 — private directory и file ownership для фактического container UID.
Для rootless учитывать user namespace mapping; существующий A2 renderer этого
не доказывает. Не использовать chmod 0644/0777 или запуск от root как обход.
A4 должен добавить один bounded materialization путь с проверенным mapping;
если mapping неизвестен — BLOCK до запуска. Без symlink/path escape, atomic
replace и no_log на secret-bearing tasks. Не хранить secret digests в events.

`roles/application_apigateway/templates/agent.hcl.j2`:

```hcl
exit_after_auth = false
vault {
  address = {{ application_runtime.vault.endpoint_url | to_json }}
  ca_cert = {{ application_runtime.vault.ca_container_path | to_json }}
}
auto_auth {
  method "approle" {
    mount_path = {{ application_runtime.vault.auth_mount | to_json }}
    config = {
      role_id_file_path = {{ application_runtime.vault.role_id_container_path | to_json }}
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
  command = {{ application_runtime.application_command | to_json }}
  restart_on_secret_changes = "always"
}
```

`application_runtime` здесь — предлагаемое расширение существующей производной
проекции, не новые desired variables. binding.contents содержит Vault Go template
с точным data path/field, например `{{ with secret "secret/data/..." }}{{
.Data.data.password }}{{ end }}`. Это строка, не второй проход Jinja и не значение
пароля. Env names/paths/fields валидируются до render.
Compose entrypoint запускает разрешённый Agent binary с agent.hcl; exec.command
сохраняет разрешённую app command. Конфликт ordinary env/identity env/secret env
блокируется. PKCS12 password поступает только в child environment.

## 10. Изменения по файлам и подэтапы

### A4.1 — endpoint и runtime contract

- Дополнить существующие application projection/runtime inputs и guards.
- Убрать A2 deferred guard только для реализованных A3/A4 функций; сохранить
  запрет неподдержанных hooks/endpoints/TLS режимов.
- Добавить optional package agent_template и typed library vault_ref; негативные schema cases.
- Использовать принятое правило host-source IPv4 → /24 и endpoint-first.
- Discovery private delivery возвращает container UID/GID → host UID/GID,
  ownership родителей и безопасную проверку читаемости без вывода RoleID.
  Проверить nonzero container UID и restart; неизвестный mapping блокируется.

### A4.2 — Vault provider preflight и library hook

- Новый небольшой service-owned application_provider рядом с Vault role.
- Переиспользовать credential reader и uri TLS через endpoint, без полного install.
- Проверить KV v2/approle mounts; default secret соответствует текущей инфраструктуре.
  Явный applications mount должен уже существовать, не создавать его из app hook.
- Один library hook публикует used shared secrets после PKI material proof.

### A4.3 — instance hook и sources

- Один instance hook выполняет KV reconciliation, policy/AppRole reconciliation
  и RoleID read. Использовать uri loops, не shell Vault CLI на каждый field.
- Read-only vault_ref подключить к существующей protected credential delivery A3.
- Ресурсные УЗ и publication используют одну source resolution на invocation.

### A4.4 — materialization и Agent launch

- Private credential files отделить от ordinary config validation A2.
- Allowlist Agent template, безопасные UID/GID/mounts и собственные directories.
- Compose validation различает Agent launch и child command; не ослаблять
  volume/entrypoint whitelist для произвольного пользовательского выполнения.
- Библиотечный .env и base Compose сохранить; secrets туда не рендерить.

### A4.5 — recovery и содержательный Verify

- Owner amendment 2026-10-21: опубликованные generated passwords повторно читаются
  из своего документа; до публикации retry может генерировать новый пароль и
  установить его после подтверждения ownership. Сбой до первоначального witness
  блокируется. Только один Apply проекта одновременно, включая standalone и
  разные Execution Nodes; общей provider/Vault транзакции нет.
- Failure после PostgreSQL create не требует rollback УЗ; retry продолжает reconcile.
- При KV/policy failure контейнер не стартует с неполной проекцией.
- Agent restart, renewal, re-auth, missing field и недоступный endpoint дают
  ограниченный nonsecret статус; не выдавать значения через /status или diagnostics.

### A4.6 — focused QA, review и документация

- Native standalone resolve → apply → verify на RED OS из текущих sources.
- Реальные Vault endpoint/TLS, PostgreSQL accounts и prepared approved image.
- FULL DIFF review как изменение credential/container security boundary;
  один owner-approved TARGETED_RECHECK только при необходимости.
- Обновить secrets/configuration/implementation plan и test journal; CURRENT_STATE
  обновлять по доказательствам, не по наличию кода. Go/UI acceptance не заявлять.

## 11. Проверки и критерии приёмки

| Сценарий | Ожидаемый результат |
| --- | --- |
| PG account + shared PKCS12 password | Agent запускает app, реальный PG login и store open успешны |
| Библиотека на двух Docker hosts | Один logical account/role/document, private delivery на два hosts |
| Shared-only / no secrets | Agent без account hooks / прежний A2 путь без Vault actions |
| Повтор Apply | Нет новых KV versions, новых RoleID и ненужного Compose restart |
| KV соседнее поле / CAS conflict | Поле сохраняется; bounded retry, без blind overwrite |
| Чужой document/policy/role | BLOCK до присвоения чужой сущности |
| vault_ref | Read original field, никаких write в исходный document |
| Неверный PG пароль / PKCS12 binding | BLOCK до публикации ошибочного значения |
| Endpoint down / wrong CA / DNS name | Fail closed, без обхода настроенного endpoint |
| Endpoint не настроен | Hook и Agent используют один resolved client address/port с TLS |
| Proxy/NAT меняет видимый client IP | Login и KV read успешны внутри принятой /24; иначе BLOCK |
| Source вне /24 и 127.0.0.1/32 / чужой KV path | Login/read denied; нет расширения policy/CIDR |
| Container restart / token expiry | Повторная auth по сохранённому RoleID, без SecretID |
| Missing secret field | Приложение не стартует с пустым secret |
| Rootless nonzero UID / symlink | Безопасная readable private delivery / отказ unsafe path |
| Отсутствует optional ref / обязательный ref | Skip незаявленного hook / BLOCK заявленного действия |
| Infrastructure-only project | Никаких application/Vault instance hooks, прежнее поведение |

QA использует существующий prepared test image из approved source; не строить и
не скачивать образы без отдельной авторизации. Читать QA procedure перед target
work; не запускать Core/Python на Windows. Проверять secret absence в safe events,
.env/Compose/project и diagnostics без печати реальных значений. Benchmark исключён.

Приёмка: все реальные native positive/negative cases PASS; private delivery,
endpoint-first / no-endpoint client-port access, restart/re-auth и no-op repeat доказаны; independent review
пройден в пределах бюджета; ограничения scope явно записаны. Автоматическое
удаление ресурсов, смена УЗ/PKCS12 password и A7 общий план не считаются реализованными.

## 12. Первичные ссылки для реализации

- [Vault Agent process supervisor](https://developer.hashicorp.com/vault/docs/agent-and-proxy/agent/process-supervisor): env_template и exec lifecycle.
- [Agent AppRole auto-auth](https://developer.hashicorp.com/vault/docs/agent-and-proxy/autoauth/methods/approle): RoleID file.
- [AppRole API](https://developer.hashicorp.com/vault/api-docs/auth/approle): role constraints, token CIDRs и TTL.
- [KV v2 API](https://developer.hashicorp.com/vault/api-docs/secret/kv/kv-v2): CAS PUT/PATCH и versions.

Версию Vault/Agent и source /24 prerequisite подтвердить по реально
выбранным artifacts и placements перед реализацией. Эти ссылки не заменяют pinned runtime QA.

### Проверка уточнения credential acquisition (2026-10-10)

RED OS, текущая ветка codex/application-libraries: 12 provider tests и 13 Core
Vault projection/schema tests PASS. Проверены typed input, standalone переменная,
чтение защищённого bootstrap admin-token и отказ на symlink. Это focused evidence;
не заменяет native A4 acceptance и обязательное независимое FULL DIFF review.

Уточнение владельца: все опубликованные endpoint используют HTTPS порт 443.
Hook и Vault Agent используют один URL https://<endpoint-fqdn> (неявный 443) независимо от
backend-портов участников. Без endpoint используется resolved client address/port.
