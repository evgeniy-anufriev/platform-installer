# A1 — минимальный контракт и сквозные fixtures

Технический план, подготовленный 2026-10-10. Область — A1 из
[общего плана](../../implementation-plan.md). Это предложение к реализации;
подготовка документа не разрешает Apply, изменения targets, сборку bundle или
переход к A2. Актуальный статус остаётся в [CURRENT_STATE](../../../../../CURRENT_STATE.md).

## 1. Результат A1 и границы

Получить один документированный Ansible-native контракт и read-only путь,
который разрешает библиотеку, её экземпляры и размещения из inventory/vars,
проверяет их и возвращает детерминированную безопасную проекцию Core.

A1 включает schemas, минимальное разрешение обычным Ansible, target-free
validation, компактные fixtures и проверки совместимости. Не включает
генерацию файлов на Docker-хостах, pull/load/up, создание УЗ/БД, Vault writes,
выдачу RoleID, публикацию endpoint, Go writer или UI. Эти операции принадлежат
следующим этапам. Описание будущего hook input не означает готовый hook.

## 2. Сначала зафиксировать единый источник каждого поля

| Область | Канонический источник | Производный результат |
| --- | --- | --- |
| Host identity и SSH transport | inventory и существующие host vars | hostId; `SERVER_ID = inventory_hostname` |
| Состав/слоты библиотеки | versioned library package defaults | выбранные определения приложений |
| ID библиотеки, bindings, ресурсы и overrides слотов | `platform_desired_state.applicationLibraryDeployments` в group_vars | library projection; instance ID = application name + library ID |
| Размещение библиотеки | `platform_application_libraries` в host_vars | список host targets |
| Application runtime defaults | defaults versioned application role | effective nonsecret settings |
| Credentials | source descriptors в vars + существующий защищённый runtime input | требования секретов, без значений |
| Package identity и image requirements | существующий lock/fingerprint механизм с расширением | exact revision и требования доставки |

Installer-managed файлы сохраняют текущие пути
`inventory/group_vars/all/platform-installer.yml` и
`inventory/host_vars/<host>/platform-installer.yml`. Standalone допускает обычные
operator-owned vars. `ansible.cfg` сохраняет установленный `hash_behaviour=merge`.
Не добавлять второй список хостов в library group_vars или новое поле server ID.
Не читать весь каталог host_vars рекурсивно в обход существующего reader.

## 3. Пакеты и defaults

Предлагаемая локальная структура переносимого проекта:

```text
application-packages/apigateway/1.0.0/
  application.yml
  roles/application_apigateway/defaults/main.yml
  roles/application_apigateway/templates/apigateway.compose.yml.j2
  roles/application_apigateway/templates/agent.hcl.j2
  files/                         # остальные явно разрешённые исходные файлы
library-packages/sdku/1.0.0/
  library.yml
  roles/library_sdku/defaults/main.yml
  roles/library_sdku/templates/.base_compose.yml.j2
  files/.env                     # общие пользовательские nonsecret параметры библиотеки
```

Manifest содержит имя/версию, ссылки на defaults/schema/templates и декларации
подключений/identity bindings. Effective values находятся в role defaults и
обычных overrides; manifest не хранит вторую копию тех же defaults. Metadata
не допускает произвольный hook command или путь плейбука от экземпляра.

Шаблон `agent.hcl.j2` принадлежит application package; A2 материализует его
как `agent.hcl` в runtime volume экземпляра на каждом хосте. Пример и входы
проекции приведены в [описании Vault Agent](../../secrets.md#шаблон-agenthcl-в-пакете-приложения).

Defaults приложения содержат image requirement, command argv, user/restart,
listeners/ports, nonsecret environment, параметры, endpoint backend settings,
provisioner и secret bindings. `application_name` берётся из определения
`applicationRef`, например `apigateway`, независимо от `apigateway-cspa`.
Шаблон command `/opt/{{ application_name }}/bin/{{ application_name }}`
разрешает Ansible. Пакет вправе задавать другой argv для своего образа;
не вводить обязательное соглашение о расположении binary для всех приложений.

Defaults библиотеки содержат именованные slots, общие настройки, требования
infra bindings, ресурсы и shared secrets. Для fixture достаточно одного slot:

```yaml
# library role defaults, сокращённо
platform_library_definition:
  slots:
    gateway:
      applicationRef: apigateway@1.0.0
      required: true
      overrides:
        parameters: {log_level: INFO}
```

## 4. Связь recipe slot → автоматически вычисленный instance ID

Ключ `applications` выбирает slot библиотеки; определение приложения берётся
из этого slot. Пользователь задаёт только ID экземпляра библиотеки. Ansible
вычисляет `application_instance_id = application_name ~ '-' ~ library_instance_id`:
для приложения `apigateway` в библиотеке `sdku` получается `apigateway-sdku`.
Отдельного поля ID приложения и повторного applicationRef в overrides нет:

```yaml
platform_desired_state:
  applicationLibraryDeployments:
    sdku:
      libraryRef: sdku@1.0.0
      runtimeRef: docker-apps
      bindings:
        database: {deploymentRef: postgres-sdku}
        cache: {deploymentRef: redis-main}
        messaging: {deploymentRef: kafka-main}
        analytics: {deploymentRef: clickhouse-main}
        secrets: {deploymentRef: vault-main}
        application_pki: {profileRef: apps-pki}
      applications:
        gateway:
          overrides:
            ports: {http: {published: 18081}}
            parameters:
              log_level: DEBUG
              redis:
                user: test-user
                password_ref: my-redis-password
```

Вычисленный ID автоматически проецируется во все объявленные identity bindings,
а Redis account descriptor берётся из defaults приложения по
`parameters.redis.user` и `password_ref`, как в [конфигурации](../../configuration.md).
Mode, source kind, grants и secret bindings не повторяются в обычном экземпляре;
явные `accounts` overrides предназначены для редких изменений. Descriptor templates
разрешаются Ansible после merge parameters; plaintext password не допускается.

Вычисленный ID определяет
пути экземпляра и имена Vault policy/AppRole. A1 требует один instance на slot;
отсутствие required slot, неизвестный slot и повтор одного определения приложения
в разных slots библиотеки блокируются, чтобы вычисленные IDs не столкнулись.
Несколько логических экземпляров одного определения потребуют отдельного явного
расширения. Один логический instance на нескольких хостах уже поддерживается
размещением библиотеки, без дополнительных instance declarations.
Старые опубликованные проекты без libraries не мигрировать.

В host_vars `node1` и `node2` одна и та же membership:

```yaml
platform_application_libraries:
  sdku: {}
```

A1 размещает весь состав библиотеки на этих хостах. Subset placement отдельных
приложений не добавлять без отдельного требования. Host-scoped overrides допускают
только параметры размещения, документированные schema; они не переименовывают
instance, не меняют library/application refs и общие provider resources.

## 5. Разрешение переменных без второго precedence engine

1. Ansible штатно загружает inventory/group_vars/host_vars на Execution Node.
2. Из refs выбираются exact versions доверенных application/library packages.
3. Общая resolve role загружает role defaults пакетов в изолированные namespaces.
   При выборе `include_role`/`include_vars` проверить обычную доступность role
   defaults и не подменять документированную Ansible precedence ручным YAML reader.
4. Явный `combine(recursive=true, list_merge='replace')` соединяет разные inputs:
   application defaults → library slot overrides → instance overrides → разрешённые
   host-scoped overrides. Это композиция сущностей, не восстановление Ansible
   precedence. Нет удаления через `null` или неявного слияния списков.
5. Identity projections добавляются после merge; пользовательские overrides
   reserved env names блокируются. Jinja разрешает Ansible, не Go/Python.
6. Core validator потребляет эту же resolved projection. Отдельного Python merge
   или второго resolver для snapshot не создавать; structured action вызывает
   общий Ansible resolve путь с точной ревизией входов.

Первая работа A1-03 — небольшой прототип обычной последовательности
playbook → resolve role → existing structured action. Основные входы:
`ansible-core/playbooks/project-snapshot.yml`, `project-snapshot-machine.yml`
и `validate.yml`; остальные snapshot consumers подключаются к тому же пути.
Role должна выполнить controller-only resolve на Execution Node без подключения
к targets и передать результат action через machine-owned Ansible variable/argument,
валидируемый по schema и привязанный к source revision. До полноценной интеграции
schemas с entrypoints доказать передачу двух instances и двух host projections с фактическими
Ansible hostvars/defaults. Способ обработки host context выбрать в этом прототипе;
не заявлять доступность несуществующего entrypoint. Action не запускает Ansible
рекурсивно и не принимает эту проекцию как альтернативный user-authored desired state.

Проекция каждого элемента loop независима: никакие set_fact/defaults предыдущего
instance или хоста не переходят к следующему. Не исполнять пользовательские
application tasks на стадии read-only resolve; доверенные templates/defaults
всё равно требуют контроля происхождения, поскольку Jinja не является sandbox.

## 6. Identity, Compose layout и multi-host

Зафиксировать в projection `libraryId`, `instanceId`, `applicationName`, `hostId`
и отдельные ссылки на выбранный Docker deployment/member. `instanceId` вычисляется
как `<applicationName>-<libraryId>`, а `SERVER_ID` равен
существующему inventory host ID. Логический ID приложения одинаков
на всех хостах. Per-host identity env требует явного binding в defaults; нельзя
молча дописывать host suffix к Kafka application/group ID.

Предлагаемый минимальный layout будущего A2: один Compose project на сочетание
project/library/instance/host. Все экземпляры библиотеки на хосте используют
один явный `--env-file` библиотеки. Base Compose библиотеки также один на хост,
переиспользуется локальными instance Compose через `extends`. Исходный library
package `files/.env` — desired input с общими пользовательскими
nonsecret параметрами без обязательной Ansible projection. Runtime `.env`
сохраняет эти ключи и получает явно объявленные projection keys (включая
`SERVER_ID`); reserved-key conflicts валидируются. Исходный файл входит в package
fingerprint и перенос. A1 фиксирует поддерживаемый dotenv syntax и сохранение
обычных пользовательских значений, A2 материализует файл для library/host.
Instance-specific overrides материализуются в environment соответствующего
Compose service, не меняют общий `.env` библиотеки.
`.env` содержит только nonsecret settings и `SERVER_ID`; одно имя
instance не может менять интерполяцию соседнего экземпляра. Пути base/extends
локальны одному хосту. Имена Compose project и пути должны учитывать project
namespace; простого `apigateway-sdku` недостаточно для разных portable projects.

A1 вычисляет descriptors имён/путей/портов, но файлов не создаёт. Ограничения
Docker names/path components валидируются; silent sanitization с возможными
коллизиями не использовать. Одинаковый published port на разных хостах разрешён,
на одном runtime/адресе/порту — конфликт. Hostname/container name могут использовать
`{{ application_instance_id }}-${SERVER_ID}` в package template.

## 7. Secret descriptors и будущие hooks

A1 фиксирует `connection_defaults` в library role defaults, с ключом serviceType
существующего каталога и override на уровне экземпляра библиотеки. Binding
хранит deploymentRef; connectionRef не повторяется по deployments. Для Kafka
selector обязателен, для остальных опускается при единственном интерфейсе,
подходящем требованиям connection приложения. Redis/Sentinel различаются
назначением; TLS policy не подменяется именем listener. Core переиспользует
Kafka listener resolution и небольшую явную mapping существующих effective
проекций остальных providers. Infrastructure apply roles и их desired state
не меняются; нет нового каталога, Go/UI resolver или постоянной runtime-модели.
Подробные примеры и первоначальная матрица — в [конфигурации](../../configuration.md#выбор-интерфейса-подключения-по-servicetype).

Для всех hooks A1 фиксирует единое условие: нет соответствующего service ref
в effective bindings — hook пропускается; есть ref и декларация действия —
hook включается. Заданный unknown ref или обязательная зависимость объявленного
действия без ref блокируются validation. Не добавлять автоматический выбор
provider. HAProxy/DNS references и действия проверяются независимо.

Непустой effective `accounts` включает credential provisioning. При отсутствии
или пустом accounts projection не требует account hooks и credential writes.
Непустой effective secret_bindings включает Agent, policy/AppRole/RoleID и
identity mounts, в том числе для shared-secret-only без accounts. Каждая source
содержит ровно account+field либо library_secret; смешанные и неполные источники
блокируются. Проверка выполняется после overrides. Ресурсы библиотеки и endpoints
независимы; без secret_bindings используется прямая команда приложения.

Схема различает `generated`, `runtime_secret_ref`, `vault_ref`, `pki_credential`
и связь app env → account field/library secret. Для mode existing запрещены
managed mutations; missing credential requirement показывается отдельно от
structural validation. В refs нет plaintext password, token, RoleID или private key.

В A1 описать входы/выходы будущих provider hooks, не реализовывать их:

- resources библиотеки подготавливаются один раз до instances;
- УЗ/grants логического instance едины для его host placements;
- managed KV v2 create = put CAS=0; изменение = patch CAS=current version;
  одинаковые данные не создают версию, vault_ref остаётся read-only;
- AppRole `bind_secret_id=false`; RoleID credential хранится только в защищённом
  runtime volume на каждом хосте, Agent mount read-only;
- `token_bound_cidrs` — derived requirement от размещения. Target-free A1 не
  назначает CIDR по SSH address: фактический адрес выхода к Vault при rootless/NAT
  разрешается в execution preflight A4. Неизвестный маршрут остаётся prerequisite;
- command argv Agent исходит из application defaults, не из instance ID;
- endpoint backend defaults/overrides отображаются в существующий provider
  contract, targets = readiness каждого host placement + published listener.

Kafka fixture требует только SSL listener без SASL. SCRAM/ACL capability не
считать реализованным из-за предложенного формата account. Provider capability
validation должна отличать требования структуры от доступности исполнения;
неподдерживаемый hook блокирует execution, а не маскируется mock principal.

## 8. Image/package trust до A2

Использовать уже собранный [QA image](../../../../../docker/application-connection-probe/qa-result.md).
Его `sha256:acd94e424cb685723e768de1e1b0a7f98ffe5b491f4666a6a89888a31bf64ebb`
— Docker image ID, не registry manifest digest и не checksum будущего tar.
Fixture application может называться apigateway, но его command для QA image
явно равен `/usr/bin/connection-probe`, а не `/opt/apigateway/bin/apigateway`.

A1 фиксирует package version/content fingerprint, доверенные локальные sources,
допустимые файлы и image platform/identity requirements через существующие locks.
Не пересобирать образ и не создавать registry только для A1. Архив/transfer/load
и compose pull принадлежат A2.1. Target-free resolve не опрашивает registry и
Docker daemon. Отсутствие offline archive описывает незакрытое требование доставки.

Пути package refs проверяются внутри portable project; запретить absolute paths,
`..`, escape через symlinks и неявное чтение соседних пакетов. Digest фиксирует
содержимое, а разрешение исполнения даёт выбранная доверенная область пакета.
Без этого A2 не начинается. Не строить signing service или новый package manager.

## 9. Точки расширения текущего проекта

| Точка | Работа A1 |
| --- | --- |
| `contracts/project/*/desired-state.schema.json` | Версионированное расширение applicationLibraryDeployments; прежние версии не ослаблять удалением additionalProperties guards |
| `contracts/project/v2alpha1/host-desired-vars.schema.json` и текущие readers | Проверить отдельную schema host membership; platform_host не смешивать с application placement |
| `platform.core` roles + общий Ansible resolve entrypoint | Namespaced defaults, composition и target-free projection |
| `plugins/action/project_snapshot.py`, `validate_project.py` | Потребление новых vars и общего resolve; прежние service paths сохраняются |
| `module_utils/project_state.py`, `project_validation.py` | Reference checks, findings и canonical revision inputs без самостоятельного precedence/Jinja |
| `contracts/project-snapshot/*` + `module_utils/project_snapshot.py` | Минимальная versioned проекция libraries/instances/placements/secret requirements |
| Существующие lock/revision/package transfer tools | Включение package inputs и content identity без второго persistence |
| `examples/valid`, `examples/invalid`, Core tests | Compact fixtures и негативные проверки |

Перед кодом выбрать exact schema versions по текущему version dispatch и
строгости consumers: не выдавать новые required semantics под прежней версией.
Проверить, что action сейчас использует project v2alpha1 schema напрямую;
добавление только нового schema-файла не подключит его к выполнению.
Если текущий snapshot consumer не поддерживает расширение, новый режим должен
отклоняться явно; A1 не добавляет Go DTO/writer ради обхода этой границы.
В A7 останутся production plan/DAG/execution integration, а не второй resolver.

## 10. Последовательность работ и артефакты

1. **A1-01 — контракт:** закрыть slot mapping, allowed host overrides, namespaces,
   shapes refs/secret descriptors; синхронизировать configuration/architecture
   и канонические contracts/ADR/roadmap при изменении границы.
2. **A1-02 — schemas:** реализовать выбранные versioned schemas и dispatch;
   old project validation остаётся прежней. Не вводить automatic migration.
3. **A1-03 — read-only resolution:** сначала прототип playbook/role/action
   передачи результата из раздела 5, затем общий путь defaults → effective
   settings → host projections. Проверить два instances и два hosts.
4. **A1-04 — Core projection:** safe structured output, findings с exact field
   path, revision/package identity; нет secret values или target probes.
5. **A1-05 — fixtures:** СДКУ и ЦСПА, общий QA application package, отдельные
   logical instance IDs и PostgreSQL refs, shared Kafka/Redis/ClickHouse/Vault
   where intended; host node1 содержит обе библиотеки, node2 — СДКУ.
6. **A1-06 — QA:** focused tests на RED OS из текущей рабочей копии, журнал
   `docs/work/application-libraries/milestones/a1/evidence/a1-test-journal.md` создаётся при реализации.
7. **A1-07 — gate:** независимый DIFF review для изменённых публичных/security
   contracts по стандартной процедуре; owner получает evidence и ограниченный
   результат A1. Следующий A2 требует отдельного разрешённого scope.

## 11. Минимальная матрица QA

| Проверка | Ожидаемый результат |
| --- | --- |
| Standalone inventory/defaults/group_vars/host_vars без project.yml | Одинаковая safe projection через общий Ansible путь |
| СДКУ/ЦСПА, один application definition | Разные instance IDs/bindings; binary application name одинаков |
| Application apigateway, library IDs sdku/cspa без ID приложения во входе | Вычислены apigateway-sdku/apigateway-cspa; все identity bindings используют вычисленный ID |
| СДКУ на node1/node2 | Одна логическая библиотека, два placement records, SERVER_ID node1/node2 |
| Два instances на node1 | Независимые parameters/env/path/port projections, нет loop leakage |
| Required slot missing, повтор определения приложения в slots, unknown refs/host/runtime | BLOCKED finding с точным полем |
| Port/name/path collision, source path escape | BLOCKED без target contact |
| Generated/runtime_secret_ref/vault_ref/PKI binding | Только descriptors; missing runtime value не печатается и не запрашивается при pure resolve |
| Accounts отсутствует/пуст, secret bindings отсутствуют | Нет credential/Vault/Agent steps; обычный запуск и независимый endpoint |
| Provider ref отсутствует, действия для него не объявлены | Соответствующий hook SKIP; прочие hooks независимы |
| Два Kafka deployments одного serviceType | Общий connectionRef из library defaults проверен на каждом deployment |
| Kafka без selector; unknown/несовместимый selector | BLOCKED с точным полем |
| Другой provider без selector, один/несколько подходящих интерфейсов | Единственный разрешён; неоднозначность BLOCKED; Redis не выбирает Sentinel |
| Изменённый effective порт/member address/TLS | Подключение следует проекции сервиса, не manifest defaultPort |
| Provider ref задан, но не разрешается; либо действие требует отсутствующий ref | BLOCKED finding с точным полем |
| Accounts пуст, shared secret binding объявлен | Agent/AppRole требуются без account hooks; неизвестный shared secret или отсутствующий Vault ref блокируются |
| Literal password/token/RoleID в desired fields | Отклонение schema/secret checks, safe error без значения |
| Unsupported SASL/account capability | Не становится разрешённым execution по факту успешного shape validation |
| Defaults/override/list precedence | Штатный Ansible и explicit combine; отсутствует Python/Go substitute |
| Исходный library package .env с пользовательскими ключами | Один runtime .env на library/host для всех instances; сохранение значений, reserved-key conflicts явные, изменение файла меняет fingerprint |
| Package content или host placement changed | Меняется fingerprint; старое execution approval не пригодно |
| Legacy проект без libraries, unknown/incompatible version | Сохранён прежний результат либо явный version BLOCK; нет hidden migration |
| Повтор read-only resolve, другой порядок ключей | Детерминированная canonical projection/fingerprint без writes |

Проверки A1 не требуют изменять уже развёрнутый full-services или запущенный QA
контейнер. Прямой read-only Ansible тест здесь является доказательством A1;
Go/UI flow acceptance появится на соответствующих следующих этапах.

## 12. Критерии выхода

A1 завершён только когда контракт и fixtures совпадают, общий resolve работает
без Go/UI, две библиотеки и multi-host размещение разрешаются независимо,
секретные значения отсутствуют во всех outputs, target-free проверки сохранены,
старые проекты не регрессировали и границы доверия определены до будущего A2.
Отдельно перечислить незакрытые execution prerequisites (providers, NAT route,
image archive). Они не исчезают из-за успешного structural resolve.

Независимое FULL PLAN review и bounded correction:
[отчёт A1](reviews/a1-plan-review.md).
