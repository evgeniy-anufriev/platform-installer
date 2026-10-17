# SDKU corrections — independent FULL DIFF review

2026-10-17. Reviewer: `/root/library_common_plan_review`. Verdict: **BLOCK**.
Base HEAD: `4aab08d865d0754831c93c70b50cb417c8128afb`.
Scope: 103 files; manifest `.runtime/sdku-corrections-diff-review-scope.json`,
SHA-256 `5cfe5cf9aacd81e643ea6cac8aa667a57985fa7e316717c55057801b150755c9`.
Reviewer verified all fingerprints. Generated frontend assets and portable-source
were excluded. No server installation or runtime activation was performed.

SDKU-PC-P01 is SUPERSEDED by the owner's explicit sequential-execution decision.
No additional tag lock is required or authorized.

## SDKU-PC-D02 — BLOCKING, OPEN

Different libraries can select overlapping runtime roots in a single sequential
run. For example, A uses `/data/sdk`, with instance `/data/sdk/api-a`, while B
uses `/data/sdk/api-a`. Both absent paths pass the initial marker checks; later
materialization of B can overwrite A's instance marker/configuration.

Affected boundary: `application_runtime/tasks/resolve_paths.yml`, library
preflight, `apply_library.yml` and `apply_instance.yml`. This is independent of
the rejected cross-project concurrency scenario.

Smallest correction: standard Ansible assertions over resolved roots before
provider/materialization writes, rejecting equal/nested roots of different
libraries. No new lock. Check both orders, HOME/absolute equivalence and unchanged
target files on refusal.

## SDKU-PC-D03 — BLOCKING, OPEN

The real Wails call reached `EXECUTION_NODE_READY_REQUIRED`; this does not prove
successful Wails → Go → Core v5 negotiation, plan v6 decoding and Review of the
explicit skip while retaining actual UNKNOWN/STALE infrastructure observation.

Smallest correction: obtain positive target-free plans through existing production
bindings on a compatible current-source QA runtime for skip false/true, inspect
Review/fingerprint, and verify unsupported-version refusal. No Start or application
installation is needed. Runtime preparation/activation was not performed.

## Other conclusions

Digest-reference compatibility correction was reviewed without an open finding:
ordinary tags retain their source reference; digest inputs retain the existing
immutable alias path. Affected tests after the final correction remain pending.
Evidence retention, explicit skip binding/version/fingerprint, shared projections
and existing trust/secret/artifact guards were inspected. Reviewer found no
unjustified mechanism. Reported test passes were not independently rerun.

Per the review procedure, automatic work stopped at BLOCK. Implementer recommends
the bounded Ansible correction and target-free acceptance above; no new lock or
server installation. After owner disposition, at most one TARGETED_RECHECK of
D02/D03 and their immediate boundaries is available.
