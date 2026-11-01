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
