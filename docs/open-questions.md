# Architecture owner decisions and deferred questions

## Resolved owner decisions

### OQ-001: First production service

Status: RESOLVED.

Kafka KRaft is the first production service, split into two independently gated slices:

- `SERVICE-01A`: standalone/single-node KRaft;
- `SERVICE-01B`: distributed KRaft.

The first slice intentionally excludes the full security/listener feature set. PostgreSQL standalone, Patroni and two independent pg_auto_failover deployments remain project-contract fixtures, not first-service implementation scope.

### OQ-002: Standalone interface

Status: RESOLVED.

The initial canonical interface is standard `ansible-playbook` with normal inventory, `group_vars` and `host_vars`. No proprietary launcher is introduced. A convenience CLI may be proposed later only from demonstrated operational need, and Ansible Core must never depend on it.

### OQ-003: Initial production execution environment

Status: RESOLVED.

Execution Node is a selectable logical role, not a mandatory dedicated host.
`AUTO`, `EXPLICIT_TARGET`, `LOCAL_INSTALLER` and
`EXTERNAL_EXECUTION_HOST` are execution-level choices. A project target may
also be the Execution Node; local transport may then be used for that host.
WSL2 remains a development adapter and service topology remains independent.

### OQ-004: Automatic placement

Status: RESOLVED FOR INITIAL V2.

Initial V2 supports explicit placement only. A future placement engine may produce an explainable proposed project patch, but cannot apply it without operator acceptance.

### OQ-005: Signature technology

Status: DEFERRED; no owner input required now.

Bundle and signature contracts remain extensible. No concrete signature technology is selected during the initial Core milestones.

### OQ-006: YAML preservation

Status: RESOLVED.

Import/export guarantees semantic preservation and preservation of declared unknown extensions. It does not guarantee byte-identical formatting or comments. A complex round-trip YAML AST editor is out of scope until a demonstrated requirement justifies it.

### OQ-007: Repository packaging

Status: RESOLVED.

V2 begins as one monorepo with strict boundaries between Ansible Core, service roles/packages, contracts, Installer backend and frontend. Ansible Core and service roles remain independently testable and usable without Installer.

## Remaining decisions requiring owner input

None currently block `CORE-01` through `CORE-03`.

Before later milestones, owner input will be requested only if implementation evidence exposes a product-policy choice, such as reducing the agreed Kafka scope or choosing a specific trust/signature technology. Technical details such as exact schema layout, Ansible collection structure and supported compatibility entries are resolved through milestone design and integration evidence rather than assumed owner policy.
