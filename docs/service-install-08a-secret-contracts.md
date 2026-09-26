# SI08-A typed input contract freeze

These additive schemas are definitions only. The active runtime remains at its
existing versions; no capability is advertised until SI08-C/D integration and
its proof. Published lease v1 request schema only admits payload v1: new typed
inputs therefore use a NEW lease request, not an in-place payload addition.

| Boundary | New version | Preserved |
| --- | --- | --- |
| Feature negotiation | ExecutionCapabilities/v1alpha4 | v1alpha1–3 immutable |
| Target-free safe descriptors | BuildRuntimeSecretDescriptors/v1alpha2 | existing v1 unchanged |
| Protected input transport | PutRuntimeSecretLease/v1alpha2 | v1 unchanged |
| Private payload | TargetCredentialLeasePayload/v1alpha4 | existing v1–3 unchanged |
| Start | StartExecution/v1alpha2 unchanged | same attempt/lease/run semantics |
| Output delivery | SecretOutputDelivery/v1alpha1 | separate fixed handshake |

Manifest `x-secretInputs` carries only ServiceSecretInputs/v1alpha1 metadata.
Neither a setting name nor a value shape is a semantic authority. Exactly two
new purposes exist: SERVICE_ADMIN_TOKEN and SERVICE_UNSEAL_SHARES. Metadata
does not contain SecretRefs, values or file paths. No portable credential
setting is needed. Existing password settings retain their existing semantics.

Descriptors include canonical serviceDeployment and the closed operation set
SERVICE_APPLY/SERVICE_VERIFY. Core derives hosts from placement. A public plan
continues using only requirementRef/purpose/hosts of DeploymentPlan/v1alpha2.
To preserve globally unambiguous refs, new typed input plan refs are `si-` plus
the first 40 lowercase SHA-256 hex characters of canonical JSON
`[serviceDeployment, manifestRequirementRef, purpose]`; Core detects collisions
and blocks, never guesses. Private manifest retains the complete identity.
Descriptor fingerprint includes identity, purpose, hosts, requiredWhen and
operations in deterministic order, not display labels or secret values.

INITIALIZED / SEALED are runtime prerequisites, not facts discovered by
target-free planning or Go. The service role evaluates them during preflight,
before mutation. A new uninitialized cluster generates its inputs in the same
run; an initialized cluster requires the operator's token; sealed nodes also
require shares. Missing material fails safely before changing initialized
storage. New generation inputs are not read from a completed output package.

Lease payload keeps target SSH/sudo, PKI password and existing bounded service
password values. New runtimeSecretInputs is a list of at most 16 typed entries,
each with requirementRef, purpose, serviceDeployment, fixed operations, value.
ADMIN_TOKEN value is nonempty valid UTF-8, at most 4096 UTF-8 bytes, unchanged.
UNSEAL_SHARES value is 1..255 distinct nonempty opaque strings, at most 128
UTF-8 bytes each; encoded JSON array is at most 32768 bytes. Vault-specific key
validity belongs to the role, not Go. Total typed-input encoded value bytes are
at most 65536; entire encoded payload is at most 1114112 bytes. Username is
at most 255 UTF-8 bytes. PKI and existing password values retain their 4096-byte
bounds and 16/65536 aggregate limits. No trimming, rounding or truncation.
JSON Schema maxLength supplies a coarse ceiling, not a claim of byte-counting:
the executable narrow admission helper must also enforce every UTF-8 bound.

Duplicates in metadata requirementRef or payload (deployment, requirementRef)
fail closed. Inputs must match the exact approved private manifest requirements
and operation scopes before attachment; extra/mismatched deployment/purpose
entries are rejected, not ignored. Existing lease binding proves project,
revision, fresh plan fingerprint, private manifest digest, runtime and attempt.
No new TTL, broker or Start transaction is introduced: existing staged TTL,
attachment, revocation and terminal cleanup apply unchanged. Lease cleanup
never revokes a Vault token server-side. Inputs are neither Wails result data
nor local secret persistence. The output encryption password never enters this
payload. No old-version fallback authorizes typed inputs.

The output-encryption prerequisite uses public safe fields only:
requirementRef=`secret-output-encryption`, purpose=`SECRET_OUTPUT_ENCRYPTION`,
hosts=[] (workstation-only requirement). Core includes it when trusted service
output metadata declares secret files. Plan remains displayable; approval/Start
requires the local password and destination. Values are never in that plan.
Vault's output contract is the two fixed entries of SecretOutputDelivery.
Workstation age/password and remote plaintext/ACK ownership remain exactly as
parent architecture §6.2. No role/controller integration is claimed in A.

Local file format freeze for D: raw administrative token is nonempty UTF-8
up to 4096 bytes, unchanged. Bounded init JSON may supply root_token for that
input. Shares files are UTF-8 JSON up to 65536 bytes before extraction: accepted
containers are API keys / keys_base64, CLI unseal_keys_hex / unseal_keys_b64,
or the Installer output container {"keys": [...]}. If both representations
are present, the hex and decoded-base64 byte sets must agree; ambiguity is
rejected, not guessed. Only the selected field is retained. Extraction of a
complete init JSON never returns its other fields to React. The selected array
must meet payload bounds; key syntax/cluster authority is checked by the role.
JSON duplicate keys, invalid UTF-8, mismatched arrays and wrong field types
are rejected. Original files are neither rewritten nor deleted.

Encrypted input/output format is binary age-encryption.org/v1, password-only
Scrypt recipient; no plugins, external command or key-based recipient guessing.
Pinned standard implementation for D: filippo.io/age v1.3.2, not a moving latest
([upstream release](https://github.com/FiloSottile/age/releases/tag/v1.3.2)).
Go API NewScryptRecipient + Encrypt / NewScryptIdentity + Decrypt is used; output
SetWorkFactor(18), input SetMaxWorkFactor(18) BEFORE decryption. Stronger work
factors are unsupported with a safe error, never plaintext fallback. The library
provides KDF/authentication; SHA-256 is ciphertext checksum only. Local encrypted
files are bounded to 131072 bytes before parsing; decrypted files use the above
plaintext bounds. This choice adds no dependency until D and claims no crypto
integration tests in A. See [standard API](https://pkg.go.dev/filippo.io/age).

SI08-C must implement descriptor/plan/private-manifest adapters together and
attest capability v4; SI08-D must add typed input/age/UI integration. Legacy
runtimes cannot run Vault secret operations. The common UI remains rendering
only. The manifest is not added to the active catalog until C.
