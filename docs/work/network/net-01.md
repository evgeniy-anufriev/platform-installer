# NET-01: Endpoint Groups and Resolved Service Endpoints

NET-01 introduces one canonical client-facing DNS namespace per endpoint
group. It is a pure Core resolution and PKI identity milestone; it does not
install, bind, publish or fail over any network service.

## Desired state

`endpointGroups.<id>.address` owns exactly one:

- lowercase DNS suffix (`domain`);
- wildcard intent (`wildcard`);

An endpoint-capable deployment assigns that group directly:

```yaml
platform_desired_state:
  endpointGroups:
    asutp:
      address:
        domain: asutp.scada.local
        wildcard: true
  serviceDeployments:
    postgres-main:
      serviceType: postgresql
      mode: standalone
      endpointGroup: asutp
```

There is no `endpointBindings`, alias, listener reference, FQDN override or
published-port field. The deployment identifier must itself be a lowercase DNS
label.

## Resolution

The read-only `ResolvedServiceEndpoints/v1alpha1` projection resolves:

```text
postgres-main + asutp.scada.local
  -> postgres-main.asutp.scada.local
```

The projection is deterministic, has a fingerprint, performs no target
contact, and is never written to `platform_generated_state`. PostgreSQL is the
first endpoint-capable package. Kafka deliberately has no generic NET-01
endpoint: its named and advertised listeners remain Kafka-package semantics.

`endpoint: {}` in a service manifest is an explicit package opt-in. It has no
transport interpretation.

## PKI

The PKI resolver consumes the resolved projection read-only. Concrete FQDN and
optional wildcard DNS name are added only when the selected existing
`sanPolicy` permits the corresponding type. When `includeEndpointVip` is true,
the resolver additionally reads virtual addresses from an endpoint-provider
deployment referencing the same group; the DNS-only endpoint projection never
becomes an address owner. A changed request fingerprint uses
the established `CERTIFICATE_REISSUE_REQUIRED` lifecycle; NET-01 never rotates
or materializes certificates on its own.

## Provider boundaries

NET-02 Keepalived references an endpoint group and owns one VRRP instance with
one or more virtual addresses. EndpointGroup never owns a VIP. NET-03 BIND
publishes the resolved FQDN with provider-owned addresses and consumes
wildcard intent; it does not become an endpoint owner. A future HAProxy
milestone will consume a provider/deployment address rather than derive one
from the group. Transport ports, frontend/backend routing, PostgreSQL writable
member selection and HAProxy checks remain deferred.

## Explicitly deferred

- Keepalived, VRRP and MASTER/BACKUP state;
- HAProxy, client ports, frontend/backend configuration and routing;
- PostgreSQL primary discovery;
- BIND, zones, records and DNS TTL;
- IPv6 runtime acceptance, aliases and custom FQDNs;
- UI implementation.
