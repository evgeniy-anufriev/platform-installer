# SERVICE-02A - Kafka named listeners and SSL consumer prerequisites

Status: DONE.

SERVICE-02A extends the Kafka service package with a named listener contract.
The supported protocols are `PLAINTEXT` and `SSL`; SASL is out of scope.
Listener names are explicit identifiers and are independent of protocol.

```yaml
tlsProfile: infrastructure-tls
listeners:
  CLIENT_SSL:
    purpose: client
    securityProtocol: SSL
    port: 9092
  INTERNAL:
    purpose: interBroker
    securityProtocol: SSL
    port: 9094
  CONTROLLER:
    purpose: controller
    securityProtocol: SSL
    port: 9093
```

The service role projects listeners according to logical member roles. Named
listeners are the only supported port contract; legacy `clientPort` and
`controllerPort` settings are not part of SERVICE-02A.

Kafka role defaults provide `PLAINTEXT` on `9092`, `SSL` on `9094`, and the
SSL `CONTROLLER` listener on `9093`. Thus every broker receives both
PLAINTEXT and SSL endpoints; controller-capable members receive the controller
endpoint as well. Deployment or member variables override the listener map
only when extra listeners or non-default ports are needed.

`tlsProfile` is assigned once to the Kafka deployment or member. Every SSL
listener on that effective Kafka scope consumes the same profile; individual
listeners do not select certificates.

Kafka CLI diagnostics consume a secret-free `KafkaCliConnection` runtime
projection selected by listener `purpose`, not listener name. It contains the
projected bootstrap endpoint and protocol; SSL adds the projected truststore
path/type and `storePasswordSecretRef`. The password itself is resolved only
while an ephemeral command-config is rendered, then the file is removed.
`server.properties` is observed state only and is not used as a configuration
or secret source for verification. Kafka's secure endpoint-identification
default is preserved: diagnostics do not inject an empty override, and TLS
handshakes verify the resolved advertised hostname or IP SAN.

PKI-01 remains the only certificate and PKCS12 materialization owner. Kafka
consumes PKI-01 materialization plans and the existing
`storePasswordSecretRef`; it does not create authorities, certificates or
password state. Missing or incomplete PKI material blocks before Kafka
configuration or service mutation.

QA state invariant:

> Stable PKI identities/fingerprints persist; PKI materialization plans do not.
> Every independent Ansible execution reconstructs derived PKI plans through
> read-only resolution.

`platform_pki_secret_files` remains the runtime-only SecretRef-to-password-file
mapping required by PKI-01; it is not repurposed as a destination directory.
Before Kafka configuration is rendered and the member is started, the
declared PKI material is copied into a Kafka-owned consumer directory. Set
`platform_kafka_pki_directory` to override it; otherwise the member uses
`<member config directory>/pki`. The copied directory and files are owned by
the Kafka service account, and Kafka does not read the PKI deployment tree.

Listener properties are managed/reserved. `advancedConfig` cannot override
listener, quorum or listener-scoped SSL properties. Generated state remains
limited to identities, fingerprints, locks and reconciliation metadata.

Acceptance evidence: focused Kafka contract tests `22 OK`, full Core suite
`113 OK`, generated catalog reproducibility, Kafka apply/verify syntax checks,
and privileged `sudo unshare -n` passed on RED OS. The isolated SSL FAST matrix
passed for SERVICE-01A through SERVICE-01D: each profile completed initial
apply, a separate read-only PKI/Kafka verify with `changed=0 failed=0`, and a
repeat apply with `changed=0 failed=0`. No reset or reformat was performed
between verify and repeat. Runtime-only roots and logs were profile-isolated;
secrets were not emitted.

The follow-up projection refactor passed focused contract tests (`25 OK`) and
RED OS 01D read-only verify plus repeat apply (`changed=0 failed=0`). A
temporary expected-state probe renamed the controller listener to `RAFT_SSL`
without changing the running Kafka cluster; quorum verification still passed,
proving the diagnostic selects `purpose: controller`, not a listener name.
