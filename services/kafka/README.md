# Kafka service package

This package implements SERVICE-01A through SERVICE-01D: Kafka 4.3.1 combined
or split broker/controller members on explicitly selected physical hosts.
SERVICE-01B also supports multiple logical members on one physical Ansible
host. The role is standalone and uses only an approved local/offline artifact
supplied by the caller.

Application library resource `kafka.topic` is supported by capability
`service.kafka.topic`. Use the existing library provider stages or invoke
`kafka_kraft` with `tasks_from: application_topics`,
`platform_kafka_application_job` (resolved candidates/topics) and
`platform_kafka_application_phase: preflight|apply|verify`.
The role consumes Core's resolved partition/RF/config values; it never calculates
them from transient live broker availability. `platform_kafka_application_timeout_ms`
defaults to 30000. Existing install-directory and startup-readiness variables apply.
Only missing managed topics are created; matching topics are reused and drift
fails without modification. No application subscription or ACL is implied.
See the [portable topic contract](../../docs/project-contract.md#kafka-topic-resources).

The delivery slices are:

- SERVICE-01A: `kraft-standalone`, production single-node KRaft (implemented);
- SERVICE-01B: `kraft-distributed`, explicit controller/broker placements with
  per-member config, storage and systemd instances;
- SERVICE-01C: the same contract across three physical hosts with dynamic
  KRaft bootstrap, stable directory IDs and host-local mutation.
- SERVICE-01D: split controller and broker members, including two logical
  members on each physical host.

The role remains callable through ordinary inventory variables without Go, the
Installer, or a custom launcher. Kafka-specific playbooks are under this
service package, not under `ansible-core`.

`playbooks/reset_kafka_host.yml` is a separately guarded destructive QA/host
reset. It stops all Kafka units and JVMs on explicitly targeted hosts and
removes installed Kafka runtime, state and unit files. It is not normal apply
or desired-state configuration, and requires the exact runtime acknowledgement
`RESET_ALL_KAFKA_RUNTIME_ON_TARGET_HOSTS`. The approved controller-side offline
payload and execution identity are outside its reset paths.

## PEM TLS material

Kafka and its broker-bound Schema Registry use `platform_kafka_store_type: PEM`
by default. Existing exact PKI-01 plans supply PKCS#8 `private-key.pem`,
`certificate.pem` and `ca-chain.pem`; the role derives a protected `identity.pem`
inside the service-owned PKI directory. The directory is0700 and identity0600,
owned by the corresponding service. The private key is unencrypted and remains
secret material. Properties contain paths, not private key contents or PKCS12
passwords. CA/hostname checks and certificate identities/ACLs remain in force.

Registry continues to use its configured SSL Kafka listener; its HTTPS and
inter-instance TLS also use PEM. Library topic/account hooks and SCRAM bootstrap
create PEM bundles only in invocation-private directories and always remove them;
authoritative PKI output is never changed by these hooks.

Explicit `platform_kafka_store_type: PKCS12` retains the previous format and
runtime store-password input. There is no automatic fallback. Verify does not
migrate an installed PKCS12 service or create missing PEM files: retain the
explicit old format or authorize a separate Apply transition. Old files are not
silently deleted. The shared PKI pipeline and Java application PKCS12 delivery
are unchanged, so they can still require their existing runtime store password.

See [PEM implementation/isolated QA](../../docs/work/application-libraries/kafka-pem-plan.md).
