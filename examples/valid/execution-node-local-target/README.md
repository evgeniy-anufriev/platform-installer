# EXEC-01 local target execution profile

This fixture models a supported execution topology in which `node1` is both
the Linux Ansible Execution Node and a service target. `node2` and `node3` are
remote targets. The inventory uses standard Ansible transport: local for the
self-target and SSH for remote targets. Bootstrap credentials and the private
key are runtime inputs and are intentionally absent from this fixture.
