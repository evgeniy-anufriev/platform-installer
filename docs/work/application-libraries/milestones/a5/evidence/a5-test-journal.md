# A5 implementation and QA journal

Date: 2026-10-11. Branch: `codex/application-libraries`.
Base HEAD: `054668d36fdaab14d9012dba8f45337bbd5cbd04`; uncommitted worktree.
Owner authorized A5 implementation, then specified ON CLUSTER default for HA
ClickHouse users/grants. No commit, master synchronization or Go/UI authorization.

## Current scope

A5 is **IN PROGRESS**, not complete. The owner accepted the A5-C01 risk and
explicitly excluded special late-DDL/retry handling on 2026-10-11; implementation
may resume. No pending marker/native-task correlation/retry gate is required.
[Cluster plan review](../reviews/a5-cluster-plan-review.md) is an independent FULL PLAN
review of the material owner revision. No milestone FULL DIFF review has run.
No existing full-services infrastructure was changed.

Implemented draft:

- Pure service-owned Redis/ClickHouse member allocation functions, shared by
  infrastructure role filters and target-free application connection resolution.
  Stable global Redis slots and host-local ClickHouse ordinals preserved; Sentinel
  and keeper-only member filtering explicit.
- Redis/Sentinel typed ACL grants and ClickHouse scoped SELECT/INSERT grants;
  provider discriminator and library/instance job projection. Existing provider
  capability gates remain: new capabilities are **not advertised** until executable
  roles and integration are complete.
- Optional absent connections prune effective accounts and corresponding Agent
  bindings. Desired defaults remain intact; plaintext guards remain even on
  skipped declarations; undeclared account aliases remain errors.
- Draft Redis service-owned RESP/TLS account helper and Ansible module: member
  lock, protected ownership witness, no takeover/password rotation, additive
  permissions, native ACL SAVE only on mutation. Not connected to provider
  entrypoints yet. Infrastructure ACL writers still need the same lock and
  named-user compatibility before capability activation.

Redis CLI lacks a structured ACL check→mutation→save→witness critical section;
the small stdlib helper keeps that sequence in one bounded process without pip
dependencies or command-line credentials. Native engine tests validate current
behavior; full TLS module/Ansible/infra-writer integration remains unverified.

## RED OS evidence

Transport: established platform-automation identity, IdentitiesOnly=yes, source
transfer/verification and cleanup through scripts/qa-sync.ps1. No Python/Ansible
tests executed on Windows. Temporary local Redis fixture bound only to an owned
Unix socket; it did not use or change deployed service accounts.

First source copy:
`/var/tmp/platform-installer-qa-b59ac84d335543f6a766b00a886b9451`.
Three allocation/projection tests PASS. Copy cleaned.

Second source copy:
`/var/tmp/platform-installer-qa-9e27a875e7e6491b94c9be54d957ed7b`.

- Application Core tests: 61 PASS.
- Redis contract tests: 12 PASS.
- Native Ansible ClickHouse topology_contract.yml: PASS, ok=37, failed=0;
  standalone and three same-host members. Ephemeral credential cleaned in always.
- Copy cleaned.

Third source copy:
`/var/tmp/platform-installer-qa-39bf975b4448488d84c753cefb8566f8`.
63 application tests PASS; one real Redis engine test PASS. Copy cleaned.

Latest tested source copy:
`/var/tmp/platform-installer-qa-ae4ced740d404650b9c3fff2d6683d60`.

- Application tests: 63 PASS.
- Real Redis engine test: PASS on installed Redis 8.6.4. Covers preflight without
  account/witness creation; create, no-change repeat and Verify; allowed key
  write/read/delete and forbidden namespace denial; wrong password/foreign managed
  account rejection; existing user without adoption; saved hash-only ACL with
  default preserved; concurrent same-scope create resulting in one mutation;
  symlink lock rejection. Test-generated passwords never printed/persisted in repo.
- Newly added optional-account projection test was written after this copy; it is
  **not yet run**, because cluster PLAN BLOCK stopped further implementation/QA.
- Copy cleaned successfully through the standard helper after the review stop.

No full native Sentinel HA, ClickHouse user/DDL/grants, Kafka container status,
end-to-end Apply/Verify/repeat, or cross infra/app lock acceptance claimed. No
performance benchmark series run. Changes to source contract tests alone do not
prove the service lifecycle.

## Owner disposition and next work

Owner closes C01 by risk acceptance, not by implementation correction or reviewer
approval. No TARGETED_RECHECK of an unimplemented mitigation is claimed/requested.
ON CLUSTER default remains required for HA user/grant batches. Keep ordinary
ownership, per-server result checks and failure before Vault publication; the
special overlap case is outside scope. C02 queue secret-hygiene remains a
nonblocking acceptance item. Continue Redis integration and ClickHouse hooks.

## Executable provider progress — 2026-10-11

Redis/Sentinel executable roles and infrastructure ACL writers now share the
member lock and preserve named accounts. Native TLS role test passed on RED OS
in source copy `platform-installer-qa-8efbbc5b1c31451e8b1e0734075fdc60`:
preflight, create, unchanged repeat, read-only Verify and infrastructure repeat
preserving application users. Elapsed 35.479 seconds is one functional test,
not a benchmark. That copy was cleaned. Application Core suite: 64 PASS;
optional-account pruning and plaintext rejection are now covered.

Credential custody uses generic `platform_application_secret_root` for Redis,
ClickHouse and Vault. The old PostgreSQL name remains a compatibility input at
the Core entrypoint; conflicting nonempty roots fail closed. Direct manual
PostgreSQL roles retain their documented old-variable fallback.

ClickHouse executable role has one library/instance module task after the
protected credential guard. Native TLS standalone passed in source copy
`platform-installer-qa-9d79da8a210c4463848b220f6d05aa32`: database before user,
SELECT/INSERT grants, authenticated login, unchanged repeat, read-only Verify,
forbidden DDL and foreign-account denial. Two tests PASS in 13.001 seconds;
copy cleaned. Earlier fixture startup failures were caused by test pool limits;
the test now also disables the watchdog and terminates its exact owned processes.

Three-server ON CLUSTER acceptance remains in progress. A first attempt failed
before DDL on the isolated server's memory limit (native code 241); this is not
a passing HA result. Native client diagnostics expose only a numeric error code,
never SQL, passwords, password hashes or raw server error output. Test fixtures
use random private credentials and do not modify deployed service accounts.

After increasing only fixture memory, the three-server native TLS test passed
in source copy `platform-installer-qa-c1b36e7dcba14df4ad6c3f326e07768a` in
20.177 seconds. It uses one isolated Keeper for distributed DDL and three
server processes: library databases first, a single initiating user/grant batch
with ON CLUSTER default, authenticated permissions on all three members,
unchanged account repeat and Verify, foreign-account rejection. It proves the
application DDL path, not Keeper quorum recovery or deployed infrastructure HA.

The above native checks subsequently allowed activation of the Redis/Sentinel
account and ClickHouse database/account capabilities. The generated catalog and
fixture locks are reproducible at
`sha256:c19752390b9d1665c3bc9f892a888dc9781c0d7fb543cf98cd7f739261541565`.

## Common pipeline acceptance — 2026-10-11

Source copy `platform-installer-qa-3fb2610dabec4657ac4da97d185dfabc`:
the full A5 entrypoint test passed in 485.472 seconds (one functional scenario,
not a benchmark). It exercised library resources before instance accounts,
Vault publication and in-container Agent, PKCS12, PostgreSQL, Redis,
Sentinel discovery/authentication and ClickHouse permissions; repeated Apply
and read-only Verify passed. Kafka SSL ApiVersions without authentication
passed against the existing QA broker at `192.168.56.101:9094`, using only its
public CA; no deployed Kafka configuration or account was changed. The test
asserts Kafka and overall `/status` when these explicit Kafka inputs are present.
Other provider processes/accounts were isolated test fixtures.

The updated rootless RED OS image is
`platform-application-connection-probe:a5-qa`, image ID
`sha256:98185c999f218e24da536febfb8b253cd42a152a5ce2000608bfc8f129c7cb60`.
No runtime bundle was published.

Full A4 regression passed in 328.665 seconds, including unchanged legacy root
inputs, existing Vault sources in Verify, CAS retry, AppRole renewal/restart,
wrong-password and foreign-document rejection, and standalone bootstrap input.
Application unit suite: 67 PASS; Vault suite: 12 PASS. Core regression:
553 tests, 534 PASS and 19 skip; 16 unchanged native PKI recovery cases were
excluded from this run. Native ClickHouse tests after the repeated-query
optimization: 3 PASS in 96.712 seconds.

ClickHouse query masking is configured on each server; fixture native logs
contain neither plaintext passwords nor the submitted verifier. Keeper's native
DDL queue legitimately carries the verifier, not plaintext. This does not prove
Keeper quorum recovery or production queue network-access/retention policy;
the existing private TLS Keeper boundary remains required. See the official
[query masking setting](https://clickhouse.com/docs/reference/settings/server-settings/settings/query#query_masking_rules).

Final ClickHouse witness/concurrent-repeat checks passed: 3 tests in 37.409
seconds in source copy `platform-installer-qa-a559456c6a394e01ac358f5c3a49196a`.
Concurrent same-instance creation yields one changed and one unchanged result;
malformed witness records fail closed. The first invocation omitted the
collection search path and failed before provider execution; the corrected
invocation above passed. Credential-root compatibility tests: 3 PASS;
all application-library playbooks pass Ansible syntax checks; generated catalog
check PASS. Mandatory FULL DIFF review remains open.
No commit or master synchronization performed.

## Owner-approved targeted acceptance follow-up

Owner authorized focused evidence for A5-D01 and A5-D02 plus documentation of
the Redis `existing` ACL profile. The Redis profile accepts the supported
canonical command/key/channel rules and rejects broader ACL categories or
permissions instead of trying to interpret them. Exact behavior is fail-closed
with `REDIS_APPLICATION_GRANTS_DRIFT`.

## Owner-approved D01/D02 targeted acceptance — 2026-10-11

REDOS QA source copy `platform-installer-qa-cf40c4f619864f1aae192c81e1fba0fe`:

- Core provider projection suite: 15 PASS. The new case projects two libraries,
  two Docker placements, separate Redis deployments on different host IDs, and
  exactly one logical account hook per library.
- Redis native ACL suite: 2 PASS. In the member fan-out recovery case, member
  one's account/witness survives a failed authentication on member two; after
  correcting the invocation credential, member two completes, repeats are
  unchanged, and the next-stage publication marker is reached only after all
  members succeed. Installing `api-cspa` preserves `api-sdku` and both witnesses.
  A broad existing ACL (`+@all`, `~*`) fails with `REDIS_APPLICATION_GRANTS_DRIFT`
  and is not adopted.
- ClickHouse native provider suite: 3 PASS, including standalone and three-server
  ON CLUSTER default. In HA, a same-name account on one member without this run's
  witness blocks before the following publication task; the existing library
  database witness is unchanged. Removing the isolated foreign fixture allows
  account creation on all members, publication proceeds, and repeat is unchanged.

The first Redis fixture revision tried to stop/restart a process and failed to
recreate its Unix socket. That draft was replaced by deterministic member
authentication failure and re-invocation; no production code change was needed.
An early ClickHouse test query used an unquoted hyphenated test identifier and
failed with syntax code 62; the fixture now quotes the identifier. A marker task
initially polluted the concurrent changed-count assertion; the test now checks
the publication barrier before testing unchanged concurrency. Final tests listed
above passed from the final synchronized source copy. This is functional
acceptance, not a performance benchmark.

All test-owned processes and the QA source copy were cleaned with the standard
helper. The independent TARGETED_RECHECK approved A5-D01/D02 against manifest
`87eadc687df307b1f2debf58c0d539aa2762d3b5e757f24441cfb2519f14d0cd`; see
[FULL DIFF and targeted review report](../reviews/a5-diff-review.md). A5 current-scope
implementation, native QA and review gates are complete. C02 production Keeper
access/retention policy remains a nonblocking infrastructure limitation.

## Independent FULL DIFF disposition

[FULL DIFF report](../reviews/a5-diff-review.md): initial BLOCK, followed by owner-approved TARGETED_RECHECK APPROVE for D01/D02. D03 is documented/tested; C02 remains nonblocking. QA copies and owned temporary logs were cleaned; the prepared image was retained. No commit/master synchronization.
