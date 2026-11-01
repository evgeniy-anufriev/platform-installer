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
