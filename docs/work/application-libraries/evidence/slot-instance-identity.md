# Slot-based application identity

2026-11-07. Owner requested using the slot name rather than the package name
for application instance IDs and permitting several slots to reference one
package. Qualified IDs are `<slot>-<library>`; the existing `application-name`
strategy uses `<slot>`. Slots matching package names keep their previous IDs.
Different aliases change IDs; installed resources are not renamed or migrated.

The preparation job computes the ID once and both native resolution passes
consume it. Projection validation checks the same rule. Script endpoint selectors
resolve explicit slots first; the package-name fallback remains only when unique.
Package loading remains invocation-scoped: two libraries sharing one package,
including a second selected slot, load three packages in total for five jobs.
No extra Ansible task, subprocess or I/O was added to a placement.

RED OS current-source checks: 36 application-library unit tests, one native
same-package/two-slot/two-host resolution test, one native connection test and
five endpoint-stage tests passed (43 total). The native test checks independent
slot/host Jinja contexts and overrides. The script-selector regression checks
slot selection and rejection of an ambiguous package-only selector.

Real React/Wails flow: Open -> bind verified runtime -> SSH trust/check ->
Prepare -> manual Project Verify. Published/activated runtime:
`sha256:1ce50e78b4cb11d331476a8e56e831ef2a2dbf9554bb052e82e4afcf3864e1b3`.
Saved revision:
`sha256:086f09fc2df5a3ec3e8c4448dc352f761e76b946189d0b5231b74b0de0920e0e`.
Verify returned VERIFIED in 39.326 seconds. The returned snapshot contains
`alarm-view-service-qa5-sdku` and `alarm-view-service-copy-qa5-sdku`, both referencing
`alarm-view-service`, each on node1/node2. Existing SZI Keycloak remains selected.
This used a target-free test bundle with installed Execution Node prerequisites;
no Plan, Start, service installation or visual acceptance was performed.

Initial QA fixture failures were corrected before this result: the native
replica needed a distinct published port, and placement-context Jinja belongs in
package defaults rather than a prematurely expanded desired-state override.
The final production-code validation used the master-based source, excluding
the optimization branch's unrelated pending provider changes.

Safe local evidence on the optimization worktree is under
`.runtime/qa/slot-identity-1107/` (`wails-results.json`, `wails-instances.json`,
`publication.json`). No credential values were persisted in this evidence.
