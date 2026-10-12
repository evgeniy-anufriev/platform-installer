# A7 — независимое FULL PLAN review

Дата: 2026-10-12. Reviewer: `/root/a7_plan_review`, `architecture-reviewer`.
Отчёт записан основным агентом по результату read-only reviewer.
Тесты/target QA не запускались; реализация A7 не начата.

## Verdict

**BLOCK — FULL PLAN, APPLICATION-LIBRARIES-A7.** Один открытый блокер.
Вердикт сформирован независимо. Исправления после BLOCK требуют решения владельца
по [процедуре](../../../../../agent-procedures/review.md).

## Review identity

HEAD: `bb32857280ba0238a1fc5a744b3226d8d3105f75`.
План: [a7-technical-plan.md](../a7-technical-plan.md).
SHA256 плана: `531a6ca3b8a4651ac53fa051d33246e62c4902aef52c502ba1adad0babcb8c66`.
Scope: snapshot, validation, requirements, planning, private manifest,
runtime-secret inputs и fixed controller. A8 barrier рассмотрен как граница этапа.

## A7-P01 — BLOCKING, OPEN

План, строки 93–101: выбранный источник образа отнесён к resolved plan и
artifact/source authority fingerprint. Это противоречит каноническому
[execution contract](../../../../../contracts/execution-planning-and-events.md),
строки 43 и 103: repository/offline source выбирается при execution после approval;
`packageSource` не является planning decision.

Риск: перенос target-dependent source selection в target-free BuildDeploymentPlan
либо привязка approval к устаревающему результату выбора.

Минимальная коррекция: план хранит image requirements, node-scoped policy и
immutable lock/runtime identity; конкретный source определяет существующий
execution resolver и сохраняет только в RuntimeProjection/observed execution.
В QA разделить target-free requirements и execution-time fallback. Проверить,
что planning не вызывает repository probes и semantic fingerprint не зависит
от доступности repository. Рекомендация исполнителя: принять эту коррекцию
без изменения остальных границ A7.

## A7-P02 — NON_BLOCKING, OPEN

§7 откладывает конкретную таблицу версий на реализацию. До изменения closed
schemas зафиксировать текущие/новые версии action enums, secret descriptors
и capability negotiation. Новый отдельный validator не требуется.

## A7/A8 и overengineering

Запрет исполняемого manifest до A8 сохраняет обязательный барьер. Две fixed
commands повторно используют standalone entrypoints. Contract tests доказывают
descriptors, а production mixed execution остаётся будущей приёмкой.

Блокирующих замечаний по overengineering: 0. Используются существующие
snapshot/plan/manifest; второй desired state, scheduler, resume DB, rollback
subsystem и granular hook operations не предложены. Whole-scope Apply/Verify
с обычными Ansible loops соответствуют требованию скорости.

## Evidence и валидность

Прочитаны план, CURRENT_STATE, scoped Core instructions, review procedure,
contract index, A7/A8 общего плана и execution contract. Проверены текущий
отказ snapshot v2alpha1, service-only controller commands и secret-operation scope.

SHA256 execution contract:
`b7fcd2fb35b00c15080a8f1247ea64b908740f9d113bc6e309dbb11e5e87c73b`.
SHA256 общего плана:
`de03949eb954b2864886061de67116d3a07d80ab655931ba45613d4d3f9da1f6`.

Вердикт относится к указанному snapshot плана. Изменение source-selection boundary
или execution gate требует проверки затронутого scope. Автоматическое
исправление/повторное ревью после BLOCK не проводилось.

## Последующее решение владельца — 2026-10-12

Владелец принял минимальную коррекцию A7-P01. Основной агент исправил разделы
4 и 9 плана: requirements/policy/immutable identity остаются в плане;
repository/offline выбор и probes принадлежат execution RuntimeProjection.
A7-P01: исправление внесено по решению владельца, TARGETED_RECHECK не выполнена.
Исходный FULL verdict не изменён на APPROVE. A7-P02 остаётся неблокирующим.

По явному запросу владельца выполнена одна [TARGETED_RECHECK](a7-targeted-recheck.md):
APPROVE, A7-P01 RESOLVED, ноль открытых блокеров в scope. Этот FULL BLOCK
остаётся историческим вердиктом по исходной редакции.
