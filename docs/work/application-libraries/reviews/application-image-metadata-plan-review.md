# Ревью плана автоматической подготовки метаданных образов

Дата: 2026-10-20. APPLICATION-IMAGE-METADATA-01. Независимый FULL PLAN review
выполнен read-only subagent с ролью `architecture-reviewer` по
[процедуре](../../../agent-procedures/review.md). Автор реализации не заменял
независимого reviewer. Дальнейшие уточнения ниже внесены автором плана;
независимый повторный review не проводился и не требовался для этих замечаний.

## Вердикт и идентичность

**APPROVE_WITH_CHANGES. Неразрешённых blocking findings: 0.**

Рассмотрен [технический план](../application-image-metadata-plan.md).
Review относится к новому предложению с одним пользовательским `image`, а не
к первоначальному варианту обсуждения с `defaults.image_artifact`.

- HEAD исходного дерева: `930d5f71a83e3be99901ea40e2af6464394526f5`.
- SHA-256 точных байтов плана при FULL review:
  `2E700BFF3ACA8EF26D7D3686CD227626063B067E9C9C3E2D8E408C2B6E1E150D`.
- SHA-256 плана после ограниченных неблокирующих уточнений AIM-P01/AIM-P02
  и ссылки на этот отчёт:
  `044132DF6E11FA852620E14649E52D59F3E2259945D8167C62C7607EAAEF660E`.

Reviewer непосредственно подтвердил переданные identities исходных контрактов:

| Файл | SHA-256 |
| --- | --- |
| docs/project-contract.md | 91F8FBD8F95CEBDC3F3B516717D5067A6BEF46C91869A502E2982CEF3612D7AC |
| contracts/artifact-source/v1alpha2/image-lock.schema.json | F7470C3E6DD7DEA6E4A860EFF56A2EF361005CE97AEBF27F0DDDD2F08AF45A28 |
| platform.core plugins/module_utils/application_runtime.py | 9C56F66ADC7CA9387CCA367870A8B30C10AD54D33ECBC6927C83EEE7F0B2AECF |
| internal/executionbundle/manifest.go | 39F380C3C3884F2B2E5791BDDBAE972FEBF97BC55A52FA62DFD0DE5C451563D8 |
| ansible-core/tools/execution_protocol.py | C10E98CABEC1E3063650D2B65E46A7D6D1BFD706BEEC1EF4520DE74223DAA3FC |

## Findings и внесённые уточнения

| ID | Severity | Замечание независимого reviewer | Уточнение автора плана |
| --- | --- | --- | --- |
| AIM-P01 | NON_BLOCKING | Исходные строки 124–125, 147–152: config Docker-save и явный alias не доказывают исходный registry manifest/index digest для offline image@sha256. Принимать только проверяемое соответствие; непроверяемый alias блокировать. Нужны отрицательный и подтверждённый положительный тесты. | Раздел 4 требует проверяемую цепочку manifest/index → platform manifest → config/imageId. Непроверяемая запись блокируется без нового acquisition/importer; подтверждённые legacy/registry identities допускают эквивалентный fallback. В матрицу bundle добавлены оба теста. Уточнение внесено; проверка реализации впереди. |
| AIM-P02 | NON_BLOCKING | Исходные строки 402–411, 425, 447: progress/cancel может подразумевать новый planning lifecycle. Текущий Create Plan синхронен, ограничен context и удерживает editMu; UI Cancel относится к execution run. | Разделы 1, 10, 13–15 явно сохраняют синхронный Create Plan, общий busy state и context/deadline/app-shutdown cancellation. Нет planning job, cancel API, polling или новой кнопки. Уточнены cleanup, timeout budget и тест недопустимости planning handle в execution Cancel. Уточнение внесено; проверка реализации впереди. |

Reviewer прямо разрешил внести эти два неблокирующих уточнения без повторного
review. Это не независимое подтверждение уже реализованных исправлений и
не основание считать будущую QA выполненной.

## Проверка сложности

Подтверждённых ненужных абстракций, дублирующих DTO/контрактов, преждевременной
области, спекулятивных возможностей и упущенных более простых механизмов: **0**.

Отдельная фиксированная подготовка нужна для сохранения target-free planner.
Индекс ссылается на существующие components без повторного SHA/size. Предусмотрены
существующий builder, потоковый hashing, Ansible orchestration и bounded HTTP/SSL;
cache/daemon/store и новый credentials subsystem не нужны. AIM-P02 ограничивает
риск ненужного расширения planning lifecycle.

## Проверенные границы и ограничения evidence

Reviewer прочитал замороженный план, root/scoped инструкции и review procedure,
применимые research/Core-review skills, project/image contracts, snapshot/plan/runtime
consumers, manifest reader, protocol staging/cleanup, source preflight, desktop
Create Plan, UI Cancel и затронутые UI design/mockup фрагменты.

Подтверждены legacy lookup по image name, recursive settings merge, private image
plumbing, fail-closed registry probe и отдельный lifecycle snapshot cleanup.
Тесты не запускались, targets и секреты не читались. Новая реализация отсутствует.

Вывод действителен для рассмотренного предложения и указанных ограниченных
уточнений. Изменение ownership, source policy, frozen identity, сетевых границ
или добавление planning subsystem меняет затронутую область review.
Следующий шаг — утверждение плана владельцем. Реализация, публикация bundle
и target acceptance требуют соответствующих разрешений; FULL DIFF и QA
после реализации остаются отдельными gates.
