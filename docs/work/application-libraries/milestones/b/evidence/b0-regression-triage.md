# B0 — regression attribution

Comparison base: `cee36a3f737f70eb10347f0e3c50bfed398bf188` (before B0).
Current source: corrected19-file identity
`5268325927c15fbbe21af4221283dbe98aa35d915a3e83233cd91651566defb1`.
Both source trees transferred and verified with `scripts/qa-sync.ps1` on RED OS.
No service installation, shared-infrastructure reset or Go/UI work.

## Reproduced pre-existing failures

| ID | Check | Cause and attribution |
| --- | --- | --- |
| REG-01 | Kafka CLI readiness retry | Fixture includes run_cli_command.yml directly without role defaults and omits platform_kafka_name, now used for the temporary-file prefix. Same undefined-variable failure before B0. |
| REG-02 | Managed Kafka fixture projection (3 subtests) | Assertions expect legacy /var/lib/kafka-main paths; actual projection uses deployment runtime namespace under /var/lib/kafka/<namespace>. Same three differences before B0. |
| REG-03 | Project resource settings (6 PostgreSQL subtests) | Assertions expect the deployment data root, while effective PostgreSQL data directory includes /postgres. Same six differences before B0. |
| REG-04 | PKI single-pass IntegrityTests and skip/reuse native fixtures | Unoptimized pki_deploy includes system CA reconciliation; the fixture does not isolate the system update-ca-certificates command. Unprivileged execution is denied by /etc/pki permissions. Do not rerun this fixture as root on a shared host to obtain a PASS. Same permission failure reproduced in the paired baseline suite and targeted skip/reuse case (8.855s); test and role inputs are byte-identical before B0. |
| REG-05 | Configuration-schema reproducibility | services/postgresql/configuration.schema.json differs from generated output only in JSON key ordering, with semantic equality, on both trees; B0 changes neither generator nor input/output service blobs. |
| REG-06 | Legacy validate fixtures | Core examples/valid and root kafka-single/postgresql-standalone fail on old definition versions or duplicated/missing inventory membership on both trees. Root application-libraries is a role-level fixture without the portable validation catalog variable; invoking validate.yml without that explicit prerequisite fails identically. |
| REG-07 | Vault directory-access static assertion | Fixture expects three deployment-level directory entries; current role has two. Reproduced before B0. |
| REG-08 | Vault template-loop native fixture | Selected tasks/templates run outside the role defaults, omitting platform_vault_name. Reproduced before B0; additional diagnostic captures the undefined-variable class without production secrets. |
| REG-09 | Five-consumer PKI change propagation, Redis subtest | Fixture omits _platform_sentinel_peer_user/_platform_sentinel_peer_password observations used by the current restart condition. Current full suite fails on undefined peer_user; paired baseline reproduction fails identically (1 test,52.213s). |

Original interrupted progress characters were insufficient to identify failing
methods: subtest failures each print F and shift naive character-to-case indexing.
Full-discovery targeted reproduction confirms REG-01/02/03 on both trees. The earlier
suspected project snapshot/save failures are not reproduced; their focused cases pass.
An initial isolated diagnostic invocation omitted module_utils import setup and
produced two loader errors; corrected full-discovery invocation loads those modules
successfully. These diagnostic command errors are not product regressions.


## Positive and improved evidence

- B0's 34 cases PASS in ordinary unprivileged full discovery, including both native
  localhost/controller fixtures. Previously accepted affected165 and offline34 remain
  separate evidence.
- Catalog reproducibility PASS on both trees, digest
  `08cd1f4c1b77104b32d11841c8eab105b14099a636a3577fdfb26b7e7009ccaa`.
- Real controller-side validate.yml on root bind-standalone PASS on both trees.
- Base target-trust test fails because its synthetic Journal lacks root; the B0 test
  fixture corrects this shape and passes. This is a base-only test error.

## Completed regression and B0 disposition

Full current suite: **685 cases,658 PASS,19 SKIP,8 failing methods**. The eight
methods produce15 unittest failure records (including subtests),0 errors.
All cases reached terminal; no PKI cases were excluded from this current run.
The16 native PKI resolution cases produced14 PASS and the two reproduced baseline
fixture failures (REG-04 skip/reuse and REG-09 Redis).

Baseline comparison:635 cases completed,609 PASS,19 SKIP,13 failure records and
1 baseline-only Journal-shape error. Its16 unchanged native PKI resolution cases
were excluded from the bounded comparison after an initial duplicate native run
was stopped by exact verified PID/cwd. Both failing native cases from the full
current suite were then separately reproduced against the base. No full baseline
suite PASS is claimed. The previously interrupted regression remains historical.

**New B0 failures:0.** All34 B0 cases pass inside full discovery. Previously
accepted affected165 (161 PASS/4 SKIP),offline34 and independent TARGETED_RECHECK
APPROVE remain valid; reviewed19-file hashes are unchanged. No production code or
repository test needed modification during attribution.

Nineteen skips remain explicit:4 gated canonical-journal observability acceptance
cases and15 root-only Vault synthetic filesystem/permission proofs. These are not
PASS; unaffected accepted service failure/recovery acceptance was not repeated.
Standalone controller validate.yml on a current BIND fixture and catalog
reproducibility PASS. Broad regression remains FAILED on documented pre-existing
fixtures/schema byte ordering, not a clean repository-wide PASS.

B0-specific standalone Core QA is complete with known baseline defects isolated.
This does not authorize B1–B4 or claim Go/UI acceptance. The public
[summary](b0-regression-summary.json) contains counts and failed-method identities.
Detailed safe logs remain under `.runtime/qa/b0/regression-triage/{current,base}`;
15 copied evidence files passed remote/local SHA256 equality.

Cleanup PASS:2 remote source workspaces removed through qa-sync after exact public
root ownership restoration,1 clean temporary local baseline worktree removed,
0 active owned QA processes. No service data/reset, canonical bootstrap, credentials,
master, commit or push changed.



## Subsequent owner-authorized repair

The owner then requested correction of these tests/fixtures and PKI isolation.
REG-01–REG-09 are resolved for the corrected test/fixture source in
[repair evidence](b0-regression-repair.md). Full current regression now PASS:
685 cases,666 PASS/19 unchanged SKIP,0 failures/errors. The FAILED counts above
remain results of the earlier source, not retroactive PASS. Working role/Core
logic was not changed for the tests; generated schema JSON semantics are identical.
