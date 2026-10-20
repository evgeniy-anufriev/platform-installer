# Kafka SCRAM admin — TARGETED_RECHECK PLAN

Дата: 2026-10-20. Независимый reviewer:
`/root/scram_compatibility_plan_review`, роль `architecture-reviewer`.
Основание: владелец принял KS-P04/KS-P05 в ответ на вопрос об обеих коррекциях
и одном целевом повторном review. Вердикт: **APPROVE**, unresolved BLOCKING **0**.

Проверен [план](../kafka-scram-plan.md), SHA-256
`8DF2F1F37AB98328A3BD4CDE39FC3B004B29ED77231511468EF2C6643F98FAF5`;
HEAD `930d5f71a83e3be99901ea40e2af6464394526f5`, dirty tree.
Scope ограничен KS-P04/KS-P05 и непосредственно затронутыми границами.
Исходный [BLOCK](kafka-scram-admin-plan-review.md) остаётся историческим.

KS-P04: OPEN → RESOLVED на уровне плана. §6 требует regular config,
единственной финальной строки super.users, active/stable MainPID/start timestamp,
точного config path в JVM argv и запуска строго позже config mtime.
Повторное наблюдение отвергает смену процесса. Bootstrap recovery перезапускает
всех участников и подтверждает runtime proof до следующих stages.

KS-P05: OPEN → RESOLVED на уровне плана. Opt-in deployment-bound public identity
выдаёт Core через общий существующий алгоритм. Исходный SecretRef и файлы
deployment-scoped; library projection использует публичный runtime alias и
не публикует неоднозначный raw alias. Go не вычисляет identity: существующая
pending custody связывает deployment/purpose password с Core descriptor и
передаёт его через существующий password map/lease. Два Kafka deployments
с одинаковым логическим SecretRef получают независимые identities/files.

Overengineering findings: 0. Второй secret store, transport или lifecycle
subsystem не добавлены; общий identity helper устраняет дублирование алгоритма,
finalization использует штатные Ansible/systemd/proc наблюдения.

Reviewer проверил чтением план и непосредственно затронутые Core/Go/Ansible
границы. Сообщённые parent Core75/Go PASS самостоятельно не повторял.
Дополнительные native/transport тесты на момент envelope ещё выполнялись;
их PASS не утверждается. Стенд и секретные значения не посещались.
Это **не FULL DIFF approval и не SCRAM acceptance**. Запрет установки сохранён.

Следующее действие: продолжить разрешённую реализацию с обычными проверками.
Этот recheck не запрашивает новый FULL PLAN review. Его validity относится
к указанной PLAN revision и KS-P04/KS-P05.
