# Kafka service package

This package implements SERVICE-01A through SERVICE-01D: Kafka 4.3.1 combined
or split broker/controller members on explicitly selected physical hosts.
SERVICE-01B also supports multiple logical members on one physical Ansible
host. The role is standalone and uses only an approved local/offline artifact
supplied by the caller.

The delivery slices are:

- SERVICE-01A: `kraft-standalone`, production single-node KRaft (implemented);
- SERVICE-01B: `kraft-distributed`, explicit controller/broker placements with
  per-member config, storage and systemd instances;
- SERVICE-01C: the same contract across three physical hosts with dynamic
  KRaft bootstrap, stable directory IDs and host-local mutation.
- SERVICE-01D: split controller and broker members, including two logical
  members on each physical host.

The role remains callable through ordinary inventory variables without Go, the
Installer, or a custom launcher. Kafka-specific playbooks are under this
service package, not under `ansible-core`.

`playbooks/reset_kafka_host.yml` is a separately guarded destructive QA/host
reset. It stops all Kafka units and JVMs on explicitly targeted hosts and
removes installed Kafka runtime, state and unit files. It is not normal apply
or desired-state configuration, and requires the exact runtime acknowledgement
`RESET_ALL_KAFKA_RUNTIME_ON_TARGET_HOSTS`. The approved controller-side offline
payload and execution identity are outside its reset paths.
