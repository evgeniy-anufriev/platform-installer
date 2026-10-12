# SI08-E follower unseal correction

Document scope: the original milestone contract/design. Historical status, review
and QA checkpoints are collected separately; current status and authorization
are recorded only in [CURRENT_STATE](../../../CURRENT_STATE.md).

Owner authorized the narrow correction on 2026-09-28. The follower include
previously passed `vault_member: "{{ vault_member }}"`, shadowing the outer
loop variable with a recursive template. Remove only this redundant override;
the existing `vault_member` loop remains the authority for the current follower.
No protocol, TLS, bootstrap custody, reset or standalone behavior was redesigned.

## Regression evidence

See [historical checkpoint](evidence/documentation-checkpoints-20261012.md#service-install-08e-follower-unseal-fix-checkpoint-001). Current status: [CURRENT_STATE](../../../CURRENT_STATE.md).

## Real HA 3/1 recovery

See [historical checkpoint](evidence/documentation-checkpoints-20261012.md#service-install-08e-follower-unseal-fix-checkpoint-002). Current status: [CURRENT_STATE](../../../CURRENT_STATE.md).

## Remaining acceptance

Strict repeat changed=0, HA 3/3, failover/restart and final SI08-E gates remain
pending. Reversible current-boot swap masks remain on QA hosts; reboot removes
them. Do not interpret this correction as overall SI08-E DONE.
