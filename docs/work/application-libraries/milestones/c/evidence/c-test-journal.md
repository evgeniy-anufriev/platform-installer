# C implementation and acceptance journal

Updated 2026-10-16. Branch `codex/application-libraries-c`, base
`a7260c6f7cbe3f41dcdf8dd996234ec529e33caa`. Owner approved C and image/port
overrides/reset; added mandatory application Secrets and runtime-secret end-to-end QA.

## Current result

Technical acceptance PASS within the approved C scope: actual editor/import,
external-revision refusal, exact library Apply/Verify, secret chain, Agent restart
and unchanged repeat. Baseline accounts restored; temporary provider users and five
remote QA workspaces removed; final target health PASS. Remaining local QA files are retained by explicit owner instruction as a cleanup
exception. Installed P2
runtime/infrastructure retained; no infrastructure Apply/new bundle/commit/master sync.

## Implementation scope

- New Applications route and master-detail editor uses existing managed view,
  typed EditCommand v1.1, edit session and common Review/Save.
- Package definitions exposed as authored data through ManagedProjectView using
  existing handle-bound package reader/manifest validator; no template evaluation.
- Narrow application amendment shares existing session compare-and-swap/expiry/
  reviewed-plan invalidation with service amendment, preserving separate allowlists.
- Import preview uses existing package validator/PlanStore within empty edit session;
  existing CommitStructuralEditPlan performs guarded publication and refresh.
- Credentials source editing and existing descriptor-bound runtime lease input;
  library-scoped dialog reuses ApplicationSecretInputs. No runtime values in project.

## Intermediate checks (historical snapshot)

- Windows `go test ./...` PASS at first editor/amendment snapshot; subsequent import
  additions require rerun before final gate. Not final-tree regression evidence.
- Focused Go application amendment/package view2 PASS, including source-change
  after preview and refusal of malformed package; prior service amendment tests PASS.
- Frontend editor5 + existing runtime-input2 tests PASS at intermediate snapshot.
  Tests cover no writes on open, image/reset, independent host/container defaults,
  preserving other local input, declared connection coverage and typed password sources.
- TypeScript PASS after subsequent editor/form additions. Lint/final regression pending.

## Initial acceptance checklist (historical snapshot)

Complete forms and negative tests; final focused/full checks and applicable native
RED OS/offline checks; independent HIGH-RISK FULL DIFF (secret/import boundaries);
real React/Wails edit/review/save/reopen/import flows; bounded target library-only
Apply/Verify, repeat and C-Q17 runtime inputs→provider hooks→Vault→Agent→application;
separate visual check, known-value audit and owned cleanup. Preserve exact run/revision
and per-provider safe evidence; do not substitute historical B/P2 PASS for C acceptance.

## Final frozen-snapshot checkpoint and review

FULL DIFF BLOCK: [report](../reviews/c-diff-review.md). C-D01 exact-set runtime
input incompatibility OPEN; C-D02 create dirty marker and C-D03 navigation UX OPEN.
Automatic correction and target QA paused awaiting owner disposition.

Final Windows go test ./... PASS; frontend182 PASS/15 files, focused10 PASS;
TypeScript/lint PASS. Earlier vet PASS. RED OS offline Go12 PASS belongs to the
preceding snapshot; unchanged current-tree Core application tests17 PASS.
No actual C UI save/start, target Apply or provider/Vault/Agent acceptance claimed.
Wails/Vite startup succeeded after one failed dev-server autodiscovery attempt;
startup alone is not flow acceptance. All three verified owned QA processes stopped.
Own node2 public-source/test workspace 8b5fe48482a845778eef173ef674e6ab removed via
qa-sync cleanup. Safe local evidence retained; production runtime/infra untouched.

User-required C-Q17 now explicitly covers runtime input through existing lease,
provider hooks and actual service authentication, Vault metadata and protected
value equality, Agent materialization/permissions and application checks. It remains
NOT RUN; prior-stage results cannot substitute for this C acceptance.

## Owner-approved correction / current QA checkpoint

Owner authorized C-D01/D02 corrections and one targeted recheck; result
[APPROVE_WITH_CHANGES](../reviews/c-diff-targeted-recheck.md), zero blockers.
C-D03 two-choice discard/stay UX explicitly owner-accepted; per-field staging retained.
Real editor positive cases PASS: image amend/reset, one-side port edit, structural
Review/Save and reopen, adjacent fields retained, two libraries same package create/
Save, dirty stay/discard. Actual Wails IDs/calls in ignored ui-editor-final.json.
No target mutation by those disposable local editor projects.

Live QA found bounded compatibility defects and corrected them without Core changes:
existing Agent .hcl data-only template accepted only for agent_template, preserving
manifest/digest/path/executable guards; Applications nav included in existing filter;
credential override requires explicitly selected account mode before source edits,
without copying package metadata. Offline native descriptor diagnosis safely caught
missing mode as SCHEMA_VALIDATION_FAILED before Start. Final frontend185 PASS,
Go full/vet PASS. Further target/import/visual/cleanup gates remain open.

## 2026-10-16 real target continuation

First C run `installer-b9f0c7e2d30814007ad1d84de9d845d0`, saved revision
`sha256:fc1ca32742fe3bcd367aeefc41f66ead815b94d3da65ffb540e4b6e70fefc65d`,
FAILED at HAProxy reachable-target publication guard; library Verify did not run.
This failure remains FAILED. Subsequent read-only target probes returned HTTP200;
transient startup readiness is a hypothesis, not a proven root cause.

C-Q17 positive evidence: all four provider credentials matched protected expected
runtime inputs in Vault and Agent child environment; 11/11 bindings matched.
Owned policy/role, readonly Agent mount and private file permissions passed.
CA/hostname-verified CSPA status200 reported all eight checks ok. Values were not
printed. This proves the secret chain, not successful overall Apply/Verify.

Normal server checks and previous-run Inspector recovered successfully after the
interrupted dev observation; Inspector returned RESOLVED/FAILED for the old run.
No manual run-record rewrite or duplicate Start was used.
New actual React/Wails run `installer-fccdd07b7cb1fe1dfef56f32428a2506` accepted
2026-10-16T06:01Z with immutable P2 bundle04. Core returned INFRA_VERIFY_MISSING
for current evidence revision; selected plan contains ten SERVICE_VERIFY plus
APPLICATION_LIBRARIES_APPLY/VERIFY, zero SERVICE_APPLY. Current run is RUNNING;
terminal result and remaining acceptance gates must be recorded before C closure.
Retry fccdd07b7cb1fe1dfef56f32428a2506 FAILED at06:29:50Z after all ten
infrastructure Verify operations succeeded; library Verify did not run. HAProxy
HTTP guards failed on all three hosts. Read-only Docker inspection proved all
three owned QA containers exited128 with OCI/runc/shim already-exists state,
not OOM; this replaces the unproven transient-readiness hypothesis for this retry.
Two node1 runc entries were stopped/pid0. No container deletion, global prune,
Docker daemon restart or infrastructure Apply occurred. Bounded ordinary docker
start attempts recovered all three existing IDs; stale stopped runtime records
cleared during those attempts. SDKU StartedAt necessarily changed during recovery;
this recovery is not clean-repeat evidence. CSPA secret-chain recheck PASS11/11,
CA-verified status200/all8ok. Before/failed/recovered container snapshots retained.
The next QA driver refuses any selected plan other than the exact library pair.
## Positive C target and repeat evidence (2026-10-16)

- Exact library pair `installer-4d36a5f2209c953262e73cdf2acffcc8` SUCCEEDED
  06:50:14Z. Apply06:37:19–06:47:02Z; real Verify followed. Zero infra operations.
  Five direct/public endpoints returned200 with all eight checks ok. All three
  containers retained recovered IDs/StartedAt/image/running metadata.
- Scoped CSPA-only container/Agent restart retained ID and restored HTTPS200,
  all8checks and11/11 expected bindings. No SDKU/infra restart in this scenario.
- Exact pair repeat `installer-efeaf47ac72f9e17e598c136aab5eead` SUCCEEDED
  07:12:40Z. Apply06:59:19–07:09:26Z. Entire before/after metadata identical:
  three container identities/StartedAt,10KVversions, PG OIDs/ACL/membership,
  ClickHouse UUID/grants, live HAProxy/BIND hashes/mtime and service counters.
- Actual import UI PASS: bad digest refuses publication/cancel; imported bytes
  remain those reviewed even after external package source changed.
- Actual external-project revision test PASS: PROJECT_CHANGED refuses Save and
  preserves external bytes. Layout checked at1440/1024,125% zoom; bounded header
  wrapping corrected. Dark OS preference still renders the existing light theme;
  no production dark-theme implementation is claimed.
- Restored baseline account sources through the real editor; Save invalidated
  target trust and first Start correctly refused TARGET_HOST_TRUST_REQUIRED.
  Repeated normal host checks. Only-library restoration run
  `installer-a07bef468522f094c0f203f5cc269980` accepted07:22:16Z, currently RUNNING.
  Temporary C-QA users will be removed only after restoration Verify succeeds.

Own QA picker exhaustion and a disposable negative-test draft left active were
pre-Start QA preparation failures; no extra target execution occurred. Dev-session
reset and explicit UI discard corrected these helper lifecycle issues. They are
not production execution PASS evidence. Earlier actual failed runs stay FAILED.
## Final C acceptance (2026-10-16)

**C complete: technical acceptance PASS; local retention explicitly owner-approved.** Safe evidence:
[c-final-summary.json](c-final-summary.json). Production dark theme was not added;
light layout was visually inspected1440×900/1024×720 and125% zoom, including OS
`prefers-color-scheme: dark` with unchanged supported light rendering.

| Gate | Final evidence |
| --- | --- |
| Independent review | FULL blockers C-D01/C-D02 corrected; owner-approved TARGETED_RECHECK APPROVE_WITH_CHANGES, zero blockers. C-D03 discard/stay explicitly owner-accepted. No extra review cycle. |
| Current Go / frontend | Windows full Go tests, vet and build PASS; current-tree affected RED OS/offline Go and Core17 application tests PASS. Final frontend186/186 across15files, lint/build PASS. No Core production changes; no unrelated full Core rerun claimed. |
| Real editing | Actual React/Wails image amend/reset, independent host/container ports, Review/Save/reopen, two libraries same package and dirty stay/discard PASS. Public descriptor cache is page/revision scoped, never contains secret values; explicit account mode added without copying package metadata. |
| Import / conflict | Actual digest refusal/cancel, positive import of reviewed bytes despite changed external source, and PROJECT_CHANGED refusing overwrite PASS. Existing path/manifest/transaction negative tests supplement these actual flows. |
| Actual two-operation execution | `installer-4d36a5f2209c953262e73cdf2acffcc8` SUCCEEDED. Apply583s, Verify197s. Exactly APPLICATION_LIBRARIES_APPLY/VERIFY, saved infra proof accepted. |
| Secret chain | Actual scoped SDKU/CSPA runtime dialogs through existing lease; four provider-account values verified in Vault and Agent; eleven bindings exact; all eight application checks ok. No credentials persisted in desired state. |
| Agent recovery | Only owned CSPA container restarted, same ID;11/11 bindings and HTTPS200/all8ok recovered. Earlier stale-runtime recovery is separately recorded and is not sibling-stability proof. |
| Unchanged repeat | `installer-efeaf47ac72f9e17e598c136aab5eead` SUCCEEDED. Apply607s, Verify194s. Entire selected stable metadata identical. No raw Ansible recap changed counter claimed by this event-only UI path. |
| Baseline restoration | `installer-a07bef468522f094c0f203f5cc269980` SUCCEEDED. Apply550s, Verify198s. Original account sources restored through UI; baseline Vault/Agent equality11/11 and all5status200/all8ok after cleanup. |
| Owned cleanup | Temporary PostgreSQL role owned zero objects; scoped privileges/role removed. Redis/Sentinel account markers/hash verified before deletion on all3members, ACL SAVE and witness publication reused. ClickHouse witness IDs matched all3members; only temporary user dropped ON CLUSTER default. Databases, baseline users, Vault paths/policies/roles, canonical PKI/bootstrap, images and Core journals preserved. Five exact own remote workspaces removed through qa-sync. |
| Secret hygiene |20 known values,182 scanned public/QA files at initial final audit,0 matches; final audit refreshed after document/evidence updates. Values never printed. |

Bounded post-review compatibility/layout corrections preserve the approved contract:
Agent-only `.hcl` import support retains exact manifest/digest/path/data-only guards;
account mode is explicit; the existing public descriptor operation is cached only
for the same page/revision. These bounded fixes were tested; no additional
independent review or architecture change is claimed.

Earlier actual failures remain FAILED, including endpoint guards during stale OCI
state; blocked pre-Start attempts were not executions. Existing unchanged common
Cancel/provider/path/trust controls are covered by regression/prior-stage evidence,
not relabelled as new C target scenarios. No new production command bridge, desired
state store, resolver, secret store, infrastructure Apply or parallelism was added.
## Local cleanup exception — automatic approval rejection

Technical C acceptance and target/remote cleanup PASS. Complete milestone closure
remains pending local-cleanup disposition. Both the guarded combined cleanup and
a narrower explicit-path public-fixture cleanup were rejected by automatic approval
with `blocked by policy`; no detailed rejection reason was returned. Neither
command ran. No further deletion attempt or alternative-shell workaround was made.

Retained local items: nine own directories under `.runtime/qa/c/` (compiled QA bin,
editor/conflict/import fixtures) and own protected
`.runtime/secrets/c/application-input-values.json`. Evidence and public QA helpers
remain intentionally retained. Existing protected B4 inputs and persistent identity
were not touched. A final known-value audit also includes the retained public
fixtures; it does not expose private runtime input values.
Final retained-public-fixture audit:20 known values,348 files,0 matches. Own dev
Wails application/driver and Vite stopped; no target execution remains active.

Owner explicitly requested deletion with sudo on2026-10-16. Verified all nine
local Windows QA directories and the exact protected C input file, with resolved
path/reparse guards. Renewed deletion was again rejected before execution by
automatic approval: blocked by policy, no detailed reason. No files removed.
These are Windows paths; remote sudo does not apply. No alternative-shell bypass
was attempted; local cleanup remains BLOCKED.

## Final owner disposition — retained local files

On2026-10-16 the owner explicitly instructed not to delete the remaining local
files. Nine QA directories and the protected C runtime-input copy are retained
as an owner-approved cleanup exception. No further deletion is authorized or
planned. This supersedes the pending cleanup decision above; historical policy
rejections remain recorded. C is complete within its approved scope. Target
cleanup, final health and secret-safety results remain unchanged. No commit or
master synchronization was requested.

## Publication authorization

Owner requested the C commit and master/origin synchronization on2026-10-16.
Prior local-retention instruction remains in force. Fetch confirmed local master
and origin/master at the same base a7260c6f before publication, with no remote
commits missing locally. No runtime secrets/QA fixtures are included in the commit;
Git history is the authoritative final commit/merge identity.
