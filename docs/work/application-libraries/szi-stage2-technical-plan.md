# SZI-STAGE2 — полная СЗИ и предоставляемые подключения

Дата: 2026-10-22. Статус: revised DRAFT / owner-authorized TARGETED_RECHECK.
Исходный FULL PLAN review сохранён с историческим BLOCK; его SHA-256:
`0B9A1B168A52275E6FECDE645F5F65718FBC2F04C31F129283996ECF0AA48451`.
Владелец разрешил внести обсуждённые изменения и один точечный речек.
Основа: master `5f614312`. Это план, не разрешение на реализацию или изменение
стенда. В checkout есть отдельные изменения APPLICATION-GENERATED-PASSWORD;
их код/приёмка не включаются в этот этап автоматически. Статусы — CURRENT_STATE.md.

## 1. Цель и решения владельца

Полностью установить и обновлять keycloak, grant-access, grant-access-front,
grant-access-audit и nginx как обычные приложения библиотеки. Добавить подключения,
предоставляемые приложениями, их использование внутри/между библиотеками и создание
прикладной УЗ через существующую область accounts с дальнейшей доставкой в Vault/Agent.

- Нет if SZI/Keycloak в Core/Go/UI, особой роли библиотеки или второго desired-state.
- Параметры подключения — произвольная карта parameters. Realm — ключ пакета,
  не отдельное поле Core/DTO. Credentials используют общие source descriptors.
- Integration enabled задаётся defaults приложения; slot/group_vars overrides и
  UI переопределяют его. Reset удаляет override, не копирует defaults.
- Создание пользователя объявляется в существующей `accounts.<connection-alias>`.
  Не добавлять вложенный account в connection, create_secret/provision_user flag,
  accountRef или отдельный KeycloakUser DTO. Это последнее уточнение владельца.
- Только установка/обновление. Disable/удаление связи из desired state НЕ удаляет
  пользователей, клиентов, группы, memberships, маршруты и Vault-данные, НЕ
  отзывает доступ и не меняет пароль. Live объекты могут оставаться активными.
- applicationId — единственный ключ интеграции: clientId, nginx subpath,
  description=endpoint приложения. Redirect URI: `https://nginx…/<applicationId>/*`.
- Порядок библиотек — config/application.yml, слотов — start_priority. Нет нового
  DAG scheduler, авто-перестановки или закрепления endpoint-порта.
- Runner получает файл, argv, account/workdir и private secret files. Docker,
  Keycloak, realm и API принадлежат пакетным скриптам.
- Сохранить batch provisioning инфраструктурных accounts. Прикладной provider
  после готовности обрабатывает только собственную группу выбранных потребителей:
  library integration hooks → instance integration hooks → accounts → dependent
  Vault/Agent. Не выполнять Kafka/Redis/PostgreSQL повторно перед каждым контейнером.
- Client secret определяется до API-вызова из одного credential source. Только
  explicit secret_bindings приложения включает его доставку в Vault/Agent;
  секретный stdout/output protocol скриптов не вводится.
- Redis credentials grant-access — legacy, не возвращать в UI/Agent.

Сохранить stage1: clean dump без admin, restore_on_create только при создании БД,
bootstrap admin с runtime password, production PKI, themes/providers. В scope
входит один внешний потребитель SDKU/alarm-view-service для сквозной приёмки;
массовое включение SDKU/CSPA, CRUD бизнес-пользователей в UI, удаление/миграции,
автоматическая ротация admin и новые детальные события всех задач — вне этапа.

## 2. Исследованная база и недостатки текущего механизма

Canonical contracts: contracts/application-libraries/v1alpha1/{application,library,
settings,deployments,package}.schema.json. Core: application_libraries.py,
application_plan.py, application_scripts.py, application_providers.py,
application_vault.py, application_runtime.py. Ansible: resolve_application_libraries,
application-libraries-provider-stage.yml, ordered-library/ordered-instance playbooks,
application_runtime и package_script. Go: application_library_save.go,
application_package_import.go, coreadapter, desktop installation plan. UI:
ApplicationsPage.tsx, ApplicationBindings.tsx, ApplicationCredentials.tsx,
application-draft.ts, backend.ts; ui-design-01.md и applications HTML mockup.

Сейчас bindings выбирают deploymentRef/profileRef. accounts.<alias> уже использует
одноимённое connection как provider. Нет exports, application-backed account provider,
условных connection scripts. Provider/Vault stage общий до
контейнеров, конфиги библиотеки материализуются заранее, endpoints публикуются
только после всех её экземпляров. Это не позволяет создать УЗ grant-access в ещё
не запущенном Keycloak и затем доставить её password в Agent. Изменения §6 обязательны.

script.lua/data.env ещё содержат фиксированные списки приложений. Stage1 README
не доказывает готовность динамической маршрутизации. Остальные четыре приложения
ещё требуют сверки Agent, entrypoint, PKI, памяти и readiness; принят только Keycloak.

## 3. Предоставляемое подключение: контракт

### 3.1. Определение пакетом библиотеки

Добавить `platform_library_definition.provided_connections`:

```yaml
provided_connections:
  sso:
    application: keycloak  # slot данной библиотеки, не второй applicationId
    protocol: https
    parameters:
      realm: master
    credentials:
      username:
        sensitive: false
        source: {kind: literal, value: admin}
      password:
        sensitive: true
        source: {kind: runtime_secret_ref, ref: szi-admin-password}
    account_provisioner:
      apply_script: ensure-user
```

Core разрешает application slot в существующий applicationId/endpoint. Public URL,
placements/targets, порт, TLS identity берутся из общей endpoint/PKI projection,
не задаются вторым ручным URL. account_provisioner необязателен: без него обычное
подключение допустимо, managed account — нет. Это callback account Apply lifecycle,
не registry произвольных CRUD-операций. Product roles/grants разбирает пакет.

В existing script descriptor добавить on-demand назначение account_apply:
такие scripts не запускаются обычными lifecycle hooks самого Keycloak. Source —
allowlisted файл exact provider application package, входящий в files/digest.
argv/secretInputs описаны manifest; code/script path из parameters/group_vars не берётся.
Общий runner исполняет тот же контракт, без понимания account API.

### 3.2. Overrides и привязка потребителя

Library deployment получает `provided_connections` overrides только parameters
и credential sources объявленных exports. application и scripts задаёт пакет.
Использовать стандартный Ansible merge, не Python/Go/React precedence engine.
Existing bindings расширить третьей взаимоисключающей source-формой:

```yaml
bindings:
  identity:
    providedConnectionRef:
      libraryId: szi
      name: sso
```

Не дублировать applicationId/slotId в binding: export уже указывает приложение.
deploymentRef/profileRef работают по-прежнему. Несколько source-форм одновременно
— ошибка. Library connections.identity сохраняет `library_binding: identity`.
Self-library ссылка допустима. Missing/disabled slot/export, несовместимый protocol
и обратный порядок библиотек диагностируются target-free.

### 3.3. parameters и credentials

parameters — карта произвольных непустых ключей и JSON-значений без realm/tenant
в Core. Scalar editor + существующий Advanced для object/list. Defaults/overrides:
карты recursively, списки replace; Reset удаляет override. Значения не исполняются
как код. Scalar идёт отдельным argv, object/list — canonical JSON аргументом либо
объявленным input file, не shell-строкой. Runtime secrets не подставляются в parameters.

credentials — карта source descriptors одного canonical source schema. sensitive
по умолчанию true; literal для sensitive credential запрещён. Для username с
sensitive:false допускается literal; остальные используют существующие допустимые
runtime_secret_ref/vault_ref/pki_credential. Публичность задаёт пакет, UI не
угадывает её по имени ключа. Существующие plaintext/secret guards сохраняются.

Canonical source admin password — credential export sso.password.
Bootstrap scripts пакета Keycloak получают его через явный local export credential
reference в secretInputs, а не держат отдельный runtime ref в своём manifest.
Разрешение source не обращается к API и не требует уже работающего self-provider:
доступность API нужна только hooks, выполняющим запросы. Override/reset export
меняет единый source bootstrap/admin hooks. Новый source не означает ротацию admin:
если существующий admin не принимает credential, Apply прекращается без сброса
его пароля. Несогласованный второй источник в пакете отклоняется при validation.
Public projection
содержит только допустимую metadata, private binding передаётся существующим
lease/file механизмом. Admin password не попадает в project/plan/argv/logs/audit
и автоматически не публикуется в consumer Vault document или ENV.

## 4. Enabled и обычные accounts

Connection declaration остаётся на существующем уровне definition, enabled —
в settings для обычной цепочки defaults/overrides:

```yaml
platform_application_definition:
  connections:
    identity: {library_binding: identity, protocol: https}
    vault: {library_binding: secrets, protocol: https}
  defaults:
    connections:
      identity: {enabled: false}
    # accounts.identity отсутствует, если прикладная УЗ не нужна
```

Для grant-access используется существующая accounts область:

```yaml
defaults:
  connections:
    identity: {enabled: true}
  accounts:
    identity:
      mode: managed
      credentials:
        username:
          source: {kind: literal, value: '{{ application_instance_id }}'}
        password:
          source: {kind: runtime_secret_ref, ref: grant-access-user-password}
```

accounts.identity выбирает provider через connection identity, аналогично текущим
accounts.postgres/redis. UI выбирает это connection как provider УЗ; в desired
state сохраняется existing canonical alias, не hardcoded `provider: szi`.
Если provider нужны groups/roles, добавить произвольную account parameters карту
к существующему account schema; смысл ключей остаётся в provider script.

Instance override в group_vars:

```yaml
platform_desired_state:
  applicationLibraryDeployments:
    sdku:
      applications:
        alarm-view-service:
          overrides:
            connections:
              identity: {enabled: true}
```

Ansible precedence: defaults → library slot overrides → instance group_vars.
enabled — логическое свойство instance, host_vars его не переопределяют.
Legacy connections без нового поля сохраняют enabled=true. Новые optional
identity connections явно задают defaults=false.

| Desired state | Исполнение |
| --- | --- |
| enabled=false | Не требуются provider/accounts/hooks/lease для этого потребителя; нет новых route upserts, live объекты не меняются |
| enabled=true, account отсутствует | Connection parameters и объявленные hooks, без прикладного user/password и без их UI inputs |
| enabled=true, accounts.identity задан | Existing credential editor/inputs; provider creates/updates user, затем штатный Vault/Agent |

Retained account при disabled не удаляется из проекта; UI показывает его
неактивным. Общий secret ref, нужный другому enabled consumer/bootstrap, остаётся
required. Смена username/applicationId/realm создаёт новую target identity;
старые объекты сохраняются. Автоматического переименования/удаления нет.

## 5. Прикладной account provider и поток credentials

```text
szi-admin-password → private API session → ensure-user в Apply
accounts.identity username/password → Keycloak user → existing Vault document
  → existing AppRole/policy → existing Vault Agent binding → app process ENV
```

1. Existing credential resolver получает username/password accounts.identity.
   Provider script получает ТО ЖЕ password value, которое затем пойдёт в Vault;
   не возвращает/генерирует его через stdout.
2. Core разрешает account_provisioner и готовит batch job из provider package для
   всех enabled выбранных потребителей этого providedConnectionRef. Once — один
   callback на provider batch, на детерминированном provider placement existing
   runtime identity. Несколько consumer placements не дублируют account request.
   Accounts других провайдеров в этот batch не входят и повторно не выполняются.
3. Package callback использует API/CLI в verified image провайдера. Python/jq
   на target не требуются. Provider/consumer identities, alias, username и
   parameters заданы явными argv/input-file refs; admin и user passwords — private
   files. Batch input — список несекретных account requests со ссылками на private
   files, а не пароли в argv. Callback может один раз авторизоваться и обработать
   список. Внешний результат — только existing aggregate status/changed, без
   credential values и списка per-request результатов, в текущем лимите stdout
   runner2048. Успех подтверждает завершение ВСЕХ requests; per-request результаты
   остаются внутренними данными callback. Частичная ошибка останавливает batch
   и dependent delivery, retry идемпотентно доводит всю группу. Docker context
   находится только в package script; output-протокол не расширяется.
4. Create/compare/update user, разрешённые memberships/roles, контрольный login,
   затем публикация credential в Vault. ENV names проверяются по фактическому
   сервису: пользовательский password не заменять OAuth client secret и наоборот.
5. Repeat с прежним credential — changed=false. Новый password source обновляет
   managed user и затем Vault. API success/Vault failure: retry доводит обе
   стороны с тем же input, без удаления user или rollback старого пароля.
6. По решению владельца от 2026-10-22 метки владельца Installer не проверять
   и не добавлять для групп, клиентов и пользователей Keycloak. Использовать
   applicationId для клиентов и точное имя для групп/accounts. Существующие
   UUID и атрибуты сохранять. Managed mode создаёт/обновляет явно выбранную
   учётную запись; existing mode только проверяет пароль и не меняет права.
   Не вводить user-profile marker. Проверки результата API остаются.
7. Provider failure не публикует новый credential в Vault и блокирует consumer.
   Все его placements используют единый reconciled account result.

Agent secret_bindings приложения использует существующие
`{account: identity, field: username/password}`, не admin credential провайдера.
Generated source — только существующий AGP механизм после его gates. Не вводить
свой генератор и не считать AGP-D01 закрытым. Базовая приёмка — explicit runtime refs.

## 6. Общая последовательность Apply/Verify

### 6.1. Resolve и ранняя подготовка

Два ограниченных прохода: effective settings/identities/endpoint exports всех
выбранных библиотек, затем active bindings/accounts/scripts. Потребители используют
одну derived projection. Это не новый scheduler и не precedence resolver.

Сгруппировать existing provider jobs по их resolved source. Infrastructure-backed
jobs выполняются в общем раннем этапе текущим batch механизмом; группировка Kafka
и обработка всех выбранных accounts за один provider проход сохраняются.
Application-backed jobs группируются по стабильному providedConnectionRef
(provider library/application/export), не по контейнерам потребителей. Все requests
enabled consumers выбранного Apply scope собираются до начала mutation.

Общий ранний этап сохраняет infrastructure resources/accounts/ACL, shared PKI
и независимые Vault/Agent операции. Если consumer требует хотя бы один отложенный
account ИЛИ provider_prepare hook с credential для Agent, его полный instance
Vault document/policy/AppRole и финальные Agent inputs ждут всех этих зависимостей.
Подготовленные PostgreSQL/Kafka credentials удерживаются existing private runtime
context; partial document с отсутствующим identity/client credential не публикуется.
Это одна классификация по типу source binding и dependencies manifest, не по SZI
или имени параметра. Product API не вызывается в target-free Plan/VerifyProject.

### 6.2. Внутри упорядоченной библиотеки

1. Материализовать независимые inputs/base configs и доставить verified images.
   Потребители с pending credentials ещё не получают финальные Agent inputs.
2. Existing library before_start hooks выполняются по прежнему назначению.
   Группы/клиенты перевести в provider_prepare (§7), чтобы собственный ещё не
   запущенный provider не требовался в library before_start.
3. Для каждого instance по existing start_priority проверить завершённую
   подготовку его dependencies, выполнить обычный before_start, запустить все
   placements, readiness и after_ready (включая bootstrap admin у Keycloak).
4. Если instance предоставляет активное используемое подключение:
   a. Через existing endpoint writer опубликовать и проверить его общий endpoint
      с проверенными placements; не подменять его прямым IP одного Keycloak.
   b. Для каждого его provider batch выполнить library provider_prepare hooks
      всех выбранных потребителей и выведенные connection callbacks в порядке order.
      Для СЗИ это группы → клиенты → назначения realm/client roles группам,
      перед accounts. Owner2026-10-22: IDENTITY_GROUPS в defaults.parameters
      библиотеки связывает каждую группу с allowlisted JSON/Jinja файлом ролей;
      существующий Ansible lookup материализует содержимое в итоговый argv.
      UI не изменяется. Универсальный integer order скрипта (default0) задаёт
      -100 для создания групп, 0 для клиентов, 100 для назначения ролей.
   c. Вызвать account_apply batch ТОЛЬКО accounts этого provider. Даже если
      потребители находятся в следующих библиотеках, выполнить их группу сейчас.
   d. Для consumers, у которых завершены ВСЕ provider batches/hooks, выполнить
      один полный стандартный Vault/Agent provisioning проход. Незавершённые
      consumers ждут своего следующего provider; нет partial writes или polling.
5. Продолжить runtime instances/libraries существующими явными loops. Перед
   consumer startup только проверка preparation result, не повторный provider call.
6. Endpoints остальных приложений публикуются в прежнем конце библиотеки; для уже
   опубликованного provider не выполнять второй mutation, только финальную проверку.
   Library after_ready и стандартный library Verify сохраняются, затем следующая
   библиотека. При любой provider/hook/account/Vault ошибке dependent startup запрещён.

Ранняя публикация нужна только endpoints приложений, предоставляющих используемые
подключения; общая проверка основана на exports/bindings, не на имени Keycloak.
HAProxy/DNS writer, endpoint placement, port selection и PKI остаются текущими.
Direct placement_https сохраняется лишь для собственного технического bootstrap
до endpoint publication; запросы потребителей и account callbacks идут через общий
endpoint с резервированием. Нет закрепления порта новым полем.

Пример: ранние Kafka/Postgres/Redis batches → собственные Vault/Agent Keycloak →
Keycloak readiness/admin/endpoint → группы → клиенты → batch Keycloak accounts →
dependent consumer Vault/Agent → grant-access и остальные consumers. Каждый batch
вызывается один раз; 100 consumers не превращаются в 100 Kafka init/login проходов.
Нет persisted очереди, нового scheduler или daemon: resolved batches и их completed
results — обычное derived execution state текущего Ansible run. Retry заново
reconcile-ит группы идемпотентно, не доверяет внешнему сохранённому ready-флагу.

Self-library provider имеет меньший start_priority; cross-library provider —
раньше в явно заданном order. Неправильный порядок — target-free finding, не
автоматический topological sort. При отказе provider placement/publication
dependent consumer не стартует. Общего дополнительного barrier сервиса нет.

По решению владельца2026-10-22 Verify не расширяется: существующая проверка
работоспособности сервисов/приложений остаётся текущей. Не добавлять scripts
phase=verify, account_verify/verify_script callbacks, API-сверку пользователей,
клиентов, групп, Vault ACL или route catalog в Verify. Read-back и проверки
результата upsert принадлежат самим Apply scripts; функциональные проверки
интеграции выполняются как QA, не как новые функции product Verify. Target-free
VerifyProject сохраняет текущую роль проверки проекта и не запускает scripts.

### 6.3. Retention Vault policy при disable — SZI2-P01

Для owned application-instance policy в этом no-delete lifecycle обновление
read-paths аддитивно: существующие управляемые read-paths сохраняются, необходимые
активным accounts/bindings добавляются. Отсутствие/disable connection или binding
не означает отзыва ранее выданного read-path. KV documents/owned AppRole остаются;
Agent может перестать запрашивать выключенный binding, но действующий Vault token
не должен потерять прежнее право чтения вследствие этого Apply.

Использовать уже читаемую existing owned policy и текущие ownership guards. Merge
ограничен каноническими managed KV read rules ЭТОГО application instance; не
переносить правила чужого instance, произвольные paths/capabilities и не повышать
права. Сохраняются только ранее подтверждённые канонические rules; нераспознаваемый
или foreign policy не переписывается, выдаётся existing ownership/format failure.
Это не общий merger произвольного HCL и не изменение service-wide infrastructure
policies. Новые active credentials продолжают обновляться; нельзя пропустить весь
instance Vault job из-за одного disabled connection. Когда активных inputs нет,
retained live document/policy не мутируются и disabled password не запрашивается.

Обязательный proof: postgres + identity → disable/remove identity → Apply postgres
update → old token читает retained identity KV, postgres updated, identity password
не запрошен/не изменён; повтор no-change. Retention проверяется также после полного
исчезновения identity declaration/binding из desired state, без второго desired
store или необходимости хранить disabled plaintext credential.

## 7. Скрипты интеграции и обновления без удаления

Добавить scripts phase=provider_prepare и `requires_connections: [alias]`.
Provider_prepare не выполняется второй раз как before_start потребителя: coordinator
собирает hooks выбранных consumer packages и connection callbacks их провайдеров
и исполняет в provider-ready точке §6. Сначала учитывается order; при равенстве
library scope предшествует instance scope. Source/digest обычных hooks принадлежит
потребителю, source/digest connection callback — провайдеру. Для hooks с несколькими connections
target connection указывается явно; все прочие required providers должны быть
раньше target provider в существующем порядке, иначе target-free finding.
Disabled dependency
исключает hook ДО разрешения argv/secretInputs. Typed valueFrom расширяется для
connection URL, parameters.<key> и private credentials.<name>. Прежний address:port
reference сохраняется. Никакого произвольного eval из typed refs.

Owner2026-10-22: группы и файлы ролей остаются в пакетах потребителей.
Создание клиента принадлежит провайдеру: provided_connection объявляет
`connection_provisioner: {apply_script: integrate-consumer}`, а provider package
содержит allowlisted callback `phase: connection_apply`, `execution: once`.
Потребитель хранит только enabled и параметры интеграции; prepare-client.sh и
декларации его вызова из application packages удаляются. Core выводит по одному
вызову на enabled connection, с consumer applicationId/parameters/endpoint и
provider source/target/credentials. Вызов включается в тот же provider batch
до accounts. Скрипт не запускается как обычный lifecycle hook провайдера.
`secretInputs` может брать source существующего consumer secret_binding;
optional binding при отсутствии не передаётся. Отдельного secret output нет.
Для Keycloak это client_secret из KEYCLOAK_CLIENT_SECRET только у grant-access.
Общий runner не меняется; продуктовые API остаются внутри provider script.
Никакого registry CRUD операций или удалённого script marketplace нет.
Ошибка групп, client callback или назначений ролей блокирует accounts и
зависимую Vault/Agent delivery. Порядок hooks задаётся order (-100/0/100),
при равенстве сохраняется стабильный library-before-instance порядок.

Для scripts, которым нужен CLI на provider host, добавить общую декларацию
`target: {connection: identity}`. Source остаётся consumer package; resolver
выбирает provider host/runtime identity, provider identifiers передаются только
явными argv refs. Existing scripts сохраняют прежние targets. Once/each_target
применяются к выбранному eligible set; проверка изменённого пароля не заменяет once.

Материализовать JSON client template из applicationId/endpoint, package parameters
и client secret при необходимости. Secret JSON inputs — только private transient
files, не config_files/public renders. Новый client: один POST JSON. Existing:
compare managed fields → PUT по API id, без delete/recreate. Чужие настройки не
обнуляются; foreign ownership даёт ошибку. Description остаётся endpoint, marker
в допустимой attributes области. Группы upsert по stable package declaration,
три baseline группы чистой БД сохраняются. Нет prune отсутствующих объектов.

### 7.0. Источник и доставка client_secret

В stage2 secret определяется ДО create/update клиента из существующего credential
source. Скрипт устанавливает то же значение в JSON Keycloak; назад он возвращает
только status/changed. Secret outputs, чтение случайно сгенерированного сервером
секрета через stdout и новый runtime secret store не добавляются.

Пример использования existing library secret и process-supervisor binding:

```yaml
# library definition / installation override: единый source
shared_secrets:
  grant_access_client_secret:
    source: {kind: runtime_secret_ref, ref: grant-access-client-secret}

# grant-access defaults, реальное ENV имя сверить по контракту образа
provisioner:
  secret_bindings:
    CLIENT_SECRET_ENV_FROM_IMAGE_CONTRACT:
      source: {library_secret: grant_access_client_secret}
```

Provider_prepare script grant-access получает тот же library secret через явный
secretInputs reference. Ссылку `library_secret` разрешать к уже выбранному source,
не дублировать runtime ref в script manifest. Existing private lease удерживает
значение до завершения API и Vault. Keycloak success — prerequisite публикации
соответствующего credential в consumer document, даже если source уже известен.
Если Vault fail после API success, repeat использует тот же source и доводит доставку.

Только explicit provisioner.secret_bindings объявляет доставку секрета приложению.
Не вводить save_secret/persist_to_vault flag. Для текущего СЗИ client_secret
автоматически доставляется в Agent/ENV только grant-access; остальные клиенты не
становятся confidential автоматически. Отсутствие binding означает отсутствие его runtime
доставки, но source может быть нужен provisioning hook. Не запрашивать secret,
если ни active hook, ни Agent binding его не использует.

Это требует фильтровать Vault shared fields по фактически объявленным Agent
bindings: само наличие shared_secrets source не разрешает раннюю публикацию
всех его значений. В shared document ранним existing CAS delta записывается,
например, java_keystore_password для старта Keycloak; client_secret добавляется
отдельным owned field delta только после успешного client hook. Перед поздним
delta перечитать текущую owned версию, сохранив другие поля, existing CAS/retry
guards и no-delete. Нельзя задержать весь shared document до Keycloak или снова
перезаписать ранние поля устаревшим snapshot. Это разделение document fields по
готовности объявленных потребителей, без новой persistence entity/API.

Гранулярность Vault ACL остаётся document-level: токен с read на <library>/shared
может прочитать ВСЕ его поля, даже без соответствующего Agent binding. Выбор поля
шаблоном не является field-level ACL. План гарантирует только отсутствие доставки
client_secret в Agent/ENV других приложений, не изоляцию от их токенов с read
общего документа. Field-level isolation не заявлена владельцем и не добавляется
как скрытый scope. Canary delivery test не доказывает запрет document read.

Admin password, client_secret и accounts.identity.password — разные credentials,
не подменять их друг другом. Generated sources возможны только через принятую
существующую AGP функциональность; при её незавершённой приёмке — runtime ref.
Source не меняется на каждом Apply. UI показывает текущий source и delivery binding
в existing Secrets, не создаёт отдельный редактор «секретов, возвращённых скриптом».

### 7.1. Динамические аварийные маршруты nginx

Заменить фиксированные HMI_*/ALARM_*/SDKU_* списки на JSON route catalog для Lua:
applicationId → endpoint, proxy subpath и только объявленные nonsecret route
parameters. В data.env остаются общие настройки, не индивидуальные URL.

Package Jinja template nginx получает общий список enabled consumers из derived
projection всего проекта и формирует routes.requested.json. Core не знает формат
СЗИ routes. Before_start package script на каждом nginx target upsert-ит
routes.effective.json, сохраняет остальные ранее установленные записи, атомарно
пишет результат и проверяет nginx config. Монтируется каталог, чтобы rename не
оставлял контейнер на прежнем inode одиночного file bind.

Effective catalog не входит в source config_files/config_directories, которые
перезаписывают/чистят его. Exact owned path и directory mount объявляет пакет,
проверяется действующим Compose mount contract; mount validation не ослабляется.
Это observed installed catalog, не второй desired-state: новая установка строит
только текущие enabled записи; на уже установленном target старые сохраняются
по no-delete решению. Repeat unchanged — changed=false. Disabled не upsert-ится
и не удаляется; новый endpoint применяется только для enabled consumer.

Два nginx placements должны иметь одинаковые новые upserts; различия retained
history диагностируются package script при Apply и проверяются в QA, без новых
правил Verify и без автоматического cross-target prune/копирования.
Существующий маршрут не означает готовность backend. СЗИ может сформировать
routes до старта SDKU, поскольку resolve видит весь проект.

### 7.2. Явный Apply scope — SZI2-P02

Общее консервативное правило: Apply любого enabled consumer, ссылающегося на
providedConnectionRef другой библиотеки, требует явного включения предоставляющей
библиотеки в тот же Apply scope раньше consumer. Проверять все такие ссылки
выбранных библиотек (включая транзитивные), а self-library удовлетворяется одним
Apply и проверкой внутреннего start_priority. Missing provider в scope —
target-free finding с именем требуемой библиотеки; scope сам не расширяется.

Основание правила — только canonical binding, а не сравнение routes.requested,
история рендеров или анализ произвольного Jinja. Core не знает формат nginx routes.
Цена — дополнительный обычный идемпотентный Apply предоставляющей библиотеки даже
при отсутствии изменений маршрута. Для stage2 это сознательное ограничение;
узкую оптимизацию по диффу данных и новый граф input dependencies не вводить.

СЗИ/SDKU, выбранные вместе, обеспечивают обновление route input при обычном Apply
библиотеки СЗИ до запуска SDKU. Nonsecret чтение полной project projection в nginx
template не становится runtime start dependency на SDKU. При удалении/disable
связи новых route writes нет и прежняя запись сохраняется. No ad-hoc SSH update.

## 8. Состав полной библиотеки

| Пакет | Изменения |
| --- | --- |
| keycloak | Existing clean restore/admin/PKI, public/admin exports, on-demand user Apply callback, helpers/client JSON. Existing service Verify без расширений. Полные темы и9 JAR остаются внешними ignored inputs |
| grant-access | Existing accounts.identity с реальным прикладным пользователем; отдельный client/secret, только если требует сервис. Username/password через Agent. Удалить legacy Redis account/bindings и ненужные декларации, без удаления deployed Redis data. Hazelcast members/ports из placements, согласованный heap/limit |
| grant-access-audit | PostgreSQL database/account/JDBC из resolved targets и actual resource name; identity account, если нужен сервису. Agent template, PKI. Убрать пустые ручные KEYCLOAK_HOST/POSTGRES_* параметры |
| grant-access-front | config.json из resolved connections/endpoint groups, applicationId/subpath, actual mounts/ports. Admin credential не попадает в browser config |
| nginx | Выбранный lawellet image, standard PKI, dynamic catalog/Lua, endpoints/credentials из declarations. Нет literals source107 |

Предварительный порядок: keycloak0 → audit10 → grant-access20 → front30 → nginx40.
Перед package implementation проверить реальные dependencies/readiness образов.
Нельзя подменить реальный cyclic backend dependency ослабленным healthcheck или
sleep. Если подтвердится цикл, вернуть конкретную зависимость владельцу до обхода.
Конфигурационная ссылка на ещё не стартовавший backend сама по себе не runtime цикл.

Сверить все mount files/dirs/archives/fonts, Agent configs, entrypoint/command,
memory/heap и readiness paths с supplied materials и текущими SDKU PKI patterns.
Не переносить runtime secrets из исходных конфигов. В stage2 QA выбрать все5 apps,
но не делать4 optional slots обязательными для прежнего Keycloak-only проекта
без его явного desired-state изменения. Готовые пакеты — examples/szi; external
consumer получает optional identity default=false.

## 9. UI, Go и lifecycle Save

### 9.1. База дизайна и обнаруженные расхождения

ui-design-01.md задаёт одну scrolling Library Connections таблицу, summary на
instance General и existing account/Secrets editor. Отдельная instance Connections
tab удалена владельцем. HTML-макет содержит части прежних tabs/C proposal: не
переносить их в production. Перед UI реализацией синхронизировать затронутый
макет/дизайн с этим планом после owner approval. Demo values не становятся Core
правилами. Existing Draft/Review/Save/runtime input lifecycle остаётся текущим.

### 9.2. Изменения экранов

- Library / Подключения: в existing table добавить source type «Приложение» и
  selector «библиотека → предоставляемое подключение». Core отдаёт candidates,
  provider identity/compatibility, resolved URL/parameters. UI не вычисляет их
  и не разбирает Ansible YAML. Ссылка «Открыть источник» ведёт к export.
- Там же «Предоставляемые подключения»: имя, приложение, computed endpoint,
  произвольный parameters editor, credential source editor, defaults/override/Reset,
  Core-derived список потребителей. Source application/scripts через этот UI не меняются.
- App / Общее: optional connection enabled switch, effective source, Reset и
  ссылка к library binding. Название из пакета, не hardcoded «Интеграция СЗИ».
- App / Секреты: existing accounts provider selector использует active connections,
  умеет provider «Приложение». Accounts запись даёт стандартные username/password
  sources/runtime fields. Без accounts записи эти inputs не появляются. Disabled
  connection показывает retained settings неактивными, не удаляет их и не требует
  runtime password. Admin credential виден только как source reference, без значения.
- Existing Agent bindings показывают account identity source для runtime ENV;
  password/username не копируются в обычный environment editor.
- Review показывает смену connection reference, parameters/source overrides и enabled.
  Disabled сопровождается текстом «ранее созданные объекты сохраняются». Secret
  values отсутствуют. «Выбрано/не разрешено/нужен пересчёт» не выдаются за health.
  Смена revision не оставляет старый resolved URL под видом актуального.

Расширить guarded writer allowlists и current command intents, не вводить новый
Keycloak backend DTO. Provider choice accounts сохраняется current account alias
по connection. Canonical source schema единый для import/writer/Core/Agent.
Local Save остаётся node-free structural safety; unresolved references могут
сохраняться для дальнейшего Core finding. Verify/BuildPlan проверяют domain rules.
Versioned envelopes/fixtures/Go projections/React bindings обновить согласованно,
старые manifests без полей должны остаться рабочими. Список кандидатов/совместимость
не реализовывать повторно в Go/React. Никакого Apply из Applications editor.

## 10. Шаги реализации и файлы

| ID | Работа | Основные файлы | Результат |
| --- | --- | --- | --- |
| SZI2-01 | Canonical contracts/compatibility: exports, binding union, parameters/credentials, enabled, batch account Apply callback, provider_prepare и scripts gating/target | contracts/application-libraries; docs/project-contract.md, docs/ansible-core.md | schema examples/negative cases, no product branches; Verify contract unchanged |
| SZI2-02 | Resolve exports → active connections/accounts/jobs; private/public split и order checks | resolve_application_libraries, application_libraries.py, application_scripts.py, application_plan.py, project_snapshot | target-free projection, descriptors/fingerprint |
| SZI2-03 | Existing infrastructure batches; provider-ready hooks/account batch/dependent Vault/Agent; early publication used exports only; policy retention | application_providers.py, application_vault.py, provider-stage, ordered playbooks, package_script callers | no per-container Kafka calls; bounded sequence, generic runner |
| SZI2-04 | Все5 SZI packages, API templates/callbacks, no-delete routes, Agent/PKI | examples/szi | schemas/digests/renders и native image proofs |
| SZI2-05 | Один внешний consumer и library group/client hooks | chosen SDKU app/library | defaults=false, explicit QA override=true |
| SZI2-06 | Go guarded save/import, adapter/projections и review/runtime reuse | internal/installer, coreadapter, desktop | no second resolver/store |
| SZI2-07 | UI source/export forms, enabled summary, existing account provider UI | ApplicationsPage, ApplicationBindings, ApplicationCredentials, backend bindings, design/mockup | tested real handler flow |
| SZI2-08 | Focused/native/offline + real Wails/Core install/update and DIFF review | tests, evidence journal, QA recipe/runtime | evidence-bound acceptance |

Последовательность 01→02→03→04/05→06→07→08. После owner approval реализация в
отдельном worktree. Не переносить AGP changes целиком и не повторять stage1 DB reset.
После принятия границ обновить ADR/roadmap/UI design; пока этот документ — proposal,
не изменение действующих contracts. HIGH-RISK: public contracts/secret boundaries/
execution changes требуют одного независимого FULL DIFF review.

## 11. QA matrix

Test Scope: contracts/resolve, late provider lifecycle, packages/idempotency,
existing secret delivery, UI editing и реальная полная СЗИ + один external consumer.

| ID | Required / negative scenario | Evidence |
| --- | --- | --- |
| C01 | Legacy packages/accounts unchanged, defaults/slot/group_vars enabled/Reset, host override rejected | schema/unit + native Ansible effective settings |
| C02 | Arbitrary scalar/map/list round-trip, JSON/argv escaping, sensitive literal rejected, conflicting binding source | writer/schema/Core; no shell interpolation |
| C03 | Self/cross-library refs, missing slot/export, wrong order/callback/protocol | target-free findings; no target contact |
| C04 | Disabled / enabled no account / enabled with account; retained account after disable; another active consumer needs same secret | exact descriptors/jobs; no spurious prompts |
| C05 | Admin never copied to consumer Vault/env/config/public; same app password reaches API and Agent | private canaries/sanitized evidence |
| P01 | Fresh/repeat/user update, marker profile proof, foreign/existing mode, managed password rotation | actual image26.4 API read-back/login |
| P02 | API success/Vault fail/retry, provider health/one placement failure | consumer not started, forward recovery, no delete |
| P03 | Same-library grant-access and external SDKU: account → Vault → Agent → start; endpoint early enough | actual execution order |
| P04 | Все5 apps health/PKI/TLS/endpoints/Agent/JDBC/Hazelcast; multiple placements | real readiness and Verify |
| P05 | Client single POST/managed-field PUT, groups upsert, ID/subpath/description agreement | API objects; repeat changed=false |
| P06 | Arbitrary app route/updating endpoint; disable/removal of desired connection retains users/clients/groups/routes/Vault | two-target/catalog/API before-after, no prune |
| P07 | Atomic route rename/interruption, no legacy keys, nginx config/reload and repeat | Lua/container native fixtures + proxy request |
| P08 | Existing service Verify после update/disable остаётся работоспособным, не вызывает новые integration scripts/API inspections и не меняет identity/Vault/routes | regression spies/counters/digests; no new product Verify functions |
| P09 | N consumers/несколько placements: existing Kafka batch count unchanged; после Keycloak ready groups→clients→один accounts batch→Vault/Agent; unrelated providers not rerun;100 requests возвращают aggregate в stdout limit | native count/order/output assertions; partial error blocks delivery, retry completes |
| P10 | Один consumer ждёт два application providers: полный Vault document только после обоих, каждый provider batch once; pending startup rejected | mixed-provider fixture, no partial Vault writes/polling |
| P11 | Client secret shared source устанавливается API и достигает только explicit grant-access binding; no binding=no delivery; disabled/no use=no prompt; API success/Vault fail/retry | secret canaries, private inputs, no secret output; same value read inside app |
| P12 | Postgres + identity: disable и затем удаление identity из desired state не отзывает old token read, active PostgreSQL update проходит; foreign policy/capabilities rejected | native Vault retention scenario, source refs unchanged |
| P13 | Один shared document: early PKI password позволяет стартовать Keycloak; late client_secret дописывается после API без потери PKI; нет Agent binding — нет Vault field; stale CAS reread | native field-delta/owner proofs и runtime pipeline |
| C06 | Consumer-only Apply blocked по providedConnectionRef; provider+consumer accepted; transitive/self refs, no route-template introspection | target-free scope findings, no automatic scope expansion |
| C07 | Bootstrap/admin hooks use single export credential source; override/reset, existing admin mismatch fails without rotation | native source-resolution/API fixtures, no public secret |
| U01 | Provider/export/parameters/binding stage/review/save/reopen/reset/unresolved draft | actual React→Wails→Go, Core when applicable |
| U02 | Existing accounts provider selector/username/password inputs, no-account no fields, retained disabled sources | actual bindings + runtime inputs; secret exclusion |
| U03 | Revision/node/session change invalidates old candidates/URL/plan, late responses discarded | existing bridge lifecycle tests |
| U04 | Full install, fresh approved update/repeat, disable no-delete | BuildDeploymentPlan→approval→Start→terminal Apply/Verify |

Contract Scenarios include bounded refs/callback selection, all declared files in
digest, exact provider/consumer identity and parameter typing. Negative scenarios
must include missing runtime credentials, unsupported managed account provider,
Keycloak API failure and invalid TLS/name without reducing existing checks.

Regression Risks: service provider partition, Vault document ownership/source
replacement/retention, endpoint candidate/rollback guards, start_priority,
existing service Verify unchanged, config dir/archive reconciliation, import/save/reopen.
Do not relax guards to satisfy unrelated stale fixtures.

Environment Requirements: current source via qa-sync on RED OS; established
platform-automation identity/sudo-n, private PEM/runtime session and host-key trust;
prepared offline images/bundle/probe image per QA/runtime-bundle procedures.
Explicitly choose QA project/PKI identity, no silent clone. Capacity for5 apps must
be checked before concrete deployment approval, not inferred from stage1.

Not Testable Locally: Windows Python/Ansible, live Keycloak API/CLI, rootless
Docker/Vault/Agent/TLS. Real Wails bridge required for affected flows; mocks/direct
Go harnesses supplementary. Visual1440/1024 — separate recorded gate.
Focused checks first, then required Go test/vet, frontend tests/typecheck/lint/build,
full Core/affected providers and offline unshare tests. Record existing baseline
failures separately. Catalog/schema and package digests/renders reproducible.

## 12. Acceptance, review и rollout

Acceptance: actual5-app install/update, enabled external consumer, accounts→Vault→
Agent, no-change repeat, disable with live objects retained, exact identities/URLs,
real UI Save/Verify/BuildPlan/Start. Record revision, source/package/runtime digests,
plan/run IDs, terminal results и sanitized evidence. No passwords/tokens.

Stage1 full-regression limitations, AGP-D01 и missing prepared probe image —
отдельные prerequisites; план их не закрывает. New install/Apply требует concrete
recipe/fresh plan/owner approval в текущем lifecycle. Не создавать dump с новым
admin password, не делать live realm reimport/manual SQL repair. Failures stop
dependents; retry updates forward с теми же inputs. Existing endpoint rollback
сохраняется, удаления identity объектов как rollback нет.

Review budget: исходный FULL PLAN BLOCK сохранён. Владелец2026-10-22 разрешил
обсуждённые изменения и один TARGETED_RECHECK SZI2-P01/P02 и непосредственно
затронутых batching/lifecycle/secret-delivery границ. P03 закрывается единым export
source bootstrap/admin, P04 — canonical vault_ref без нового alias. Это intended
corrections, не утверждение reviewer resolution. При повторном BLOCK автоматическая
работа останавливается; третьего цикла без отдельного owner запроса нет. Review
не разрешает implementation/Apply и не закрывает stage1/AGP acceptance gates.

### Уточнение владельца после TARGETED_RECHECK, 2026-10-22

Владелец исключил расширение Verify: удалены предложенные verify_script/
account_verify callbacks и scripts verify-фаза. Existing Verify проверяет
работоспособность по текущим правилам; upsert read-back остаётся в Apply scripts,
новые интеграционные проверки — в QA. Это owner scope restriction после reviewed
SHA3B359B511D825F9C04C0142D09C27F1243FB302696C04F856E7E274B11AA249C и
documentary corrections SHA AFD92A4B4B030FC78C48442D6B012160FCC99A9ED966901D7CBC5599E04C4E83.
Исторические отчёты не переписываются, нового review не запускалось; прежний
verdict не выдаётся за независимое рассмотрение этой последующей правки.


### Owner-approved FULL DIFF corrections D01–D03, 2026-10-22

Owner accepted all three findings and authorized minimal general PKI correction.
D01: derive application PKI plans from its selected library profile/host using
existing materialization plans, independently of Agent/password bindings. Deliver
certificate.pem and private-key.pem unconditionally with existing CA/stores into
private instance pki; no new certificate generation or SZI branch. Agent delivery
and required Agent directory mount retain their prior contract; non-Agent packages
retain explicit mounts. Align SZI templates with canonical filenames and mounts.
D02: callback connection arguments use consumer library context; provided_connection
uses provider exports. Script source and target remain provider-owned.
D03: target.connection selects provider execution hosts before once/each_target;
actual target host participates in invocation identity and targetHostId argv.
Existing generic runner remains context-free. Owner-approved corrections receive
one TARGETED_RECHECK of D01–D03 and directly affected boundaries, not another FULL.

### Owner follow-up: safe Core failure codes, 2026-10-22

Preserve known fixed Core error tokens in the existing ExecutionEvent.error projection. Accept only exact known tokens from structured code/error_code or a code-only message; arbitrary result/output text is never journaled. no_log/censored task results retain redacted diagnostics. Keep Go transport unchanged; render existing errorCode/errorSummary beside failed tasks in both Installation event views. Validate callback/journal/controller classification, unknown/injected tokens, secret-bearing payload exclusion, real standalone Ansible callback, Go view preservation and React rendering. Include the correction in a new verified immutable runtime bundle before fresh Stage2 Apply/Verify and repeated Apply.

Owner UI/provider update (2026-10-22): connection usage toggles are file-only (defaults/group_vars), removed from UI. Library connection editing uses compact ENV-style parameter rows and credential tables. SZI exports one connection named sso; separate public export removed. Nginx reads only sso URL/realm from the resolved library projection, without requesting client provisioning; the three configured client consumers remain grant-access, grant-access-audit and grant-access-front.

Owner refinement 2026-10-22: remove secret entry from Installation/Plan. Application accounts keep existing inline inputs; library provided connection credentials and shared secrets use the same session fields. Vault administrative token keeps its existing input in Infrastructure → Vault → Secrets; no duplicate library field or backend extension. No secret values enter desired state.

## Owner follow-up: REST provider execution on Execution Node (2026-10-22)

Keycloak integration uses curl and jq directly on the selected Execution Node. It does not launch a Compose helper container, use Java/kcadm/keytool, or require access to Docker on the process host. It calls the published redundant HTTPS endpoint using installed system CA trust. Authentication form bodies, tokens, API responses and optional account/client-secret inputs remain invocation-private and are cleaned after execution. The package retains declared API reconciliation/readback semantics and existing-mode restrictions.

An explicit generic scripts[].run_on=execution_node with execution=once selects process location. The default target behavior is unchanged. The connection target continues to associate a provider preparation hook with the correct dependency/batch. Core delegates the generic runner to localhost (the Core Execution Node), uses the invocation project root and current process account, and passes only declared argv/private inputs. The provider callback also carries this location for the single batched account invocation. No Keycloak/product condition is added to Core.

On failure the generic runner keeps raw command output under no_log and emits only APPLICATION_SCRIPT_EXECUTION_FAILED plus bounded numeric rc/step/http_status/curl_exit. The existing Journal stores the safe diagnostic and existing Go/UI error projection displays it. No second log store or raw response persistence is introduced. The script ID is part of the failure task name. See the canonical project contract for limits. The owner explicitly stopped the follow-up review; further review is not requested.
