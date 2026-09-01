# SERVICE-02A - Kafka named listeners and SSL consumer prerequisites

Status: IN PROGRESS.

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

The service role projects listeners according to logical member roles. Existing
`clientPort` and `controllerPort` inputs remain a bounded PLAINTEXT adapter and
are not persisted beside named listeners. Supplying both models is accepted
only when deterministic equivalence is proven.

Kafka role defaults provide `PLAINTEXT` on `9092`, `SSL` on `9094`, and the
SSL `CONTROLLER` listener on `9093`. Thus every broker receives both
PLAINTEXT and SSL endpoints; controller-capable members receive the controller
endpoint as well. Deployment or member variables override the listener map
only when extra listeners or non-default ports are needed.

`tlsProfile` is assigned once to the Kafka deployment or member. Every SSL
listener on that effective Kafka scope consumes the same profile; individual
listeners do not select certificates.

PKI-01 remains the only certificate and PKCS12 materialization owner. Kafka
consumes PKI-01 materialization plans and the existing
`storePasswordSecretRef`; it does not create authorities, certificates or
password state. Missing or incomplete PKI material blocks before Kafka
configuration or service mutation.

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

The implementation is not complete until focused contract tests, standalone
and centralized RED OS SSL acceptance, existing SERVICE-01A-01D regression,
offline/security checks and documentation evidence pass.
