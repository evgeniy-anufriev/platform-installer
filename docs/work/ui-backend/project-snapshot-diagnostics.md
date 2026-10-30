# Project Verify snapshot failure diagnostics

Owner requested concrete safe reasons for PROJECT_SNAPSHOT_INPUT_INVALID and
publication to GitHub on 2026-10-30.

The snapshot action now identifies the failing resolution stage and maps known
input failures to fixed messages (missing/invalid documents, inventory selection,
catalog references, application artifact lock conflict and resolution identity).
Unknown exceptions expose a fixed category and stage, never exception text,
input values, parser excerpts, filesystem paths or dictionary keys.
The existing finding code and snapshot/verification contracts are retained.
Go retains bounded matching findings from typed ExecutionError on Verify failure;
the Project page shows those summaries beneath its existing general error.
This is a bounded diagnostic correction within the existing safe-finding path;
it changes no desired-state ownership, writer, execution or trust semantics.

Verification:

- `go test ./internal/desktop ./internal/executionnode -count=1`: PASS.
- `go vet ./internal/desktop`: PASS.
- `npm test -- --run src/App.test.tsx`: 87 PASS.
- `npm run typecheck`: PASS.
- Added Core action tests for missing document, parser-content exclusion and
  closed reason vocabulary. NOT EXECUTED: strict SSH connections to configured
  RED OS 192.168.56.101 and .102 both timed out on port 22. No local Windows
  Python/Ansible execution or installation was substituted.
- Real React/Wails -> updated Execution Node Core acceptance is OPEN, not
  replaced by mocked frontend or direct Go tests. New desktop build and a new
  verified/published/bound runtime bundle are required to deliver both halves.
  No bundle build/publication/activation or installation run was performed.
- No visual inspection PASS is claimed; unrelated dirty work is preserved.

## Follow-up: callback fallback and owner no_log instruction

The owner screenshot showed callback fallback `Project snapshot could not be
built`, not an action finding. The resolution role's snapshot task used
task-level `no_log: true`, which also censors safe findings before callbacks.
The original correction did not cover this path.

Owner explicitly requested removal of no_log from this task and an actual
diagnostic without speculative alternatives. The task flag is removed. Private
cached resolution objects are referenced by two fixed task-variable names inside
the action, rather than templated into arguments. Successful private results
retain `_ansible_no_log: true`; only the public snapshot is written to the
existing output artifact. Failed results publish only the fixed safe finding,
adding actual exception category and code basename/line within the 512-byte
limit. Raw exception text, source excerpts, locals and private configuration
are excluded. Callback preserves that finding. A failure before publication
has a factual fallback without alternate guesses.

Added tests for censored failures, private success result protection,
malformed/oversized/symlink artifacts and native Ansible task failures with
no_log both true and false. After owner startup of RED OS101, current-source
combined bootstrap/snapshot action/output/native resolution/preview suite:
35 PASS (35.115s), no skips, Python3.11.15/Ansible Core2.18.15. Native no_log
failure publication and private-success register/output exclusion passed.
Initial34 PASS/1 FAIL was an obsolete callback wording assertion, corrected
to verify the stable diagnostic code and nonempty safe message. Production
behavior was unchanged. Both qa-sync workspaces were removed and their absence
confirmed. Previous SSH unavailability is historical. Real Wails acceptance OPEN.

Independent FULL DIFF of the initial filtered-publication change and one revised
FULL DIFF after the owner's explicit task-no_log removal instruction both
returned APPROVE_WITH_CHANGES, zero blockers. Revised review recommendation
SDO-N02 (native successful private-register/output check) was incorporated into
the test source; SDO-N01 negative artifact cases were also added. These added
tests now passed on RED OS101 as recorded above. `git diff --check` PASS. No Go/React code changed
in this follow-up, so their earlier results are not a native acceptance claim.

## Explicit root and implicit localhost regression

Owner's manual project-snapshot run exposed a pre-action templating failure:
`platform_project_root | default(inventory_dir | dirname)` evaluates its filter
argument even when an explicit root is present. An implicit localhost does not
have inventory_dir. The action cannot return its structured finding because it
has not started, explaining the callback fallback shown by Project Verify.

Use Ansible's lazy conditional at the nine equivalent root fallback expressions
in resolution/validation and application provider/runtime tasks. Explicit root
remains authoritative, ordinary inventory-root fallback remains available, and
no new defaults, path discovery, persistence or precedence implementation is
introduced. Existing fixtures explicitly declared localhost and therefore
masked this issue.

RED OS101 regression: remove localhost from the representative inventory and
run the production project-snapshot.yml with an explicit relative project root,
once with application libraries and once without. On the isolated baseline with
the two old role expressions restored, both cases failed. Restoring current
sources and verifying them with qa-sync produced37 PASS in36.436s, zero skips,
for native resolution, bootstrap, snapshot action/output and preview tests.
Native Ansible Templar additionally evaluated all nine production expressions
with undefined inventory_dir and explicit root, then with ordinary inventory
fallback. Both branches passed. No target contact or installation was performed.
Real React/Wails acceptance after delivery of a new runtime bundle remains OPEN.

## Prepared-node retention during topology drafts and Verify findings

Owner reported a prepared node reverting during topology edits and an INVALID
Project Verify with an empty diagnostic area. Investigation found two separate
presentation/lifecycle faults: a saved Core preview finishing after a draft opens
could pass through operation-only binding validation and revoke the prepared
binding; GetExecutionNodeContext omitted its runtime digest while editing.
The draft operation guard now rejects operations without revoking trust merely
because a draft exists. Saved-only presentation/publication checks retain the
same endpoint, identity generation, credential availability, host-key pin,
command guard, runtime bundle and saved revision checks. No new Core request is
started for an open draft. Preparation does not authorize execution or retain
an old approved deployment plan after Save.

The Project page previously displayed findings only when Verification.error
was present, hiding ordinary INVALID results. Its counter also depended on a
separately loaded snapshot rather than the current verification evidence.
It now displays current-revision verification findings with code, summary and
subject and severity, including truncation notice; old-revision findings remain
hidden. Warnings are not styled as blocking errors.
The owner's screenshots compare different revisions: manual PASS 767dcc1f...
and UI INVALID 6ae9d4ab.... They are not evidence of contradictory validation of
the same saved bytes.

Validation: desktop regression suite and go test ./... PASS; go vet ./... PASS;
App frontend 93 tests PASS; frontend typecheck, lint and production build PASS;
Windows Wails production build PASS. Tests cover draft operation rejection
without readiness loss, repeated context reads retaining runtime digest,
credential revocation during draft and late preview rejection after saved
endpoint/credential/host-key/command guard/bundle/revision changes. Go race
runner unavailable with this environment's CGO disabled. Real React/Wails
prepared-node/topology/Verify acceptance remains OPEN, not replaced by these
unit tests or compilation. No Core source or runtime bundle change is required
for this desktop/UI correction. Independent FULL DIFF review of six source/test
files at base fcbf4a02 returned APPROVE_WITH_CHANGES, zero blockers. Nonblocking
DBR-N01 (require a nonempty verification revision) and DBR-N02 (distinguish
warning presentation) were corrected with regression tests. The review
fingerprint before these bounded corrections was
d4c19952eb33a42be7fab9e3f807d01731071c72702dcad32d12eaebb72d7228.

## Missing secret reference and header navigation

For RUNTIME_SECRET_REFERENCE_REQUIRED, desktop presentation now names the
service deployment and configuration setting from Core's existing `field`
path. Only the closed `serviceDeployments.<id>.configuration.<setting>` shape
with bounded validated identifiers is rendered. Invalid, oversized or deeper
paths retain the safe Core summary; configuration and secret values are never
read. No Core requirement semantics or public DTOs changed.

INVALID and technical Verify errors share the existing status-chip--danger
palette in the header and are buttons navigating to Project through the
existing requestPage handler. Previously ordinary INVALID was a green readonly
div; technical failure already navigated but used the green readonly class.
This resolves a discrepancy with the shared findings/status visual language.

Validation: go test ./... and go vet ./... PASS; App 95 tests PASS, including
navigation from Servers through both failure badges to the detailed Project
finding. Typecheck initially caught an unsupported test-query option; removed
it, frontend typecheck/build and lint PASS. Go regressions check two different
instance/setting pairs and reject unsafe/oversized/deeper diagnostic paths.
Real React/Wails acceptance and visual inspection remain OPEN; mocked frontend
tests and production compilation are supplementary evidence.
