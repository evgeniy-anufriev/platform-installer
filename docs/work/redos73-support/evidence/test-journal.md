# RED OS 7.3 Core and service test journal

Date: 2026-10-12. Target: RED OS MUROM 7.3.7, x86_64, Python 3.8.20,
Ansible 6.7 / ansible-core 2.13.13. Source was copied from the current working
tree to a temporary QA workspace with `scripts/qa-sync.ps1`.

## Core and playbook checks

| Check | Result | Evidence |
| --- | --- | --- |
| Ansible module lookup | PASS | `ansible.builtin.systemd` resolves; `ansible.builtin.systemd_service` does not resolve in Core 2.13.13. |
| Per-service apply/verify syntax | PASS | 20 of 20 playbooks passed independently with all service collections in `ANSIBLE_COLLECTIONS_PATH`. |
| Core execution-capabilities syntax | PASS | Target-free playbook syntax check. |
| Built bundle execution-capabilities | PASS | Target-free playbook on RED OS 7.3 returned `ExecutionCapabilities`, bundle `redos73-20261012-01`, Core `0.1.0`, `ok=1 changed=0 failed=0`. |
| Full Core Python unittest suite | NOT CLEAN | 383 tests; 28 failures, 31 errors, 15 skipped. This run preceded updates to old `systemd_service` test expectations. The harness also lacked `importlib_resources`, used incomplete collection paths in some fixtures and hit sudo/ownership-sensitive tests; current dirty Kafka/PostgreSQL/Redis changes have additional failures. |
| Focused Vault clear contract tests | PARTIAL | 18 tests; 2 failed because subprocess fixtures could not resolve the service collection on Ansible 2.13, 14 root-only filesystem proofs skipped under `admin`; the remaining 2 passed. |

## Service suites (run separately)

| Service | Result | Notes |
| --- | --- | --- |
| bind | PASS | 19 tests, 2 skipped. |
| clickhouse | PASS | 7 tests, 2 skipped; does not prove RPM availability or installation. |
| dns-client | PASS | 8 tests. |
| docker | PARTIAL | 3 tests; one ownership fixture failed even in the root rerun. |
| haproxy | PARTIAL | 29 tests; one partial-optimization test failed. Updated `systemd` contract assertions passed. |
| kafka | FAIL | 32 tests; 6 failures, including normalization, contract and unit-ownership cases in the current uncommitted Kafka work. |
| keepalived | PASS | 13 tests; updated `systemd` assertion passed. |
| postgresql | FAIL | 29 tests; 6 unit-ownership runtime cases failed in the current working tree. |
| redis | FAIL | 17 tests; 5 failures, including current unit-ownership cases. |
| vault | PARTIAL | 54 tests; one artifact-source contract failure. Updated service module assertions passed. |

## Target state and scope

Before testing, no target service packages or units were present (the base
system included BIND libraries/utilities); only SSH listened on TCP. The test
suites were run as local Ansible/Python fixtures, not as service installations
on the target. No service package was installed and no host-wide reset was
performed. Only the user-requested Ansible installation and temporary QA
access were used; temporary QA access is removed during cleanup.

Repository metadata queries against the VM's enabled repositories return
`postgresql16` (through 16.15) and `pg_auto_failover-16` 2.2-1. PostgreSQL's
current role metadata still pins Red OS 8 names/builds, so these repo packages
have not yet passed role-level installation. ClickHouse client,
common-static and server 26.8.14.3 are present in the offline bundle, matching
the artifact set used for Red OS 8; they have not yet passed a 7.3 Apply.
Other repository versions listed in the implementation note are candidates
only until role-level Apply/Verify/repeat checks pass.

## PostgreSQL package-mask resolution follow-up

The role now probes both `postgresql-<version>*` and
`postgresql<major>-<version>*` families with target-local DNF `repoquery`,
selects all three PostgreSQL components from one complete family, and passes
the exact x86_64 NEVRA values to the package module. In `pg_auto_failover`
mode, it similarly probes major-scoped and legacy package masks. Missing or
partial families fail closed with a service-specific error.

On RED OS 7.3, the role's read-only package-resolution playbook passed:
11 tasks, `changed=0`, `failed=0`. The resolved package set was checked against
`postgresql16` 16.14, `postgresql16-server` 16.14,
`postgresql16-contrib` 16.14, and `pg_auto_failover-16` 2.2-1. The PostgreSQL
service Apply and Verify were not run by this check, and it did not install
any packages.

The RED OS 7.3 Ansible 2.13.13 VM also passed the PostgreSQL `apply.yml`,
`verify.yml`, and package-resolution playbook syntax checks. The focused
PostgreSQL contract suite passed 28 tests. The broader RED OS 7.3 service
suite results above remain unchanged; no full service acceptance is implied.
