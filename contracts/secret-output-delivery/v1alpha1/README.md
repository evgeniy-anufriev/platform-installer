# SecretOutputDelivery/v1alpha1

This new contract is independent of immutable execution Start, capabilities,
event and terminal-result contracts. It is not yet advertised by a runtime.
The control request is at most 8192 UTF-8 bytes; a safe control response is at
most 32768 bytes. Unknown fields, operations and versions fail closed.
Schemas express structural bounds; implementations must enforce byte limits,
authentication, exact identity bindings and duplicate-key rejection as well.

The transport is SSH with the established host-key and execution identity
policy. The request is JSON on stdin to a fixed trusted entrypoint. Control
stdout is a closed response. Stderr is never copied into error messages.
Fetch content requires a separate binary reader and must never pass through
the ordinary command helper which includes output previews in errors.

## Fetch frame

Success has this fixed representation, with all lengths unsigned big-endian:

```text
magic          4 bytes: ASCII SOD1
metadataLength 4 bytes: 1..8192
tokenLength    4 bytes: 1..4096
sharesLength   4 bytes: 1..32768
metadata       metadataLength bytes of metadata.schema.json JSON (READY)
token          tokenLength bytes of valid UTF-8 (no transformation)
shares         sharesLength bytes of bounded UTF-8 init/shares JSON
EOF            required, no trailing data
```

The entire frame is at most 65536 bytes. Parse and validate all lengths before
allocating. A nonzero SSH process result invalidates the frame even when it
appears complete. A closed JSON error instead of the success magic produces
only a fixed safe code. Never expose partial stdout, stderr or JSON validation
exception strings. Passwords, contents and plaintext hashes are not control
metadata. Returned project/package/generation/cluster identities must match
the request and saved trusted binding before content is used.

Fetch uses the same per-package protected object as apply and standalone
verify, without writing plaintext to a workstation file. Plaintext buffers are
scoped to backend use, never Wails/React DTOs. Workstation uses age encryption;
the encryption password remains on the workstation. Exported files are
admin-token and unseal-shares entries encrypted separately with that password.

## Publication and acknowledgement

The two trusted output entry IDs are also the protected source filenames:
`admin-token` and `unseal-shares` (the latter contains bounded JSON). The
temporary `init-response.json` is recovery-only and is never included in Fetch.
Package ownership is bound to `projectId` + `deploymentId`; this protocol does
not invent or infer a service-internal cluster ID.

The workstation ACK is sent only after both encrypted files and a complete
local receipt have been durably published and read-back/decrypt verified.
Ciphertext digests are SHA-256 and bind each of the two fixed entries. The
remote side checks authenticated owner, project/package/generation and durable
producerCompletion evidence. An absent journal never establishes completion.

ACK commit is a durable nonsensitive receipt before plaintext deletion.
Cleanup failure returns ACKED_CLEANUP_PENDING; an exact repeated ACK retries
cleanup and returns DELIVERED once complete. A different receipt/generation
is a conflict, not permission to replace the committed receipt. A lost response
after deletion is recovered using the same receipt. Run retention must preserve
the journal until terminal/released-producer evidence is durable in the package.

ListPending is scoped to authenticated execution owner and project. Only
READY and ACKED_CLEANUP_PENDING packages appear; receipt metadata survives
ordinary run-history cleanup. No automatic TTL deletes undelivered material.
The cursor is the opaque last package ID of a stable lexical page. Packages
added before an existing cursor appear on the next fresh listing, not an
unbounded live snapshot. Every returned entry must belong to the requested
project; collections and byte limits both apply.

This transport is Installer-only. Standalone Ansible uses protected files in
`<project>/secrets/<deploymentId>` (or an explicit safe output directory), with
no Go, UI, age or delivery ACK requirement. The architecture authority is
`docs/service-install-08-vault-architecture.md`, especially sections 6.1–6.2.
