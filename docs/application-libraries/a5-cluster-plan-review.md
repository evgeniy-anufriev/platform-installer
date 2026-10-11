# A5 — review of ClickHouse ON CLUSTER revision

Date: 2026-10-11. Mode: independent FULL PLAN of the owner-approved material
ClickHouse HA revision, not a rerun of the initial nonblocking plan findings
and not an implementation DIFF review.

Reviewer: `architecture-reviewer`, task `/root/a5_cluster_revision_review`.
HEAD: `054668d36fdaab14d9012dba8f45337bbd5cbd04`.
Reviewed plan SHA256:
`a26a58980369534e12a1a3a947cadb12ca5048ea91d5b707445994d44c007f35`.

## Verdict

**BLOCK** at the reviewed snapshot. Owner disposition 2026-10-11: **A5-C01
CLOSED BY OWNER RISK ACCEPTANCE**. The owner explicitly excludes special handling
of late queued DDL overlapping a repeat as disproportionate to the accepted risk.
No pending-operation marker, native-task correlation or ambiguous-result retry
gate is required. Normal ownership/result checks and failure before Vault
publication remain. This is not a reviewer APPROVE or TARGETED_RECHECK result.
The owner decision removes the implementation stop for C01; C02 remains
nonblocking. Earlier A5 PLAN APPROVE_WITH_CHANGES remains
valid as historical evidence of the previous fan-out design. The present review
only addresses the changed cluster account/grant execution boundary.

## A5-C01 — original BLOCKING; CLOSED BY OWNER RISK ACCEPTANCE

The critical section is undefined for deferred distributed DDL. The plan requires
per-member check→mutation→witness locks, but submits one asynchronous cluster
batch from an initiator. It does not specify lock custody until all workers have
finished, timeout/cancellation/crash handling, pending-operation recognition on
retry, or when per-member UUID ownership witnesses may be published.

Ownership checks can become stale before queued GRANT execution. A local file
lock does not stop ClickHouse's DDL worker; a batch can continue after the client
exits and overlap a later hook. Final login alone does not establish that rights
were never granted to a foreign same-name object.

Reviewer-proposed smallest correction, pending owner decision:

1. One stable initiator and shared lock for managed application writers of the
   deployment, with topology checked before submission.
2. A private nonsecret pending-operation witness written before submission, and
   explicitly defined correlation with the native distributed DDL task.
3. Timeout/cancellation leaves the operation unresolved: no Vault publication,
   no automatic resubmission. Retry first resolves the prior operation.
4. Confirm all server members, ownership/UUID and grants before publishing
   completed ownership witnesses. An unproven crash gap remains fail-closed.
5. Limit guarantees to cooperating managed writers; external administrator
   replacement is outside file-lock guarantees. No OR REPLACE or foreign-user
   adoption.

If reliable native task correlation is not available, the simpler acceptable
alternative is an automatic retry BLOCK after an ambiguous result until explicit
operator recovery. A scheduler or distributed transaction framework is not
required. Implementer recommends this bounded fail-closed alternative initially.

Required QA: concurrent initiators, submission timeout, delayed server return,
crash before witness publication, retry with pending DDL, foreign user on one
member. None may publish credentials or submit an unapproved duplicate batch.

## A5-C02 — NON_BLOCKING / OPEN

Native Keeper DDL queue stores SQL text and can contain a password verifier.
Secret-hygiene acceptance must cover queue/Keeper access and diagnostics: only
a supported verifier, no plaintext password; no verifier output in diagnostics;
access protections and native retention checked on the pinned version.

## Overengineering and evidence

No unnecessary abstractions, duplicate DTOs, speculative features or premature
scope found. ON CLUSTER is a native owner-selected mechanism. Minimal lock and
pending witness or explicit fail-closed recovery suffice for C01.

Reviewer read instructions, current state, review procedure, A5 plan and earlier
review, relevant architecture/Core contracts and the ClickHouse server template.
Existing TLS native transport, private access storage, cluster default and Keeper
configuration provide the basis, not tested distributed-DDL acceptance. No tests,
target contacts, secret reads or edits were performed by the reviewer.

Source for deferred distributed DDL behavior:
[ClickHouse distributed DDL](https://clickhouse.com/docs/reference/statements/distributed-ddl).
