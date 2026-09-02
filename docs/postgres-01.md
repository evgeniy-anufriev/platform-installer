# POSTGRES-01 — PostgreSQL standalone and pg_auto_failover

## Status

POSTGRES-01 is accepted. The selected RED OS acceptance set is
PostgreSQL 16.14 (`postgresql`, `postgresql-server`, `postgresql-contrib`)
with pg_auto_failover 2.2. The packages are resolved from the approved RED OS
system repositories. No product functionality was added during finalization.

Pre-failover HA acceptance has passed. The direct transient
`pg_stat_activity` plus `pg_stat_ssl` session was not observed during bounded
25-second observations on each data node (150 ms polling; configured
`health_check_period=5000 ms`), so it is explicitly not claimed as direct
catalog evidence. Acceptance uses equivalent runtime evidence: monitor-to-data
TLS authentication passed, both data nodes remained Reachable, the
topology-scoped `hostssl`/SCRAM rule was effective, plaintext authentication
was rejected, and no new `pgautofailover_monitor` HBA/authentication rejects
appeared. The period and timeout were observed read-only and were not changed.

Final acceptance evidence:

- standalone apply, verify and repeat apply passed with `changed=0` and
  `failed=0`;
- HA initial apply, separate verify and repeat apply passed with all four
  recap hosts at `changed=0`, `failed=0`;
- the final HA state was one automatic `PRIMARY` and one `SECONDARY`, both
  reachable, with matching PostgreSQL `system_identifier`;
- pre-failover and post-failover data were present after automatic promotion,
  rejoin and post-rejoin verification; the former primary was not restored by
  force;
- data-to-data replication used TLS, and monitor/data authentication used
  topology-scoped TLS rules; plaintext internal healthcheck authentication was
  rejected by HBA;
- direct built-in healthcheck catalog capture was not observed and is not
  required by the owner decision. Accepted equivalent evidence is the TLS
  authentication result, Reachable monitor state, effective `hostssl`/SCRAM
  HBA policy, plaintext rejection and absence of new monitor rejects.

Final static gates passed on RED OS: 48 focused tests, 113 full Core tests,
configuration-schema and fixture-catalog reproducibility, PostgreSQL and Kafka
syntax checks, privileged `sudo unshare -n` validation and `git diff --check`.

Secrets remain runtime-only through `SecretRef`; no plaintext credentials are
stored in tracked project state, generated state, logs or evidence.

## Contract

The service package is Ansible-native. Desired service configuration is owned
by ordinary group/member variables; generated state may contain only stable
machine identities and reconcile metadata. The initial modes are:

- `standalone`: exactly one `database` member;
- `pg_auto_failover`: exactly one `monitor` and exactly two `database` members
  on distinct hosts.

Every deployment requires a configurable `adminSuperuser` with a username and
runtime `passwordSecretRef`. Only the SecretRef is authored or persisted. The
password is resolved immediately at runtime, never placed in argv, generated
state, events or evidence.

## Ownership

| Area | Platform role | PostgreSQL | pg_auto_failover |
| --- | --- | --- | --- |
| Packages, paths, config and HBA | owns desired projection | consumes files | observes managed node |
| initdb and system lifecycle | performs state-aware orchestration | owns data files | supervises HA node when enabled |
| Monitor formation and node registration | invokes declared CLI | hosts extension | owns formation/state transitions |
| TLS material | consumes PKI-01 PEM projection | owns SSL runtime use | receives verified connection policy |
| Failover/rejoin | verifies outcome | exposes runtime state | owns promotion and rejoin decisions |

The role must not repeatedly rewrite files or settings owned by pg_autoctl.
Expected configuration is kept separate from observed configuration during
verify. Verify never initializes data, changes roles/passwords, registers
nodes, changes HBA, restarts services or writes generated state.

## TLS and security

PostgreSQL consumes PKI-01 PEM material directly. It does not create a second
PKI lifecycle and does not convert the material to JKS/PKCS12. HA internal
connections use `hostssl` HBA rules only; plaintext fallback is not permitted.
The selected pg_auto_failover 2.2 CLI supports `--ssl-mode verify-full`,
`--ssl-ca-file`, `--server-key` and `--server-cert`. Acceptance must prove
actual TLS through PostgreSQL runtime views, not only configuration text.

## Lifecycle and state

Managed paths are deployment/member scoped. Data state is classified as
uninitialized, initialized or partial/unknown using `PG_VERSION` and
`pg_controldata`; partial or conflicting initialized state blocks apply.
PostgreSQL `system_identifier` is the stable storage identity for reconcile.
The monitor formation/node identity is retained only when needed to prevent
unsafe re-registration.

The file created by `initdb` at `data/postgresql.conf` is never replaced.
Platform renders `postgresql-platform.conf` as a separate, Jinja-generated
fragment and adds one idempotent `include` line to the initdb-owned file.
Managed settings are emitted from dynamic dictionaries, including
`advancedConfig`; the systemd unit starts PostgreSQL with its normal data
directory and therefore keeps the PostgreSQL default configuration chain
intact.

## Deferred

Patroni, multi-monitor HA, more than two data members, backup/PITR, upgrades,
certificate rotation, imported external CA, generic database provisioning and
production UI remain outside POSTGRES-01.
