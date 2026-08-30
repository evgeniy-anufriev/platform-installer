# Kafka service package

This CORE-01 package declares the future Kafka KRaft capability and the role
layout only. It contains no installation tasks, so it is not a SERVICE-01A
implementation.

The delivery slices are:

- SERVICE-01A: `kraft-standalone`, production single-node KRaft;
- SERVICE-01B: `kraft-distributed`, explicit controller/broker placements.

The role will remain callable through ordinary inventory variables without Go,
the Installer, or a custom launcher.
