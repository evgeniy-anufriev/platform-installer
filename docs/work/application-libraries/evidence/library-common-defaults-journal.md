# Library common defaults — implementation evidence

2026-10-17. Owner authorized the updated plan and requested minimal implementation,
without server installation/start. Production changes stay in the existing Core
action/resolve role, snapshot, runtime template context, Go writer/transport and
React controls. No new API, daemon, persistence store or expression parser.

## Implemented behavior

Library defaults contain only ENV/parameters. Native Ansible composes common
defaults, application defaults, legacy slot overrides, library group_vars
overrides, instance overrides and legacy host overrides. SDKU has no slot/host
overrides. inherit_defaults=false skips both common layers. Common expressions
resolve before application jobs, using raw host vars and an isolated Ansible
context without application facts, hostvars, vars or ansible_facts aliases.

Rows/snapshot expose commonDefaults and inherited ENV/parameters; runtime receives
library_runtime.defaults. Inherited excludes instance overrides. UI library Common
parameters uses the existing field controls and writer commands. Instance Startup
uses a matching saved-revision Core baseline; edits/reset hide stale baseline and
request fresh verification. A host selector handles distinct placement baselines.

## Checks

| Check | Evidence |
| --- | --- |
| Windows Go | go test ./..., go vet ./..., go build ./... PASS |
| Writer | Common Save/reopen/reset writes deployment.overrides, creates no empty slot; image/command/provisioner common addresses rejected |
| SDKU import boundary | Native Go manifest/digest check27 PASS |
| Frontend |249 tests/22 files PASS; typecheck, lint, build PASS |
| RED OS affected Core unit scope |50 tests PASS: application_libraries/runtime_contract/plan/member_projection |
| Native inheritance | Common → own default → common override → instance override; both Reset levels, numeric parameter and opt-out PASS |
| Native context isolation | Indirect reference to an old application_name refuses safely; no stale application value reaches common defaults |
| Native + edit-contract broader run |20 methods; three pre-existing failed assertions in two methods, zero errors; remaining18 methods pass |
| SDKU current source |27 package schemas/digests, two example jobs,26 native synthetic Compose renders PASS |
| Actual React/Wails | Common ENV Save/reopen/reset, numeric common parameter Save/reset/reopen, instance ENV Save/reopen/reset/reopen PASS |
| Stale baseline UI | After instance reset/reopen, explicit override disappears and UI requires Core Verify; no stale inherited value presented |
| Visual inspection | Common parameters tab inspected at1440×900 and1024×720; scrolling content and fixed footer remain usable |

Real Wails evidence: `.runtime/library-defaults-wails.json`, fixture
`.runtime/library-defaults-ui-project-1792222644384`; five recorded cases,
bridge REAL_WAILS, targetOperations0. Native source workspace:
`/var/tmp/platform-installer-qa-0242fb5dbeb34628894c18fe309047e0`.

The first native run also exposed a test environment collection-path omission.
The fixture now includes the existing service collection roots; validation then
passes. Three remaining assertions expect all password/token-named arbitrary
parameters/resource fields to be suppressed, while current contracts permit
user-authored arbitrary names. They fail identically with the baseline
`application_libraries.py` from HEAD8feb047af1c24c70ede737fe03941b9bbf04ac3c:

- test_plaintext_never_returned_in_projection;
- test_free_resources_grants_endpoint_never_leak_secrets, resources/grants subcases.

The comparison used the exact HEAD source module in the isolated QA workspace
and restored the current module afterward. No skips were added, assertions
removed or production secret checks weakened. No complete native-suite PASS.

Earlier fixture-only stale digest and generator failures remain historical in
SDKU validation notes. Current native failures above are distinct baseline cases.

## Acceptance limits

No service installation, application/container start, provider mutation, image
download, bundle build/publication or activation was performed. The installed
older bundle does not implement the new schema. Real UI Verify using a newly
published bundle is not claimed; inherited-value calculations were exercised
through the current-tree target-free native Ansible path, UI presentation through
focused tests, and actual local Save/reset through real React/Wails.

## Independent review and final correction

[FULL DIFF](../reviews/library-common-defaults-diff-review.md):
APPROVE_WITH_CHANGES, zero blockers. Reviewed141-entry fingerprint
`c33cd5202029a8be1ad52f050c34df19462e1f19098624e1a1d2ae57e5dda0b5`.
LCD-P01/P02 resolved. LCD-D01 corrected with one selected host for both baseline
lookup/select; focused17 and typecheck PASS after that bounded correction.
The full frontend249 run preceded that correction; affected tests were rerun.
No additional architecture review was required for the nonblocking UI correction.

LCD-D02 remains an explicit additional QA scope: native independent common
overrides across two libraries, reversed jobs with frontend first, and identical
base bytes for multiple consumers. These are not marked PASS.

## Cleanup exception

Standard qa-sync Verify confirmed the tested RED OS tree. The combined cleanup
command was rejected before execution by automatic approval policy with
`blocked by policy`, without a detailed reason. No bypass or repeat deletion.
Retained own paths:

- RED OS `/var/tmp/platform-installer-qa-0242fb5dbeb34628894c18fe309047e0`;
- local `.runtime/library-defaults-ui-project-1792222644384`.

The local fixture was copied without its source .runtime, uses synthetic common
parameters and is closed in the real app. Existing owner-retained QA directories,
credentials, source server and target services were not cleaned or changed.
