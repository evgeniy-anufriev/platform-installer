# Kafka library topics — FULL DIFF review

2026-10-17. Independent architecture reviewer `/root/kafka_topics_plan_review`.
Verdict: **BLOCK**, 2 unresolved blocking findings. Reviewer returned the report
read-only; parent recorded it here. No automatic correction/review after BLOCK.

## Identity and scope

Base `9788b405d185c153612c8bb692ac0b67365c9797`.
Frozen manifest `.runtime/kafka-topics-source-fingerprints.json`, SHA-256
`6bd4547653c95daacde3f51d6cf35c1c1e7acab7bda67c11369fc687f73f1ac9`.
58/58 file hashes matched. Whole implementation diff inspected, generated frontend
dist excluded. Includes Core projections/provider stages, schemas, Kafka tasks and
template, Go writer/DTOs, UI, tests, metadata and docs. Documentation may subsequently
record this verdict; production implementation was not corrected after the review.

Owner approved deployment-dependent RF/minISR, standard Ansible tasks first,
minimal code and no application installation. Review followed the review procedure
and ansible-core-review skill. Reviewer performed read-only source/diff/hash checks;
test results below were supplied by the implementer, not rerun by reviewer.

## Findings

### KTP-D01 — BLOCKING, OPEN: implicit listener/security selection

`application_providers.py:146–147` sorts client listeners and selects the first
when `connection_defaults.kafka.connectionRef` is absent. A library topic need
not have an application Kafka connection. With PLAINTEXT and SSL client listeners,
this new mutating path may choose PLAINTEXT without operator selection, contrary
to the plan's resolved-security-context requirement.

Smallest correction: use the existing explicit connectionRef, or infer only a
strictly unique client listener. Do not choose alphabetically. No new lock or
selector contract is needed. Target-free tests should cover a unique listener,
explicit SSL with PLAINTEXT present, and ambiguous SSL+PLAINTEXT without a selector,
including a topic-only resource without application Kafka connections.

### KTP-D02 — BLOCKING, OPEN: actual Kafka production boundary unverified

Native shell fixtures exercise production tasks but do not prove actual Kafka
CLI/output formats, TLS/mTLS client configuration, creation or effective config
reads against a supported broker. This is an acceptance gap, not a demonstrated
Kafka task defect. The evidence journal correctly distinguishes it.

After separate owner authorization, perform bounded actual Kafka QA using current
production entry points: create, unchanged repeat, read-only Verify, drift without
alteration, custom properties, literal dotted name, TLS and safe errors. Installing
applications is unnecessary and remains excluded. Reviewer authorizes no target
operation. Real Wails/Core acceptance had no positive terminal result when the
review closed and must not be assumed PASS.

### KTP-D03 — NON_BLOCKING, OPEN: missing-topic diagnostic hidden by retries

In `application_topic_describe.yml`, exhausting `until` on the private command
fails that task before the safe TOPIC_MISSING assert. `failed_when: false` does
not suppress exhaustion failure. The operation remains fail-closed, but loses the
intended safe diagnostic. Use standard Ansible handling to pass the registered
result to the safe assert after bounded waiting. Test missing existing/Verify
topics for safe code/topic/provider and no raw stdout/stderr. This nonblocking
correction does not itself require another architecture review.

## Overengineering

No unnecessary abstraction, duplicate contract/store, premature alter/delete/ACL
scope, scheduler, lifecycle mechanism or new lock was found. Existing projections,
`command.argv`, builtin filters and `always` cleanup suit the requirement.
KTP-P01 is RESOLVED: existing physical-name claim handling and parameter comparison
reject conflicts before resource jobs. D01 has a smaller solution using the
existing selector/uniqueness rule.

## Evidence and next gate

Reported evidence: Go test/vet PASS; frontend255/build/lint PASS; RED OS libraries20,
providers18 and native2 PASS. No actual Kafka broker mutation/TLS acceptance or
complete real Wails/Core acceptance is claimed. Reviewer read no secrets and
performed no server operation.

Validity: CURRENT for the frozen source identity. Present D01/D02 to owner for
decision. Only after owner-approved corrections/QA may the single permitted
TARGETED_RECHECK cover these blocker IDs and their immediate boundary. No second
automatic FULL review or repeated convergence cycle.
