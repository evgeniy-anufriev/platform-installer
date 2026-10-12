# NET-04: HAProxy HTTPS routing

Status: DONE.

NET-04 installs a host-scoped HAProxy deployment, terminates HTTPS on the
fixed `public` frontend at `*:443`, and derives deployment and explicitly
selected host routes from the existing endpoint, inventory and PKI
projections. Keepalived health tracking is implemented separately by
[NET-04.1](net-04-1.md).

## Integration ownership

HAProxy integration belongs to the relationship:

```text
target service deployment -> HAProxy deployment
```

The canonical declaration is stored next to the target service deployment so
that `group_vars` remains service-oriented and the HAProxy deployment does not
become one large registry of every project backend. HAProxy integration is not
a target service's native application configuration.

```yaml
platform_desired_state:
  endpointGroups:
    asutp:
      address:
        domain: asutp.scada.local
        wildcard: true

  serviceDeployments:
    haproxy:
      serviceType: haproxy
      mode: https-host-routing
      endpointGroup: asutp
      configuration:
        tlsProfile: platform-tls

    postgres-main:
      serviceType: postgresql
      mode: standalone
      endpointGroup: asutp
      configuration:
        # PostgreSQL-native settings only.
        port: 5432
        tlsProfile: platform-tls
      haproxy:
        deploymentRef: haproxy
        backend:
          balance: leastconn
          check: true
          fall: 3
          rise: 2
          ssl: true
          sslVerify: required

    vault-main:
      serviceType: vault
      mode: standalone
      endpointGroup: asutp
      configuration: {}
      haproxy:
        deploymentRef: haproxy
        backend:
          balance: roundrobin
          check: true
          fall: 3
          rise: 2
          ssl: true
          sslVerify: required
```

The following shape is invalid because it mixes HAProxy relationship policy
with PostgreSQL-native settings:

```yaml
postgres-main:
  configuration:
    haproxy: {}
```

`haproxy.deploymentRef` is the explicit logical link to the HAProxy deployment
that publishes the target. NET-04 permits zero or one such relation per target
deployment. Multiple HAProxy publishers, lists and maps of integrations are
deferred.

## Endpoint scopes

Assigning `endpointGroup` to an endpoint-capable service deployment continues
to create one deployment endpoint:

```text
haproxy.asutp.scada.local -> haproxy-asutp -> all healthy HAProxy hosts
```

A physical placement may additionally opt into a host endpoint:

```yaml
node1:
  platform_deployments:
    haproxy: {hostEndpoint: true}
```

This derives:

```text
haproxy-node1.asutp.scada.local -> haproxy-node1-asutp -> node1 only
```

`hostEndpoint` is a boolean inventory placement property. Absence or `false`
does not create a host endpoint. The deployment endpoint remains present. The
FQDN is derived from deployment id, host id and endpoint-group domain; it is
not authored separately. Existing wildcard DNS directs both endpoint scopes
to the Keepalived VIP. No `endpointBindings` entity is introduced.

Core validates that the target supports endpoints, both sides reference the
same endpoint group, host endpoint placements participate in the deployment,
the endpoint group permits wildcard names, and all resulting names are valid
and collision-free.

## Relationship validation

Target-free validation requires:

- `deploymentRef` exists;
- the referenced deployment has `serviceType: haproxy`;
- the target service package is endpoint-capable;
- the target deployment has `endpointGroup`;
- the HAProxy deployment has `endpointGroup`;
- both endpoint-group references are equal in NET-04;
- no more than one HAProxy relation is declared for a target deployment.

Representative blocking findings are
`HAPROXY_DEPLOYMENT_NOT_FOUND`, `HAPROXY_DEPLOYMENT_TYPE_INVALID`,
`HAPROXY_TARGET_ENDPOINT_UNSUPPORTED`, `HAPROXY_ENDPOINT_GROUP_REQUIRED`,
`HAPROXY_ENDPOINT_GROUP_MISMATCH`, and
`HAPROXY_INTEGRATION_CARDINALITY_UNSUPPORTED`.

A service deployment without a `haproxy` section produces no HAProxy backend.
Core never infers publication merely because service and HAProxy deployments
share an endpoint group.

## BackendSettings

`BackendSettings` is one reusable typed HAProxy-integration contract:

```yaml
balance: roundrobin  # roundrobin | leastconn | source
check: true
fall: 3
rise: 2
ssl: true
sslVerify: required  # required | none
```

Backend settings are declared in the target service's
`serviceDeployment.haproxy.backend`. HAProxy role defaults contain only
HAProxy/package-owned defaults (for example, the local stats backend), not
per-service backend defaults. The resolver receives the authored backend
object explicitly and does not infer service-specific defaults.

Effective precedence is:

```text
serviceDeployment.haproxy.backend
-> future host/member override, only when explicitly supported
```

Each authored layer is structurally validated as a partial object. Core then
merges the layers, performs dependent-field normalization, and validates the
effective object:

```text
if ssl == false  -> remove sslVerify
if check == false -> remove fall and rise
```

For example, defaults `{ssl: true, sslVerify: required}` plus override
`{ssl: false}` produce exactly `{ssl: false}`. Defaults
`{check: true, fall: 3, rise: 2}` plus override `{check: false}` produce
exactly `{check: false}`. Cross-field validation applies to the normalized
effective object, not to an incomplete user override. Runtime projection,
fingerprints, rendering, verification and diagnostics all consume the same
normalized object.

When effective `ssl` is true, `sslVerify` is required. `required` also requires
a resolved CA file; `none` keeps encryption but disables peer-certificate
verification. When effective `check` is true, `fall` and `rise` are required
and bounded. Unknown properties and raw HAProxy directives remain forbidden.

## ResolvedHAProxyBackends

Core discovers relations from desired state, not from Jinja:

```text
target service deployment
  + serviceDeployment.haproxy.deploymentRef
  + serviceDeployment.haproxy.backend
  + target topology and listener projection
  + resolved deployment/host endpoints
        -> ResolvedHAProxyBackend
```

For each HAProxy deployment Core selects only service deployments whose
`haproxy.deploymentRef` points to it. The read-only runtime projection contains
normalized settings, endpoint identity, target addresses and ports, server
names, backend names, TLS/CA paths and a deterministic fingerprint. It is not
written to generated state.

The HAProxy role consumes only this projection. Jinja templates do not discover
relationships, resolve references, merge settings or implement fallback
semantics.

## Package-owned statistics

HAProxy statistics are internal package-owned backends. The HAProxy deployment
must not declare a self-reference such as:

```yaml
haproxy:
  deploymentRef: haproxy
```

The package creates the pooled `haproxy-<endpointGroup>` backend and opted-in
`haproxy-<host>-<endpointGroup>` backends as product invariants. Their settings
pass through the same BackendSettings normalizer and serializer used for
resolved external relations, but no canonical desired-state relation is
created.

The fixed public endpoint is `/stats`. Each concrete backend contains only its
resolved server or, for the deployment endpoint, all healthy HAProxy hosts. The
internal stats listener defaults to port `8404`, uses the effective backend TLS
policy and permits only HAProxy participant addresses. `stats admin` is not
enabled.

## Host normalization and routing

The `public` frontend is a product invariant and binds `*:443` with the
PKI-projected certificate. It normalizes `Host` once before routing:

```haproxy
http-request set-var(txn.route_host) req.hdr(host),lower,regsub(:[0-9]+$,)
acl asutp var(txn.route_host) -m end -i .asutp.scada.local
use_backend %[var(txn.route_host),field(1,'.')]-asutp if asutp
```

The same `txn.route_host` drives ACL matching and backend-name derivation.
Requests with or without `:443` therefore select the same backend. Missing,
foreign or unresolved dynamic backend names receive `503`.

## Configuration ownership and lifecycle

The package installs HAProxy from configured RED OS repositories. The initial
package `global` and `defaults` values become structured role defaults and are
rendered dynamically by `haproxy.cfg.j2`; package example frontend/backend
sections are not retained. Operators may override documented role defaults.

All Platform-owned files under `/etc/haproxy/conf.d` are Jinja-rendered from
the runtime projection. Third-party files are not deleted. Unknown pre-existing
non-example sections block first ownership transition instead of being silently
discarded.

The apply lifecycle is:

```text
target-free validation
-> endpoint, relation and BackendSettings resolution
-> PKI resolve/materialize/deploy
-> package installation and complete candidate rendering
-> native haproxy -c on every participant
-> cluster validation barrier
-> atomic activation and start/reload
-> read-only verification
```

Any candidate failure prevents active replacement, start and reload on every
participant. Verify reconstructs the projection independently and performs no
mutation. Unchanged verify and repeat apply must return `changed=0 failed=0`.

## Contract and acceptance coverage

Focused contract tests cover:

- valid `deploymentRef`;
- unknown `deploymentRef`;
- reference to a non-HAProxy deployment;
- endpoint-group mismatch;
- a service without `haproxy` producing no backend;
- zero-or-one integration cardinality;
- explicit resolver defaults plus a partial BackendSettings override;
- `ssl: false` clearing inherited `sslVerify`;
- `check: false` clearing inherited `fall` and `rise`;
- deterministic relation/backend ordering and fingerprinting;
- absence of a canonical backend registry inside the HAProxy deployment;
- deployment and explicit `hostEndpoint: true` endpoint projections;
- Host routing equivalence with and without `:443`;
- unknown Host returning `503`;
- stats remaining package-owned without a self-reference.

Runtime acceptance uses all three RED OS nodes and proves the pooled deployment
stats endpoint, each opted-in host stats endpoint, TLS verification, backend
target identity, one non-VIP-owner backend failure and recovery, separate
verify, repeat apply and post-recovery idempotence. Full Core, NET-01 through
NET-03.1, PKI, PostgreSQL, Kafka, catalog/schema reproducibility, offline and
security gates run before documentation is marked DONE or a commit is created.

## Accepted runtime evidence

The three-node RED OS acceptance completed with Barrier A and Barrier B passing
on every node, with each active graph equal to its candidate graph and native
`haproxy -c` passing. The deployment endpoint and every enabled host endpoint
passed TLS hostname verification and returned the expected stats route. Host
normalization treated `Host` values with and without `:443` identically, while
an unknown Host returned `503`.

Runtime socket counters confirmed that bounded deployment-endpoint requests
used all three healthy HAProxy backend participants. The configured VIP owner
was determined semantically; stopping HAProxy only on a non-owner made only
that host endpoint return `503`, without migrating the VIP or affecting the
pooled and remaining host endpoints. Restoring the service recovered every
endpoint. Separate verify, repeat apply, post-recovery verify and
post-recovery repeat apply all returned `changed=0 failed=0` for localhost and
all three targets.

The deployment-scoped TLS identity covers the deployment, configured host
endpoint names and `*.asutp.scada.local` on every HAProxy participant. The
wildcard SAN was added using the explicit selected PKI reissue lifecycle; it
is never an implicit ordinary NET-04 reconcile.

## Deferred

NET-04 itself does not activate Keepalived `vrrp_script` or `track_script` and
does not introduce multiple HAProxy publishers per target service. Opt-in
HAProxy tracking and owner-failure VIP migration are covered by NET-04.1.
