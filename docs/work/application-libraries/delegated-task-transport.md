# Delegated application task transport

## Scope and cause

Owner-reported Vault CA read failed while the same file could be read over SSH
from the Execution Node. Native RED OS reproduction showed that a task under
`connection: local` could retain the local transport despite `delegate_to` naming
a remote inventory host. The original CA correction is `2a2cdbb0`; the owner
confirmed the corrected diagnostic passed. This is not full installation evidence.

The follow-up fixes the same inherited-transport problem in all seven identified
application paths. No public contract, desired-state model, credential lifecycle,
SSH trust policy or provider selection rule changes. Canonical behavior is in
[Ansible Core](../../ansible-core.md#application-task-transports) and the existing
[package script contract](../../project-contract.md#package-script-execution-location-and-failure-diagnostics).

## Changes

| Path | Explicit remote transport points |
| --- | ---: |
| PostgreSQL application provider: discovery, preflight/TLS/login, resources, accounts, restore and Verify | 18 |
| Redis application account | 1 |
| ClickHouse application scope | 1 |
| Kafka topic/account include apply blocks | 2 |
| Image placement include apply and registry availability probe | 2 |
| Vault application network discovery | 3 |
| Provider script identity lookup and script role apply | 2 |

The 29 points explicitly use SSH for remote work. Script role apply selects
`local` for `runOn: execution_node` and `ssh` for explicit/default target mode.
Controller file handling, Vault HTTP/controller work, local delivery and facts
remain local. Operator inventory connection variables retain Ansible precedence.

## Validation

Tests run from the current working tree copied with `scripts/qa-sync.ps1` to the
established RED OS QA node as `platform-automation`, using its existing identity
and passwordless sudo policy. No owner installation host or live service changes.

`test_application_delegation_transport.py`: four native tests PASS, covering 35
routing cases. Provider payloads are replaced only inside the test with a read
of a temporary public controller marker. A closed loopback SSH port must be
unreachable for remote cases; accidental local reads make the test fail. The
tests cover 25 remote leaf tasks, five include/default-target cases, four local
script/delivery cases from an SSH caller and one explicit inventory-local case.
Temporary files are cleaned. No real credentials, CA contents or service data
are included in fixtures or output.

Focused regression matrix: 125 distinct test cases, 124 PASS and one SKIP.
The skip is the existing opt-in rootless PKI fixture
(`PLATFORM_QA_APPLICATION_PKI=1`), not a transport test.

- Four new routing tests PASS (35 cases).
- Existing provider/Vault/image preparation, script dispatch/post-install,
  entrypoint, PKI contract, native registry/auth tests: 109 cases, final 108 PASS
  and one SKIP. The initial run found two broken standalone registry fixtures:
  their temporary play lost the source-relative `placement.yml` include and
  their localhost target relied on inherited local connection. The fixture now
  retains the real include path and explicitly declares inventory-local
  transport. The full affected registry module reran with all eight tests PASS,
  including verbose success/failure credential-redaction checks.
- Existing package script runner, failure diagnostics, input availability and
  member projection: 12 PASS. The real Execution Node callback test confirms it
  never contacts its unreachable provider host and cleans its secret inputs.
- Native syntax checks PASS for applications Apply, Verify, post-install,
  image preparation, registry availability and standalone provider Apply.
- `git diff --check` PASS. Temporary QA source workspace cleaned using the
  standard sync helper.

Real React/Wails installation acceptance and an updated runtime bundle are not
part of this validation. Source fixes do not update deployed immutable bundles.
No independent review invoked, per the owner's explicit instruction.
