# Архитектурный review UI-01F5

Вердикт: **BLOCK**

Режим: **PLAN / FULL**  
Milestone: **UI-01F5**  
Рассмотренный план: `docs/ui-01f5-architecture.md`  
SHA-256: `423335767D508AB1BBAEE67431C9B67F0307DCC64A6DC9DA900F7857B8FE7C11` — подтверждён.  
HEAD/base commit: `08d2b6c42af5d56302a4737335ce0b26fe16014e` — подтверждён.  
Worktree на момент review: новый F5-план и обновление статуса/ссылки F4/F5 в
`docs/ui-01f-architecture.md`; reviewer изменений не вносил.

## Findings

### UI01F5-PLAN-001 — BLOCKING / OPEN

Место: `docs/ui-01f5-architecture.md`, разделы 9.1–9.2.

Доказательство: план объявляет `ProjectVerification` источником revision/runtime
freshness, но состояния `CURRENT` и `INVALID` проверяют только равенство project
revision и отсутствие draft. `ProjectVerification` уже содержит
`projectIdentity`, `executionNodeId` и runtime identity. `VerifyProject`
сохраняет snapshot, привязанный к конкретному Execution Node, однако
`SelectExecutionNode` меняет выбранный узел без сброса текущих `Verification` и
`Snapshot`.

Влияние: после успешной Verify оператор может выбрать другой Execution Node, а
F5 продолжит показывать FQDN/provider/VIP предыдущего узла как `CURRENT`. Это
нарушает требование показывать provider/VIP только из свежего Core evidence.

Минимальная коррекция:

- расширить freshness key до project identity + project revision + текущей
  Execution Node selection identity + принятой runtime evidence;
- после успешной смены Execution Node немедленно переводить frontend preview в
  `STALE` или `NOT_VERIFIED`;
- не принимать результат асинхронной `VerifyProject`/`CurrentProject`, если во
  время запроса сменился проект или Execution Node;
- добавить эти случаи в acceptance tests.

Новые DTO, API, Core operation или persistence для исправления не нужны.

Проверка: frontend/App-тесты смены узла после Verify и смены узла/проекта между
`VerifyProject` и `CurrentProject`; старые FQDN/VIP не отображаются как current.

Owner decision: требуется решить, входит ли bounded invalidation fix в F5 или
оформляется как prerequisite.

### UI01F5-PLAN-002 — NON_BLOCKING / OPEN

Место: `docs/ui-01f5-architecture.md`, раздел 9.3.

Доказательство: план требует ограничивать provider rows и virtual addresses, но
не фиксирует конкретные пределы.

Влияние: разные реализации могут по-разному трактовать bounded projection и
truncation acceptance.

Минимальная коррекция: зафиксировать именованные конечные лимиты и единый
truncation indicator.

Проверка: тесты на ровно limit и limit+1 для providers и virtual addresses.
Повторный architecture review для этой non-blocking коррекции не требуется.

## Обязательный overengineering analysis

Фактических overengineering findings: **0 BLOCKING / 0 NON_BLOCKING**.

- Ненужные абстракции: отсутствуют. Pure presentation selector оправдан
  безопасной проекцией динамического `ProjectSnapshot`; прямой render
  произвольных maps был бы менее безопасен.
- Дублирующие contracts/DTO: отсутствуют. План переиспользует v1alpha5,
  `ManagedProjectView`, `ProjectCatalogView`, `ProjectSnapshot` и
  `ProjectVerification`.
- Преждевременный scope: отсутствует. Provider mutation, service editor,
  execution, новые Core operations и UI-01F6 исключены.
- Спекулятивные возможности: отсутствуют. Нет generic form framework, graph UI,
  polling, cache или UI-расчёта provider/VIP.
- Упущенный более простой механизм: отсутствует. PLAN-001 — недостающий
  freshness guard, а не избыточный механизм; минимальное исправление использует
  уже существующие identity fields и App state.

## Evidence

Проверено напрямую:

- `AGENTS.md`, `CURRENT_STATE.md` и роль architecture reviewer;
- F5-план и его SHA-256;
- parent F architecture и F1–F4 contracts;
- UI design и mockup Entry points;
- v1alpha5 reducer/writer/reference/catalog guards;
- `ProjectOpenResult`, `ProjectVerification`, `CurrentProject`, `VerifyProject`
  и `SelectExecutionNode`;
- Core endpoint/provider projection и ProjectSnapshot schema.

Тесты не запускались: это documentation-only PLAN review. Выполнены read-only
проверки hash, Git identity/status и точечная инспекция. Target hosts и секреты
не затрагивались.

## Review validity

Статус: **CURRENT** для указанного SHA-256 и base commit.

Review станет STALE при изменении F5-плана, owner scope, freshness/invalidation
архитектуры или контрактов `VerifyProject`/`CurrentProject`/Execution Node
selection. Реализация этим PLAN review не проверена и не авторизована.

Точный unresolved blocking count: **1**.

Следующее действие: владелец выбирает bounded invalidation fix в F5 либо как
prerequisite. После owner-approved коррекции разрешён один
`TARGETED_RECHECK` только `UI01F5-PLAN-001` и непосредственно затронутой
freshness boundary. Полный второй review не запускается.

## TARGETED_RECHECK addendum

Вердикт: **APPROVE**  
Режим: **PLAN / TARGETED_RECHECK**  
Finding scope: только `UI01F5-PLAN-001` и непосредственно прилегающая
selection/freshness/late-response boundary.  
Проверенный SHA-256 плана:
`03FE74438E75B21BEA9CEB78C08847CF1E637D92523AD602D385F85B654EF731`.  
Base commit/HEAD: `08d2b6c42af5d56302a4737335ce0b26fe16014e`.

### UI01F5-PLAN-001 — BLOCKING — OPEN → RESOLVED

Подтверждено:

- freshness key связывает project identity/revision, effective Execution Node
  identity, `verification.executionNodeId` и полный runtime tuple;
- пустые или частичные node/runtime evidence запрещены для `CURRENT` и
  `INVALID`;
- реальная смена выбранного узла очищает только in-memory `Snapshot` и
  сбрасывает `Verification` в существующее `UNVERIFIED` под App lock;
- повторный выбор того же effective node является no-op;
- project/node generation и request token закрывают поздние ответы между
  Verify, `CurrentProject`, сменой проекта/узла и новым Verify;
- acceptance покрывает смену узла, same-node no-op и late-result rejection.

Owner decision: `OWNER-UI-F5-01`; bounded invalidation включена непосредственно
в F5. Новые DTO, API, persistence или Core operation не введены. Новых
блокирующих регрессий не обнаружено.

Implementation QA ещё не выполнялась и остаётся acceptance gate F5.

### Overengineering targeted recheck

**0 BLOCKING / 0 NON_BLOCKING findings.** Используются существующие
`ProjectVerification`, `ExecutionNodeContext`, `CurrentProject` и App lock.
App-local generation/request guard — минимальный механизм для отклонения уже
возвращённого, но ещё не опубликованного frontend response; одной очистки Go
state для этой гонки недостаточно.

Review validity: **CURRENT** для указанного SHA-256. Незакрытых блокеров: **0**.
Автоматический TARGETED_RECHECK budget исчерпан; дополнительный review требует
отдельного основания и авторизации.

## Post-review owner amendments

После TARGETED_RECHECK владелец зафиксировал две дополнительные границы:

- `OWNER-UI-F5-02`: `INVALID` показывает safe findings, но никогда не
  показывает authoritative FQDN/provider/VIP preview;
- `OWNER-UI-F5-03`: React остаётся presentation-only. Проверка показала, что
  существующие `coreadapter.Snapshot` endpoint/provider поля являются
  динамическими `map[string]any`, а ProjectSnapshot schema не задаёт им
  collection bounds. Поэтому план использует один минимальный strict
  typed/bounded Go `GetEndpointPreview()` вместо разбора raw snapshot maps в
  React.

Новая SHA-256 плана:
`DF3DCA1E4DF8F49696F15C0272A788AF4F22F519100044183AA4221B0FEBF284`.

Эти owner amendments внесены **после** проверенной ревизии и не были предметом
предыдущего TARGETED_RECHECK. Исторический результат
`UI01F5-PLAN-001 OPEN → RESOLVED` сохраняется, но review validity для текущего
полного плана теперь **STALE**. Автоматический review budget уже исчерпан;
новый review не запускается без отдельной авторизации владельца.
