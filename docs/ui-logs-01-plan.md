# UI-LOGS-01 — implementation plan

Status: owner-revised scope; targeted architecture recheck APPROVE_WITH_CHANGES (no blockers)

## Goal and owner decision

Implement the currently disabled «Журналы» navigation item using the
owner-selected table-and-right-details design. The page is a session-scoped
view of the latest Installer execution only, not historical run browsing.

The owner revised the earlier historical-history scope: a new execution clears
the previous UI event list; replacing/closing the project clears it; and a
process restart/reopen of Installer starts with an empty Logs page. During one
Installer process, the current run's events remain visible after it reaches a
terminal state until the next run or project-context reset.

## Current evidence and contract

- `docs/roadmap.md` UI-LOGS-01 and `docs/ui-design-01.md` currently describe
  historical run browsing. This plan explicitly supersedes that part of scope
  subject to owner acceptance and roadmap/design synchronization.
- `frontend/src/UtilityPages.tsx` already receives the in-memory
  `InstallationEventView[]` and current run ID. `App.tsx` clears the list on
  Start; it previously capped the list at the latest 512 events. The app's
  React state is not restored after process restart.
- Existing Go/Wails event subscription already transports safe normalized
  execution events. The existing Core and Go observer/mirror bounds are 8192
  events; supporting runs above that limit requires a separate coordinated
  Core/Go bound change. No run-history query, persistent history index, or
  event persistence is needed for this session-scoped view.
- The existing `.runtime`/cache Execution Node event mirror remains unchanged:
  it supports run observation/recovery and is not the Logs page's data source.
  «Журналы» must not read it on reopen or delete it to simulate a cleared UI.

## Proposed implementation

1. Keep the existing current-run event subscription and safe
   `InstallationEventView` boundary. Render rows in authoritative event
   sequence order; use the existing run ID/state for the compact context.
2. Replace the temporary event cards with the selected table layout: filters
   («Все», «Ошибки», «Предупреждения»), text search, columns «Время»,
   «Этап / задача», «Сервис», «Узел», «Результат», and a right details panel
   for the selected event. Details use only safe message, task, action/phase,
   elapsed, error code/summary and redaction indicators already in the view.
   Related events may be grouped only by existing run/sequence/action/task
   identity; do not infer infrastructure or deployment semantics.
3. Add clear no-run/no-events states and distinguish an active run, a
   completed run, and an observer/history-gap diagnostic using existing safe
   lifecycle/event state. Do not display old runs as available after reopening.
4. Paginate the complete in-memory current-run stream at 512 rows per page;
   do not evict older UI events at a page boundary. Preserve the separate
   upstream Core/Go observer limit and report a genuine history gap if one
   is observed.
5. Keep Logs read-only. Do not add filesystem access, history persistence,
   execution protocol changes, or Go project-operation events. Project
   open/save/verify are not currently durable run-bound events; do not
   synthesize them from UI/debug messages.

## Scope and non-goals

- In scope: enable Logs navigation; current-run table, filters/search, selected
  details, lifecycle/empty/gap states; focused React tests and
  design/roadmap updates.
- Out of scope: historical run list, reopening past runs, cross-process
  retention, remote journal listing, new protocol/Go/Wails APIs, export/delete,
  project audit trail, deleting operational event mirrors, V1 reuse, and
  changes to Installation → Execution/Result behavior.

## Safety and acceptance

- Render only safe `InstallationEventView`; do not expose secrets, runtime
  paths, raw Ansible output or non-redacted callback text.
- Match events to the current `runId`, deduplicate by sequence, retain sequence
  order, and clear on new Start/project-context replacement. Process restart
  naturally begins with no Logs UI event state.
- Unit tests cover active/terminal/empty states, filter/search, selection/detail
  panel, safe-field rendering, run mismatch/deduplication, reset behavior, and
  512-row pagination and a genuine upstream history-gap indication.
- Run focused frontend tests, typecheck, lint and formatting checks; preserve
  unrelated worktree changes. Real React/Wails bridge acceptance remains
 distinct from mocked UI tests and must not be claimed unless performed.

## Owner clarification — pagination and columns

Render the complete in-memory current-run event stream in pages of 512 rows;
do not evict rows from React state because a page boundary was reached. All
fields exposed by `InstallationEventView` are available through a hide/show
column chooser. The existing upstream Core/Go observer limit is 8192 events;
10,000-event run support requires a separately reviewed coordinated limit
increase and must not be claimed by this UI-only implementation.
