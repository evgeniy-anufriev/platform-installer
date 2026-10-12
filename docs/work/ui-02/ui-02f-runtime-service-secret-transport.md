# UI-02F — bounded runtime service-secret transport

Document scope: the original milestone contract/design. Historical status, review
and QA checkpoints are collected separately; current status and authorization
are recorded only in [CURRENT_STATE](../../../CURRENT_STATE.md).

## Status

See [historical checkpoint](evidence/documentation-checkpoints-20261012.md#ui-02f-runtime-service-secret-transport-checkpoint-001). Current status: [CURRENT_STATE](../../../CURRENT_STATE.md).

## Scope and non-goals

UI-02F transports the exact bounded runtime passwords required by an already
approved fresh plan.  It preserves the existing `PutRuntimeSecretLease/v1alpha1`
request envelope, `StartExecution/v1alpha2`, lease state machine, run binding,
expiry, terminal cleanup, and target credential semantics.

It does not:

- persist a password, SecretRef, private path, lease ID, or secret-derived
  diagnostic in a portable project, draft, public plan, Wails state, event,
  mirror, journal, result, environment, or argv;
- discover secrets from setting names, labels, object shapes, or service IDs;
- add a vault, a secret renewal service, arbitrary target files, or automatic
  secret selection;
- change `DeploymentPlan/v1alpha2`, `StartExecution/v1alpha2`, or an older
  lease payload version;
- calculate PKI, PostgreSQL, topology, or service semantics in Go/React.

## 1. Trusted requirement declaration and Core ownership

Only a catalog setting with a closed `ui.x-runtimeSecretRequirement` extension
may cause a service password requirement.  Its normative, closed value is:

~~~yaml
ui:
  x-runtimeSecretRequirement:
    requirementRef: postgresql-admin-password
    purpose: SERVICE_PASSWORD
~~~

It contains exactly `requirementRef` and `purpose`.  `requirementRef` matches
`^[a-z][a-z0-9-]{0,63}$`; the only supported extension purpose in UI-02F is
`SERVICE_PASSWORD`.  The extension is valid only for a `MANAGED` setting whose
closed object schema requires `passwordSecretRef` as a non-empty runtime-secret
reference.  The catalog decoder, generator and plan collector use this one
validator.  An unknown purpose, unknown key, invalid identifier, incompatible
setting schema, duplicate requirement ID, or malformed extension makes the
catalog/plan unavailable; it is never guessed or silently ignored.

Only the final active deployment configuration participates.  Metadata on a
setting unused by the selected mode, an absent setting, or an empty reference
creates no requirement.  Core then reads the actual opaque `runtime:*`
reference only from the explicitly declared setting value.  It never infers
secret semantics from names or shapes.

The initial use is the three PostgreSQL settings:

- `adminSuperuser.passwordSecretRef`;
- `monitorCredential.passwordSecretRef`;
- `replicationCredential.passwordSecretRef`;

The pg_auto_failover monitor health-check does not consume a configurable
password: upstream pg_auto_failover 2.2 uses a fixed probe identity. PostgreSQL
provisions that dedicated least-privilege role with a monitor-IP-scoped,
TLS-only HBA rule, so it is not a runtime secret requirement.

PKI retains its existing Core-derived fixed requirement.  A generic Core
collector merges the two trusted sources in stable requirement-ref order and
fails closed for duplicate requirement references, invalid runtime references,
or an unsupported/missing declaration.  A private `runtimeReference` is also
unique across the entire merged set: two requirement IDs may not alias one
reference, including across PostgreSQL and PKI.  Shared-secret semantics, if
ever needed, require one explicitly coalesced future requirement rather than
two IDs with the same reference.

For every executable plan Core produces two projections of the same exact
requirements:

~~~text
public DeploymentPlan/v1alpha2.requiredCredentials
  { requirementRef, purpose, hosts }

private digest-bound ExecutionManifest.runtimeSecretRequirements
  PKI:     { requirementRef, purpose, hosts, runtimeReference }
  service: { requirementRef, purpose, hosts, runtimeReference, serviceDeployment }

private ExecutionManifest.runtimeSecretDescriptorSetFingerprint
  sha256 of canonical safe descriptors in stable
  (serviceDeployment | null, requirementRef) order:
  { requirementRef, purpose, serviceDeployment | null, hosts }
~~~

The public schema remains unchanged; `runtimeReference` and all values remain
private.  `serviceDeployment` is mandatory only for `SERVICE_PASSWORD`; it is
the exact final deployment that owns the declared setting.  It is omitted for
the existing Core-derived PKI requirement.  The manifest is the authority that
maps one safe requirement ID to one opaque runtime reference and, where needed,
one deployment, then binds that mapping to project revision, plan fingerprint,
runtime release, and Start attempt.  The controller selects service mappings
only when its manifest operation has the same `serviceDeployment`; it does not
filter by a service name, requirement name or UI label.

Core returns the same canonical `runtimeSecretDescriptorSetFingerprint` with
every descriptor response.  The broker may rebind pre-plan values only when
the fresh private manifest has the identical fingerprint and the same project
revision/runtime identity.  Labels are deliberately excluded from this equality
test.  Any changed deployment, purpose, hosts, requirement ID, revision or
runtime clears the affected values before PUT.

## 2. Closed v1alpha3 lease payload

`TargetCredentialLeasePayload/v1alpha1` and `/v1alpha2` are immutable.
`TargetCredentialLeasePayload/v1alpha3` is a closed successor with this exact
complete field set:

~~~text
apiVersion, kind
username
exactly one of password | privateKey
sudoPassword | null
pkiStorePassword | null
runtimeSecretValues | null
~~~

`pkiStorePassword` preserves the v1alpha2 valid UTF-8 1–4096-byte rule.  It is
non-null exactly when the private manifest contains the fixed PKI requirement;
otherwise it is null.  `runtimeSecretValues` is non-null exactly when the
private manifest contains one-or-more `SERVICE_PASSWORD` requirements;
otherwise it is null.  Both may independently be non-null for a PostgreSQL
apply that also materializes PKI.

`runtimeSecretValues` is an object keyed only by public `requirementRef`.
Its key set must exactly equal the private manifest's required secret set when
that set is non-empty; it must be `null` when no runtime secret is required.
Each value is a non-empty valid UTF-8 string of at most 4096 UTF-8 bytes.
There are at most 16 entries and their combined encoded secret bytes are at
most 65536 bytes.  Values are never trimmed, normalized, truncated, rounded,
or rewritten.  Go and Python apply identical bounds and reject extra, missing,
duplicate-after-normalization, malformed, or over-limit input before lease
publication.

The existing 1088 KiB complete-payload ceiling remains.  Capability negotiation
advertises v1alpha3 only when the runtime implements this exact decoder and
private manifest attestation.  A plan requiring service secrets blocks before
PUT if v1alpha3 is unavailable; it never downgrades to v1alpha1/v1alpha2.

`ExecutionCapabilities/v1alpha1` and `/v1alpha2` remain immutable.  A runtime
that supports this feature publishes the closed `ExecutionCapabilities/v1alpha3`
envelope.  Its required top-level fields are exactly `apiVersion`, `kind`,
`bootstrapProtocol`, `coreVersion`, `catalogDigest`, `schemaDigest`, `runtime`,
`supportedOperations`, `executionStart`, and `runtimeSecretDescriptors`; its
only optional inherited top-level fields are `projectSnapshotRequestVersions` and
`targetCredentialLease`.  Those inherited fields retain their v1alpha2
closed-object semantics, including the existing digest grammar, runtime shape,
Start protocol and maximum payload bound.  `supportedOperations` uses the
v1alpha2 operation vocabulary plus `BuildRuntimeSecretDescriptors`, which is
mandatory.  The required v1alpha3-only top-level field is a closed object with
exactly these four fields:

~~~text
runtimeSecretDescriptors:
  protocol: BuildRuntimeSecretDescriptors/v1alpha1
  maxDescriptors: 16
  maxHostsPerDescriptor: 256
  maxResponseBytes: 65536
~~~

Its existing `targetCredentialLease.payloadVersions` is the stable ordered
list `TargetCredentialLeasePayload/v1alpha1`, `/v1alpha2`, `/v1alpha3`; a
v1alpha3 publisher must implement all three decoders.  `v1alpha2` remains
valid for existing non-descriptor planning and legacy credentialed Start, but
cannot authorize a descriptor request or a service-secret Start.  A malformed
v1alpha3, unknown descriptor protocol, absent descriptor capability, or absent
`TargetCredentialLeasePayload/v1alpha3` fails closed; it is never reinterpreted
as v1alpha2.

## 3. Installer and UI boundary

The Go request to the existing runtime-secret broker carries only public safe
descriptors (`requirementRef`, `purpose`, `hosts`, and the trusted catalog
display label) for the fresh approved plan.  It does not carry
`runtimeReference`, manifest contents, or a node file path.

The Services page presents a generic **Secrets** action for a selected saved
deployment before plan creation.  It obtains its fields only through the new
target-free Core operation `BuildRuntimeSecretDescriptors/v1alpha1`; Go/React
do not parse catalog metadata or infer active requirements.  The closed request
has no caller-supplied Execution-Node path.  The adapter creates a
request-owned archive in its fixed staging root, verifies the archive digest
and canonical revision, and gives Core only that verified staged source.  It
removes that staging root after success, failure, cancellation, or a lost
response; it never creates an execution manifest, run, or lease.  The closed
result contains only:

~~~text
projectIdentity, projectRevision, runtime identity
descriptors[]:
  requirementRef, purpose, serviceDeployment, displayLabel, hosts
~~~

The response is at most 65536 bytes and contains at most 16 descriptors.  A
descriptor has at most 256 hosts; `requirementRef` is at most 64 ASCII bytes,
`serviceDeployment` at most 128 ASCII bytes, and `displayLabel` at most 160
UTF-8 bytes.  Core either returns the complete deterministic set (including
the canonical descriptor-set fingerprint) or a bounded safe blocking result;
it never returns a partial set.  These are response bounds, not new desired
state grammar.

It contains no SecretRef, configuration value, private manifest, planned
operation, lease ID, path or secret bytes.  It is deterministic, reads the
same final active desired state and trusted catalog metadata as plan building,
performs no target contact and has no write path.  A malformed response or
revision/runtime mismatch fails closed and keeps the dialog unavailable.

The operation is advertised only through a new closed
`ExecutionCapabilities/v1alpha3` envelope.  Existing capability versions stay
immutable: an older or malformed capability does not fall back to a local
catalog interpretation and merely leaves pre-plan secret entry unavailable.
The selected Execution Node must be READY for this target-free Core request;
readiness/preparation ownership remains unchanged.

The result opens one reusable `ServiceSecretsDialog` in the selected deployment
context, with password fields from trusted labels and status only.  It does not
implement a PostgreSQL-specific screen.  Saving that dialog means “retain for
this Installer session”, not “save the project”; it never calls the project
writer.  The Certificates page uses the same descriptor operation for the
separate PKI-store-password dialog because that value belongs to the TLS
profile rather than a service deployment.

Before a plan exists, the broker binds values to the descriptor result's exact
project identity, saved revision, selected Execution Node/runtime identity,
descriptor-set fingerprint, deployment ID and public requirement ID.  It clears
them on semantic Save, project/node/runtime switch, descriptor expiry, terminal
completion, explicit clear or application exit.  At Start, a freshly built
private manifest must expose the same descriptor-set fingerprint and the same
revision/runtime identity; otherwise the broker clears the affected values and
requires a new descriptor read and entry.  Only then are the in-memory values
rebound to the plan fingerprint and staged.  React receives
only safe status per requirement (`REQUIRED`, `PRESENT`, `MISSING`, `EXPIRED`)
and the approved prompt label; it never receives a value, SecretRef, lease ID,
or path. Approval checks availability against public requirements already in
the fresh Core plan; it does not issue another descriptor request. Start repeats
the check against the current Core descriptor set before PUT because session values can
expire or be cleared after approval; the error directs the user to the owning
Services or Certificates dialog.

## 4. Execution Node and controller

The node validates the exact manifest requirement list before accepting a
v1alpha3 lease and again before the durable Start commit.  It retains the
existing atomic STAGED -> ATTACHED(runId) transaction.  The controller resolves
the attached payload only after that commit and creates one private `0600`
file per manifest mapping inside the run directory.

For a service operation, the controller selects only private requirements whose
attested `serviceDeployment` equals that operation's manifest deployment, then
projects them to the established role variable derived from the selected
service manifest's validated `roleEntrypoints.variablesPrefix` plus
`secret_files`.  Thus a PostgreSQL operation receives the exact attested mapping in
`platform_postgresql_secret_files`; unrelated operations receive no PostgreSQL
mapping.  PKI materialization continues to receive its existing separate
`platform_pki_secret_files` mapping.  A PostgreSQL apply which imports PKI may
receive both independently attested maps; PostgreSQL verify receives only the
PostgreSQL map when PKI verification does not require the store password.

The private projection is therefore conceptually:

~~~text
platform_pki_secret_files: { runtime:<opaque-ref>: <private-run-path> }
platform_postgresql_secret_files: { runtime:<opaque-ref>: <private-run-path> }
~~~

Each mapping contains only references attested for that operation/service and
is not exported beyond the controller.  No role knows the Execution Node
storage layout.  Existing terminal/recovery cleanup removes the derived files
with the attached lease; a stale/failed pre-commit attempt creates no
authoritative run and no reusable projection.

## 5. Compatibility and failure rules

| Situation | Required result |
| --- | --- |
| Legacy runtime or only v1/v2 payload | planning may work; Start of a service-secret plan is blocked before PUT |
| No service secret requirement | existing v1/v2 behavior remains available |
| Extra/missing requirement ID or private-manifest mismatch | fail closed; no lease or Start |
| Expired/cleared broker values | Start blocks before PUT; project is unchanged |
| Lost PUT/Start response | existing same request/start-attempt idempotency applies; no duplicate lease/run |
| Pre-commit failure | existing staging rollback; no run/projection |
| Post-commit launch failure | existing authoritative run becomes terminal FAILED; normal lease cleanup applies |

## 6. Required proof

1. Catalog/Core tests prove only explicit trusted metadata creates a service
   requirement; names or arbitrary objects do not.  They cover malformed or
   unknown extension fields, invalid IDs/purposes, incompatible setting schemas,
   duplicate IDs, inactive-mode settings and no-metadata/no-inference.
2. Plan/manifest tests prove stable public/private projections, no
   `runtimeReference` in public plan/Wails DTO, exact requirement mapping, and
   the canonical descriptor-set fingerprint.  They prove a descriptor value
   cannot rebind if deployment, requirement, purpose, hosts, revision, runtime
   identity or descriptor-set fingerprint changes.
3. Capability/descriptor tests prove the closed v1alpha3 envelope, no v1alpha2
   fallback, immutable v1/v2 compatibility, request-owned archive staging,
   archive digest/revision verification, cleanup on success/failure/cancel/lost
   response, no caller-selected node path, and no manifest/run/lease/target
   contact for the target-free operation.  They cover over-capacity Core BLOCK
   rather than partial response, all descriptor/host/field/response limits,
   deterministic order and secret-free DTOs.
4. Go/Python protocol tests cover v1/v2 compatibility, v1alpha3 PKI-only,
   service-only and combined payloads, positive and negative byte bounds,
   exact null/key-set validation, duplicate runtime-reference rejection
   including PostgreSQL/PKI, idempotency, and no secret output.
5. Controller/role tests prove PostgreSQL mapping presence only for PostgreSQL,
   its absence for unrelated services, exact SecretRef-to-private-file mapping,
   service-deployment scope selection, terminal/recovery cleanup, and no
   path/value leakage or target contact before committed Start.
6. Core-adapter tests prove the descriptor operation is target-free,
   deterministic, revision/runtime-bound, bounded and secret-free.
7. Wails tests prove the generic per-service Secrets dialog, session-only Save,
   stale-value clearing and safe statuses/prompts only, with no value round trip.
   UI acceptance reconciles the existing mockup before implementation: the
   action is present only for a selected managed deployment with a READY
   descriptor capability; its dialog makes session-only retention and missing
   Start prerequisites clear without adding a service-specific screen.
8. SERVICE-INSTALL-06 then adds PostgreSQL through the existing Go/UI lifecycle
   to the cumulative project, runs two full plans, and proves PostgreSQL plus
   all existing services verify successfully with repeat `changed=0`.

## Exit criteria

UI-02F is complete only after a new immutable runtime release advertises the
closed v1alpha3 capability, all protocol/secret/regression gates pass, and
SERVICE-INSTALL-06 succeeds through `CreatePlan -> ApprovePlan -> Start`
without a manual Execution-Node secret file or a non-UI execution path.
