# Kafka service package

This package implements SERVICE-01A, SERVICE-01B and SERVICE-01C: Kafka 4.3.1 combined
broker/controller members on explicitly selected physical hosts. SERVICE-01B
also supports multiple logical members on one physical Ansible host. The role
is standalone and uses only an approved local/offline artifact supplied by the
caller.

The delivery slices are:

- SERVICE-01A: `kraft-standalone`, production single-node KRaft (implemented);
- SERVICE-01B: `kraft-distributed`, explicit controller/broker placements with
  per-member config, storage and systemd instances;
- SERVICE-01C: the same contract across three physical hosts with dynamic
  KRaft bootstrap, stable directory IDs and host-local mutation.

The role remains callable through ordinary inventory variables without Go, the
Installer, or a custom launcher. Kafka-specific playbooks are under this
service package, not under `ansible-core`.
