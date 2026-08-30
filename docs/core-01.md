# CORE-01 — Contract and validation foundation

## Scope

CORE-01 establishes a standard Ansible project contract and a read-only
validation vertical slice. It does not install Kafka, contact target hosts or
implement `plan`, `apply` or `verify` mutations.

## Physical portable project

```text
project/
  project.yml                       identity and catalog/artifact locks
  inventory/hosts.yml              localhost controller + platform_targets
  inventory/group_vars/all/platform.yml  platform_project desired topology
  inventory/host_vars/<host>.yml         platform_host desired host values
```

`project.yml`, `platform_project`, inventory host IDs and `platform_host`
values form one logical project. The validation fingerprint covers their safe
normalized values. It never includes Ansible connection variables or runtime
credentials.

## Implemented contracts

- project manifest, desired state, desired host variables and assembled input;
- derived service catalog;
- service package manifest;
- finding and validation result;
- plan, event and execution result alpha contracts.

Service manifests are authored sources. A catalog is a derived, digest-pinned
artifact and must not become a second manually maintained service definition.

## Standard Ansible validation

The public interface is standard `ansible-playbook`:

```bash
cd ansible-core
ansible-playbook -i examples/valid/inventory/hosts.yml playbooks/validate.yml
```

The play runs only on controller `localhost`, gathers no facts and selects only
the safe `platform_host` value for every target. Target connection variables
are not passed to the validator. Validation writes an atomic structured result
under `.runtime/` and returns non-zero when the result is `BLOCKED`.

The current semantic validator covers:

- project identity and contract version;
- catalog/artifact lock identity and digests;
- catalog/service version and digest matching;
- recomputation of canonical catalog and embedded service-definition digests;
- known service types and modes;
- explicit member-to-inventory-host references;
- supported member roles;
- mode member-count and role-cardinality constraints;
- distinct-host constraints;
- rejection of plaintext secret-like fields in portable topology and host
  desired values, while runtime secret references remain allowed;
- deterministic fingerprinting;
- structured safe findings.

## Fixtures

Contract fixtures cover:

- empty topology;
- Kafka KRaft standalone and distributed;
- PostgreSQL standalone and Patroni;
- two independent pg_auto_failover deployments;
- missing host reference;
- unknown mode;
- invalid distinct-host placement.

PostgreSQL and etcd definitions in the fixture catalog are conformance data,
not implemented production services.

## Kafka role status

The package contains the independently usable collection namespace and
`platform.kafka.kafka_kraft` role skeleton. It deliberately has no
`tasks/main.yml`: production work starts in SERVICE-01A only after Core
contracts are stable.

## Validation evidence

The read-only Core smoke was executed on RED OS as an Ansible controller:

- Python 3.11.15;
- ansible-core 2.18.15;
- contract schema-document tests: 4/4 passed;
- Core unit and catalog-consistency tests: 20/20 passed;
- derived catalog reproducibility check passed;
- syntax check passed;
- all six valid root fixtures passed with `changed=0`;
- all three invalid fixtures returned non-zero with the exact expected
  structured finding code and field.

No target host was contacted or modified. Temporary controller files were
removed after the test.

## Remaining CORE-01 gate

The target controller does not contain the Python `jsonschema` package. The
repository therefore does not claim full JSON Schema Draft 2020-12 runtime
enforcement. Current validation is a dependency-free semantic subset, while
the published schemas are syntax/reference checked.

Before CORE-01 is marked complete, choose and prove an offline-compatible
schema conformance mechanism, run every valid/invalid repository fixture
through it, and record the exact dependency/bundle contract. This is a
technical closure task and currently requires no product-owner decision.
