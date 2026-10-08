# Agent context maintenance record

## Scope and provenance

Owner-approved documentation/context optimization, 2026-10-08:
compact startup documents, conditional procedures, bounded reading and a
small recurring-task index. No product/runtime contract or acceptance gate
is changed. Source baseline: `f358e2ab27421ad32f028dc51822e4a769b183b0` plus
the exact working-tree files captured before migration.

`CURRENT_STATE.md` was split into 75 original level-two sections. All section
prose, dates, IDs, fingerprints and recorded evidence are preserved in four
archives. Only relative Markdown link destinations were relocated; section
hashes are compared after reversing that relocation. Archive grouping preserves
original section order within each topic; the local migration manifest records
the original global order. Archives warn that their statuses are historical.
The source preamble was only `# Current state` and blank lines.

I05 PASS is a current owner-confirmed correction, not a reinterpretation of an
old failed run. Remaining SI11 cases and naming acceptance are kept open.

## Instruction coverage map

| Original AGENTS section / rule | Maintained destination |
| --- | --- |
| Outside-in architecture, V1 policy, current milestone authority | Root AGENTS introduction and canonical documents |
| All Core/Go/UI, precedence, source-selection and desired-state boundaries | Root AGENTS Boundaries, retained verbatim |
| Desired/discovered/resolved/result/secret separation | Root AGENTS State separation, retained verbatim |
| Canonical reads, single contract, Ansible simplicity and effective variables | Root AGENTS Change discipline |
| UI pre-start/acceptance mockup and discrepancy checks | Root AGENTS Change discipline; affected screens plus shared rules, expand for cross-screen impact |
| Architecture PLAN/DIFF risks, budget, BLOCK, reviewer envelope/fallback, overengineering | [Review procedure](agent-procedures/review.md), original full rule text; mandatory root route and independent-review summary |
| Scoped agents, main-agent tests, milestone QA delegation | Root AGENTS Change discipline, subject to request/available delegation |
| Canonical document list, PostgreSQL explicit PKI plan | Root AGENTS Canonical documents and Change discipline |
| Vendor exclusions, fixtures, V1, generated catalog, concise logs | Root AGENTS Context efficiency |
| Runtime secret handling and missing prerequisites | Root AGENTS Secrets; [QA](agent-procedures/qa.md) |
| Real React/Wails gates, no substitute mocks, honest visual status | Root AGENTS Secrets/acceptance; QA original full rule text |
| PEM/session expiry, host-key comparison and approval | QA original full prerequisites; mandatory root route before WebView |
| SI11 preparation sequence, warning, no Computer Use, separate Approve/Start | [SI11 procedure](agent-procedures/si11.md), original full text; root route |
| RED OS/ALT location, exact source transfer/cleanup, no read-only target mutation | QA original full rules; root RED OS summary |
| EXEC-01 identity/NOPASSWD/bootstrap-only recovery | QA original exact connection; root no-password/admin fallback rule |
| Trusted node2 acquisition, bootstrap location, exact publication/cache/import/fallback | [Runtime bundle procedure](agent-procedures/runtime-bundle.md), original full rules; root acquisition/publication summary |
| Exact Wails process-image restriction | QA original rule; mandatory root route before stopping |
| Missing artifacts, no Downloads/Desktop search, separately authorized DEV, no production downloads | Runtime bundle original rule; root prohibition |

QA skills route to the common procedure instead of maintaining competing SSH,
sudo, transfer and cleanup instructions. Their focused/milestone checks remain.
Nested AGENTS are unchanged; the root/index explicitly require loading the
applicable file even when the session starts at the repository root.

SI11 test cases already require stricter visible-UI-only full acceptance than
the preparation automation seam. The SI11 procedure explicitly keeps these
scopes separate; direct preparation never substitutes for acceptance.

## Maintenance and verification

- Current state: update the relevant entry; journal detailed runs, then link.
  Preserve open blockers and exact limits of evidence. Do not prepend history.
- Root instructions: preserve unconditional safety/ownership gates and mandatory
  procedure triggers. Procedures must not change permission or acquire ledgers.
- Index: keep paths/symbols current, scope routes to recurring tasks, load only
  relevant documents. Remove stale routes rather than expanding a whole-repo map.
- Validate local links/anchors and procedure reachability after moves; confirm
  original section content and instruction coverage, not just file sizes.
- Trial routes: UI change -> shared/screen design and actual flow gate;
  Save/backend change -> scoped Go rules, project/transaction contract and review
  classification; Core role change -> Core rules, role contract and RED OS gates.
- Compare characters/bytes in root/state and total required text for those
  routes. Character reduction is not a measured reduction in full task tokens.
- Documentation-only checks do not invoke service QA, change targets, or imply
  a new product acceptance PASS.

Migration helpers and byte snapshots are ignored local QA artifacts under
`.runtime/qa/agent-context-20261008/`; they contain documentation only and are
not runtime dependencies. No memory files were changed.

## Verification result — 2026-10-08

- All 75 historical section hashes match the original after reversing only
  relocated link destinations; all seven migrated procedure blocks are intact.
- Root Boundaries and State separation text is preserved (line endings normalized).
- All 144 local Markdown links in changed/new documentation and skills resolve;
  referenced anchors and task-index symbols were checked. Existing SI11 journal
  and naming-plan bytes are unchanged from the captured working-tree baseline.
- All four changed skills pass the bundled skill-creator `quick_validate.py`.
- `git diff --check` passes. Only Markdown documentation/skills are deliverables;
  no service/runtime QA or target mutation was performed for this change.

| Reading measurement | Characters |
| --- | ---: |
| Previous AGENTS + CURRENT_STATE | 208,049 |
| New AGENTS + CURRENT_STATE | 21,966 |
| Previous startup plus full UI design and mockup | 331,833 |
| Trial UI route: startup/index/QA, selected design and Servers mockup/shared CSS | 63,967 |
| Trial backend route: startup/index, internal rules, project contract, review and QA | 49,117 |
| Trial Core route: startup/index, Core rules, Core/project contracts and QA | 54,716 |

Startup text is reduced by 89.44%. Trial routes validate navigation/required
gate discovery, not product behavior. They exclude task-specific source/tests,
milestone plans and additional HTML handlers/cross-screen dependencies. These
figures are character counts, not exact token counts or total task savings.
