# Оптимизация установки Kafka и проверок сервисов

Владелец разрешил реализацию 2026-10-26. Ветка
`codex/service-runtime-optimization`, база `4236abaf`.

## Область

1. Kafka Apply: повторно использовать нормализованные данные между Kafka и
   Schema Registry внутри одного playbook; сократить повторные CLI-чтения ACL;
   исключить повторные проверки неизменных данных в пределах операции.
2. Verify инфраструктуры: оставить read-only проверку работоспособности через
   штатный протокол с проверкой TLS и аутентификацией, где они настроены.
   Для кластеров сохранить готовность участников и кворума. Сверка конфигурации,
   файлов, пользователей и разрешений относится к Apply, не к Verify.
3. Не вводить кеш между запусками, новые desired-state настройки, обходы
   источников артефактов, изменения Go/UI или ослабление TLS.
4. Не менять активный bundle и текущий полный run. Новая установка не требуется
   для разработки; реальные измерения производительности отдельно от тестов.
5. Уточнение владельца: HAProxy сохраняет `haproxy -c` — read-only проверку
   установленного бинарного файла и активной конфигурации перед health-проверками.
   BIND также сохраняет штатный Verify, включая 
amed-checkconf` и DNS-запросы.

## Проверки

- Native Ansible на RED OS: корректный ответ, недоступный сервис, неверные
  credentials, недоверенный TLS, неготовый кластер; changed=0 у Verify.
- Kafka: сохранение ACL/SCRAM, идемпотентное повторение, отсутствие лишнего
  запуска main при переходе к Schema Registry; standalone вход остаётся рабочим.
- Тесты выполняются из текущего worktree через qa-sync; до полного run
  требуется успех проверок затронутых ролей. Реальный React/Wails и ускорение
  холодной установки не подменяются unit-тестами.

## Базовый замер

Kafka Apply 37:20: роль 26:51, resolver библиотек 6:00, доставка 1:53.
2021 TASK_STARTED; интервалы последовательных задач, без суммирования хостов.
Это восстановительный запуск, а не чистый cold-install benchmark.
Цель сравнения на одинаковых ВМ — снижение не менее 30%, пока не подтверждена.

## Выполнение

Реализация внесена; [результаты QA и ограничения](service-runtime-optimization-journal.md),
[FULL DIFF и согласованный D01 recheck](service-runtime-optimization-review.md).
Проверка `_schemas` сохранена на каждом участнике. Общая подготовка endpoints
использует уже вычисленные Ansible rows в том же процессе, с обычным fallback.
Новый bundle, реальная UI-приёмка и сравнительное измерение времени ещё впереди.

## Этап5: переиспользование разрешения проекта (реализация согласована владельцем)

Уточнение реализации 2026-10-27: reuse остаётся приватным механизмом Core на
Execution Node. Публичные Go DTO и версии протокола не расширяются opaque
reference: точную identity Core проверяет по фактической closure каждого
независимого запроса и неизменяемому runtime. Один заменяемый файл на project ID
не создаёт историю ревизий. Go сохраняет существующие проверки и пересборку
авторитетного плана перед Start. По указанию владельца текущий run не
останавливается, ревью не вызывается; phase5 в активный bundle не включается.

Задача владельца: не выполнять resolver и snapshot несколько раз для одной
ревизии при Project Verify, формировании плана и Start. Реализация и новый
установочный запуск этим предложением не разрешены. Текущий run не изменять.

### Границы и минимальный порядок реализации

1. Сначала убрать дублирование внутри одного BuildDeploymentPlan: результат
resolver/snapshot из image DESCRIBE передавать в final planner вместе с фактически
подготовленными image metadata. Это отдельная проверяемая часть без межзапросного
кеша. Не переносить Ansible precedence или service semantics в Go.
2. Затем использовать тот же механизм между Verify, descriptors, image inputs,
Plan и Start. Не добавлять глобальный cache framework, БД, индекс или демон.
Один текущий reusable result на project/revision/runtime/context выбранного
Execution Node; уже используемые plan/run staging остаются владельцами файлов.

### Результат Core и его идентичность

Core формирует версионированный внутренний resolved result из существующих
outputs project_snapshot action: public redacted snapshot, execution_configuration,
execution_connections, желаемые PKI requests/materialization inputs, желаемые
application image requirements. Не сериализовать runtime secrets, tokens,
credential leases или protected outputs. Применять существующие границы
secret/reference, а не эвристическое сканирование значений.

Отделить чистое разрешение desired state от enrichment: результат подготовки
образов, PKI reissue/verify coverage и наблюдения runtime не входят в reusable
base. Итоговый публичный snapshot/fingerprint и manifest формируются после
актуального enrichment, с сохранением существующих значений/семантики.

Идентичность включает фактический source closure/archive digest, project identity
и revision, runtime bundle/catalog/schema, Core format version, Execution Node и
существенный resolver context. Core проверяет соответствие, Go хранит только
opaque reference и не вычисляет инфраструктурный cache key. Нельзя считать одну
revision достаточной для неучтённых внешних Ansible inputs. При отсутствии
доказанной детерминированной closure выполнить обычный fresh resolve; не вводить
новый анализатор произвольных lookup/env. Подтвердить эти ограничения тестами
реально поддерживаемых контрактом выражений/inventory.

### Хранение и протокол

Использовать existing private root-owned staging, отдельный внутренний artifact
с format/identity/digest и opaque reference наружу. Сам private result не отправлять
в React/Go. Контроллерная запись атомарная существующими файловыми средствами,
read-only после публикации. Не менять владельца под target script user.

Первым этапом сохранить текущую передачу проекта и Go ProjectRevision checks.
Core сопоставляет reusable result с фактически переданной closure. Если result
содержит абсолютные пути, удерживать исходный captured root и использовать именно
его; не интерпретировать сохранённые пути относительно другого staging root.

Расширить существующие BuildProjectSnapshot/BuildRuntimeSecretDescriptors/
PrepareApplicationImages/BuildDeploymentPlan negotiated protocol, без параллельных
DTO desired state. Optional opaque ref; standalone без ref работает как сейчас.
При отсутствии/устаревании ref — fresh resolve; повреждение опубликованного
artifact — явная структурированная ошибка, не доверять или скрывать повреждение.

Go удерживает reference в памяти для текущего binding. Смена revision/input
closure, runtime/catalog/schema, node/context или rebind делает его неприменимым.
Ротация runtime секретов не инвалидирует чистый desired base. Cleanup использовать
из существующего staging lifecycle, не удалять файлы, на которые ссылаются
активные планы/запуски. Не добавлять бесконечную историю версий. При невозможности
безопасного удержания/очистки оставить только reuse внутри одного запроса до
отдельного согласования межзапросного lifecycle.

### Потоки

Verify: локальная saved revision и node/runtime identity checks → fresh/reused
Core result → redacted projection и verification evidence. Service preview
использует готовый общий результат при его наличии. При cache miss сохраняет
существующий облегчённый configuration_only preview без полного resolver,
обязательного Verify или Plan.

Plan: validated base → image DESCRIBE из base → штатный image PREPARE → final
plan из base + свежих image evidence и текущих planner inputs. Наблюдения target,
source-selection, PKI reissue/Verify state не переиспользовать по одной revision.

Start сохраняет authoritative plan rebuild и fingerprint comparison. Перед ним
снова проверять текущие source/revision/runtime, TTL/approval, secrets и SSH trust;
descriptors получать из того же base. Повторять изменяемые image/PKI/verify/source
проверки как требует существующий контракт. Изменившееся намерение требует
свежего плана и одобрения, неизменившееся не запускает resolver повторно.

Не менять Apply/Verify сервисов и библиотек и не переносить UI/session/process
lifecycle в Python. Не смешивать этот cache с удалённым кешем файлов скриптов.

### Измерения и QA

Секретобезопасные интервалы в существующих QA/protocol metadata: source hash,
archive/transfer, resolver/snapshot, descriptors, image DESCRIBE/PREPARE, final
planner, credential/trust/dispatch. Не выводить значения/argv/env/secret contents.

Проверить реальное число resolver calls: Verify→descriptors→Plan→Start равно1
при точной неизменной identity в допустимом для reuse контексте; direct
Plan→Start тоже1 для такого контекста. Перед вторым шагом явно перечислить
поддерживаемые контексты и eligibility; неподтверждённые внешние inputs
принудительно требуют fresh resolve. Сохранить golden public
snapshot/plan/fingerprint/manifest. Изменения defaults/group_vars/host_vars,
package closure/directories, runtime/node/context должны инвалидировать result.
Изменения selection и mutable PKI/verify/image/source evidence не должны скрываться
reuse; source base может сохраниться, итоговый plan пересчитывается корректно.
Проверить внешние inputs/fallback, отсутствие/повреждение result, одновременные
запросы/разные revision, source paths и lifecycle активного run; никакие runtime
секреты не попадают в artifact. Standalone Core без Go, RED OS native и реальный
React/Wails проходят отдельно. HIGH-RISK FULL DIFF после разрешённой реализации.

Целевые ожидания, а не PASS: после первого resolve убрать около минуты на каждый
повтор; warm Plan30–60с, warm Start45–90с, экономия всей цепочки порядка3–5мин
требует подтверждения равным benchmark. Исходные интервалы и ограничения замеров
в текущем service-runtime-optimization-journal.md. Один FULL PLAN review этого
раздела, замечания BLOCK вернуть владельцу без автоматического redesign/re-review.


## Последовательная подготовка библиотек и скриптов

Owner request2026-10-27: commit current optimizations, then reduce orchestration
and generic runner overhead observed in SZI (48:43,1158 task starts). Existing
HAProxy optimization remains the committed baseline. No new concurrency,
script source cache, provider-specific runner rules or public contract.

Use existing Ansible mechanisms: select current library/instance placements once;
only include script handlers for nonempty scope/phase; keep transient script paths
as role variables rather than host facts; use one ordinary copy loop for script,
selected secret files and optional invocation JSON. Keep permission modes, fresh
source copy, stale-input removal, always cleanup, argv, timeouts, safe diagnostics
and script-reported changed semantics. Provider script target context remains a
lazy task variable; Execution Node callbacks must not contact target hosts.

QA: native phase dispatch/order and empty placements; literal argv/batch input;
multiple selected secrets/modes, failure cleanup, repeat changed=0; existing
cross-account neighbor substitution repair, hook batching, skipped-provider
callback and terminal-script regressions. One owner-requested FULL DIFF review.
Existing runtime/bundle is not replaced during current run. PG/Redis/Vault provider
logic, readiness policy and endpoint barriers remain outside this change.

## Owner policy: omit global library Verify from new installation plans

Explicit owner request removes the entire repeated global library Verify pass:
resolver/snapshot/provider projections, container/config checks and endpoint
HAProxy/DNS/HTTPS checks. Keep readiness at startup, per-library container health
and endpoint publication/probes inside Apply. Emit only APPLICATION_LIBRARIES_APPLY
and optional post_install depending on applications:apply. The standalone Verify
playbook and saved Apply/Verify manifests remain supported; existing in-flight
plans/bundles are immutable. Existing schema versions already allow Apply-only
operations and do not require new fields, versions, flags or Go/UI domain logic.
Use one shared admission suffix check for Apply-only and exact legacy Apply/Verify;
keep infrastructure coverage, scope matching and terminal failure/cancel gates.

Affected native/unit/schema/controller tests125 OK/2 explicit native gates;
the two real action/controller gates independently enabled:2PASS6.089s. Controller
fixture fails if the global Verify playbook is invoked. UI32PASS shows only Core-
declared actions while retaining old-plan display. New tests cover FULL_PROJECT,
libraries-only with/without SkipInfraVerify, legacy manifests with/without terminal,
invalid order/duplicates/scope and terminal dependency. Updated-bundle real Wails
acceptance/benchmark pending. Independent FULL DIFF required for changed admission;
9file source manifest c673a9d7497d298fd1dc2ca4e2c1bca507c762b61b22c7b9ac55556b41cb5984.
