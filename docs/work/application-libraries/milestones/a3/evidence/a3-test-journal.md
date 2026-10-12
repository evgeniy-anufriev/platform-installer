# A3 functional QA journal — 2026-10-10

Branch `codex/application-libraries`, base `f3ba74c`. Uncommitted standalone
PostgreSQL providers. Execution Node RED OS 192.168.56.101, established
platform-automation identity, sudo -n. All writable SQL used temporary isolated
clusters. Deployed full-services was not mutated. No benchmark performed.

## Scope and owner decisions

One resource batch per library, one account batch per logical instance;
read-only discovery once per PostgreSQL deployment, database members only.
Explicit additive grants, no global ACL traversal or automatic revocation.
preflight_objects.sql.j2 merged into preflight.sql.j2; unused cspa package removed.
Owner accepted FULL DIFF corrections D01–D04 and one targeted recheck D01–D02.

## Evidence before review corrections

Core provider projection 10 PASS and application libraries 17 PASS.
Four native role cases PASS after additive-grant simplification/template merge:
two-account Apply/Verify/repeat changed=0, role IDs/password hashes unchanged;
wrong-password/foreign-owner rejection; existing read-only/additional rights;
table/sequence grants, removed declarations preserve privileges, missing USAGE
fails Verify and is restored by Apply. This suite predates D01 authentication
corrections; it is not represented as a final whole-suite rerun.
An earlier attempt retained an outdated PUBLIC-block expectation; test corrected.

## FULL DIFF corrections evidence

Verified source transfer using scripts/qa-sync.ps1:

- `72129bb0e3214df39d6099e71188c0c0`: D01 native existing user without CONNECT
  to postgres PASS; wrong application password with maintenance trust PASS
  (Verify rejects it). Native primary/physical-standby selection PASS, including
  zero writable, two writable after promotion and unavailable candidate.
- `d70b0810c75d444abea51b0fdecb150c`: two-account repeat/Verify PASS;
  primary/standby and three negative discovery cases PASS again;
  stalled PostgreSQL SSLRequest/TLS peer terminates with timeout exit124 PASS.
  This is native PostgreSQL replication QA, not full pg_auto_failover installation.
- Full entrypoint fixture first failed while controller copied a CA from
  postgres-private data. Fixed test-only copy using remote_src and become.
- Next full entrypoint reached actual resolve and PKI-projected prerequisite,
  then exposed root-only PKI parent directories. Read-only TLS/login probes
  now use existing platform_pki_owner/execution technical user convention;
  administrative socket SQL still uses postgres. Infrastructure directory
  permissions were not changed.
- `58af58102fac4ab39a8c92c80a1e36a2`: final PKI-owner native cases **3 PASS**: two-account Apply/Verify/repeat changed=0, D01 restricted CONNECT/different HBA negatives, and full production resolve/apply/verify entrypoints.

Full-entrypoint test imports the production resolve, apply and verify playbooks;
it supplies ordinary inventory/defaults/group_vars and protected credential refs,
not prepared jobs. Only this temporary project's public CA is materialized at
actual Core-projected directories, then cleaned. Logs private; password canary
checked against command output. Cluster/data/PKI fixture teardown is explicit.

Unbounded broad regression against d70 deliberately cancelled during unchanged native PKI recovery (KeyboardInterrupt recorded; no PASS claimed). Bounded Core regression against 58af excludes 16 unchanged test_pki_single_pass_resolution cases; **PASS: 528 executed, 509 passed, 19 skipped**. Python projection unchanged
by subsequent probe-user-only Ansible correction. Bounded result PASS; 16 excluded unchanged native PKI recovery cases are not counted as passes or skips in this run.

## Review and cleanup

Initial FULL DIFF BLOCK recorded in a3-diff-review.md. Owner-approved single TARGETED_RECHECK **APPROVE**, A3-D01/D02 RESOLVED; zero blockers in scope. No Go/UI/bundle acceptance
claimed. All 14 A3 source copies cleaned with the standard helper after their tests stopped. Known A3 temporary safe/protected logs removed after recording evidence. PostgreSQL and per-project public CA fixtures were removed by their teardown. No release/master commit.

Final HA source 4ae0377a964643418ee19ee364881b87: **1 native case PASS**, primary/standby resource and account creation/Verify; zero/two writable and unavailable candidate use full phase sequence and prove zero newly created DB/account. Source transfer verified; final production files match 58af (only QA fixture strengthened).

Catalog generator --check PASS, digest sha256:45fc3603889c0cbe2a435c1dc94be7ca975943727a736d6d6c648da3c79d4a43. git diff --check PASS. No benchmark, ALT-specific check, Go/UI acceptance, bundle publication or commit performed.
