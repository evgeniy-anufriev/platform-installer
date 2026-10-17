# Library common defaults — independent FULL DIFF review

2026-10-17. Independent architecture-reviewer: **APPROVE_WITH_CHANGES**,
zero unresolved blocking findings. One FULL DIFF review; no repeat review.

Base: `8feb047af1c24c70ede737fe03941b9bbf04ac3c`.
Reviewed manifest: `.runtime/library-defaults-review-scope.json`, SHA-256
`c33cd5202029a8be1ad52f050c34df19462e1f19098624e1a1d2ae57e5dda0b5`.
All141 entries verified, including deleted generated assets: zero mismatches.
Reviewed updated plan SHA-256:
`3c474f690eeca8d81e1a3b688f1f2fc94036804e8a41493da23bb2f1706eed4b`.

## Findings and bounded corrections

- **LCD-P01 RESOLVED:** Core exposes inherited values without instance overrides;
  UI uses the matching saved revision and hides stale baseline after edits/Reset.
- **LCD-P02 RESOLVED:** common resolution precedes application jobs, uses isolated
  native templating and refuses the tested indirect application-context reference.
- **LCD-D01 NON_BLOCKING, corrected after review:** selected baseline host could
  remain absent from a newly selected placement. One selectedBaselineHost now
  drives both lookup and select. Focused UI test changes to disjoint placements,
  checks the selected host and displayed inherited value, then checks Reset.
  Final focused17/typecheck PASS. Reviewer explicitly allowed this bounded fix
  without another architecture review.
- **LCD-D02 NON_BLOCKING, remaining tests recorded:** dedicated native cases for
  two libraries with distinct common overrides, reversed jobs with frontend first,
  and comparing base bytes of multiple consumers were not executed. Existing
  native composition/Reset/opt-out and package render checks do not replace them.

## Architecture and overengineering

Zero unjustified abstractions, duplicate contracts/DTOs, premature features or
missed simpler mechanisms. Two read-only baseline fields serve different concrete
needs: shared runtime Compose and inherited editor Reset. Existing Ansible
templar/combine, guarded writer commands and UI controls are reused. No new
resolver, daemon, storage, profiles, deployment lifecycle or CRUD API.

Packages/group_vars remain desired state. Runtime base/snapshot are derived;
Go/React do not calculate Ansible precedence. SDKU slots contain no overrides;
frontend inherits its separate base, independent of alarm-service.

## Evidence limits

Reviewer inspected code/schemas/templates/design/tests/journal and verified the
141-entry identity and git diff --check. Generated assets were fingerprinted,
not deeply reviewed. The local Wails evidence file records REAL_WAILS/PASS,
five cases and zero target operations. The reviewer did not independently
rerun tests/UI or contact targets/read secrets.

Go/frontend/native results and the baseline failure comparison are implementer
evidence, not independently repeated review evidence. No real UI Verify with
a newly published runtime is claimed. Cleanup was rejected by automatic policy;
exact retained paths are in the implementation journal. Review does not authorize
installation or change the owner's explicit no-start scope.
