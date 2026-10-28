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
