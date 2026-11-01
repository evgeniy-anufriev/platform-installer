# Kafka discovery aggregation under a service host limit

2026-11-01. Owner-reported first installation: five inventory servers, Kafka
placed on three. The service runner passes `--limit localhost:<service targets>`
but aggregation read discovery facts from the full `platform_targets` group.
Excluded application servers therefore had no discovery fact.

The existing single controller snapshot now uses sorted
`ansible_play_hosts_all`, the actual limited play host set. It retains strict
failure for missing discovery on a selected host. No identity, persistence,
source-selection, or execution-lifecycle contract changes; bounded fix, no
architecture review required under the review procedure.

Current sources were transferred with `scripts/qa-sync.ps1` to RED OS
192.168.56.101, workspace
`/var/tmp/platform-installer-qa-16f309d5a2734c35bb2094e3604c1b79`.
`test_kafka_discovery_aggregation.py`: 3 PASS, actual local Ansible tasks
(complete three-host snapshot, three of five hosts under --limit, missing
selected-host fact fails). `test_service_apply_pki_contract.py`: 13 PASS.
Tests used synthetic inventories and in-memory facts; no installed service
or active run was changed. Temporary QA workspace cleaned afterward.

Updated-bundle React/Wails installation acceptance remains pending: the trusted
bundle build host 192.168.56.102 timed out on SSH (8-second connection timeout).
No bundle built, published, rebound, or activated; no installation started.
Deployment of this fix requires a rebuilt runtime bundle and node preparation.

## Computed nodeId delivery to execution

The next owner-reported failure reached inventory-to-instance construction:
all three saved members omitted `configuration.nodeId`. Core already resolved
the numeric suffix for the editor, but `_execution_role_variables` deliberately
omitted ROLE_DEFAULT settings, expecting ordinary role defaults to provide them.
There is no scalar role default for this computed per-member value.

Kafka nodeId now declares the existing `x-memberInputOnly` capability. The
planner carries resolved member-only values in the existing private role map as
`<variablesPrefix>member_inputs`, keyed by member ID, without host scalar
overwrites. The Kafka instance task uses this Core value when ordinary inventory
does not supply an explicit nodeId. No suffix algorithm was added to Ansible,
no Go/UI changes or portable-project writes, and no new execution entrypoint.
Fixture catalog and example locks were regenerated with the standard builder.

Focused current-tree RED OS 101 checks: 100 tests PASS across nodeId execution
(3), deployment plan (35), configuration resolution (28), runtime role transfer
(3), Registry projection types (1 with native-mode/port subcases), discovery
aggregation (3), configuration contract (7), fixture catalog (7), and service
Apply/PKI contracts (13). New execution tests use the real Core resolver,
planner role-variable projection, real action-only runtime transfer, and actual
Kafka `project_runtime.yml`/instance tasks with local synthetic inventory:
three of five targets, classic/native Jinja, explicit zero/42, and co-located
members with distinct IDs. They assert integer node IDs, unchanged desired
input and `changed=0`; no service installation occurs.

Temporary source workspace
`/var/tmp/platform-installer-qa-0fd799b61f9949efbbb7cf8e3bc52ff2` was cleaned.
The trusted build host 192.168.56.102 is still unreachable (SSH timeout8s).
Updated-bundle React/Wails acceptance remains pending; no bundle publication,
node preparation, plan approval, or installation Start was performed.
