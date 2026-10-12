# Historical documentation checkpoints

Extracted on 2026-10-12 from the original milestone documents. Recorded statuses,
versions, review verdicts and test outcomes describe their source scope and dates.
They do not override [CURRENT_STATE](../../../../CURRENT_STATE.md), authorize new
work or prove later acceptance. Requirements and planned QA remain in the source
documents. A moved evidence section retains its original wording and title.

## service-install-06-postgresql.md

Source document: [service-install-06-postgresql.md](../service-install-06-postgresql.md).

<a id="service-install-06-postgresql-checkpoint-001"></a>

## Acceptance evidence

The production-shaped Go lifecycle acceptance passed on 2026-09-24 against
three distinct RED OS targets: node1 (`192.168.56.101`) as monitor, node2
(`192.168.56.102`) and node3 (`192.168.56.103`) as database members.

| Cycle | Run ID | Terminal result | Duration | Apply changes |
| --- | --- | --- | --- | --- |
| First | `installer-45943379628ebee4a28716d85b571916` | `SUCCEEDED` | 17m45s | 65 |
| Repeat | `installer-4fcc0cd5afc8689509aea2e2a49935e6` | `SUCCEEDED` | 17m9s | 0 |

Both cycles completed PKI apply, PostgreSQL/pg_auto_failover apply and
PostgreSQL verify successfully. The opt-in Go test
`TestServiceInstall06PostgreSQLLifecycle` passed in 2094.93s. Its operator
event mirrors are retained under the corresponding Git-ignored
`.runtime/executions/<run-id>/events.jsonl` directories.

During acceptance, a valid topology without an explicit monitor member port
exposed a templating defect in the TLS credential probe. The role now consumes
the already-resolved defaultable monitor port; the focused RED OS contract,
deployment-plan, lifecycle, PKI-apply and configuration-resolution suite ran
111 tests successfully. No secret value was written to the project, events,
journal or evidence.


<a id="service-install-06-postgresql-checkpoint-002"></a>

Status: **DONE (2026-09-24)**.


## postgres-01.md

Source document: [postgres-01.md](../postgres-01.md).

<a id="postgres-01-checkpoint-001"></a>

## Status

I07 repeat finding (2026-10-10): the healthcheck role's no-password invariant
remains required. The Apply probe used `pg_roles.rolpassword IS NULL`, but
PostgreSQL's public `pg_roles` view masks that field. A read-only check on the
current primary showed `pg_roles` reporting non-null while protected
`pg_authid` reported the actual password as null. The probe now reads only the
nullness predicate from `pg_authid` as the local PostgreSQL superuser; it does
not return or log a password. Full UI repeat acceptance is still open.

Owner addition (2026-10-09): managed HBA permits all database/user client
connections from the observed subnet of the local PostgreSQL member address
using `hostssl all all <network/prefix> scram-sha-256`. Subnet/prefix comes
from ordinary Ansible network facts, not a fixed /24 or another host's default
route. Specific HA rules retain priority. Missing or ambiguous interface facts
block Apply before mutation. This source change awaits bundle delivery and
real client acceptance; current evidence is in the SI11 test journal.

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
