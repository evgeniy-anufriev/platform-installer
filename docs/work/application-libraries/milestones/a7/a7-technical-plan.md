# A7. Core snapshot, validation, planning и execution contract

Дата: 2026-10-12. Ветка: `codex/application-libraries`.
Исходная версия: `bb32857`. Статус: технический план; реализация не разрешена
этим документом. Авторитетный статус — [CURRENT_STATE](../../../../../CURRENT_STATE.md).

## 1. Цель и граница этапа

Завершить структурированный Core-контракт библиотек, используя standalone A1–A6:
одинаковые effective Ansible variables, resolver, provider hooks, доставка
образов, runtime Apply/Verify и endpoint hooks. Не вводить второй исполнитель,
независимое объединение defaults/vars или новый scheduler.

A7 готовит snapshot, findings, fingerprints, планируемые действия, private
manifest и поддержку действий фиксированным controller. A8 соединяет эти
действия с общим инфраструктурным планом и доказывает обязательный барьер
после Verify **всех** инфраструктурных deployments. До A8 смешанный план
не должен получить право production Start без этого барьера.

Это принципиальная граница: поддержка application operations в controller
сама по себе не разрешает исполняемый общий план. Нельзя просто убрать
`APPLICATION_LIBRARY_EXECUTION_NOT_IMPLEMENTED` и возвращать EXECUTABLE.
Для application-проекта A7 возвращает структурированный BLOCKED с finding
о незавершённой интеграции общего плана, без исполняемого manifest. Полный
план разрешается в A8. Внутреннее построение application actions проверяется
контрактными тестами и не становится новым публичным selective API.

Не входят: Go models/adapter, React, UI секретов/редактор библиотек,
новый API выборочной установки, Kafka ACL/SASL, migrations, новые hooks,
повторная реализация PKI/Vault/HAProxy/DNS и benchmark.

## 2. Подтверждённый исходный код

| Механизм | Текущее состояние | Изменение A7 |
| --- | --- | --- |
| `project_snapshot.py` action | Уже собирает `applicationLibraries` через native rows и проверку package identities | Довести публичную проекцию, origins/findings и fingerprints |
| `project-snapshot-machine.yml` | Уже условно вызывает `resolve_application_libraries` | Сохранить обычную Ansible precedence и отсутствие target contacts |
| Snapshot `v2alpha1` | Существует application-aware schema | Расширять её в рамках допустимой совместимости, не создавать второй snapshot |
| `deployment_plan.py` | Явно отклоняет snapshot `v2alpha1` | Заменить исключение корректным результатом BLOCKED; добавить построение application actions/requirements |
| `build_deployment_plan.py` action | Пишет защищённый private manifest из Core результата | Сохранить атомарную запись, права и связку digest; не выдавать manifest для BLOCKED |
| `execution_controller.py` | Имеет фиксированные команды для service/PKI operations | Добавить только фиксированные application Apply/Verify |
| Standalone playbooks A1–A6 | Выполняют рабочий полный application pipeline | Переиспользовать, без копирования provider tasks в controller |
| `execution_secret_lease.py` | Typed input requirements пока привязаны к service operations | Добавить application scope явно, без маскировки библиотеки под service deployment |

В публичной application projection остаются переходные значения
`imageRequirement.delivery=DEFERRED_TO_A2_1` и
`approle.token_bound_cidrs=DEFERRED_TO_EXECUTION_PREFLIGHT`.
Первое заменить корректным desired requirement; второе явно обозначить как
runtime-only derivation. Target-free snapshot не должен выдумывать observed CIDR.

## 3. Единые данные и validation

### 3.1. Snapshot

Оставить одну `applicationLibraries` projection. Для библиотеки показывать:
ID, package identity/digest, resources, provider references, shared-secret
requirements и instances. Для экземпляра: application/package identity,
производный ID, placements по inventory host ID, image requirement,
несекретные parameters, connectionRef и resolved connections, accounts/grants
без credential values, secret bindings, endpoint projection.

Не добавлять в public snapshot: passwords, Vault admin token, role_id,
unseal keys, rendered secret templates, содержимое `.env`, SSH keys,
runtime credential paths или полные hostvars/defaults.
`role_id` получает контейнер только при выполнении A4; snapshot содержит
декларацию AppRole, а не результат создания роли.

Defaults/group_vars/host_vars разрешаются Ansible. Python использует готовые
rows; повторный deep merge для plan запрещён. Проекцию и исходные package
digests сверять существующими проверками, не обходить их через raw desired YAML.

### 3.2. Findings и origins

Использовать существующий формат finding. `field` должен указывать на точный
library/instance/connection/resource/parameter; host override имеет host scope.
Origin показывает логический источник и переменную, без значений секретов.
Если Ansible merge не сохраняет происхождение конкретного leaf, фиксировать
честный уровень known origin, не реконструировать precedence по эвристике.

Проверки: providers существуют и имеют capability; Kafka listener выбран явно;
для единственного listener допускается существующий default; обязательные
account/shared-secret bindings полны; placements ссылаются на Docker hosts;
package/schema версии поддерживаются; runtime/image lock совместим;
endpoint identity и backend names не конфликтуют. Использовать существующие
A1–A6 проверки, а не запускать повторно SQL/Vault/DNS или docker inspect.

Проект без библиотек продолжает прежний путь. Отсутствие accounts/service ref
сохраняет существующий skip соответствующего hook. Отсутствие secrets не требует
Agent/Vault inputs. Validate и snapshot не читают credential values.

## 4. Artifact requirements и стабильность плана

Подключить image requirements A2 к существующей artifact/source authority.
Snapshot и target-free plan содержат requirements, node-scoped source policy
и immutable lock/runtime identity. BuildDeploymentPlan не выполняет repository
probes и не выбирает конкретный источник образа.

После approval существующий execution resolver выбирает совместимый approved
repository на узле, иначе verified offline bundle, иначе блокирует выполнение
до соответствующей image/container mutation. Конкретный источник хранится
только в execution RuntimeProjection и observed execution result, с привязкой
к node/runtime/bundle. Docker targets могут иметь разные источники;
не переносить решение одного хоста на остальные.

Plan fingerprint включает project revision, effective rows/package digests,
placement, resource/connection/account declarations, secret references и
bindings, endpoint/backend settings, artifact requirements, source policy,
immutable lock identity и runtime release.
Не включает выбранный repository/offline source, результаты repository probes,
доступность registry, timestamps, observed Running/health, секретные значения и роль,
полученную от Vault при предыдущем запуске. Для одинаковых входов порядок
library/instance/host/requirement должен быть детерминированным.

Смена referenced secret value не создаёт plaintext fingerprint в public plan.
Текущий защищённый lease привязан к точному plan/manifest и проверяется перед
мутацией; неприменимый или отсутствующий lease отклоняется существующим путём.

Нельзя считать snapshot PASS доказательством provider readiness: это target-free
структурная проверка. Native readiness A3–A6 выполняется перед mutations.

## 5. План действий без раздробления playbooks

Сохранить текущие provider batching правила: resources — один batch на библиотеку,
accounts/grants — один вызов на application instance, не общий batch по deployment.
Не превращать каждый SQL grant, Vault field, Ansible task или placement в
отдельную controller operation.

Минимальная предлагаемая гранулярность для дальнейшего общего плана:

| Action | Назначение | Исполнитель |
| --- | --- | --- |
| `APPLICATION_LIBRARIES_APPLY` | Весь resolved application scope; resources перед instance actions; затем запуск и endpoints | Существующий `application-libraries-apply.yml` |
| `APPLICATION_LIBRARIES_VERIFY` | Наблюдаемый результат контейнеров/providers/endpoints | Существующий `application-libraries-verify.yml` |

Одна Apply и одна Verify на весь application scope проекта, содержащий все
заданные библиотеки. Это не selective-install API и не объединение SQL jobs:
внутренние loops/batches A3–A6 сохраняются. Для отображения внутри каждой
operation достаточно существующих Ansible task events и library/instance/host
context; отдельных Ansible процессов на hooks и контейнеры не создавать.

Public actions описывают IDs, targets, dependsOn, mutating и безопасный summary.
Private operations содержат trusted runtime projection и ссылки на requirements,
но не credentials. Public plan и private manifest выводятся из одного semantic
model, не строятся независимо. Последующая Verify зависит от Apply.

A8 добавит зависимости первой application mutation от **всех** infrastructure
Verify общего плана. При failure/cancel ни одна application mutation не запускается.
A7 не добавляет обход этого правила через выбор libraryId в запросе.

## 6. Fixed execution и runtime inputs

Controller принимает только разрешённые operation types и значения из
digest-protected manifest. Application playbook path зафиксирован в release;
argv/произвольный playbook/CLI flags от клиента запрещены. Inventory и project
copy принадлежат тому же run, что manifest. Перед запуском проверить revision,
release/bundle identity, manifest digest и credential binding обычным протоколом.

Повторно использовать защищённые runtime projection files и существующее
материализованное credential root. Передать существующим ролям native vars
и authority A2, без нового runtime-secret хранилища. Apply/Verify должны получать
один согласованный execution context — inventory, vars, limit и Ansible env;
не запускать вложенный ansible-playbook из application hook.

Requirements включают только реально используемые account/shared secrets,
provider admin credentials, Vault admin token и registry credentials.
Дедупликация допустима для одного ref с совместимыми purpose/scope; конфликт
назначения или host/operation binding даёт finding, не молчаливое объединение.
Accounts отсутствуют — account credentials не требуются; endpoint disabled —
endpoint inputs не требуются. Verify запрашивает только используемые inputs.

Core принимает уже расшифрованный Vault token через runtime inputs или
существующие plaintext bootstrap-files standalone. Расшифровка выбранного `.age`
для Installer остаётся будущей задачей Go; age CLI/Python age decoder не добавлять.
CIDR `/24` хоста и `127.0.0.1` вычисляются existing A4 runtime logic.

Cancellation, timeout, safe events и private failure output используют существующий
controller. При частичной ошибке не выполнять автоматический rollback пользователей,
БД, secrets или DNS. Повтор идёт штатным идемпотентным Apply; не создавать resume DB.

## 7. Версии контрактов и bundle

До кодирования составить короткую таблицу изменяемых enum/closed properties:
plan action types, capabilities/request versions, snapshot fields, runtime-secret
descriptors/lease и private operation validation. Старые версии не должны вдруг
принимать новую семантику через произвольные additionalProperties.

Сохранить infra-only текущие request/plan версии. Для application-aware контракта
выделить следующую свободную minor версию только где существующая closed schema
не допускает нужный shape; не занимать `plan/v1alpha3`, уже имеющую selective scope.
Capabilities честно объявляет поддержанные requests, но не EXECUTABLE applications
до A8. Unknown major и несовместимый lock отвергаются; скрытой миграции нет.
Конкретные номера новых minor фиксируются в реализации вместе с schema tests.

Реализация A7 фиксирует следующую карту (A7-P02):

| Граница | Версия и поведение |
| --- | --- |
| Native snapshot | Существующий `project-snapshot/v2alpha1` для непустых библиотек; `v1alpha1` без библиотек. Добавлены scope provenance и per-host image requirements |
| План | Новый `plan/v1alpha4`: application actions и container-image requirements. Старые v1alpha2/v1alpha3 неизменны; application plan обязательно BLOCKED до A8 |
| Secret descriptors | Новый `BuildRuntimeSecretDescriptors/v1alpha3` с отдельными `applicationInputs`; без библиотек остаётся v1alpha2 |
| Private preparation | `execution-manifest/v1alpha2/application-operation.schema.json` описывает только закрытый application operation fragment; это не полный исполняемый manifest |
| Lease и Start | Существующие typed runtimeSecretValues/lease payload и Start; новые application credentials используют requirementRef и защищённое хранилище запуска |
| Capabilities | Существующая инфраструктурная capability неизменна. Application execution и новый Installer descriptor flow не рекламируются до интеграции A8/Go |

`applicationExecution` — приватный preparation fragment результата Core. Он не
регистрируется как manifest, не возвращается callback как execution authority и
не разрешает Start. Его operations имеют опубликованную closed schema; требования
секретов проверяются существующим runtime lease consumer с отдельной библиотечной
областью действия. A8 должен связать этот fragment с полным manifest admission.

В bundle включить resolver/action plugins, application/provider playbooks,
roles, package templates и schemas, необходимые существующему pipeline.
Не включать проектные secrets или все возможные images. Проверить closure
выбранной representative библиотеки и lock на package/runtime identity.
Использовать existing builder/validator/publisher по [процедуре](../../../../agent-procedures/runtime-bundle.md).
В рамках A7 сначала build/validate; publication/rebind только при необходимости
авторизованной dependent QA. PROD не скачивает отсутствующие images.

## 8. Подэтапы и файлы

| Подэтап | Работа | Основные точки изменения | Выход |
| --- | --- | --- | --- |
| A7.0 | Инвентаризация closed schemas/guards и согласование гранулярности | contracts/plan, snapshot, execution-capabilities, runtime-secret; deployment_plan/controller | Один scope/version map, без нового desired-state |
| A7.1 | Public snapshot/findings/origins | application_libraries.py, project_snapshot.py action, snapshot schema/tests | Secret-safe target-free projection без устаревших A2 placeholders |
| A7.2 | Image requirements и fingerprints | application_runtime.py/helpers A2, deployment_plan.py, authority tests | Общая source policy и стабильная semantic identity |
| A7.3 | Application actions/manifest descriptors | deployment_plan.py, build_deployment_plan.py, machine plan playbook | Единая модель actions; production BLOCKED до A8 integration |
| A7.4 | Typed credential scope и fixed commands | execution_secret_lease.py, execution_protocol.py, execution_controller.py, existing validators | Без произвольной команды и без secret output |
| A7.5 | Runtime closure и focused QA | build_execution_runtime_bundle.py, affected tests | Проверенная closure, old infra compatibility, негативные contract cases |
| A7.6 | DIFF review и документация | milestone journal/review, CURRENT_STATE, contract index | Точные verdicts и оставшиеся A8/A9 gates |

Изменять только реально затронутые модули. Private manifest validation найти
по существующим consumers; не создавать отдельный новый validator по названию.
UI/Go файлы не изменяются. Обновить канонический execution contract/schema index
при принятии новых operation types; ADR только для material boundary decision.

## 9. Проверки и приёмка

Все Python/Ansible проверки — на RED OS из текущей ветки, после чтения
[QA procedure](../../../../agent-procedures/qa.md). Никаких benchmark.

| Проверка | Ожидаемый результат |
| --- | --- |
| Infra-only проект и пустые libraries | Старые snapshot/plan/protocol behavior и fingerprints сохраняются, кроме явно документированной schema evolution |
| Library snapshot через native inventory/defaults/group_vars/host_vars | Multi-host override и derived IDs совпадают с standalone A1–A6 |
| Library + shared/account secrets | Публично только refs/bindings/requirements; нигде credential values |
| No accounts/no service ref/no endpoint | Не появляется ненужный hook или credential requirement |
| Kafka multiple listeners, missing provider/capability | Точный field finding, без target контакта |
| Unknown version, package/lock mismatch | BLOCKED без manifest и без скрытой миграции |
| Изменение image, placement, binding, backend | Меняет semantic fingerprint; порядок YAML и timestamp — нет |
| Target-free planning при доступном/недоступном registry | Repository probes не выполняются; requirements и semantic fingerprint одинаковы |
| Execution-time registry unavailable + compatible offline / no source | Verified offline RuntimeProjection / отказ до соответствующей image/container mutation |
| Tampered operation/project/release/lease | Отказ до target mutations; safe error code |
| Application-aware BuildDeploymentPlan до A8 | Структурированный BLOCKED, не исключение и не EXECUTABLE обход |
| Старый production protocol lifecycle | Реальный infra-only Build/Start/events/cancel работает без Go |
| Fixed application commands | Только существующие playbooks/vars/inventory; нет нового вложенного CLI |
| Build bundle offline closure | Все imports/templates/schema присутствуют; secrets отсутствуют |

Native execution самих application операций в production mixed run будет доказана
при A8/A9, когда общий барьер реализован. A7 не объявляет это PASS по unit tests.
Для A7 достаточно соответствия descriptors/commands standalone A1–A6, негативного
production gate и native infra protocol regression. React/Wails acceptance
потребуется последующему Go/UI этапу; A7 её не заявляет.

Независимый FULL PLAN review обязателен перед представлением архитектурного плана.
Реализация изменяет versioned/execution/secret boundary: HIGH-RISK, один FULL DIFF
review и не более одной owner-approved TARGETED_RECHECK по блокерам.
См. [review procedure](../../../../agent-procedures/review.md).

## 10. Критерий завершения A7

Snapshot/Validate библиотек структурированы, детерминированы и target-free;
требования образов/секретов совпадают со standalone; application actions и fixed
controller descriptors используют existing pipeline; production gate до A8
не допускает небезопасный Start; infra-only путь не изменил поведение.
Closure/schema/focused QA и review отражены в журнале. Общий запуск,
all-infrastructure barrier и полная mixed acceptance остаются A8/A9.

## 11. Решение владельца по PLAN review

2026-10-12: владелец принял минимальную коррекцию A7-P01. Разделы 4 и 9
исправлены: конкретный источник выбирается при execution, без repository probes
и результатов выбора в target-free plan/fingerprint. Исходный FULL PLAN BLOCK
сохранён в отчёте как вердикт по прежнему snapshot. Owner-approved TARGETED_RECHECK
завершилась APPROVE, A7-P01 RESOLVED. Затем владелец принял план и разрешил
реализацию A7 в `codex/application-libraries`. Коммит требует отдельного запроса.
