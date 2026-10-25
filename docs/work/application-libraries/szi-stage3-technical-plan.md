# SZI-STAGE3 — пропуск установки библиотек и интеграция СДКУ/CSPA

Дата: 2026-10-24. Статус: FULL PLAN APPROVE_WITH_CHANGES/blocking0; неблокирующие уточнения внесены;
реализация не начата. Отчёт: [независимое ревью](reviews/szi-stage3-plan-review.md).
База: master 24e24f9594b38b484682d27e433bc25b572935b5.
Владелец запросил подробный план и независимое ревью. Этот документ не разрешает
Apply, остановку контейнеров, изменение БД или публикацию нового runtime.

## 1. Цель и границы

Добавить выбор пропуска установки отдельных экземпляров библиотек в текущем
запуске. Пропущенная библиотека остаётся в portable project и может предоставлять
подключения устанавливаемым приложениям. Проверить этот механизм на установленной
СЗИ и потребителях СДКУ/CSPA через обычный React/Wails/Core план.

Основной сценарий: проект содержит szi, sdku и cspa; оператор пропускает szi.
Core не выполняет её установку/Verify, но использует sso и существующие endpoints,
создаёт/обновляет интеграции выбранных потребителей и затем устанавливает их.
Никаких веток по именам szi, keycloak, sdku или cspa в Core/Go/UI.

Входит:
- выбор по library instance ID, сохранение полного проекта и порядка библиотек;
- точная выборка ресурсов, образов, секретов, lifecycle tasks и Verify;
- повторное использование прикладного провайдера без его Apply/readiness/Verify;
- пакетные группы/клиенты/accounts → Vault/Agent для устанавливаемых потребителей;
- обновление nginx-маршрутов как интеграционной операции пакета;
- файловые настройки sso для СДКУ/CSPA и сквозная проверка двух потребителей;
- сохранение generated-password и инфраструктурного batching из текущего master.

Не входит: удаление/отзыв доступа, bootstrap уже установленной СЗИ, восстановление
её БД, новая система discovery/observed installation state, новый DAG scheduler,
health-gates для пропущенных библиотек, изменения содержания Verify, постоянный
признак skip в проекте, массовое включение SSO во всех пакетах, UI редактор групп.

## 2. Подтверждённая исходная реализация

1. application_plan.application_execution_model требует полный точный порядок
   библиотек и собирает образы/секреты всех resolved libraries.
2. application_connection_order_findings требует провайдера раньше потребителя.
3. application-libraries-preflight.yml проверяет и рендерит все runtime jobs.
4. Общий provider-stage готовит инфраструктурные accounts/Vault до контейнеров;
   прикладные batches выполняются в ordered-instance после readiness провайдера.
5. application-provider-script.yml получает account/instancePath из полного Docker
   preflight целевого провайдера, даже для run_on=execution_node.
6. integration dependencies и shared secret dependencies уже отделены от scripts
   runner; раннер передаёт только declared argv/private inputs.
7. application-libraries-verify.yml и endpoint-stage сейчас охватывают все jobs.
8. nginx prepare-routes — before_start; входной routes.requested.json получается
   через config_files. Простое исключение СЗИ оставит старые маршруты.
9. routes-upsert.lua уже делает атомарный additive upsert; script.lua читает
   routes.effective.json при обработке запроса. Новый HTTP management API не нужен.
10. SDKU имеет sso, library group hooks и alarm-view-service с sso.enabled=false.
    Пакет alarm-view-service общий для SDKU/CSPA; у библиотеки CSPA пока нет sso
    binding и библиотечных group hooks.

Основные файлы:
- contracts/execution-runtime/v1alpha6, plan/v1alpha7,
  execution-manifest/v1alpha5, execution-capabilities/v1alpha10;
- tools/execution_protocol.py, execution_controller.py; module_utils/application_
  plan, integrations, connections, scripts, runtime, providers, vault, images;
- playbooks/application-libraries-{resolve-runtime,preflight,provider-stage,
  apply,ordered-library,ordered-instance,verify,endpoint-stage}.yml;
- playbooks/tasks/application-provider-{batch,script}.yml, application-deliver-ready.yml;
- internal/executionnode/{execution_service,infrastructure_verification,
  application_image_preparation,runtime_protocol}.go;
- internal/desktop/installation_plan.go, frontend/src/{App,InstallationPage}.tsx;
- examples/szi/application-packages/nginx; examples/sdku/library-packages/{sdku,cspa}.

## 3. Семантика выбора

Вход текущего запуска:

```json
{
  "executionMode": "APPLICATION_LIBRARIES_ONLY",
  "skipInfrastructureVerify": true,
  "applicationLibraryOrder": ["szi", "sdku", "cspa"],
  "skipApplicationLibraries": ["szi"]
}
```

Имена здесь — пример instance IDs, не package names. При нескольких экземплярах
одной библиотеки выбор независим. Флаг не записывается в inventory/group_vars,
SQLite desired state, настройки библиотеки или пакет.

Обозначения:
- R — все разрешённые экземпляры библиотек проекта;
- S — skipApplicationLibraries, уникальное подмножество R;
- A = R minus S — библиотеки, которые устанавливаются в этом запуске;
- C — приложения-потребители из A с эффективными enabled connections;
- P — точные прикладные провайдеры, требуемые C, включая провайдеров из S.

applicationLibraryOrder остаётся полным порядком R. Core фильтрует выполнение,
не удаляя пропущенные элементы и не переставляя потребителей. Порядок из
config/application.yml и start_priority сохраняется. Для provider_prepare
requirements учитывается замыкание явно объявленных подключений, не поиск по
строкам шаблонов. Без нового обхода графа/планировщика: использовать resolved
connections и существующие dependency/batch projections.

Собственные потребители пропущенной СЗИ, например grant-access, НЕ становятся C:
их клиенты/accounts/секреты не переподготавливаются только из-за наличия в R.
Подключение к провайдеру не включает повторную установку всего provider library.

Пропущенная библиотека:
- не получает своих resource/account writes в инфраструктурных providers;
- не получает restore_on_create, PKI issuance/delivery, Vault document/AppRole
  reconciliation для собственных приложений, materialize/config/image jobs;
- не выполняет before_start/after_ready, compose up/recreate, readiness/Verify;
- не публикует и не проверяет заново свои существующие endpoints;
- может получить только явно объявленные integration callbacks для C.

Обычная target-free валидация полного проекта/пакетных деклараций сохраняется.
Это не обещание отсутствия чтения исходных файлов пропущенного пакета: проект
по-прежнему содержит точные package references и должен структурно разрешаться.
Не требуется наличие его образов в выбранном image preparation closure.

S=[] полностью сохраняет нынешнее поведение. Для APPLICATION_LIBRARIES_ONLY
A=[] даёт явную ошибку пустой выборки; интеграции без устанавливаемого потребителя
сами по себе не запускаются. В FULL_PROJECT пустое A допустимо при наличии
инфраструктурных действий. Для INFRASTRUCTURE_VERIFY_ONLY непустой S недопустим;
поведение пропуска инфраструктурной Verify не меняется.

Если приложение выключило sso, наличие СЗИ не включает его автоматически.
Сохраняется явный binding на providedConnectionRef; ошибочная/отсутствующая ссылка
при включённом подключении — обычная ошибка разрешения, без silent fallback.

## 4. Версионированные контракты

Новые версии, не изменение смысла старых версий:
- execution-runtime/v1alpha7: BuildDeploymentPlan и PrepareApplicationImages;
- plan/v1alpha8: normalized skip list и Core-derived installation/integration scope;
- execution-manifest/v1alpha6: тот же execution scope, fingerprint и dispatch;
- execution-capabilities/v1alpha11: поддержка library selection/integration hooks.

Точные номера сверить с master перед реализацией. Старые запросы означают S=[].
Непустой S нельзя молча отбросить при работе со старым bundle: явное unsupported.
Схемы новых версий описывают также applicationLibraryOrder, который сейчас
обрабатывается execution_protocol как ограниченное расширение входа.

Один canonical selection definition со ссылками из связанных схем. Вход содержит
только skip list; A/C/P выводит Core, Go/UI их не рассчитывают. Existing operation
applicationLibraries означает A; отдельная derived provider scope фиксирует P,
чтобы credentials законно адресовали провайдера, которого нет в install list.
Не расширять секретный scope до всех R для обхода текущей subset-проверки.

Валидация: reuse существующих правил library ID, уникальность, принадлежность R,
разрешённость executionMode; никаких новых лимитов файлов/ownership-проверок.
Нормализованный S участвует в plan ID/fingerprint, manifest attestation,
semantic fingerprint и image preparation inputsDigest/lease. Перестановка S
эквивалентна; изменение множества инвалидирует approval и подготовку образов.
Start пересобирает ровно сохранённую выборку из PlanRecord. Pending image/secret
responses с другой revision/node/runtime/selection не могут подменить текущие.

## 5. Изменения Core и Ansible

### 5.1. Одна производная execution scope

Добавить небольшой pure helper рядом с application_plan/integrations. Он принимает
full snapshot, полный порядок и S и возвращает A/C/P и фильтры существующих jobs.
Все project resources/endpoints/connections по-прежнему разрешаются обычными
Ansible precedence и существующими Core резолверами. Не создавать второй snapshot
как desired state и не дублировать merge/defaults в Go.

### 5.2. План, образы и требования секретов

- image requirements, registry credentials, pull/load checks и prepared image
  descriptors только для A; установить filter ДО image acquisition/preflight;
- инфраструктурные resource/account batches только от приложений A;
- lifecycle secrets/PKI inputs/Vault jobs собственных приложений S исключены;
- для P оставить только credentials реально вызываемых connection/account/
  integration callbacks: например szi_admin_secret, даже если szi входит в S;
- secret_bindings и generated passwords потребителей проходят прежнюю процедуру;
- исключённые registry/bootstrap/GA/audit secrets СЗИ не требуются;
- серверный CA, необходимый curl на Execution Node, берётся из существующей
  разрешённой PKI/runtime trust схемы; не выпускать сертификаты пропущенной СЗИ;
- host closure включает нужные target placements hooks из P, а не только C;
  для execution_node callback не требовать SSH/Docker checks неиспользуемых hosts.

### 5.3. Preflight и минимальный контекст provider script

Полный Docker preflight, archive checks, render/inspection/permissions существующих
runtime paths выполняются только для A. Для P подготовить script invocation из
package declaration + resolved provider placement + существующего runtime path
projection. Не вызывать lifecycle preflight ради получения account/workdir.

Для run_on=execution_node account и workdir уже определены контрактом раннера;
поля Docker не нужны. Target hook получает только его объявленный target account/
workdir и argv. Никакой container context не вводится в package_script runner.
Не добавлять новые target readiness probes/owner labels/identifier rechecks.

### 5.4. Координация по существующему полному порядку

Для provider library, входящей A: обычный Apply; после готовности точного provider
instance — его endpoint, отобранные batches C, accounts, dependent Vault/Agent.
Для provider library из S: не выполнять его Apply/Verify; на его месте в полном
порядке выполнить необходимые batches C, используя уже существующий endpoint.
Один и тот же application-provider-batch.yml, а не вторая Keycloak-specific ветка.

Порядок внутри batches прежний: groups(order -100) → clients(order0) → role mappings
(order100) → один accounts batch провайдера → Vault/Agent готовых потребителей.
Завершение batch записывается только после успеха; ошибка останавливает запуск
потребителей. Никаких persisted ready markers или доказательства «установлено».
Пропуск — явное решение оператора использовать уже работающий provider; фактический
HTTP/TLS/auth failure выходит из обычного скрипта с безопасной диагностикой.

Повторное использование P не запускает unrelated Kafka/Redis/PostgreSQL batches.
Существующая защита single concurrent Apply остаётся; параллельные изменения
realm/маршрутов отдельными runs не входят в acceptance.

### 5.5. Endpoint scope и Verify

Публиковать/проверять endpoints только A. Существующие provider DNS/HAProxy records
из P сохранить как retained entries штатного reconciliation, не удалить из-за
фильтра A и не пересобрать источники S. Источник новых consumer endpoints — обычный
Core endpoint placement, без фиксации портов или прямых IP вместо HAProxy.

Отдельная verification action и внутрибиблиотечный Verify фильтруются по A;
endpoint-stage получает ту же выборку. Содержание Verify не меняется: никаких
проверок групп/accounts/ролей/скриптов там не появляется. Это Apply/readback и QA.

## 6. Пакетные интеграционные hooks и nginx

Предлагаемое небольшое расширение существующего scripts contract:
optional phase `integration_apply` для library/application scripts. Это тот же
package_script runner, существующие once/each_target и target/execution_node.
Новый executor, HTTP gateway API, account provider или произвольный command bridge
не вводятся. Старые пакеты без этой фазы работают как раньше.

Для этих расширений вводится manifest API
`platform.installer/application-package/v1alpha2` и
`contracts/application-libraries/v1alpha2/package.schema.json`. Schema v1alpha1
не расширяет свои enum задним числом. Core load_package выбирает schema по
apiVersion; поддерживает прежнюю v1alpha1 и новую v1alpha2, сохраняя прежние
application/library/settings/deployments definitions. Не копировать эти definitions
ради новой версии manifest: неизменные shared definitions использовать через $ref.
Новый nginx manifest использует v1alpha2; потребительские пакеты без новых script
возможностей могут остаться v1alpha1. Capabilities объявляют supported package API
versions и script features. Import/resolve нового manifest с неподдерживаемым
runtime отклоняется до target contacts, независимо от наличия skip-флага.

Для integration_apply допустимы target + once/each_target и execution_node + once;
execution_node + each_target отклоняется schema/contract validation. Execution Node
не подменяется target host. Старый package/new runtime сохраняет прежнюю семантику;
новый package/старый validator даёт явный unsupported import/resolve результат.

Phase запускается в рамках позиции provider library в полном порядке, если её
экспорт реально используется C. После её обычного Apply (если A) либо без него
(если S), но обязательно до перехода к внешним потребителям. Для application hook
выполнение адресуется placements именно объявившего приложения, не placements
Keycloak по совпадению host IDs. Каждый required target должен завершиться успешно.

Текущая readiness/accounts/Vault координация внутренних приложений СЗИ остаётся:
не блокировать старт GA/nginx ожиданием собственного позднего route hook. Существующие
batches обслуживают accounts как раньше; ordered-library barrier не пускает внешних
потребителей, пока integration_apply hooks provider library не завершены. При S
никакие внутренние consumer batches СЗИ не выполняются.

Добавить один typed argv source `integration_consumers`: безопасная проекция
реально выбранных потребителей экспортов данной provider library. Содержит
libraryId/applicationId, resolved public endpoint, connection references и
разрешённые несекретные integration parameters. Не содержит credentials, token
или private file contents; не публикуется в UI/events как raw payload. На уровне
Core ключи IDENTITY_ROUTE/realm/nginx не разбираются: пакет выбирает свои параметры
из обычного resolved consumer context. Existing output/timeout/argv bounds остаются.

Пакет nginx:
1. Сохранить нынешний before_start для первого запуска и прежних пакетов,
   но и routes.requested.json.j2, и integration_apply должны получать одну
   отфильтрованную проекцию: выбранные внешние потребители C плюс собственные
   маршруты устанавливаемой provider library. Не обходить все R в старом шаблоне.
   Невыбранные внешние потребители только retained, даже если их desired endpoint
   изменён. Обе точки построения requested routes проверяются одной матрицей.
2. Добавить integration_apply hook с execution=each_target, используя тот же
   prepare-routes.sh с jq на target; Docker и вспомогательный контейнер не нужны.
3. Передавать текущую nonsecret projection через argv, не материализовать заново
   весь config_files пропущенной СЗИ. Скрипт создаёт только временный вход для
   upsert и изменяет routes.effective.json; temporary input удаляется.
4. Использовать существующий instance path и установленный на target jq.
   Не вызывать Docker, не запускать контейнеры, не менять image/Compose основного
   nginx. JSON объединяется jq и атомарно заменяется при изменении содержимого.
   Проверка nginx остаётся в штатной проверке сервиса, вне integration hook.
5. Merge только новых/обновлённых маршрутов C, сохранить остальные, включая
   собственные маршруты GA/front. No-delete при выключении/пропуске/удалении binding.
6. Main Lua читает routes file на запрос; не нужен reload основного nginx.
7. Отказ одного target останавливает run до старта C; retry — additive/idempotent.
   Межхостовая атомарность не обещается, уже записанные маршруты не откатываются.

Обоснование phase: before_start нарушает skip; существующий provider_prepare
адресуется connection target, а не произвольным placements nginx и завязан на
batch credentials. Привязка к совпадению hosts недопустима. Новая фаза расширяет
существующий механизм на одну декларативную точку координации и избегает HTTP API,
отдельного SSH транспорта или повторного Apply. На FULL PLAN review отдельно
оценить более простой reuse существующих hooks с теми же гарантиями.

## 7. Go и UI

Go передаёт selection как opaque Core input: InstallationPlanRequest/View,
ExecutionService/PlanRecord, transport, image preparation и Start reattestation.
Не определяет A/P, не проверяет наличие СЗИ по имени, не рассчитывает dependencies.
Обновить bindings и deep-copy мест хранения selection, включая cached run plan.

На вкладке «План», в существующем блоке библиотек: колонка «Пропустить установку».
По умолчанию флаги сняты; отображаются реальные instance IDs и имена библиотек.
При изменении остаётся виден старый план с явной пометкой, что выборка изменена;
его нельзя напрямую одобрить/запустить. Как в B4: Approve при изменённом выборе
сначала строит authoritative plan, показывает его и требует существующего
подтверждения returned plan. На активном run выбор locked. Смена проекта сбрасывает
S; навигация внутри текущего проекта сохраняет local selection. Не сохранять S
в portable project или вводить отдельную форму секретов на странице плана.

UI показывает Core-normalized skipped libraries и интеграционные действия явно:
«СЗИ: установка и Verify пропущены; используется как провайдер интеграции».
Никаких ложных зелёных «установлено/проверено» для S. Требования секретов только
из current Core descriptors, со стандартным вводом в настройках ресурсов/библиотек.

Дизайн discrepancy: ui-design-01 B4 прямо говорит «Libraries always run Apply/Verify
and have no checkbox in this stage». Stage3 — owner-requested extension; до кода
обновить эту секцию и relevant Installation mockup, сохранив B4 ownership/approval
model. На acceptance сверить реальный React/Wails, визуальный результат отдельно.

## 8. СДКУ/CSPA: файловые настройки

Первая реальная матрица — alarm-view-service в SDKU и CSPA, то есть общий пакет
с двумя разными library instance IDs/applicationIds. Остальные приложения
проверяются рендером/сохранением их прежних defaults, без массового запуска.

- Сохранить optional sso.enabled в defaults приложения; включить только у двух
  QA instances обычными group_vars overrides.
- SDKU: использовать имеющиеся sso binding, group hooks и role file, проверить
  clientId references от resolved applicationId.
- CSPA: добавить аналогичные sso declaration, scripts и собственный файл ролей/
  списка групп. Никакой копии integration.sh/prepare-client.sh у потребителей:
  create/update clients остаётся у provider package.
- При необходимости вынести одинаковый короткий consumer wrapper в тот же
  существующий шаблон/пакетный механизм; не вводить новую сущность ради dedup.
- Проверить реальные поддерживаемые ENV/URL приложения по его контракту/образу
  перед настройкой SSO; не изобретать переменные на основании имени библиотеки.
- Сохранить applicationId для clientId, nginx subpath и route key, description
  равен endpoint; redirect https://nginx…/<applicationId>/*.
- Public consumers не получают ненужный client_secret; существующие accounts и
  secret_bindings используются только если это требуется конкретному приложению.
- Никакого UI для IDENTITY_GROUPS или включения sso: это текущая файловая настройка.
- Обновить README, roles docs и SDKU import-catalog через Core digests после правок.

## 9. Пункты реализации

| ID | Изменение | Основные файлы | Готовность |
|---|---|---|---|
| SZI3-01 | canonical request/plan/manifest/capabilities, package manifest v1alpha2 и compatibility | contracts; execution_protocol; runtime_protocol | schema positive/negative, старый runtime explicit unsupported |
| SZI3-02 | один execution scope; image/secret/resource/PKI filtering | application_plan/images/providers/vault/runtime | чужие jobs/секреты не выбираются, fingerprint binding |
| SZI3-03 | reuse skipped providers, minimal script context, batching | application_integrations/scripts; preflight/provider/ordered playbooks | provider без lifecycle; выбранные hooks/accounts exactly once |
| SZI3-04 | integration_apply + typed consumer argv projection | package/settings schemas; scripts; ordered-library | once/each_target, target/context/secret exclusion, без product names |
| SZI3-05 | nginx additive integration route upsert | examples/szi/nginx scripts/defaults/manifest | оба target, no reload/recreate, unchanged repeat/no-delete |
| SZI3-06 | endpoint retention и Verify scope | endpoints; endpoint-stage; verify playbook | sources S не тронуты, active C проверены, Verify semantics прежние |
| SZI3-07 | Go pass-through и UI selection/approval | desktop/executionnode/frontend; design/mockup | реальные handlers, stale plan не запускается |
| SZI3-08 | SDKU/CSPA manifests/defaults/group role files | examples/sdku и import-catalog | два независимых клиента/группы, прежние providers работают |
| SZI3-09 | native/focused/offline/regression | Core/service/frontend/Go tests | все предварительные сценарии PASS до нового run |
| SZI3-10 | bundle и настоящая стендовая приёмка | QA/journal; стандартный publisher | fresh plan/approval/start, terminal, repeat, сохранность СЗИ |

Реализация в отдельном worktree после решения владельца по результату review.
Перед кодом перечитать актуальные scoped AGENTS/contracts. Архитектурные изменения
отразить в существующих architecture-decisions/roadmap/contracts; не создавать
новый desired-state документ. Текущий запрос разрешает только FULL PLAN review: DIFF review сейчас не
запускается. После разрешения реализации изменения versioned contracts, execution
scope и credential custody классифицируются HIGH-RISK; обязательный независимый
FULL DIFF gate выполняется по review procedure до соответствующего acceptance/
promotion с отдельной точной implementation identity. Неблокирующие уточнения
этого плана не требуют нового PLAN review.

## 10. QA test plan

### Test Scope

Scope = selection, integration scheduling, consumer delivery, public endpoints,
SDKU/CSPA clients/groups/roles и сохранность skipped SZI. Полная инфраструктурная
переустановка, business message acceptance всех приложений и ротация admin не входят.

### Required Scenarios

| Case | Сценарий | Доказательство |
|---|---|---|
| P01 | S=[] на старом/новом запросе | прежние order/actions/secret/image sets |
| P02 | szi skipped; sdku+cspa install | resources/PKI/images/lifecycle/Verify СЗИ0, callbacks C выполнены |
| P03 | только sdku, cspa skipped | ни групп/клиентов/accounts CSPA, ни её установки; прежние объекты retained |
| P04 | два экземпляра одной library | skip по instance ID, distinct applicationIds и clients |
| P05 | skipped provider на других hosts, run_on=execution_node | нет Docker preflight/CLI у API hook, EN curl/jq с TLS |
| P06 | integration_apply target each_target/once | точные nginx placements, не placements Keycloak; dedup |
| P07 | groups→clients→roles→accounts→Vault/Agent | фактический Ansible порядок и один batch на provider |
| P08 | repeat | callbacks changed=false, objects/credentials metadata/Vault versions стабильны |
| P09 | normal SZI install + external clients | нет cycle между GA/nginx/account batches и late route hook |
| P10 | mixed generated/manual passwords | published reuse, no regeneration, Kafka/PG/Redis batch counts прежние |
| P11 | маршруты и SSO | оба nginx routes, TLS request, redirect/login/role behaviour по app contract |
| P12 | selection меняется после image prepare/approve | stale lease/plan rejected до target mutations |
| P13 | runtime inputs | нужны provider admin и secrets C, не требуются bootstrap/registry/GA secrets S |
| P14 | endpoint reconciliation | retained provider DNS/HAProxy entries не удалены и не переписаны |
| P15 | nginx/provider устанавливается, SDKU выбран, CSPA пропущена с изменённым desired endpoint | старый before_start и новый hook не меняют CSPA route; S=[]/first install отдельно PASS |

### Negative Scenarios

- неизвестный/повторный ID, пустая library-only выборка, запрещённый mode;
- provider reference отсутствует; consumer раньше provider; отсутствующая callback;
- disabled sso не вызывает API даже при наличии СЗИ;
- Keycloak недоступен/TLS не доверен/admin password неверен: обычная ошибка скрипта,
  consumer не запущен; no automatic install/repair пропущенной СЗИ;
- частичный отказ client/groups/accounts: нет premature dependent Vault delivery;
- route hook успешен на одном host и отказал на другом: нет старта C; retry завершает;
- несуществующая installed nginx config/image: package error, без acquisition/recreate;
- изменение S без пересборки plan/approval/image lease, stale async result;
- исключённая библиотека с lifecycle script: script не вызван; provider internal
  accounts не включены в C; чужой secret не появляется в descriptors;
- raw stdout/stderr/trace/plan/events не содержат runtime secrets/JWT.

### Contract Scenarios

Новые schemas и v1alpha compatibility, в том числе package v1alpha1/new runtime и
package v1alpha2/unsupported runtime, target once/each_target, execution_node once
и отклонение несовместимых сочетаний phase/run_on/execution. Canonical normalized S и fingerprint,
manifest tampering, минимальный provider secret provenance, argv projection,
missing capability, одинаковые результаты UI и standalone Ansible variables.
Manual standalone использует platform_application_skip_libraries=[] и полный
platform_application_library_order; та же Core selection function, без Go/UI.

### Regression Risks

Полная регрессия Core, затронутые service provider suites, Go test/vet и race
для затронутого async/session state при изменениях, frontend tests/lint/build,
SDKU schema/digest/Compose matrix, offline unshare для pure selection/planning.
Native tests должны вызывать реальные production tasks/scripts, не повторять
условия implementation в assertions. Сначала локальные API stubs/Ansible fixtures,
затем реальные scripts на isolated fixtures; только полный успех разрешает
подготовку нового реального run после owner разрешения.

### Environment Requirements

Core/Python/Ansible только RED OS Execution Node; source transfer через qa-sync.
Проверить доступные CPU/RAM/диск и выбранные placements перед стендом. Не выключать
посторонние сервисы и не очищать рабочую БД. СЗИ этапа2 сохраняется; нужен отдельный
QA project copy с корректным существующим project ID/PKI либо согласованная новая
PKI. Исходный SZI-only QA project сам по себе не является project с SDKU/CSPA:
добавить библиотеки штатным import/editor flow, а не менять runtime derived files.

Сохранить текущие SZI container IDs/StartedAt/restarts, config/PKI public hashes,
Vault versions, текущие users/groups/clients IDs и credentials metadata. Для
пропущенной библиотеки разрешённые изменения только новые/обновлённые внешние
integration objects и routes. Существующие GA/audit credentials не меняются.
Секреты/SSH/Vault через штатные session inputs; пользователь не выбирает файл
вручную — существующий bounded QA chooser только для известного Vault token file.

Новый immutable runtime bundle собрать/validate/publish/rebind стандартным способом,
после owner разрешения реализации. Старый bundle должен явно отклонять непустой S.
SKIP не заменяет обычный fresh BuildDeploymentPlan→review→approval→Start.

### Not Testable Locally

Windows не подтверждает native Ansible, Vault/Agent, реальную доставку PKI,
HAProxy/DNS/SSO или отсутствие изменений контейнеров. Mock frontend/Go harness
вспомогательные. Стендовая приёмка только real React handlers→Wails→Go→Core;
визуальная проверка отдельно и не объявляется PASS без выполнения.

## 11. Стендовая последовательность acceptance после реализации

1. Предварительные tests/fixtures полностью PASS; import/save/reopen/Project Verify.
2. СЗИ в полном desired project, skip szi, включены sso двух потребителей;
   сохранить baseline и runtime binding, выбрать существующий инфраструктурный Vault.
3. Fresh plan: только SDKU/CSPA installation и необходимые integrations;
   проверить images/secrets/host/endpoint scope и явную skipped-provider пометку.
4. Реальные approval/start. Записать revision, plan/run IDs и terminal Apply/Verify.
5. API-readback групп/realm+client roles, клиентов/applicationId/URLs/description;
   оба gateway targets и SSO/token/login поддерживаемых flows; Agent comparisons
   без раскрытия значений. Core Verify остаётся только service health.
6. Доказать отсутствие lifecycle/resource/PKI/Vault mutations СЗИ и неизменность
   container IDs/StartedAt/credentials; отдельно указать разрешённые route/API upserts.
7. Новый authoritative plan и repeat Apply с тем же S; no duplicate clients/groups,
   callbacks/route upsert unchanged, original credentials/Vault versions стабильны.
8. Отключение sso/исключение одного consumer — отдельный согласованный QA запуск:
   новые callbacks не вызываются, прежние объекты/маршруты не удаляются.
9. Журнал/Current state обновляются только по фактическим результатам; cleanup
   временных QA source/workspaces через установленную процедуру.

## 12. Вопросы независимому FULL PLAN review

Проверить достаточность A/C/P scope для images, resources, secrets и endpoints;
отсутствие скрытого Apply/Verify/PKI skipped provider; законность provider credential
custody без расширения до R; место integration_apply относительно внутренних
account dependencies и внешних consumers; target placement при разных host sets;
простоту расширения scripts и жизнеспособность более простого existing-hook варианта;
binding selection к plan/image lease/Start; compatibility и реальные QA gates.

Независимый reviewer фиксирует один FULL verdict с finding IDs. BLOCK не запускает
автоматический редизайн/повторный review. После решения владельца допустим один
TARGETED_RECHECK исправленных blocker IDs. До этого implementation/target actions0.
