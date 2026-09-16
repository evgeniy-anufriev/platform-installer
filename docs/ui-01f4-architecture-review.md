# Архитектурный review UI-01F4

Вердикт: **APPROVE_WITH_CHANGES**

Режим: **PLAN / FULL**  
Milestone: **UI-01F4**  
Рассмотренный план: `docs/ui-01f4-architecture.md`  
SHA-256: `855E78FC9933B683DD355C4DFD6EFE7E212271F55B7BD03E1C4F6C314CFE61B1` — подтверждён.  
HEAD: `a516228551a7bff849d0a126d900dd37c1a9ccf8` — подтверждён.  
Worktree на момент review: план был единственным untracked-файлом; reviewer изменений не вносил.

## Findings

### UI01F4-PLAN-001 — NON_BLOCKING / OPEN

Место: `docs/ui-01f4-architecture.md:400-416`, `:456-466`.

Доказательство: план требует сохранения активной вкладки, deployment/host
selection при навигации, но implementation shape не фиксирует владельца этого
состояния. Текущий `TopologyPage` хранит `selectedID` и локальное состояние, а
`App` условно размонтирует страницы (`frontend/src/TopologyPage.tsx:109-111`,
`frontend/src/App.tsx:628-657`).

Влияние: при переходе на Servers/Project и обратно состояние вкладки и выбора
может потеряться, что нарушит заявленный UX-контракт.

Минимальная коррекция: явно поднять `activeTopologyTab`,
`selectedDeploymentId` и `selectedHostId` в существующий App-level state либо
гарантировать сохранение mounted-компонента; определить сброс и revalidation
при open/close, discard и commit.

Проверка: frontend-тесты перехода Topology → Servers/Project → Topology,
project switch, discard и commit с сохранением/сбросом selection согласно
плану.

### UI01F4-PLAN-002 — NON_BLOCKING / OPEN

Место: `docs/ui-01f4-architecture.md:286-305`, `:374-382`.

Доказательство: для `MEMBER_SCOPED` By servers должен создать одну новую строку
с выбранным host как default, но не определено, как обеспечивается обязательный
уникальный `memberId`. План одновременно указывает, что новые IDs редактируемы
пользователем.

Влияние: возможен неясный UX при добавлении placement с сервера: пустой или
дублирующийся ID либо неявное UI-генерирование идентификатора.

Минимальная коррекция: зафиксировать, что `memberId` для новой строки вводится
явно и проверяется на непустое значение/уникальность до Apply; либо описать
детерминированный UI-only candidate ID без его трактовки как Core-семантики.
Для `HOST_SCOPED` synthetic `memberId` по-прежнему запрещён.

Проверка: acceptance Add placement из By servers, duplicate-ID rejection и
подтверждение, что emitted command содержит только полный `members[]` без
per-host patch.

## Обязательный overengineering analysis

Фактических blocking overengineering findings: **0**.

- Новая desired-state persistence: отсутствует; используется существующий
  `EditSession` и guarded transaction.
- Новые Go/Wails contracts или DTO: отсутствуют; v1alpha5 переиспользуется.
- Дублирование mutation seam: отсутствует; By services и By servers используют
  один complete-placement editor и один reconcile intent.
- Generic framework/state manager/event bus: явно исключены; bounded selectors
  достаточны.
- Service-specific UI semantics: отсутствуют; placement kind и roles приходят
  из pinned catalog.
- Premature scope: endpoint/provider/settings/execution остаются за пределами
  F4.
- Сложность interaction: одна complete-placement modal и один intent на
  deployment — соответствует минимальной архитектуре.

## Evidence

Проверено напрямую:

- `.codex/agents/architecture-reviewer.toml`;
- `AGENTS.md`;
- `CURRENT_STATE.md`;
- `docs/ui-01f4-architecture.md`;
- `docs/ui-01f-architecture.md`;
- F1–F3 architecture documents;
- `docs/ui-design-01.md`;
- `docs/ui-design-01-mockups.html`;
- текущие App/Topology/backend types и F2 placement contracts/reducer
  references.

Тесты и implementation QA в рамках PLAN review не запускались; reviewed
implementation отсутствует.

## Review validity

Статус: **CURRENT**.

Review становится STALE/PARTIALLY_INVALIDATED при:

- изменении содержимого плана или несовпадении указанного SHA-256;
- изменении canonical-state ownership, v1alpha5 contract, EditSession/Save
  lifecycle или catalog authority;
- добавлении Go/Wails/backend mutation seam;
- изменении F2/F3 baseline, влияющем на placement reducer, command limits или
  recovery semantics.

Точный unresolved blocking count: **0**.

Следующее действие: передать владельцу два открытых non-blocking исправления;
повторный review для них не требуется автоматически.

## TARGETED_RECHECK addendum

Milestone: **UI-01F4**  
Режим: **PLAN / TARGETED_RECHECK**  
Проверенный план: `docs/ui-01f4-architecture.md`  
SHA-256: `8FC87B329A2B23A458DD38EB805327C59C5A169B696FE48399FD235F8F8D97DC` — подтверждён.  
HEAD: `a516228551a7bff849d0a126d900dd37c1a9ccf8` — подтверждён.  
Область: только `UI01F4-PLAN-001`, `UI01F4-PLAN-002`.

### UI01F4-PLAN-001 — PASS

Lifecycle: `NON_BLOCKING / OPEN` → `RESOLVED`.

Evidence: план §12, строки 407–423.

`App` явно владеет `activeTopologyTab`, `selectedDeploymentId` и
`selectedHostId`; определены сохранение при navigation/unmount, сброс при
close/open/switch, revalidation после acknowledged intent, discard и успешного
Commit refresh, fallback при исчезновении ID и очистка при
`COMMITTED_REFRESH_FAILED`.

### UI01F4-PLAN-002 — PASS

Lifecycle: `NON_BLOCKING / OPEN` → `RESOLVED`.

Evidence: план §8.2, строки 286–300; §9, строки 326–339; §11, строки 364–382;
QA §16.1, строки 489–507.

Для каждой новой member-scoped строки `memberId` вводится оператором, поле
изначально пустое, применяется закрытая grammar и проверка уникальности среди
всех строк до Apply. Apply отправляет один полный reconcile после
acknowledgement. Для By-servers явно запрещены autogenerated и derived IDs;
host-scoped форма не содержит `memberId` и synthetic identity.

### Overengineering

Новых blocking overengineering findings: **0**. В проверенной области нет
второй persistence, DTO, mutation seam, reducer или state manager.

Тесты не запускались: это проверка плана; QA остаётся acceptance-критерием
реализации.

### Итог

Exact unresolved blocking count: **0**.

Verdict: **APPROVE** — только для данного targeted scope; это не повторная
полная проверка плана.

Review validity: **CURRENT** для указанного SHA и HEAD.

Recheck становится stale/partially invalidated при изменении SHA или
содержания плана, изменении App-level lifecycle/selection ownership, member-ID
grammar/authority, v1alpha5 placement contract, F2 reducer/writer semantics
либо добавлении нового backend/persistence mutation boundary.

## TARGETED_RECHECK addendum — current owner decision

Milestone: **UI-01F4**  
Mode: **PLAN / TARGETED_RECHECK**  
Reviewed scope: only `UI01F4-PLAN-001`, `UI01F4-PLAN-002`.  
Reviewed plan: `docs/ui-01f4-architecture.md`  
SHA-256: `FBD2CD1E80F0769DFB2DC996A467A7388469076761CB2B95D8AE9F1887B3C3C7` — verified.  
HEAD: `a516228551a7bff849d0a126d900dd37c1a9ccf8` — verified.

### UI01F4-PLAN-001 — PASS

Lifecycle: `RESOLVED`.

Evidence: plan §12, lines 415–428. `App` owns controlled active Topology tab,
selected deployment ID and selected host ID. The plan defines survival across
conditional unmount/navigation, resets on project close/open/switch,
revalidation after acknowledged intent, Discard and successful Commit refresh,
fallback after a selected ID disappears, and clearing alongside the stale view
on `COMMITTED_REFRESH_FAILED`.

### UI01F4-PLAN-002 — BLOCK

Lifecycle: `UNRESOLVED`.

Evidence: plan §8.2, lines 294–307; §11, lines 392–395; QA §16.1, lines
494–498. The proposed UI-only, editable smallest-unused `<serviceType>-<n>`
candidate is shared by both entry points and correctly avoids service
configuration, hostname parsing, Core semantics, automatic host-change rewrite,
service-specific branches and a second mutation path. However, exact catalog
`serviceType` is not guaranteed to form a v1alpha5 `memberId`: catalog
identifiers allow `_`, `.` and up to 128 characters, while v1alpha5 requires
`^[a-z0-9][a-z0-9-]{0,62}$`. Thus a valid catalog service type such as
`pg_auto_failover`, or a longer valid service type, yields an invalid generated
candidate. The plan validates only before Apply and does not define the required
safe handling of an invalid initially generated candidate.

Smallest correction: define the fail-closed UI behavior for a catalog
`serviceType` whose literal `<serviceType>-<n>` does not satisfy v1alpha5
`memberId` grammar. Do not silently normalize, truncate or derive a different
identity without an explicit owner decision.

### Overengineering

Blocking overengineering findings: **0**. In the reviewed scope the design uses
one existing shared editor, one bounded candidate rule and one existing
intent/reducer/Save lifecycle. It introduces no DTO, persistence, framework,
service branch or topology semantics.

### Verdict and limits

Verdict: **BLOCK** for this TARGETED_RECHECK.  
Exact unresolved blocking count: **1**.

This review was read-only and examined only the two requested plan findings and
their immediate v1alpha5/catalog boundary. No implementation or runtime QA was
run. Per the review budget, no further automatic architecture review is
authorized; return the correction decision to the owner.

## TARGETED_RECHECK addendum — deterministic memberId candidate

Milestone: **UI-01F4**  
Mode: **PLAN / TARGETED_RECHECK**  
Reviewed scope: only `UI01F4-PLAN-002`.  
Reviewed plan: `docs/ui-01f4-architecture.md`  
SHA-256: `2F85A9659FB6EF184D1D51A2BA67C874E19FCB811FE9C3B3E36889A2AAB1BA5E` — verified.  
HEAD: `a516228551a7bff849d0a126d900dd37c1a9ccf8` — verified.

### UI01F4-PLAN-002 — PASS

Lifecycle: `UNRESOLVED` → `RESOLVED`.

The owner-authorized UI-only candidate is contract-safe: it lowercases the
service type, maps `_` and `.` to `-`, collapses repeated hyphens, trims edge
hyphens and limits the base so `<base>-<n>` is no longer than 63 characters.
It selects the smallest unused positive `n`; an empty normalized base leaves
the explicit manual field empty. Before Apply, the final value must still be
non-empty, satisfy the closed v1alpha5 identifier grammar and be unique within
the deployment.

Evidence: plan §8.2 and §16.1; `contracts/project-edit/v1alpha5/schema.json`
`$defs.id`. The rule is an editable presentation convenience only: it changes
neither catalog/service configuration nor Core identity, does not parse host
names, contains no service-specific branch, and reuses the existing complete
reconcile/EditSession mutation seam. Existing member IDs remain read-only.

### Overengineering

Blocking overengineering findings: **0**. No DTO, persistence, API, framework,
reducer/state manager or parallel mutation path is introduced.

### Verdict and limits

Verdict: **APPROVE** for this `PLAN / TARGETED_RECHECK`.  
Exact unresolved blocking count: **0**.

This was an independent read-only plan recheck. No tests, host contact or
implementation review were performed. It is CURRENT only for the SHA and HEAD
above and becomes stale if the candidate rule, v1alpha5 identifier contract,
placement mutation boundary or the reviewed plan changes.
