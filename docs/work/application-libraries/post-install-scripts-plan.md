# Завершающие скрипты пакетов — post_install

Дата: 2026-10-25. Статус: FULL PLAN APPROVE_WITH_CHANGES, blocking0; уточнения внесены. Владелец утвердил реализацию 2026-10-25; реализация и standalone QA завершены в согласованном объёме. FULL DIFF замечания отклонены владельцем; без расширения общей логики.
Рабочая ветка: codex/szi-stage3. Реальный installation run отложен владельцем.

## Требование

Скрипты приложения или библиотеки с `phase: post_install` являются последними
исполняемыми действиями успешного плана установки. Используется существующий
контракт scripts и универсальная роль package_script. Новых обработчиков СЗИ,
контейнерных требований или командных мостов Go/UI не появляется.

## Семантика

1. Существующие before_start, after_ready и интеграционные фазы не меняются.
2. Core добавляет одну операцию APPLICATION_LIBRARIES_POST_INSTALL после всех
   обычных операций плана, включая APPLICATION_LIBRARIES_VERIFY и проверку
   endpoints. Операция появляется только при наличии активных post_install.
   В FULL_PROJECT она следует также за инфраструктурными действиями.
3. При ошибке/отмене предыдущего действия завершающие скрипты не запускаются.
   Это не always/finally и не механизм очистки или отката.
4. Ошибка скрипта завершает run ошибкой через существующую безопасную диагностику.
   Не вводятся ignore_errors, автоматические повторы или продолжение после ошибки.
5. Повторный Apply повторно вызывает post_install; идемпотентность обеспечивает
   сам скрипт, changed передаётся по текущему протоколу package_script.
6. Скрипты пропущенных библиотек не выполняются, включая пропущенных провайдеров.
   Их разрешённые integration callbacks остаются на текущем этапе подготовки.
7. INFRASTRUCTURE_VERIFY_ONLY и standalone Verify не вызывают post_install.
8. Порядок строго последовательной общей очереди: индекс в эффективном libraryOrder,
   order, id, scope (library перед instance), instanceId, hostId. Для library scope
   instanceId — выбранный текущим resolver представитель; once дедуплицируется
   существующими правилами до сортировки. `execution: once` означает один вызов для
   соответствующего scope в пределах run, а не постоянную отметку выполнения.
   Используется текущее правило выбора целевого хоста, без нового scheduler.
9. Сохраняются run_on=target/execution_node, target connection, when_connection,
   argv, secretInputs и выбор once/each_target. Раннер получает только явные
   входы. Контекст приложения разрешает Core, не раннер.

Пример в package manifest:

```yaml
scripts:
  - id: finish-setup
    source: assets/finish-setup.sh
    phase: post_install
    execution: once
    run_on: execution_node
    argv:
      - valueFrom: libraryId
```

## Изменения Core

- Каноническая схема package v1alpha3 (application и library): добавить фазу
  post_install с сохранением остальных полей/проверок. Согласовать ссылки схем;
  не создавать отдельный тип завершающего скрипта.
- application_plan/application_scripts: включить выбранные скрипты и их входы в
  resolved model, semantic fingerprint и точную область секретов/хостов завершающей
  операции. Не требовать для post_install образов или secret requirements,
  относящихся исключительно к запуску контейнеров.
- Планирование/manifest: добавить типизированную последнюю операцию. Новая
  комбинация операции и порядка получает plan/v1alpha9 и
  execution-manifest/v1alpha7 (текущие максимумы v1alpha8 и v1alpha6).
  Старые версии package/plan/manifest и планы без post_install сохраняют прежнее
  поведение. Capability execution protocol: applicationPostInstall с protocol
  ApplicationPostInstall/v1alpha1 и поддерживаемыми тремя версиями контрактов;
  отсутствие capability блокирует новый контракт до планирования.
  SchemaValidator, protocol admission и controller должны принимать один и тот же
  контракт; проверка терминального положения обязательна в Build и Start.
- execution_controller: сопоставить операцию самостоятельному Ansible entrypoint,
  использовать текущие projection, trust, lease, events, failure/cancel и cleanup.
  Не выполнять callback из Go и не добавлять постобработку вне утверждённого плана.
- Ansible entrypoint post-install: разрешить текущий runtime/script context без
  Apply/preflight/provisioning/readiness/Verify, затем вызывать package_script.
  Переиспользовать существующее разрешение target/execution_node и доставки
  секретных файлов. Если небольшой общий task нужен для двух точек вызова,
  вынести только его, без новой инфраструктуры обработчиков.
- Секреты materialize/lease должны оставаться доступны до конца этой операции.
  Не удалять её inputs в always конца Apply. Операция не зависит от оставшихся
  process facts предыдущего ansible-playbook; контекст воспроизводится из
  утверждённой проекции и существующего защищённого хранилища входов run.

## Go, UI и документация

Go допускает новую версию/операцию и передаёт её без вычисления порядка или
семантики. Журнал/страница плана показывают завершающее действие из Core через
существующие отображения; нового редактора scripts нет. Проверить узкие allowlist
операций runtime secrets, host trust и execution adapter. Не расширять доступ
секретов на все действия плана.

Обновить контракт scripts, execution planning/events, описание standalone
entrypoint и текущий Stage3 журнал. Изменение публичного контракта требует
независимого FULL DIFF после реализации. UI acceptance остаётся отдельным gate;
реальный run не запускать до нового явного указания владельца.

## Проверки до реального run

1. Package schema → реальный протокол → manifest → controller: оба scope,
   once/each_target, оба run_on, target connection, argv и secretInputs.
2. Plan без post_install не меняется; с post_install ровно одна последняя
   операция; отрицательные случаи перестановки, дубля и подмены scope отвергаются.
3. FULL_PROJECT и APPLICATION_LIBRARIES_ONLY; skip выбранной библиотеки;
   отсутствие post_install в Verify-only; сохранение provider integrations.
4. Standalone Ansible на Execution Node с простыми fixture scripts записывает
   порядок событий: обычные действия → Verify/endpoints → post_install.
   Проверить один вызов once, each_target, повтор, ошибку и отсутствие запуска
   после предыдущей ошибки/отмены. Это изолированный QA, не план установки стенда.
5. Отдельный Ansible-процесс получает после Apply исходный runtime input,
   secret_binding и generated account password через существующее точное чтение
   опубликованного значения/защищённую materialization, без второго хранилища. Значение
   не попадает в argv/events/logs/project; lease/cancel cleanup работает.
6. Аffected Go/frontend tests и сборка; новые схемы совпадают с реальными
   payload протокола, старые fixtures по-прежнему принимаются.

## Текущее состояние очистки стенда

До изменения владельцем приоритета завершился уже начатый bounded reset:
удалены шесть consumer containers на 101/102, шесть клиентов и шесть групп
СДКУ/CSPA в Keycloak, шесть маршрутов на работающем nginx103. Три маршрута СЗИ
сохранены. Provider accounts/ресурсы ещё не удалялись. Wails plan/Start не вызваны.
Очистка оставшихся ресурсов и реальный run отложены до возврата к приёмке.

## Независимое ревью

FULL PLAN: APPROVE_WITH_CHANGES, blocking0; overengineering findings0.
[Отчёт](reviews/post-install-scripts-plan-review.md). POST-P01: версии/capability
зафиксированы; POST-P02: полный ключ и последовательная очередь зафиксированы;
POST-P03: отдельный процесс, secret_binding/generated values добавлены в gate.
Это уточнения плана, тесты и реализация ещё не выполнены.
