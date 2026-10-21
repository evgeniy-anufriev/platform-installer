# APPLICATION-INLINE-SECRET-INPUT — FULL DIFF

2026-10-21. Независимый architecture-reviewer. Вердикт **BLOCK**.
Блокирующих архитектурных нарушений в просмотренном коде не выявлено;
блокирует незавершённая обязательная production-boundary приёмка.

Base HEAD `61c52f194d45c11d6ddd8991424026372f4190f3`.
Manifest `.runtime/qa/inline-secret-input/diff-manifest.json`, SHA256
`c50094656cec7da46c3dc1b8d9688659115673612c5a9c2b25894263fb3a9871`.
Reviewer проверил20/20 file hashes, включая новые source/test файлы.
План в manifest: `fa9296f9629db16d2ed231a7a028c7ee250b67a0a65139207ad0bada36a6296b`.
Scope: singleton/presence API, React resource fields/header, lower-form removal,
transports/generated bindings, tests/contracts. Чужие Kafka/Core изменения
и generated dist не входят в review.

## AIS-D01 — BLOCKING / OPEN

На момент verdict подтверждены Wails build и actual React ChooseProject →
OpenProject. Не подтверждены actual resource session-save/badge, secret
exclusion from project/Review/public evidence, полный Installation regression
после inline save/reattestation, real stale/invalidation и visual1440/1024.
Go fake-clock expiry не является real2h TTL acceptance; ClearSessionCredential
проверяет invalidation, а не expiry.

Минимальная коррекция: результаты ограниченной real React/Wails приёмки на
frozen source. Невыполненные gates не помечать PASS. Код менять для закрытия
этого finding не требуется. Перенос acceptance gate — отдельное решение владельца.

## AIS-P03 — NON_BLOCKING / OPEN, частично исправлен

Generation/serialized queue и delayed-response test защищают смену revision.
Однако descriptor cache/in-flight discovery ключуются только projectRevision,
а Execution Node/runtime identity не передаются в ApplicationsPage. После
смены node backend очищает evidence: badge безопасно UNAVAILABLE, но
восстановление требует remount либо первой неудачной записи, очищающей cache.

Минимальная коррекция: node/runtime token в cache/discovery context; одно
discovery на смену контекста, presence-only polling. Проверка смены node/runtime
без смены saved revision и запоздавшего ответа. Нового store/API не нужно.

AIS-P01/P02 RESOLVED. Overengineering:0. Singleton переиспользует DTO/Broker,
presence getter оправдан отсутствием side effects, aggregate React badge
соответствует запросу; новых persistence/desired-state/lifecycle слоёв нет.

Непосредственно исследованы весь manifest scope, diff/new files, exact
admission guards, Broker presence, React mapping/lifecycle, tests/transports
и contracts. Parent сообщил Go tests/vet, frontend full271, focused33 и
build/typecheck/lint PASS; reviewer tests не запускал и target/secret material
не открывал. Validity CURRENT для manifest; QA evidence не требует нового FULL.
Неразрешённых blockers: **1**. Автоматическая работа остановлена по процедуре.
Owner decision требуется для продолжения и применимого ограниченного recheck.
