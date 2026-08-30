# CORE-03 — Deterministic Service Configuration Resolution

## Boundary

CORE-03 produces a derived, read-only logical configuration projection:

```text
role defaults + portable inventory/group_vars + ResolvedTopology identity
    -> ResolvedServiceConfiguration
```

The portable project remains the desired-state source. Core does not create a
second persistent service configuration, generated `group_vars`, runtime role
variables, or Ansible files.

## Sources

- Role defaults in `roles/<service>/defaults/main.yml` are the canonical
  defaults for the standalone role contract.
- Deployment-level `serviceDeployments[*].configuration` in portable
  `group_vars` is the explicit logical override.
- `host_vars` remain a physical-host context and `members[*].configuration`
  is resolved by CORE-04 as a distinct logical-member scope.
- `ResolvedTopology` contributes only deployment identity, service type,
  definition version and mode. Host placement does not affect the
  configuration fingerprint.

CORE-03 does not evaluate Jinja, Ansible precedence, facts or runtime values.
Literal role defaults may be materialized. Non-literal defaults are reported
as `DEFERRED` with reason `NON_LITERAL_ROLE_DEFAULT`. Scoped inheritance and
the restricted exact-reference model are defined by CORE-04.

## Package mapping

Each service package may declare versioned `configurationMapping` metadata:

```yaml
configurationMapping:
  clientPort: {roleVariable: platform_kafka_client_port}
```

The mapping is a direct logical-property-to-role-variable association. It has
no expressions, transforms, conditionals or Jinja. Generic Core never guesses
names. The role remains independently callable with ordinary Ansible
variables and does not depend on Core or Installer.

## Projection and fingerprint

`ResolvedServiceConfiguration` contains effective logical values, resolved or
deferred state, service identity, member variable contexts, relevant input
digests and findings. It does not contain role-variable dictionaries,
endpoints, certificates, secrets, artifacts or generated files. Host identity
is context metadata only; host variables never enter member precedence.

The fingerprint includes canonical service identity/mode, effective logical
configuration, service-definition/schema/default/mapping digests and excludes
actual placement. A placement change changes `topologyFingerprint`, but does
not change `configurationFingerprint` when logical configuration is unchanged.
