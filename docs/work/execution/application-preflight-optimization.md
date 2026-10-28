# Application preflight optimization

Owner request (2026-10-28): create a new worktree from master and begin preflight
optimization. Base: `112b7950` (`master` after fast-forward from origin/master).

## First implementation slice

1. In `application_runtime/tasks/resolve_paths.yml`, select other libraries before
   the overlap loop and deduplicate their library paths. Keep the same equality
   and ancestor/descendant assertions. Same-library consistency remains guarded
   by apply_library. Do not introduce a persistent cache.
2. Replace source_config's separate stat checksum and slurp with one read-only
   Core module, `application_source_file`. It runs on the selected Execution Node
   through the existing delegate_to localhost / become false task. Open a regular
   file without following the final symlink, reject nonregular files (including
   FIFO without waiting), read bytes once, and return base64 plus SHA-256 of those
   same bytes. Check descriptor metadata before/after reading for mutation and
   fail closed. Preserve arbitrary binary/large config support without adding a
   new file-size limit. Always close descriptors; static errors disclose neither
   file contents nor paths. Preserve no_log and the existing config record fields,
   source path, mode, secret-content validation and downstream copy semantics.

Built-in stat/slurp cannot return a digest of the same binary read in one module
call. A small module is proposed instead of a cache, shell pipeline or scheduler.
Ansible/Core remains the desired-state and execution authority; no Go/UI changes,
artifact selection changes, bundle publication or installed-service Apply.

## Evidence and gates

Baseline runtime16: prepare 23m06s; target preflight 6m38s. Eleven skipped overlap
tasks total20.2s, fourteen stat and fourteen slurp results total31.7s. These are
observed task durations, not promised savings.

Native isolated RED OS checks: equal/nested/sibling paths, same-library filtering,
duplicate paths, cross-host isolation, text/empty/binary/large files, SHA-256 parity,
missing/symlink/directory/FIFO/unreadable input, mutation rejection and safe output,
existing secret-content rejection and repeated read-only execution. Run affected
runtime contract/render tests and Apply/Verify syntax checks from fresh qa-sync
sources, then clean temporary QA workspaces.

Owner explicitly waived review in this conversation; no reviewer is invoked.
File-read safety is covered by the focused negative tests. Real React/Wails installation
and end-to-end speed acceptance remain pending until a separately coordinated
updated-bundle run; isolated tests do not substitute for that acceptance.

## Status

First slice implemented in `codex/application-preflight-optimization`; owner authorized the commit.
No review was requested or performed after the owner's explicit waiver.

Fresh RED OS101 source transfer: 36 tests, 35 PASS / 1 SKIP, no failures/errors,
67.637s. Modules: `qa_application_preflight_optimization` (10 tests),
`qa_application_preflight_pairs`, `test_application_runtime_contract`.
The historical SSH source-delivery test requires its own explicit inventory and
was skipped; the new isolated native test executes the production source and copy
tasks, checks exact binary bytes/mode and repeat changed=0. This is not remote
SSH target delivery or React/Wails acceptance. Native JSON template rendering,
binary content validation, check mode and secret-safe failure tests passed.

Apply/Verify syntax checks PASS on the same production source. `git diff --check`
PASS. Both temporary qa-sync workspaces cleaned. Local ignored evidence:
`.runtime/qa/preflight/initial-35.log` and `.runtime/qa/preflight/final-36.log`.

Source-file module calls decrease from two to one per file (28 to14 for the
baseline's14 files); the existing record-building set_fact remains. Overlap tasks
still exist, but their loop excludes own-library entries before expansion and
checks each distinct other-library path once. No wall-time saving is claimed.
Current bundle, active installation and published master code were not changed.

Remaining preflight candidates: shared-library calculations, batching filesystem
observations and reducing other inapplicable task expansions. They are outside
this first slice; provider/ClickHouse/Vault optimizations are also not included.

## Resource context batching (owner follow-up)

ClickHouse rendering was committed separately as `41b0fbfb`. The owner then
requested reducing skipped task work. The foreign-library/root filtering is
already committed in `82695173`; it is not a new change in this follow-up.

`resolve_application_libraries` now builds both resource maps in one `set_fact`
per application placement. The previous include loop over connections and task
loop over all resources are replaced by an ordinary Jinja expression. Resource
kind, binding presence and deploymentRef matching retain the previous rules,
including aliases, default empty references and existing map entries. No new
filter/plugin, persistent cache, provider selection rule or external request.
`no_log` and `become: false` remain in place. Legacy topic-role processing still
runs after direct resource keys.

This removes per-resource skipped events from this task (the baseline had 32
results including 24 skips), rather than hiding callbacks or skipping validation.
There is now one context task result per placement, including empty maps. This
does not eliminate all 375 skipped results or claim a 100.6-second stage saving.

Validation uses fresh RED OS sources and target-free native Ansible. Full
React/Wails installation and stage wall-time acceptance remain pending; no
bundle publication, active run or deployed provider has been changed. Review
remains waived by the owner. The owner authorized committing this follow-up.

QA evidence for resource batching:
- Native Ansible test PASS (3.134s): five scenarios, exact expected maps, alias and
  deployment isolation, ignored kinds/missing bindings, provided references,
  preservation of existing entries, empty sets and repeated execution. Exactly
  one context task per scenario, changed=0, skipped=0.
- Apply/Verify syntax checks PASS.
- Initial library selection: 2 PASS / 1 FAIL (157.317s). Named topic inheritance/
  override/reset and ClickHouse connection/history tests passed. The direct-key
  test fixture supplied empty PostgreSQL parameters, rejected by the existing
  deployments schema requiring name; this is not a successful regression run.
  The fixture now supplies its explicit database name and restores that name
  when testing reset. Production validation was not relaxed.
- Evidence retained in `.runtime/qa/resource-context/`; corrected direct-key
  regression is run separately from fresh qa-sync sources.
- Corrected direct-key/alias/legacy collision/reset test PASS (77.910s), including
  rejection of invalid binding and absent required topic. Final focused selections
  total four distinct passing tests; the earlier fixture failure remains recorded.
  Both qa-sync workspaces cleaned. `git diff --check` PASS. No full-suite or
  end-to-end installation performance PASS is claimed.
