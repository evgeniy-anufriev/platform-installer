# Architecture decisions

## ADR-001: V2 is a separate repository

Status: Accepted.

V2 is developed in `platform-installer-v2`. V1 remains an operational reference and is not used as a source dependency.

Reason: the new contract order must not be constrained by V1 persistence, UI or execution models.

## ADR-002: Ansible Core precedes backend and UI

Status: Accepted.

The first executable product is standalone Ansible Core. Go backend work starts only after one production service proves the lifecycle and project contract.

## ADR-003: Portable project is the canonical desired state

Status: Accepted.

Backend databases and frontend stores are projections/caches. They cannot introduce desired-state concepts absent from the portable contract.

## ADR-004: Topology is explicit and first-class

Status: Accepted.

Service deployment, mode, members, roles, placements, dependencies and endpoint bindings are explicit project entities. Inventory is derived.

## ADR-005: Service catalog belongs to versioned service packages

Status: Accepted.

React may render and enhance the catalog but does not manually redefine supported service types, modes, fields or constraints.

## ADR-006: Roles remain conventionally usable

Status: Accepted.

Roles accept documented normal Ansible variables. The project compiler is one producer of those variables, not a mandatory Installer-specific runtime inside every role.

## ADR-007: Derived state is immutable and disposable

Status: Accepted.

Facts, plans, inventory, resolved topology and results are fingerprinted outputs. They are never silently merged back into desired state.

## ADR-008: Secrets are references in desired state

Status: Accepted.

Plaintext secret values exist only in the execution boundary and are never included in project files, plans, events or ordinary diagnostics.

## ADR-009: Execution mechanism is replaceable

Status: Accepted.

Dedicated Linux node, container, WSL2 development and future mechanisms implement the same Core invocation contract. None appear in topology or service domain models.

## ADR-010: Compatibility is evidence-backed data

Status: Accepted.

Certified OS/runtime/service combinations are populated by integration tests. Architecture documents do not invent supported RED OS or ALT Linux versions.

## ADR-011: First production service is a contract probe

Status: Proposed.

The first service must exercise packages, configuration, systemd, topology, secrets, endpoints, TLS, verification, offline artifacts and idempotency. PostgreSQL is a strong candidate, but selection requires an explicit scope decision before implementation.

## ADR-012: Standalone launcher implementation technology

Status: Deferred.

The behavioral CLI contract is defined first. Whether the launcher is Python, an Ansible plugin/collection command or a thin packaged executable will be decided during CORE-01 using offline distribution and maintainability evidence.

## ADR-013: Automatic placement

Status: Deferred.

Explicit placement is supported first. Automatic placement requires a deterministic algorithm, explanation contract and independent tests before becoming part of stable V2.

## ADR-014: Production execution packaging

Status: Deferred.

The initial production adapter is chosen after standalone Core prerequisites are measured. WSL2 remains development-only unless explicitly selected by deployment policy.

## ADR-015: Project mode and direct-role mode coexist

Status: Accepted.

The portable project compiler provides the platform workflow, while every production role remains callable with manual inventory and ordinary role variables. This prevents the service automation from becoming dependent on the project editor or compiler.

## ADR-016: Project files, not SQLite, own desired state

Status: Accepted.

The future backend may index and revision projects in SQLite, but the managed project file remains authoritative. SQLite owns discovered, execution, audit and local-environment state.

## ADR-017: Certificate profile and scope are distinct

Status: Accepted.

A profile defines issuance, key and SAN policy. A scope explicitly defines one aggregation boundary and its topology/endpoint sources. Certificates are never implicitly created per service member.
