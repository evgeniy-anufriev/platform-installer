# Пользовательские библиотеки приложений — общий план реализации

Документ для обсуждения последовательности работ. Подготовка этого плана не
означает начала реализации, запуска QA на targets или разрешения нового milestone.
Обсуждение завершено; по указанию владельца действует стандартная процедура ревью.
Результат FULL PLAN: [APPROVE_WITH_CHANGES](plan-review.md), ноль блокирующих замечаний.
Текущий статус и разрешённый scope
ведутся только в [CURRENT_STATE](../../CURRENT_STATE.md), результаты будущих проверок —
в отдельном журнале. Здесь нет параллельного списка DONE/NEXT.

## Цель и последовательность

Дать возможность установить библиотеку СДКУ/ЦСПА с переиспользуемыми контейнерными
приложениями, общими ресурсами, индивидуальными УЗ, Vault Agent и endpoints:

1. **A — standalone Ansible + Core:** обычные inventory/defaults/group_vars/host_vars,
   Core schemas/snapshot/validation/планирование и исполнение на Execution Node;
   запуск без Go, Wails, UI и обязательного project.yml.
2. **B — Go backend:** подключение готового Ansible/Core пути через существующий
   адаптер, guarded writer, approval/execution lifecycle и доставку runtime.
3. **C — UI:** страница «Приложения» и полный пользовательский сценарий.

Вся инфраструктурная семантика Ansible/Python Core реализуется и проверяется
в A. Этап B добавляет только Go application semantics и оркестрацию готового
контракта: он не воспроизводит defaults, resolver, DAG или provider rules.

Подробные предметные решения: [архитектура](architecture.md),
[конфигурация](configuration.md), [установка](execution.md),
[секреты](secrets.md), [UI](ui.md).

## Правило простоты

Для каждой части сначала найти существующий путь и расширить его минимально.
Новый механизм допустим только при конкретном пробеле, который нельзя закрыть
обычной ролью, task sequence, шаблоном, module или небольшим расширением контракта.
Обоснование должно называть этот пробел и более простую рассмотренную альтернативу.

| Потребность | Использовать | Не создавать |
| --- | --- | --- |
| Настройки | Role defaults и обычные Ansible vars; явный combine разных inputs | Второй precedence/Jinja engine |
| Compose | Исходные шаблоны, base Compose, `.env`, штатные extends и validation | Собственный Compose merger/parser для исполнения |
| Ресурсы и УЗ | Общие provider-owned tasks/entrypoints и manifest capabilities | SQL/ACL hooks на каждое приложение, универсальный script DSL |
| Зависимости | Существующий Core DAG; обычная последовательность Ansible tasks | Второй scheduler, daemon, event bus |
| Vault/PKI | Существующие credentials, identity, trust, runtime-secret boundaries | Второй secret store в проекте, plaintext env с паролями |
| HAProxy/DNS | Существующие resolver, publication, ownership/reconcile | Второй генератор HAProxy и отдельный DNS registry |
| Save/Start | Guarded writer, revisions, plans, approval, execution protocol | Applications-only save/start bypass |
| UI | Формы и interaction patterns страницы «Сервисы», metadata/snapshot | Семантика инфраструктуры в React |
| Packages/artifacts | Existing locks, transfer/export, bundle/source policy | Собственный package manager или updater |

Не писать общий CRUD/plugin framework ради нескольких текущих полей. Не заводить
новую БД или durable ledger, если existing runtime evidence решает задачу. Не
обещать общую транзакцию между providers и Compose. При этом простота не отменяет
secret safety, ownership, явную проверку refs и безопасное восстановление.

Тестировать контракты и реальные риски, не зеркалировать каждую строку реализации.
Сначала affected checks; полный набор повторять только по gate или новым причинам.

## A. Standalone Ansible + Core

### Общее требование A1–A9: скорость выполнения и минимум действий

Граница hooks уточнена владельцем 2026-10-10: resource batch относится к одной
логической библиотеке, account/grants hook — к одному логическому экземпляру
приложения. Не объединять mutations разных библиотек/экземпляров в provider-wide
batch. Общий provider discovery допускается один раз в invocation; Docker
placements не размножают logical hooks. Применять это правило ко всем следующим
providers, включая Vault/Redis/ClickHouse/Kafka и endpoint hooks. Benchmark
сравнения отменены владельцем; дополнительные benchmark runs не выполнять.

Уточнение владельца 2026-10-10: скорость выполнения — приоритет всего этапа A.
Минимизировать Ansible tasks, SSH/module invocations, SQL/API requests, повторное
обнаружение и файловые операции. Десятки контейнеров и несколько providers не
должны повторять общую подготовку для каждого instance/placement.

- Разрешение проекта и построение jobs выполняются один раз на execution.
  Общие readiness/discovery проверки — один раз на provider deployment;
  library resources/shared secrets — один раз на logical library; account/
  AppRole/policy — один раз на logical instance. Host materialization, image
  availability и container startup выполняются только на нужных Docker-хостах.
- Объединять compatible SQL/API/file операции внутри одной библиотеки либо
  одного экземпляра в небольшое число явных фаз. Не объединять разные logical
  scopes ради уменьшения числа provider calls.
  Не создавать task на каждый privilege, credential field, env variable или
  Vault policy rule. Использовать существующие native bulk/batch средства;
  отсутствие безопасного batch API не оправдывает новый framework.
- Переиспользовать execution-local discovery/results, сохраняя обязательную
  проверку writable state/ownership/version перед mutation. Не заводить
  persistent cache фактов/секретов или второй desired-state store.
- Чистый повтор не выполняет лишних DDL, password resets, KV versions, policy
  writes, uploads, docker pull/load, recreate/restart и endpoint reload.
  Сравнить actual/expected, применять только изменения. changed=0 сам по себе
  недостаточен: измерять фактические вызовы и продолжительность.
- Verify использует пакетные read-only проверки; не повторяет install/provisioning
  и не reparирует drift. Полный standalone Apply не должен внутри каждого hook
  повторно запускать общий infrastructure Verify/PKI/runtime preparation.
- Не вводить scheduler, очередь, workers или daemon ради скорости; сначала
  убрать дублирование и мелкие actions. Параллельность — только штатная Ansible,
  где она не нарушает library/infra barriers, ownership, locks и CAS.
- Скорость не отменяет guards, secret isolation, least privilege и safe retry.
  Unsafe shortcut запрещён; проверку объединить/переиспользовать, а не удалить.

В каждом подэтапе фиксировать first Apply / clean repeat / Verify duration,
число module и provider calls; отдельно image delivery и readiness wait.
Проверять масштабирование 1/10/30 instances и несколько hosts: общая работа
не должна расти как instances × placements × providers. Числовой budget
согласовывать по реальным RED OS замерам; не обещать непроверенный SLA.
Известные длительности A2 — baseline для анализа, не основание повторять
target QA без отдельного scope. Performance requirement не открывает уже
закрытые A1/A2 на автоматический refactor.

### A1. Минимальный контракт и сквозные fixtures

Подробный scope, последовательность и acceptance matrix:
[технический план A1](a1-technical-plan.md).

- Зафиксировать формы application/library definitions и instances, overrides,
  placement, bindings, resources, secret bindings и endpoint backend settings.
- Вычислять application instance ID как `<application_name>-<library_instance_id>`;
  пользователь задаёт только ID библиотеки. Recipe slot выбирает definition,
  повтор одного definition в нескольких slots блокируется в начальном scope.
  Вычисленный ID автоматически заполняет нужные env.
- Выбрать простейшую Compose layout, доказывающую два экземпляра одного приложения
  на одном хосте и одну библиотеку на двух Docker-хостах: service keys, локальные
  `.env`/Compose projects, paths, ports и names без коллизий. `${SERVER_ID}`
  проецировать из существующего ID inventory-хоста, без отдельного поля в `host_vars`.
- Сохранить defaults authority, явный combine и существующий ansible.cfg.
- Подготовить компактные fixtures СДКУ/ЦСПА с одним application definition и
  различными instance IDs/bindings. Проверить их current schemas там, где возможно.
- До A2 определить доверенные пакеты и допустимые файлы/пути. Достаточно явно
  выбранных владельцем локальных пакетов с зафиксированным содержимым; digest
  подтверждает идентичность, но не является разрешением исполнения. Изменение
  содержимого требует проверки области доверия и новой ревизии плана. Новый
  signing service/package manager не нужен; B2 добавляет безопасный импорт.

**Результат:** небольшой контракт с примерами и точными точками расширения.
**Выход:** два экземпляра разрешаются независимо; отсутствует второй desired state;
нельзя начать mutation части до определения ownership и secret boundaries этой части.

### A2. Материализация и запуск простого контейнера

Подробные границы, изменения contracts/runtime и проверки:
[технический план A2](a2-technical-plan.md). Реализация требует отдельного
разрешения владельца после независимого PLAN review.

#### A2.1. Доставка образов на Docker-хосты

До Compose startup обеспечить образы на каждом хосте размещения библиотеки.
Переиспользовать существующую node-scoped source policy и bundle transfer:
совместимый образ в настроенном approved registry имеет приоритет, иначе
использовать verified immutable bundle, иначе BLOCK.

- Registry: получить закреплённый образ штатным `docker compose pull` в выбранном
  rootless Docker runtime; registry credentials поступают только через runtime
  secret механизм. Pull выполняется явно в фазе доставки, а не случайно при `up`.
- Bundle: доставить архив образа на каждый Docker-хост, проверить artifact digest
  и выполнить `docker load` в его выбранном daemon. Проверить загруженную image
  identity/platform по lock metadata; digest архива и image identity различаются.
- Compose использует reference, соответствующий проверенному локальному образу;
  offline startup выполняется без pull/build. Если архив не сохраняет пригодный
  registry digest reference, локальный reference материализуется из lock metadata,
  а не вычисляется из имени tar-файла. Собственный image importer не создавать.
- Повтор использует уже проверенный образ; предусмотреть отсутствие registry,
  повреждённый архив, несовместимую platform, недостающий образ и два Docker-хоста.
  Сборка/DEV acquisition и изменение bundle остаются отдельными операциями.

- Общие tasks формируют base Compose и несекретный `.env` библиотеки.
- Template приложения получает identity и instance overrides, сохраняя extends.
- Использовать выбранный существующий rootless Docker runtime; Docker installer
  не переписывать. Проверять безопасные paths/ownership и доступность image;
  из Compose сверять только значения, проецируемые Core, оставляя авторские
  поля и literal host bind address на усмотрение пользователя.
- Реализовать apply/verify через стандартные Ansible средства и имеющиеся
  зависимости. Если подходящий module уже доступен — переиспользовать; новый
  dependency вводить только с обоснованной необходимостью и offline closure.
- Source selection выполняется при execution: approved compatible source,
  затем immutable offline artifact, иначе BLOCK; без неявного pull/build.

**Результат:** ручной ansible-playbook запускает два изолированных экземпляра.
**Выход:** defaults/overrides, readiness, repeat changed=0, отсутствие port/path
коллизий; изменение одного instance не перезапускает другой без причины.
Повторить запуск одной библиотеки на двух Docker-хостах; общие ресурсы и УЗ
готовятся один раз, а Compose и `${SERVER_ID}` материализуются для каждого хоста.
Это технический baseline, ещё не полный сценарий приложения с УЗ/Vault.

### A3. Ресурсы библиотеки и общий PostgreSQL hook

Подробные contracts, последовательность, performance и QA:
[технический план A3](a3-technical-plan.md). Реализация требует отдельного
решения владельца после независимого PLAN review.

- В A1 закрепить выбор интерфейса в `connection_defaults` библиотеки по serviceType,
  с override экземпляра библиотеки. Binding выбирает только deploymentRef.
  Kafka требует connectionRef; другие providers — только при неоднозначности
  подходящих интерфейсов. Использовать существующие effective проекции Core,
  не менять инфраструктурные apply roles и не вводить новый каталог интерфейсов.

- Для всех provider hooks использовать одно условие: соответствующий service ref
  и объявленное действие. Без ref hook пропускается; неизвестный заданный ref
  или обязательный ref отсутствующий у объявленного действия блокирует validation.
  Не требовать все providers и не выбирать их автоматически; refs через library
  bindings учитываются. HAProxy и DNS hooks проверяются независимо.

- Сначала реализовать один provider end-to-end: создание БД/схемы библиотеки,
  затем УЗ и grants экземпляров через один PostgreSQL entrypoint.
- Ресурсы имеют явные ссылки, ownership и managed/existing semantics.
- Барьер подготовки библиотеки блокирует dependent instances при ошибке.
- Создание таблиц/миграции отделить от создания БД и поставить до соответствующих
  grants. Не строить отдельный migration engine; использовать существующий путь
  приложения, если он определён, иначе оставить prerequisite явно незакрытым.
- Credentials подаются через текущий runtime-механизм. До A4 использовать только
  безопасный standalone credential input; не писать временную plaintext альтернативу.

**Результат:** два приложения вызывают одинаковые PostgreSQL tasks с разными inputs.
**Выход:** least privilege, foreign-resource rejection, repeat и interrupted
create/retry; нет takeover по username и неявного удаления общих ресурсов.

### A4. Vault provisioning, Agent и общие PKI-секреты

- Account/grants hooks и credential writes включаются при непустом effective
  accounts после overrides. Vault Agent, policy/AppRole/RoleID и Agent files/volumes
  включаются при непустом secret_bindings, включая shared-only без accounts.
  Каждая source выбирает ровно account+field либо library_secret; одновременно
  разные bindings могут использовать оба вида. Без bindings запуск прямой командой.
  Library resources и endpoints независимы; shared secrets нужны только потребителям.

- Один provider-owned Vault hook: secrets, минимальная policy, AppRole.
- Managed KV v2: отсутствующий документ создавать через `put` с CAS=0,
  изменённые поля существующего — через `patch` с текущей версией CAS; одинаковые
  значения не записывать. Проверить сохранение соседних полей, CAS conflict,
  read-only `vault_ref` и согласованность password rotation с provider.
- AppRole: `bind_secret_id=false`; Core автоматически вычисляет `token_bound_cidrs`
  из адресов выхода хостов размещения к Vault (IPv4 `/24` плюс `127.0.0.1/32`, union для
  нескольких хостов), без ручного CIDR в vars. Владелец подтвердил, что видимый
  Vault source IP, включая proxy, входит в /24; host-level isolation не заявляется.
  Endpoint при наличии имеет приоритет, иначе resolved client address/port;
  error fallback запрещён. После создания роли читать RoleID
  и доставлять в защищённую volume-папку
  каждого Docker-хоста с read-only mount и правами чтения для Vault Agent;
  SecretID не создавать. Проверить разрешённый/запрещённый источник и фактический
  source address при rootless/NAT, restart/re-auth по сохранённому RoleID.
- Defaults связывает env name с account field, library secret либо явно existing
  Vault secret. Хук не получает произвольный исполняемый путь от приложения.
- На библиотечном этапе публиковать общий java_keystore_password из точного PKI
  credential/material binding. Не дублировать его в каждом instance path.
- Для экземпляра выдавать read только на объявленные secret paths и генерировать
  agent.hcl. Template syntax Agent не должен случайно исполняться Ansible/Jinja.
- Зафиксировать bootstrap, restart/re-auth/expiry, rotation и interrupted retry
  перед реализацией. Не считать одноразовый wrapped token решением всех restart.
- Agent внутри подготовленного образа передаёт secrets процессу; обычные `.env`,
  Compose, snapshot и logs остаются без значений секретов.

**Результат:** PostgreSQL credential и общий PKI-secret доходят до процесса через Agent.
**Выход:** read isolation, missing credential failure, повтор без смены паролей,
restart/re-auth и согласованность keystore/password; admin secrets не доступны app.

### A5. Остальные providers по тому же образцу — текущий scope выполнен

Подробная последовательность, defaults/overrides и QA:
[технический план A5](a5-technical-plan.md). Для текущего согласуемого scope
учтено ранее выбранное Kafka SSL-подключение без аутентификации; полная
SASL/principal/ACL часть строки A5.3 ниже требует отдельного security расширения
и не считается выполненной SSL protocol probe.

Текущий Redis/Sentinel, ClickHouse и Kafka SSL-only scope реализован и прошёл
обязательный review/QA; см. [FULL DIFF и targeted recheck](a5-diff-review.md)
и [журнал](a5-test-journal.md). C02 Keeper production access/retention proof
остаётся неблокирующим ограничением. Kafka SASL/principal/ACL по-прежнему требует
отдельного security scope.

Выполнять отдельными ограниченными частями:

| Часть | Минимальный результат |
| --- | --- |
| A5.1 Redis | Общий ACL user hook, key/command permissions и проверка подключения |
| A5.2 ClickHouse | Общий account/grants hook и проверка нужной БД/таблиц |
| A5.3 Kafka | Сначала явная поддержка выбранного SASL mechanism/listener/ACL в пакете, затем общий principal/ACL hook |

Переиспользовать A3/A4 envelope и provider-owned tasks, не делать общий SQL/ACL
язык. Topic/database provisioning добавлять только для явно заявленных ресурсов.
Текущий Kafka manifest отмечает SASL unsupported: нельзя закрыть этот пункт
созданием фиктивной УЗ или переходом на anonymous access. Scope Kafka security
изменения отдельно детализировать до кода.

**Выход каждой части:** реальное authenticated connection, минимальные права,
повтор и отсутствие secret leakage. Затем один экземпляр подключается ко всем
четырём providers через свои credentials, полученные Vault Agent.

### A6. Endpoints через существующие HAProxy/DNS hooks

- Расширить source identity существующей интеграции на application instance.
- Defaults backend и instance overrides отображать в существующий HAProxy
  contract. Адрес/порт каждого target получать из host placement и выбранного
  listener; один endpoint включает готовые targets всех выбранных хостов.
- Сохранить service IDs/FQDN/ownership и existing provider selection/reconcile.
- Публиковать после readiness; проверить frontend/backend TLS и protocol-specific
  probes. Не считать HTTP probe универсальным для всех listener protocols.
- Сохранить действующее missing-provider поведение и отдельно показать, что
  endpoint не опубликован; не вводить новый execution terminal state.

**Выход:** правильные DNS/HAProxy targets, реальный внешний endpoint, repeat,
конфликты/частичный сбой и отсутствие изменений у соседних источников.

### A7. Core snapshot, validation, планирование и execution contract

Расширить существующие schemas/snapshot/findings: libraries, instances, origins,
resources, secret requirements и endpoint projection. Потреблять те же определения
и resolver/tasks. Интегрировать фазы библиотеки и экземпляров в существующий Core
DAG, target-free plan и production execution protocol; не создавать второй путь.
Подготовить Core package/bundle requirements, fingerprints и offline closure через
существующие инструменты по [bundle procedure](../agent-procedures/runtime-bundle.md).
Минимальные части этого контракта вводятся по мере A1–A6; A7 завершает интеграцию.

**Выход:** связь findings с точным полем, стабильный fingerprint, отсутствие target
контакта при target-free операциях и secret values в output; совпадение standalone
и structured Core пути. Инфраструктурный план и execution protocol работают без Go.
Контрактные проверки: старый проект без libraries сохраняет прежнее поведение;
неизвестная major version и несовместимый package/runtime lock отклоняются;
Apply не выполняет скрытую миграцию. Использовать existing version/lock mechanisms,
без отдельного migration framework.

### A8. Интеграция библиотек в общий план выполнения

Общий Core план содержит два последовательных этапа:

1. **Инфраструктура:** Apply/Verify всех инфраструктурных deployments, включённых
   в план, в их существующем порядке зависимостей.
2. **Библиотеки приложений:** подготовка ресурсов библиотеки, УЗ/секретов,
   запуск экземпляров, публикация endpoints и Verify.

Между ними обязательный барьер: библиотеки не начинают mutations, пока успешно
не завершены установка и проверка всех инфраструктурных сервисов общего плана,
а не только непосредственных providers первой библиотеки. Ошибка, отмена или
незавершённость инфраструктурного этапа не допускает переход к библиотекам.
Target-free validation всех частей может выполняться заранее.

Bindings библиотек остаются явными dependency references: проверять наличие,
capabilities и порядок providers, не заменять проверки одним барьером. Общий план
имеет одно approval и execution lifecycle, не цепочку скрытых отдельных запусков.
Реализовать этапы существующей последовательностью/DAG; не добавлять scheduler.

Создание БД/УЗ и endpoint hooks библиотек выполняются во втором этапе на уже
подготовленных providers. Это потребительская настройка инфраструктуры, а не
повторная установка PostgreSQL/Vault/HAProxy/DNS. Такая граница предотвращает
цикл «инфраструктура ждёт будущие endpoints приложений».

Частичная установка одной библиотеки не подразумевается новым этапом и не
расширяет отложенный selective-plan scope. В ручном standalone использовании
ранее установленной инфраструктуры readiness обязательных providers проверяется
явно; отсутствие infrastructure actions не является доказательством готовности.

**Выход:** один общий план infrastructure + libraries; все infrastructure Verify
предшествуют первой library mutation. Проверить успешный порядок, ошибку даже
не связанного напрямую infra deployment, cancel на границе, отсутствие запуска
библиотеки после сбоя и сохранение прежнего поведения infrastructure-only плана.

### A9. Полная standalone Ansible + Core приёмка

Пройти сценарий: inventory/vars → ресурсы библиотеки → общие secrets → УЗ/apps
→ Agent → connections → endpoint/verify. СДКУ и ЦСПА используют один пакет приложения
с разными ID и bindings. При возможности использовать предоставленные реальные
манифесты/образы; недоступность обязательного образа отмечается prerequisite,
тестовый контейнер не выдаётся за приёмку реального приложения.
Проверить одну библиотеку на двух Docker-хостах: один логический instance,
два локальных Compose-запуска, разные `${SERVER_ID}` из inventory host IDs,
готовность обоих targets и один общий endpoint.

В QA использовать уже собранный
[тестовый образ подключений](../../docker/application-connection-probe/README.md)
как проверяемое приложение библиотеки. Его `/status` должен подтвердить
PostgreSQL, Redis, Sentinel и ClickHouse под УЗ экземпляра, получение секретов
через Vault Agent с AppRole, PKCS12 truststore/keystore и подключение к клиентскому
Kafka SSL listener без аутентификации. Для Kafka это проверка TLS и протокола,
не проверка ACL или прав на топики. На A4 проверять доставку секретов и PKCS12,
на A5 — соответствующие подключения, на A6 — публикацию `/status` через endpoint,
на A9 — полный standalone путь. Проверять образ по зафиксированному digest;
предыдущий [результат на RED OS](../../docker/application-connection-probe/qa-result.md)
подтверждает только ручной QA-запуск на node1, а не прохождение будущего Ansible/Core
или UI-сценария.

Проверить также structured Core snapshot/validate/plan/execution из A7 и общий
двухэтапный план с барьером из A8.
**Выход A:** ручной и structured Core запуск без Go/Installer, repeat changed=0, targeted failure/retry,
изоляция библиотеки/экземпляра, safe secrets и внешний endpoint. Проверки идут на
RED OS из текущих исходников по [QA procedure](../agent-procedures/qa.md).
Никакого Ansible/Python QA на Windows. Standalone PASS не означает UI PASS.

## B. Go backend

### B1. Подключение готового Core контракта через адаптер

Расширить существующий Go adapter/read model для результатов A7: libraries,
instances, findings, origins и secret requirements. Сохранить revision/runtime
binding и обработку структурированных ошибок; не вычислять effective values в Go.
**Выход:** backend предоставляет проекции Core без потери идентичности и без
дублирования доменных правил; target-free Verify вызывает проверенный Core путь.

### B2. Существующий guarded writer

Добавить ограниченные typed edits библиотеки/instance и overrides в текущий
Review/Save путь. Сохранить opaque data, atomic writes и revision checks.
Определить разрешённые package files и безопасный import/export/trust scope;
не создавать полноценный package editor ради базового добавления экземпляра.
**Выход:** Save без Execution Node, reopen/export/import без потери источников;
конкурирующая ревизия и небезопасные пути отклоняются существующими guards.

### B3. Approval/execution lifecycle и доставка runtime

Подключить готовое Core планирование A к существующим BuildDeploymentPlan/approval/Start,
credentials, events, cancellation и observations. Go не строит инфраструктурный DAG.
Go передаёт и исполняет общий двухэтапный план A8, не пересчитывая порядок и не
запуская библиотеки отдельным скрытым run. Approval покрывает оба этапа.
План показывает library preparation,
provider mutations и instance actions. Изменение source/vars/package/runtime
делает старое approval непригодным. Отмена не обещает rollback providers.
Подключить подготовленный в A runtime к existing locks/transfer/cache/rebind;
проверка и публикация — по [bundle procedure](../agent-procedures/runtime-bundle.md).
**Выход:** approved scope совпадает с dispatch, secret-safe results, partial
failure/cancel/retry, точные revision/digest; публикация не выполняется вручную.

### B4. Проверка Go backend integration

Проверить A-сценарий через production execution protocol, writer и observation.
Прямые harness checks вспомогательны и не закрывают реальную UI acceptance.
**Выход B:** frontend получает все нужные metadata/findings/results без доменных
вычислений; standalone остаётся работоспособным тем же путём. UI gate остаётся C.

## C. UI

### C1. Макет и соответствие действующим flow

Сопоставить «Сервисы», shared UI rules и новый [UI proposal](ui.md).
Подготовить конкретный макет «Приложения»: библиотека → экземпляры.
Отдельно показать ресурсы/общие секреты библиотеки, origin и одно поле instance ID.
**Выход:** согласованная структура и записанные расхождения с текущими mockups;
никакой преждевременной реализации альтернативного редактора.

### C2. Редактирование библиотек и экземпляров

Переиспользовать existing form controls, schema-driven settings, validation,
Review/Save и runtime-secret input. Добавить bindings/resources/accounts,
secret variable mappings, endpoint/backend settings и reset override.
Core проекции отображаются read-only; raw YAML не разбирается React.
**Выход:** реальный Save/reopen через Wails, один ввод ID, верное inheritance,
секреты не возвращаются в обычные модели UI.

### C3. Установка и наблюдение

Общая страница «Установка» показывает отдельные этапы «Инфраструктура» и
«Библиотеки приложений» в порядке Core. Второй ожидает успешного завершения
первого; причина блокировки/отмены видна без нового terminal state.
Внутри второго этапа показываются фазы библиотеки и экземпляров, review
provider changes, existing approval/Start, events и cancellation. После выполнения
отдельно показываются running, connection checks и verified endpoint.
**Выход:** отсутствует скрытый start path; устаревшие plans отклоняются;
блокировка library preparation понятна пользователю.

### C4. Сквозная реальная приёмка

На реальных React handlers/Wails bindings и Execution Node пройти создание
библиотеки/instance, изменение inherited settings, Save, fresh plan, approval,
Start, terminal/verify и повтор. Покрыть missing credential, provider failure,
Agent restart, непройденную endpoint проверку, изменение только одного instance.
**Выход C:** конкретные saved revisions/run IDs и safe evidence в журнале;
visual acceptance отдельно. Mocked tests/Go harness не заменяют этот gate.

## Как вести следующие подэтапы

- Перед началом выбрать один ограниченный подэтап и критерий выхода; не объединять
  несколько инфраструктурных переделок, writer и UI в один большой diff.
- Читать только соответствующие контракты/procedures из task index и scoped AGENTS.
- Следовать [стандартной процедуре ревью](../agent-procedures/review.md).
  Текущий FULL PLAN отчёт связан выше; прежние review раннего черновика не закрывают
  будущую реализацию. Соблюдать budget, BLOCK stop и owner approval;
  HIGH-RISK DIFF требует независимого FULL DIFF review.
- В коротком отчёте фиксировать результат, выполненные проверки, открытый gate и
  отклонение от плана. Не размножать status ledgers по документам.
- При изменении границы сначала обновить затронутый контракт и этот scope,
  затем продолжать реализацию только в разрешённых пределах.

## Вне начального объёма

Автоматическое multi-host планирование/переразмещение и HA/failover приложения,
Swarm/Kubernetes, универсальный Compose importer,
новый package marketplace, arbitrary hook scripting, автоматические миграции любой
БД, динамические credentials всех providers и межсервисный rollback engine.
Обязательные сценарии account provisioning, Vault shared secrets, backend overrides
и UI не исключаются ради упрощения: упрощается механизм, а не требование.
