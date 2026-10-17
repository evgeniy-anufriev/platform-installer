# Kafka library topics — implementation evidence

Owner approved implementation on 2026-10-17, with Ansible tasks preferred and
application installation explicitly excluded. The per-binding Kafka deployment
controls RF/minISR. No new production Python file, lock or desired-state store.

## Source and implementation

Base revision: `9788b405d185c153612c8bb692ac0b67365c9797`, master.
Canonical application-library schemas extend resource kind/settings; existing
Core projections calculate topics and validate instance aliases/provider refs.
Kafka package alpha.3 declares `service.kafka.topic`. Go accepts the existing
setting key and transports Core topic projections. React reuses resource CRUD,
Startup and guarded Review/Save/Reset. Existing provider stages invoke Kafka
builtin tasks for preflight/create/read-only verification, before accounts and
containers. Raw CLI/config values are suppressed; safe diagnostics remain visible.

## Automated checks

- Windows: `go test ./...`, `go vet ./...` PASS.
- Frontend: all 23 files / 255 tests PASS; build/typecheck/lint PASS. Existing
  production bundle chunk-size warning remains informational.
- RED OS .102, established platform-automation identity, current source workspace
  `/var/tmp/platform-installer-qa-cec0f8fb7ee34f8f9f4aa2ce6dc5573c`:
  application libraries 20 PASS/1.104s, providers 18 PASS/0.026s.
  Includes standalone and distributed 1/2/3/4 brokers, controller exclusion,
  colocated members, explicit RF/minISR, invalid counts, duplicate physical-name
  claims, cross-provider bindings and existing package compatibility.
- Native production Ansible tasks + target-free snapshot: 2 PASS/138.409s.
  The CLI fixture checks preflight/no creation, explicit creation, matching repeat
  changed=0, read-only Verify, partition drift/no alteration, literal dotted name,
  file mode 0600 and secret-canary exclusion from errors. Separate native snapshot
  exercises application default binding, explicit empty selection and Reset.
  These CLI fixtures do not establish acceptance against an actual Kafka broker.

Local logs: `.runtime/kafka-topics-{go-all,go-vet,ui-all,ui-build,ui-lint,core,providers,native}.log`.

## Real bridge and runtime

Verified QA runtime09 digest:
`sha256:8a5743d82577e724878771ed3425f5aff9b832512576fbe3bdecaf42b73219b9`.
Catalog: `sha256:417be4b10a4dfc81352af03149cd562201a63f46a9a582e9c5adfc17051f3223`.
Built on trusted .102 from current sources and existing verified runtime packages,
Kafka archive and application probe image; no downloads. Published through the
standard publisher into active cache, preserving prior runtime08 locally. Standard
QA promotion prepared .102 and rebound the isolated fixture. A first QA-only input
had a duplicate runtime directory and failed bundle validation; it was not
published. A JSON-shaped QA manifest failed canonical lock update; converting that
fixture to standard YAML let the existing promotion resume successfully.

Initial real UI automation failed on tab/pagination selectors; no initial complete
PASS was claimed. Independent [FULL DIFF review](../reviews/kafka-topics-diff-review.md)
was BLOCK for D01 implicit listener selection and D02 actual Kafka/TLS acceptance.
D03 missing-topic diagnostics was nonblocking. Automatic work stopped. The owner
then explicitly authorized correcting listener/diagnostics, bounded actual Kafka
QA and completion of Core/UI checks, while prohibiting application installation.

## Owner-authorized corrections and final QA

D01: an absent selector infers only a unique client listener; multiple client
listeners require the existing connectionRef. Explicit SSL and sole-client
PLAINTEXT remain supported. Existing target-free test covers all three choices
without application Kafka connections. Providers18 PASS/0.045s.

D03: builtin `ignore_errors` lets exhausted private describe retries reach the
safe assert. Added missing existing/preflight and Verify checks require visible
TOPIC_MISSING. Native production tasks1 PASS/43.615s, including secret canary.
Current Core/services/contracts/config tree was verified against the QA copy.

Actual Kafka4.3.1, Ansible2.18.15, existing 3-broker cluster .101/.102/.103:
production topic role tasks executed on .102 through explicit TLS listener9094,
existing private keystore/truststore and runtime-only password file. Topics:
`platform.qa.library-topics.20261017-1810` and fresh creation proof
`platform.qa.library-topics.20261017-fresh10`. Config: partitions2, RF3, minISR2,
cleanup.policy=delete, retention.ms=600000. Fresh create changed=1; matching
Apply/repeat, existing mode and Verify changed=0. Partition and config drift
failed without alteration; final Verify still passed. Missing topic reported
TOPIC_MISSING. TLS against the plaintext port failed with safe
APPLICATION_TOPIC_DESCRIBE_FAILED / TimeoutException / timeoutMs3000; raw CLI
and credentials remained suppressed. Private QA credential cleanup passed.
Existing Kafka listener configuration was not modified. Client keystore/truststore
were exercised; no separate change to require client certificate authentication
was made. A deliberately short initial QA timeout and a QA-only templated string
count caused preliminary failures; production defaults and concrete typed Core
projection were used for the final cases. No new production script was added.
Logs: `.runtime/qa/kafka-topics-live-evidence/topics-live-*.log`.

Verified/published/prepared runtime10:
`sha256:216ae63dadbbb21671ef8bdf4182da2a44c0d44c4612ec517edaa264cfcfe706`;
catalog digest unchanged. Built on trusted .102 from current sources and existing
verified runtime09 artifacts, without acquisition. Local runtime09 remains retained.

Real React/Wails/Core acceptance PASS, eight cases: topic resource create/Save/
reopen; binding Save/reopen; Reset to application defaults; fresh executable plan;
Core Verify and displayed independent standalone1/1 and cluster3/2 defaults;
numeric partition edit/Save/Verify/display; changed revision/fingerprint; resource
remove/Save/reopen. No Approve/Start or application installation occurred.
An actual numeric edit exposed JSON float64 being written as YAML !!float3;
the existing generic scalar writer now writes exactly representable integral JSON
numbers as YAML integers and retains fractional values. Go save/reopen test covers
counts and fractional config. An existing UI refresh omission was corrected by
reading the existing CurrentProject binding after successful Verify, exposing the
Core snapshot rather than recalculating in React. A focused frontend regression
and the actual UI checks cover this path.

- First plan `plan-93b15296e32c605127375136`, EXECUTABLE / PLAN_REVIEW;
  revision `sha256:13ae56040e78a4feed1ce205d106e961a53fdb713f3eb10e3b77479d26238b49`;
  fingerprint `sha256:93b15296e32c6051273751360a80baf9936167853c7ffee8537d116fa43dbdca`.
- Edited plan `plan-87b9a74de724debe26e5ed20`, EXECUTABLE / PLAN_REVIEW;
  revision `sha256:9990ec4e6179a17f93bc40e05512708d7637b0bc054b40b10024b0313cab89fe`;
  fingerprint `sha256:87b9a74de724debe26e5ed205aeceb22f043143c949e452c7cb7b9dfc57ceaac`.
  Project Verify VERIFIED for this exact revision. Both plans remained unapproved.

Evidence: `.runtime/qa/application-design/kafka-topics-wails.json`;
final Go test/vet PASS; frontend256/23 files, build and lint PASS.
No visual/manual acceptance or final full Core-suite PASS is claimed.
Independent [TARGETED_RECHECK](../reviews/kafka-topics-targeted-recheck.md) APPROVE,
64/64 fingerprints matched, zero blockers. D01/D02/D03 RESOLVED. No additional
review or application installation is inferred.

Owned QA source workspaces 026dca04, e0d47e15 and cec0f8fb were removed with
`scripts/qa-sync.ps1 -Cleanup`. Owned remote bundle/input staging was removed;
the prepared verified runtime and local evidence remain for continuation.
Final correction workspace 8c1c176b was verified against current sources and removed
with the same cleanup helper. Both owned Kafka QA topics were deleted; an anchored
describe returned no topics. Private credential cleanup reported QA_SECRET_CLEAN.
Remote runtime10 build staging was removed; prepared runtime10 and local evidence
remain. Final `git diff --check` PASS. Source and QA closure are recorded above.
