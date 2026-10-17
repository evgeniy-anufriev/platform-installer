# Общие параметры библиотеки — план изменения контракта

Дата: 2026-10-17. Владелец разрешил реализацию обновлённого плана. Поддержка
schema/resolver/writer/UI реализована в текущем дереве; проверки и ограничения —
в [журнале](evidence/library-common-defaults-journal.md). Установка, запуск
приложений и публикация runtime bundle исключены из этой работы.

## Задача и обнаруженное ограничение

В исходном SDKU общая карта из 48 ENV была объявлена YAML-якорем в
`slots.alarm-service.overrides.environment`; base Compose читает её через имя
alarm-service. Владелец уточнил: общие параметры — в defaults библиотеки,
собственные — в defaults приложения, переопределения экземпляров — только
в group_vars. В SDKU slots больше не содержат overrides вообще.

`library.schema.json` сейчас разрешает name/version/slots/connection_defaults/
shared_secrets и запрещает дополнительные свойства. Deployment не имеет общего
overrides, а writer требует slot или host для SetApplicationLibraryOverride.
Ansible resolver соединяет application defaults, slot overrides, instance
overrides и host overrides. UI читает defaults приложения и индивидуальные
overrides, общего слоя библиотеки нет.

Отдельный include-файл или только base Compose не обеспечивает требование:
snapshot/редактор не увидят общий слой, Reset вернёт неверное наследуемое значение.
Предлагается расширить существующие сущности без нового механизма конфигурации.

## Формат пакета

```yaml
platform_library_definition:
  name: sdku
  version: 1.0.0
  defaults:
    environment:
      KAFKA_CONSUMER_REQUEST_TIMEOUT_MS: "60000"
      KAFKA_PRODUCER_REQUEST_TIMEOUT_MS: "60000"
    parameters: {}
  slots:
    alarm-service:
      applicationRef: alarm-service@1.0.0
      required: false
    hmi-backend:
      applicationRef: hmi-backend@1.0.0
      required: false
    hmi-frontend-viewer:
      applicationRef: hmi-frontend-viewer@1.0.0
      required: false
      inherit_defaults: false
```

`defaults` необязателен, по умолчанию пуст. В этом расширении разрешены только
environment и parameters с существующими типами и ограничениями settings.schema.
Образ, command, ports, credentials/provisioner, identity и provider bindings
не становятся общими через этот блок.

`inherit_defaults` — необязательный boolean слота, default true. Значение false
отключает оба общих слоя ниже только для этого слота; в SDKU оно явно ставится
на frontend-слотах. Выбор backend/frontend не выводится из имени приложения.
Это свойство рецепта, не отдельная настройка установки и не новая сущность UI.

В SDKU все 48 общих ENV перенесены в defaults.environment. Из 18 backend-слотов
удалены overrides и YAML-якоря; восемь frontend-слотов имеют inherit_defaults=false.
Slots описывают только состав, обязательность и выбор наследования. Например,
JAVA_OPTS="-Xmx4048m" остаётся в defaults пакета hmi-backend. Его изменение
для sdku-main записывается только в group_vars, как в следующем примере.
Defaults самостоятельных пакетов приложений не получают ссылок на SDKU.
Существующая поддержка slot.overrides других опубликованных библиотек сохраняется
для совместимости, но этот промежуточный слой не используется в новой структуре SDKU.

## Переопределение конкретной библиотеки в group_vars

```yaml
platform_desired_state:
  applicationLibraryDeployments:
    sdku-main:
      libraryRef: sdku@1.0.0
      runtimeRef: docker-apps
      overrides:
        environment:
          KAFKA_CONSUMER_REQUEST_TIMEOUT_MS: "90000"
      applications:
        hmi-backend:
          overrides:
            environment:
              JAVA_OPTS: "-Xmx2048m"
```

Bindings/resources/shared_secrets и размещение host_vars сохраняют свои нынешние
поля. В SDKU host_vars содержит только membership, без instance overrides.
`sdku-main` и `sdku-reserve` имеют независимые overrides; словари для
всех приложений, YAML-якоря и второй список host targets не нужны.

## Единый порядок разрешения

Для слота с inherit_defaults=true:

1. Общие defaults пакета библиотеки.
2. Собственные defaults пакета приложения.
3. Общие overrides экземпляра библиотеки из group_vars.
4. Overrides выбранного приложения из group_vars.
5. Существующая Core identity projection, которую нельзя переопределять.

Собственный default приложения выигрывает при совпадении ключа с общим default.
Явный override в group_vars выше обоих defaults. В SDKU нет слоя slot overrides
или instance overrides в host_vars. Старые проекты без новых полей сохраняют
прежнюю обработку legacy slot/host overrides; их автоматическое удаление или
миграция не входят в задачу. Если другой проект использует новый общий слой
вместе с legacy overrides, совместимый порядок фиксирован: library defaults →
application defaults → legacy slot overrides → library group_vars overrides →
application group_vars overrides → legacy host overrides → Core identity.
Старые пять слоёв сохраняют взаимный порядок; SDKU legacy слои не использует.

Поздний слой выигрывает. Отсутствие ключа означает наследование, null не является
удалением. Словари соединяются штатным Ansible combine(recursive=true,
list_merge='replace'); обычная Ansible inventory precedence применяется до
композиции сущностей. ENV остаются несекретными, параметры сохраняют типы.
Для inherit_defaults=false пропускаются только шаги 1 и 3.

Один и тот же порядок применяется к application_parameters и итоговым settings.
При отсутствии новых полей результат старого проекта обязан быть идентичным.
Общий базовый словарь environment/parameters вычисляется отдельно от конкретного
приложения: библиотечные выражения могут ссылаться на обычные inventory vars и
идентификатор библиотеки, но не на application_name/application_instance_id или
application_parameters. Ошибки/циклы блокируют resolve. Это обеспечивает одинаковые
base bytes у всех потребителей одной библиотеки на хосте.

Common baseline вычисляется в изолированном Ansible template context без
application facts предыдущего job. Запрет app-specific зависимостей не реализуется
поиском текста выражения: косвенная ссылка через inventory var тоже должна дать
ошибку undefined. Использовать существующий template boundary/изолированные
namespaces; не добавлять собственный parser. Проверить перестановку jobs, первым
frontend и косвенные зависимости от предыдущего application context.

## Core, base Compose и UI

- Core: расширить library/deployments schemas и существующую native resolve role.
  Общие значения поступают в snapshot и runtime projection через прежний pipeline;
  код Go/React не вычисляет Ansible expressions или precedence.
- Runtime projection: добавить один общий resolved словарь на library/host,
  доступный шаблонам как library_runtime.defaults. Он формируется из шагов 1+3
  независимо от выбранного приложения. Существующая проверка идентичности
  baseContent у потребителей остаётся. Никаких lookup по alarm-service.
- SDKU base Compose: backend.environment берётся из library_runtime.defaults.environment;
  frontend использует base без backend environment. Application Compose содержит
  отличия итогового ENV от базового и прежние provider/identity значения.
  Даже при выключенном alarm-service результат не меняется.
- Writer: использовать Set/RemoveApplicationLibraryOverride с пустыми entityId
  и hostId только для property environment/parameters; owner — deployment.overrides.
  Существующие slot/host операции не меняют цель. Без новых CRUD/API/хранилищ.
- UI: добавить раздел «Общие параметры» на уровне библиотеки с ENV и parameters,
  используя имеющиеся поля и draft/Review/Save. Изменения пишутся в group_vars.
  Package defaults не переписываются. Reset снимает только соответствующий override.
  У экземпляра видны его явные отличия и результат последнего Core resolve.
- UI получает raw package/library/slot значения из существующего managed view,
  а общий resolved baseline — из Core snapshot для сохранённой revision.
  До свежего resolve выражения показываются как expressions/DEFERRED, общий
  effective baseline не рассчитывается в React/Go. Для старого snapshot без
  общего baseline показывается «требуется проверка», без выдуманного fallback.
- Различать общий library/host baseline для base Compose и наследуемый baseline
  выбранного приложения: library defaults + application defaults + общий group_vars override,
  без собственного instance override. Второй предоставляется Core, либо получается
  свежим resolve после Reset. Старый итоговый snapshot не выдаётся за значение
  после снятия override: до обновления он помечается устаревшим. Reset common
  не отменяет собственный default приложения или его явный group_vars override.

Текущее UI design не содержит библиотечного редактора ENV/parameters: это
явное расширение дизайна, требующее согласования вместе с этим планом.
При реализации обновить соответствующие mockups, ownership/Reset тексты,
ADR-034 и roadmap; не объявлять per-field provenance без доказательства Core.

## Совместимость и объём

Расширение существующих alpha schemas аддитивное. Старые пакеты/проекты без
defaults, inherit_defaults и deployment.overrides не мигрируются и не меняют
семантику. Старый Core обязан отвергать новые поля как неподдерживаемые при
Verify/BuildPlan, до execution. UI не должен показывать новое разрешение как
прошедшее на старом runtime; точные schema/runtime digests продолжают участвовать
в обычных проверках. Тестом запретить молчаливое игнорирование новых полей.

Runtime projection расширяется аддитивно в существующих application snapshot/rows
и typed Go transport. Не вводить новый resolver, библиотечные profiles, daemon,
secret store или механизм установки. Пакетные digest пересчитать после рефакторинга.
Сборка/публикация нового runtime bundle и реальный target run не входят в эту
работу; использование новых полей на установленном старом runtime невозможно.

## Проверки и критерий завершения

- Native RED OS: старые fixtures без новых полей дают прежние значения; проверяются
  все описанные слои, false/отсутствующий inherit_defaults, типы, списки, неизвестные
  поля, запрет secret values, циклы и недопустимые app-specific common expressions.
- Две библиотеки на одном хосте имеют независимые overrides; два backend-слота
  одной библиотеки имеют одинаковые base bytes; frontend не наследует общий ENV.
- Без alarm-service в выбранном составе/рецепте resolve/base render успешен.
- Индивидуальный override и его Reset возвращают общий результат; общий Reset
  возвращает библиотечный default. Изменение общего ENV не меняет frontend.
- Один ключ с разными значениями на каждом слое: Reset instance возвращает
  наследуемый baseline, Reset common сохраняет собственный default приложения
  и его явный group_vars override; UI не использует старое
  итоговое значение вместо наследуемого baseline.
- Writer/Go: локальный Save/reopen/reset, revision guards, чужие файлы, экспорт,
  импорт обновлённых пакетов, slot/host addressing и старые проекты.
- Реальные React handlers → Wails методы: общий ENV/parameter → draft → Save →
  reopen → instance override/reset; UI на 1024/1440 и inspection перед visual PASS.
  Target-free Core Verify требует подготовленного подходящего runtime; если его
  нет, этот gate остаётся открытым, не заменяется mocks/синтетическим render.
- Повторить SDKU package/schema/digest и Ansible render проверки, обновить
  README/примеры/validation/CURRENT_STATE с точными границами evidence.

Нужны один FULL PLAN review перед согласованием и один FULL DIFF review после
реализации: меняются public/versioned contract semantics. Самостоятельная
проверка реализатора не заменяет независимый review. Дополнительный recheck
возможен только в рамках процедуры и разрешения владельца.

## Первоначальный FULL PLAN review и уточнение владельца

Независимый review: APPROVE_WITH_CHANGES, ноль blockers.
[Отчёт](reviews/library-common-defaults-plan-review.md). LCD-P01 (точный
унаследованный baseline/Reset) и LCD-P02 (изоляция common context, включая
косвенные зависимости) уточнены в рамках того же предложения. Повторный review
для этих nonblocking уточнений не требовался.

После этого владелец явно уточнил модель: defaults библиотеки / defaults
приложения / instance overrides только group_vars; в SDKU slots без overrides.
Этот документ обновлён под решение владельца, включая порядок library default
→ собственный application default. Первоначальный review относится к прежнему
хешу и не является review изменённой последовательности. Новый review в рамках
этой редакции плана не запускался. 2026-10-17 владелец явно разрешил реализацию
по обновлённому плану с минимальным объёмом кода. Реализация использует существующие
Ansible combine, action plugin, writer commands и UI controls. Отдельный FULL DIFF
review фиксируется в журнале; первоначальный PLAN report не подменяет DIFF review.
