# Kafka service package

This package implements SERVICE-01A: one Kafka 4.3.1 combined broker/controller
instance on one explicitly selected physical host. The role is standalone and
uses only an approved local/offline artifact supplied by the caller.

The delivery slices are:

- SERVICE-01A: `kraft-standalone`, production single-node KRaft (implemented);
- SERVICE-01B: `kraft-distributed`, explicit controller/broker placements.

The role remains callable through ordinary inventory variables without Go, the
Installer, or a custom launcher. Kafka-specific playbooks are under this
service package, not under `ansible-core`.
