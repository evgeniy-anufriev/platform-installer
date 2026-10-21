# APPLICATION-INLINE-SECRET-INPUT — TARGETED_RECHECK DIFF

2026-10-21. Независимый architecture-reviewer. Вердикт **APPROVE**.
Неразрешённых BLOCKING: **0**. Только AIS-P03, AIS-D01 и непосредственно
затронутые границы; новый FULL не проводился.

Владелец после FULL DIFF BLOCK поручил исправить AIS-P03 и выполнить AIS-D01
на реальном Wails/React. Отдельно разрешил завершить остальные проверки сейчас,
оставив реальный двухчасовой TTL открытым пунктом. Это не expiry PASS.

## Identity и validity

Первоначальный FULL base `61c52f194d45c11d6ddd8991424026372f4190f3`.
Текущий HEAD `19e1518d966e1f0457dbb1f72970cd5d897c0448`; соседний Kafka scope
не исследовался. Source manifest recheck-source-manifest.json SHA256
`36108e46bb522b2db23642ec9d7dd45934686454e90688bba619b01f1ddd7761`.
Evidence manifest recheck-evidence-manifest.json SHA256
`c63e82a18eafc6c860d24e5823cef861abed733b58512abed004607732b6546d`.
Оба manifest находятся в `.runtime/qa/inline-secret-input/`.
Reviewer проверил и повторно сверил **20/20 source и 7/7 evidence hashes**.
Review validity **CURRENT** для этих manifests. Последующие status/cleanup
bookkeeping изменения журнала не отменяют проверенные результаты.

## Findings

**AIS-P03 — NON_BLOCKING, OPEN → RESOLVED.** App передаёт selection/node/runtime/
status. Descriptor cache и in-flight discovery связаны с revision/execution
context; promise identity защищает новый cache от позднего старого discovery.
Availability scope и field remount используют тот же контекст. Mounted-page
test проверяет same-revision node/runtime change, очистку ввода, поздний ответ
и успешную следующую запись без предварительного stale failure.

**AIS-D01 — BLOCKING, OPEN → RESOLVED в согласованном владельцем объёме.**
Driver, terminal evidence и журнал подтверждают actual React→Wails→Go→Core
Verify и два независимых singleton save; header badges, очищенные поля и
отсутствие нижней формы; исключение собственных случайных значений из112
desired files, public CurrentProject и React Review; полный Installation-ввод
и первую последующую Core reattestation; real stale отказ, node-switch
invalidation и ClearSessionCredential; visual1440/1024.

Real2h TTL **OPEN / owner-deferred**, не PASS. Перенос QA-пункта не отменяет
TTL/security guards. Fake-clock expiry — supplementary evidence.
AIS-P01/P02 остаются RESOLVED; вне targeted scope повторно не открывались.
Новых блокирующих регрессий в исправлении не выявлено.

## Evidence и пределы

Reviewer непосредственно изучил correction code/test, driver, acceptance.json,
журнал и четыре PNG. Затронутые элементы читаемы при1440/1024, видны header
badges/hints и пустые password inputs. Driver вызывает настоящие handlers/
bindings; setter не подменён. Тесты лично не повторялись: frontend272/lint/
typecheck/build и прежние Go test/vet — evidence implementer.
Target hosts, credentials и private material reviewer не открывал.

Explicit descriptor rediscovery сохраняет прежнее очищение attached inputs;
доказана первая reattestation после полного ввода. Сохранность после второго
rediscovery не заявляется. Approve/Start/Apply отсутствуют.

Overengineering: **0 новых findings**. Context identity добавлен существующим
cache/field механизмам; нового API, DTO, store или lifecycle слоя нет.
Promise identity — достаточная небольшая защита позднего ответа.
Новый FULL review этим результатом не требуется.
