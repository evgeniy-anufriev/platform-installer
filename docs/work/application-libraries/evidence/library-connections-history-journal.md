# Library-owned connections and ClickHouse history — evidence

2026-10-19, base a5ce142c plus accepted uncommitted DIRECT/ENV/ports/topic work.
master/origin/master checked0/0. Current delta before-images retained locally in
`.runtime/qa/library-connections-history-before`; earlier work preserved.

Owner authorized library-owned binding/protocol/purpose, application connection
keys, own users/grants/ENV, and ClickHouse history default
`{{ library_instance_id | replace('-', '_') }}` with group_vars overrides.
History resource ID differs from connection clickhouse and provider binding
analytics. No application installation, SQL/Kafka writes or automatic migration.

FULL PLAN APPROVE_WITH_CHANGES, zero blockers. LCH-P01 corrected with allOf/object
constraint on library connections; app lists/legacy maps, library map/list rejection
and missing connection key are covered. No second PLAN review.

Focused current-tree RED OS proof:

-22 Core cases PASS: list/declaration schemas, two libraries/multiple hosts,
  ClickHouse name template, aliases, instance/resource precedence and resets,
  unknown key rejected before ENV. Raw namespace leaf access left the expression
  unexpanded in the first experiment; ordinary isolated library defaults lookup
  resolves it after binding identity. Final focused rerun PASS.
-27 SDKU package schemas/digests,2 prepare jobs,26 Compose renders and one shared
  base PASS. Existing validator reused; no new Python script.
- Native26:497 tasks, changed=1 only synthetic QA artifact, failed=0. All13
  ClickHouse consumers' JDBC strings resolve to sdku_dm for library sdku-dm.
  First fixture attempt removed unrelated operator parameters and failed; fixed
  QA fixture retains them and removes only obsolete database_name/topic ENV.
- Frontend261 tests/build/lint PASS; missing type-only import corrected before
  final build. Resources ClickHouse inheritance/override/reset covered.
- Go tests and vet PASS; no production Go semantic changes.

Runtime43 built on node2 from current-tree sources.907 components independently
hashed/validated; all five affected runtime files match current source. Standard
publication into active cache, digest
`sha256:45db19215f0e2734a78bceeb33992502024a17479b70a9d1e9ea54f5dde5e7b9`.
Previous42 retained locally. To provide archive+extraction space on node3, old
inactive QA41 was revalidated locally, remote manifest/current-symlink checked,
then only that release removed. Active42 and40 retained. Owned node2 build/input43
removed after complete local bundle verification; shared acquisition input kept.

QA workspace `/var/tmp/platform-installer-qa-be0dd278a57d448ebb1583a138834892`.
Real React/Wails uses isolated `.runtime/qa/library-connections-history-ui-project`;
it selects history through the existing Resources UI before Verify. Own app
accounts/Sentinel metadata preserved, now declared in that QA library rather than
duplicated in app.

Actual React handlers/real Wails methods: runtime43 PREPARED, connection-key
metadata rendered from the library. Resources Add from defaults selected history
with no authored name. Save/Verify resolved sdku_dm at revision
`sha256:28ea629b13295585323b748bf0c3af8cd06b40e3f86e2ce0a7dc003584affe5c`;
override custom_history at
`sha256:dfd60a9ff73f72899d25c2864b7c6ba8b27298ebfb17d21fbac68e0d7d2d1c44`;
clear/reset returned to the original revision/name. Both JDBC ENV values were
checked for every placement. Reopen preserved the exact reset revision and no
authored name override. Evidence: local ui-crud JSON/log under
`.runtime/qa/application-design/library-connections-history-*`.

Fresh real UI/Core plan `plan-fe1c3abf1993334c6cfa5228` EXECUTABLE on reset
revision28ea629b, skipInfrastructureVerify=true, exactly
APPLICATION_LIBRARIES_APPLY and APPLICATION_LIBRARIES_VERIFY. Not approved or
started; this is plan acceptance, not resource execution.

Initial consolidated83:81 PASS, one existing skip, one legacy Kafka native test
timeout60s. It overlapped bundle/native work, but causality is unproved. The exact
failed case reran alone PASS24.421s without changing tests/timeouts. Final
consolidated83 completed372.917s:82 PASS, one existing skip, zero errors/failures.
Owned node2 source workspace removed by standard qa-sync cleanup; independently
confirmed absent. Shared acquisition input and active runtime retained.

Independent FULL DIFF APPROVE, zero blockers, LCH-P01 RESOLVED, no new findings or
unnecessary mechanisms. Final40 implementation fingerprint
`a340398eb2eada128c9fca394743b346724f4b19b9444c46984ec3c72159f570`
rechecked unchanged. [Review](../reviews/library-connections-history-diff-review.md).
git diff --check PASS. Uncommitted; previous dirty work preserved.

Subsequent owner-requested YAML field ordering only: library name/version first;
applications name/version/defaults/connections first; application defaults
image/user/restart first.27 SDKU defaults files reordered without changing any
lines or values; import-catalog digests refreshed. RED OS yaml.safe_load comparison
of each before/after document confirmed exact semantic equality; requested field
order and git diff --check PASS. Earlier review fingerprints describe the
pre-formatting bytes; no ownership/resolution behavior changed. No runtime
rebuild, application restart or server resource changes for this formatting step.
Visual inspection and actual SQL/Kafka/application deployment are outside scope.
