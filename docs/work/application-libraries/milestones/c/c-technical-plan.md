# C — редактор библиотек приложений

Дата: 2026-10-15. Статус: проект плана для согласования. Разрешены планирование
и HTML-макет; реализация production UI и target mutations этим документом не разрешаются.
Текущий статус — [CURRENT_STATE](../../../../../CURRENT_STATE.md).

## 1. Результат и границы

Добавить страницу «Приложения» между «Сервисы» и «Установка»: выбрать пакет,
создать deployment библиотеки, настроить подключения, ресурсы, slots, размещение
и явные overrides, пройти обычные Review/Save и Project Verify. Установка использует
существующий B4 lifecycle и оптимизированный P2 Apply без нового параллелизма.

Не создавать YAML-редактор, универсальный schema form engine, новый draft store,
новую очередь заданий, второй resolver, собственную публикацию endpoint или
отдельную кнопку запуска приложения. Не добавлять пакетный IDE, редактирование
Compose/Jinja в браузере, автоматическое скачивание образов/пакетов, автообновление
версий, клонирование/переименование deployment и target Clear.
Удаление из desired state не является удалением установленных ресурсов.

## 2. Опора на реализованный код

| Область | Существующая точка | Использование в C |
| --- | --- | --- |
| Разрешённые библиотеки/instances/placements | `internal/coreadapter/application_libraries.go` | Показывать Core snapshot; не вычислять identity, providers, paths, FQDN, precedence |
| Guarded edits | `internal/installer/application_library_save.go` | Существующие девять application EditCommand операций v1.1, base revision, reference/conflict guards |
| Wails edit transport | `internal/desktop/app.go`, `frontend/src/backend.ts` | `startEditSession`, `appendEditCommand`, `reviewEditSession`, `commitEditPlan`, `discardEditSession` |
| Импорт пакетов | `internal/installer/application_package_import.go` | `PlanApplicationPackageImport`; containment, manifest/digest, existing transaction/recovery |
| UI формы | `frontend/src/ServicesPage.tsx`, `TopologyPage.tsx`, `CertificatesPage.tsx` | Master-detail, существующие controls, selection, dialogs, findings, Review/Save |
| Секреты | `frontend/src/ApplicationSecretInputs.tsx`, existing descriptor/Broker lease | Сессионный ввод только по typed descriptors; ни проектный draft, ни localStorage |
| Установка | B3/B4 Installation lifecycle, existing bindings | План/Approve/Start/events/Cancel/Reconnect без нового execution API |

Перед выделением общего control найти реальное повторение в двух страницах.
Переносить только этот небольшой control, сохранив поведение Services. Сам компонент
ServicesPage не превращать в generic editor через десятки flags. Не копировать его целиком.

## 3. Контракт чтения: authored отдельно от resolved

1. Authored значения читать через существующий managed project/edit-session view.
   Во время C2 проверить полноту его application полей. Если UI не получает поле,
   добавить минимальную типизированную проекцию в тот же view и binding; не парсить
   YAML в React и не создавать параллельный файл состояния.
2. Resolved snapshot читать только как Core evidence для конкретной saved revision,
   runtime и контекста. При несохранённых изменениях подписывать «Расчёт для сохранённой
   версии; есть изменения», не показывать его как результат текущего draft.
3. `ApplicationOrigin` сейчас имеет `ANSIBLE / RESOLUTION_SCOPE`: это область разрешения,
   а не доказанный источник каждого поля. Показывать отдельно «Явное переопределение»
   по authored command/view и «Значение из последнего расчёта Core». Не рисовать
   вымышленную цепочку defaults → library → host. Field-level provenance не входит в C.
4. Не редактировать `SERVER_ID`, instance ID, container name, Compose project,
   runtime paths, resolved providers, AppRole identity. Только Core возвращает их.
5. Catalog/package metadata не гарантирует UI-schema для всех вложенных полей.
   В C2 сделать таблицу field → canonical schema → read source → edit operation.
   Неизвестные/неподдержанные поля сохранять без потери и показывать read-only с причиной.
   Для заявленных в §5 editable полей отсутствие проекции — prerequisite, а не молчаливый skip.

## 4. Дизайн и навигация

[Интерактивный макет](../../../../design/ui-design-01-mockups.html) — страница «Приложения».
Он содержит синтетические значения и не обращается к Core/диску/targets.
Проверяются layout, выбор, поиск и вкладки. Create/import/Review/runtime-input —
поясняющие заглушки; локальный ввод сбрасывается при переходе. Dirty-navigation,
focus trap и настоящее сохранение draft — требования production C2/C4, не QA этого макета.

- Слева постоянный поиск и компактное дерево: deployment библиотеки → slots приложений.
  SDKU/CSPA — примеры, не зашитый перечень продуктов. Сверху «Добавить библиотеку»,
  отдельно «Импорт пакета». Empty state предлагает эти действия.
- Справа header выбранной библиотеки/slot, точный package ref, тип выбранного уровня,
  затем короткие вкладки. Длинная форма прокручивается внутри панели.
- Библиотека: «Общее», «Подключения», «Ресурсы и секреты», «Размещение».
- Slot: «Параметры», «УЗ и файлы», «Endpoint», «Расчёт и состояние».
- Сохранение общее проектное: изменения сначала попадают в edit session;
  Review показывает общий diff. «Применить» внутри формы означает лишь изменение draft;
  использовать недвусмысленную надпись «В черновик». Не смешивать с target Apply.
- Контекст проекта, dirty state, Execution Node и run остаются в общем shell.
  На странице нет собственного Save-to-disk или Start.
- При смене элемента незавершённый локальный ввод: «В черновик / Отбросить / Остаться».
  Команды уже в edit session сохраняются при навигации. При закрытии проекта действуют
  существующие lifecycle prompts. Не хранить поля в browser persistence.
- Ввод с labels, видимый focus, ошибки связаны с полем, selection — обычные buttons
  с aria-current, не неполный ARIA tree. Dialog: focus trap, Escape, возврат focus.
- 1440×900: список 260px + редактор; 1024×720: список 220px + редактор, tabs со scroll.
  На более узкой ширине последовательные панели. Footer действий доступен без прокрутки окна.
  Проверить light/dark, 200% zoom и длинные имена; не скрывать критичные findings.

### Состояния

| Состояние | Поведение |
| --- | --- |
| Нет проекта | Общая shell-заглушка; нет editor mutations |
| Нет библиотек | Empty state, добавить/import |
| Пакет недоступен/неизвестная версия | Сохранить authored данные; structured finding и точное действие импорта |
| Нет свежего Core snapshot | Authored editing доступно по Local Save contract, derived поля «Не рассчитано» |
| Dirty/stale | Явная подпись revision; прежние результаты не становятся актуальными |
| Проверка BLOCKED | Findings с deployment/slot/host/field адресом; safe fallback к общей панели |
| RUNNING/STARTING/CANCELLING | Применить текущие backend locks; просмотр доступен, запрещённые edits disabled с причиной |
| Нет runtime credentials | Сессионный диалог; отсутствие не блокирует обычный Local Save |
| Удаляется deployment/slot | Подтверждение с перечнем затрагиваемых authored ссылок; Core/writer остаются authority |

## 5. Формы и точные mutations

| Форма | Ввод/проекция | Операция |
| --- | --- | --- |
| Создание библиотеки | Один deployment ID; exact `libraryRef=name@semver`, `runtimeRef` | `CreateApplicationLibraryDeployment` |
| Общее/подключения | `libraryRef`, `runtimeRef`, `bindings`, `vault_ref`; кандидаты из Core/catalog | `UpdateApplicationLibraryDeployment` |
| Ресурсы/общие секреты | `resources`, `shared_secrets`; typed source references и PKI usage | Та же Update, только изменённый authored участок |
| Состав | Slot IDs из выбранного recipe; `overrides`, `accounts`, optional `credentials.vault_binding` | `SetApplicationLibrarySlot` / `RemoveApplicationLibrarySlot` |
| Размещение | Существующие host IDs; library membership | `SetApplicationLibraryPlacement` / `RemoveApplicationLibraryPlacement` |
| Slot override | image/command/user/restart/parameters/environment/ports/endpoint/accounts/provisioner/readiness/config_files | `SetApplicationLibraryOverride` / `RemoveApplicationLibraryOverride` |
| Host override | Только parameters/ports, как позволяет текущий writer | Те же override операции с hostId; не расширять scope до per-slot-per-host |
| Удаление библиотеки | Deployment ID, подтверждение только desired-state deletion | `DeleteApplicationLibraryDeployment` |

`entityId` и `hostId` в override взаимоисключающие. UI не обещает независимое размещение
одного slot, которого нет в текущем library membership contract. Slot removal semantics
проверить на recipe: удаление authored slot не выдавать за гарантированное отключение
default slot. До подтверждения показывать backend/Core preview результата, без изобретения
нового enabled-флага. Изменение версии — explicit diff, без автоматической миграции.

Пользователь вводит только deployment ID; slot выбирается из recipe. Preview instance ID
появляется после Core, React не конкатенирует идентификаторы. Пакеты immutable в C:
меняется ссылка на версию, не содержимое общего пакета «изнутри» instance editor.

Для parameters/environment использовать существующий key/value подход с типами,
для command — список аргументов, ports — structured rows, endpoint — поля действующей
схемы. Connections/resources/accounts имеют небольшие специализированные секции по
существующему контракту, не DSL редактор. Произвольные пользовательские параметры
и содержимое пользовательских файлов не классифицировать по словам PASSWORD/TOKEN.
Явные credential descriptors проверяются существующим validator: секретные значения
только runtime lease. `config_files` в форме — существующие package file refs/mount intent,
а не произвольная запись файла по пути с клиента. Нет произвольного host-path browser.

«Сбросить» удаляет authored override, а не записывает текущее effective/default значение.
### Образ и порты экземпляра — уточнение владельца

На вкладке slot «Параметры» добавить редактируемые поля «Образ · image»,
«Порт хоста · host / published» и «Порт контейнера · container».
Образ и именованные port mappings по умолчанию берутся из пакета приложения;
UI не создаёт overrides при открытии формы. Для каждого поля показывать
«По умолчанию из пакета» или «Переопределено в экземпляре» по authored состоянию,
рядом — «Сбросить к default». Это не обещание полного field-level Ansible provenance.

Image: существующий `SetApplicationLibraryOverride` с entityId=slot,
setting=image, без property. Сброс — соответствующий Remove.
Порты: structured rows по именованному listener пакета, property=ports,
setting=listener, value=port mapping действующей schema (`published`/`container`
и прочие поддержанные поля). Изменение одной стороны сохраняет остальные authored
поля mapping. Не добавлять в backend контракт альтернативный ключ `host`:
это пользовательская подпись для `published`.

Текущий writer удаляет port entry целиком, а не вложенное поле mapping.
Для независимого сброса host/container пересобрать только authored mapping без
сбрасываемого поля и отправить Set; если authored mapping пуст — Remove entry.
Не копировать оставшиеся effective defaults в overrides. При нескольких pending
изменениях использовать тот же механизм согласования intent из §5.
Core должен подтвердить merge частичного port mapping с package defaults;
проверка этого поведения обязательна до реализации формы, при отсутствии —
явный prerequisite и минимальное уточнение существующего контракта, без UI resolver.

Проверки Core: допустимый image reference/доступность по существующей source policy,
целые порты1–65535, протокол и конфликты публикации на каждом размещении.
UI может давать раннюю подсказку, но не заменяет Core semantic validation.
Slot override действует на все его размещения; host-specific ports доступны только
через существующий membership override, отдельно от slot формы.
Сброс возвращает наследование; если более приоритетный authored host override остаётся,
показывать его отдельно, не обещать package default как итоговое effective значение.

В C-Q03/C-Q04/C-Q13 добавить случаи: исходные image/host/container из пакета;
изменение каждого поля; независимый и полный сброс без записи defaults;
сохранение/reopen; разные slots не меняются; stale revision; недопустимые/конфликтные
порты; Core план и реальный запуск с выбранными image/ports после approval.

Открытие формы, переключение tab или preview не генерирует edit commands.
Повторное изменение одного поля должно заменять pending intent через существующий
механизм edit-session amendment. `amendServiceConfigurationDraft` service-specific:
не вызывать его с application payload. Если существующего общего механизма нет,
добавить узкую application amendment операцию к тому же session command list с
expected-command/revision guards; не создавать вторую очередь и не обходить overlap guard.
Пересекающиеся parent/child edits сводить к одному intent до Review либо возвращать
existing conflict finding; не silently менять порядок команд.

## 6. Импорт пакета

Использовать `PlanApplicationPackageImport` и существующий structural transaction:
native directory chooser → kind/name/exact version/expected digest → preview состава
и findings → обычное подтверждение/commit. В C2 проверить существующий desktop transport;
в текущем frontend backend API готового package import flow нет. Добавить только тонкие
методы выбора и preview/commit в существующий lifecycle, без arbitrary file read bridge.
Не скачивать пакеты. Проверки traversal/symlink/reparse/size/digest/duplicate identity
и cancellation/rollback сохраняются. При активном dirty edit сначала обычный Save/Discard/
Cancel; import plan должен быть привязан к актуальной revision и уже захваченным проверенным source bytes.
Commit публикует ровно рассмотренные bytes/digest из existing PlanStore. Изменения
внешнего source после preview не попадают в подтверждённый план; для новых bytes
нужен новый preview. Дополнительный source watcher/re-read не вводится. Изменение
revision самого проекта по-прежнему отклоняется.
Отмена не меняет проект. После commit обновить каталог/managed view существующим refresh.

## 7. Установка и наблюдение: сохранить B4

Из редактора ссылка «К плану установки» переводит на существующую страницу.
Services checkbox остаётся на Plan tab: меняет лишь отображение до Approve; актуальный
Core Build выбранного состава происходит при одобрении. Библиотеки всегда Apply→Verify.
Свежий infra evidence даёт ровно две library операции; missing/stale evidence — тот же
план с fixed SERVICE_VERIFY prefix, никогда скрытый infrastructure Apply.
Редактирование/revision/runtime change инвалидирует plan согласно существующему lifecycle.
Не переносить approval cache/Verify logic в страницу приложений.

Observed состояние отображать отдельно: контейнер Running, connection checks,
endpoint Verify с run/revision/time/source. Наличие snapshot или сохранённой конфигурации
не доказывает здоровье. Если текущий backend observation не предоставляет показатель,
показывать «Нет данных», а не запускать новые polling jobs. Переиспользовать общие
run events и имеющиеся observations; no new daemon/health loop.

## 8. Подэтапы и acceptance

| Подэтап | Работа | Выход |
| --- | --- | --- |
| C1 | Этот план, дизайн, интерактивный mockup, список расхождений, FULL PLAN review | Решение владельца по плану; implementation ещё не начата |
| C2a | Аудит field mappings, недостающий минимальный authored/catalog transport, route/list/detail, create/update/delete, placement | Реальный Wails Save/reopen; отсутствие materialization defaults и потерь неизвестных полей |
| C2b | Slots/overrides/resources/accounts/references/endpoint, reset, bounded import flow | Guarded Review/Save, revision conflicts, безопасный import; нет duplicate desired state |
| C3 | Contextual findings, наблюдение, ссылки в Installation, runtime secret dialog reuse | Актуальные/stale/unknown различены; B4 approve/start/reconnect не регрессируют |
| C4 | Сквозная приёмка и design acceptance | Реальные handlers→Wails→Core, bounded target proof, hygiene/cleanup, финальный журнал |

Каждый подэтап отдельным ограниченным diff. Сначала согласовать C1; не начинать C2
по одному факту подготовки документа. Существующие B/P2 результаты — baseline,
не доказательство работы нового editor flow.

## 9. QA-матрица

| ID | Проверка | Ожидаемое доказательство |
| --- | --- | --- |
| C-Q01 | Empty/no project/missing package/Core unavailable | Correct actions, no writes on open/navigation |
| C-Q02 | Create two deployments same package, select recipe slots | Distinct backend identities; no product hardcoding |
| C-Q03 | Edit parameter then edit same value again/reset | One coherent pending intent; effective/default not copied |
| C-Q04 | Host overrides, library placement, invalid host/provider | Existing bounds; no per-slot-host extension; structured findings |
| C-Q05 | Shared resources/accounts/PKI/secret refs | Exact authored subtree; arbitrary user PASSWORD parameter accepted; typed literal secret rejected |
| C-Q06 | Review/Save/close/reopen, external revision change | Real Wails, stable files; conflict refuses overwrite; unknown fields preserved |
| C-Q07 | Version/import/cancel/digest mismatch/path traversal/source change | Original transaction guards and rollback; no partial install/package rewrite |
| C-Q08 | Dirty navigation/dialog Escape/focus/long list | Keyboard + visual evidence at1440×900 and1024×720, light/dark/zoom |
| C-Q09 | Existing Services/Topology/Certificates and app editor share controls | Focused frontend regression; no service behavior change |
| C-Q10 | Runtime inputs through existing dialog | Descriptor-bound lease; no plaintext in project/log/events/browser persistence |
| C-Q11 | Fresh plan/scope checkbox/changed revision/acknowledgement | Real React/Wails; only returned authoritative plan approved |
| C-Q12 | Saved infra proof present / absent | Exact2libraryops / fixedVerify prefix; zero SERVICE_APPLY in bounded QA |
| C-Q13 | Create/change one instance, Apply→Verify and unchanged repeat | Run IDs, saved revisions, all real status checks, unchanged sibling IDs/StartedAt; changed0 repeat |
| C-Q14 | Missing input, provider refusal, endpoint failure, Cancel/reconnect | Existing failure states, no skipped barrier; independent evidence per exercised case |
| C-Q15 | Agent restart scenario | Only explicitly scoped QA instance; verify recovery and endpoint, retain shared infra |
| C-Q16 | Hygiene + cleanup | Known-value audit counts/paths only; exact owned temporary resources, safe evidence retained |
| C-Q17 | Runtime secrets: реальный UI → lease → provider hooks → Vault → Agent → приложение | Каждое объявленное подключение подтверждено отдельно, секреты не выводятся; детали ниже |

### C-Q17 — обязательная сквозная проверка runtime-секретов

Уточнение владельца: тестировать не только сохранение descriptor/ref и наличие
контейнера, но и фактическое прохождение runtime credentials через hooks.
Использовать реальный React/Wails «Секреты», свежий утверждённый план и существующий
runtime lease. Для отдельных disposable C QA accounts задать защищённые тестовые
значения; ввод автоматизировать через существующий bounded seam без логирования.

1. Для каждого connection пакета составить матрицу provider → credential descriptor →
   ожидаемая provisioner/hook операция → Vault destination → Agent binding →
   конечная проверка приложения. Проверить отсутствие пропусков объявленных inputs.
2. PostgreSQL/Redis/ClickHouse: проверить создание/обновление только QA accounts,
   права и реальную аутентификацию с runtime input. Не считать один успешный SQL
   connection доказательством всех providers. Kafka в текущем SSL-only контракте:
   проверить объявленные TLS/PKI material и broker connection; не добавлять SASL/ACL
   и не выдумывать password requirement, которого пакет не объявляет.
3. Vault: проверить policy/AppRole bindings и metadata/version ожидаемых KV документов.
   Сравнение actual значения с заданным input выполнять только внутри защищённого
   target/controller процесса; наружу возвращать boolean совпадения и безопасный
   идентификатор случая, не значение/хеш короткого пароля/response payload.
4. Agent: подтвердить чтение именно требуемых документов, успешную материализацию
   всех объявленных переменных/файлов, ownership/mode и доставку в дочерний процесс.
   Проверка внутри защищённого процесса возвращает только число совпавших/ожидаемых
   bindings и boolean; не печатать environment, render files, tokens или leases.
5. Приложение: существующий реальный connection probe подтверждает использование
   переданных credentials для каждого provider и expected status. Один health200
   без проверки всех объявленных checks недостаточен.
6. Missing/incorrect input: стандартная ошибка Core/hook до успешного Verify, без
   маскирования результата. Исправление — новые inputs и fresh plan/approval по
   действующему lifecycle. Unchanged repeat сохраняет существующие KV versions и
   identities; C-Q15 отдельно проверяет восстановление после scoped Agent restart.
7. В evidence: saved revision, runID, перечень объявленных/проверенных providers,
   safe hook results, KV versions, Agent bindings counts, boolean authentication
   и application checks. Known-value audit до и после; cleanup только QA-owned
   credentials/accounts/policies/paths по проверенному ownership.

Здесь hooks — существующие provider/provisioner механизмы. Новые HTTP webhooks,
secret transport, диагностический endpoint с секретами или инфраструктурный Apply
для этой проверки не вводятся. Неприменимые providers обозначаются по контракту,
а отсутствие проверки заявленного provider остаётся незакрытым acceptance gate.

Core tests run on current-tree RED OS via qa-sync. Frontend mocks and Go tests supplement,
never replace actual React/Wails acceptance. Target QA only after approved bounded scenario:
preserve installed infrastructure and canonical PKI/Vault inputs, no infrastructure Apply,
no global Docker prune. Destructive resource tests require exact disposable ownership.
Do not silently skip unavailable real bridge, visual test or supported field: report separate gate.
Run affected regression once; repeat only for changed code/failures/required gates.

## 10. Расхождения и решения к согласованию

1. Старый общий UI proposal обещал точный origin и более широкую instance модель.
   C использует реальный RESOLUTION_SCOPE и library-level membership; отсутствующие
   semantics не реализуются заново в React.
2. Старый макет не содержал «Приложения»; добавлен master-detail в текущий shell.
   Production навигация не меняется до C2. Package IDE исключён, bounded import включён.
3. Общий implementation-plan C3 ранее подразумевал обязательный infra Apply barrier;
   действуют финальные B4 решения: saved evidence либо fixed Verify prefix.
4. Legacy параметры/файлы с любыми пользовательскими именами остаются допустимыми;
   credential descriptors и runtime values — отдельные границы.
5. ID редактируется только при создании; rename/clone и target deletion отложены.
6. Snapshot не содержит универсальную UI schema/authored provenance: C2 начинается
   с mapping существующих DTO, минимальные недостающие поля добавляются в них.

## 11. Review, документы, DoD

По [review procedure](../../../../agent-procedures/review.md) — один FULL PLAN review
этого плана и mockup. BLOCK останавливает автоматические исправления до owner disposition;
неблокирующие уточнения допускаются без автоматического повторного FULL.
Implementation risk классифицировать по фактическому diff: layout/typed CRUD на существующем
lifecycle не требуют нового FULL DIFF автоматически; изменения secret/transaction/public
contract boundaries — HIGH-RISK и отдельный обязательный FULL DIFF gate.

Обновлять существующие design/implementation-plan/contract-index/roadmap и одну строку
CURRENT_STATE. Детальную C QA evidence вести в `milestones/c/evidence/c-test-journal.md`
при реализации, не создавать вымышленные run IDs сейчас. План считается подготовленным
после review и проверки макета; C завершён только после owner-approved реализации,
реальной приёмки, честно разделённой visual/nonvisual evidence и cleanup/hygiene.

## 12. Результат PLAN review и проверки дизайна

[FULL PLAN review](reviews/c-plan-review.md): APPROVE_WITH_CHANGES, 0 blockers.
C-P01/C-P02 уточнены автором после review: immutable reviewed import bytes и точные
границы интерактивности макета; повторный FULL не выполнялся. Решение о реализации
остаётся за владельцем. [Design QA](evidence/c-design-check.md) описывает только
проверенный HTML; production C acceptance пока не выполнялась.

## Owner implementation authorization — 2026-10-15

План согласован, разрешены C2–C4 и необходимые проверки. Дополнительно обязательно
добавить «Секреты» по образцу Services: credentials для всех подключений выбранного
приложения, настройки typed sources и отдельный существующий runtime lease input.
Пользовательские параметры/файлы не ограничивать по именам; literal runtime secrets
в project не добавлять. Статус реализации/acceptance отражается только в CURRENT_STATE
и C journal, прежние запреты в C1 описывают историческую фазу планирования.

Owner UX disposition2026-10-15: C-D03 accepted. Keep per-field В черновик and discard/stay navigation; no automatic batch staging on navigation.
