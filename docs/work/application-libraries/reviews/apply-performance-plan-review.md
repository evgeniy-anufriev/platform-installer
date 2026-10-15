# Apply performance — независимый FULL PLAN review

Дата: 2026-10-15. Reviewer: `architecture-reviewer`, task
`apply_performance_plan_review`. Режим: один FULL PLAN, read-only.

**Вердикт: APPROVE_WITH_CHANGES. Нерешённых BLOCKING: 0.**

## Позднейшее решение владельца: P2

После review владелец отложил весь новый параллелизм до измерения Apply после
остальных простых оптимизаций. P2 исключает AP3/probe runner/workers; существующие
последовательные проверки сохраняются. SHA-256 P2:
`4AF301FD424CAA5946FAE7DEA19E2C8795AB695521EA51A84D79C665D102B5D6`.
Это запись сужения scope главным агентом, не новый независимый review. Вердикт
и overengineering assessment ниже относятся к проверенной P1; они не разрешают
реализацию отложенного runner. Нового review не проводилось.

## Проверенная идентичность

- Base/HEAD: `3fcf54c83ec13dcb2fda035862a5305c843a1095`.
- Документ: `docs/work/application-libraries/apply-performance-plan.md`, P1.
- Проверенный SHA-256: `85F7F139F722F42C9069C7BE892E00F3D5A3F89C1A9244B7C65F4D64BE016400`.
- Scope: AP0–AP4 — transport, scoped provider batching, bounded probes, QA/cleanup.
- Реализация не оценивалась и не разрешалась; target-команды/тесты не запускались.

## Findings и bounded corrections

| ID | Severity | Независимое замечание | Коррекция после review |
| --- | --- | --- | --- |
| AP-P01 | NON_BLOCKING | DNS UPDATE prerequisites не дают TTL-CAS; различить NXDOMAIN и owner без A/CNAME | §6.3 явно ограничен existence/type/RDATA CAS, TTL проверяется до/после без обещания атомарности; prerequisites разделены |
| AP-P02 | NON_BLOCKING | При замене uri сохранить proxy/no-proxy и timeout semantics, не только TLS/status | §7.2 и P01/P09 требуют A/B прежнего пути и runner, GET/Host/proxy/no-proxy/redirect/TLS/status/timeout; неэквивалентный режим не получает acceptance |

Обе коррекции внесены главным агентом внутри согласованной архитектуры; повторного
review не проводилось и новый review verdict не подразумевается. Reviewer прямо
указал, что эти уточнения не требуют повторного FULL review.

SHA-256 документа после этих двух bounded corrections:
`28636C47F52E1E5A4BFB1DE6CAB5D5ED4E93BFCF390E4CC0DCAE48E2B2714A67`.

## Overengineering assessment

Ненужных абстракций, дублирующих DTO/хранилищ, преждевременного scope и спекулятивных
механизмов не обнаружено. Один узкий synchronous probe runner обоснован требованием
ограничить concurrency внутри observer host; Ansible loop последовательный,
unbounded remote async добавляет lifecycle и cleanup. Реальный remote Cancel cleanup
остаётся обязательным gate: остановка локального ssh сама по себе его не доказывает.

Переиспользуются штатные pipelining/mux, list resolvers, candidate/archive/reconcile
и nsupdate. Нет health cache, daemon, нового scheduler или distributed rollback.

## Evidence и ограничения

Reviewer прочитал root/scoped instructions, review procedure, план, canonical
architecture/project/execution contracts и релевантные controller, endpoint,
HAProxy/BIND tasks. Подтвердил кодом custom SSH args без multiplexing,
последовательный per-source lifecycle и nsupdate на RRset.

Тайминги и B4 target/regression evidence были предоставлены; reviewer их повторно
не выполнял. Секретные материалы не открывал. Другие dirty files не оценивались.

Следующий шаг — решение владельца. Реализация HIGH-RISK требует одного FULL DIFF
review и реальной QA по плану; этот отчёт не заменяет их и не разрешает target mutations.
