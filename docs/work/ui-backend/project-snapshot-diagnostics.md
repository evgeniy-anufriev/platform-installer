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
