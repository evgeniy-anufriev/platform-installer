# Kafka library topics — TARGETED_RECHECK

2026-10-17. Independent architecture reviewer `/root/kafka_topics_plan_review`.
Verdict: **APPROVE**, zero unresolved blocking findings. Read-only reviewer returned
the report; parent recorded it here. No additional review is required for this gate.

## Identity and scope

Base `9788b405d185c153612c8bb692ac0b67365c9797`.
Manifest `.runtime/kafka-topics-recheck-fingerprints.json`, SHA-256
`1801073cf83979a48fdfe5779016284061e4b38f4e1ea28f117dceba03619259`.
64/64 fingerprints matched. Scope was KTP-D01/D02, explicitly authorized D03,
and immediately affected numeric serialization/UI snapshot refresh. Other FULL
DIFF questions were not reopened. Owner authorized corrections, bounded real Kafka
QA and Core/UI completion; application installation remained prohibited.

## Findings

- **KTP-D01 — RESOLVED.** Only a unique client listener is inferred. Ambiguity
  without connectionRef fails through the existing resolver; explicit SSL remains
  valid. Resource-only tests cover sole/ambiguous/explicit choices. No new lock,
  selection layer or security fallback.
- **KTP-D02 — RESOLVED.** Saved production-task evidence from actual Kafka4.3.1
  confirms fresh create changed=1; repeat/existing/Verify changed=0; partition and
  config drift safe failures with changed=0; final Verify PASS; safe missing-topic
  and TLS-on-plaintext error diagnostics. Existing TLS listener and runtime client
  stores were exercised. The server was not changed to require client certificate
  authentication; no separate mandatory-mTLS result is claimed. Real React/Wails/
  Core evidence has eight completed cases, VERIFIED, different saved revisions/
  fingerprints and two EXECUTABLE / PLAN_REVIEW plans on runtime10. Plans remained
  unapproved and unstarted; no application installation was claimed.
- **KTP-D03 — RESOLVED.** Builtin ignore_errors carries exhausted private retries
  into the safe assert. Actual missing-topic evidence shows TOPIC_MISSING and
  failed=1; absence does not become success.

## Immediate boundary and overengineering

The existing scalar writer preserves exact integral JSON counts as YAML integers,
retaining fractions; save/reopen coverage was inspected. This is serialization,
not Kafka policy in Go. React reads existing CurrentProject after successful Core
Verify, including browser transport; RF/minISR remain Core calculations. No new
public backend method, alternate Save/Start path or blocking regression was found.

Unnecessary abstractions, duplicate DTO/contracts, premature scope, speculative
functions, persistence/lifecycle/lock mechanisms and missed simpler standard
mechanisms: **0**. Corrections reuse resolver, scalar writer, CurrentProject and
builtin Ansible error handling. Target-free selection and serialization properly
remain in existing Python/Go layers, without a new script.

## Evidence and limits

Reviewer directly inspected hashes, source, tests and retained Kafka/Wails logs;
no tests/server commands were rerun by reviewer. Implementer Go test/vet,
frontend256/build/lint and RED OS providers18/native1 results agree with journal.
QA_SECRET_CLEAN confirms private-material cleanup; topic deletion/configuration
preservation were reported by implementer. Secrets were not read. Final full Core
suite and visual acceptance are not claimed.

Validity: CURRENT for the fingerprint/evidence. Changes to execution/security,
listener selection, writer or UI refresh need assessment of the affected part;
recording final status/review documents does not itself invalidate source approval.
No authorization to install applications is conferred.
