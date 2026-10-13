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
| Rebuilt bundle after Core changes | PASS | Built `redos73-20261012-02` on trusted `node2` from the current working-tree source and retained approved runtime inputs from `-01`; 1,108 component files matched manifest size/SHA-256, with RED OS 7.3 and 8.0.3 platforms and five verified artifact sources. Manifest SHA-256 `c696d19335120c5869fe0adcce21384b8e01bbac5846f0345407ad839e3f81ba`. On RED OS 7.3 / Core 2.13.13, current Core `execution-capabilities.yml` returned `ok=1 changed=0 failed=0`. Bundle retained in `.runtime/qa/redos73-bundle-redos73-20261012-02/bundle/`; not published to active cache. |
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

## Initial direct standalone Apply / Verify / repeat on RED OS 7.3

This checkpoint predates the later Docker and BIND support corrections below.

The service roles below were run directly from a synchronized current-tree
workspace on the 7.3 VM, with temporary standalone inputs and without Go,
Wails, React, or Installer orchestration. Each deployment used a unique QA
name/port; runtime credentials stayed in protected temporary files and were
not printed. SELinux was set to Permissive for these tests at the owner's
request, so they do not establish behavior under enforcing policy.

| Service | Apply | Verify-only | Repeat Apply | Result |
| --- | --- | --- | --- | --- |
| ClickHouse 26.8.14.3 from the verified offline bundle | `ok=114 changed=3 failed=0` | `ok=33 changed=0 failed=0` | `ok=114 changed=0 failed=0` | PASS; TLS `SELECT 1` also passed. |
| PostgreSQL 16.14 plus `pg_auto_failover` package family | `ok=73 changed=5 failed=0` | `ok=42 changed=0 failed=0` | `ok=71 changed=0 failed=0` | PASS; TLS-enabled instance on a separate QA port. |
| Redis 8.10.1-1.el7 | `ok=83 changed=8 failed=0` | `ok=44 changed=0 failed=0` | `ok=86 changed=0 failed=0` | PASS; TLS authentication and standalone health checks passed. |
| Vault 2.0.4-1.el7 from the configured repository | `ok=157 changed=22 failed=0` | `ok=49 changed=0 failed=0` | `ok=140 changed=0 failed=0` | PASS; initialized, unsealed, and audited; root token and unseal shares remain in mode-0600 files under the admin account's mode-0700 runtime secrets directory. |

Redis first failed because the requested SELinux Enforcing mode denied the
service log write. After the owner-requested runtime switch to Permissive, a
fresh clean QA deployment passed. Its initial authentication retry was caused
by a newline in the temporary test secret; the secret fixture was corrected,
not the role. The final Apply/Verify/repeat figures above are from the clean
successful run.

Docker's direct Core probe stopped before mutation with
`DOCKER_ROOTLESS_UNSUPPORTED_TARGET`: its current validator accepts only RED OS
8.0, while the VM is 7.3. BIND authoritative mode and Keepalived VRRP require
at least two distinct inventory hosts, so this one-host VM cannot exercise
their deployment paths. Kafka standalone, HAProxy and DNS-client did not
receive direct service Apply/Verify/repeat runs at this checkpoint. Thus the four
successful services establish per-service 7.3 runtime evidence only for those
combinations, not general support for all ten services.

The QA deployments for ClickHouse, PostgreSQL, Redis and Vault remain on the
test VM after the runs. Vault's protected bootstrap custody files are retained
because the initialized Vault deployment remains present. Temporary source
workspaces, SSH access, and nonsecret local fixture files are removed during
cleanup.

## Additional direct service checks

These checks were performed from the same synchronized current-tree workspace
on the single RED OS 7.3 VM. They exercise service roles directly and do not
exercise Go, Wails, React, or Installer orchestration.

| Service | Apply | Verify-only | Repeat Apply | Result |
| --- | --- | --- | --- | --- |
| Docker Rootless | `ok=110 changed=13 failed=0` | `ok=112 changed=0 failed=0` | `ok=112 changed=0 failed=0` | PASS; rootless daemon, TLS API and Compose verified. Added `dnsmasq` to configured package list after LXC network setup showed it was required but absent. |
| BIND authoritative primary (`qa.redos73.test`) | `localhost ok=27 changed=1; node1 ok=87 changed=9; failed=0` | `ok=15 changed=0 failed=0` | `localhost ok=30 changed=0; node1 ok=72 changed=0; failed=0` | Full `services/bind/playbooks/apply.yml` and `verify.yml` passed on RED OS 7.3. Apply reconciled the old A record from stale `.104` to current `.105`; repeat Apply was idempotent. |
| HAProxy 3.4.3 | `ok=36 changed=3 failed=0` | PASS | `ok=36 changed=0 failed=0` | PASS on the VM's current `192.168.56.105` address, with isolated QA listener ports. Initial attempt used stale DHCP address `.104` and failed bind before successful rerun. |
| DNS-client | `ok=14 changed=0 failed=1` | Not run | Not run | BLOCKED before mutation: `/etc/resolv.conf` is a regular NetworkManager-managed file while `systemd-resolved` is loaded; role correctly rejected taking ownership (`DNS_CLIENT_RESOLV_CONF_CONFLICT`). |

BIND was initially tested using a direct role-phase harness (`prepare`,
`activate`, `start`, `verify`) with one authoritative primary and no secondary.
After the Python 3.8 schema-resource compatibility fix and the single-primary
contract correction, the full service playbooks passed with the one-host
project fixture. This verifies the full standalone primary flow on 7.3, but
not multi-host delegation or replication. An earlier Apply attempt had stopped
before target mutation on `No module named 'importlib_resources'`.

Kafka standalone was subsequently exercised with a direct role harness (see
the Kafka result below). Keepalived's VRRP behavior cannot be proven
on the available single-host VM because it requires at least two distinct
participants. Neither is marked PASS. These limitations are separate from the
successful direct checks above.

Docker's successful run supersedes the earlier `DOCKER_ROOTLESS_UNSUPPORTED_TARGET`
blocker: the RED OS 8-only validator was removed, and the role now installs
configured generic package names on 7.3. This only establishes the tested
Docker Rootless combination on this VM.

## BIND standalone cardinality correction

The BIND service mode now accepts one primary participant with zero or more
secondaries. The Core DNS resolver still requires exactly one primary and
validates every supplied participant; when there are no secondaries, the zone
NS set contains only the primary. The role omits `allow-transfer` and
`also-notify` when the secondary set is empty. The service manifest and
compatibility version are now `1.0.0-alpha.2`; the fixture catalog and project
catalog locks were regenerated from the current service manifests.

The Core validator's vendored JSON Schema reader no longer depends on the
external `importlib_resources` backport under Python 3.8. It uses stdlib
`pkgutil.get_data` for schema and vocabulary resources; Python 3.9+ continues
to use `importlib.resources.files`.

On RED OS 7.3 / Python 3.8.20 / Ansible Core 2.13.13, the schema-validation,
project-validation, and BIND contract suites passed (7, 24, and 21 tests; one
BIND test skipped). BIND `apply.yml` and `verify.yml` syntax checks passed,
and fixture catalog reproducibility passed. Target-free
`ansible-core/playbooks/validate.yml` against `examples/valid/bind-standalone`
now returned `PASS`, `ok=12 changed=0 failed=0 skipped=2`. An earlier run
before the compatibility fix failed on the missing module import; the
successful run demonstrates project validation now accepts the one-primary
topology. The subsequent full BIND service Apply/Verify/repeat run is recorded
above; it answered authoritatively for `qa.redos73.test` and returned the
current host address `192.168.56.105`.

## Kafka standalone check

On RED OS 7.3.7 / Python 3.8.20 / Ansible Core 2.13.13, the Kafka 4.3.1
`platform.kafka.kafka_kraft` role was run directly from the synchronized
current tree, without Go, Wails, React or Installer orchestration. A combined
single-node broker/controller used dynamic quorum, plaintext client,
inter-broker and controller listeners on ports 19092, 19094 and 19093, and
Schema Registry was disabled. The offline archive
`kafka_2.13-4.3.1.tgz` matched SHA-256
`f118328b2d053497350d5befd82c08db7ffd710327ff52943dd5caaa1b25db21`.
The role installed `java-21-openjdk-headless-21.0.12.1.1-1.el7.x86_64` from
the VM's enabled RED OS Updates repository.

Apply passed (`ok=87 changed=13 failed=0 skipped=24`), Verify-only passed
(`ok=81 changed=0 failed=0 skipped=39`), and repeat Apply passed
(`ok=87 changed=0 failed=0 skipped=24`). The systemd unit remained active and
all three listeners accepted connections. `kafka-broker-api-versions.sh` also
successfully queried broker node 71. This evidence covers only the tested
single-host, plaintext combined-member configuration; it does not establish
TLS, Schema Registry or multi-host quorum behavior.

## RED OS 7.3 three-host service checks

On 2026-10-12, direct Ansible/Core checks used the freshly synchronized
worktree on RED OS 7.3.7 hosts `192.168.56.104`, `.105`, and `.106`. No Go,
Wails, React, or Installer orchestration was involved. The bundle
`redos73-20261012-02` was built and component hashes were verified, but it was
retained as a QA artifact and not published to the active cache.

| Service/topology | Target-free validation | Apply | Verify | Repeat Apply | Result |
| --- | --- | --- | --- | --- | --- |
| Keepalived, three VRRP participants | PASS (`ok=12 changed=0 failed=0`) | PASS; active on all hosts and `.104` owned VIPs `.107` and `.108` | PASS; one MASTER (`.104`), two BACKUP (`.105`, `.106`), `ok=17/13/13`, no failures | PASS; host recaps `ok=30 changed=0 failed=0` | PASS for this three-host topology |
| BIND primary plus two secondaries | PASS (`ok=12 changed=0 failed=0 skipped=2`) | PASS; `.104` primary, `.105` and `.106` secondaries; recaps `ok=103/54/54`, no failures | First check on `.105` preceded AXFR convergence; after serial 1 arrived, Verify passed (`ok=15/12/12`, no failures) | PASS; recaps `ok=90/44/44`, no failures | PASS after expected asynchronous zone transfer |
| Kafka distributed KRaft with Schema Registry | PASS after refreshing stale fixture catalog version (`ok=12 changed=0 failed=0`) | BLOCKED before mutation on all hosts | Not run | Not run | Ansible Core 2.13 rejected the Schema Registry assert because `fail_msg` at `schema_registry_validate.yml:31` resolves to a list; no service mutation occurred |
| ClickHouse server and Keeper, three paired members | Not separately captured for this runtime harness | Six named systemd instances started, but HA Verify failed waiting for the Keeper TLS client listener; subsequent reapply output was not retained | BLOCKED; HTTPS `/ping` returned 200 on all three, but replication verification failed while creating the replicated table; read-back was not proven | No conclusive idempotence result | NOT PASS; TLS/cluster verification remains unresolved |

These results do not complete multi-host testing for all ten services. In
particular, multi-host PostgreSQL, Redis, Vault, HAProxy, Docker Rootless, and
DNS-client checks were not run in this session. Existing single-host evidence
does not substitute for those topologies or for full Installer acceptance.

After the checks, the requested service cleanup ran on all three hosts.
ClickHouse, Keepalived, and BIND packages and their QA data/config directories
were removed. A final read-only check found no matching service packages or
active service units, no ClickHouse QA data/root, and no BIND QA zone directory.
The DNF transactions also removed the dependency packages `hw-id`, `inxi`, and
`loginfo-cli` on each host as dependencies of the requested BIND package
cleanup. Temporary QA credentials and synchronized source workspaces were
removed.

### Kafka and Schema Registry follow-up — 2026-10-12

The first distributed Kafka + Schema Registry Apply exposed an Ansible Core 2.13 contract error before service mutation: Schema Registry passed a list of finding mappings to `assert.fail_msg`. The role now serializes those findings with `to_nice_yaml`; a focused regression test passed. A three-node Apply then completed (`node1 ok=265 changed=28 failed=0`; `node2/node3 ok=262 changed=26/28 failed=0`). Kafka KRaft listeners became ready, each Schema Registry HTTP and HTTPS endpoint passed readiness, and all nodes verified trusted HTTPS connections to all three Registry peers.

The current-tree Verify passed with no changes (`node1 ok=174 changed=0 failed=0`; `node2/node3 ok=159 changed=0 failed=0`). Repeat Apply also passed idempotently (`node1 ok=276 changed=0 failed=0`; `node2/node3 ok=273 changed=0 failed=0`).

PKI previously failed on a clean controller because materialization invoked `keytool` before Kafka installed Java on the target hosts. PKI now probes for `keytool` before requests that produce PKCS12 stores, installs the configurable `platform_pki_keytool_package` when missing, and verifies the executable again before continuing. With Java removed, a fresh PKI Apply on RED OS 7.3.7 installed `java-21-openjdk-headless` from the enabled repository (`localhost changed=1`), passed the recheck, and completed with `failed=0` on localhost and all three targets. The focused PKI preflight contract test passed. Java, PKI target artifacts, the project CA trust anchors, Schema Registry and Kafka data/configuration/distributions were removed afterward; Kafka host reset verified its selected paths absent.

The complete `test_service_apply_pki_contract.py` file still has two unrelated failures against other current-tree edits (PostgreSQL monitor address expectation and HAProxy exact PKI selector expectation); the new PKI test passes independently. The focused Schema Registry serialization test also passes independently. This remains direct RED OS Core/service evidence only, not Go/Wails/React acceptance.

### DNS-client three-host rerun — 2026-10-13

The current working tree was synchronized to RED OS 7.3.7 host `.104` and
Ansible Core 2.13.13 ran the DNS-client role across `.104`, `.105`, and `.106`.
The target-free project validation passed (`localhost ok=16 changed=0
failed=0`). A read-only role discovery pass succeeded on every node
(`ok=10 changed=0 failed=0 skipped=2` per host): NetworkManager was selected
because it was both loaded and active; `systemd-resolved` was not active, and
`/etc/resolv.conf` was a regular file on all three nodes. Apply then stopped
before changing any host with `DNS_CLIENT_SPLIT_DNS_UNSUPPORTED` on every node
(`changed=0`, `failed=1` each), because none has the required NetworkManager
split-DNS configuration. Verify and repeat Apply were not run. This confirms
the active-service backend selection change and identifies a remaining target
configuration prerequisite; it does not establish DNS-client deployment
support on RED OS 7.3.

The temporary QA key was removed from all three `authorized_keys` files and
verified absent. The synchronized source workspace, fixture, and temporary
controller credential files were removed. No DNS configuration was changed.

### DNS-client three-host resolution with systemd-resolved — 2026-10-13

After the owner enabled `systemd-resolved` on all three RED OS 7.3.7 hosts,
NetworkManager was configured to use the `systemd-resolved` DNS plugin, and
`/etc/resolv.conf` was linked to the systemd stub resolver. Read-only checks
confirmed the service active/enabled, upstream DNS `10.0.2.3`, and successful
external name resolution on `.104`, `.105`, and `.106`.

The current working tree was synchronized to `.104`; Ansible Core 2.13.13 ran
the BIND primary/secondary and DNS-client playbooks directly, without Go,
Wails, React, or Installer orchestration. Three-host BIND Apply passed
(`localhost changed=1`; node1 `ok=103 changed=12`, node2/node3 `ok=54
changed=10`, all `failed=0`). BIND Verify passed (`ok=15/12/12`, all
`changed=0 failed=0`). DNS-client Apply passed (`localhost ok=16 changed=0`;
all three nodes `ok=24 changed=3 failed=0`). DNS-client Verify passed (`ok=16`
localhost; `ok=25 changed=0 failed=0` per node). Repeat Apply passed
(`ok=23 changed=0 failed=0` per node; localhost `ok=16 changed=0`). Verify
checked the effective split route and servers through `resolvectl status` and
resolved the managed host name through the normal system resolver. This
supersedes the earlier `DNS_CLIENT_SPLIT_DNS_UNSUPPORTED` block for this
configured backend. BIND and DNS-client QA configuration remains on the three
hosts for continued inspection and testing.

### PostgreSQL pg_auto_failover and Redis Sentinel three-host rerun — 2026-10-13

A fresh three-host project using Ansible Core 2.13.13 passed target-free validation (`localhost ok=12 changed=0 failed=0 skipped=2`). PostgreSQL `pg_auto_failover` was configured with one monitor on `.104` and two database members on `.105`/`.106`, using repository packages, managed PKI and TLS.

The first PostgreSQL Apply exposed setup issues before completion: the QA controller needed explicit PKI inventory/owner paths, and the role hardcoded `/usr/bin/pg_ctl` although RED OS 7.3 installs PostgreSQL 16 binaries under `/usr/pgsql-16/bin`. Both `pg_autoctl create monitor` and `create postgres` now use `platform_postgresql_binary_directory/pg_ctl`. After synchronizing the current tree, Apply passed (localhost `ok=226 changed=0`; `.104/.105/.106` `ok=108/112/105`, `changed=8/19/14`; all `failed=0`). Verify passed (`ok=52 changed=0 failed=0` on every node). Repeat Apply passed with `changed=0 failed=0` on localhost and all nodes (`ok=226/104/107/105`).

Redis Sentinel HA was applied on the same three hosts (`ok=122/117/117`, `changed=12/13/13`, `failed=0`) and Verify passed (`ok=58/53/53`, `changed=0 failed=0`). The later 2026-10-13 current-tree follow-up ran Verify (`localhost ok=10`; nodes `ok=64/59/59`, all `changed=0 failed=0`) and repeated Apply three times while resolving convergence. First repeat changed three TLS material/service tasks per host; second repeat changed the Redis ACL-file attachment and Redis member restart on `.105` and `.106` only; the third repeat was clean (`localhost ok=431 changed=0`; `.104/.105/.106 ok=131/125/125 changed=0`). Final Verify also passed (`localhost ok=10`; nodes `ok=64/59/59`, all `changed=0 failed=0`). Inspection after reconciliation confirmed the member configs point to their expected per-member ACL files. Latest Redis Apply/Verify/repeat evidence is PASS; the earlier changed runs remain as convergence history.

These are direct standalone Ansible/Core checks without Go, Wails, React or Installer orchestration. PostgreSQL multi-host Apply/Verify/repeat is PASS; Redis multi-host Apply/Verify passed but repeat-Apply idempotency is unresolved.

### PostgreSQL binary-directory portability correction — 2026-10-13

PostgreSQL no longer defaults `platform_postgresql_binary_directory` to the
versioned RPM path. The role detects an existing `pg_ctl` in `/usr/bin` or
`/usr/pgsql-<major>/bin`, honors an explicitly configured directory, and
rechecks the selected path after package installation. The pre-install fallback
uses the RED OS major version so a clean 7.x target can form its initial PATH;
Verify works without gathered distribution facts.

On the three RED OS 7.3.7 nodes, `pg_ctl` is present at
`/usr/pgsql-16/bin/pg_ctl`; it is not under `/usr/bin`. Current-tree Apply
passed (`failed=0` on all hosts), and Verify passed (`changed=0 failed=0` on all
hosts). One earlier repeat reported 5 changed tasks per host and 28 on
localhost. Its task log shows the controller creating CA/request directories,
CA and leaf keys/certificates, CSR/fingerprint files and PKCS#12 stores; target
logs show CA trust-anchor and Core PKI deployment, followed by PostgreSQL-owned
TLS files and reloads. This was reconstruction of missing managed PKI state,
not repeatable PostgreSQL-role drift. The reason that runtime-only PKI state
was absent for that run was not established. After the PKI state was present,
current-tree PostgreSQL Apply completed with `changed=0 failed=0` on the
controller and all three nodes (`localhost ok=424`; nodes `ok=120/123/121`).
An initial Verify attempt exposed the missing distribution-fact fallback; after
correction, Verify passed. RED OS 8's `/usr/bin` path is supported by candidate
detection but was not retested in this run. Direct Ansible/Core evidence only.

### Vault Raft three-host rerun — 2026-10-13

Vault Apply first stopped at its documented `VAULT_SWAP_ENABLED` preflight on
all three nodes. Swap was 3 GiB with 0 bytes used and several GiB of memory
available per host; it was disabled with `swapoff -a` for this live QA session
only, without changing `/etc/fstab`. The repeated Apply then passed on all
hosts (node1 `ok=193 changed=19`, node2/node3 `ok=102 changed=12`, all
`failed=0`). Verify passed (`localhost ok=22`; node1 `ok=57`, node2/node3
`ok=46`; all `changed=0 failed=0`). Repeat Apply passed idempotently
(`localhost ok=233 changed=0`; node1 `ok=172 changed=0`; node2/node3
`ok=111 changed=0`). Vault bootstrap output remains in its configured protected
secret directory. Endpoint integration plays had no matching hosts. This is
direct Ansible/Core evidence only.

### HAProxy and Docker Rootless three-host rerun — 2026-10-13

The current working tree was synchronized to RED OS 7.3.7 host `.104`; Ansible Core 2.13.13 ran the multi-host service playbooks directly. HAProxy target-free validation passed (`localhost ok=12 changed=0 failed=0 skipped=2`). Apply passed on all three nodes (localhost `ok=104 changed=2`; node1/2/3 `ok=81 changed=15/13/15`; `failed=0`). Verify passed with `changed=0 failed=0` on all nodes (`localhost ok=14`; each target `ok=20`). Repeat Apply was idempotent (`localhost ok=98 changed=0`; targets `ok=81 changed=0`).

Docker Rootless was added to the protected three-host QA project with its own managed TLS profile and runtime-only account password reference. Apply passed (`localhost ok=439 changed=24`; each target `ok=142 changed=22`; `failed=0`). Verify passed (`localhost ok=10`; each target `ok=60 changed=0 failed=0`). Repeat Apply was idempotent (`localhost ok=424 changed=0`; each target `ok=141 changed=0 failed=0`). The first Apply exercised the rootless daemon restart handler successfully; no service cleanup was performed. These are direct Ansible/Core checks only, without Go, Wails or React.

ClickHouse was not rerun during this immediate HAProxy/Docker pass. The protected inputs expected by the old manual-role fixture were absent. It was later rerun with a separate project-managed PKI fixture; see “ClickHouse three-host Raft and replication rerun” below.

### ClickHouse three-host Raft and replication rerun — 2026-10-13

A separate three-host fixture was prepared for `.104/.105/.106` with a unique deployment ID, a project-managed TLS profile and the existing protected runtime password. The ClickHouse 26.8.14.3 RPMs were reused from the preserved RED OS 7.3 bundle; all three digests matched the manifest. Core target-free validation passed (`localhost ok=12 changed=0 failed=0 skipped=2`).

Apply passed (`localhost ok=247 changed=28`; each target `ok=143 changed=22`; `failed=0`). The first Apply generated and deployed the profile certificates through the normal Core PKI flow. Dedicated Verify passed with no changes (`localhost ok=22`; each target `ok=47 changed=0 failed=0`). An authenticated HTTPS check with CA verification created a ReplicatedMergeTree table, inserted one row through `.104`, and read that row through all three TLS endpoints (`localhost ok=4 changed=0 failed=0`). Repeat Apply was idempotent (`localhost ok=233 changed=0`; each target `ok=140 changed=0 failed=0`).

This supersedes the 2026-10-12 failed multi-host ClickHouse verification, which used a separate direct-role TLS fixture and did not prove Keeper convergence or replication. The new check used managed Core PKI; no certificate verification was bypassed. Service state and the test table remain on the three QA nodes for inspection. Direct Ansible/Core evidence only.

### REDOS73-DIFF targeted corrections — 2026-10-13

On RED OS 7.3.7 (Ansible Core 2.13.13), the current working tree was synced
through `scripts/qa-sync.ps1` to `.104`. The focused
`ansible-core/tests/test_service_apply_pki_contract.py` suite passed (13 tests),
and `services/keepalived/tests/test_net_02_contract.py` passed (13 tests).
The PostgreSQL contract now asserts the pg_auto_failover monitor URI uses the
explicit monitor member's `address`, the member registration uses that member's
`address`, and PostgreSQL dispatches runtime reconciliation through its current
`reconcile.yml`. The HAProxy contract now follows `lifecycle.yml`, asserting the
exact TLS profile and local deployment key are passed to PKI selection before
artifact delivery. Keepalived's two lifecycle service actions are asserted to
use `ansible.builtin.systemd` explicitly. Temporary source workspaces were
removed after the test run. This is direct Core contract evidence only.

The earlier FULL DIFF report records a fingerprint mismatch but omits the
submission's path manifest and fingerprint algorithm, so the old comparison is
not reproducible. The independent targeted recheck recomputed all 66 entries in
`redos73-diff-fingerprint.txt` and approved the current reviewed snapshot at
`sha256:fdee91010b78d766a712dba0523f4eb78ba78092609130555f39b832dd962201`.
It resolved `REDOS73-DIFF-01` and `REDOS73-DIFF-02` with zero blockers, and
confirmed the PostgreSQL monitor address and HAProxy exact PKI selector. The
owner closed `REDOS73-SUPPORT-01` for the tested Core/Ansible scope; no Go/Wails
acceptance was required because those layers were not changed. No support claim
is made for unverified versions or service topologies. The two corrected suites
passed before the read-only review; the reviewer did not rerun tests.
