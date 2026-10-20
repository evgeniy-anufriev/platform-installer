# Автоматическая подготовка метаданных образов приложений

Дата: 2026-10-20. Этап: APPLICATION-IMAGE-METADATA-01. Проект технического
плана для утверждения владельцем. Запрос разрешает подготовку плана;
реализация Core, сетевое получение артефактов, публикация bundle и запуск
приложений этим документом не разрешены. Текущий статус проекта определяется
только [CURRENT_STATE](../../../CURRENT_STATE.md).

## 1. Результат для пользователя

В настройках образа пользователь задаёт только `image` в defaults приложения или в существующем
переопределении экземпляра. Он не вводит `imageId`, manifest digest, SHA архива,
размер, платформу или `localReference`. Исходный `image` остаётся в Compose;
фактическая установка и Verify проверяют точную идентичность образа.
По уточнению владельца экземпляр библиотеки также может выбирать registry и
задавать его логин/пароль через runtime-secret inputs; значения не сохраняются
в desired state. Эта настройка общая для приложений данной библиотеки.

Defaults пакета, фрагмент `roles/application_data-manager/defaults/main.yml`:

```yaml
platform_application_definition:
  name: data-manager
  version: 1.0.0
  defaults:
    image: registry.example/data-manager:1.5.0
    # Остальные defaults пакета остаются без изменений.
```

Переопределение в существующем `inventory/group_vars/all/platform-installer.yml`:

```yaml
platform_desired_state:
  applicationLibraryDeployments:
    sdku-main:
      applications:
        data-manager:
          overrides:
            image: registry.example/data-manager:1.6.0
```

Это фрагмент существующего desired state, а не замена всего документа.
Reset удаляет только `overrides.image`. Обычные Ansible defaults/overrides,
включая уже поддержанные host overrides, сохраняют существующий порядок.
Новые `image_artifact`, `image_artifacts`, пользовательский `reference` или
отдельный `images.lock` не вводятся.

После Save построение плана автоматически подготавливает недостающие
метаданные. Новый ручной шаг или кнопка в UI не требуются. Create Plan остаётся
ограниченным синхронным вызовом с общей busy-индикацией подготовки. Сетевой
шаг никогда не запускается из Save.

## 2. Текущее устройство и точки изменения

| Область | Текущее поведение | Необходимое изменение |
| --- | --- | --- |
| Defaults и редактор | `defaults.image`, `applications.<slot>.overrides.image`, override/reset уже существуют | Сохранить shape и обработчики |
| Общий lock | `platform_artifact_lock.x-container-images.images[image]` содержит техническое описание | Для новых поставок получать описание автоматически; сохранить legacy-чтение |
| Snapshot | `project_snapshot.py` вызывает `resolve_image_lock` и передаёт private `application_image_lock` | Передавать проверенные производные метаданные текущей попытки |
| План | `application_plan.py` ищет запись по имени образа; identity входит в execution model | Использовать запись конкретного placement/platform и включать её в fingerprint |
| Standalone | `prepare_application_runtime.py` и `application_runtime.prepare_runtime` повторно читают общий lock | Потреблять ту же выбранную identity, что и план |
| Bundle builder | `build_execution_runtime_bundle.py:components` уже считает SHA и размер каждого файла | Автоматически связать образы с существующими components |
| Bundle consumer | `internal/executionbundle/manifest.go` содержит components и service artifactSources | Добавить проверяемый необязательный индекс container images |
| Машинный протокол | `BuildDeploymentPlan` запускает controller-only playbook | Отдельная подготовка до вызова, без сети внутри planner |

Применимые контракты: [portable project](../../project-contract.md),
[Core](../../ansible-core.md), [execution planning](../../contracts/execution-planning-and-events.md),
[A2 runtime](milestones/a2/a2-technical-plan.md),
[review](../../agent-procedures/review.md),
[QA](../../agent-procedures/qa.md),
[runtime bundle](../../agent-procedures/runtime-bundle.md).

## 3. Владение данными

| Данные | Владелец и место | Срок действия |
| --- | --- | --- |
| Желаемый образ | Defaults приложения / существующие Ansible overrides | До изменения проекта или пакета |
| Registry и ссылки на его username/password inputs | `registry_credentials` экземпляра библиотеки в существующем group_vars | До изменения проекта |
| Разрешённые registry, trust и источник credentials | Существующая политика узла и runtime identity | По существующим правилам |
| Архив образа | Неизменяемый runtime bundle | Версия поставки |
| SHA и размер архива | Существующая запись `components` manifest bundle | Версия поставки |
| Связь image/platform с архивом и imageId | Автоматически построенный индекс в том же manifest | Версия поставки |
| Полученные registry manifest/config и факты платформы | Private runtime staging текущей подготовки | Текущая попытка планирования |
| Выбранные imageId/platform/registry digest и допустимый fallback | ExecutionManifest и semantic fingerprint плана | Одобренный план |
| Реально загруженный imageId и контейнер | Наблюдения Apply/Verify | Конкретное выполнение |
| Пароли, tokens, auth config contents | Только существующий runtime credential mechanism | Существующий lease/identity lifecycle |

Go организует staging, отмену, жизненный цикл попытки и хранение плана.
Core/Ansible нормализует ссылки, выбирает метаданные и источник, проверяет
платформу и эквивалентность fallback. React отображает значения, стадии и
структурированные findings. Go/React не реализуют эти инфраструктурные правила.

Производные данные не записываются в `group_vars`, defaults, SQLite desired
state или новый постоянный registry cache. Несколько планов одной saved revision
могут получить разные digest изменяемого тега; каждый требует своего approval.

## 4. Автоматический индекс в manifest bundle

Добавить необязательное поле `containerImages` в существующий manifest.
Пример ниже описывает предлагаемую форму; значения digest условные.

```yaml
containerImages:
  - reference: registry.example/data-manager:1.5.0
    platform:
      os: linux
      architecture: amd64
    imageId: sha256:<config-digest>
    archiveRef: runtime/artifacts/applications/data-manager-1.5.0.tar
```

`archiveRef` ссылается на единственную запись существующего `components`.
Индекс не повторяет её `sha256`/`size` и не содержит `bundleDigest`.
При сборке компоненты и индекс формируются раньше окончательного manifest;
digest bundle вычисляется по существующим правилам. Цикла package → bundle →
package не появляется.

`reference` здесь является ключом соответствия для файла поставки, а не вторым
пользовательским полем рядом с `defaults.image`. Manifest может обслуживать
несколько приложений и версий, поэтому должен уметь отвечать на запрос по имени.

Ключ уникальности: нормализованные reference + OS + architecture + variant.
Точные дубликаты схлопываются при сборке; противоречащие imageId/archiveRef для
одного ключа блокируют сборку. Несколько явно объявленных имён могут ссылаться
на один образ/архив. Нельзя выбирать «первый похожий файл» по basename, имени
приложения или совпадению только тега. При переносе на другой registry alias
требуется явное соответствие при сборке, а не поиск по одинаковому suffix.

Нормализация ссылок принадлежит Core. Нужно явно покрыть host:port, tags,
digest references и Docker Hub short names; не допустить ошибочного разбиения
host:port как image tag. Платформа образа использует linux/amd64 или linux/arm64;
это отличается от RED OS version и x86_64/aarch64 в совместимости runtime bundle.

Для `image@sha256:…` config из Docker-save не доказывает исходный registry
manifest/index digest. Явный alias также не является таким доказательством.
Принимать offline digest reference можно только при проверяемой цепочке
исходный manifest/index → platform manifest → config/imageId. Если входы
существующего поддержанного формата не позволяют проверить эту цепочку,
сборка такой записи блокируется. Не добавлять acquisition или новый importer
ради её получения. Уже подтверждённая legacy identity либо registry preparation
по @digest может использовать архив с тем же проверенным imageId/platform как
fallback; одного совпадения имени недостаточно.

Расширение manifest является объявленной capability нового runtime. Старые
bundle без индекса остаются читаемыми. Старый consumer не считается поддерживающим
автоматические image metadata только потому, что его YAML parser игнорирует
неизвестное поле. Проверка capability предшествует использованию нового режима.

## 5. Сборка индекса из локального архива

Расширить существующий bundle builder, сохранив его основной CLI.
Добавить повторяемое указание пары image/reference и пути к существующему архиву
во входном runtime-каталоге. Рабочее имя аргумента: `--application-image`.
Окончательный синтаксис закрепить тестом CLI в первом шаге реализации.
Например, два отдельных аргумента одной опции: image reference и relative archive
path. Пользователь сообщает соответствие имени и файла, но не его checksum.

Последовательность:

1. Проверить принадлежность архива approved runtime input; разрешены только
   обычные файлы без symlink/path traversal. Не искать Desktop/Downloads.
2. Прочитать поддержанный Docker-save формат без распаковки. Проверить manifest,
   выбранную config-запись, platform и принадлежность записи объявленному образу.
   Для alias, отсутствующего в RepoTags, требуется явное отображение на одну
   конкретную запись; неоднозначность блокируется.
3. Вычислить imageId по байтам config; проверить согласованность config identity,
   объявленных layers и состава архива. Не подменять imageId SHA всего tar.
4. Использовать существующий потоковый расчёт SHA/size components. Не держать
   архив или слои целиком в RAM, не выполнять `docker load` и не запускать контейнер.
5. Внести индекс в итоговый manifest; проверить, что archiveRef существует в
   components и объявленная identity получена именно из включаемых байтов.
6. Проверить неизменность входных файлов при сборке; при конкурентном изменении
   отклонить результат. Не публиковать частично сформированный bundle.

Начальный формат — явно поддержанный Docker-save tar. OCI layouts, экспорт
root filesystem через `docker export`, произвольные zip и общий import framework
не входят в scope. Необязательные форматы не угадываются по расширению.
Manifest/config имеют ограниченный размер; duplicate tar members, небезопасные
ссылки, отсутствующие layers и чрезмерное число записей дают безопасный отказ.

Отдельная команда приобретения образа из сети этим шагом не добавляется.
DEV download разрешается только отдельным запросом и существующим acquisition
workflow. PROD и QA не скачивают отсутствующий архив автоматически.

## 6. Подготовка метаданных перед планированием

Добавить фиксированную Core-операцию `PrepareApplicationImages` и соответствующий
Ansible entrypoint. Это read-only подготовка инфраструктурных входов, не Apply.
Она выполняется только на выбранном Execution Node; при необходимости Ansible
делает ограниченное чтение фактов целевых узлов и registry. Новый daemon,
локальный Python на Windows или произвольный command bridge не нужны.

Вход: точная staged saved revision, runtimeRelease/bundleDigest, выбранный scope
плана и его placements. Core самостоятельно получает эффективные image и
node-scoped policy через существующее Ansible разрешение. UI/Go не присылают
доверенный список imageId, platform или approved registry.

Факты целевой платформы получаются ограниченным read-only Ansible discovery,
которое не требует работающего Docker и не устанавливает пакеты. Существующий
server information UI не является авторитетным inventory и не используется
как замена Core discovery. Unsupported/unknown architecture блокирует
подготовку соответствующего placement, без предположения о платформе workstation.

Результат записывается в private staging текущей попытки планирования. Он связан
с project identity/revision, runtime release, scope/order, effective image,
placement host и его платформой, эффективной node-scoped registry/trust policy.
Включает выбранные imageId, подтверждённые registry descriptors и допустимые
ссылки на fallback. Повторное использование другой попыткой не разрешается.

Registry discovery и выбор образа не создают контейнеры, accounts, каталоги
приложений, Docker tags, provider resources или package transactions. Разрешены
private файлы протокола на Execution Node и краткоживущая secret materialization
по существующим runtime identity правилам на выбранных целевых узлах. Чтение auth config и сетевые ответы
должны проходить существующие runtime identity и redaction правила.

## 7. Получение метаданных из registry

Для node-approved registry подготовка читает manifest по requested image,
выбирает точный platform manifest и получает его config. Layers на этой стадии
не скачиваются. Исходный mutable tag разрешается один раз на попытку; дальнейшие
запросы обращаются по полученному digest. Core проверяет digest по исходным
байтам ответа, не по повторно сериализованному JSON и не только по HTTP header.

Поддержать Docker schema2 manifest/list и OCI manifest/index. Из multi-platform
index выбрать единственную совместимую OS/architecture/variant запись; затем
проверить согласованность manifest/config/platform. Attestations и неизвестные
media types не трактовать как исполняемый image. Schema1 не поддерживать молча.
Index digest, platform manifest digest, config/imageId и archive checksum
остаются разными типизированными величинами.

Реализация: обычные Ansible задачи для orchestration, небольшой модуль Core
для ограниченного чтения registry metadata и проверки байтов/структуры.
Не добавлять Docker SDK, Skopeo, Buildx или обязательный Docker daemon на
Execution Node ради этой операции. Стандартные HTTP/SSL возможности установленного
Core runtime достаточны для ограниченного протокола. Общую registry-платформу,
универсальный downloader и обновление всей системы доверия не разрабатывать.

Запросы выполняются в сетевом и credential-контексте соответствующего узла;
проверка с Execution Node вместо узла не выдаётся за доказательство доступности
registry этому узлу. Использовать existing node trust и выбранный credential
source. Явный library runtime-secret имеет приоритет и не смешивается с
credentials другой библиотеки или глобальным Docker auth. Без явной настройки
сохраняется existing node credential source/anonymous поведение. Если Docker
account/config ещё не существует, library runtime inputs позволяют выполнить
metadata-запрос без создания account или Docker login. Для private registry
отсутствие требуемого runtime input — prerequisite BLOCK. Поддерживаемые legacy
auth форматы и credential helpers инвентаризировать в шаге 0; неподдерживаемый
способ даёт явный BLOCK, не anonymous downgrade и не silent offline fallback.

Проверять TLS, границы timeout/response size/redirects и read-only repository
scope token. Не пересылать credentials на другой origin; auth realm и разрешённые
redirect origins должны соответствовать существующей политике доверия.
Ошибки auth, TLS, timeout, malformed manifest и digest mismatch имеют разные
структурированные findings. Payload ответа, tokens, auth headers и URL userinfo
не попадают в логи. Секреты не входят в fingerprint или результат подготовки.

Основные правила registry протокола опираются на
[Distribution API](https://distribution.github.io/distribution/spec/api/),
а platform selection — на
[OCI image index](https://github.com/opencontainers/image-spec/blob/main/image-index.md).

### Runtime credentials экземпляра библиотеки

Уточнение владельца: выбрать registry в параметрах экземпляра библиотеки,
указать логин и пароль как runtime-secret и применять их на целевых узлах.
Расширить существующий library deployment необязательным `registry_credentials`.
Ключ — registry authority host[:port] без scheme, path, userinfo и wildcard.
Это назначение credentials, не новая registry allowlist или image catalog.

```yaml
platform_desired_state:
  applicationLibraryDeployments:
    sdku-main:
      registry_credentials:
        registry.example:
          username:
            source:
              kind: runtime_secret_ref
              ref: sdku-main-registry-username
          password:
            source:
              kind: runtime_secret_ref
              ref: sdku-main-registry-password
```

В YAML находятся только ссылки; ни username, ни password не записываются
как literal. Поле размещается на уровне library deployment рядом с bindings,
а не в произвольном slot или defaults приложения. Для нескольких registry
допустимы отдельные записи той же map; образ выбирает соответствующую запись
по exact normalized registry authority. Нельзя передавать пароль одного registry
другому registry, использовать suffix matching или считать credentials разрешением
обойти node-approved policy. Нормализация authority и назначение hosts — Core.

UI в параметрах экземпляра библиотеки показывает блок «Доступ к registry»:
выбор registry, runtime login/password inputs, статусы наличия значений и
существующие clear/re-enter действия. Список registry для подсказок получает
из Core-проекции effective images; UI не парсит Docker references. Ссылки сохраняются
через existing typed writer/Review/Save; ввод значений использует существующий
ApplicationSecretInputs/runtime-secret broker, отдельно от project Save.
Password скрыт; оба значения остаются только в runtime session. Reopen проекта
восстанавливает ссылки, но не раскрывает и не восстанавливает истёкшие значения.
Удаление назначения в проекте и очистка значения runtime session — разные действия.

Расширить существующие typed descriptors purposes для registry username/password.
Descriptor связывает libraryId, registry authority, sourceRef, selected hosts
и допустимую операцию. Значения не входят в descriptor/fingerprint. Deduplication
не объединяет разные libraries/auth scopes только по одному host/reference:
один registry может иметь разные credentials у разных экземпляров библиотеки.
Не применять общий auth config всей установки и не возвращать секретные значения
из read API; оба input имеют существующие limits runtime-secret values.

`BuildRuntimeSecretDescriptors` формирует registry input requirements target-free
из saved references до metadata preparation. Текущий `PutRuntimeSecretLease`
привязан к готовому planFingerprint/executionManifestDigest и сам по себе не
решает pre-plan authentication. Нужна versioned доработка того же lease-механизма
для ограниченного preparation scope; отдельный secret store/broker не вводится.
Preparation lease привязан к exact staged project/revision, runtime release,
Execution Node identity, preparation attempt, registry/library/hosts и descriptor
set fingerprint. Допустима только операция чтения registry metadata. Использовать
фиктивный planFingerprint или придавать такому lease право Apply/Start нельзя.

После получения authoritative плана существующий approval/Start путь выдаёт
execution lease для разрешённого pull, используя те же session inputs и refs.
Pre-plan lease не повышается автоматически до execution authority. Проверка
контейнера Verify не требует registry password, если не выполняет registry reads.
Expiry, изменение sourceRef/registry/library/hosts/revision или mismatch lease
блокируют доступ; renewal тех же runtime values не разрешает сменить frozen image.
Завершение/ошибка/timeout подготовки закрывают её lease; execution lifetime
сохраняет существующие TTL, active-run custody и cleanup правила.

Metadata requests выполняет Ansible-модуль на целевом узле с переданными runtime
username/password. Execution Node участвует в защищённой передаче runtime secrets,
но не нуждается в доступе или login в registry. Метаданные и значения не смешиваются
в одном публичном response. Секреты не передаются в command arguments, событиях,
project vars, manifest bundle, ENV приложения или диагностических ответах.

Для pull под selected Docker account создать private временный `DOCKER_CONFIG`
по существующим runtime-secret materialization правилам. Только этот pull/probe
использует auth для выбранного registry; не изменять `~/.docker/config.json`,
daemon configuration или credentials других библиотек. Не выполнять постоянный
`docker login` и не передавать password в argv. Auth config доступен только
runtime identity, с закрытыми правами и `no_log`; очистка в `always` и existing
recovery cleanup. После pull credentials не остаются в каталоге приложения.
Передача и materialization — часть existing execution secret protocol, а не
открытый произвольный Ansible variable bridge. Registry CA/TLS policy остаётся
node-owned и не отключается наличием password.

Если явно настроены runtime refs и значения отсутствуют, истекли или отвергнуты,
операция блокируется без перехода к другой учётной записи, anonymous запросу
или offline fallback ради сокрытия auth failure. Без `registry_credentials`
legacy auth на узле остаётся поддержанным. Для anonymous registry ничего нового
заполнять не требуется. Vault provisioning, запись registry secrets в Vault и
постоянная настройка Docker credentials этим уточнением не добавляются.

## 8. Порядок источников и согласованность fallback

Порядок остаётся node-scoped: совместимый образ из разрешённого registry,
затем совместимый immutable bundle, иначе BLOCKED. Registry отсутствующий
в approved policy не опрашивается; это не разрешение использовать другой
registry. Node policy не переносится в package defaults.

| Результат подготовки | Поведение |
| --- | --- |
| Разрешённый registry вернул совместимый образ | Фиксировать его platform manifest digest и imageId |
| Registry candidate отсутствует в policy либо подтверждено отсутствие совместимого образа | Использовать единственную подходящую запись verified bundle |
| Registry auth/TLS/transport/protocol/integrity error | BLOCK по существующему fail-closed правилу, без сокрытия ошибки fallback |
| Registry и bundle содержат одинаковый imageId/platform для requested image | Включить bundle как допустимый fallback |
| Один tag в registry и bundle указывает на разные imageId | Registry wins; старый bundle не включать как fallback этого плана |
| Нет совместимого источника | BLOCK с image и placement, без автоматического download |

Если identity фиксируется legacy lock, registry проверяется по уже зафиксированному
digest; изменение текущего tag не меняет legacy identity. В автоматическом режиме
новый план может разрешить tag заново. В обоих случаях Apply не разрешает mutable
tag повторно для выбора новой identity.

При недоступности выбранного registry после approval Apply может использовать
только предусмотренный планом эквивалентный fallback и только при исходах,
разрешённых существующим source resolver. Auth/TLS/transport ошибки не превращаются
в «образ отсутствует». Если эквивалентного fallback нет, выполнение останавливается.
Старый tar с тем же тегом не подставляется. Source probe непосредственно перед
доставкой сохраняется: подготовка не доказывает будущую доступность registry.

Образы разных архитектур разрешаются отдельно для каждого placement.
Для одинаковых requested image и платформы противоречащие imageId разных узлов
в одной попытке блокируются; разные imageId для разных платформ допустимы.
Индекс и модель не должны схлопывать amd64/arm64 в одну запись по одному tag.

## 9. Сохранение target-free Core

Пользовательский flow создания плана:

```text
Save exact project revision
  → stage project once
  → PrepareApplicationImages (bounded facts/registry reads)
  → BuildDeploymentPlan (target-free, consumes frozen preparation)
  → review plan and explicit approval
  → StartExecution bound to that plan
  → existing delivery / Compose / Verify
```

`BuildProjectSnapshot`, local Save, Project Verify и authoritative
`BuildDeploymentPlan` не получают сеть или discovery как побочный эффект.
Автоматизация находится в Go orchestration пользовательской команды Create Plan;
подготовка и авторитетный planner остаются разными Core operations.

Если нет application placements в выбранном scope, подготовка не выполняется.
`INFRASTRUCTURE_VERIFY_ONLY` и service-only планы не требуют image registry.
Режимы FULL_PROJECT / APPLICATION_LIBRARIES_ONLY, порядок библиотек и существующий
skipInfrastructureVerify не изменяют правила доверия к образам.

Project Verify проверяет структуру image, package/runtime compatibility и
доступные локальные metadata, но отсутствие ещё не полученной registry identity
не должно превращать обычный image override в некорректный desired state.
В этом случае возвращается отдельное readiness finding о необходимости подготовки;
PASS структурной проверки не означает готовности Apply. Противоречащий legacy lock
или повреждённый уже выбранный metadata contract по-прежнему даёт BLOCK.

Проверить всех consumers execution model, включая `BuildRuntimeSecretDescriptors`.
Получение secret requirements должно оставаться target-free и быть доступно до
сетевой подготовки; нельзя создать цикл «для registry нужен lease, для lease нужен
готовый image plan». Отделять извлечение secret requirements от допуска к исполнению,
не считать отсутствующие image metadata разрешением на запуск.

Standalone Ansible получает тот же порядок через документированный entrypoint:
resolve native desired → prepare images → target-free plan либо standalone runtime
с exact prepared authority. Прямые роли по-прежнему работают с документированными
переменными и legacy lock. Для offline-only использования достаточно bundle index
и поддержанной платформы; registry запрос не выполняется без registry candidate.

## 10. Связь подготовки с планом и исполнением

Подготовка получает только уже staged exact saved revision. Go не пересоздаёт
архив проекта между подготовкой и planner. Core повторно проверяет привязки;
изменение проекта, runtime, scope/order, placements или policy требует новой попытки.
Внешнее изменение файла проекта не может сохранить старую готовность плана.

Машинный ответ подготовки содержит bounded typed handle и digest результата.
Planner принимает handle только своей попытки; путь файла определяет backend/Core,
произвольный путь из UI или project vars не разрешён. Файл без завершённого статуса,
с несовпадающим digest, symlink или неверной привязкой отклоняется.

Выбранная authority включается в private ExecutionManifest и semantic fingerprint,
включая requested image, imageId/platform, pinned registry descriptors и fallback
component/bundle identity. При Start/standalone runtime нельзя заново собирать её
из текущего tag, изменившегося registry или случайного локального Docker image.
Текущая runtime-проверка `application_execution_model` должна использовать frozen
authority, а не требовать заново заполненный `platform_artifact_lock`.

Go PlanStore сохраняет существующий lifecycle и opaque Core plan. Новый cache,
таблица SQLite, долговременный lease метаданных или API редактирования digest
не вводятся. Private evidence живёт в существующем plan staging/journal;
отмена и ошибки удаляют только принадлежащую попытке незавершённую область.
Сформированные планы следуют существующей retention и TTL.

Существующий Create Plan остаётся синхронным и ограниченным context/deadline.
Отмена здесь означает отмену context, deadline или завершение приложения.
Не вводятся отдельные planning job, API отмены, polling или новые кнопки.
Execution Cancel продолжает принимать только execution runId. Не увеличивать
существующий общий timeout молча; подготовка и planner используют общий бюджет,
deduplication одинаковых запросов и ограниченные сетевые ожидания. Тimestamps
discovery и секретные значения не включаются в semantic identity.

## 11. Совместимость со старыми проектами

1. Читать legacy `platform_artifact_lock.x-container-images` и compatibility
   `project.yml.artifactLock` как раньше, включая правило их равенства.
2. Если для effective image есть валидная legacy запись, она фиксирует identity.
   Текущий tag из registry не заменяет её новым образом.
3. Совпадающая запись bundle может дополнить такую identity только эквивалентным
   источником. Конфликтующую запись для одного image/platform не выбирать молча.
4. Если legacy image entry отсутствует, использовать автоматический путь;
   отсутствие entries для нового override само по себе не ошибка old-lock формы.
5. Не удалять и не переписывать старые locks автоматически. Не выполнять миграцию
   пользовательских group_vars, пакетов или рабочего проекта при открытии/Save.
6. Новый runtime поддерживает старые bundle/locks. Runtime без новой capability
   поддерживает прежний путь и явно отклоняет запрос автоматической подготовки;
   Go не подменяет его локальным вычислением или непроверенным запуском.

В новых examples image metadata из `group_vars` удаляются только после готовности
автоматического пути. Общий artifact lock с bundle digest, catalog binding и
другие service artifacts не удаляются. Defaults приложения остаются только
источником image и собственных настроек приложения.

## 12. Контракты и исходные файлы

| Слой | Основные точки |
| --- | --- |
| Bundle builder | `ansible-core/tools/build_execution_runtime_bundle.py`; существующие tests builder |
| Bundle reader | `internal/executionbundle/manifest.go`, `component.go`, соответствующие tests |
| Canonical image schema | `contracts/artifact-source/v1alpha2/image-lock.schema.json` и общие definitions следующей совместимой версии |
| Native resolve | `roles/resolve_application_libraries/tasks/instance.yml`; только передача effective image/context |
| Metadata preparation | Новый bounded module_utils/module и role/entrypoint внутри platform.core; сеть отдельно от pure resolver |
| Registry runtime inputs | Library deployment schema и существующий writer intents; `internal/desktop/application_secret_descriptors.go`, существующий broker и `frontend/src/ApplicationSecretInputs.tsx`; расширение `ansible-core/tools/execution_secret_lease.py` и `internal/executionnode/credential_lease.go` для preparation scope |
| Snapshot и план | `plugins/action/project_snapshot.py`, `module_utils/application_plan.py`, `deployment_plan.py`, `playbooks/deployment-plan-machine.yml` |
| Runtime | `plugins/action/prepare_application_runtime.py`, `module_utils/application_runtime.py`, `roles/application_runtime/tasks/preflight.yml`, `image_delivery.yml`, `pull_registry.yml` |
| Fixed protocol | `ansible-core/tools/execution_protocol.py`, Core capabilities и versioned request/response schemas |
| Go orchestration | `internal/executionnode/runtime_protocol.go`, `infrastructure_verification.go`, `execution_service.go`; desktop `installation_plan.go` при необходимости |
| Go projection | `internal/executionnode/application_image.go`; только typed transport/limits и binding, без source/platform resolver |
| UI | Существующие image override/reset в `frontend/src/ApplicationsPage.tsx`, стадия планирования и findings в Installation flow |
| Examples/docs | `examples/valid/application-runtime`, SDKU configuration, project/Core/execution contracts, новый ADR и roadmap после утверждения |

Версии существующих закрытых request/response schemas не расширяются молча.
В шаге 0 сверить занятые версии capabilities/execution-runtime/plan/manifest:
в дереве уже есть несколько поколений, включая plan v1alpha6 и manifest v1alpha4.
Назначить следующие свободные версии и capability `PrepareApplicationImages`.
Изменение public typed image requirement делать только если требуется для
transport; private metadata и semantic fingerprint не превращать в UI DTO-копию.
Схемы image identity/platform переиспользовать через общие definitions.

## 13. UI и проектные материалы

Проверены shared ownership/Save/Verify/plan rules и Instance General в
[UI design](../../design/ui-design-01.md), текущий image override/reset в
`ApplicationsPage.tsx` и соответствующий
[HTML mockup](../../design/ui-design-01-mockups.html).

Согласованная часть: один image input, явный override/reset, Save через существующий
writer, инфраструктурные правила в Core. Обнаруженное расхождение: отдельная стадия
сетевой подготовки image metadata перед planner пока не описана и не показывается.
План предлагает отразить её в общей индикации существующего Create Plan, без нового
поля/кнопки и без автоматического обращения к registry при вводе или Save.
Для этого scope достаточно общей busy-индикации «Подготовка образов и плана»;
поток отдельных progress events и новый planning lifecycle не добавляются.
Это изменение flow включается в утверждение данного плана.

Последующее уточнение владельца добавляет в Library General блок выбора registry
и runtime username/password. Это явное расширение UI scope по запросу владельца,
а не добавление новых image metadata полей. Используются существующие runtime
input компоненты; отдельной страницы registry, постоянного password editor
или фонового planning subsystem не появляется. Обновить design/mockup для этого
блока при реализации и повторить проверку на acceptance.

Сообщения должны различать «образ не найден», «платформа не поддерживается»,
«нет доступа к registry», «нет подходящего оффлайн-образа», «требуется обновить
runtime» и «проект изменился во время подготовки». SHA/размеры не являются
обязательными полями формы. Точный imageId/digest можно показать read-only
в существующих деталях плана для review, без новой вкладки или image manager.
Отмена context подготовки не запускает execution run и не изменяет проект.
Существующая кнопка Cancel установки не управляет подготовкой плана.

Повторить проверку соответствующих flows при acceptance. Nonvisual actual
React/Wails acceptance и visual inspection учитывать раздельно.

## 14. Порядок реализации

| Шаг | Работа | Условие перехода |
| --- | --- | --- |
| 0 | Утвердить план; инвентаризировать protocol versions, все image consumers, node auth/platform prerequisites; закрепить registry runtime refs, preparation/execution lease scopes, схемы и ошибки | Один понятный контракт без unresolved ownership/auth/platform вопросов |
| 1 | Автоматическое чтение Docker-save и containerImages в bundle builder; Go проверка ссылок на components | Builder/reader negative tests PASS; legacy bundles работают |
| 2 | Pure Core selection из bundle + legacy compatibility, per-placement/platform model и fingerprint | Target-free/offline focused tests PASS; нет ручных metadata в новом example |
| 3 | `PrepareApplicationImages`: bounded discovery, registry metadata, exact source/fallback equivalence и private result | Metadata-only registry/native tests PASS; разрешены только transient runtime secrets, без layers/install/permanent target writes |
| 4 | Новый protocol capability, preparation handle binding, frozen runtime authority, target-free registry secret descriptors и preparation-scoped lease | Replay/mismatch/expiry/cancel tests PASS; metadata lease не разрешает Apply/Start; planner остаётся target-free |
| 5 | Синхронный Go Create Plan orchestration, общая busy-индикация, existing findings и library registry runtime inputs | Настоящие React handlers → Wails → Core refs Save/reset/reopen и session inputs/plan PASS; context/deadline cancellation проверена отдельно |
| 6 | Обновить examples, контракты, ADR/roadmap и выполнить regression/review gates | Один FULL DIFF и требуемая QA, точная идентичность проверенного дерева |
| 7 | По отдельному разрешению собрать/опубликовать bundle, выполнить bounded install/Verify acceptance | Exact plan/image evidence, terminal result и cleanup |

Шаги 1–2 не означают готовность нового online flow. Шаги 3–5 не считаются
завершёнными по mocked tests. Установка/DEV acquisition/миграция рабочего
проекта не следуют автоматически из утверждения кода или этого плана.

## 15. Проверки и критерии приёмки

| Группа | Обязательные случаи |
| --- | --- |
| Пользовательский контракт | Default image, override, reset, Save/reopen; отсутствие новых технических полей в group_vars |
| Bundle | Один/несколько images; aliases; amd64/arm64; повторяемая сборка; ref вне components; conflicting key; повреждённый config/layer; symlink/traversal/duplicate entries; изменение файла во время сборки; отказ произвольному @digest alias и положительный случай доказанной manifest/config identity |
| Registry | Schema2 и OCI; tag и @digest; index selection; host:port; missing image/platform; auth failure; TLS failure; timeout; oversized/invalid JSON; неверный manifest/config digest; redirect/token redaction |
| Registry credentials | Library/registry/host isolation; refs-only YAML; username/password session input и expiry; missing/wrong inputs без fallback; old node auth без назначения; registry доступен только targets; metadata preparation без установленного Docker/account; временный DOCKER_CONFIG и cleanup при pull error/disconnect; секреты отсутствуют в argv/logs/public responses/export |
| Registry lease | Target-free descriptors до подготовки; pre-plan lease только metadata; запрет Apply/Start и cross-attempt/revision/node/registry/host reuse; отдельный approved execution lease для pull; renewal не меняет frozen image; Verify без registry read не запрашивает password |
| Identity | Tag изменился между preparation и Start; новый план видит новую identity; старый план использует прежний digest либо блокируется; разные identities одного image/platform на узлах блокируются |
| Источники | Registry wins; только bundle; эквивалентный fallback; одинаковый tag/разные imageId; unapproved registry не опрашивается; отсутствующий источник не вызывает download |
| Runtime | Все выбранные fallback проверены до provider/filesystem/container mutations; повреждённый неиспользуемый fallback не читается delivery preflight; imageId/platform после pull/load; original Compose image; Verify точного контейнера |
| Binding | Другой project/revision/bundle/scope/order/placement/policy; изменённый evidence; чужой handle; symlink; повтор/context cancellation/deadline подготовки; cleanup незавершённого staging; непрерывность exact staged revision |
| Standalone | Те же identities через manual inventory и документированный entrypoint; Ansible/YAML precedence; отсутствие зависимости от Go/Wails |
| Совместимость | Legacy-only projects/bundles; равенство native/manifest locks; pinned legacy tag; конфликт новых/старых metadata; old runtime capability; service-only/infra-verify планы |
| Target-free | Snapshot/Project Verify/secret descriptors/BuildDeploymentPlan без сети и target contact, включая offline `unshare -n` на RED OS; отдельно проверяется разрешённый сетевой prepare |
| Настоящий UI | React image override/reset → Wails Save/reopen; offline/registry синхронный Create Plan; busy/failure/retry; свежий Core plan; отсутствие изменений project metadata; execution Cancel не принимает planning handle |

Проверка отсутствующего/повреждённого unused fallback относится к source-selection
и delivery preflight, а не отменяет полную проверку компонентов при публикации
и активации bundle. Нельзя выдавать повреждённый bundle за verified runtime.

Python/Ansible QA выполняется на RED OS с синхронизацией текущего worktree через
`scripts/qa-sync.ps1`. Windows использует Go/frontend/static checks; Python/Core
на workstation не устанавливается. Для затронутых Go packages — focused tests,
затем требуемые Go test/vet/build; frontend — focused handlers и обязательные
typecheck/lint/build. Broad Core/offline/runtime regression — по действующей
QA процедуре после focused PASS, без повторных полных прогонов без причины.

Реальная install acceptance после отдельного разрешения включает минимум
registry-only и offline delivery, эквивалентный fallback, fresh plan/approval/Start,
терминальный результат и Verify imageId/platform. Получение registry metadata
само по себе не подтверждает application health. Multi-platform behavior проверяется
Core fixtures и, при наличии поддержанного узла, отдельно native; без такого узла
не заявляется ARM target acceptance. ALT нужен только при ALT-specific изменениях.

Доказательства: source revision/дифф identity, версии bundle/runtime, saved revision,
preparation/plan/run IDs, safe terminal events, фактический imageId, отдельный статус
visual inspection и cleanup. Секретные значения и полные registry responses в
evidence не сохраняются.

## 16. Review и завершение

Изменение затрагивает artifact trust/source authority и versioned execution
contract: HIGH-RISK DIFF. До реализации нужен один независимый FULL PLAN review
и утверждение владельцем; после реализации — один независимый FULL DIFF.
Действует бюджет review procedure: BLOCK останавливает автоматическую работу;
не более одного owner-approved TARGETED_RECHECK исправленных blockers.
Self-review не заменяет независимый review.

Независимый [FULL PLAN review](reviews/application-image-metadata-plan-review.md):
APPROVE_WITH_CHANGES, 0 blocking. Неблокирующие AIM-P01 (доказательство offline
@digest) и AIM-P02 (синхронный lifecycle) уточнены в разделах 4, 10, 13–15.
Повторное review для этих уточнений не требуется; утверждение владельцем
по-прежнему предшествует реализации.

Уточнение владельца о library registry runtime-secret меняет secret/UI scope.
Первоначальный FULL PLAN выше относится к версии до этого уточнения.
Для новой редакции выполнен отдельный независимый
[FULL PLAN review](reviews/application-image-metadata-registry-auth-plan-review.md):
APPROVE, новых findings 0, blocking 0; AIM-P01/AIM-P02 подтверждены как RESOLVED.
Утверждение владельцем, HIGH-RISK DIFF review и QA остаются отдельными gates.
Код не реализован.

Критерий завершения: новый проект с единственным пользовательским `image`
строит exact digest-bound план для offline и supported registry источников;
старые проекты продолжают работать; подготовка не меняет desired state;
Save/Verify/planner сохраняют свои границы; actual React/Wails/Core gates и
разрешённая target acceptance имеют отдельные проверяемые результаты.

Первоначальный вариант обсуждения с `defaults.image_artifact` и ручным
переопределением metadata этим планом заменён. Ни defaults, ни group_vars не
становятся хранилищем вычисленных checksum. После утверждения обновить действующие
контракты и дорожную карту в рамках реализации, не выдавая предложение за уже
реализованную архитектуру.
