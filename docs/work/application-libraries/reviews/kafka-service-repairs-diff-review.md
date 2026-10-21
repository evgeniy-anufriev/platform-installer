# Kafka service repairs: independent FULL DIFF

Date: 2026-10-21. Reviewer: independent read-only architecture-reviewer
`/root/kafka_service_repairs_review`. One FULL review; no TARGETED_RECHECK.

**Verdict: APPROVE. Open BLOCKING: 0. Validity: CURRENT.**

Owner scope: repair KAFKA-M01–M06 and admin inventory with simple Ansible tasks,
isolated QA and documentation. No stand installation or service restart.
Existing sole-admin, anonymous data access, runtime SecretRef and PKI contracts
remain authoritative. Concurrent inline-secret/UI work excluded.

## Exact source identity

Base: `61c52f194d45c11d6ddd8991424026372f4190f3`.

Fingerprint: `sha256:c98af61a7cfe20553d3f18804d2d939aeb03c3350f9ecea2394000b4a689cb76`.

SHA256 of compact JSON of sorted `[repository-relative path, file SHA256]`
pairs. All 15 file hashes and aggregate fingerprint directly verified by the
reviewer. Scope:

- `ansible-core/tests/qa_kafka_service_repairs.py`
- `ansible-core/tests/qa_kafka_application_acl.py`
- `ansible-core/tests/test_kafka_tls_plan_selection.py`
- `services/kafka/playbooks/apply.yml`
- Under `services/kafka/ansible_collections/platform/kafka/roles/kafka_kraft/tasks/`:
  `authorization_inputs.yml`, `authorization_security_guard.yml`,
  `authorization_setup.yml`, `authorization_transition.yml`,
  `authorization_finalize_member.yml`, `main.yml`, `resolve_cli_connection.yml`,
  `run_cli_command.yml`, `verify.yml`, `verify_member.yml`, `verify_quorum.yml`.

The existing `application_acl.yml` predicate is unchanged from the base;
M04 coverage is added in the scoped ACL test.

## Findings from the same review pass

| ID | Severity | Final status | Evidence and correction |
| --- | --- | --- | --- |
| KSR-D01 | BLOCKING | RESOLVED | Initial admin template task alone had the generic secret-file alias; nested finalized-admin account template also needs it. Alias moved to the entire authorization block. Bootstrap/finalized admin and no-reset cases inspected and PASS. |
| KSR-D02 | BLOCKING | RESOLVED | SASL diagnostic headers were initially compared with legacy client_endpoint. Exact selected listener name/protocol/address now used per broker. SASL-port acceptance and legacy-port rejection cases inspected and PASS. |

No other open findings. Administrative setup failure stops all hosts before
revocation. Member finalization is sequential; quorum failure stops subsequent
revocations. Limited bootstrap plays are rejected before delegated revocation
outside their host set. This guard does not constrain preexisting admin setup
delegation to the selected broker.

M02 normalizes boolean decisions; M03 selects CLUSTER blocks; M05 preserves
listener keys; M06 uses admin/SASL_SSL with SCRAM and retains the controller route
without it. M04 retains the prior corrected predicate with new integration
coverage for IdempotentWrite/ClusterAction in mixed-resource ACL inventory.

## Overengineering assessment

Unnecessary abstractions: 0; duplicate contracts/DTOs: 0; new persistence: 0;
premature scope: 0; speculative features: 0; missed simpler mechanisms: 0.
Task includes separate existing transition, one-member finalization and quorum
verification operations. Built-in assert/set_fact/include_tasks/lineinfile/
systemd/wait_for tasks are used. No new production Python orchestration.

## Evidence inspected and limits

- Native11 PASS /218.160s before the final limited-play guard.
- Final affected transition5 PASS /36.068s, including limited-play refusal.
- ACL5 PASS /24.572s; Kafka/Core35 PASS /40.666s.
- Standard Kafka Apply/Verify syntax PASS.
- Final source-copy verification reported PASS by the implementing agent.

Reviewer read the source, instructions/contracts and safe terminal QA logs;
did not run tests, edit files, inspect secrets or contact targets. A complete
12-case native rerun on the final guard revision is not claimed: the five
directly affected cases were repeated. Full real Kafka Apply/Verify/repeat,
cold-start, interrupted-bootstrap recovery and React/Wails acceptance remain
unproven and require separate authorization. This review does not authorize
installation. Documentation-only evidence synchronization does not invalidate
the reviewed source fingerprint.

Detailed implementation/QA evidence: [journal](../evidence/kafka-pem-journal.md#kafka-m01m06-source-repairs-and-admin-inventory--2026-10-21).

Post-review commit preparation: only the redundant blank EOF line in
verify_quorum.yml was removed. No task/behavior/security change or additional
review claimed; the fingerprint above identifies the actually reviewed and
stand-tested snapshot before this whitespace-only normalization.
