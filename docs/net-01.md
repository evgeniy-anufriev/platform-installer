# NET-01: Endpoint Groups and Resolved Service Endpoints

NET-01 introduces one canonical client-facing address namespace per endpoint
group. It is a pure Core resolution and PKI identity milestone; it does not
install, bind, publish or fail over any network service.

## Desired state

`endpointGroups.<id>.address` owns exactly one:

- lowercase DNS suffix (`domain`);
- wildcard intent (`wildcard`);
- IPv4 VIP (`vip`).

An endpoint-capable deployment assigns that group directly:

```yaml
platform_desired_state:
  endpointGroups:
    asutp:
      address:
        domain: asutp.scada.local
        wildcard: true
        vip: 192.168.6.112
  serviceDeployments:
    postgres-main:
      serviceType: postgresql
      definitionVersion: "1.0.0-alpha.1"
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
  -> 192.168.6.112
```

The projection is deterministic, has a fingerprint, performs no target
contact, and is never written to `platform_generated_state`. PostgreSQL is the
first endpoint-capable package. Kafka deliberately has no generic NET-01
endpoint: its named and advertised listeners remain Kafka-package semantics.

`endpoint: {}` in a service manifest is an explicit package opt-in. It has no
transport interpretation.

## PKI

The PKI resolver consumes the resolved projection read-only. Concrete FQDN,
optional wildcard DNS name and VIP are added only when the selected existing
`sanPolicy` permits the corresponding type. A changed request fingerprint uses
the established `CERTIFICATE_REISSUE_REQUIRED` lifecycle; NET-01 never rotates
or materializes certificates on its own.

## Provider boundaries

NET-02 Keepalived references an endpoint group and derives its VIP; it must
not own a second VIP field. NET-03 HAProxy derives a future bind address from
the group. Transport ports, frontend/backend routing, PostgreSQL writable
member selection and all HAProxy checks are deferred to NET-03. NET-04 BIND
will publish the resolved FQDN/VIP and consume wildcard intent; it will not
become an endpoint owner.

## Explicitly deferred

- Keepalived, VRRP and MASTER/BACKUP state;
- HAProxy, client ports, frontend/backend configuration and routing;
- PostgreSQL primary discovery;
- BIND, zones, records and DNS TTL;
- multiple VIPs, IPv6 runtime acceptance, aliases and custom FQDNs;
- UI implementation.
