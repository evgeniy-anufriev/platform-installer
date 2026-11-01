# Kafka archive location: separate controller and target

2026-11-01. Owner-authorized correction after Kafka archive assertion failure.
Core delivery stages `kafka-binary` on the target and returns that target path.
Kafka previously statted it on localhost and used `unarchive remote_src: false`.
An Execution Node also hosting Kafka could mask both errors.

The existing approved source chooses location: OFFLINE_BUNDLE is statted and
unpacked on the target; ordinary manual `platform_kafka_artifact_path` remains
controller-local. Target stat uses become for the root-private staging directory.
SHA-256 assertions, delivery validation and source authority are unchanged.
No downloads, repository changes, new defaults, Go/UI or persistent state.

## Other services inspected

- Separate Schema Registry already switches stat/delegation and remote_src
  between delivered target archives and manual controller archives. Shared
  Registry likewise checks its approved archive at the proper location.
- ClickHouse checks/copies manual controller RPMs separately from delivered
  target RPMs; its DNF task consumes the target path.
- Vault, PostgreSQL, BIND, Keepalived and HAProxy use package installation and
  the shared delivery role, with target-side RPM checks/installation.
- Redis and Docker package tasks execute on targets; they do not treat a
  delivered archive path as a controller path. DNS client has no archive
  extraction. Common artifact_delivery stat/assert/DNF tasks execute on targets.

No additional instance of this archive-location defect found in this source
inspection. This is not fresh deployment acceptance of every service.

## Validation and limits

RED OS101 current-source workspace:
`/var/tmp/platform-installer-qa-478d03953dae4165a8e661d61363f807`.
18 tests PASS: new artifact-location4, shared-distribution7, Registry port types1
(with subcases), nodeId execution3, discovery aggregation3.

The new native fixture uses private mount namespaces for target /opt and the
fixed approved staging directory. A temporary test-only local connection enters
that namespace for real Ansible modules; localhost remains outside it. Real
Core delivery plus Kafka selection/stat/SHA-256/unarchive execute unchanged.
The delivered file is proven absent from the controller's staging filesystem.
Cases: offline fresh/repeat changed=0, manual controller archive fresh/repeat,
missing archive rejection and corruption rejection before extraction. Existing
services, host /opt and real staged artifacts remain untouched.

Two negative-control runs changed only disposable QA source copies back to the
old stat delegation or old remote_src separately; the new offline regression
failed in each case. Exact current bytes were restored afterward. Temporary
sources cleaned with qa-sync. Safe output is in local `.runtime/qa/` logs.

Independent review was started conservatively for archive verification, then
interrupted immediately on the owner's explicit "не вызывай ревью" instruction;
no verdict is claimed and no further review requested.

Trusted build host192.168.56.102 remains unreachable (SSH timeout8s). No bundle
build/publication/rebind/preparation or real React/Wails installation performed.
Updated-bundle acceptance remains pending. Deploy through a rebuilt verified
runtime bundle and ordinary node preparation; no active bundle was patched.

## Combined distribution installation path

The next owner screenshot failed at the stable installation link. Their staged
defaults set archive_directory=confluent-7.8.0 and
install_directory=/opt/confluent-7.8.0, matching the bundle builder's shared
Confluent layout. The role attempted to convert the extracted directory into
a symlink to itself. These defaults are valid and remain unchanged.

One task condition now creates the stable link only when its destination
differs from the extracted /opt/<archive_directory>. Existing /opt/kafka aliases
remain supported; ownership/marker checks are unchanged. The existing native
shared-distribution sequence now exercises both alias and direct bundle layouts
through fresh/repeat/Registry-only/Verify/missing-marker phases, checking that
the direct directory remains a directory and the alias stays the expected link.

Current-source RED OS101 validation: 22 tests PASS (shared-distribution8,
bundle artifact projection10, artifact-location4), no skips. This includes the
builder's existing test asserting the shared Kafka/Registry installation path.
Workspace `/var/tmp/platform-installer-qa-e6b274f975bb4ceabc8cbb7bba44cb0f`
was cleaned with qa-sync after validation. Previous intermediate alias checks
incorrectly followed an absolute target symlink in the controller namespace;
the test now checks its exact link target instead. Production direct-layout
checks passed; this test-fixture issue did not require another production edit.
Negative control without the new condition reproduced Ansible's exact refusal:
`the directory /opt/confluent-qa is not empty, refusing to convert it`.
Current source bytes were restored before cleanup.

No review invoked, following the owner's instruction. Build host102 still
times out on SSH; updated-bundle React/Wails installation remains untested.
No distributed bundle, service or active execution was modified.

## Static storage formatting and role default

Owner's Confluent7.8 CLI help has no --initial-controllers,
--no-initial-controllers or --standalone. The existing static configuration
already rendered controller.quorum.voters, but its format argv incorrectly
appended --no-initial-controllers. STATIC now has no dynamic-only flags.
Dynamic strategies retain their three existing command shapes.

After extraction, before member formatting, dynamic mode checks the installed
CLI's format --help. Missing capabilities produce the closed code
KAFKA_DYNAMIC_QUORUM_UNSUPPORTED; the existing diagnostic allowlist exports a
fixed Russian explanation, never arbitrary CLI text. This is a target-side
pre-format check, not target-free Project Verify or pre-plan capability proof.
The owner also explicitly requested role default quorum mode static; an
explicit desired dynamic override remains effective. No automatic migration.

31 focused RED OS101 tests PASS: storage/config command scenarios6,
safe diagnostics10, controller/SCRAM credentials3, shared distribution8,
artifact location4. New native Ansible tests execute production config/strategy/
format tasks against legacy and modern CLI-interface fixtures; they are not
actual Confluent7.8 binary installation acceptance. Owner subsequently authorized
real Confluent7.8 static installation on the three test VMs and separate official
DEV artifact acquisition; that acceptance is in progress.

### Confluent7.8 real-binary listener correction (2026-11-01)

Owner-authorized real React/Wails install of the official SHA256-verified
Confluent7.8.0 payload reached storage format but FAILED:
installer-c50aeb4e1cd521d7a05e8a8d8066cad7, plan-9efaaa85dea321c97f6d169c,
revision a5b9368c1ee09f641a8e03958261b9de5ba49962636ff8deadd4812a147befb2,
bundle346e8ec9d6786c9185c1d54f0ad55e1b072e52dc712c187f8955e47e9478c159.
An isolated format probe reproduced Kafka3.8 IllegalArgumentException:
advertised.listeners included the controller listener on a combined broker.
Static flags and salted SCRAM argfile themselves passed isolated native probes.

Production projection now advertises only broker listeners and omits
advertised.listeners for controller-only members. Bound listeners and the
controller quorum addresses remain unchanged. No existing data was formatted,
deleted or migrated by the diagnostic probes.

RED OS102 current-source tests: test_storage_format_runtime.py 8 PASS,
including actual Confluent7.8.0 storage formatting using production listener,
broker-config, static-quorum and format tasks in an isolated temporary directory.
Seven CLI fixture scenarios remain supplementary; they now reject advertised
controller endpoints. Real three-node installation acceptance remains pending.
No independent review invoked, per explicit owner instruction.

### Kafka3.8 Verify output compatibility (2026-11-01)

Real React/Wails Apply completed on all three QA nodes with bundle
f17aca4ed8b72e7323b93b4da832efa0e8fdbb29adbb61fafc34c651c41a8105,
source bca9d0d8, plan-e858e95c42155da3592289e8,
installer-d640f8d49c0869f2cecd3ebcb30834d2.
All3 format assertions passed (events1666/1814/1962); all3 Kafka7.8.0
and Registry units active. Verify then FAILED3217: its existing CLI-output
checks only accepted newer Kafka reply shapes. The observer25min deadline
did not stop execution; read-only subscription resumed through terminal.

Read-only real7.8 CLI: metadata quorum rc0/LeaderId2/CurrentVoters[1,2,3];
broker API versions rc0, exactly endpoints101/102/103:29094 with IDs1/2/3,
headers omit isFenced. One earlier ad-hoc broker query returned rc1;
subsequent bounded query succeeded. Existing4.3.1 Kafka/Registry services
and /opt/kafka pointers remain intact on all3. No data repair or format retry.

Shared Verify now parses only the CurrentVoters JSON line (integer IDs or
modern objects) and accepts successful legacy broker API headers without the
new isFenced field. Explicit modern isFenced:true still fails. Exact expected
membership/endpoints/count and actual CLI success remain mandatory.
RED OS102 current production source: native Ansible/TLS/API health suite12 PASS
(includes Kafka3.8 output and explicit fenced rejection); diagnostic/parser5 PASS.
Actual updated-bundle Verify via React/Wails remains pending.

### Final real Confluent7.8 static acceptance (2026-11-01)

Approved DEV payload: official
https://packages.confluent.io/archive/7.8/confluent-community-7.8.0.tar.gz
and matching official .sha256.txt;367139824 bytes,
SHA256 e8b8688c7eaa1fc1771b31ef54586a9367d9baa01a4ce00192a1805c3e2d9443.
Build host RED OS102; source transferred by qa-sync; standard bundle validator
and publisher used before real UI rebind/preparation. Source originals and
existing distributed bundles were not patched.

Updated bundle c97e77d7f9d2336a83fd588f790fa737759c2a4a56157d4cce4216a41b051a4f,
production source120c739c. Project project-684405e9a2769a67, saved revision
c694b0838ebbed088e40ea14146a80622217dfa99c35d11a77bad8bcf4ec8c9b.
Actual React mode-change callback selected supported INFRASTRUCTURE_VERIFY_ONLY;
actual React fresh-plan/acknowledge/Approve/Start handlers called real Wails Go
methods. No production bypass or test-only start path was added. Before Start,
guard asserted only SERVICE_VERIFY/qa78-static on node1,node2,node3, no Apply/PKI.
Harness originally checked every checkbox and unintentionally selected Full;
this was corrected to .acknowledgement inputs before any Start. The accidental
Full review plan was never started.

Plan plan-2097d7eb68e863b410a4be4d;
run installer-4502e578ce29ac6bffa91f8df73df9d7 SUCCEEDED.
Authoritative remote public events journal:346 unique sequences1..346/no gaps,
FAILED0/CHANGED0. Kafka quorum, exact broker endpoints/membership, TLS and all3
Schema Registry APIs passed real Verify. All3 test Kafka7.8 and Registry units
active after completion; node.id1/2/3 and the same explicit static voter list
confirmed on101/102/103. Existing Kafka4.3.1/Registry services and /opt/kafka
pointers were preserved. No project data deleted or reformatted after install.

This is successful real Apply followed by corrected separate Verify, not a
claim that the earlier combined run succeeded. The combined run FAILED in
Verify as recorded above. No second full Apply was executed. Focused tests:
storage8 (including actual7.8 binary), health12, diagnostics/parser5 PASS.

Nonvisual React/Wails integration PASS. Terminal Go observation was asserted;
the immediate UI screenshot still showed pre-terminal progress, and replay
subscription captured only144/346 events. Full counts above come from the
authoritative remote public journal. Complete terminal-screen visual acceptance
is not claimed. Known Wails ipc.js runtime-ready/null-nodes development warnings
were excluded by their exact existing stack signature; no other React errors
were observed. Owned Wails/Vite processes stopped after terminal completion.
All temporary remote source/build workspaces cleaned with qa-sync; QA services
and required runtime identities retained, secret values never logged or committed.
