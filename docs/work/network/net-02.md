# NET-02: Keepalived / VRRP / Stable VIP Ownership

Document scope: the original milestone contract/design. Historical status, review
and QA checkpoints are collected separately; current status and authorization
are recorded only in [CURRENT_STATE](../../../CURRENT_STATE.md).

Each Keepalived `serviceDeployment` is exactly one unicast VRRP instance. It
owns `endpointGroupRef`, `virtualRouterId` and one-or-more
`virtualAddresses`; all listed addresses have one runtime owner and move
together. The endpoint group supplies DNS namespace only and never duplicates
a VIP.

Participation is host-scoped inventory data: each participating host sets only
`platform_deployments.<deployment>.priority`. There are no logical router
member IDs, roles, member-local interfaces or manually maintained peer lists.
The renderer derives unicast peers from the participating inventory hosts.

NET-02 renders `state BACKUP` and `nopreempt`. MASTER/BACKUP ownership is
observed runtime state. Verify is read-only and blocks when a configured
virtual-address set is split, missing, or has anything other than one complete
owner; active non-owners are the remaining BACKUP participants.

The future HAProxy readiness helper is materialized root-owned with mode 0750,
but NET-02 renders neither `vrrp_script` nor `track_script`. NET-04.1 later
adds explicit opt-in HAProxy-triggered failover behavior.

## Acceptance

See [historical checkpoint](evidence/documentation-additional-checkpoints-20261012.md#net-02-checkpoint-001). Current status: [CURRENT_STATE](../../../CURRENT_STATE.md).
