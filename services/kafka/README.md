# Kafka service package

This package implements SERVICE-01A through SERVICE-01D: Kafka 4.3.1 combined
or split broker/controller members on explicitly selected physical hosts.
SERVICE-01B also supports multiple logical members on one physical Ansible
host. The role is standalone and uses only an approved local/offline artifact
supplied by the caller.

Kafka command names use `platform_kafka_script_extension: ".sh"` by default.
For a distribution with extensionless commands, set
`platform_kafka_script_extension: ""` in inventory `group_vars` or `host_vars`.
The suffix applies to Kafka startup, storage, verification and application
topic/account/ACL commands, including Kafka commands used by Schema Registry.

For a combined Kafka/Schema Registry archive, set these ordinary role variables
in defaults or inventory (the current defaults retain separate distributions):

```yaml
platform_kafka_archive_directory: confluent-7.8.0
platform_kafka_install_directory: /opt/kafka
platform_kafka_script_extension: ""
platform_kafka_schema_registry_use_kafka_distribution: true
platform_kafka_schema_registry_install_directory: /opt/confluent-7.8.0
```

Also set `platform_kafka_version` and `platform_kafka_schema_registry_version`
to the actual component versions of the approved distribution. The archive
release number is not necessarily the embedded Kafka version. Manual inventory
must supply `platform_kafka_artifact_path` and its approved
`platform_kafka_artifact_checksum` (`sha256:...`). Kafka extracts the archive
once under `/opt`; Registry reuses its real directory, launcher and versioned
JAR. Separate Registry delivery/extraction and its separate distribution marker
are skipped. Service configuration, users and systemd remain independent.

The shared archive must be installed by this role: successful extraction records
`.platform-kafka-approved-sha256`. An existing unmarked directory is rejected,
not silently adopted. Shared Registry Apply checks both the approved archive
and this installation marker, including in `schema_registry`-only phase.
Verify checks the marker, launcher and JAR without delivering or extracting an
archive; the approved Kafka checksum is still required. A repository package
cannot substitute for the requested combined archive, and the role does not
fall back to a different source when repository resolution selects one.

If extraction is interrupted before its marker is written, repeat Apply refuses
the unmarked directory. Recovery requires a separately authorized stop of both
services, preservation of any distribution-local logs/custom files, and moving
the unmarked directory aside after confirming it is the configured distribution
root (not `/opt/kafka` or service data/configuration). Rerun Kafka Apply from the
same approved archive so extraction creates a new marker. Do not manually create
the marker or delete Kafka data/configuration to bypass this check.

For Installer/bundle use, update the service package's `service.yml`,
`artifacts.yml` and compatibility metadata to describe the approved combined
distribution: both logical requirements (`kafka-binary` and
`schema-registry-binary`) reference the same archive/checksum, with the correct
component versions. Keep both requirement IDs for planning; one flag in inventory
does not rewrite package metadata or acquire artifacts. The current pinned
separate artifacts remain unchanged; the example above is not a claim of
Confluent 7.8.0 runtime compatibility.

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
Metadata is read once for the exact declared topic-name regex; effective
configurations (including broker defaults) are read once for the deployment and
selected by exact topic name. Newly created topics get an individual read-back.
SCRAM account hooks describe all user metadata and list all ACLs once per
deployment invocation, then select the exact principal and resource
type/name/pattern; only missing managed ALLOW grants are added. The standard
Apply and explicit provider Verify use Core's existing deployment-level account
jobs. Each account still authenticates separately with its own credentials.
These read results live only within the invocation. Library Verify checks
container/readiness/endpoint; explicit provider Verify remains available.
The library provider stage invokes Kafka topic/account hooks only in Apply:
metadata, credential authentication and ACL discovery run once before Vault
credential publication and container startup. No preflight observation cache is
used. Credential or principal conflicts therefore fail during Apply, possibly
after library resources have been created. Direct preflight/verify role calls
remain available and read fresh state.
See the [portable topic contract](../../docs/project-contract.md#kafka-topic-resources).

ACL writes group equal missing operation sets for topic/group/transactional-id,
within one principal and pattern type. Resource identity includes both type and
case-sensitive name. Cluster grants remain separate; batching does not grant
extra operations or delete existing bindings. The same writer serves application
accounts and compatibility principals. One CLI invocation can still issue several
Kafka protocol requests; batching avoids repeated JVM/client startup.

Schema Registry Apply requires Ansible's ordinary `linear` strategy (explicit in
the supplied playbook); `free` is not supported. Preparation completes before
topic reconciliation and activation. `_schemas` policy is checked once per
deployment in the current Ansible batch, through a prepared member. With `serial`
it is read again in each batch. A partial inventory may check through a non-seed
member but cannot create the missing topic there. The coordinator supplies only
candidate identity; the delegated operation uses the selected host's exact
prepared local instance and captured CLI directory after uniqueness/activation
checks. Creation is followed by policy
readback before activation. Ownership, symlink, PKI and configuration guards stay
enabled. Ordinary health-only Verify remains unchanged.

New Registry units start before the final HTTP/HTTPS readiness loop so startup
waits can overlap. A unit is new only when its file is absent and systemd reports
`LoadState=not-found` and `ActiveState=inactive`; loaded/active/ambiguous units keep
the sequential activation/readiness path. Per-instance flags are a host-local list
reset on each invocation, including with hash_behaviour=merge; they are not
portable desired state or a persistent cache.

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
inter-instance TLS also use PEM. Library topic/account hooks and administrative CLI
create PEM bundles only in invocation-private directories and always remove them;
authoritative PKI output is never changed by these hooks.

Explicit `platform_kafka_store_type: PKCS12` retains the previous format and
runtime store-password input. There is no automatic fallback. Verify does not
migrate an installed PKCS12 service or create missing PEM files: retain the
explicit old format or authorize a separate Apply transition. Old files are not
silently deleted. The shared PKI pipeline and Java application PKCS12 delivery
are unchanged, so they can still require their existing runtime store password.

See [PEM implementation/isolated QA](../../docs/work/application-libraries/kafka-pem-plan.md).

## Controller authentication and encrypted JAAS

The default controller listener uses `SASL_SSL` with `PLAIN`; client SASL
listeners retain `SCRAM-SHA-512`. `StandardAuthorizer` remains enabled and
`super.users` contains only `User:admin` from the first start. An authorized
deployment requires its controller listener to use SASL_SSL; an explicit legacy
SSL controller override must be updated in ordinary inventory/group_vars.
Listener names and ports remain supplied by the normal listener projection.

Controller JAAS uses the existing `platform_kafka_admin_credential.passwordSecretRef`
and `platform_kafka_secret_files`. No second password variable is added.
`systemd-creds` encrypts the JAAS from stdin using the node's host key, storing
only `controller-jaas.cred` in the member configuration directory (root,0400).
`LoadCredentialEncrypted` presents it to the Kafka JVM in the service-private
credentials directory; the unit supplies the JAAS path through KAFKA_OPTS.
The standard systemd host key is node-local `/var/lib/systemd/credential.secret`,
not another operator password and not part of the portable project.
The target needs systemd encrypted-credential support; RED OS systemd253 has
been exercised. Other OS versions require their own compatibility acceptance.

Before encrypting, Apply decrypts the existing blob only into operation memory
and compares the expected JAAS. Unchanged credentials preserve the ciphertext
and do not restart the service. Credential/unit changes participate in the
existing member restart condition. Existing caller EnvironmentFile overrides
must preserve the managed JAAS JVM option.

For empty storage, the normal `kafka-storage format` call seeds the same admin
as SCRAM-SHA-512 using `--add-scram`. An invocation-private0600 argfile in `/run`
contains salt and saltedPassword, never a password in process argv; it is always
removed after formatting. Existing storage is never reformatted. Subsequent
administration authenticates the preseeded/existing SCRAM admin and reconciles
the normal ACLs. Certificate superuser bootstrap, revocation and finalization
restarts have been removed. Ordinary inter-broker SSL certificate ACLs remain.
Changing an existing admin password requires coordinated credential rotation;
this change does not add an automatic password-rotation mechanism.

### Infrastructure Verify

`platform_kafka_verify_only: true` enters `tasks/verify_entry.yml` directly.

Apply and Verify normalize the complete input member list through the same
`normalized-members.json.j2` template once per host. Host-specific defaults
remain effective; no normalized state is reused from a previous operation.
Local Verify includes use ordinal member/listener slots so Ansible can execute
matching tasks concurrently on different hosts, including uneven placements.
SCRAM quorum and broker diagnostics share one temporary mode-0600 CLI config
inside an `always` cleanup scope. Distinct non-SCRAM controller/client
connections retain separate configs and both diagnostic commands remain.
It checks each local member's active process, listener ports and actual TLS
handshakes, then cluster quorum, registered unfenced brokers and each enabled
Schema Registry HTTPS `/subjects` endpoint. It does not enter installation,
ownership, configuration-drift, package or artifact checks. The existing shared
member normalizer keeps manual inventory and project-derived identities equal.
TLS paths are resolved once per local member and reused only within that Verify;
Apply always resolves its own current inputs. Quorum diagnostics run on one
selected member. CA/hostname validation and configured CLI authentication remain
enabled; no certificates, accounts or service configuration are reconciled.
