# APPLICATION-LIBRARIES-B — FULL PLAN review

Дата: 2026-10-14. Независимый read-only `architecture-reviewer`,
agent `/root/b_plan_review`. Вердикт: **APPROVE_WITH_CHANGES**, **0 BLOCKING**.
Реализация/target QA не разрешены этим вердиктом.

## Identity и scope

План: [b-technical-plan.md](../b-technical-plan.md).
Проверенный reviewer SHA256:
`C846C43D299B179C6AA235617284CCA176AB16BDE9322268266D4DE17DBAFB7F`.
База `cee36a3f737f70eb10347f0e3c50bfed398bf188`.
Scope: весь B0–B4, cross-run admission, fingerprints/coverage, локальная проекция,
remote evidence, writer/import/export, lifecycle и acceptance boundaries.
Владелец запросил подробный MD и отдельный запуск библиотек после Verify всей инфраструктуры.
Вердикт сформирован независимо, ожидаемый результат reviewer не задавался.

## Findings

### B-P01 — NON_BLOCKING, OPEN в reviewed revision

§4.2/5.2/6, исходные строки185–210: generation invalidation не уточняла, относится
«первая mutation» ко всему run или к каждой операции. Возможны ненужная потеря
Verify A при последующем Apply B или слишком широкое сохранение старого evidence.
Минимальная коррекция: определить generation для Apply A/Verify A/Apply B/Verify B,
момент публикации evidence и recovery при crash между result/index. Неполное
обновление допускает потерю readiness, но не ложный PASS. Новая transaction subsystem не нужна.
Проверки: указанная последовательность, FAILED после Verify A, crash result/index,
последующий Verify-only.

### B-P02 — NON_BLOCKING, OPEN в reviewed revision

§7/11/12, исходные строки215–218/242–247: два заявленных mode не объясняют положение
Verify-only, который также имеет fresh plan/approval/run.
Минимальная коррекция: два mode относятся к установке; Verify-only — отдельный
versioned scope/capability того же lifecycle. Ни обхода planning, ни fallback на Apply.
Проверки: только verification operations в manifest, unsupported runtime ничего
не запускает, approval покрывает exact scope.

## Overengineering

Ненужные abstractions:0; подтверждённые duplicate contracts/DTO:0;
преждевременный scope:0; speculative mechanisms:0; missed simpler mechanisms
с blocking impact:0. Отдельный local JSON сохраняет evidence после замены last-run;
remote bounded index агрегирует несколько runs без неограниченного scanning.
Existing journal namespace/atomic replace/active-run admission достаточны;
distributed lock service, daemon, новая БД и generic selective installer не нужны.
Полный infra fingerprint — явный компромисс простоты против selective reuse.

## Evidence и ограничения

Reviewer прочитал root/scoped AGENTS, CURRENT_STATE, review procedure, полный план,
общий план B, execution/project/architecture contracts, controller barrier/materialization/
dispatch, active-run admission, local_run_record.go, shared UI rules и installation mockup.
Code подтверждает same-run barrier и local record одного run. Тесты не запускались,
targets не опрашивались, файлы и secret material не изменялись/не читались.
A9 — историческое evidence, не доказательство новой функциональности.
Замечена предсуществующая несогласованность старого application snapshot текста
project contract с A7/A8: синхронизировать при B0 contract update.

Review CURRENT для указанного SHA. Изменение authority/reuse/invalidation/trust/locks
или execution scope требует оценки затронутого review. B-P01/B-P02 — ограниченные
уточнения; новый FULL review для них не требуется. Следующее действие — согласование владельцем.

## Действия автора после отчёта

В §6 добавлены run-level generation, terminal publication и result-before-index
ordering; в §7 — explicit Verify-only scope/capability; добавлены B-Q21–22.
Это авторские corrections, не независимое RESOLVED/re-review. Исходный вердикт
и fingerprint сохранены; zero blockers не означает разрешение реализации.
