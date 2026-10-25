# Library progress validation

Implementation branch: master. Base: `3d9c8871b435b3f867f3cf44917557d388c48bb9`.
Owner authorized implementation on 2026-10-25. No installation run, runtime
bundle activation or application container mutation is part of this validation.

## Review

Independent FULL PLAN: APPROVE_WITH_CHANGES, blocking 0. P01 addressed: terminal
FAILED/CANCELLED/INTERRUPTED state stops active child presentation without requiring
a parent ACTION_COMPLETED FAILED event. P02 addressed in acceptance limits: native
and mocked tests do not substitute for real React/Wails/new-runtime acceptance.
Independent FULL DIFF: APPROVE_WITH_CHANGES, blocking 0. LPROG-D01 is a
nonblocking schema/decoder admission mismatch; corrected with a shared negative
fixture and a schema condition restricting steps to application Apply. See the
[review record](reviews/library-progress-review.md). No second review required.

## Checks

- All Go packages: `go test ./...` PASS; `go vet ./...` PASS.
- Frontend: 27 files / 305 tests PASS; lint PASS; production build PASS.
  New tests cover nested rows, unchanged parent execution, leaf counting,
  event replay/duplicates and terminal failure/cancel without parent completion.
- Fresh current-tree RED OS source:
  `/var/tmp/platform-installer-qa-1457f4f7ddb042ed8c1cdcef7ec10d7b`.
  `test_application_progress`, `test_application_image_protocol`,
  `test_application_plan`, `test_application_selection`,
  `test_application_post_install`, `test_execution_task_observability`,
  `test_execution_lifecycle`, `test_infrastructure_verification`:
  214 tests, OK, 7 explicit skips (five isolated root-controller cases and two
  existing isolated infrastructure native cases). No failures.
- Actual subprocess protocol: resolver/planner/manifest and new plan/capability
  schemas agree; selected plan excludes skipped provider installation steps and
  retains its integration credentials/manifest admission.
- Native Ansible callback: actual production start/end marker tasks on two local
  inventory hosts, success, second-host failure and skipped markers PASS.
  Failure has TASK_COMPLETED FAILED on the second host and no child completion.
- Callback tests reject wrong-parent/no_log/extra-field/invalid-ID marker
  content; synthetic payload sentinel does not enter the journal.
- Go retains child metadata across cloning and local run-record reopen/rollback.
  Duplicate/colliding step IDs and steps attached to service actions are rejected.
- Both temporary RED OS source directories were cleaned with qa-sync after the
  initial and extended checks. Post-review D01 uses one further fresh workspace
  for its focused schema/protocol check, cleaned after completion.
- Post-review D01: affected Go package PASS; fresh RED OS progress/actual image
  protocol suites 22 tests PASS, no skips. Shared invalid service-progress JSON
  is rejected by both schema and decoder. Its temporary source workspace
  `/var/tmp/platform-installer-qa-5f08004191e543859362134a99541e46` was cleaned
  with qa-sync. `git diff --check` PASS after generated HTML line normalization.

An initial frontend test fixture omitted mandatory event fields and failed;
the fixture was corrected and the complete 305-test run then passed. The initial
Core subset was 77 tests / 5 skips; the 214-test run above supersedes it.

## Acceptance limits

The subsequent owner-authorized [all-libraries installation](szi-stage3-all-libraries-journal.md)
published/activated runtime03 46e624e5 and completed actual React/Wails
Plan/Approve/Start: installer-432346595068ea5f1067aeb5a60ebd9f SUCCEEDED.
The UI confirmed preparation, szi, sdku, cspa, Verify and post_install,
100%/6 of6. Its terminal1280px screenshot was visually inspected.

Real delivery exposed a UI ordering defect: an ACTION_STARTED arriving after
a newer TASK event did not activate its child. An independent action-boundary
sequence now controls active status. The failing regression passed after the
fix, and actual subscription replay restored preparation without restarting
execution. Parent rows are unnumbered groups; leaf numbering matches the
counter. Frontend307/focused33/lint/build PASS. Core's existing explicit library
order also had to be forwarded for the full-selection path; real native
controller-to-Ansible tests cover full order, skipped scope and the old failure.

Existing runtime plans/records without children remain supported. Orphan
reconnect after a Wails restart is still not tested; replay within the current
Wails process is separate evidence.
