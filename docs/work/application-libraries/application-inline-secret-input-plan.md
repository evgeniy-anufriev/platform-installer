# Ввод секрета УЗ непосредственно в строке приложения

Дата: 2026-10-21. Статус: скорректирован по решению владельца после FULL PLAN
BLOCK; требуется TARGETED_RECHECK AIS-P01. Запрос владельца: на странице
«Приложения», вкладка «Секреты», вводить значение пароля УЗ любого ресурса,
а runtime-ссылку связывать автоматически.

Уточнение владельца 2026-10-21: нижнюю форму удалить; на вкладке экземпляра
оставить ввод только в полях ресурсов. Предложение reviewer сохранить нижнюю
форму владельцем отклонено как UX-вариант. AIS-P01 устраняется удалением всей
формы, а не отправкой неполного набора её оставшихся полей.

## Проверенная база и расхождение с макетом

`ApplicationCredentials.tsx:CredentialSourceEditor` для `runtime_secret_ref`
сейчас показывает текстовое поле `ref`, включая неразрешённые шаблоны defaults.
Ввод значений вынесен в `ApplicationSecretInputs` под таблицами и охватывает
всю библиотеку, хотя заголовок содержит выбранный slot.
UI design § Existing-contract secret binding editor и production mockup уже
предусматривают сессионный пароль рядом с источником. Это расхождение UX.

`ApplicationInstance.credentialRequirements` в существующем Core snapshot
содержит разрешённые источники конкретной УЗ; `applicationInputs` содержит
Core-issued requirementRef/sourceRef и library membership. React не должен
разрешать Jinja или строить requirementRef.

`App.SetDeploymentRuntimeSecretValues` требует все requirementRef выбранной
библиотеки. Его отрицательный тест «missing shared ref» запрещает частичную
отправку. Broker уже умеет заменять точный переданный набор requirements и
сливать его с остальными pending values. Менять полный библиотечный контракт
на неявную частичную запись нельзя.

## Поведение интерфейса

1. При источнике «Сессионный секрет» строка password показывает пустое
   password-поле и действие «Сохранить в сессии». Пользователь вводит значение,
   а не ссылку. Сохранённый пароль не считывается и не подставляется обратно.
   Успех подтверждается локальным сообщением; после изменения контекста или
   ошибки оно не служит доказательством актуальной доступности секрета.
2. Для существующей runtime-ссылки, включая шаблон package defaults,
   сохранить исходный desired state. Привязку взять из свежего Core snapshot
   выбранных library/slot/account/field, затем найти ровно соответствующий
   APPLICATION_SECRET descriptor по sourceRef и membership библиотеки.
   При отсутствии или неоднозначности блокировать ввод с объяснением.
3. При переключении другого источника на сессионный автоматически создать
   непрозрачный `application-<uuid>` ref и поместить только source в обычный
   черновик accounts через существующий writer. Существующее требование
   явного account.mode сохраняется. До Review/Save и свежего Core snapshot
   значение не принимается: рядом указать «Сохраните настройки проекта перед
   вводом секрета». Не удерживать пароль между ревизиями ради автосохранения.
4. У runtime username применить тот же механизм ввода значения; literal username,
   generated, Vault и PKI источники сохраняют свои существующие редакторы.
   Нижний ApplicationSecretInputs на вкладке экземпляра удалить полностью:
   никаких дополнительных общих форм, кнопок или диалогов для этих УЗ.
   Никакой остаточной shared/admin формы здесь не создавать и не отправлять
   частичный payload через старый полный API. Отдельные существующие flows
   registry в настройках библиотеки и shared/admin ввода на странице «Установка»
   вне scope этого изменения и сохраняют прежний полный API. Их реальное
   сохранение после inline-ввода входит в regression gate.
5. Значение живёт только в локальном состоянии поля до отправки. Не включать
   его в dirty/edit intents, Review, Save, экспорт, browser storage или telemetry.
   Очищать после отправки (успех/ошибка), отмены, смены контекста и размонтирования.
   Пока есть незавершённые структурные изменения или нет свежей saved revision,
   поле отключено. Значение не переносится в другой account/slot/ref по remount.
6. Если несколько строк/приложений используют один Core sourceRef, это один
   секрет: изменение действует на всех его потребителей. Показывать понятное
   предупреждение о совместном использовании, без автоматического разделения
   существующих ссылок или миграции проектов.

## Минимальное расширение backend

Уточнение владельца после TARGETED_RECHECK: у каждого ресурса нужна плашка
«Секрет задан» / «Секрет не задан», по аналогии с инфраструктурными секретами.
Последующее уточнение владельца: плашка находится в одной строке с именем
deployment и типом сервиса, не в строке credential. Она агрегирует runtime
requirements данного ресурса: зелёная только при наличии всех значений.
Подсказка «Сохраните проект и получите актуальную проверку Core перед вводом
секрета.» также находится в заголовке ресурса; строки credentials её не повторяют.
Это статус наличия значения в Broker, а не факт наличия ссылки в проекте.
Без свежего подтверждения показывать «Статус секрета недоступен».

Добавить read-only GetApplicationRuntimeSecretAvailability, возвращающий
существующий RuntimeSecretDescriptorOperation с revision/fingerprint и картой
applicationSecretAvailability {Core requirementRef: bool}. Метод использует
только действующий cached descriptor evidence для текущих project/revision/
runtime/node и Broker.MissingRequiredSecrets(includePending=true); не вызывает
Core, не делает attestation/promotion, не очищает attached values и не продлевает
TTL. Не возвращает values, sourceRef или произвольные client refs. При отсутствии
актуального evidence возвращает UNAVAILABLE. Одна batch-query обслуживает все
плашки страницы. UI обновляет её после записи, при открытии/возврате фокуса и
с ограниченным интервалом 10s, без перекрывающихся запросов; ошибка убирает
положительный статус. Read-only polling не вызывает GetRuntimeSecretDescriptors
повторно: этот метод меняет attachment и требует Core. Новый getter провести
через существующие Wails/browser transports. Никакого status cache/store в Go.
Плашка доступна для runtime sources; generated/Vault/PKI значения не объявляются
«заданными в сессии» без runtime requirement. Тесты проверяют expiry, independent
refs, stale evidence и отсутствие side effects у status read.

Расширить существующий `RuntimeSecretValuesInput` необязательным полем
`applicationRequirementRef`. Старые вызовы без этого поля продолжают требовать
полный набор библиотеки/сервиса. Не ослаблять тест «missing shared ref».

Для нового режима обязательны непустой applicationLibrary, пустой
serviceDeployment, ровно одно значение, ключ которого совпадает с указанным
applicationRequirementRef. Backend находит descriptor в текущем evidence,
проверяет purpose=APPLICATION_SECRET, membership указанной библиотеки и все
существующие guards project/revision/runtime/node/fingerprint и project binding.
Проверка текущей saved revision обязательна; устаревший snapshot UI не авторитет.
Не принимать sourceRef вместо Core-issued requirementRef и не вычислять его в Go.
Пустое значение не означает удаление секрета; применяются существующие bounds.

После проверки передать singleton requirements в существующий
SetPendingRuntimeSecretValuesForRequirements. Сохранить остальные pending
application/shared/admin/registry values, сроки жизни/поколения, последующее
Core attestation/promotion и immutable run lease. Никакой новой secret storage,
нового Core capability или изменения Ansible source resolution не требуется.
Существующий pending admission не требует действующей SSH credential lease:
не добавлять такой запрет. Различать актуальность descriptor evidence, TTL
pending values и SSH credential lease; истечение pending TTL очищает pending
значения, а дальнейшая запись следует существующему admission. При promotion
по-прежнему требуется действующая credential lease и Core attestation.
Обновить TypeScript/Wails binding и существующий browser transport при необходимости;
не добавлять параллельный API. Ошибки/status не содержат введённое значение.

## Последовательность реализации

1. После согласования плана: scoped Go extension с отрицательными тестами,
   сохранением полного старого API и проверками merge/promotion/isolation.
2. Компактный reusable runtime value input и передача в credential rows
   разрешённых snapshot sources, revision-bound descriptors и существующего
   save callback. Existing writer передаёт только ссылки/настройки.
3. Удалить нижнюю форму экземпляра целиком; проверить сохранность отдельных
   существующих Installation/registry flows полного ввода; синхронизировать
   UI design/контракт runtime input и журнал этого подэтапа. Обновить CURRENT_STATE
   отдельной записью только по фактической реализации/приёмке.
4. Focused tests, go test ./..., go vet ./..., frontend test/typecheck/lint/build.
   Независимый FULL DIFF review обязателен из-за изменения admission секретов;
   бюджет/остановка BLOCK — по docs/agent-procedures/review.md.
5. Реальная React/Wails приёмка на изолированном QA-проекте через существующий
   loopback seam. Verify/descriptor query только на выбранном Execution Node;
   не Approve/Start и не менять работающие УЗ/пароли серверов.

## Проверки и пределы приёмки

* Backend: singleton save и replacement; старый полный scope; неизвестный,
  чужой, service/admin/registry requirement; mixed scope, extra/missing/empty
  values; stale revision/fingerprint/runtime/node; отсутствие/истечение SSH lease
  при действующем descriptor evidence; истечение pending TTL; сохранность
  соседних pending values; promotion и guards активного run/lease как в текущем
  контракте. Ошибка проверки не изменяет broker.
* UI: PG/CH/Redis/Kafka credentials через одну форму без provider rules;
  inherited template ref берётся из Core; переключение создаёт только ref;
  Reset возвращает default; поле не отображает ref и не отправляет пароль
  в draft/Review/Save. Смена slot/revision/source и ошибка очищают значение.
  Два разных refs обновляются независимо; общий ref явно обозначен.
  Нижняя форма экземпляра отсутствует. Inline account save → отдельный полный
  Installation-ввод shared/admin/accounts → reattestation не теряет значения;
  отрицательный missing shared ref по старому API сохраняется.
* Real React/Wails: saved revision, Core descriptor fingerprint, exact safe
  requirement identity, реальные вызовы session-save, отсутствие synthetic
  значения в проекте/Review/публичном evidence, корректные отказы stale/expiry.
  Пользовательские секреты не читать, не печатать и не сканировать.
* Визуально проверить 1440/1024 CSS px отдельно; mock tests не заменяют Wails.
  Недоступные bridge/credentials — открытый acceptance gate, без PASS.
* Core/Ansible семантика не меняется: полный service/Core regression и новый
  bundle не нужны, если реализация остаётся в описанном scope. Если потребуется
  менять Core projection, остановить расширение scope и согласовать поправку.
* Установка/Apply, смена паролей на стенде, миграция рабочих проектов, новый
  secret store, автогенерация паролей и редактирование Vault KV вне scope.

## Решение владельца

Последующее поручение владельца 2026-10-21: исправить AIS-P03 и выполнить
AIS-D01 через реальный Wails/React. Исправление ограничено ключом кеша и
in-flight discovery (saved revision + переданные Go node/runtime/readiness
identity), контекстом поля и отбрасыванием устаревшего результата. После смены
контекста делается одно discovery при входе; polling остаётся presence-only.
Проверка включает смену node/runtime без изменения revision, поздний ответ
прошлого контекста, очистку ввода и отсутствие необходимости первой ошибочной
записи для обновления кеша. Разрешён один TARGETED_RECHECK AIS-P03/AIS-D01
после исправления и получения фактического evidence; новый FULL не запускается.

Владелец отдельно разрешил завершить остальные проверки сейчас и оставить
реальное двухчасовое истечение TTL отдельным открытым пунктом. Этот gate не
помечается PASS и не заменяется fake-clock тестом; перенос не относится к
реальным stale/context/session-invalidation проверкам.

Владелец уточнил обязательный UX: ввод только в полях ресурсов и полное удаление
нижней формы экземпляра. Техническая коррекция AIS-P01 описана выше; AIS-P02
уточнён разделением descriptor evidence, pending TTL и SSH lease. Повторный
review ограничен этими finding IDs и непосредственно затронутой границей.
Реализация и ограниченная проверка — после прохождения review, без установки.
