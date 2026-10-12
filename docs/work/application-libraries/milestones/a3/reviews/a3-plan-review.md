# A3 — независимый FULL PLAN review

Дата: 2026-10-10. Reviewer: architecture-reviewer `/root/a3_full_plan_review`.
Режим: один FULL PLAN, без TARGETED_RECHECK. Реализация не разрешается отчётом.

## Проверенная идентичность

- Основа master: `ae3002907842bcdf8700bfb78305fe64d7c7e3c9`.
- a3-technical-plan.md SHA256:
  `2db518851e7f058ef0f70e56c3d43eb210ea4830049acb5fe7ccbb7b8a95a019`.
- implementation-plan.md с общим performance требованием A1–A9 SHA256:
  `8a587d28decca2beea8d0cbf34f1b45d6e00f954ad41fcd450188c2f5ad6483a`.
- Scope: standalone Ansible/Core PostgreSQL resources/accounts/grants,
  ownership/retry, protected runtime inputs, HA database-only writable discovery,
  read-only Verify, library barrier и минимизация действий.
- Не пересматривались A1/A2; Vault/Agent, Go/UI, остальные providers, execution
  planner, bundle и target mutations вне scope.

## Независимый вердикт

**APPROVE_WITH_CHANGES. Неразрешённых BLOCKING: 0.**

Review validity CURRENT для указанных fingerprints; bounded nonblocking
коррекция ниже не меняет architecture/secret/authority границы. Материальная
смена границ требует оценки по review procedure, не автоматического re-review.

## A3-P01 — NON_BLOCKING

Места проверенной версии: a3-technical-plan.md:150–161, 294–298, 330–337.

План одновременно требовал только объявленные права/отсутствие неожиданных
privileges вне scope и запрещал изменение чужих/template databases. PostgreSQL
предоставляет системные права через PUBLIC: глобальное требование отсутствия
любого такого доступа даст ложный отказ или попытку нормализации чужих ACL.
Подтверждённого нарушения безопасности нет; чужие mutations уже запрещены.

Минимальная коррекция reviewer: managed login — safe flags, no memberships,
unexpected direct grants/ownership; exact effective allowlist на управляемых
application objects. Existing login — required access без reconcile. Системные
PUBLIC defaults вне application scope не являются автоматически устраняемым
drift; опасный PUBLIC access к application objects блокируется. Новая БД —
TEMPLATE template0, без изменения templates.

Основания: [PostgreSQL 16 privileges](https://www.postgresql.org/docs/16/ddl-priv.html),
[CREATE DATABASE](https://www.postgresql.org/docs/16/sql-createdatabase.html).

QA: обычный system baseline проходит; лишний PUBLIC grant на application table
и membership managed login блокируются; соседние/системные ACL не изменяются.

Implementer disposition: **RESOLVED IN PLAN** после FULL, ограниченной правкой
разделов 4/8/10 и QA matrix. Это фиксация implementer correction, не отдельный
независимый recheck. Повторный PLAN review по этому замечанию не требуется.

## Overengineering / скорость

Блокирующих замечаний сложности: 0. Ненужные abstractions, parallel DTO/stores,
преждевременный scope, speculative frameworks и пропущенные простые механизмы: 0.
Небольшая provider роль оправдана; reuse install main.yml повторял бы infra.
Native psql, обычные vars, trusted templates, session locks и ownership markers
достаточны. Нет SQL DSL/plugin registry/scheduler/persistent cache/migration engine.

Общее уточнение владельца A1–A9 и A3 performance: discovery один раз/provider,
batch catalog/DDL/grants, stable lock order, один account login probe/run,
минимум writes на clean repeat, замеры 1/10/30 instances и нескольких hosts.
Ориентир 8–12 phase tasks не требует объединять несовместимые security boundaries;
числовой SLA не обещается. Performance gates не открывают A1/A2 на refactor.

## Evidence и ограничения

Reviewer прочитал current state/procedures/scoped instructions, canonical
Core/project contracts, общий план, A1 resolver/resources schema и PostgreSQL
defaults/native SQL/socket/credential tasks. HEAD/fingerprints проверены напрямую.
Тесты не запускались, targets/secrets не читались. Это review предложения,
не acceptance implementation/HA. Реализация A3 — отдельное owner решение.

После review в общий план добавлена только навигация на A3; в technical plan —
bounded A3-P01 correction. Проверенные исходные fingerprints сохранены выше.
