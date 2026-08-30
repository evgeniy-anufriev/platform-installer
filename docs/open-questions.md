# Open architecture questions

These questions do not block the architecture baseline unless stated otherwise.

## OQ-001: First production service

Status: NEEDS OWNER DECISION before `SERVICE-01`.

Candidates:

- Kafka KRaft: exercises Java, offline artifacts, systemd, TLS, listener identity and distributed quorum; V1 contains an initial contract example.
- PostgreSQL: directly exercises the most important topology examples—standalone, Patroni and pg_auto_failover—but the first production scope is larger if all modes are included.

Recommendation: use Kafka KRaft single-node followed immediately by distributed KRaft as the first Core proof, while keeping PostgreSQL multi-deployment fixtures in the project-contract conformance suite. If PostgreSQL is the commercial priority, restrict the first production slice to standalone before adding HA modes.

## OQ-002: Standalone launcher technology

Status: DEFERRED to `CORE-01` spike.

Compare a Python launcher shipped with the collection, an Ansible-native plugin/command and a small packaged executable. Selection criteria are offline installation, predictable dependencies, Windows independence, version negotiation and maintainability.

## OQ-003: Initial production execution environment

Status: DEFERRED until Core prerequisites are measured.

The project contract is neutral. Initial expectation remains a dedicated Linux execution node; WSL2 is a development adapter. Container/bundled Linux options remain possible.

## OQ-004: Automatic placement

Status: DEFERRED.

V2 first supports explicit placement. Auto-placement requires deterministic scoring, explanation and an operator-accepted project patch; it may never mutate explicit placements silently.

## OQ-005: Signature technology

Status: DEFERRED.

The bundle trust envelope is signature-neutral. Concrete technology and trust-root lifecycle require a separate security decision.

## OQ-006: Canonical YAML preservation

Status: PROPOSED.

Guarantee semantic and extension-preserving round trips, not byte-identical formatting/comments. Confirm before UI import/export implementation.

## OQ-007: Repository packaging

Status: PROPOSED.

Start as one V2 repository with independently bounded `ansible-core`, service packages, contracts, backend and frontend directories. Split service packages or Core into separate repositories only when release cadence or access-control evidence justifies it.
