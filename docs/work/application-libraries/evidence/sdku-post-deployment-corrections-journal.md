# SDKU post-deployment corrections — source-only evidence

2026-10-17. Owner approved all seven corrections, explicitly rejected SDKU-PC-P01
and forbade a new daemon/tag guard. Supported execution is sequential. No target
installation, runtime publication/rebind/activation or StartExecution performed.

Ansible tasks own target HOME expansion/path checks, original-tag assignment and
pre-start image identity check, Compose rendering and ordinary Apply/Verify paths.
No new production Python file. Existing Python edits are limited to target-free
shared connection projection/Registry reuse and the existing execution protocol,
plan/admission and evidence lifecycle; role tasks cannot own pre-execution admission.
Application task-domain classification/persistence removed, not replaced.

Focused RED OS tests: library projection19 PASS (three Registry members/member
ports/disabled), runtime contract16 PASS, infrastructure37 PASS/2 standard skips
(including explicit skip, manifest tamper, no fabricated evidence and retained
application-stage evidence). SDKU package27/prepare2/render26/one shared base PASS
before final alias cleanup; final source confirmation follows below.
Go affected packages PASS; new lifecycle skip-tamper and runtime-directory Save/
Reset tests included. Frontend focused43/typecheck PASS. Final broad gates pending.

Real React/Wails .runtime/qa/application-design/sdku-corrections-wails.json:
- library-directory actual guarded Save/reopen and Reset/Save/reopen PASS;
- explicit true skip reaches actual CreateInstallationPlanForMode Go binding;
- default false and execution-mode reset PASS;
- isolated copy Build returns BLOCKED EXECUTION_NODE_READY_REQUIRED. This is not
  a positive new-protocol UI/Core plan acceptance and does not prove installation.
No Start call. Visual acceptance not performed. New packaged runtime positive
UI/Core acceptance remains unavailable without separately authorized runtime work.

Full initial Core regression is running against its frozen preliminary workspace;
latest production source changes require final focused current-tree checks.
One independent FULL DIFF review follows exact final source fingerprints and
must respect the owner-rejected blocker; no additional lock is authorized.

Final recorded focused evidence: Go `go test ./...` and `go vet ./...` PASS;
frontend 252 tests, typecheck and lint PASS. Latest RED OS focused run: infrastructure
38 PASS/2 standard skips, runtime16 PASS, libraries19 PASS; SDKU27 package checks,
prepare2, render26 and sharedBase1 PASS; two native path/default/reset checks PASS.
These precede the final digest-reference compatibility correction; no final-source
full-regression PASS is claimed. Preliminary broader Core run was still active
when the review returned BLOCK.

Independent FULL DIFF returned BLOCK, D02/D03; see
[report](../reviews/sdku-post-deployment-corrections-diff-review.md).
The rejected P01 is superseded and was not reopened. Automatic implementation
stopped under the mandatory review procedure. D02 requires a bounded standard
Ansible overlap assertion, not another lock. D03 requires positive target-free
Wails/Core acceptance on a compatible QA runtime, not an application installation.

## Owner-authorized D02/D03 correction

Owner authorized the bounded correction and QA runtime work on 2026-10-17.
D02: `resolve_paths.yml` now compares each resolved absolute root with earlier
host-local preflight rows. Different-library equal/nested paths fail before
provider/materialization writes; same-library placements and sibling roots pass.
Only builtin Ansible assert/loop is added; no lock or production Python change.
Native current-source test PASS: HOME/absolute equality, both nesting orders,
siblings, same-library reuse and existing invalid traversal. The included tasks
only set facts/assert and do not write markers, configurations or provider state.

Final affected runtime contract16 PASS, including source tagged reference and
digest-pinned alias compatibility. Final frontend production build PASS.
Preliminary broader Core run: 705 tests/21 skips, one stale assertion expected
an explicit Redis client selector to be rejected for a Sentinel declaration.
The approved selector behavior takes precedence; corrected test asserts the real
client member/port projection. Current-source member projection4 PASS. This is
not represented as an all-final-source full-suite PASS.

QA runtime `sdku-corrections-20261017-08` built from current sources on .102,
validated and published with the standard publisher, prepared on .103 using
the standard resumable promotion helper. Exact digest:
`sha256:9df8b8d7facba2c767023dfc155a52227124d745014d8392050ebe3d0e3fb735`.
Saved QA revision after lock rebind:
`sha256:1866004c81b9a27027866768135bbe8f0b6395c6801afae53691386bfbc20895`.
The isolated QA project contains Docker and one minimal application declaration
using the verified source DM image archive; no container is started. Service
payloads not used by this QA project and the unrelated probe archive are omitted.
The full initial build failed for disk capacity; the bounded build used temporary
RAM storage for immutable runtime inputs, now removed. No existing runtime release
or service data was deleted. Owned temporary source/build workspaces were cleaned.

D03 positive acceptance on the final UI/Core path PASS: real React handlers and
Wails Go methods, trusted selected node3, saved revision
`sha256:2c4ab1653db164b914541f025c02f7fbf1750c7162146ea715d7c092f0757203`.
Default false plan `plan-175cd94bfff8339c989b47e8` is EXECUTABLE/PLAN_REVIEW,
with SERVICE_VERIFY before library Apply/Verify. Explicit true plan
`plan-907024a7bff353ef8f299c0b` is EXECUTABLE/PLAN_REVIEW, with only library
Apply/Verify. Fingerprints differ; both retain the identical actual infrastructure
observation BLOCKED/INFRA_VERIFY_STALE and null evidenceRevision. No fake PASS.
The true plan's risk notice was observed in Review. Neither plan was approved or
started. Safe evidence: `.runtime/qa/application-design/sdku-corrections-plan-asserted.json`.

Acceptance exposed and corrected one immediate UI issue: changing only the skip
option left the prior plan approvable and hid its fresh Build button. The skip
change now invalidates current approval and offers Build; tests cover both toggle
directions. Existing owner-approved B4 mode-change/rebuild-on-Approve behavior is
preserved when the skip flag is unchanged. Focused UI33 PASS. No production Go or
Python correction was needed for this finding.

The initial QA-project input error was APPLICATION_ARTIFACT_LOCK_CONFLICT: its
ordinary group_vars lock still named runtime07 after the manifest lock rebind.
Only the isolated QA input was aligned; the Core conflict guard was retained.
The running QA Wails process also retained its old cache path; the existing owned
restart helper loaded the new published cache before positive acceptance.

Negative compatibility evidence: native retained runtime07 rejects new GetCapabilities
v5 with EXECUTION_PROTOCOL_INVALID. Focused Go negotiation/no-fallback and retained
flag/rebuild-tamper tests PASS. Positive flag acceptance therefore exercises the
new capability/plan protocol; unsupported runtime refusal is not silently replaced
with an old request. Visual inspection was not performed or claimed.

Local temporary input cleanup was rejected by automatic approval policy; the
owned `.runtime/qa/sdku-corrections-runtime-input` directory remains. No workaround
delete was attempted. New QA bundle/cache and evidence remain available.

Final UI253/build/typecheck/lint PASS after the bounded toggle correction.
Real React/Wails positive false/true acceptance repeated against the final UI;
same revision, plan IDs and fingerprints reproduced. Native diagnostic source
workspace cleaned with qa-sync. Independent owner-approved TARGETED_RECHECK
D02/D03 requested against 104 current fingerprints, manifest
`.runtime/sdku-corrections-targeted-review-scope.json`, SHA-256
`33314425319330a96552675eb9998775351d93adb5845a186c4034a2594e5ab2`.
No fingerprint drift at dispatch. No further FULL review or application Start.

Independent [TARGETED_RECHECK](../reviews/sdku-post-deployment-corrections-targeted-recheck.md)
APPROVE: D02/D03 RESOLVED, zero unresolved blockers, 104/104 fingerprints match.
P01 remains superseded; no additional review or lock required. All seven source
corrections and bounded plan acceptance are complete. Application installation
and visual acceptance are outside this closure and were not performed.
