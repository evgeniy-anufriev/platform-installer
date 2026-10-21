# APPLICATION-INLINE-SECRET-INPUT — implementation evidence

2026-10-21. Реализовано; после owner-authorized исправления AIS-P03 реальная
ограниченная приёмка PASS. TARGETED_RECHECK APPROVE; real2h TTL отдельно OPEN
по решению владельца. Текущий frozen source: recheck-source-manifest ниже.

## Реализованный scope

* Секрет вводится в поле ресурса, значение идёт только в session Broker.
  Inherited шаблон ref сопоставляется через свежий Core snapshot/descriptors.
  Новый runtime source автоматически создаёт ref; writer получает только source.
* Нижняя instance-форма удалена полностью. Полный Installation API/форма
  остаются прежними. Singleton API проверяет exact requirement/purpose/library,
  revision/fingerprint/runtime/node и сохраняет соседние pending values.
* Presence-only getter не делает Core discovery/promotion/attachment cleanup
  и не продлевает TTL. UI опрашивает batch status, отбрасывает старые replies.
* Aggregate chip и Save/Core prerequisite hint — в header deployment/service.
  Зелёный статус требует всех runtime secrets ресурса. Value read-back отсутствует.
* По решению владельца убрана длинная подсказка schemas/CREATE/ownership;
  права, Core и semantics владения не менялись.

## Автоматические проверки

Go full `go test ./...` и `go vet ./...` PASS. Focused Application/secret-presence
PASS, включая singleton scope/merge/promotion, старый full scope, unknown/foreign/
admin requirement, extra/missing values, stale saved revision, TTL59/61min и
read-only availability. Реальные2h не ожидались; fake-clock не выдаётся за UI PASS.

Frontend full271/25files PASS до последних header/hint изменений и auto-ref test.
Финальный focused34/4files PASS; typecheck/lint/Vite build PASS. Проверены auto
reference без values в draft, singleton payload, очистка полей, aggregate status,
размещение chip в header и отложенный ответ предыдущей revision. Wails debug
build frozen source PASS: `build/bin/platform-installer-inline-secret-qa.exe`.

## Первая QA попытка до поручения исправить AIS-P03/AIS-D01

Isolated source/project под `.runtime/qa/inline-secret-input/`, separate bridge
127.0.0.1:34125; пользовательский bridge34115 не изменялся/не останавливался.
Desired project скопирован без его `.runtime`. Использован опубликованный
runtime53 digest `babc408943933b6dc1dd30d043295ded963d1df6d59ba72cbc985d3747bf16a1`.
Bundle import в QA-копии выполнен из verified active cache, штатный UI rebind
изменил artifactLock; initial modal-close ожидание завершилось90s timeout,
это не execution failure. Ручной cache copy не выполнялся: новый isolated
cache опубликован штатным publisher из rebind flow.

CDP попытка отдельного debug WebView недоступна; переключились на standard
Wails loopback bridge с точной QA-копией Go source. Actual React ChooseProject →
OpenProject PASS; initial saved revision
`sha256:e26cf526fbce77f933a3b305785548a9e3d8f4938b72e604ddd777836584d475`.
PEM established identity transport probe с strict known_hosts PASS; runtime
credential PRESENT, host fingerprint сравнён с trusted known_hosts и утверждён
через существующий Go method; CheckExecutionNode READY. Эти setup calls не
выдаются за React credential/trust acceptance.

Actual React Verify был вызван; на capture состояние ещё «Проверяется», terminal
не наблюдался. В real React Secrets видны header chip/hint и отсутствуют нижняя
форма/удалённая access-подсказка. Resource inputs оставались prerequisite-gated;
synthetic value в resource setter не отправлялся. Это partial evidence, не
positive secret/badge acceptance. Screenshots не просмотрены, visual PASS нет.
Нет Approve/Start/Apply, run ID или изменений паролей/УЗ на стенде.

AIS-D01 OPEN: positive React/Wails singleton/save/badge, independent resources,
project/Review/public secret exclusion, full Installation regression,
stale/invalidation и visual1440/1024 остаются непроверенными. AIS-P03 runtime/node
cache recovery — NON_BLOCKING OPEN; backend возвращает UNAVAILABLE безопасно.

## Первоначальная остановка и cleanup

После FULL DIFF BLOCK новые QA действия не запускались. Уже выполнявшийся
скрипт завершился partial capture; isolated app PID7416 и Wails PID3052 остановлены
по точному executable path. Ранее isolated debug PID22052 остановлен. Original
user bridge34115/PID18372 оставлен работающим. Runtime credentials были только
в памяти isolated process; private PEM contents не читались/не печатались.

Автоматическая проверка отклонила combined cleanup/delete command с причиной
`blocked by policy` без подробностей. Процессы остановлены отдельной менее
рискованной командой. QA source/project/cache и vendor junction сохранены;
удаление не обходилось другим инструментом. Raw local QA logs/manifest остаются
под указанной `.runtime/qa` директорией, без введённого application secret.
Production source, build outputs и документы не закоммичены; чужие Kafka
изменения сохранены. Повторный FULL review автоматически не запускается.

## Owner-authorized correction и реальная приёмка

Владелец поручил исправить AIS-P03 и выполнить AIS-D01 на реальном Wails/React.
Отдельным ответом разрешил завершить остальные проверки сейчас, оставив
реальный двухчасовой TTL открытым пунктом. Это не expiry PASS.

AIS-P03: descriptor/in-flight cache привязан к saved revision и Go-projected
node selection/runtime/readiness; context передан полю, старый ввод очищается.
Поздний discovery не заменяет кеш нового контекста. Mounted-page test меняет
node/runtime при той же revision, возвращает старый ответ последним и успешно
сохраняет с новым fingerprint без предварительной ошибочной записи.
Frontend full **272 tests / 25 files**, lint, typecheck/Vite build PASS.
Go source в QA-копии и основном checkout совпадает (app.go SHA256
`76b9e685738f2aac56f4d531e828727f0c1bea23d89e7cd4a3129364cd9868d8`).

Реальный flow: actual React handlers → Wails loopback34125 → Go → установленный
runtime53 на RED OS node1. Native picker заменён только выбором точной QA-копии;
Open/credential/trust/Verify/save/Review/full-form/node-switch/clear выполнялись
штатными методами. Никакого mocked setter, save bypass или test clock в приложении.
Исходный bridge34115/PID18372 не менялся. Fixture project-current скопирован из
ранее принятого SDKU/CSPA проекта вместе с managed ansible.cfg. Первые попытки
без этого файла корректно отклонялись PROJECT_CANDIDATE_FILE_UNSAFE; guards
не ослаблялись. Затем React Verify terminal VERIFIED.

Saved revision (initial = verified = session-save):
`sha256:be3c233e9156e3040fbe69ca917b223dd54bcb9c1a45a9cfc6eb4875b18d395f`.
Core descriptor fingerprint:
`sha256:ef9f2db8dcaebfd605d549d6de1513d37175e191f842329e6c6cd0ee0f648ef4`.
11 application requirements. Runtime digest остаётся указанным runtime53.

PASS ограниченного прогона:

* React credential form, trusted fingerprint comparison и выбранный node1 READY;
  actual React Verify возвращает VERIFIED.
* Два независимых inline save cspa clickhouse/kafka: exact singleton requirements
  `application-secret-d84d4c9fa603137901c9b52008fdb84a` и
  `application-secret-2b6cdc290d016e0ca0e2a8c866836d7e`; соседний ресурс не становится
  заданным от первой записи, поля очищены, chip внутри deployment h3.
* 112 desired files, public CurrentProject и actual Review не содержат собственных
  случайных synthetic values; после full form desired files проверены повторно.
  Пользовательские значения не читались и не сканировались. QA evidence содержит
  только requirement/revision/fingerprint/count, без значений.
* Unplaced slot не принимает runtime value и показывает prerequisite в header;
  нижней instance-формы и удалённой schemas/CREATE подсказки нет.
* Старая полная Installation-форма принимает все11 inputs после inline save;
  последующая Core reattestation даёт authoritative presence=true для всех11.
* Реальный Wails singleton со stale revision отклонён
  RUNTIME_SECRET_DESCRIPTORS_STALE. UI node1→node2 сбрасывает подтверждённый chip
  при неизменном desired project; actual React Clear очищает session availability.
* Снимки resource-secrets и resource-prerequisite при1440/1024 реально просмотрены:
  header badges/controls читаемы, вводы пусты после сохранения, layout PASS.

Explicit descriptor rediscovery по существующему контракту очищает уже attached
inputs и переаттестует pending; повторное открытие страницы после promotion не
доказывает сохранность attached values. Первое ожидание green после дополнительного
rediscovery было неверным QA assertion. В финальном прогоне positive screenshots
получены сразу после inline save; перед node-switch введён новый pending secret.
Presence polling при этом не выполняет rediscovery и не продлевает TTL.

Final driver `.runtime/qa/inline-secret-input/acceptance.cjs`, SHA256
`98fd466d446e5ce2f46b22a7674b29a724123283170e5d5d6265502b3238ac9c`.
Evidence `acceptance.json`, SHA256
`aa648ad3cba96f9695adc25b3049926052c35858e9053a5f5851c9dabb0ada3a`:
status PASS, terminalStage complete, realTwoHourExpiry NOT_RUN.
Исходники заморожены в recheck-source-manifest.json (20 files), SHA256
`36108e46bb522b2db23642ec9d7dd45934686454e90688bba619b01f1ddd7761`.
Текущий HEAD `19e1518d966e1f0457dbb1f72970cd5d897c0448`; соседний Kafka commit
не относится к correction/recheck. Source hashes не менялись во время прогона.
Execution run ID отсутствует: Approve/Start/Apply не выполнялись, серверные
пароли/УЗ не менялись. Real2h TTL **OPEN / owner-deferred**; fake-clock test
остаётся отдельным supplementary evidence.

## Итог recheck и cleanup

[TARGETED_RECHECK DIFF](../reviews/application-inline-secret-input-diff-targeted-recheck.md)
APPROVE: AIS-P03 RESOLVED, AIS-D01 RESOLVED в owner-agreed scope, BLOCKING0.
Reviewer независимо сверил20/20 source и7/7 evidence hashes; сам тесты не
повторял. Эти status/cleanup строки добавлены после frozen evidence review.
Production source20 остался неизменным.

После actual React Clear подтверждены credential MISSING, selected node2
NOT_PREPARED, availability UNAVAILABLE и прежняя managed revision be3c233e….
Isolated child59556 и Wails56144 остановлены после проверки exact executable,
parent PID и bridge port34125. Original user process18372 сохранён работающим.
QA source/project/cache и vendor junction оставлены: ранее отклонённое policy
удаление не повторялось и не обходилось. Секретные application values были
только в памяти isolated процесса, затем сеанс очищен и процесс остановлен.
Real2h TTL остаётся единственным отдельным owner-deferred QA-пунктом.

## Однострочные username/password — owner layout refinement

2026-10-21: переменные и кнопки больше не переносятся; имена сокращаются с
полным tooltip, расширенные источники прокручиваются горизонтально. Inline
сообщения сохранены как доступный information indicator с tooltip. Pure layout,
handlers/transport/secret guards не менялись; новый FULL review не требуется.
Focused18, typecheck/lint/build PASS. Actual React layout fixture (не Wails/Core
acceptance) проверяет literal/runtime/Vault/PKI при1440/1024: высота каждой строки
47px, включая runtime shared/status indicator. Снимки просмотрены, визуально
однострочные поля без перекрытий. Evidence `.runtime/qa/credential-row-layout.json`
и `credential-row-1440.png`, `credential-row-1024.png`; private values не использованы.

## Username из актуального Core snapshot

2026-10-21: literal username в неизменённом поле отображается из переданного
Core credentialRequirements. Existing freshSecrets gate исключает busy/draft/
dirty/stale revision; password и runtime/Vault/PKI values не подставляются.
Focus показывает исходный authored/package текст; blur без редактирования
возвращает Core projection. onSave использует только authored values, поэтому
показанный derived username не записывается автоматически в проект. Без
актуальной проекции остаётся исходный шаблон, Jinja в React не вычисляется.
Focused30 PASS, финальный focused7 после type-only test correction PASS;
lint и typecheck/Vite build PASS. Actual React browser fixture проверил
Core display → focus raw → blur Core и строки47px при1440/1024; это не новый
Wails/Core acceptance. Артефакты `.runtime/qa/username-core-layout.json` и
`username-core-1440.png`, `username-core-1024.png`; снимок1024 просмотрен.

Последующая проверка по просьбе владельца выполнена через отдельный actual
Wails bridge34125 и реальный проект full-services (копия принятого SDKU/CSPA,
project-current), без synthetic credential rows. Actual React Open → credential/
trust → node1 READY → Verify VERIFIED, revision be3c233e… (полный выше).
Core username clickhouse `alarm_view_service_cspa` совпал с фактическим input
на вкладке cspa/alarm-view-service/Секреты. Получены real-project-username-1440.png
и real-project-username-1024.png;1440 просмотрен. Evidence
`.runtime/qa/inline-secret-input/real-project-username.json`: PASS/complete,
Core runtime53, приложение не запускалось. Это реальная проверка отображения,
редактирование/сохранение username повторно не выполнялось. Сеанс очищен через
React, isolated child45264/Wails54168 остановлены по exact identity; оригинальное
окно18372 сохранено. QA source/package credentials в снимках отсутствуют.

## Имя БД вместо ключа ресурса

2026-10-21: AccountAccess получает актуальные resolvedResources через existing
snapshot revision/draft gate. Колонка «База данных» и options используют
Core parameters.name, затем authored name/reference как fallback. Option value
и saved databaseRef остаются ключом. Открытие редактора прав не убирает имя
базовой БД. Frontend focused32, lint, typecheck/Vite build PASS; test подтверждает
Core name в row/option и сохранение исходного ref.

Actual React/Wails/Core на копии full-services: Verify VERIFIED (be3c233e…,
runtime53); у clickhouse resource history в таблице фактически показано cspa,
равное Core resources.history.parameters.name. Evidence
`.runtime/qa/inline-secret-input/real-project-database.json`: PASS/complete;
screenshots real-project-database-1440.png и -1024.png,1440 просмотрен.
Первые попытки: trust/probe timeout; дополнительный параллельный диагностический
probe инвалидировал snapshot после Verify. Финальный последовательный повтор
без параллельного probe PASS. Реальные rights edit/Save/Apply не выполнялись.
Сеанс очищен через React; exact isolated child31404/Wails1156 остановлены,
пользовательское окно не останавливалось. Application passwords не вводились.
