# Architecture owner decisions and deferred questions

Decision index, not a milestone ledger. Initial decisions below link to ADRs;
later ADRs may refine their scope. Apply the current boundaries in [AGENTS](../AGENTS.md)
and current authorization in [CURRENT_STATE](../CURRENT_STATE.md). The complete
[original text](history/owner-decisions-20261012.md) is preserved as history.

## Resolved owner decisions

### OQ-001: First production service

Decision: [ADR-011: Kafka KRaft is the first production service](architecture-decisions.md#adr-011-kafka-kraft-is-the-first-production-service).

### OQ-002: Standalone interface

Decision: [ADR-012: Standard Ansible is the standalone interface](architecture-decisions.md#adr-012-standard-ansible-is-the-standalone-interface).

### OQ-003: Initial production execution environment

Decision: [ADR-014: Execution Node is a selectable logical role](architecture-decisions.md#adr-014-execution-node-is-a-selectable-logical-role).

### OQ-004: Automatic placement

Decision: [ADR-013: Automatic placement](architecture-decisions.md#adr-013-automatic-placement).

### OQ-006: YAML preservation

Decision: [ADR-018: Semantic YAML round trips](architecture-decisions.md#adr-018-semantic-yaml-round-trips).

### OQ-007: Repository packaging

Decision: [ADR-019: One boundary-enforced monorepo](architecture-decisions.md#adr-019-one-boundary-enforced-monorepo).

## Deferred question from the initial Core scope

### OQ-005: Signature technology

Status: DEFERRED; no owner input required now.

Bundle and signature contracts remain extensible. No concrete signature technology is selected during the initial Core milestones.

This deferral belongs to the initial Core milestones named above; it does not
claim that later trust/bundle decisions are still pending. See the later
[ADR-021 bundle boundary](architecture-decisions.md#adr-021-pre-core-bootstrap-uses-a-verified-offline-runtime-bundle)
and [runtime bundle procedure](agent-procedures/runtime-bundle.md).

## Remaining decisions requiring owner input

Before later milestones, owner input will be requested only if implementation evidence exposes a product-policy choice, such as reducing the agreed Kafka scope or choosing a specific trust/signature technology. Technical details such as exact schema layout, Ansible collection structure and supported compatibility entries are resolved through milestone design and integration evidence rather than assumed owner policy.
