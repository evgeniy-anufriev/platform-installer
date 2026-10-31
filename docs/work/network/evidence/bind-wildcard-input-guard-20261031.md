# BIND wildcard input guard — 2026-10-31

Owner production diagnostic: run installer-fdae863d27dee46cd8689e27fff2ce54
failed on node1 while validating an A-record update. Read-only recalculation of
the saved project through its active Core returned PASS and included
`*.installer.scada.local.` -> `10.21.38.117`, TTL300. The role's ordinary DNS
owner regex rejected the wildcard which Core and the zone renderer support.

The production change adds only an optional literal leftmost `*.` label to the
existing owner regex. ASCII, length, remaining labels, trailing dot and zone
containment checks stay unchanged, as do address/TTL, authoritative-answer,
CNAME, DNS prerequisites and post-update verification. No Go/UI changes,
additional resolver, persistence or source-selection policy were introduced.

## Regression and QA

The existing nested-include test now obtains its zone from the production
`resolve_dns_zones` with a wildcard endpoint group, then runs the real BIND
base-record/update/prepare includes twice against an isolated dig fixture.
It checks wildcard and ordinary owners and unchanged repeat behavior. Native
guard negatives cover internal/repeated stars, out-of-zone names, uppercase,
missing trailing dot and newline/command input. Update rendering checks the
literal wildcard owner and its DNS prerequisite.

Before the role fix, this pipeline reproduced
BIND_DNS_A_RECORD_UPDATE_INPUT_INVALID on the exact owner-regex assertion for
`*.example.test.`; failed1, changed0. After the fix, current sources transferred
with qa-sync.ps1 to RED OS101 passed:

- focused zone batch/runtime: 5 tests, 12.501s, no skips;
- Core DNS resolution: 14 tests, 0.019s, no skips;
- full BIND suite including native isolated runtime/prepare checks: 27 tests,
  31.644s, no skips.

Only isolated temporary directories/processes were used; running target DNS
configuration was not changed. Source workspaces were cleaned with qa-sync.ps1.
Safe outputs: .runtime/qa/approval-target-trust/bind-before.txt, bind-after.txt
and bind-suite.txt. Other pre-existing worktree edits were preserved.

Prior tests covered wildcard zone rendering and ordinary dynamic-update owners
separately. They did not carry a Core wildcard through the actual update input
guard. Historical deployment success alone does not establish which bundle or
wildcard update path was exercised.

## Review and acceptance limit

Independent FULL DIFF APPROVE, blocking0; base
37ff44ee2b6e0b3c031215d96c30753e4c417e45; two-file source diff SHA256
07dda0e45d7ec4b4113adde3f3016aff5887e0778a6f0b0068ff04ba6cf95257.
No unnecessary mechanism or nsupdate text-injection expansion found.

No updated bundle was built/published/activated and no React/Wails installation
was started for this change. The configured node2 acquisition/build host
192.168.56.102 SSH timed out; bundle-dependent UI acceptance remains pending.
The source fix must be included in a rebuilt runtime bundle and activated
through ordinary node preparation before a new installation can consume it.
No full deployment, visual or production acceptance is claimed.
