# Historical documentation checkpoints

Extracted on 2026-10-12 from the original milestone documents. Recorded statuses,
versions, review verdicts and test outcomes describe their source scope and dates.
They do not override [CURRENT_STATE](../../../../CURRENT_STATE.md), authorize new
work or prove later acceptance. Requirements and planned QA remain in the source
documents. A moved evidence section retains its original wording and title.

## net-04-1.md

Source document: [net-04-1.md](../net-04-1.md).

<a id="net-04-1-checkpoint-001"></a>

Three-node RED OS acceptance proved native candidate and active barriers,
candidate-to-active SHA-256 equality, and clean verify/repeat apply. Stopping
HAProxy on the semantic VIP owner made its helper fail and the instance enter
FAULT; all configured VIPs migrated together to one healthy backup while the
deployment endpoint remained available. Restoring HAProxy returned the former
owner to BACKUP without failback. The same HAProxy failure on a non-owner made
only that backup FAULT and did not move the VIP. Final Keepalived and HAProxy
verify, plus repeat apply, returned `changed=0 failed=0`.



## net-03.md

Source document: [net-03.md](../net-03.md).

<a id="net-03-checkpoint-001"></a>

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



## net-03-1.md

Source document: [net-03-1.md](../net-03-1.md).

<a id="net-03-1-checkpoint-001"></a>

## Acceptance

All three RED OS nodes selected the `systemd-resolved` adapter.  The accepted
safe `resolv.conf` stub link remained unchanged.  Each node received the same
derived primary-plus-secondary DNS list and `~scada.local` route domain.
Normal system resolver/NSS queries passed for a project host, endpoint record
and wildcard record, while `example.com` continued through the pre-existing
default resolver path.

This is the historical NET-03.1 acceptance result. During SI11 on 2026-10-08,
DNS client Verify ran before the endpoint source hook and failed on an
unpublished endpoint record. The role now checks only its project host record;
the revised full-service flow still requires a real UI repeat.

Separate verify and repeat apply returned `changed=0 failed=0` on node1,
node2 and node3.  With the BIND primary stopped, and then the primary plus one
secondary stopped, all clients continued resolving host, endpoint and fresh
wildcard names through the normal system resolver.  Restoring the BIND
services required no client change; post-recovery verify and repeat apply were
again clean.

The NetworkManager fallback has focused contract coverage.  Runtime QA for it
is deliberately deferred until a host without a `systemd-resolved` unit is
available; the resolved-enabled three-node baseline is never modified merely
to force that branch.




## net-02.md

Source document: [net-02.md](../net-02.md).

<a id="net-02-checkpoint-001"></a>

## Acceptance

Three RED OS nodes were accepted with one VRID and two virtual addresses on a
common interface. Native candidate validation passed on all nodes. Initial and
repeat apply, separate verify, post-rejoin verify and post-rejoin repeat all
returned `changed=0 failed=0`. Both addresses moved together through automatic
failover; restored higher-priority nodes rejoined without failback. An
additional bounded sequence proved the third participant could become owner.
