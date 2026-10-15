# B — Go backend библиотек и отдельный запуск после инфраструктурного Verify

Дата: 2026-10-14. Статус документа: **предложение для согласования**.
Основание: завершённый A9 и запрос владельца подготовить следующий этап,
добавив отдельную установку библиотек при подтверждённом Verify всей инфраструктуры.
Этот документ не разрешает реализацию, target mutations или новый запуск QA.
Текущий статус работ ведётся в [CURRENT_STATE](../../../../../CURRENT_STATE.md).

## 1. Решение и границы этапа

Следующий этап общего плана — **B, Go backend**. Он подключает библиотеки к
существующим read models, guarded writer, Build/Approve/Start, runtime credentials,
events, Cancel и восстановлению наблюдения. Страница «Приложения» остаётся этапом C.

Предлагается добавить явный режим **«Только библиотеки»**. Он запускает существующие
application-libraries Apply и Verify новым самостоятельным run, без повторного
SERVICE_APPLY/SERVICE_VERIFY инфраструктуры. Каждый такой run получает свежий
авторитетный план и отдельное одобрение владельца. Автоматического запуска вслед
за Save, восстановления старого approval или скрытого второго run нет.

Условие допуска: Core подтверждает успешный Verify **всех включённых инфраструктурных
deployments текущего проекта**, включая сервисы, не используемые библиотеками напрямую.
Результаты разрешено получить в нескольких завершённых runs. Локально сохраняются
безопасные сведения о проверках; окончательное решение принимает Core по собственному
журналу Execution Node и текущему resolved infrastructure fingerprint.

Это небольшое дополнение Core перед B3: существующий A8 допускает библиотеки только
после Verify внутри одного mixed run. Удалить инфраструктурные операции из плана
в Go недостаточно и недопустимо. Сам A8 и его текущая семантика сохраняются.

**Не входит:** новый scheduler, отдельная БД, второй resolver, общий selective-service
installer, arbitrary playbook API, редизайн всех страниц, UI прогресса из roadmap draft,
автоматический reset Vault, установка инфраструктуры при неуспешном admission,
импорт прежнего A9 acceptance как машинного разрешения нового запуска.

## 2. Подтверждённая исходная реализация

Проверена база master `0421456516ed72b8e9da6485ff30ba035eafe2aa`; последующий
`cee36a3f` обновляет generated portable snapshot и не меняет рассмотренные contracts.

| Область | Текущее поведение | Изменение B |
| --- | --- | --- |
| A7/A8 | Structured application projection, фиксированные операции Apply/Verify, mixed barrier | Передать через Go без повторения Core rules |
| `_validate_application_barrier` в `ansible-core/tools/execution_controller.py` | Для application suffix требует пары SERVICE_APPLY/SERVICE_VERIFY | Отдельная versioned ветка для подтверждённой ранее инфраструктуры |
| `internal/desktop/local_run_record.go` | Operational record в UserConfigDir/platform-installer/run-records, ключ canonical project root + project ID; один run, PENDING/RUNNING/TERMINAL | Отдельная локальная проекция Verify, не перезаписывающая запись восстановления активного run |
| `installation_execution.go` | Сохранение Start intent и run identity, восстановление наблюдения | Использовать для обоих режимов исполнения |
| A9 | Standalone libraries, repeat, failure/retry и cleanup доказаны | Не выдавать это за Go/UI acceptance |
| A9 mixed14 | FAILED; инфраструктура принята владельцем по раздельным доказательствам | Исторический FAILED не превращать в SUCCESS/автоматический admission |

Источники: [общий план](../../implementation-plan.md),
[A8](../a8/a8-technical-plan.md), [A9](../a9/a9-technical-plan.md),
[execution contract](../../../../contracts/execution-planning-and-events.md),
[project contract](../../../../project-contract.md),
[architecture](../../../../architecture.md).

## 3. Ответственность слоёв

| Слой | Ответственность |
| --- | --- |
| Portable project | Desired state: inventory, vars, definitions, placements, locks |
| Ansible/service packages | Resolve effective configuration, Apply/Verify сервисов, provider hooks, контейнеры/endpoints |
| Core на Execution Node | Состав инфраструктуры, fingerprints, достоверность Verify, invalidation, admission, plan/manifest и enforcement перед mutation |
| Go backend | Edit/session и filesystem transactions, transport, local operational cache, approval, credentials, run/reconnect lifecycle |
| React/Wails | Показ решений и явные пользовательские действия; без вычисления достаточности Verify |

Go не хэширует YAML ради определения эквивалентности инфраструктуры и не определяет,
какие сервисы нужны библиотеке. Все domain fingerprints возвращает Core. Локальная
запись не изменяет `project.yml`, inventory или `group_vars` и не участвует в Ansible precedence.

## 4. Что означает «вся инфраструктура Verify»

### 4.1. Единица учёта

Ключ проверки — стабильный `serviceDeploymentId`, а не тип сервиса, подпись в UI
или номер строки. Два Kafka deployments требуют двух подтверждений. Проверка
одного хоста из трёх не подтверждает deployment целиком.

Core строит набор всех enabled infrastructure deployments из полного resolved
проекта. Для каждого необходим terminal SUCCESS именно service Verify с полным
плановым coverage hosts/roles. Project Verify, Validate, target-free plan,
Apply SUCCESS, порт 200 и произвольный shell exit0 не являются таким подтверждением.
Пустой набор инфраструктуры в первом scope возвращает BLOCKED с отдельной причиной:
не вводим неоговорённый режим external unmanaged providers.

### 4.2. Составление доказательств

Каждая запись ссылается на завершённую операцию защищённого execution journal:
run ID, operation ID, deployment ID, проверенную конфигурацию и host coverage.
Run должен быть terminal с подтверждённым завершением процессов. Неизвестный итог
Cancel/stop, активный run или недописанный результат не дают admission.

Успешная завершённая операция Verify может учитываться из FAILED run, если другая
операция упала позднее, а после этого Verify не было затрагивающих инфраструктуру
мутаций. Это не меняет terminal state исходного run. Допустимо объединение
подтверждений из разных runs одной и той же инфраструктурной конфигурации.

Для первоначальной реализации использовать **один полный infrastructure fingerprint**
и per-deployment coverage. Не вводить граф частичной совместимости доказательств.
Если fingerprint меняется, прежние подтверждения остаются историей, а readiness
новой конфигурации требует Verify для всего текущего набора. Это консервативнее,
но проще и предсказуемее частичной инвалидации настроек.

### 4.3. Fingerprint инфраструктуры

Core вычисляет его из своей resolved модели, а не из исключения нескольких путей
из project revision. Включаются все effective inputs, которые читают infrastructure
Apply/Verify: deployment IDs, topology/hosts, transport identity и approved host keys,
версии/настройки сервисов, paths, listeners, PKI intent/authority references,
пакеты, schema/catalog/runtime identity, locks и существенная execution policy.
В первый scope входит exact runtime bundle digest: смена bundle требует нового Verify.

Project revision сохраняется отдельно для аудита, но не является единственным ключом
переиспользования. Изменение только библиотечного command/env/образа/ресурса не
инвалидирует инфраструктуру, **если Core доказывает неизменность её resolved inputs**.
Application bindings, ports, endpoint/PKI requirements, влияющие на infrastructure
projection, могут изменить fingerprint; это определяет Core, а не список исключений Go.
Секретные значения и их обычные хэши в публичный fingerprint не включаются.
Используются безопасные generation/reference identities, где это необходимо.

### 4.4. Актуальность и предел гарантии

Уточнение владельца после FULL DIFF B0 (2026-10-14): INFRA VERIFY не привязан к
SSH account, выполнившему проверку. Смена УЗ сама по себе не меняет состояние
инфраструктуры и не требует нового Verify. Для каждого Start остаются обязательными
валидный typed credential lease, approved host keys, trust и необходимые права.
Если использование другой УЗ меняет resolved configuration через Ansible defaults,
это учитывается обычным infrastructure fingerprint. Имя пользователя не служит
самостоятельным ключом или разрешением reuse.

Исторический Verify доказывает проверенное состояние на определённый момент, но
не непрерывное здоровье серверов. Произвольные внешние изменения нельзя обнаружить
по локальному JSON. Перед library mutations сохраняются штатные provider readiness,
ownership, credential и endpoint guards. Они не заменяются историческим Verify.

В первом scope нет произвольного TTL и фонового polling-daemon. UI показывает время
проверки и ограничение актуальности. Оператор может выполнить отдельный Verify-only
инфраструктуры, чтобы обновить доказательства без её повторной установки.
Нельзя называть короткие probes полным Verify всех сервисов.

## 5. Хранение: локально, как run_id, но с удалённым источником истины

### 5.1. Локальный operational cache

Предлагается небольшой JSON рядом с существующим store, например
`UserConfigDir/platform-installer/infrastructure-verification/<project-key>.json`.
Переиспользовать canonical root/project key, безопасные ограничения файлов и
atomic replace существующего `local_run_record.go`; не строить универсальную БД.
Отдельный файл необходим, поскольку новый библиотечный run заменяет last-run record,
но не должен стирать сведения о предыдущих инфраструктурных Verify.

Предлагаемая форма (имена полей предварительные, версия schema согласуется в B0):

```json
{
  "schemaVersion": 1,
  "projectId": "project-example",
  "projectRoot": "<canonical-local-root>",
  "executionNodeBinding": "<safe-binding-id>",
  "infrastructureFingerprint": "sha256:<core-derived>",
  "runtimeBundleDigest": "sha256:<verified-runtime>",
  "evidenceRevision": "<core-journal-revision>",
  "observedAt": "<UTC>",
  "deployments": [
    {
      "deploymentId": "postgres-main",
      "verifyState": "SUCCESS",
      "sourceRunId": "installer-<id>",
      "operationId": "<verify-operation>",
      "coverageDigest": "sha256:<core-derived>",
      "verifiedAt": "<UTC>"
    }
  ]
}
```

Это только UI/cache, без `allowStart=true`. В нём нет паролей, Vault token/unseal,
AppRole/SecretID, приватных ключей, payload stdout или secret paths. JSON локального
диска может быть изменён оператором: это не security authority.

Запись bounded по размеру/числу deployments, версия проверяется, replace атомарный.
Повреждение означает UNKNOWN, не PASS. Старая версия run record v1 продолжает
восстанавливать run; при миграции нельзя выводить Verify из его `TerminalState`.
Ошибка сохранения cache не меняет удалённый результат и не инициирует повторный Start.
Перенос/копирование проекта или импорт с другого компьютера не переносит допуск.

### 5.2. Авторитетное доказательство на Execution Node

Переиспользовать защищённые журналы execution, результаты операций и project lock.
Нужен bounded project-scoped индекс ссылок на Verify и generation инвалидации,
хранящийся внутри существующего execution state namespace. Это operational metadata,
а не инфраструктурная desired-state БД. Не сканировать неограниченную историю на каждый Build.

Индекс обновляет Core при terminal operation/result; перед использованием проверяет
ссылки на оригинальные immutable manifest/results. Потерянный исходный журнал,
несовместимая schema, неполное coverage или противоречивый индекс дают UNKNOWN/BLOCKED.
Удаление evidence при cleanup должно явно инвалидировать индекс. Локальная копия
не восстанавливает удалённое разрешение. Восстановление требует нового Verify-only.
Сборка сертификатов, signing service или доверие к произвольному присланному JSON не нужны.

## 6. Инвалидация и конкуренция

| Событие | Результат |
| --- | --- |
| App-only edit при неизменных resolved infra inputs | Evidence остаётся; план/approval библиотек всё равно устаревают |
| Изменение инфраструктуры, enabled set, размещения, host trust, bundle или PKI intent | Новый fingerprint; readiness STALE |
| SERVICE_APPLY/CLEAR/другая известная infrastructure mutation | До первой mutation под project lock повышается evidence generation; прежняя readiness недействительна |
| Такой run упал/отменён после начала mutations | Не восстанавливать старую readiness; нужен Verify |
| Validate/Build/отказ до mutations | Не уничтожать действующее доказательство |
| Library provider hooks и application-owned endpoint reconcile | Не считать SERVICE_APPLY; readiness reuse допустим только в проверенном ownership scope A, guards сохраняются |
| Library run выявил сбой общего provider/infra | Маркировать readiness требующей проверки по структурированной классификации Core; неизвестная причина — консервативно UNKNOWN |
| CSPA child missing-binary / application-only failure | Не аннулировать доказанные Verify инфраструктуры; app run остаётся FAILED |
| Потеря связи, смена Execution Node, неподтверждённый stop | Запрет запуска до повторной авторитетной проверки / завершения старого run |

Не допускать гонку «Build получил PASS → другой клиент начал Clear → Start использовал
старый PASS». Build связывает план с evidence revision и fingerprint; Start под тем
же project mutation lock перечитывает authoritative evidence. Несовпадение требует
нового плана и approval, а не автоматического расширения scope. Пока library run
владеет lock, инфраструктурный run того же проекта не допускается, и наоборот.
Модель не обещает блокировку произвольных ручных SSH-команд внешнего оператора.

Generation повышается **один раз на инфраструктурный mutating run**, под project
lock до его первой mutation. Последовательность `Apply A → Verify A → Apply B →
Verify B` принадлежит одной generation; Verify A не обесценивается только из-за
следующего Apply B того же одобренного графа. Это сохраняет семантику существующего
mixed barrier. Новый инфраструктурный mutating run начинает новую generation и
инвалидирует весь прежний набор. Verify-only run не повышает generation и может
дополнить её подтверждения. Library-only run не повышает инфраструктурную generation.

Результаты Verify записываются в journal по мере завершения, но индекс предоставляет
их для admission только после подтверждённого terminal/stop исходного run. Если
run завершился FAILED после Verify A, A остаётся доказательством текущей generation;
остальной coverage отсутствует до успешного Verify-only. При этом источники из
предыдущей generation не дополняют новый набор даже при одинаковом fingerprint.
Порядок записи: durable result/terminal → atomic replacement производного индекса.
При crash между ними допустим UNKNOWN/потеря readiness; индекс не может выдать PASS
без проверяемых durable results. Восстановление ограничивается известными ссылками
и их валидацией, не добавляет transaction manager и не угадывает результаты.

## 7. Контракт планирования и исполнения

Предлагаются два явных **режима установки**: `FULL_PROJECT` и `APPLICATION_LIBRARIES_ONLY`.
Точные wire values/schema versions определяются контрактным diff B0; старый mixed
request не получает новую семантику задним числом. Capability negotiation обязателен.
Старый runtime возвращает unsupported, а не молча запускает всю инфраструктуру.

```text
Save текущей ревизии
  → Core resolve + read authoritative infrastructure evidence (без target SSH)
  → Build(mode=APPLICATION_LIBRARIES_ONLY)
  → plan: evidence summary + providers/resources/instances/endpoints + secret requirements
  → явное approval exact plan/fingerprint/revision
  → Start: trust/lease/lock + повторная проверка evidence revision
  → fixed APPLICATION_LIBRARIES_APPLY
  → fixed APPLICATION_LIBRARIES_VERIFY
  → terminal, events/result, local operational cache refresh
```

Admission query/Build остаются target-free: чтение journal на Execution Node не
превращается в скрытый Verify. При совместимом полном evidence library-only manifest
содержит только APPLICATION_LIBRARIES_APPLY/VERIFY и binding на проверенную ревизию
evidence. Если доказательство отсутствует или устарело, один authoritative plan
содержит fixed SERVICE_VERIFY для всех enabled infrastructure deployments перед
библиотечными операциями. Это не отдельный Verify-only plan/run и не второе одобрение.

SERVICE_APPLY запрещён в обоих library-only вариантах. Core выполняет Verify через
существующие entrypoints и передаёт управление библиотекам только после успешного
завершения этой фазы. Ошибка или отмена Verify завершает общий run обычным путём Core
до начала library Apply. Частичные результаты Verify сохраняются по действующим
generation/journal правилам и становятся evidence только после terminal состояния.
Контроллер принимает только local trusted proofs; произвольные playbook/command input
и `skipBarrier` в request запрещены.

Отдельный `INFRASTRUCTURE_VERIFY_ONLY` остаётся явным scope, но не используется как
автоматический второй план при снятом Services checkbox. Не реализовывать произвольное
подмножество сервисов в рамках этого этапа.

Verify-only — отдельный explicit verification scope того же lifecycle, а не третий
неявный режим установки. B0 переиспользует существующий scope, если он доказан
совместимым, иначе публикует versioned `INFRASTRUCTURE_VERIFY_ONLY` capability/request.
Manifest такого scope содержит только разрешённые verification operations всех
enabled infrastructure deployments, без Apply/repair. Exact scope включён в approval;
старый runtime возвращает unsupported и не выполняет fallback. Wire naming и версии
фиксируются в B0 вместе со schemas, до Go integration.

Отдельный library run использует полный enabled library scope. Выбор отдельной
библиотеки не входит в первый B3. Cancel/partial failure/retry сохраняют текущие
правила; общей транзакции providers/Compose/endpoints и rollback не обещается.

## 8. Runtime secrets и Vault

Library-only run не создаёт Vault и не может использовать CURRENT_RUN_BOOTSTRAP,
поскольку соответствующей producer operation в его manifest нет. Используется
существующий typed runtime input/lease с актуальным admin token установленного Vault.
Unseal shares не требуются для библиотек и не доставляются в application scope.

Сохранённое Verify не означает наличия credential. Истёкший/отозванный token,
смена generation или недоступный SecretRef дают отдельную prerequisite failure.
Хранение токена в local status JSON недопустимо. Автоматический поиск по старым
bootstrap audit directories и выбор «последнего token» не вводятся. Повторное
использование сохранённого bootstrap допускается лишь через уже установленный
защищённый input/custody flow с exact provider/project binding.

Секреты не возвращаются через read models, events, findings и local record. После
terminal/cancel сохраняется existing lease cleanup. Canonical bootstrap custody
не удаляется при очистке application run.

## 9. B1 — Go read models и adapter

Расширить существующие `internal/coreadapter` и projection models полями libraries,
instances, findings, origins, secret requirements и infrastructure verification summary.
Проверять supported versions, IDs и bounds; structured error codes сохранять.
Core возвращает missing/stale coverage и причину admission; Go лишь транспортирует.

Необходимы read-only операции: получить application snapshot; получить/обновить
verification summary; получить план выбранного mode. Не создавать второй catalog
resolver или преобразователь Compose. Offline local view может показать прошлый
статус с observedAt и UNKNOWN текущей доступности; кнопка Start требует нового Core Build.

## 10. B2 — guarded writer, пакеты и перенос проекта

Добавить typed edits через существующие ReviewStructuralEditSession/Commit и managed
writer: добавить/изменить library deployment, settings/overrides, slot application,
placement, bindings, resources и endpoint settings. Derived instance identity и
effective values не сохраняются вместо исходного desired state.

Сохранять opaque YAML, unknown supported extensions, explicit overrides и origin;
reset override удаляет именно пользовательское поле. Save остаётся локальным:
структура/containment/conflict checks, stage/atomic replacement/recovery, без Node/Ansible.
Несохранённый draft не строит исполняемый план.

Package import ограничить утверждёнными definitions/templates/configuration/assets,
с metadata/digest и проверяемым allowlist из существующего package contract.
Отвергать path traversal, absolute paths, symlink/reparse escapes, дубликаты путей,
неограниченные размеры и попытку подложить executable hooks. Изменение package
меняет revision и требует нового review/trust по existing rules. Не создавать package editor.
Export/import переносит desired package closure/locks; local run/evidence caches,
credentials и approvals не переносит. Сохранённый статус не является свойством копии проекта.

## 11. B3 — lifecycle и presentation contract

Два mode используют те же CreateInstallationPlan, ApproveInstallationPlan,
StartApprovedInstallation, CancelInstallationRun и reconnect. Не добавлять прямой
«запуск Ansible» из frontend. Local PENDING start intent сохраняется до отправки
remote Start; uncertain outcome восстанавливается по existing protocol без duplicate Start.

На «Установка» для отдельного режима показывать:

- «Инфраструктура проверена» с датой, deployment coverage и доступной причиной STALE/UNKNOWN;
- «Будут выполнены только библиотеки» и реальные provider/endpoint mutations;
- план библиотек, credentials, approval и обычные Execution/Result;
- исходные run IDs инфраструктурных Verify в Advanced, отдельно от текущего library run ID.

Не выводить «инфраструктура установлена» только по Apply или Project Verify. Не рисовать
пропущенные сервисы как успешно исполненные в текущем run. Shared UI vocabulary остаётся
PASS/WARNING/BLOCKED/UNKNOWN/ACTION_REQUIRED; wire evidence states — техническая детализация.

Сравнение с [UI design](../../../../design/ui-design-01.md), его mockups и
[application UI proposal](../../ui.md) выявило предметное расхождение: сейчас описан
только общий mixed flow. Предлагаемое изменение — явный выбор mode на общей странице
«Установка», verification summary и действие Verify-only. Никакой второй страницы
запуска, новой stage strip или изменения Project Verify. Детальный визуальный макет
и согласование этого расхождения — до UI implementation C; здесь фиксируется backend contract.

## 12. Последовательность реализации и gates

| Подэтап | Результат | Gate |
| --- | --- | --- |
| B0 | Versioned Core admission/evidence, infra fingerprint, Verify-only, library-only manifest/controller | Standalone RED OS contract/native QA без Go/UI; independent review |
| B1 | Typed adapter/read model и local evidence projection | Contract/version, missing/corrupt/cache failure tests |
| B2 | Bounded writer/package import/export | Atomicity, stale revisions, opaque preservation, path/size security |
| B3 | Общий Go lifecycle с двумя mode, trust/lease, reconnect | Fresh Build/approval/Start, stale evidence race, cancellation |
| B4 | Production integration + evidence/journal, documentation | Focused regression и требуемая real bridge acceptance |
| C | Полный редактор/страница «Приложения» | Отдельное разрешение, mockups и сквозная UI/visual acceptance |

B0 — явное уточнение прежнего тезиса «вся Core семантика закончена в A»:
cross-run admission ранее не входил в A8/A9. Это ограниченное prerequisite extension,
а не перенос infrastructure rules в Go. Реализовывать последовательно отдельными
reviewable diffs. Перед изменением contract обновить соответствующий ADR и execution
contract; этот proposal пока не изменяет действующие wire schemas.

## 13. Матрица технической приёмки

| ID | Сценарий | Ожидаемый результат |
| --- | --- | --- |
| B-Q01 | Все infra Verify SUCCESS; libraries-only | Только две application operations, ни одного service Apply/Verify |
| B-Q02 | Один отсутствующий Verify, в том числе unrelated provider | BLOCKED с точным deployment |
| B-Q03 | Apply PASS без Verify; Project Verify PASS | Admission не выдаётся |
| B-Q04 | Verify subset hosts / skipped / failed / incomplete | Нет полного coverage |
| B-Q05 | Несколько terminal runs одной infra configuration | Полное coverage агрегируется; исходные terminal states сохранены |
| B-Q06 | FAILED mixed run после успешных infra Verify | Учитываются валидные Verify; FAILED не переписывается |
| B-Q07 | App-only command change | Evidence пригодно; старый plan/approval stale |
| B-Q08 | Infra config/placement/PKI/bundle/host trust changed | Evidence stale; отдельный Verify-only обновляет, Apply не запускается |
| B-Q09 | Поддельный/повреждённый local JSON, старый run record v1 | UNKNOWN/authoritative reload, обход барьера невозможен |
| B-Q10 | Удалён source journal; remote unavailable | Нет разрешения из cache, typed reason |
| B-Q11 | Clear/Apply другого клиента между Build и Start | Lock/evidence revision guard отклоняет stale Start |
| B-Q12 | Mutating run FAILED/CANCELLED; stop uncertain | Evidence invalid/blocked до подтверждённого terminal + Verify |
| B-Q13 | Reopen/Attach после отправленного Start с потерянным ответом | Один run, восстановление events и Cancel, нет duplicate |
| B-Q14 | Expired token / wrong generation / CURRENT_RUN_BOOTSTRAP в library-only | Secret prerequisite fail, без token в public output |
| B-Q15 | Library failure CSPA и repair | SDKU не пересоздаётся; fresh revision/plan/retry; infra не переустанавливается |
| B-Q16 | Clean library repeat | changed0 + IDs/StartedAt/KVversions/DBOIDsACL/endpoint files stable |
| B-Q17 | Typed edits Save/reopen/export/import, external competing edit | Sources сохранены, conflict отказ; caches/secrets не экспортированы |
| B-Q18 | Package traversal/symlink/oversize/unsupported code | Safe refusal до записи/исполнения |
| B-Q19 | Старый runtime без capability | Unsupported mode, без fallback на full install |
| B-Q20 | Исходный mixed flow | Same-run barrier/cancel/bootstrap semantics без регрессии |
| B-Q21 | Apply A/Verify A/Apply B/Verify B; FAILED после Verify A | Одна generation внутри run; partial evidence только после terminal; Verify-only дополняет текущую generation |
| B-Q22 | Crash после durable result до index replacement | UNKNOWN или безопасное восстановление; нет ложного PASS и mutation replay |

Go unit/integration/race проверки — на affected packages; Core/Python/Ansible — только
RED OS из текущего дерева через qa-sync. Не повторять весь A9 или инфраструктурную
установку без конкретной необходимости. Target QA получает отдельный approved scope,
использует установленную совместимую инфраструктуру и явный Verify-only при необходимости.

Production Wails bindings и actual React handlers должны подтвердить затронутый
installation flow по QA procedure. Harness/mock PASS не заменяет это требование.
Если нужное действие ещё не доступно через обычный React flow до C, B фиксируется
как backend-validated с незакрытым integration gate; не добавлять test-only Start API.
Visual acceptance записывается отдельно и только после фактической проверки.

## 14. Ошибки, evidence и завершение

Предлагаемые stable findings: INFRA_VERIFY_MISSING, INFRA_VERIFY_STALE,
INFRA_VERIFY_COVERAGE_INCOMPLETE, INFRA_EVIDENCE_UNAVAILABLE,
INFRA_EVIDENCE_CHANGED, EXECUTION_MODE_UNSUPPORTED. Это проектные названия;
до реализации согласовать с существующим error vocabulary, не дублировать коды.

В журнале этапа хранить revision, runtime digest, mode, plan/manifest fingerprints,
evidence revision/coverage, run IDs, terminal states, safe failures, scoped cleanup
и ограничение acceptance. Ни tokens, ни stdout с потенциальными secret payloads.

Definition of Done: обычный standalone Core путь сохраняется; backend умеет редактировать
и планировать библиотеки; отдельный run библиотек допускается только по актуальному
Core evidence, не повторяет infrastructure install, переживает reconnect и не ослабляет
approval/secret/lock boundaries. QA и cleanup подтверждены, review blockers разрешены
или явно приняты владельцем по процедуре, границы Go/UI acceptance отражены честно.

## 15. Решения, предлагаемые к утверждению

1. Добавить B0 prerequisite Core extension и сохранить B1–B4 как Go backend этапы.
2. Сохранять локальный per-deployment Verify cache рядом с run records; authority —
   existing Execution Node journals и bounded operational index.
3. Требовать все enabled infra deployments, разрешать evidence из нескольких terminal
   runs при одном полном infra fingerprint; без TTL и без частичной совместимости в v1.
4. При stale/missing evidence в library-only plan выполнять fixed Verify всех enabled
   infra services перед library Apply; infrastructure Apply не включать.
5. Library-only — новый явный approved run полного library scope; Vault через актуальный
   runtime input; никакого неявного извлечения старого bootstrap.
6. Начинать код только после согласования этого плана. Этот запрос разрешает документирование.

## 16. Независимый PLAN review

[FULL PLAN report](reviews/b-plan-review.md): APPROVE_WITH_CHANGES, zero blockers,
для SHA256 `C846C43D299B179C6AA235617284CCA176AB16BDE9322268266D4DE17DBAFB7F`.
После review внесены два ограниченных уточнения: B-P01 (generation/result/index
ordering, §6 и B-Q21–22), B-P02 (явный verification scope, §7). Это редакционные
уточнения предложенной архитектуры; повторный review не выполнялся, независимое
RESOLVED для изменённого текста не заявляется. Решение о реализации — за владельцем.


### B2 owner amendment - 2026-10-14

D01/D02: user-defined environment, parameters and package files accept arbitrary
parameter names and assignments, including PASSWORD. Do not infer credentials
from names or assignment text. Explicit Installer credential source descriptors
and runtime private-key custody remain separate. D03: reject overlapping
parent/child edit writes while retaining independent slot edits. Reuse existing
writer and Core validators; no new secret classification framework.


### B4 owner UI refinement (2026-10-14)

Owner approved minimal integration on the existing Installation page. Final
choice: Infrastructure checkbox checked = FULL_PROJECT; unchecked = library
Apply/Verify using saved infrastructure Verify evidence. No actual infrastructure
Verify is implied by unchecked. Libraries have no checkbox yet and always use
Apply/Verify. No new Core scope/manifest/protocol is introduced. Scope choice
must survive navigation and reject use of an old plan for another selection.
The existing React/Wails lifecycle and later separate editor scope are retained.
Positive target acceptance still requires its own approved bounded QA scope;
prerequisite refusal through the real bridge is partial evidence only.


Final owner placement clarification: the operator first builds the plan from the
topology, then chooses to omit repeated infrastructure installation in its services
block on the Plan tab. No scope checkbox before an initial plan or above the tabs.
Keep the prior plan visible but services muted; require fresh mode-specific Build
and approval before any Start. Libraries remain Apply/Verify without a checkbox.

B4 owner amendment (2026-10-14, final): the services checkbox is local presentation
only and never calls Core. On Approve, a changed scope first builds an authoritative
plan with the existing mode-aware API. Only that returned plan can be approved.
New acknowledgements, changed runtime/revision/node, or re-including infrastructure
require reviewing the returned plan before another confirmation. No separate Build
click is required for the scope change. Libraries remain Apply -> Verify; Start is
unavailable while the displayed plan differs from the selected scope. This replaces
the earlier B4 instruction requiring an explicit fresh Build after checkbox changes.

B4 owner amendment (2026-10-14, missing Verify evidence): when Services is unchecked
and Core has no compatible saved infrastructure Verify evidence, the authoritative
plan contains fixed SERVICE_VERIFY operations for every enabled infrastructure
deployment followed by the existing library Apply/Verify operations. This is one
plan, one approval and one run. It never includes infrastructure Apply. Verify
failure or cancellation stops the same Core run before libraries; successful Verify
publishes infrastructure evidence under the existing generation/journal rules. If
compatible saved evidence exists, the plan remains library-only and skips infra Verify.

B4 owner clarification: the missing-evidence SERVICE_VERIFY prefix is part of the
same library execution plan, not a separate plan or approval. The fixed library
Apply/Verify operations remain in that plan. Standard Core failure handling stops
the run before library operations if infrastructure Verify fails; no separate
preflight stage or approval is added.

B4 presentation clarification: while the displayed plan still belongs to the
previous scope and the Services checkbox is unchecked, the Plan tab rebuilds
only its local display projection and omits `SERVICE_APPLY` rows from the services
block. It does not send a request to Core or mutate the received plan. Once Core
returns the authoritative selected-scope plan during approval, the UI displays
that plan without filtering.

### B4 credential completion amendment (2026-10-15)
Owner authorized removal of the requirement-count limit and carrying applicationInputs through the existing runtime lease. Reuse Core descriptors, the existing Broker/value map, current binding/expiry/size guards and actual React/Wails flow. Plan gets a minimal session-only library-secret dialog. Do not change application configuration or weaken target acceptance to avoid credential requirements. Independent FULL DIFF review and real target acceptance remain required; infrastructure Apply is forbidden in this QA.
