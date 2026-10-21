# APPLICATION-INLINE-SECRET-INPUT — FULL PLAN с presence badges

2026-10-21. Независимый architecture-reviewer: **APPROVE_WITH_CHANGES**.
Base HEAD `61c52f194d45c11d6ddd8991424026372f4190f3`.
SHA256 проверенного плана `bfe2a224600a98abe1e9268841daedf786357a9efdc47b70672bc31e51e7e9ce`.
Новый FULL выполнен для явно добавленного владельцем scope presence API.

AIS-P01/P02 остаются RESOLVED. AIS-P03 NON_BLOCKING OPEN: защищать UI от
запоздавших polling replies после смены контекста/сохранения посредством
context/request generation и сбрасывать неподтверждённый положительный статус.
Повторный PLAN review для этой рекомендации не требуется.

Overengineering: 0. Presence getter нужен, потому что descriptor discovery
очищает attachment; используется существующий Broker presence primitive и
operation DTO, один batch request, без нового store/daemon/Core resolver.
Reviewer непосредственно проверил план, contracts, Broker presence и transport
точки. Production tests/real Wails/visual QA не выполнял. Неразрешённых blockers0.
Validity CURRENT для указанного hash/scope; реализация требует FULL DIFF review.
