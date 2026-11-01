# PostgreSQL monitor-first and bounded create acceptance

Owner request (2026-11-01): fix data registration before a monitor on node3;
bound both pg_autoctl create commands. Owner explicitly limited acceptance to
real Core/Ansible Apply, without UI; no independent review was requested.

## Result

Apply now groups selected inventory hosts from ordinary effective role variables,
fully applies the monitor first, and only then applies data/standalone hosts
serially. Monitor failure is fatal before subsequent data plays. The same path
supports Core runtime_role_variables and manual inventory; no Go/UI service rules
or new desired-state persistence were added.

Both create commands use the role's existing GNU timeout dependency:
platform_postgresql_pg_autoctl_create_timeout=300 seconds by default, TERM then
KILL after5seconds. Positive timeout is required in HA mode. Ordinary create
postgres slot-convergence failures retain20retries/delay3; rc124/137 stop retries
and remain failed. No migration, PGDATA cleanup or monitor reassignment.

## Focused tests

Current sources synced with qa-sync and tested on RED OS102:
41 PostgreSQL tests PASS. Native Ansible scheduling covers a monitor at each
inventory position, monitor failure stopping data, --limit and standalone flow.
Real timeout/native command tests terminate synthetic hanging processes for
both create tasks (TERM and forced KILL), assert no remaining process, and
preserve ordinary transient-failure retry behavior. These timeout cases do not
claim a deliberately hung real PostgreSQL installation.

## Real Apply

Selected Execution Node RED OS101; actual existing
services/postgresql/playbooks/apply.yml including Core validation and PKI.
Fresh isolated project qa-pg-monitor-first:
PostgreSQL16.14-1.red80 / pg_auto_failover2.2-1 already installed on all3 VMs.
node3 monitor, node1/node2 database; port25432; deployment qa-pgmon3.
Dedicated data/config/log paths and pgpass/profile locations preserve existing
clusters, global PostgreSQL login profile and existing credential files.
Synthetic inputs generated only in the Execution Node's protected .runtime/secrets.
Persistent approved SSH identity forwarded through a temporary local agent;
only its public identity/verified known_hosts copied, no private key copied.

Native Apply exit0:
localhost ok239/changed31/failed0/unreachable0;
node3 ok114/changed21/failed0/unreachable0;
node1 ok117/changed22/failed0/unreachable0;
node2 ok110/changed17/failed0/unreachable0.
QA used a120second positive timeout override; product default remains300seconds.

Safe native log markers (.runtime/qa/pg-monitor-first/native-apply.log):
line2242 create monitor CHANGED node3;
line2355 first data play;
line3006 create postgres CHANGED node1;
line3767 create postgres CHANGED node2.
The monitor service was active/pg_isready accepting before data application.
Final pg_autoctl show state from node3:
node1 primary/read-write, node2 secondary/read-only, both timeline1/LSN0/3051820.
No Installer run/plan ID: this is direct native Apply, not a UI execution.
No separate UI, Verify-playbook or second Apply was run.

A standard bundle was built/validated/published before the owner's scope
clarification (digest2729542e0d603baf7c40b725b40f1926c5dedff49942b6edd9601ed8922c2a7b).
It was not activated; native testing used synced source. Prior active cache is
restored with the standard publisher during cleanup. Temporary source workspaces,
controller-only synthetic secret inputs and local forwarded agent are removed;
new isolated test services/data and managed PKI state are retained.
