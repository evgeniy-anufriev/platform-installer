# SI08-A — contract foundation, DONE

Owner implementation authorization: 2026-09-26. Architecture authority:
[Vault plan](service-install-08-vault-architecture.md). Latest SI08-PLAN-02
correction is owner-authorized; independent PLAN re-review of that correction
is not claimed. Automatic PLAN review budget remains exhausted. The initial
SI08-A implementation DIFF gate is separate and is required before closure.

Implemented so far:

- New additive SecretOutputDelivery/v1alpha1 request, safe metadata and control
  response schemas. No existing schema version is modified.
- Fixed binary Fetch-frame specification with byte bounds and identity binding.
- Go `internal/secretoutputwire.Consume`: exact frame/identity verification,
  bounded reading, safe parse/transport errors, duplicate metadata rejection,
  borrowed secret-buffer cleanup. Not yet connected to an SSH process; its
  caller must establish a successful process exit before consumption.
- Positive/negative schema and decoder tests.
- Closed Go control-request decoder with presence, operation-specific fields,
  duplicate keys, UTF-8 and byte-limit admission.
- Python request/Fetch codec reusing the existing offline SchemaValidator;
  no filesystem access, target contact or active runtime entrypoint.
- Private Linux package publication and Fetch storage foundation in
  `ansible-core/tools/execution_secret_output.py`: fixed entry names,
  descriptor-relative no-follow access, opened-object ownership/mode/link
  checks, package flock, durable binding and entries, READY metadata published
  last via atomic replace. Identical retry is admitted; conflicting identity
  or contents never overwrite. Failed publication preserves protected partial
  material and does not expose it as READY. No ACK or cleanup is enabled yet.

Owner-authorized DEV acquisition completed on 2026-09-26: exact
`vault-1.21.2-1.red80.x86_64` from configured RED OS `updates`, no install.
The acquired binary reports `Vault v1.21.2` (cgo). This is artifact evidence,
not deployment or full service/OS compatibility acceptance. Source policy is
unchanged; no runtime release was published or activated.

Evidence: RED OS contract suite 21 PASS and Python codec tests 3 PASS;
`go test ./...`, `go vet ./...` and `git diff --check` PASS. Focused Go
secretoutputwire and executionnode packages PASS. Temporary QA workspaces are
cleaned using qa-sync after verification. Full milestone acceptance gates,
including protected storage/recovery and OS-specific race tests, remain pending.

2026-09-26 continuation: RED OS storage tests 10 PASS, codec tests 3 PASS,
contract tests 21 PASS. Core suite ran 320 tests, OK (4 skipped).
`go test ./...`, `go vet ./...`, and `git diff --check` PASS. Storage tests
cover symlinks/hardlinks/FIFO, mode/bounds, held-directory path replacement,
partial-write and atomic-publication failures, exact retry and no overwrite.
This is unit/fault-injection evidence, not an activated runtime or Vault run.

Not implemented yet: trusted controller package integration and terminal evidence, retention
guard, authenticated runtime operations, local age encryption/publication/ACK,
Vault service package/Ansible init-unseal-configure-verify, Core output
descriptors, conditional incoming credentials, Wails/React and real deployments.
This progress entry preceded closure below. SERVICE-INSTALL-08 has no
end-to-end acceptance result.

## Exact SI08-A closure boundary (2026-09-26)

The architecture §9 defines A as owner decisions, a pinned verified artifact,
checked contract gaps and closed manifest/settings/secret contracts. It does
not define A as a Vault deployment or completion of every B–E implementation.
The storage/codec foundation above is progress, not proof of those entire gates.

The artifact prerequisite was previously blocked by missing acquisition
authorization; the owner explicitly supplied it on 2026-09-26. It is now
RESOLVED. Exact download used `dnf download`, with only configured `updates`
enabled, on trusted QA node 101. No package install was performed.

- Local import: `.runtime/artifacts/vault/vault-1.21.2-1.red80.x86_64.rpm`.
- Size: 80,737,986 bytes.
- RPM SHA-256: `sha256:11db853f514625835ed4516876311057b7021fbaf39a53040e5e13d111bc41dd`.
- Repository package checksum equals that exact SHA-256; remote file and
  workstation copy also match it.
- `rpmkeys --checksig --verbose`: existing trusted RED OS RSA/SHA256 signing
  key `f8ac18ee` OK; header and payload digests OK. No key was imported.
- Extracted `/usr/bin/vault` SHA-256:
  `sha256:f72a62dc3209cc60cf96da83b6f13c5452af6994150cd255af6b37bc6762b7c2`.
- Extracted binary version command: `Vault v1.21.2, built 2025-09-26T10:06:34Z (cgo)`.
- `.runtime/artifacts/vault/` is Git-ignored. No artifact was added to Git.
- Remote acquisition workspace and extracted binary removed after local digest
  verification; the verified local RPM remains available for the next steps.

RPM metadata declares BUSL-1.1. The pinned
[upstream license](https://github.com/hashicorp/vault/blob/v1.21.2/LICENSE)
sets redistribution/notice and production-use conditions; no general legal
clearance for distributed product packaging is claimed. This RPM file list
does not include LICENSE. Before an offline distribution, preserve the license
and notices and confirm the intended use under those conditions. Acquisition
does not authorize automatic bundle redistribution.

Pinned initialization bounds were checked against upstream v1.21.2
`SealConfig.Validate`: integer shares/threshold 1..255, threshold <= shares,
and threshold >= 2 when shares > 1. Architecture §5 records the exact rule;
default 2-of-3 is valid. No change to an older schema was made.

SI08-A contract definitions are now present: `services/vault/service.yml`,
reproducible configuration schema and compatibility candidate; exact additive
input-secret schemas and byte/scope admission helper. Definitions and integration
obligations are in [typed contract freeze](service-install-08a-secret-contracts.md).
ExecutionCapabilities v4, descriptor v2, lease v2 and payload v4 are NOT active
or advertised. Start v2, existing capability/lease/plan/manifest/catalog schemas
are unchanged. Vault is not added to the active fixture catalog.

2026-09-26 A gates: contract tests 31 PASS, including typed input and capability
positive/negative cases; Core suite 320 tests, OK (4 skipped); configuration
schema and catalog reproducibility PASS; network-isolated contract tests 31
PASS (`sudo -n unshare -n`); RED OS Go wire race PASS; Windows full Go test/vet
and diff-check PASS. Existing published schemas have no diff. Frontend/Wails
are unaffected and not rebuilt. Mockup review confirms no new installation
page; file inputs/output password controls remain D implementation obligations.

Remaining A gate: one initial high-risk implementation DIFF review of the
frozen A-owned scope. No new FULL PLAN or exhausted PLAN recheck is run.
ProducerCompletion/retention/ACK and runtime/UI integration remain unimplemented
and must be completed at their approved boundary before any secret-output run.

## Initial implementation DIFF result — BLOCK (2026-09-26)

Independent architecture-reviewer reviewed base HEAD
`221b05dee8c54492991af0d61c92842d7cf10d75`, A-owned 31-file content fingerprint
`cbfc00b02ba7faa88bfdddd167c06c03ab739be3ad16aa517d27ad76f21b3a6b`.
This is the one initial implementation DIFF review, not another PLAN review.

- SI08-A-DIFF-01 BLOCKING: canonical/input deployment IDs permit dots and
  underscores, but output metadata and Go binding validation reject them.
  Proposed bounded correction: align output admission with canonical grammar
  and test identical ID cases across schema, Python storage and Go decoder.
- SI08-A-DIFF-02 NON_BLOCKING: Go metadata struct decode accepts altered key
  case. Proposed correction: validate exact metadata keys before decoding.
- SI08-A-DIFF-03 RESOLVED: callback errors cannot propagate secret content;
  Consume returns fixed ErrTransfer and clears borrowed buffers. Independent
  focused QA and its new regression test PASS.
- Overengineering: 0 findings.

After the callback correction: Windows full Go test and vet PASS; RED OS
wire race PASS (1.059s); diff-check PASS. The earlier unchanged Python/schema
gates remain 31 contract tests and 320 Core tests, OK (4 skipped).
The latest explicitly created QA workspace was removed through qa-sync.

At that review revision SI08-A was BLOCKED, not DONE. No SI08-B or Vault
deployment. Work stops for owner direction on the two bounded corrections;
no automatic correction/review loop is started. The fingerprint identifies
the reviewed implementation before this evidence-only documentation append.

## Owner-approved correction and closure (2026-09-26)

One TARGETED_RECHECK of SI08-A-DIFF-01/02: APPROVE, both RESOLVED;
DIFF-03 remains RESOLVED. Zero blocking and zero overengineering findings.
Canonical deployment grammar is now identical in output schema and Go,
with a 128-character bound. Python schema/publish/Fetch and Go tests cover
hyphen, dot, underscore, max length and rejected identifiers. Exact metadata
keys are checked before Go struct decode; changed-case aliases fail closed.

Reviewer-bound SHA-256:

- metadata.schema.json: `82138B0B92178789087BE9250E2113CEBC49E2EFFC921AC5E2802F1014F21543`
- frame.go: `F468910930E9B5725600F94C450120442F7A073D001931F60A30E05AE0DA55DB`
- frame_test.go: `A9A1F7967B7461C38FDC6262FC0591EEF2B8761DAD38BBF72A52C2F6E24658B0`
- test_execution_secret_output.py: `18247703DD4C3A4AFBE86E4747B2C7DBD42BE46040081986674B99C88DF53227`

Final gates: Windows focused/full Go test and vet PASS; RED OS contracts
31 PASS; Core 321 tests OK (4 skipped); wire race PASS (1.034s); catalog
and service-schema reproducibility PASS; git diff --check PASS. Independent
callback leakage QA PASS is preserved. Both correction QA workspaces were
removed using qa-sync. Frontend/Wails unaffected; no Vault/target deployment.

SI08-A DONE is limited to the approved contract foundation, pinned verified
artifact and tested codec/storage primitives. SI08-B NOT STARTED. Runtime
advertisement, roles, custody delivery/ACK, retention, Core descriptors and
UI integration remain later milestone obligations, not completed features.
