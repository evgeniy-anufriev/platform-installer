# UI-02E — PKI runtime store-password transport

Status: **OWNER-APPROVED DESIGN; implementation pending one PLAN review.**

UI-02E acceptance exposed a real boundary: a TLS profile may require a
runtime-only PKCS12 store password, while the published
`TargetCredentialLeasePayload/v1alpha1` deliberately transports only target
SSH and optional sudo credentials.  The existing payload remains immutable.
This addendum introduces no generic secret store, map, vault, desired-state
field, or workstation-to-target execution path.

## 1. Fixed scope and ownership

The only newly transportable value is one PKI store password for the already
supported desired-state reference `runtime:pki-store-password`.

| Concern | Authority |
| --- | --- |
| Whether the saved project requires this secret | Core, while building the exact plan/manifest |
| Raw password collection and expiry | Installer `runtimesecret.Broker`, in process memory only |
| Lease transport and private files | selected Execution Node |
| Mapping to `platform_pki_secret_files` | trusted controller/runtime projection |
| PKI use and materialization | existing Ansible/Core role |

React receives only a closed requirement state (`NOT_REQUIRED`, `REQUIRED`,
`PRESENT`, `MISSING`, or `EXPIRED`).  It never receives a SecretRef, raw
password, lease ID, private file path, manifest, or secret-derived diagnostic.
No value is added to portable project files, saved drafts, snapshots, plans
shown to React, journals, event mirrors, results, logs, environment or argv.

The exact runtime reference is deliberately closed in this version.  A TLS
profile using any other `runtime:*` store-password reference remains valid
portable desired state, but its executable plan is blocked with the safe Core
finding `PKI_STORE_PASSWORD_REFERENCE_UNSUPPORTED`; it is not rewritten or
lost.  This prevents silently treating a one-password payload as a generic
secret registry.

## 2. Core plan and private-manifest attestation

For an executable plan, Core derives the requirement from the resolved PKI
materialization plan, not from React or a service name:

~~~text
no store password reference                -> no requirement
runtime:pki-store-password (one or more)  -> PKI_STORE_PASSWORD requirement
another runtime reference                  -> BLOCKED finding
~~~

The immutable public `DeploymentPlan/v1alpha2.requiredCredentials` projection
uses exactly one existing-schema entry in stable order:

~~~json
{
  "requirementRef": "pki-store-password",
  "purpose": "PKI_STORE_PASSWORD",
  "hosts": ["<stable resolved PKI target host IDs>"]
}
~~~

`requirementRef` and `purpose` are fixed public convention constants, not
desired-state SecretRefs.  `hosts` is the existing bounded, distinct,
lexicographically ordered target-host projection from the exact resolved PKI
materialization plans.  The entry contains no secret reference, password,
lease ID, private path or runtime-secret bytes and uses no new v1alpha2
field.  Existing consumers can therefore decode it through the unchanged
published schema.

The private, digest-bound `ExecutionManifest` carries the same closed public
requirement and its fixed private runtime reference.  The manifest digest
therefore binds the need before the workstation can stage a lease.  The
controller rejects a v2 payload with
`pkiStorePassword` unless that exact manifest requires it, and rejects a
manifest requiring it when the attached lease lacks it.  This is an
attestation and transport gate, not local PKI/SAN/consumer calculation.

`BuildDeploymentPlan` remains fresh and mandatory immediately before Start.
Changing the saved project produces a different revision/plan/manifest and
cannot reuse a staged lease from the earlier binding.

## 3. Versioned closed payload and capability

`TargetCredentialLeasePayload/v1alpha1` is unchanged.  A new closed
`TargetCredentialLeasePayload/v1alpha2` has exactly:

~~~text
apiVersion, kind
username
exactly one of password | privateKey
sudoPassword | null
pkiStorePassword | null
~~~

The SSH/sudo fields keep their v1alpha1 validation and bounds.  The new field
is `null` or a valid, non-empty UTF-8 value whose encoded size is **at least
1 and at most 4096 bytes**.  The byte sequence is neither trimmed, normalized,
truncated nor rewritten; Unicode code-point count is not a bound.  Go and
Python apply the same `1 <= len(UTF8(value)) <= 4096` rule and reject malformed
UTF-8 at byte-oriented protocol boundaries.  No secret refs, maps, names,
lists, metadata or extension fields are accepted.  `null` is required when
the private manifest does not attest `PKI_STORE_PASSWORD`; a non-null value is
required when it does.  Payload canonical bytes and digest remain lease
request-idempotency inputs.

`ExecutionCapabilities/v1alpha2.targetCredentialLease.payloadVersions` is a
closed, stable unique list.  A runtime implementing this design advertises
both v1alpha1 and v1alpha2 only if it can safely handle both.  Credentialed
Start chooses v1alpha2 exactly when the private fresh manifest requires the
PKI secret; otherwise it may continue using v1alpha1.  Missing v1alpha2,
malformed capability data, insufficient advertised bytes, or an incompatible
payload version blocks that credentialed Start.  There is no downgrade of a
PKI-required run to v1alpha1 and no SSH fallback from workstation to target.

`PutRuntimeSecretLease/v1alpha1` stays the metadata/lease protocol.  Its
existing closed request envelope is unchanged; `payload.apiVersion` chooses
the closed body decoder.  `StartExecution/v1alpha2`, `startAttemptId`, and
the committed-run idempotency rules remain unchanged.

## 4. Installer session input

The existing project-bound broker lease is extended with one optional raw PKI
store password and a safe status bit.  It is accepted through a narrow Wails
setter only after the active plan's public safe requirement indicates
`PKI_STORE_PASSWORD`; the setter returns status only and never the value.
The UI presents one password prompt during Start preparation when it is
required and missing.  It does not prefill, persist, reveal, validate against
PKI, or conflate it with SSH/sudo credentials.

The password uses the broker's existing binding, TTL, replacement, expiry,
project-switch, clear, zeroing and synchronous-callback rules.  Starting a
PKI-required plan without a current password fails before PUT with
`PKI_STORE_PASSWORD_UNAVAILABLE`; draft/project/canonical files remain
unchanged.  A plan that does not require it never requests or transports one.

## 5. Node private material and controller projection

On an accepted v2 PUT, the node stores the complete bounded payload in the
existing 0700 lease directory with existing 0600/atomic/fsync semantics.  It
does not write an independently named secret cache.  After the durable Start
commit attaches that lease to the authoritative run, the controller validates
the manifest requirement and derives one private 0600 password file from the
attached payload in the run-private directory.  It sets:

~~~text
platform_pki_secret_files = {
  "runtime:pki-store-password": <controller-private path>
}
~~~

only in the controller-owned runtime projection consumed by the existing PKI
role.  The mapping/path is excluded from journal events, diagnostics, Wails,
environment, stdout/stderr and result projections.  The derived file and the
attached lease material are removed only through the existing terminal/recovery
lease cleanup.  A cancellation request, UI navigation or observer failure does
not remove material while the run may still use it.

The controller fails closed before dispatch when manifest/lease requirement
and payload disagree.  It never guesses a reference, derives a password, or
allows Ansible to obtain one through lookup, environment or arbitrary file.

## 6. Failure, recovery and compatibility

Pre-commit PUT/Start failure follows the existing STAGED rollback rule and
leaves no authoritative run.  Post-commit launch failure terminates the same
authoritative run and uses normal attached-lease cleanup.  A repeated Start
with the same attempt returns the same run and does not write a second PKI
file or attach another lease.  Expired/cleared broker input requires a fresh
attempt.

Legacy v1alpha1 capability/runtime remains valid for non-PKI credentialed
plans.  A PKI-required plan on that runtime is safely blocked; no published
v1alpha1 schema or behavior is changed.  Manual standalone Ansible remains
outside this Installer transport and retains its documented runtime-secret
prerequisite.

## 7. Acceptance and non-goals

Focused tests must prove:

- Core derives exactly the closed requirement and blocks unsupported runtime
  refs without exposing secret values;
- the public plan uses only the unchanged `requirementRef`, `purpose`, and
  bounded `hosts` convention; an existing v1alpha2 consumer decodes it without
  a schema upgrade;
- v1alpha1 is unchanged; v1alpha2 rejects unknown/malformed fields and
  requirement/payload mismatch;
- the password boundary rejects empty and 4097-byte values, accepts 1-byte and
  exactly 4096-byte values (including multibyte UTF-8 at that exact byte
  length), and rejects multibyte overflow or malformed UTF-8 without reporting
  password bytes;
- capability negotiation selects v2 only when required and compatible;
- broker expiry/binding/zeroing covers the PKI password;
- node idempotency, attach, terminal cleanup and recovery cover v2 material;
- controller emits the private mapping only for the attested attached run;
- runtime projection, events, mirror, result, Wails DTOs and diagnostics do
  not expose the password, reference, lease ID or private path;
- the real one-host/three-member Kafka fixture performs PKI apply/verify,
  Kafka apply/verify and repeat apply `changed=0` through the generic
  `CreatePlan -> ApprovePlan -> Start` flow.

Out of scope: arbitrary runtime secret references; multiple PKI passwords;
Vault/keyring integration; secret persistence; secret rotation; a service
specific Kafka branch; PKI editor redesign; Core PKI semantic/SAN changes;
and changes to target credential transport semantics beyond payload v1alpha2.
