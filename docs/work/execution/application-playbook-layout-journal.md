# Организация application playbook — 2026-10-25

Запрос владельца: перенести application-playbook из корня Core в отдельный
каталог, работать в отдельном worktree/ветке и проверить Go-интеграцию и
standalone Ansible. Владелец ранее исключил React/Wails из проверок.

Worktree: `organize-application-playbooks/platform-installer-v2`.
Ветка: `codex/organize-application-playbooks`; база `f5b6c62c` (`origin/master`
на момент создания). На этапе реализации основной checkout и параллельная установка не изменялись.

## Изменения

- Перенесены19 root-level application-файлов и5 общих task fragments.
  В `ansible-core/playbooks/` осталось14 общих YAML-файлов.
- `applications/{apply,verify,post-install}.yml` — главные точки входа;
  `images/` —3 playbook подготовки образов; `stages/` —11 импортируемых
  playbook; `tasks/` —7 фрагментов для include/import_tasks.
- Обновлены3 Core-вызывающих компонента: execution controller, machine
  protocol и image-preparation runner. Типы операций, версии DTO, порядок
  выполнения, inventory, scope/targets и runtime custody не менялись.
- Относительные import/include, путь к integrations и fallback contracts
  пересчитаны. Структурное сравнение24 YAML подтвердило31 разрешимую ссылку
  и отсутствие прочих изменений порядка, аргументов и условий.
- В роли `resolve_application_libraries` fallback `contracts_root` теперь
  привязан к `role_path`, а не каталогу вызывающего playbook. Явный
  `platform_contracts_root` сохраняет приоритет. Две реальные native-проверки
  покрывают прямой CLI и импорт из внешнего каталога без override.
- Обновлены активные Python/QA-вызывающие пути и standalone-документация.
  Исторические планы, журналы и generated portable-source не переписывались.
- Корневые compatibility wrappers не оставлялись: ручные команды используют
  новые документированные пути. Старые runtime bundles сохраняют собственные
  controller/playbook-пары; новые файлы поставляются вместе в новом bundle.

Это ограниченный рефакторинг файловых путей в существующем контракте; новой
архитектуры, dispatcher/registry или второго источника состояния нет.

## Проверки

| Проверка | Результат |
| --- | --- |
| Windows `go test ./...` | PASS,16 пакетов |
| Windows `go vet ./...` | PASS |
| Syntax-check всех основных playbook, включая вложенные |69 PASS |
| Standalone runtime resolution, прямой вызов и внешний import |2 PASS |
| Те же standalone-проверки в `sudo -n unshare -n` |2 PASS |
| CLI `--list-tasks` всех6 внешних entrypoint из отдельного cwd |6 PASS, без исполнения target tasks |
| Real Core image protocol / native Ansible planning |2 PASS в Core regression |
| Native infrastructure scope и real controller Verify → Application Apply/Verify |2 PASS, синтетические local fixtures |
| Caller/lifecycle/plan/post-install и bundle closure |110 PASS |
| Skipped-provider callback, два повторных запуска |1 PASS |
| Native PKI single-pass, включая recovery, пять потребителей и password rotation |16 PASS |
| Структура перенесённых файлов |24 YAML/31 imports, прочих semantic changes0 |
| Сверка итоговых production sources с full-regression workspace |28 файлов, mismatch0; нормализованные LF |

Проверка упаковки подтверждает включение всех24 application YAML и совпадение
component hashes. Реальный runtime bundle не публиковался и не активировался.
Для новой раскладки не требуется менять Go API; Go выбирает прежние Core
операции, а конкретные пути находятся внутри соответствующего Core release.

## Full Core regression

Полный прогон завершён штатно:932 cases,1 failure,2 errors,26 skips;
5828с по внешнему таймеру. Его исходная сводка **не объявляется PASS**:

- `test_application_selection_native` падал из-за отсутствующего
  `scope.installLibraries` в старой fixture; поле дополнено, отдельный повтор
  того же native-теста:1 PASS с двумя CLI-запусками.
- `test_szi_stage1.test_ordered_library_playbook_runs_keycloak_before_dependent_instances`
  обращался к `tasks[0]`, где после добавления progress marker уже нет set_fact.
  Селектор исправлен по ключу `application_library_instance_ids`; повтор1 PASS.
  Приоритет Keycloak и assertions порядка сохранены.
- `test_acquire_redos8_infrastructure.test_current_requirements_include_ancillary_packages_and_exact_versions`
  завершился исходным `TypeError` в не изменённом acquisition tool. Он остаётся
  открытым baseline-дефектом и не относится к переносу; повтор на исходном
  коде описан ниже.

Новых production-отказов, вызванных изменением путей, не обнаружено.
Все16 native PKI cases завершены успешно; ни один прогон не останавливался.
Пропуски — существующие gated native/root/SSH/Compose-сценарии; отдельно
выполненные2 native controller cases закрывают соответствующий gate в
затронутом application-потоке. Это не объявляет остальные skips PASS.

В ходе QA исправлены три устаревшие тестовые фикстуры: повторное
`execution_target_trust.stage` удалено после первоначальной штатной регистрации,
а skipped-provider scope дополнен `installLibraries: []` для существующих
progress markers. В проверке порядка СЗИ позиционный доступ `tasks[0]`
заменён поиском set_fact по ключу `application_library_instance_ids`.
Production trust/selection guards не отключались.
Последние изменения этих fixtures и расширенная bundle-проверка отдельно
проверены после запуска полного прогона. Все28 изменённых production-файлов
совпадают с версией полного прогона.

В базовом `acquire_redos8_infrastructure.requirements` воспроизведён
`TypeError: unhashable type: 'list'`: `groups.extend([[name]] ...)` создаёт
вложенные списки. Выполнен отдельный повтор функции из `git show HEAD` на тех
же неизменённых manifests/defaults. Сбой не относится к переносу; production
acquisition tool в эту ветку не включён и не исправлялся.

## Границы

React/Wails и реальная установка приложений не запускались. Native controller
использовал только временные синтетические playbook и local connections.
Проверка real UI acceptance и production runtime activation не заявляется.

Логи: `.runtime/qa/application-playbook-layout-evidence/`, Go-логи в
`.runtime/qa/go-test.log` и `go-vet.log`. Все8 временных source workspace
удалены штатным `qa-sync.ps1` после сохранения evidence. `git diff --check` PASS.

Владелец отдельно разрешил коммит и синхронизацию изменений в master.
