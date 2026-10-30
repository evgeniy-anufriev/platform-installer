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
no_log both true and false. Core/native tests remain NOT EXECUTED: both RED OS
101/102 strict SSH probes timed out again. Real Wails acceptance remains OPEN.

Independent FULL DIFF of the initial filtered-publication change and one revised
FULL DIFF after the owner's explicit task-no_log removal instruction both
returned APPROVE_WITH_CHANGES, zero blockers. Revised review recommendation
SDO-N02 (native successful private-register/output check) was incorporated into
the test source; SDO-N01 negative artifact cases were also added. These added
tests have not been executed. `git diff --check` PASS. No Go/React code changed
in this follow-up, so their earlier results are not a native acceptance claim.
