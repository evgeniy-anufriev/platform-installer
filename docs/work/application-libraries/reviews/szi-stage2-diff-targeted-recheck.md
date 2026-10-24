# SZI-STAGE2 — TARGETED_RECHECK D01–D03

Independent reviewer `/root/szi_stage2_plan_review`: **APPROVE — DIFF / TARGETED_RECHECK**.
SZI2-D01, D02, D03: **OPEN → RESOLVED**. New adjacent blocking regressions:0.
This closes the scoped architecture findings, not full-library acceptance.

Identity: branch codex/szi-stage2, base/HEAD327c0b76af5ff315c2a104abb1248de042debe5c;
source04553f581d9c13521ce3c50c26b9d6cdb4d3de8e7faaaf39f4bc143436c4a79e;
planb0df5e8c74115628312e4c9b7a3da216f364ec25cfe28fcfe50e711c4bea4ea0.
102 paths; reviewer independently matched fingerprints before/after using previous
recipe and compared original FULL metadata. Scope only D01–D03 and directly
changed PKI, argument resolution, invocation projection, guards and tests.

## D01 RESOLVED

Runtime plans select effective profileRef/host from existing materialization plans,
independently of Agent and password binding. application_identity_files delivers
canonical certificate.pem/private-key.pem with existing CA/stores. Vault payload
is Agent-only; Apply/preflight run for Agent OR PKI plans. GA/audit standard
mounts and nginx/front canonical names corrected. Existing Agent directory bind
requirement preserved; other non-Agent packages receive no new required mount.
Canonical names match pki_deploy/tasks/plan.yml; no new certificate generation.
Reviewed native delivery/Compose tests and reported RED OS results. Actual full
SZI TLS/start remains an acceptance gate, not the original unresolved defect.

## D02 RESOLVED

_argument accepts explicit provider_library for provided_connection; connection
uses consumer library. Callback retains consumer identity/settings and provider
source/target. Sensitive credentials remain forbidden in argv. Cross-library test
covers consumer infrastructure/application bindings, provider export and targetHostId.
No new resolver/DTO.

## D03 RESOLVED

Provider targets form the sorted unique execution set. once selects one and
each_target emits one invocation per host. Actual host participates in targetHostId
and batch-hook dedup identity. Untargeted execution keeps its earlier branch.
Eight host/scope/frequency cases cover both consumer/provider host counts,
once/each_target, library/instance scope and actual execution argv.

## Overengineering and evidence

Blocking overengineering findings:0. Existing delivery module, argument function
and invocation list/dedup extended; no new store, generator, SZI role, fictitious
Agent, scheduler or persistence. Verify/delete/provider CRUD/UI not expanded.
Owner-approved scope recorded in amended plan714–728.

Reviewer inspected identities, scoped diff, canonical filenames, adjacent guards,
context-free runner and tests; personally ran no tests/target operations and read
no secrets. Parent reported RED OS95tests OK/skipped1,21.092s, including native
PKI private delivery/repeat and Compose validation of all five applications.
Native coordinator/Vault delivery, token retention, full Apply/TLS/repeat and
actual React/Wails acceptance remain open. Historical Stage1/AGP gates retained.

CURRENT for recorded fingerprint/scope. Historical FULL BLOCK remains unchanged.
Single allowed TARGETED_RECHECK consumed. Continue authorized QA/installation;
no further automatic review assigned and no milestone completion implied.
