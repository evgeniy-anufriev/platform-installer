# B2 local application-library writer

`project-edit/v1alpha11` adds fixed library edits; existing v1alpha10 commands
keep their version/meaning. Sessions normalize only library commands to v11.
Review/Save remain local, through the existing managed writer and PlanStore.

All operations use the EditCommand envelope, exact base revision and deploymentId
of the authored library deployment. They never accept derived instance identity.

| Operation | Additional input | Authored change |
| --- | --- | --- |
| CreateApplicationLibraryDeployment | entity with libraryRef/runtimeRef | new library deployment |
| UpdateApplicationLibraryDeployment | partial entity | supplied libraryRef/runtimeRef/bindings/resources/shared_secrets/vault_ref/applications fields |
| DeleteApplicationLibraryDeployment | none | remove deployment; remaining placements block deletion |
| SetApplicationLibrarySlot | entityId, entity | supplied overrides/accounts/credentials fields of slot |
| RemoveApplicationLibrarySlot | entityId | remove authored slot, never package defaults |
| SetApplicationLibraryPlacement | hostId, placement | host membership |
| RemoveApplicationLibraryPlacement | hostId | remove only that membership |
| SetApplicationLibraryOverride | entityId or hostId, property, setting, value | single authored override |
| RemoveApplicationLibraryOverride | same location, no value | delete only that field |

For slot overrides, optional property selects a parameters/environment/ports/endpoint
entry; without it, setting selects an entire declared settings field. Host override
property is parameters or ports, matching the native membership contract. HostId
and entityId cannot be combined. Effective values, SERVER_ID and origin are not
write inputs. New library state explicitly selects desired-state v3alpha1.

Unknown adjacent YAML fields are retained; user-owned documents remain byte-identical.
Overlapping intents and missing direct final-state references are rejected. The
existing revision/document guards, project lock, transaction/recovery and refresh
remain intact. Save proves structural safety; Core Project Verify separately owns
resolution and semantic validity. No Node/Ansible is required for local Save.

## Package import and transfer

Backend.PlanApplicationPackageImport takes source directory, kind, exact name/version,
current revision and reviewed expected digest. Its StructuralEditPlan commits with
CommitStructuralSave. Existing handle-bound export reads capture reviewed bytes in
the bounded opaque PlanStore. No new extractor, catalog, persistence or execution
path is added. Version destinations are immutable; changes require a new version.

The existing manifest must match identity/default namespace, exact file allowlist
and digest of sorted `[relativePath, sha256Hex]` rows, including the manifest.
Destinations derive from `<kind>-packages/<name>/<version>`. Import/transfer admits
manifest, exact role defaults/templates, configuration/assets data and library .env.
It rejects hooks/tasks/handlers/plugins paths, unsafe/traversing or
absolute paths, symlink/reparse points, reserved device names, case-folded duplicate
paths, unlisted/missing files and identity/digest mismatch. This is an Installer
data import policy, not an Ansible resolver or arbitrary-template execution sandbox.

Files of any extension, including no extension, are allowed within the existing
assets/configuration/template paths as trusted application inputs;
they are not executed by the controller. `config_files.source` uses byte-preserving
Ansible copy, while `template` remains text rendering. Core rejects private-key
material in declared configuration; ordinary words such as `password` and
`token` do not classify content as a secret. Compressed archive contents are
not inspected. Source config digests use SHA256 of the original bytes.

Limits for the Go writer/import path: 512 package files, the existing 64 MiB
aggregate project budget and 1024 transaction
document limits. Edits are bounded to 64 KiB/depth16 and existing structural session
limits. Explicit credential/shared-secret descriptors use the closed source shapes of
settings.schema.json: required fields, no extra source or descriptor fields.
Core and Go no longer apply an 8 MiB per-file limit to package assets or
declared configuration. The aggregate project budget remains; the candidate
tar archive sent to the Execution Node has a separate 32 MiB limit.
Literal username is permitted; literal password/shared-secret payload is not.
Generated/runtime/Vault/PKI references remain available as declared by Core.
Private keys remain runtime material. User-defined environment,
parameters, grants and package configuration/templates may contain arbitrary
names and assignments, including PASSWORD. Names do not classify user data as
Installer credentials. Library .env rejects duplicate keys and SERVER_ID, not
credential-like names. This owner amendment applies consistently to local
Save/read/import/export and Core validation. Overlapping parent/child writes in
one review are rejected; independent slots remain composable.

Local revision includes package bytes, including templates and .env. Export includes
and validates their closure alongside existing inventory/project locks. Generated
state, runtime credentials, approvals, run/evidence caches remain outside fixed
export roots. Unsupported packages block export rather than producing partial copies.
An exported project reopens through the existing project-open path.

These are B2 backend primitives. Production UI/package-picker integration is later;
local Save never grants installation admission.

## C editor integration

ManagedProjectView additionally exposes applicationPackages keyed by kind:exactRef,
with kind/ref/digest/definition. Definitions are authored package data from the
existing handle-bound reader/manifest validator, not Ansible-resolved values.
Template/file contents are not exposed. Opening a form never creates an override.

AmendApplicationLibraryDraft reuses edit-session compare-and-swap, byte/expiry
bounds and reviewed-plan invalidation. It can only replace/withdraw the exact
application target; service amendment remains separately restricted.

ReviewApplicationPackageImport binds an existing data-only import preview to
an empty edit session. Existing CommitStructuralEditPlan remains the sole
publication path and performs its normal transaction/revision/refresh checks.
Source bytes are captured at preview; changing the external source afterward
cannot replace the reviewed bytes. Dirty ordinary edits cannot mix with import.

Application Secrets edits typed credential source descriptors through existing
slot accounts; source values use the existing descriptor-bound runtime lease.
The UI may scope visible runtime requirements by declared applicationLibraries,
while preserving the authoritative descriptor-set fingerprint and requirement IDs.
Core source rules and runtime descriptor validation remain authoritative.
