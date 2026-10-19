# Kafka defaults and named application roles — evidence

Owner accepted existing `resource_defaults` design on2026-10-19; then explicitly
requested replacing `alarms-main*` with `sdku-alarms*` everywhere in current
configuration. No application installation/restart or Kafka mutation authorized.

## Implementation

- `resource_defaults.kafka.topics.<resourceId>` parameter templates; package ->
  instance resource_defaults -> selected resource.parameters, recursive config.
  Defaults alone create nothing; existing RF/minISR uses the selected deployment.
- Built-in Ansible tasks bind named `application_topics.<alias>.<role>` before
  parameters/ENV, resetting context per placement. The same merged resources
  feed snapshot/provider jobs. Existing Python projection supports role maps
  alongside unchanged legacy lists; no new Python script.
- Guarded Save stays node-free. Existing Go writer accepts both forms without
  precedence logic; Core adapter/Wails transport preserves list/map shapes.
- Resources can select default IDs without copying effective names/settings.
  Named role selects, explicit clear and per-role Reset reuse draft/Review/Save.
  Core names are hidden for draft/stale revisions. CH schema controls stay hidden.
- SDKU declares only used roles, moves standard topic names into four library
  templates, removes obsolete topic parameters. Standard families are
  `sdku-main*` and `sdku-alarms*`; existing topic ENV overrides remain possible.
  Images, commands, TLS, identity/port behavior remain outside this extension.
- Owner's subsequent logical-ID correction uses main/main_compact/alarms/
  alarms_compact for templates, resources and application binding values.
  Physical sdku-* names remain in library name fields; a CSPA library can supply
  its own names for the same IDs. Final27-schema/26-render checks and native26/
  378-task PASS were repeated for this final package data, in
  `topic-roles-logical-renders.log` and `topic-roles-native26-logical.log/json`.
- Owner's name correction also applied to two local desired-state copies:
  `.runtime/qa/sdku-data-manager-project` and `.runtime/qa/sdku-env-ui-project`,
  inventory group_vars and their existing HMI package. Historical results/plans
  and server configurations were preserved. Original working project runtime
  lock remains40; new role QA uses an isolated copy/runtime41.

## Focused checks

- RED OS current-tree native snapshot plus Core/provider/runtime tests:59 tests
  OK, one existing skip. Covers defaults/config precedence, rename, role switch,
  reset, explicit ENV/reset, no implicit creation, multihost/library isolation,
  cleared/missing/wrong-binding rejection and legacy lists. Existing unit tests
  exercise standalone/cluster RF/minISR independently.
- SDKU schema/digest validation27, synthetic Compose renders26, shared base
  variants1 PASS. Full native resolver/render26 apps:378 tasks, failed0,
  changed1 only writes the owned nonsecret QA JSON artifact; no target contact.
- Go `go test ./...`, `go vet ./...` PASS after transport change; frontend258
  tests, build and lint PASS. Build retains existing chunk-size advisory.
- An initial mass-edit YAML error was caught by package import/render checks,
  restored from the exact pre-extension current-tree copy and corrected; final
  checks above use repaired packages. No malformed package was deployed.

Local bounded evidence logs: `.runtime/qa/topic-roles-core-final.log`,
`topic-roles-sdku-render-final.log`, `topic-roles-native26.log/json`,
`topic-roles-go-transport-final.log`, `topic-roles-vet-transport-final.log`,
`topic-roles-ui-tests-final.log`, `topic-roles-ui-build-final.log`,
`topic-roles-ui-lint-final.log`. These are QA artifacts, not desired state.

## Real React/Wails gate

Runtime41: `sha256:e6ac45576762e68fb816810732889be3803e408f2e1a4ded29a6edf06298ce52`,
906 components, built on trusted .102 from current sources, verified and published
with the standard publisher. Previous runtime40 preserved locally.
Isolated project `.runtime/qa/topic-roles-ui-project`; existing SSH identity,
independent host-key comparison and real handlers/bindings. No Approve/Start.

Initial QA copy had mismatching runtime locks between optional project.yml and
inventory; Wails Verify returned UNVERIFIED before CRUD. Both were corrected to
the same verified41 digest, then normal UI preparation requested UPDATE_REQUIRED.
The isolated app originally lost its project-specific Sentinel/account
declarations when replacing its package with generic defaults. These QA-only
declarations were preserved from its original package; native standalone
configuration remains the same as the accepted working project.

Real Save/reopen/reset/Verify PASS: default resource added without copying name,
role selected to sdku-alarms-2, resource renamed to sdku-alarms-3, then role Reset
restores sdku-alarms-compact on all three placements. Save revisions:

- b0d1adbee006a242c611e422f43eb2b0783420dd7532b803f8f23405c827ec7d
- 2353cc70e6c042eff72b0f2a78fec318422d5eb30b1866adcb087c5fcb1054ac
- 1999b16147cea7a1e964aebab33c0a3fa31ffe0e062e60e09ec07edaf28c2ead
- final/reopen32fd489ac4abe59a31d2e2e470c826729d3b958b94e6e1782a4d9ebff1def1f3.

During an earlier attempt, Verify after successive Saves returned UNVERIFIED /
EXECUTION_RUNTIME_IDENTITY_UNCONFIRMED (a preceding generic PROJECT_VERIFY_FAILED
was also observed). Live execution context had reset to NOT_PREPARED / node1 /
AUTO_FIRST_ELIGIBLE. The same files passed native Ansible (45 tasks, changed0),
Go snapshot decode and production OpenSSHTransport snapshot on .103. Selecting
node3 through React instead of the old driver's direct Go selection did not by
itself prevent the reset. Its cause/regression attribution is not established.
Final CRUD explicitly restored node3 once through ordinary React selection,
session identity and independently checked host-key approval; subsequent Verify,
rename, Reset and reopen passed. This proves persisted topic behavior, not
preservation of the previous READY binding. No production lifecycle fix/bypass
was introduced. Safe earlier evidence is retained as
`topic-roles-ui-crud-context-loss.json`; final CRUD is
`application-design/topic-roles-ui-crud.json` and `topic-roles-ui-crud.log`.

Fresh real React/Wails plan `plan-bc8e8e3d9cecb457c7d725b4` EXECUTABLE on the
same final32fd489a revision, Verify VERIFIED, runtime41 e6ac4557. Exactly
APPLICATION_LIBRARIES_APPLY + APPLICATION_LIBRARIES_VERIFY,
skipInfrastructureVerify=true. Explicit QA guards reject Approve/Start, neither
was invoked. Final evidence `application-design/topic-roles-ui-final-plan.json`
and `topic-roles-ui-final-plan.log`. No server table/topic/application writes.

Independent [FULL DIFF](../reviews/topic-role-bindings-diff-review.md) APPROVE,
zero open blockers; TOPIC-D01 stale-label correction RESOLVED in the original
FULL. Source63 hash9dd6f60f and all five runtime component hashes confirmed.
Execution-context limitation above is retained separately, not claimed fixed.

All six owned RED OS source/test/build workspaces cleaned using qa-sync cleanup
(logs topic-roles-cleanup1..6). Immutable local runtime40/41, protected runtime
identity/input files, local QA evidence and original working project preserved.
No visual/manual WebView, server Kafka mutation, application deployment or full
Core-suite acceptance claimed. Source changes remain uncommitted.
