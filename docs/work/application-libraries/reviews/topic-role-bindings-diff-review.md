# Kafka defaults / topic roles — independent FULL DIFF

2026-10-19, `/root/topic_roles_plan_review`, architecture-reviewer, read-only.
**APPROVE; zero open blockers.** One original FULL DIFF; no targeted recheck.

Base `a5ce142cfb9f29dbab524d45b0ec6f3cb6ef73fb`. Fingerprint of63 reviewed source
files: `9dd6f60f109b6333a34e321c00593143a1c4212b55dff5f9767ab7e5233e84d0`.
Method: SHA-256 of sorted path + NUL + SHA256(raw file) + LF. Scope includes
changed Core tasks/projection/tests, schemas, Go transport/writer tests, Wails
model, UI sources/tests, SDKU packages/catalog/config example/validator and new
topic_roles.yml. Generated dist and evolving journals excluded. Rechecked after
freeze, matching. Previous ENV/port work separated using exact26-default baseline
`.runtime/qa/topic-roles-before-packages`, fingerprint
`4e888b9622527f5bea030e33fc03b4b998161a29982a7a4034cc84882ead11b9`.
Reviewed plan after owner data-name corrections:
`297d7bbd404ae30a51e4348f38a5b562b5a933f57e4209301c50fac5c60b1ec8`.

TOPIC-D01 NON_BLOCKING: stale Core topic labels in draft/other revision.
OPEN -> RESOLVED within this FULL. Both forms now receive empty projection for
draftActive or revision mismatch. No other implementation findings.

Reviewer confirmed early per-placement context before ENV, one merged resource
set into provider planning, no implicit default resource creation, invalid/empty/
wrong-provider rejection, preserved legacy lists, Reset deleting overrides and
logical IDs reusable in CSPA. Go/UI add no topology/precedence resolver. Images,
commands and nontopic settings match the pre-extension baseline.

Overengineering: zero unnecessary mechanisms. Small standard Ansible sequence;
derived application_topics; existing transport map shapes, RF/minISR/provider
jobs. No Python script, new DTO/API/store/lock/defaultsRef/startup lookup.

Evidence inspected directly: focused Core59/one skip, final logical native26/
378tasks/failed0 (changed1 synthetic artifact),27 package schemas/digests/26 renders,
Go tests/vet and frontend258/build/lint. Reviewer did not run tests or servers.
All five changed runtime files match published runtime41 e6ac4557 byte hashes.

Real React/Wails evidence independently checked: resource selection, role switch
to sdku-alarms-2, rename to sdku-alarms-3, Reset, Save/reopen and ENV/projection
agreement. Final revision
`sha256:32fd489ac4abe59a31d2e2e470c826729d3b958b94e6e1782a4d9ebff1def1f3`;
Verify VERIFIED; `plan-bc8e8e3d9cecb457c7d725b4` EXECUTABLE, exactly Library
Apply/Verify and skipInfrastructureVerify=true. No Approve/Start.

Separate evidence limitation: selected-node/READY context was lost after Save,
with EXECUTION_RUNTIME_IDENTITY_UNCONFIRMED. Final successful flow included one
ordinary React selection/trust rebind of node3, explicitly recorded. Cause and
regression attribution are unproved; preservation of prior READY binding is not
confirmed. Direct native/transport checks did not replace real UI acceptance.

Validity CURRENT for the above fingerprint/owner decisions. Production or
contract changes require assessing affected validity; journal additions do not.
Approval does not authorize application installation or Kafka mutation.
