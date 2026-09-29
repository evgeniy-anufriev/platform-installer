# SERVICE-INSTALL-07 — Redis и Redis Sentinel с TLS

Статус: **реализация начата; acceptance на targets ещё не проводился**.

## 1. Цель и граница этапа

Один service package `redis` поддерживает два режима: `standalone` устанавливает
один Redis на одном сервере; `sentinel-ha` размещает три Redis и три Sentinel
на одном, двух или трёх серверах. Начальная конфигурация с тремя парными
members на **одном** выбранном сервере должна работать без ручного назначения
портов и каталогов; размещение на трёх серверах также обязательно поддержать.
Клиентский Redis-порт в обоих режимах, а в HA также
репликация, подключения Sentinel к Redis и меж-Sentinel соединения используют
TLS; обычные TCP-порты Redis и Sentinel отключены. Этап включает самостоятельные
Ansible validate/apply/verify, Core snapshot/plan/execution, существующий Go
edit/save/plan/start/observer и Wails/React редактор для **обоих** режимов.
Для каждого режима приёмка требует два полных запуска с `SUCCEEDED`, verify
PASS и `changed=0` на повторном apply.

Следующий, отдельный SERVICE-INSTALL-08 проверит все **семь** сервисов одним
планом. Этот документ не запускает реализацию или тестовый deployment.

### Сверка UI до реализации

`docs/ui-design-01-mockups.html` и `docs/ui-design-01.md` задают порядок
Серверы → Топология → Сертификаты → Сервисы → Установка, переход из
топологии в настройки выбранного deployment, вкладки План/Выполнение/Результат.
Макет показывает Redis только как пример строки; его примерные статусы не
являются правилом Core. Для Redis сохраняются существующие страницы и
диалог «Секреты» выбранного сервиса. Макет не изображает парные процессы
Redis/Sentinel на одном host; для `sentinel-ha` UI должен показывать три
placement members, каждый с двумя ролями и двумя службами, в том числе когда
все три размещены на одном host. Для `standalone` — один member и только
Redis. Отдельной модели размещения Sentinel не требуется. Перед
UI-подэтапом и при приёмке эту сверку повторить.

## 2. Canonical desired state и топология

Добавить один versioned service package `services/redis/`, включающий
`service.yml`, совместимость, источник артефакта, configuration schema,
Ansible collection, apply/verify playbooks и тесты. Catalog и schema
генерируются действующими инструментами; опубликованные схемы и старые
service contracts не меняются только ради Redis.

Решение владельца для этого этапа: в одном canonical project допускается
Операционно этот этап поддерживает один Redis deployment в проекте. Это не
ограничение числа Redis-процессов: один `sentinel-ha` deployment содержит три
Redis и три Sentinel members. Два Redis deployments (например, `standalone` и
`sentinel-ha`) пока не поддерживаются как проверенная конфигурация, но Core
сейчас не блокирует такой проект отдельной проверкой. Для standalone
acceptance используется изолированный проект; ограничение остаётся
документированным эксплуатационным пределом, а не новым Core-контрактом.

Режим `standalone`: `placement.explicit=true`, `minMembers=maxMembers=1`,
`memberRoles=[redis]`, cardinality `redis minimum=maximum=1`. Он не создаёт
Sentinel unit, Sentinel listener, Sentinel state или replication settings.
Режим `sentinel-ha`: `placement.explicit=true`, `minMembers=maxMembers=3`,
`distinctHosts=false`, `memberRoles=[redis,sentinel]`, cardinality обеих ролей
`minimum=maximum=3`. Три canonical members, каждый с обеими ролями, выражают
требование «3 Redis + 3 Sentinel» существующим generic Core validator.
Повторяющиеся hostId допустимы: 3/1, 3/2 и 3/3 — поддерживаемые размещения;
три members на одном host — базовый путь без специальных ручных overrides.
Не нужны шесть member IDs, второй deployment или правило парности в Go.
Четвёртый member либо пропущенная роль блокируются до обращения к targets.
Один host при 3/1 остаётся единой точкой отказа: три Sentinel-процесса
образуют process-level quorum, но это **не** отказоустойчивость к потере host.
UI/plan/result не должны обозначать 3/1 как трёхсерверную HA-топологию.

Проект хранит deployment, одно либо три размещения согласно mode,
поддерживаемые настройки, `tlsProfile` и opaque `runtime:*` SecretRefs.
Core передаёт в существующем `x-memberListVariable` закрытый список
`platform_redis_instances` с deploymentId, id, host, address и roles каждого
member. Текущий generic private list уже несёт всё, кроме deploymentId;
добавить этот известный Core operation ID в **private** member entry, без
изменения публичного plan/schema или отдельного Redis DTO;
`roleVariablesByHost` несёт только общие для deployment настройки, одинаковые
для всех members данного host. Как и в Kafka, Redis role строит собственную
списковую *runtime* проекцию экземпляров до мутаций, а не пытается записать
три разных port/path scalar в одну host-scoped карту. В самостоятельном
Ansible path эта же проекция строится из канонических `platform_deployments`
в inventory/`host_vars`; если проектный список недоступен, допустим явно
переданный документированный `platform_redis_instances` с теми же identity
fields. Обе ветви проходят
один normalizer и один набор safety-проверок; role не требует Go/Core для
самостоятельного запуска. UI/Go не собирают эту проекцию и не разбирают YAML.
Первый bootstrap seed выбирается детерминированно из трёх canonical members
при *первой* инициализации `sentinel-ha` и не означает желаемого постоянного
primary. В `standalone` единственный Redis не участвует в выборе seed.
Текущую роль primary/replica сообщает Redis/Sentinel; она не записывается
в `project.yml` и не пересчитывается как desired state.

Manifest объявляет Redis data TLS listener для обоих режимов и Sentinel
control TLS listener только для `sentinel-ha`. Оба HA listener — member-scoped.
Для baseline `sentinel-ha` normalizer сортирует три стабильных memberId
*по всему deployment*, присваивает слоты 0, 1, 2 и выводит Redis TLS port
`6379 + slot`, Sentinel TLS port `26379 + slot`. Поэтому 3/1 работает без
ручных overrides, а перенос member между hosts сам по себе не меняет его
порт. `standalone` использует один slot 0 и не получает Sentinel endpoint.
Deployment-level base ports могут быть явными документированными managed
settings; членские port/path overrides в начальном Redis contract не
публикуются и не замалчиваются. `roleVariablesByHost` не передаёт в Redis
различающиеся member-level scalar settings: иначе текущий Core выдаёт
`EXECUTION_CONFIGURATION_HOST_CONFLICT`. Отдельные systemd instance names,
config, data, log и writable Sentinel-state paths выводятся из неизменяемых
deploymentId/memberId и фиксированных product-owned root paths. Все входные base ports,
вычисленные порты, адреса и paths проверяются как одна закрытая member-list
проекция до первого изменения target; apply, verify и diagnostics используют
именно её, а не независимо пересчитывают значения. Изменение состава/ID
members или base ports при уже существующем target state, способное
переназначить порт либо каталог, блокируется до apply, а не мигрируется
неявно: сверить только принадлежащие этому deployment существующие unit/config
и каталоги с рассчитанной проекцией, без сканирования чужого state и без новой
базы назначений. Sentinel объявляет именно достижимые address+port своего instance.
До мутаций проверяются коллизии портов и target-owned paths между members
и с соседними deployments; занятому порту нельзя присвоить новый экземпляр
даже при отсутствии Redis-процесса. Роли не
подставляют произвольные hostname вместо проверенных адресов и не открывают
plaintext fallback. Фиксированные product invariants: `port 0` и положительный
`tls-port` для Redis; для HA также `port 0`/`tls-port` у Sentinel и
`tls-replication yes` у реплик и Sentinel. В `standalone` TLS-only Redis
работает без репликации и без процессов Sentinel.
При несовместимых портах, отсутствии TLS support у одобренного пакета или
конфликте уже занятых ресурсов план/предзапускная проверка блокируется.

По умолчанию Redis использует отдельные верхнеуровневые каталоги
`/etc/platform-redis`, `/var/lib/platform-redis` и `/var/log/platform-redis`.
Общий `/etc/platform`, `/var/lib/platform` или `/var/log/platform` может быть
закрыт владельцем другого сервиса; Redis не меняет права общих родительских
каталогов ради доступа.

## 3. PKI, TLS и runtime credentials

Использовать существующий managed PKI: выбранный `tlsProfile`, сертификат
с `serverAuth` и `clientAuth`, доверенный CA и SAN объявляемых DNS/IP адресов
фактических серверов (`standalone`: одного; `sentinel-ha`: от одного до трёх).
При 3/1 три TLS endpoints могут иметь один host SAN, но каждый проверяется
по реально объявленному адресу; порт не является частью SAN. Для
deployment-scoped сертификата общий ключ допустим
только при уже принятой PKI scope-политике; его нельзя выдавать за три
независимых host certificates. `tls-auth-clients yes` и клиентские cert/key
нужны Redis, Sentinel, репликации и локальным проверкам. Core определяет
effective SAN и блокирует несовпадение идентичности; Go/React не вычисляют
SAN. Apply импортирует действующий `pki-apply.yml` до запуска Redis; verify
проверяет материальные сертификаты и соединения с проверкой цепочки/имени.
`CERTIFICATE_REISSUE_REQUIRED` и другие PKI blocks не обходятся.

`redisCredential.passwordSecretRef` нужен в обоих режимах: в `standalone`
для TLS-клиента Redis, в HA дополнительно для Sentinel и реплик.
`sentinelCredential.passwordSecretRef` нужен только в `sentinel-ha` для
меж-Sentinel аутентификации и отсутствует в standalone desired config и
наборе runtime requirements. Обе настройки — закрытые object descriptors с явным
`ui.x-runtimeSecretRequirement` (`SERVICE_PASSWORD`) и уникальными
статическими `requirementRef`; их точные IDs фиксируются в manifest при
реализации, различаются между Redis и Sentinel и не совпадают с требованиями
других сервисов. Текущая глобальная уникальность requirementRef остаётся
неизменной: ограничение одним Redis deployment не создаёт двух требований
Redis с тем же статическим ID в одном плане. Это решение не объявляет
поддержку нескольких Redis deployments без отдельного пересмотра secret
identity contract. Иные права/ACL вводятся только если доказаны необходимыми для
одобренной версии Redis; имена полей сами по себе не создают требований.

### Единый путь «Секреты» для Redis, PostgreSQL и следующих сервисов

В manifest modes используется extension `x-requiredRuntimeSecretSettings`:
ограниченный список **setting IDs**, который UI показывает как ожидаемые
runtime-секреты для выбранного mode. Для Redis: `standalone` содержит
только `redisCredential`; `sentinel-ha` — `redisCredential` и
`sentinelCredential`. Для уже существующего PostgreSQL: `standalone` содержит
`adminSuperuser`; `pg_auto_failover` — четыре его текущих credential settings.
Это UI-контекст для ввода до установки, а не новая универсальная Core
валидация обязательности полей по mode. Core сохраняет существующую проверку
формата и согласованности фактически заданных runtime-ссылок; отсутствие
поля из этого списка само по себе здесь не объявляется новым Core finding.
Поддержка метаданных вне этих runtime-секретных UI-подсказок не расширяется.

Пользовательский вход — существующая кнопка «Секреты» на выбранном сервисе.
Диалог доступен во время редактирования проекта, без проверки готовности,
подготовки или обращения к Execution Node. Go использует точный локально
проверенный catalog, выбранный mode и доверенные mode/setting metadata, чтобы
показать только объявленные требования, безопасные названия полей и
поддерживаемые ограничения ввода. Go проверяет UTF-8, непустое значение,
байтовые bounds и лишь те дополнительные правила, которые явно и полностью
заданы закрытым доверенным контрактом setting. React показывает результат,
не выводит правила из имени сервиса/поля и не считает локальную проверку
доказательством правильности пароля для внешней системы. При неизвестном mode,
отсутствующем либо несовместимом catalog и конфликтующей существующей ссылке
диалог возвращает безопасный prerequisite без записи. При активном чужом
черновике нет скрытого Commit: пользователь сначала сохраняет или отменяет
его. Для отсутствующих ссылок Go добавляет **только** закрытые
`SetServiceConfigurationValue` intents с
`{passwordSecretRef: "runtime:<trusted requirementRef>"}` (и требуемым
не-секретным username, если он предусмотрен descriptor) в существующий
EditSession, проводит обычный structural Review/Commit/reopen под его revision
guard и не вводит второго writer. Поля, уже правильно настроенные, не
переписываются. Если требуемый username отсутствует, пользователь вводит его
в диалоге как обычное desired поле до Save. Несовпадающий существующий ref,
даже грамматически допустимый, не перезаписывается молча — операция
останавливается с безопасным finding.

После сохранения ссылок Go принимает значения в существующий ограниченный
session-only broker через узкий **pre-plan pending** admission по проверенным
локальным metadata: точный project ID/root, deployment ID, mode, catalog lock,
setting ID и requirementRef. Это отдельное состояние доказательства, а не
второй broker, desired-state store или Core descriptor. Для ввода сервисного
пароля не требуются заранее заданные SSH/sudo credentials: тот же broker
держит короткоживущее project-bound service-only pending состояние, которое
не выдаётся через `WithTargetCredential` и не может создать Start lease.
Последующее задание/замена SSH/sudo credentials переносит pending значения
только при совпадении точной project binding и действующего TTL; иначе
обнуляет их и требует повторного ввода. Закрытие/истечение broker обнуляет
и target credentials, и pending значения. В pending допускаются
только ключи из закрытого набора текущего deployment; 1–4096 UTF-8 байт на
значение и существующие пределы числа/суммарных байт. Ни значение, ни
SecretRef не возвращаются React в ответах; одноразовый входной Wails-вызов
передаёт введённое значение из React в Go без логирования, а поля очищаются
после приёма/закрытия диалога. UI показывает «Задан» и локальные ошибки
формата, но не «Проверен Core». Pending evidence и значения удаляются при
смене проекта, deployment/mode, catalog/runtime identity, истечении lease,
изменении соответствующих secret settings либо новой canonical revision;
после Save ссылок ввод происходит уже на новой revision. Любой дальнейший
Save, способный изменить требования, требует повторного ввода с явным
сообщением пользователю. Нельзя перенести pending values на другой проект,
узел или иную ревизию молча.

Переход к установке — единственный обязательный readiness gate: выбранный
Execution Node проверяется существующим путём, изменяющая его подготовка
требует явного подтверждения. Один успешный результат проверки для той же
доверенной node/runtime identity не запускается повторно из-за каждого
project Save; изменение canonical revision всё равно делает прежние Verify
и DeploymentPlan устаревшими. До разрешения Start приложение запрашивает
`BuildRuntimeSecretDescriptors` у Core для **текущей сохранённой revision**,
сверяет project/runtime identity, descriptor fingerprint, deployment и
полный набор requirementRefs с текущими pending values и строит свежий
`BuildDeploymentPlan`. Расхождение, отсутствие или истёкшее значение блокирует
Start **до target contact**, показывает конкретные недостающие поля и
предлагает повторный ввод; неподтверждённые pending values не становятся
runtime lease для Execution Node. При совпадении используются существующие
lease transport, approval и Start. Отдельный запрос дескрипторов и план могут
выполняться в одном installation flow без второй полной проверки готовности;
нужно проверить текущие вызовы readiness и исключить лишний многоминутный
повтор при неизменной node/runtime identity, сохранив свежий Core plan.

Выбор project server в панели сам по себе пока не создаёт доверенный
Execution Node binding: текущий readiness path принимает `EXPLICIT_EXTERNAL`.
При `BINDING_REQUIRED` установка показывает prerequisite в панели «Серверы»,
сохраняет только проектные ссылки и не передаёт значения узлу. Поддержка
project-server binding требует отдельного решения и не является частью
секретного диалога. Страница остаётся минималистичной: отдельного редактора
SecretRef нет.

Для PostgreSQL добавление mode metadata изменяет service definition:
увеличить её version, воспроизводимо пересобрать catalog и новый immutable
runtime bundle. Проекты со старым catalog/artifact lock остаются на старой
совместимой версии и не перепривязываются автоматически. Для acceptance
явно проверить старый lock без новой семантики и отдельный контролируемый
upgrade/relock путь к новому digest перед новым Secrets flow; при
несовместимости блокировать, не ослабляя lock или schema checks.

Core публикует безопасные descriptors при переходе к планированию и private
manifest mappings; Go broker держит предварительные значения только в session,
а перед Start сверяет их с Core descriptors. Существующий v1alpha3 lease
доставляет их Execution Node, а контроллер даёт Redis operation лишь его
private `platform_redis_secret_files`. Значения не попадают в проект, план,
snapshot, ответы Wails, event stream или диагностику. Входной Wails-вызов
несёт значение только от формы к Go и не записывается в журнал/ошибки.

Target Redis/Sentinel может требовать собственные защищённые runtime-файлы с
паролем для перезапуска после завершения run. Роль создаёт их с владельцем
службы и mode `0600`; не использует plaintext в argv, template diff или
Ansible callback. В документации и тестах отдельно проверить target-file
ownership, маскировку секретных tasks и отсутствие секрета в видимых артефактах.
Отсутствие обязательного для выбранного mode runtime value блокирует Start до
target contact. Самостоятельный Ansible
получает те же documented variables и защищённые файлы по явным локальным
путям, без Go lease как обязательной зависимости роли.

## 4. Владение Sentinel state и безопасная сходимость

Sentinel сам изменяет свой рабочий `sentinel.conf`: сохраняет обнаруженные
узлы, config epoch и нового master после failover. Файл расположен в
долговечном target-owned каталоге и принадлежит пользователю службы. Ansible
создаёт seed-конфигурацию только при доказанно новой установке; при repeat
не перезаписывает Sentinel-owned поля и не возвращает initial master.
Статические TLS/auth/port параметры проверяются отдельно. Если их нельзя
безопасно обновить без потери динамического state, apply возвращает явный
block и требует отдельной контролируемой операции, а не удаляет рабочий
конфиг. Полная потеря Sentinel/Redis persistent state при существующем
deployment также fail-closed; автоматическое создание нового кластера под
старым project identity запрещено.

Redis data directories, AOF/RDB и, для HA, текущая репликация остаются
target-owned runtime state. В `standalone` существующий data directory не
очищается и не превращается автоматически в HA deployment. Инициализация
первого HA master/реплик разрешена только при подтверждённом пустом deployment.
После первого HA bootstrap Sentinel определяет
активный master, а роль проверяет и согласует наблюдаемую репликацию без
жёсткого `replicaof` на первоначальный seed. Нормальный failover или restart
не должен делать repeat apply `changed>0`. Ни Go, ни project writer не хранят
Sentinel epoch, master address или Redis data.

## 5. Полный путь реализации

1. **Standalone Ansible.** Создать package/role с обычными документированными
   переменными и playbooks `validate`, `apply`, `verify`; проверить mode,
   placement, TLS, credentials и target paths. `standalone` выполняет
   PKI → один Redis → verify. `sentinel-ha` выполняет PKI → Redis seed →
   два Redis replica → три Sentinel → convergence/verify. `verify` только
   читает. Проверить безопасный repeat и отказ при частичном state в обоих
   режимах; переход между ними требует отдельной миграции и здесь заблокирован.
2. **Core.** Подключить manifest и schema к catalog, target-free
   `ProjectSnapshot`/`BuildDeploymentPlan`, artifact source authority,
   pre-plan secret descriptors, private role variables и PKI materialization.
   Единая mode-metadata проверка обязательных secret settings применяется и
   к PostgreSQL; существующий extractor требований остаётся ref-bound, а
   отсутствие ref блокируется до extractor через validation.
   Для Redis `x-memberListVariable` передаёт member identity/placement, а
   deployment-level base settings остаются обычными role variables; не
   создавать три разные host-scoped scalar settings или новую публичную
   per-instance DTO. Роль делает общую для managed и standalone Ansible
   member-list normalization до apply/verify.
   Использовать существующие generic gates, без `if service == redis` в Go
   или отдельных Redis DTO. Core plan остаётся одним execution gate для всех
   сервисов проекта.
3. **Go.** Создание deployment, одного `redis` member либо трёх paired
   `redis`/`sentinel` members, settings и `tlsProfile`
   проходят существующий typed EditSession → local Review/Save → reopen.
   Проверка проекта остаётся отдельной; для запуска нужен fresh plan,
   approval, lease и Start. Для кнопки «Секреты» Go координирует тот же
   EditSession/Review/Commit и локальный pending admission в существующий
   broker. Core descriptor operation выполняется при планировании установки;
   никакого нового writer/save механизма или хранения plaintext.
4. **Wails/React.** В Топологии выбрать `standalone` с одним member либо
   `sentinel-ha` с тремя members, каждый с ролями `redis` и `sentinel`,
   по умолчанию допускает выбранный один host для всех трёх;
   настройки берутся из точного каталога.
   Поддерживаемые поля и TLS profile используют текущий редактор. Закрытые
   credential objects остаются скрытыми в settings; кнопка «Секреты»
   выбранного deployment обеспечивает ссылки через обычный Save, показывает
   ограниченные поля по доверенному каталогу и принимает значения без
   Execution Node. Локальные ошибки видны сразу; Core descriptors сверяются
   при переходе к установке до Start.
   В Установке показываются тот же план, task events и terminal
   result. Новых Redis-specific экранов, парсинга Ansible YAML и прямого
   чтения `events.jsonl` в React нет.

Сначала подтвердить наличие одобренного TLS-enabled Redis пакета для RED OS,
совместимые systemd binary paths, доступные порты и отсутствие конфликта с
существующими QA deployments на выбранном одном либо трёх hosts. Источник — approved repository
или immutable offline bundle по текущей node-scoped source policy. Никакого
скачивания во время production apply.

## 6. Приёмка и этапы QA

Отдельный Redis milestone проверяет оба режима без изменения одного deployment
из `standalone` в `sentinel-ha`. `standalone` испытывается в отдельном
изолированном управляемом QA project; `sentinel-ha` добавляется как
**единственный Redis deployment** в накопительный проект для финального
SERVICE-INSTALL-08. Два Redis deployments никогда не находятся в одной
ревизии проекта. Это не подменяет прошлые Kafka/PostgreSQL evidence.
Перед тестом снять read-only карту units,
портов, каталогов и владельцев; удалять только доказанно legacy QA Redis
state. Проверки идут последовательно:

- самостоятельный Ansible target-free validate/plan, затем реальный
  apply/verify `standalone` на одном RED OS host: один Redis unit, TLS-only
  client login, сохранение данных и repeat `changed=0`, без Sentinel unit;
- затем отдельный `sentinel-ha` apply/verify с тремя members **на одном** RED OS
  host без ручной настройки портов/каталогов: шесть раздельных units, шесть
  непересекающихся TLS listeners и state paths, объявленные address+port,
  TCP=0, TLS handshake, SAN/EKU, Redis replication и
  `SENTINEL CKQUORUM`/`GET-MASTER-ADDR-BY-NAME`;
- focused target-free и role-normalizer tests подтверждают один и тот же
  memberId→slot→port/path результат для 3/1, 3/2 и 3/3, а также для
  managed Core и самостоятельного inventory; различающиеся member-level
  scalar overrides, занятый порт, пересечение путей и опасный identity/port
  drift блокируются без частичной установки;
- acceptance использует один Redis deployment в каждом проекте; два Redis
  deployments в одном проекте не заявляются как поддерживаемая конфигурация,
  но отдельной новой Core-блокировки для них нет;
- общий Secrets flow: PostgreSQL и оба Redis mode создают отсутствующие refs
  из trusted mode metadata без ручного SecretRef; password input и локальная
  проверка доступны без Execution Node; существующий draft, stale catalog,
  revision и конфликт refs не фиксируют скрыто чужие изменения; после Save
  ref есть в проекте, значение отсутствует в canonical файлах и хранится
  только в session broker; Core подтверждает полный набор до Start;
- Save после ввода, смена deployment/mode/catalog/project, истечение lease и
  смена Execution Node не переносят pending secret values молча; UI показывает
  необходимость повторного ввода. Длительная проверка Execution Node не
  запускается при открытии диалога или каждом Save;
- ввод сервисного пароля до SSH/sudo credentials и после них проходит без
  readiness; замена target credentials для того же проекта сохраняет pending
  значения только до их прежнего TTL и никогда не создаёт Start lease без
  свежего Core-сопоставления; ответы Wails и ошибки не содержат пароль;
- Core и Go plan проверяют формат и согласованность runtime-ссылок, которые
  присутствуют в desired state; mode metadata служит UI для описания
  ожидаемого ввода и не добавляет нового Core finding на отсутствие ссылки;
  повторное открытие Secrets не добавляет команд и не меняет canonical revision;
- отдельный 3/3 acceptance на трёх RED OS hosts доказывает распределённое
  размещение и независимость от однохостового baseline; 3/2 также допускается
  контрактом и проверяется focused topology/port tests;
- Go-managed project edit/save/reopen, свежий plan, secret descriptors,
  approval и Start; Wails/React end-to-end создаёт тот же deployment и
  наблюдает реальные task events, без прямого YAML редактирования;
- для `standalone` первый и повторный Go/UI run `SUCCEEDED`, verify PASS,
  repeat `changed=0`, на target активен ровно один Redis данного deployment;
- для `sentinel-ha` в 3/1 и 3/3 первый полный run `SUCCEEDED`, три active Redis
  и три active Sentinel units,
  один observed master, две синхронизирующиеся replicas, три согласованных
  Sentinel и TLS-only connections;
- свежий второй plan/run для 3/1 и 3/3 `SUCCEEDED`, verify PASS и все apply
  recaps `changed=0`; проверка, что после штатного Sentinel failover следующий
  read-only verify видит нового master, а повторный apply не возвращает seed;
- отсутствие plaintext в проекте, плане, журнале, installer mirror, UI и
  diff; сохранность соседних QA deployments; Core/Go/frontend/Wails/RED OS
  regression, race, catalog/schema reproducibility и `git diff --check`.

Управляемый failover может прервать сервис; выполнять его только на
изолированном Redis QA deployment после проверки ownership и влияния на
соседей. Если такой тест нельзя безопасно провести, зафиксировать его как
непройденный критерий, а не считать этап DONE по одному health check.

## 7. Не входит и открытые проверки перед кодом

Нет Redis Cluster/sharding, произвольных ACL редакторов, внешних CA, Vault,
автоматической смены паролей, нового public protocol, локального парсинга
Ansible в UI или generic state database. Конкретные версии пакетов/команды
проверяются на RED OS и фиксируются в `compatibility.yml` и tests до
публикации bundle. Приоритет — существующий путь сервисного пакета.

Прежде чем считать финальный all-services этап готовым, нужно подтвердить,
что PostgreSQL SERVICE-INSTALL-06 evidence из изолированного проекта перенесено
в один cumulative canonical project: его отдельный PASS не доказывает
совместную установку. SERVICE-INSTALL-08 принимает именно одну свежую
ревизию и один plan для всех семи сервисов.

## Источники технических ограничений Redis

- [Redis Open Source TLS](https://redis.io/docs/latest/operate/oss_and_stack/management/security/encryption/):
  `port 0`, `tls-port`, `tls-replication yes` и TLS для Sentinel.
- [Redis Sentinel](https://redis.io/docs/latest/operate/oss_and_stack/management/sentinel/):
  writable persistent `sentinel.conf`, quorum, discovery и failover state.
- [Redis ACL](https://redis.io/docs/latest/operate/oss_and_stack/management/security/acl/):
  права Sentinel и replica, если выбран ACL-based вариант.
