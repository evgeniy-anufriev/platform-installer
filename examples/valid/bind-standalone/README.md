# Standalone BIND primary fixture

This portable Ansible project places one BIND authoritative primary on one
inventory host. Secondary participants are optional; add hosts with
`roles: [secondary]` when zone transfer and notification are needed.
