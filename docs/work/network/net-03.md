# NET-03: Authoritative BIND DNS

NET-03 provides a three-node authoritative BIND primary-secondary DNS service.
The Core resolver derives canonical project-host, endpoint and wildcard A
records from desired state and host-scoped inventory.  It also derives a
logical zone-content fingerprint.  These projections are read-only; only the
per-deployment DNS fingerprint and serial are machine-owned generated state.

On an unchanged logical zone, the generated serial is reused.  A changed
logical fingerprint increments it exactly once.  The apply playbook
materializes that state once and publishes a runtime projection for every
subsequent role task in the same execution; remote tasks never depend on an
inventory refresh to rediscover newly written state.

Candidate construction and activation are deliberately separate cluster
barriers.  Every participant first assembles and validates its complete
candidate configuration.  The primary also validates its candidate zone.  No
active configuration is installed and no service is started unless all
candidates pass.  Phase B installs the exact validated candidate, validates
the active graph, and only then reloads an active `named` when managed active
artifacts or the served serial require it.  An inactive service is started
only after this active-validation barrier.

The primary owns the managed text zone and retains `allow-update { none; };`.
Secondaries receive their zone through native BIND transfer and do not receive
an Ansible-managed zone-file copy.  Verify is read-only and checks active
configuration, service state, SOA and a project-host record locally.

`configuration.advancedConfig.options.minimal-responses` is the only accepted
NET-03 native option in this slice.  Routing, transport-port selection, DNS
load balancing and HAProxy integration remain outside this milestone.

## Acceptance

Three RED OS nodes passed complete candidate and active barriers, with a
byte-identical candidate/active main configuration on every node.  Native
authoritative responses proved project-host records, endpoint FQDNs and
wildcards on all nodes.  Secondaries held BIND-transferred raw zones with the
same SOA serial as the primary.  Separate verify and repeat apply returned
`changed=0 failed=0`.

A safe logical zone-content change changed the fingerprint and incremented the
serial from 1 to 2 exactly once; both secondaries converged by transfer, and a
further unchanged apply did not increment it.  Stopping only the configured
primary left both secondaries authoritative for host and endpoint records.
Restoring the primary preserved roles; post-recovery verify and repeat apply
again returned `changed=0 failed=0`.  The accepted harmless advanced option
materialized on all nodes without changing the DNS serial and remained
idempotent.
