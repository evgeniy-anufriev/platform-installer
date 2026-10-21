# APPLICATION-INLINE-SECRET-INPUT — FULL PLAN review

2026-10-21. Независимый read-only architecture-reviewer. Вердикт **BLOCK**.
План: [application-inline-secret-input-plan.md](../application-inline-secret-input-plan.md).
Base HEAD: `61c52f194d45c11d6ddd8991424026372f4190f3`.
SHA256 плана: `b980acbe43d76b69956b3f890f31d259340f44a03229ef175ca762169bffda60`.
Validity CURRENT для указанного плана; реализация не начата.

## AIS-P01 — BLOCKING / OPEN

План предлагает исключить account requirements из нижней формы, сохранив
полный библиотечный API для старых вызовов и singleton только для
APPLICATION_SECRET. `ApplicationSecretInputs` отправляет значения лишь
отображаемых полей; backend требует полный набор библиотеки. Inline values
не возвращаются клиенту. Поэтому после исключения account requirements
оставшаяся shared/admin форма получит отказ: обязательных account values
нет в payload. Точное сопоставление Core refs не устраняет конфликт.

Минимальная коррекция на решение владельца: сохранить нижнюю полную форму,
включая account requirements, как явно обозначенный дополнительный полный
ввод. Основной ввод остаётся inline. Удаление дублирования не вводить в этот
scope. Не менять старый exact-set API и не читать значения из Broker.

Проверка: inline account save → полный нижний ввод shared/admin и accounts →
reattestation; отрицательный тест missing shared ref остаётся обязательным.

## AIS-P02 — NON_BLOCKING / OPEN

Уточнить expiry/session wording: credentialBindingLocked проверяет открытый
проект, а не действующую SSH lease. Существующий pending setter намеренно
допускает ввод без target credential и обновляет pending TTL при записи.
План должен различать descriptor evidence, pending TTL и SSH lease,
сохранять pending admission и не вводить новый запрет при expiry SSH lease.
Отрицательные expiry-тесты должны называть конкретный объект.

## Overengineering и evidence

Доказанных избыточных механизмов: 0. Используются существующие DTO, Core
projection и Broker merge/promotion; отдельные API/store/lifecycle services
не нужны. Меньшая альтернатива AIS-P01 — оставить полную дополнительную форму
ценой ограниченного дублирования.

Reviewer непосредственно проверил инструкции, CURRENT_STATE, review procedure,
план, architecture/project/application secrets contracts, UI design/mockup,
credential editors, input DTO/admission, descriptor validation, Broker
merge/promotion и exact-scope tests. Production tests/Wails/Core/визуальная
приёмка не выполнялись; runtime secret material и target hosts не открывались.
Parent plan-only git diff --check PASS.

Неразрешённых blockers: **1**. Автоматическая реализация остановлена по
review procedure. Владельцу переданы AIS-P01, минимальная коррекция и AIS-P02.
Коррекции и один TARGETED_RECHECK требуют решения владельца; повторный FULL
review автоматически не запускается.
