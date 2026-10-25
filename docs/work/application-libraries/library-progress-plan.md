# Library progress within the existing Apply operation

Owner authorized implementation on master on 2026-10-25. This changes progress
presentation, not the installation sequence or service verification rules.

## Implementation

1. Core adds optional `progressSteps` to application Apply actions in plan/v1alpha10.
   Each step has an ID and summary: shared preparation, then installed libraries
   in the resolved library order. Skipped libraries have no installation step.
   Existing Verify and post_install actions remain ordinary leaves. The execution
   manifest, operation list and number of Ansible processes remain unchanged.
2. Advertise the new plan contract with an application progress capability. The
   Go adapter continues accepting older runtime plans without progress steps.
   Steps are display metadata included in the existing plan fingerprint, never
   executable operations. Transport bounds and unique IDs apply to steps too.
3. Use explicit built-in debug markers at the beginning/end of shared preparation
   and each installed library. The existing callback recognizes a closed tag and
   bounded marker payload and emits existing ACTION_STARTED/ACTION_COMPLETED
   events with the step ID. Completion is emitted only after successful work on
   all hosts (linear strategy, any_errors_fatal, run_once marker). A skipped marker
   is not success. No task-name or arbitrary output parsing. Callback task events
   continue to use the parent action ID; execution failure/cancel remains governed
   by the existing parent operation. No invented completion for an interrupted step.
4. Go decodes, clones and projects the optional steps into the existing plan view;
   its existing local run snapshot/reconnect retains them. No new persistence.
5. React shows child rows in plan/execution/result. Progress counts leaf steps
   instead of their parent, plus ordinary actions. Parent outcome is still retained
   for errors. Shared preparation/each library get equal work units; this is
   completed work, not elapsed-time prediction. An active child remains visible
   while ordinary parent task events arrive. Parent failure terminates the active
   child display without marking its work successful. Terminal run status also
   ends the active display: current controller failures need not emit a parent
   ACTION_COMPLETED FAILED event. Existing missing-event and
   reconnect rules remain in force.

## Validation

- Core schema and actual protocol plan projection, unchanged manifest operations,
  ordering/skipped/all-skipped cases; callback tests for success, skipped markers,
  duplicate/replay events and safe payloads.
- A real target-free Ansible fixture on RED OS exercises tagged markers across
  two inventory hosts, failure before completion, and normal callback journal.
- Go decoder/clone/desktop snapshot tests; all Go tests and vet.
- React progress/render/replay/failure tests; frontend tests, lint and build.
- Bounded real React/Wails transport check if the existing bridge is available;
  no installation plan Apply/Start or target-container changes in this task.
  Unavailable real bridge keeps that acceptance gate open.

## Review and limits

One independent FULL PLAN review before implementation; one independent FULL
DIFF review because the versioned public plan contract changes. Review procedure
and owner decisions govern blockers. No installation run is authorized by this
progress change. Real multi-library installation acceptance remains a separately
authorized run; unit/fixture checks do not claim that acceptance.
