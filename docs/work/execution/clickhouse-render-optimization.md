# ClickHouse table rendering optimization

Owner request: optimize ClickHouse after preflight; review remains explicitly
waived. Branch `codex/application-preflight-optimization`, base `82695173`.
No new worktree, commit, bundle publication or installation run requested.

## Change

The existing action rendered every table using a separate native Ansible lookup
and templar context copy. Replace that loop with one native template lookup that
returns the complete ordered table list as JSON. The ordinary single-table entry
and the new batch entry use one DDL macro; SQL is still owned by the role template.
Validate the returned number, database identity, definition and nonempty SQL
against the current job before passing it to application_scope.

No cache, source-authority change or second desired-state representation is added.
The existing action result shape remains database/definition/sql. Accounts and
empty table jobs retain their existing empty result without template lookups.
Preflight continues to render/validate before provider mutations. Resources and
standalone Verify use current inputs. TLS, credentials, ownership witnesses,
per-member schema checks, locks, DDL retries and service queries are unchanged.

Baseline runtime16 had eight rendering task results totaling65.55s (including two
cheap accounts calls). That is not a measured saving. This change reduces template
lookups from table-count to one per nonempty job, including repeated phases,
rather than retaining SQL across phases with potentially stale context.

## Validation

RED OS render suite: six tests PASS, no skips, 19.617s. Tests compare full SQL byte-for-byte with the
pre-change template for standalone/raft-ha, multiple databases, quoting and table
settings. Additional tests cover 64-table invocation counts, empty/accounts jobs,
malformed/truncated/mismatched batch results and safe template failures.
An isolated native benchmark compares the old action/template with the new action
on the same 24-table job; timing is recorded but is not a correctness threshold.
Measured action times: legacy 2.2513s, batch 0.3228s (about 7x for this fixture).
The fixture is not a full installation benchmark; runtime16 savings have not
been measured. Local ignored evidence: `.runtime/qa/clickhouse/render-final.log`.
Apply/Verify syntax checks PASS. All seven provider tests finished `ok`, including
isolated native standalone and three-server resources/accounts/repeat/Verify,
ownership rejection and grant isolation. Their enclosing broad library run was
interrupted after unrelated snapshot tests returned PARTIAL because their
synthetic Kafka fixture lacked the now-required adminCredential reference.
That broad run is not PASS; its evidence is retained in
`.runtime/qa/clickhouse/regression-interrupted.log` and `library-diagnostic.log`.

Aligned only the test setup with the current Kafka contract by adding a synthetic
`runtime:kafka-admin-password` reference, without a credential value. Fresh source
transfer: both affected library tests PASS in 64.287s, no skips (ClickHouse history
defaults/overrides/reset and table settings/DDL rendering, including native
ClickHouse parsing). Evidence: `.runtime/qa/clickhouse/libraries-final.log`.
The full unrelated library suite was not repeated or claimed successful.

Final focused selections cover 15 distinct passing tests across these runs:
6 renderer/action tests, 7 provider tests and 2 corrected library tests. All three
temporary qa-sync workspaces were cleaned; native fixtures clean their own
temporary servers and data. `git diff --check` PASS. Owner authorized committing this implementation.

Actual React/Wails installation, bundle-dependent QA and full-stage speed
acceptance remain pending. Temporary QA services, if exercised, are isolated from
deployed services; no active run or installed service is changed.
