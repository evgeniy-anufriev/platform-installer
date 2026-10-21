# СЗИ, этап 1: библиотека, универсальные скрипты и bootstrap Keycloak

Статус: одобренный технический план, реализация ведётся в отдельном worktree. Исходный FULL PLAN review дал `BLOCK` по SZI-P01–P03; targeted recheck закрыл P01/P03 и указал на холодный старт в P02. Владелец принял исправление P02: HTTPS и сертификат проверяются скриптом после readiness, без отдельной проверки Core до Apply. FULL DIFF review позднее отметил SZI-D04 по детализации операции restore в публичном плане; владелец 2026-10-21 отклонил добавление такой детализации только для `restore_on_create` и вывел общий показ подробных действий за пределы этапа. Исходный вердикт review сохранён отдельно и не переименован в APPROVE. Полная приёмка не выполнена. Текущий статус проекта определяется только `CURRENT_STATE.md`. Этот документ описывает первый этап СЗИ; создание групп СДКУ, клиентов интегрируемых приложений и их маршрутов остаётся следующим этапом.

## Уточнение границ этапа владельцем, 2026-10-21

На этапе 1 развёртывается библиотека СЗИ только с выбранным приложением `keycloak`
на узлах 102/103. Проверяются импорт чистой БД без admin, пакетные скрипты,
bootstrap постоянного admin из runtime secret и штатный Apply/Verify.
`grant-access`, `grant-access-front`, `grant-access-audit` и `nginx` остаются
в составе доступных пакетов как необязательные slots, но не выбираются для
этого развёртывания. Их запуск, служебный клиент grant-access и интеграции
относятся к этапу 2. Redis credentials для grant-access не нужны: это legacy.
Это уточнение заменяет прежний объём установки пяти приложений на этапе 1.
## 1. Цель и исходные факты

Один обычный `APPLICATION_LIBRARIES_APPLY` устанавливает библиотеку `szi`, восстанавливает исходную БД Keycloak **только при её создании**, создаёт постоянного `admin` с паролем из runtime secret и завершает штатные readiness/endpoint проверки. Повторный Apply не восстанавливает БД, не заменяет пароль и возвращает `changed=0`, если желаемое состояние уже достигнуто. Core и Go не содержат условия по имени `szi`.

В [рабочем драфте пакетов](../../../examples/szi/README.md) описаны пять обычных приложений: `keycloak`, `grant-access`, `grant-access-front`, `grant-access-audit`, `nginx`; nginx принадлежит СЗИ. Для единственного экземпляра СЗИ в проекте instance ID каждого приложения равен имени приложения. `config_directories`, `config_archives`, обновление каталога и digest архива уже реализованы; повторять их контракт в этом этапе не требуется. Пакетные файлы и Compose пока не проходили полный Core Apply.

Исходный PostgreSQL custom dump `keycloak_clean_no_admin_2026-10-21.dump` (210681 байт, SHA-256 `5928ad8c51aa50e7528533e78e0b729eba915e23a9b96cf313384083c4f1eae8`) проверен восстановлением в отдельную БД. В нём нет пользователей, credentials и пользовательских назначений ролей; сохранены шесть встроенных клиентов, три группы, realm-роли `admin` и `default-roles-master`. Ручной стендовый прогон на отдельной копии подтвердил цепочку `bootstrap-admin service` → production Keycloak → создание постоянного `admin` через Admin API → удаление временного клиента. Это не доказательство работы штатного Apply.

## 2. Граница изменений

| Слой | Изменение |
| --- | --- |
| Installer config / план | Приоритеты типов библиотек рядом с `serviceExecutionPriorities` в `config/application.yml`; Installer выводит порядок выбранных library IDs и передаёт его Core, Core проверяет членство и фиксирует его в плане. |
| Portable contract / Core | Типизированный `restore_on_create` только у управляемого `postgresql.database`; `scripts` в метаданных library/application package; валидация ссылок, фаз, выбора target и secret refs; предсказуемые jobs и план. |
| Ansible PostgreSQL provider | Безопасное первичное создание и восстановление БД на выбранном primary; повторное обнаружение без восстановления; блокировка частичного/чужого состояния. |
| Ansible application runtime | Общий runner скриптов; один общий provider stage, затем в заданном порядке библиотеки: Apply всех размещений, readiness/endpoint и read-only проверка текущей библиотеки. |
| Go adapter / package import | Перенос новых типизированных полей и файлов через существующие package/plan/runtime механизмы без собственной инфраструктурной семантики. Отображение ошибок и secret requirements в существующем потоке. |
| Пакеты СЗИ | Окончательные Compose/defaults, архив тем, плагины, Keycloak dump и два объявленных bootstrap-скрипта. |
| UI | Новых экранов и специальных элементов «СЗИ» нет; используются существующие библиотечные bindings, runtime secrets, Verify и план. |

Нет нового типа операции верхнего уровня, нового состояния в SQLite, отдельного bootstrap-orchestrator или второго источника desired state. Базовый дамп не является `config_archive` контейнера и не копируется в его filesystem. Смена пароля уже существующего `admin` вне первичного bootstrap и автоматическая очистка/пересоздание БД в scope не входят.

## 3. Подготовка библиотеки СЗИ

1. Завершить пять пакетов по актуальным образам и манифестам. В `application.yml` оставить только реально доставляемые файлы; девять JAR — каталог `config_directories`, полная тема — `config_archives`, конфиги и Compose — обычные шаблоны. Проверить digest/состав темы и совместимость с Keycloak 26.4. Образ nginx должен поступить из разрешённого registry или проверенного offline bundle; при отсутствии совместимого образа план/Apply блокируется.
2. Закрыть отмеченные в драфте конфигурационные вопросы до target Apply: Vault Agent и `secret_bindings` для Keycloak/grant-access/audit, PKI и Java truststore, адреса/порты и discovery кластера, `KC_CACHE_STACK` против `cache-ispn.xml`, лимит памяти против `-Xmx8g`, исходные ручные адреса и nginx-конфиг. Значения endpoint и identity выводятся из resolved projection, не из сервера 107. Секреты не попадают в defaults, Compose environment или пакет.
3. Объявить в deployment СЗИ существующий managed PostgreSQL resource `keycloak` и его binding, с проверенным `restore_on_create`. PostgreSQL provider выполняется раньше приложений. Стандартные provisioning, Compose validation, image delivery, readiness и endpoint hooks остаются общими.
4. Добавить в **Installer** [`config/application.yml`](../../../config/application.yml) `libraryExecutionPriorities` рядом с существующим `serviceExecutionPriorities`. Это конфигурация приложения Installer, а не `group_vars` и не portable desired state. Приоритет назначается имени library package без версии; меньшее число исполняется раньше:

   ```yaml
   libraryExecutionPriorities:
     - {libraryName: szi, priority: 0}
     - {libraryName: sdku, priority: 1}
     - {libraryName: cspa, priority: 1}
   ```

   При равенстве — порядок записей в конфиге, затем library deployment ID. Как в действующем инфраструктурном механизме, выбранные library IDs передаются в точном порядке в `BuildDeploymentPlan`; Core не читает `config/application.yml` и не вычисляет приоритеты. Он проверяет полное членство без повторов и сохраняет порядок в fingerprint/manifest. Для самостоятельного Ansible Core порядок подаётся явным обычным входным параметром; отсутствие Go не блокирует Core. Отсутствующая приоритетная запись для выбранного имени библиотеки — ошибка подготовки плана, не тихая сортировка. Версию `config/application.yml` обновить с явным сообщением об upgrade, сохранив операторские настройки. Пакетный `application.yml` каждого приложения — другой файл и не управляет порядком библиотек.
5. Все provider resources, accounts, Vault secrets, ACL и другие подготовительные действия выбранных библиотек выполняются одним общим stage **до** контейнеров. После него runtime Apply/проверка идут по порядку library IDs из плана: полностью запустить и проверить СЗИ до начала запуска контейнеров СДКУ. Это не запрещает раннее создание ресурсов СДКУ; владелец сознательно ограничил гарантию порядком запуска. Ошибка provider stage останавливает запуск всех библиотек, ошибка запуска/проверки СЗИ останавливает запуск СДКУ.

## 4. PostgreSQL `restore_on_create`

Предлагаемое поле ресурсного контракта (точное имя вложенного поля закрепить в схеме, не вводя параллельный DTO):

```yaml
resources:
  keycloak-db:
    kind: postgresql.database
    binding: database
    mode: managed
    parameters:
      name: keycloak
      restore_on_create:
        source: assets/db/keycloak_clean_no_admin.dump
        sha256: 5928ad8c51aa50e7528533e78e0b729eba915e23a9b96cf313384083c4f1eae8
        format: pg_custom
```

`source` — файл allowlist пакета библиотеки, а не путь с рабочей станции или на target; байты входят в package/project digest. Использовать существующую доставку проверенных package files и protected runtime staging. Перед включением дампа в распространяемый пакет отдельно доказать отсутствие секретов и закрытых персональных данных в **полном** содержимом, включая client attributes; ноль пользователей сам по себе этого не доказывает. Если дамп содержит такие значения, очистить его в изолированной копии и повторно проверить/зафиксировать новый digest; не обходить правило отсутствия plaintext secrets в проекте.

Валидация запрещает `restore_on_create` у `mode: existing`, других resource kinds, неизвестного format, неразрешённого source или несовпадающего digest. Target-free Validate/Plan проверяет схему, пакетный allowlist, размер и digest без контакта с PostgreSQL. Декларация восстановления входит в semantic fingerprint общего действия Apply; содержимое дампа в план не попадает. Отдельная детализация `restore_on_create` в публичном плане не вводится: решение владельца от 2026-10-21 оставляет подробный показ действий всех типов за пределами этого этапа. Перед изменением БД provider подтверждает primary, владение resource и точный digest доставленного файла.

В PostgreSQL provider восстановление встраивается между созданием owner role/пустой БД и существующими шагами per-database ресурсов/аккаунтов. Для restore-resource нельзя сначала выполнить нынешний generic `resources.sql.j2`, который создаёт и маркирует БД как готовую: этот участок нужно узко разделить, сохранив старый путь без restore без изменений. При отсутствии БД provider создаёт её под ожидаемым owner, восстанавливает через `pg_restore --exit-on-error --no-owner --no-acl` с ограниченным runtime identity, проверяет ожидаемую структуру baseline и только после успеха записывает существующий ownership marker и допускает account grants/запуск Keycloak. При существующей БД с совпадающим ownership marker восстановление не выполняется. Чужая БД, другой marker или созданная, но не помеченная после прерванного восстановления БД — `BLOCK` с диагностикой; автоматических `DROP DATABASE`, очистки таблиц и повторного импорта нет. Нужна изолированная проверка пограничного окна между restore и записью marker.

Дамп загружается на фактический PostgreSQL primary, а не на Docker-хост; временная копия удаляется после операции. Ошибки и `pg_restore` output проходят редактирование/`no_log`, диагностике достаточно стабильного кода, этапа и digest. Существующая PostgreSQL ownership/connection-проверка сохраняется.

## 5. Общий контракт package scripts

`scripts` может быть объявлен в `library.yml` или `application.yml`; объявление входит в versioned package schema, allowlist и digest. Версия 1 ограничена фазами `before_start` и `after_ready`, режимами `each_target` (default) и `once`. Скрипт не является произвольным UI shell command: `source` указывает на исполняемый файл из того же пакета, а `argv` — упорядоченный массив литералов либо разрешённых несекретных resolved refs (`applicationId`, параметр, endpoint, connection). Неизвестный ref, secret ref в `argv`, дублированный `id`, пустой список подходящих targets или конфликт ID блокируют Validate/Plan.

```yaml
scripts:
  - id: bootstrap-admin
    source: assets/scripts/bootstrap-admin.sh
    phase: before_start
    execution: once
    argv: [--realm, master, --db-user, szi_keycloak,
           --project, {valueFrom: projectId}, --library, {valueFrom: libraryId},
           --instance, {valueFrom: applicationId}, --host, {valueFrom: targetHostId}]
    secretInputs:
      bootstrap_client_secret: {valueFrom: runtime_secret, ref: szi-bootstrap-client-secret}
      db_password: {valueFrom: runtime_secret, ref: keycloak-postgres-password}
  - id: create-admin
    source: assets/scripts/create-admin.sh
    phase: after_ready
    execution: once
    argv:
      - --realm
      - master
      - --keycloak-url
      - {valueFrom: placement_https, application: keycloak}
      - --project
      - {valueFrom: projectId}
      - --library
      - {valueFrom: libraryId}
      - --instance
      - {valueFrom: applicationId}
      - --host
      - {valueFrom: targetHostId}
    secretInputs:
      bootstrap_client_secret: {valueFrom: runtime_secret, ref: szi-bootstrap-client-secret}
      admin_password: {valueFrom: runtime_secret, ref: szi-admin-password}
```

Разрешённые runtime refs определяет Core из стандартных Ansible vars/projection; Go не вычисляет endpoint или параметры. `placement_https` — HTTPS URL выбранного размещения Keycloak: адрес `ansible_host` соответствующего target и порт из существующей реализации endpoint placement. Отдельное правило выбора порта в контракте скриптов не вводится. Это адрес до публикации nginx/HAProxy endpoint; скрипт выполняется на том же target. Существующий application preflight проверяет объявленное соответствие портов Compose и свободность нового published port; отдельной проверки сертификата или живого HTTPS до Apply нет. После readiness `create-admin` подключается к этому URL с обязательной проверкой CA и имени сервера, затем вызывает Admin API. Если `ansible_host` — IP, сертификату нужен этот IP в SAN; если имя — соответствующий DNS SAN. Несовпадение останавливает Apply, `-k` не допускается. Публичный endpoint проверяется позже обычным endpoint stage. Для этой проверки не добавляется специальная задача или правило Core; Core только предоставляет общий resolved ref `placement_https` в контракте скриптов.

`secretInputs` — имена и references, не значения. Их требования проходят через существующий lease/runtime-secret транспорт на Execution Node. Общий runner `platform.core.package_script` получает только путь allowlisted файла, рабочий каталог, учётную запись, массив argv и карту защищённых secret files. Он копирует секреты на target в mode-0600 transient files, передаёт скрипту только пути через `PLATFORM_SCRIPT_SECRET_<NAME>_FILE` и удаляет файлы после выполнения, в том числе при ошибке. Runner не получает Compose argv, имя контейнера, Docker environment или идентификаторы проекта/библиотеки/приложения как неявные переменные: необходимые несекретные данные задаются явными `argv` в package manifest. Docker и Keycloak принадлежат только двум скриптам пакета Keycloak. Runtime identity — выбранная учётная запись target job, без специального ограничения на Docker-хост. Исполнение — Ansible `command: argv`, без shell-интерполяции; timeout и terminate поведение задаются общим runner. На выходе один короткий машиночитаемый несекретный результат (`changed`, `status`); stdout/stderr скрипта не публикуются. Ошибка делает Apply failed.

`once` означает один детерминированно выбранный target из resolved eligible targets логического объявления и сохраняет этот выбор внутри данного плана; оба Keycloak-скрипта используют тот же target. `each_target` запускается для каждого выбранного target. Это выбор места выполнения, не дедупликация по процессу Ansible и не метка в SQLite. Скрипт сам проверяет фактическое конечное состояние, поэтому повторный Apply возвращает `changed=0`. Verify этого этапа не запускает мутационные scripts; действующий `APPLICATION_LIBRARIES_VERIFY` сохраняет контракт проверки контейнеров/endpoint, а результат bootstrap проверяется в Apply и отдельной приёмке. Для порядка экземпляров внутри библиотеки optional `slots.<name>.start_priority` (default 100) сортирует сначала по приоритету, затем по ID; у слота Keycloak приоритет 0, поэтому его `after_ready` завершается до запуска grant-access.

## 6. Порядок фаз Apply

Существующий `application-libraries-apply.yml` сначала материализует конфигурацию по хостам, затем активирует jobs по хостам; provider stage обслуживает все библиотеки до этого. Простое добавление `run_once` внутрь `activate_instance.yml` **не гарантирует**, что `before_start` завершится до запуска всех размещений Keycloak. Общий Ansible coordinator сохраняет единый preflight/provider stage и затем проходит библиотеки по переданному из плана порядку library IDs, а внутри каждой — логические экземпляры:

1. Разрешить и проверить все package files, script refs, secrets, provider jobs и placements; выполнить общий preflight без мутаций.
2. Выполнить общие resources **всех выбранных библиотек**, включая restore Keycloak, затем штатные accounts/Vault/PKI/ACL provider hooks всех библиотек. Никакой контейнер ещё не запущен.
3. Материализовать Compose/конфиги и проверить Compose на всех placements экземпляра; доставить образ на все его targets.
4. Выполнить `before_start` по объявленному `execution`; для Keycloak все его placements ещё остановлены. При частично работающем Keycloak на повторном Apply bootstrap-скрипт должен распознать уже завершённое состояние и не выполнять CLI; незавершённый bootstrap при работающем узле блокируется.
5. Запустить все placements этого экземпляра штатным Compose и выполнить существующий readiness/healthcheck для каждого. При ошибке дальнейшие экземпляры не запускаются.
6. После readiness выполнить `after_ready`. Скрипт `create-admin` сам проверяет живое HTTPS-соединение по адресу выбранного Keycloak endpoint placement, включая CA и имя сертификата, прежде чем запрашивать токен или менять пользователя. Проверить несекретный результат скрипта и перейти к следующему экземпляру. `create-admin` завершается до приложений СЗИ, которым требуется Keycloak.
7. После всех экземпляров библиотеки опубликовать и проверить только её endpoint sources существующим общим hook, затем выполнить read-only container/endpoint Verify её placements. Только после успеха начать runtime Apply следующей библиотеки. По завершении всех библиотек существующий отдельный `APPLICATION_LIBRARIES_VERIFY` остаётся итоговой read-only проверкой; новый тип операции верхнего уровня не нужен.

Здесь меняется только общий порядок вокруг существующих `apply_library`, `image_delivery`, `activate_instance` и `verify`. Следует сохранить их ownership labels, digest, `--pull never`, rootless daemon, Vault и endpoint guards. Прежний порядок для пакетов без скриптов должен остаться эквивалентным по результату; при необходимости допускается единая фазная группировка jobs, а не специальный SZI playbook.

## 7. Bootstrap Keycloak и восстановление после обрыва

`bootstrap-admin` проверяет, что постоянный `admin` уже существует или что БД находится в разрешённом начальном состоянии. До скрипта общий runtime доставляет и проверяет точный образ Keycloak на выбранном target, материализует Compose и все конфиги. Пакетный скрипт, запущенный общим runner, использует rootless daemon той же runtime identity и `docker compose run --rm --no-deps` с переопределённым entrypoint: временный контейнер из **того же уже проверенного образа** выполняет `/usr/lib/keycloak/bin/kc.sh bootstrap-admin service`, без pull, зависимых контейнеров и публикации портов. Он получает те же DB options и необходимые read-only mounts (CA, providers, themes), что штатный Keycloak. Защищённые runtime-файлы DB credential и заранее заданного bootstrap client secret монтируются только во временный контейнер; короткий wrapper внутри него читает их и передаёт CLI через environment **процесса**, а не Compose environment или Docker argv/metadata. Keycloak поддерживает `--client-secret:env`; точный wrapper и совместимость образа/entrypoint проверяются на стенде. После CLI временный контейнер и secret mounts удаляются; при обрыве runner обнаруживает и очищает только контейнер с точной bootstrap ownership identity. Все постоянные Keycloak placements в этот момент остановлены. Повторный вызов не меняет secret и не создаёт второй client. Если обнаружено несовместимое или неоднозначное состояние, возвращает стабильную ошибку, а не исправляет БД вручную.

После production startup `create-admin` сначала проверяет живой HTTPS и сертификат локального размещения. Только после этой проверки он получает временный service token, вызывает Admin API для создания включённого постоянного `admin`, назначает realm-роли `admin` и `default-roles-master`, вызывает `reset-password` с runtime password и `temporary: false`. Он проверяет новый login и административный API, отсутствие `is_temporary_admin`, удаляет временный service client и повторно проверяет его отсутствие. Секрет client и пароль уже существуют в runtime custody до запуска обеих фаз и не регенерируются после обрыва. Токен не сохраняется между запусками: его получают заново из того же временного client, если тот ещё присутствует.

Если `admin` уже постоянный и его пароль из текущего runtime secret работает, а временного клиента нет, оба скрипта сообщают `changed=0`. Если `admin` создан, но следующий шаг оборвался, `create-admin` сверяет роли, пароль и временный client, завершает недостающие действия только при подтверждённой принадлежности bootstrap-состояния. Неизвестный `admin`, неверный пароль при отсутствии временного client, иной временный client или запущенные узлы до первого offline bootstrap — явный `BLOCK` с восстановлением оператором; менять чужую учётную запись вслепую нельзя. `bootstrap-admin user` не используется: стендовый прогон показал признак `is_temporary_admin`.

Новый дамп после установки постоянного пароля не создаётся. Базовый дамп остаётся без `admin`; каждое новое развёртывание получает пароль только из своего runtime secret.

Уточнение по стенду 2026-10-21: временный CLI bootstrap использует HTTP management без загрузки HTTPS keystore и без публикации портов; обычный `start-dev` не создаёт bootstrap-аккаунт в уже существующем `master`. Постоянный Keycloak использует штатный каталог PKI и PKCS#12 с паролем из Vault Agent. CA для Admin CLI читается внутри контейнера из `/opt/application/pki/ca-chain.pem`; хостовый Docker account не должен читать приватные файлы UID контейнера. Один CA truststore настраивается для обоих временных CLI config. Импортированный user profile не сохраняет неописанную bootstrap-метку: существующий admin с рабочим runtime-паролем может завершить очистку временного клиента без этой метки и без смены пароля. Если пароль не работает и метки нет, автоматическое продолжение блокируется; новый marker store не вводится.

## 8. Реализация по шагам и проверки

1. **Installer config, контракты и target-free Core.** Расширить `config/application.yml`/`internal/appconfig` приоритетами библиотек по существующей модели сервисов, вывести порядок из выбранных deployment IDs и передать его в план. Расширить versioned runtime/schema contract, package allowlist/resolve, snapshots, план и secret requirements. Добавить положительные и отрицательные schema/target-free тесты: приоритеты/равенство/неизвестное имя/неполное членство порядка, неверный source/digest, secret в argv, unsupported phase/mode, два script ID, ноль targets, restore у existing/чужого provider, пакет без скриптов. Обновить `docs/project-contract.md`, `docs/ansible-core.md`, архитектурное решение и roadmap при принятии границы.
2. **PostgreSQL provider.** Узко добавить create-and-restore путь до accounts; сохранить старый путь, marker и preflight для ресурсов без restore. На RED OS проверить fresh/unchanged repeat, partial restore, unmarked/foreign DB, wrong digest, standby/primary, account grants после успешного restore и отсутствие потери данных. Использовать отдельные тестовые БД; рабочую `keycloak` не пересоздавать.
3. **Ansible script runner и фазирование.** Доставка по digest, безопасный target selection, secret custody, direct argv execution, ограниченный результат, timeout/cancel и failed propagation. Общий provider stage оставить до запуска, затем обработать runtime Apply → endpoint → read-only Verify каждой библиотеки по порядку из плана. Проверить точное/дублированное/пропущенное членство списка, `szi,sdku` и обратный порядок, `once`/`each_target`, несколько hosts, phase ordering, failure до запуска, failure после readiness, repeat `changed=0` и отсутствие секретов в логах/результатах. Для `create-admin` проверить отказ при неверном CA/SAN после readiness без добавления отдельного pre-Apply TLS-probe в Core. Зафиксировать, что ресурсы СДКУ могут создаваться до запуска СЗИ, но его контейнеры не стартуют при отказе СЗИ.
4. **Пакеты СЗИ.** После проверки содержимого дампа добавить typed resource и оба скрипта в пакет; завершить перечисленные в разделе 3 конфиги, image closure и Vault/PKI bindings. Проверить package/schema/digest, Jinja/Compose renders и негативные cases без подстановки ручных адресов.
5. **Go и реальный поток.** Убедиться, что import/export, revision, plan transport, runtime secret requirements и ошибки проходят через существующий adapter без второго resolver. Выполнить соответствующие Go checks, затем реальный React/Wails Save → fresh Plan → approval → Start → terminal result для затронутого потока; direct harness и моки являются дополнительными проверками.
6. **Изолированная приёмка.** На разрешённом RED OS стенде из текущего дерева: отдельная PostgreSQL БД, полный library Apply, production Keycloak с темами/плагинами, HTTPS/API, все пять контейнеров и endpoint; повторный Apply без восстановления/смены пароля; прерывание после restore, после `before_start`, после создания `admin`, после удаления временного client. Проверить штатный Verify, отсутствие plaintext secrets и точное сохранение чужих БД/клиентов. Записать plan/revision/run IDs, terminal evidence и cleanup. До этого пакетный Apply СЗИ не считается принятым.

## 9. Решения перед началом реализации

- Подтвердить проверкой полного дампа возможность его размещения в library package без нарушения secret boundary. При обнаружении секрета сначала готовится новый очищенный baseline и его digest; текущий SHA нельзя молча объявлять допустимым.
- Уточнить окончательные package values для Vault Agent, PKI, Keycloak cache/memory и nginx image/config; открытые вопросы перечислены в драфте. Отсутствующий image/archive или runtime secret блокирует план/Apply.
- Проверить protected-file transport для secretInputs, временный Compose CLI-контейнер и способ распознавания принадлежности частично созданного `admin`. Это часть review contract, а не решение по имени библиотеки в Core.

Контракт restore и scripts, secret boundary и изменение порядка execution делают реализацию высокорисковой для DIFF review. Исходный FULL PLAN review и TARGETED_RECHECK сохранены отдельно. P01/P03 закрыты targeted recheck; P02 исправлен решением владельца после него. FULL DIFF review вынес `BLOCK` по SZI-D04; владелец отклонил это требование как выход за согласованный этап. Исторический вердикт review остаётся `BLOCK`, техническая коррекция D04 не выполняется и точечный recheck по нему не требуется.
