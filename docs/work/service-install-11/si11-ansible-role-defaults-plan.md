# SI11 — effective service defaults at execution

Status: owner-directed correction before the next SI11 full-plan run.

## Decision and boundary

For every service setting, an absent project override leaves the effective
Ansible variable to the role's `defaults/main.yml` and ordinary inventory
precedence. A saved deployment/member setting or an authored variable document
is an explicit override. UI default labels and target-free Core preview are
read-only projections; they do not become runtime overrides by their presence.
No new public contract, persistence model, or service-specific Go/React rule is
introduced. Direct standalone `ansible-playbook` continues to use manual
inventory, `group_vars`, `host_vars`, and role defaults.

## Narrow correction

1. The existing private Core `roleVariablesByHost` map retains structural mode
   and declared member-list inputs, plus explicit deployment/member/group-vars
   values. It omits a setting whose sole source is `ROLE_DEFAULT`, including an
   exact static reference with `origin: ROLE_DEFAULT`. Core may still show or
   validate that default in a read-only snapshot. Preserve member-specific
   client-port entries without requiring a copied host default port.
2. The existing `runtime_role_variables` adapter transfers only those private
   operation values. It remains the typed transport for explicit managed
   settings; no generic Ansible precedence emulator is added.
3. Kafka's existing project adapter keeps its multi-member-on-one-host
   projection. It assigns `quorumMode` only when explicitly present in
   canonical deployment configuration. The absent value leaves the role's
   `platform_kafka_quorum_mode: dynamic` or an authored inventory value intact;
   the invalid `kraft` fallback is removed. Do not attach the generic member
   list adapter to Kafka or add new settings projection in this correction.
4. Keepalived declares `platform_keepalived_advert_interval: 1` in role defaults.
   Its template uses the explicit canonical `advertInterval` when present and
   otherwise the effective role variable. Manual inventory may therefore
   override the default. Existing BIND `defaultTtl` remains an explicit required
   input; HAProxy and DNS-client retain their existing direct resolution paths.
5. Vault, Redis, and PostgreSQL apply/verify playbooks include the existing
   `runtime_role_variables` role only when the private Installer map is present,
   as Docker and ClickHouse already do. A supplied malformed map still fails
   closed. This restores their standalone playbook route without changing the
   service roles.

## Acceptance

- A default-only Kafka project reaches the role with `dynamic`; explicit
  `static` and authored inventory overrides are honored. Repeat this for Kafka
  3 members on 1 and 3 hosts.
- Generic service private operations do not copy defaults into facts. Explicit
  project, member, and authored variable-document values retain their types,
  host scope, and existing conflict guards.
- Keepalived renders advert interval 1 from role defaults, an authored
  inventory value when supplied, and an explicit project value when supplied.
- Standalone Vault/Redis/PostgreSQL apply and verify work without the private
  Installer map; an invalid supplied map is rejected.
- Run focused RED OS/Core/Ansible checks, then affected full regression,
  reproducibility and `git diff --check`. The subsequent SI11 acceptance still
  requires a new immutable runtime and a real Wails full-plan Start and repeat.

The owner-approved correction is limited to default/override precedence and
the directly affected standalone playbook prerequisites. Existing execution
state, service topology and secret boundaries are unchanged.
