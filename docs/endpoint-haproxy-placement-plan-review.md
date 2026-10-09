# ENDPOINT-HAPROXY-PLACEMENT-01 — независимый FULL PLAN review

Дата: 2026-10-09. Первоначальный широкий план: **BLOCK**, SUPERSEDED
после явного изменения владельцем объёма. Новый узкий FULL PLAN:
**APPROVE_WITH_CHANGES**, блокирующих замечаний нет; реализация разрешена.
Review выполнен независимым `architecture-reviewer`.
Рассмотренный план: `endpoint-haproxy-placement-plan.md`.
HEAD: `3efc11262c32bec8d90c503785a03dfdb359bda0`.
SHA256 исходного плана:
`5B56661AD45E7DC98A558FA51A4A9025594E2E74E605F4076547F7DA708CDAC4`.
После review изменён только статус документа и добавлена ссылка на замечания.

## EHP-01 — BLOCKING, SUPERSEDED для нового scope

Раздел 6 предполагает атомарную активацию source backend через существующие
задачи, но они сначала архивируют старые backend (`activate.yml`), затем
последовательно публикуют файлы (`activate_publish.yml`). Rescue сообщает
`HAPROXY_ACTIVATION_RECOVERY_REQUIRED`, не восстанавливая прежний набор.
Атомарность отдельного файла не равна транзакции нескольких фрагментов сервиса.

Минимальная коррекция: определить границу source-scoped транзакции, сохранить
точный прежний набор и обеспечить восстановление при сбое публикации,
проверки или reload. Гарантия атомарности подтверждена владельцем и не может
быть ослаблена без его решения. Проверить прерывание после удаления старого
фрагмента, между публикациями, ошибку reload и восстановление после рестарта.

## EHP-02 — BLOCKING, SUPERSEDED для нового scope

Раздел 5 описывает запись результата после успеха, но не durable intent
до первой мутации. Авария после активации backend до записи результата
может потерять новый узел из списка прежних cleanup targets после переноса
или удаления source. Локальный архив не обеспечивает обнаружение такого узла.

Минимальная коррекция: до мутации атомарно сохранить bounded pending запись
одобренных exact target/action/fingerprint в существующем generated-state.
Затем обновлять подтверждённый результат. Fresh plan учитывает pending и
confirmed цели без расширения scope уже выполняемого плана.
Проверка: остановка между публикацией и receipt, затем изменение endpoint
или удаление source; следующий план должен включить правильную cleanup.

## EHP-03 — NON_BLOCKING, RESOLVED в новом плане

PARTIAL aggregate не следует смешивать с private terminal lifecycle.
Зафиксировать отдельно статус private ExecutionResult и отображение
«Завершено с пропусками»; владелец должен подтвердить итоговую проекцию.
Missing-provider: ERROR + SKIPPED, следующие действия продолжаются,
backend не отображается успешно выполненным.

## Исторический итог широкого плана

Схема выбора размещений соответствует решениям владельца. Избыточных
механизмов, новой БД/демона/API и дублирующих DTO reviewer не выявил.
Existing resolvers, partial role и generated-state остаются основой.

Два блокера переданы владельцу. Рекомендация исполнителя: внести минимальные
коррекции EHP-01/EHP-02 в план, сохранив выбранную архитектуру; затем провести
один owner-approved TARGETED_RECHECK только этих замечаний. Автоматическое
исправление/re-review не выполнялись. Тесты, SSH и установка в review
не запускались. Approval review не является разрешением Start/cleanup.

## Новый узкий FULL PLAN review

Независимый `endpoint_haproxy_narrow_review` рассмотрел owner-approved замену
только механизма привязки. HEAD прежний; SHA256 рассмотренного плана
`B42BC3857B918CD638BEB645232618B92AF91BC675667BB259CC4751515F4755`.
Verdict **APPROVE_WITH_CHANGES**, ноль блокирующих замечаний.
EHP-01/EHP-02 SUPERSEDED для нового scope, а не исправлены: новые гарантии
атомарности и durable intent владелец явно исключил. EHP-03 RESOLVED:
существующий terminal lifecycle, FAILED diagnostic + SKIPPED integration.

EHP-04 NON_BLOCKING: host scope применять в full/partial backend selection
и managed file inventory. Реализовано обоими фильтрами; production-task
Ansible тест проверяет три provider host, два Keepalived host и сохранение
другого source при partial. EHP-05 NON_BLOCKING: перенос/удаление на прежних
исключённых узлах partial не обнаруживает; ограничение записано в NET-04.2,
без нового хранилища целей. Реальная move/delete acceptance не заявлена.

После owner approval добавлены согласованные package backend defaults и
зависимость source от base provider, соответствующая существующему partial
lifecycle. Это включено в FULL DIFF review; повтор FULL PLAN не выполнялся.

## FULL DIFF review

Независимый `endpoint_haproxy_diff_review`: **APPROVE**, unresolved blocking=0.
HEAD `3efc11262c32bec8d90c503785a03dfdb359bda0`;
SHA256 актуального плана
`514AF0F5DD8721EDE9DAF6C44E4FB8800BF98C75E0C41A51318A3A0EA20D38BB`.
Reviewer fingerprint
`353EAE1C909BF40CAD539E015DBF2D639690A3B273E92B3B5AA47CA9E0E37CC0`:
tracked binary diff HEAD с LF join + path marker/content нового host-scope
test. Review scope исключает накопленные изменения UI/secrets/Kafka/DNS-client
и прежний PKI summary. После freeze менялись только evidence/status docs.

EHP-04 RESOLVED: full/partial backend и managed inventory фильтруются по
providerHostIds, три partial-фазы используют разрешённые hosts.
EHP-05 OWNER_ACCEPTED: existing-path ограничение former-host cleanup явно
записано. EHP-01/EHP-02 SUPERSEDED. Новых находок нет; лишних механизмов — 0.
Reviewer не запускал тесты/SSH. Full Core regression на момент verdict
выполнялся; реальный UI/HTTPS/repeat и move/delete остаются отдельной acceptance.

После verdict исправлены только защитные пустые значения: начальная projection
содержит haproxyHosts=[]; host expression возвращает [] при syntax-check без
hostvars. Actual empty-source/three-phase tests и standalone syntax PASS.
Выбор реальных целей не менялся. Дополнительная read-only snapshot acceptance
PASS после замены устаревшего числа catalog types проверкой покрытия deployed
types. Full Core 497 tests: 477 PASS, 19 skipped, один stale test KeyError;
исправлен выбор named HAProxy start task, isolated five-consumer recheck PASS.
Полного rerun после test-only correction не было. См. итоговый SI11 journal.
