# A5 — независимое PLAN/FULL ревью

Дата: 2026-10-11. Reviewer: отдельный read-only `architecture-reviewer`
`/root/a5_plan_review`. Вердикт: **APPROVE_WITH_CHANGES**. Незакрытых
архитектурных блокеров: **0**. Это PLAN review; implementation/target QA не выполнены.

## Идентичность и границы

- HEAD `054668d36fdaab14d9012dba8f45337bbd5cbd04`, branch
  `codex/application-libraries`.
- Проверенный [план](../a5-technical-plan.md), SHA256
  `fbaae479a4fcbd38a0a7ba19772b3dca4e482c1e24c0d64a72cc8e351578b1d9`.
- Scope: Redis/Sentinel ACL, ClickHouse database/account/grants, Kafka SSL
  без аутентификации, shared member projection, reuse A3/A4.
- Owner decisions: минимум tasks/calls; resources scoped библиотекой, accounts
  экземпляром; без benchmark-серий; A4 закрыт owner-confirmation, не reviewer PASS.

## A5-P01 — NON_BLOCKING

Witness и native member lock оправданы ownership requirement, но исходный план
не оговаривал участие infrastructure ACL writers в одном lock. Mode 0600 также
не заменяет безопасного открытия witness/lock path.

Риск: конкурентный infrastructure Apply и application mutation могут пересечься
при сохранении ACL. Минимальная корректировка: общий per-member lock для всех
ACL mutations/file replacement, bounded timeout, re-read actual state под lock;
regular-file/no-symlink/owned-parent guards. Для CH тот же check/mutation/witness
критический участок. Native evidence должна включать app/app, infra/app и unsafe
path cases. Новый coordinator не требуется.

**Document correction:** §6.2 дописан именно этим правилом, включая одно bounded
invocation и private descriptor/path guards. Finding закрыт в тексте исполнителем;
это не новое review и не evidence работающей реализации.

## A5-P02 — NON_BLOCKING

Defaults Sentinel не были явно обозначены как HA example; current resolver не
фильтрует Sentinel members. Необходимо исключить обещание Sentinel port на member,
где Sentinel не запущен.

Минимальная корректировка: пример обозначить `sentinel-ha`, Sentinel targets
выбирать по role. Present binding без eligible targets — BLOCK. Absent optional
binding исключает из effective scope connection/account/Agent bindings вместе,
без dangling refs. Проверить mixed roles, standalone, unsupported declared
Sentinel account и absent optional binding.

**Document correction:** §4 обозначен HA, введена отдельная optional binding
`sentinel` на тот же Redis deployment; добавлены role/skip/BLOCK правила.
Finding закрыт в тексте исполнителем без повторного review.

Дополнительно после ревью YAML приведён к существующему contract:
`platform_desired_state.applicationLibraryDeployments`; package/version задаёт
library definition, поле `applicationRef` удалено из deployment overrides.
Это исправление примера, не новая модель desired state.

## Overengineering и evidence

Ненужных абстракций, дублирующих DTO/contracts и speculative scope не найдено.
Shared member projection заменяет реальные существующие allocation formulas;
явные provider role includes достаточны. Witness хранит только наблюдавшееся
ownership: username/IF NOT EXISTS не дают безопасной альтернативы. Crash gap
fail-closed. Redis без immutable account ID не защищён от внешнего admin
delete/recreate; ограничение добавлено в план.

Native SQL client и Redis CLI, с условным небольшим provider helper, допустимы.
Helper обосновать конкретным отсутствием безопасного scoped batching в pinned CLI;
общий framework не нужен. Runtime свойства ещё не доказаны.

Reviewer прочитал план, review procedure, current status, Core/project excerpts,
connection resolver, Redis/CH normalization, Redis ACL guards, CH SQL access
storage/admin/native TLS, A3 ownership и provider-stage, текущие probe operations.
Тесты и target visits не выполнялись; секреты не читались, файлы не менялись.

Вердикт относится к указанной исходной редакции. Бounded уточнения выше не
требуют нового FULL review по процедуре. Единственное первоначальное PLAN/FULL
review использовано; реализация и target mutations требуют решения владельца.
