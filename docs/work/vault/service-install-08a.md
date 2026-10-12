# SI08-A — contract foundation

<a id="si08-a--contract-foundation-done"></a>

Document scope: the original milestone contract and constraints. Historical
results are linked separately; current status and authorization are recorded
only in [CURRENT_STATE](../../../CURRENT_STATE.md).

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

Recorded evidence: [historical checkpoint](evidence/documentation-checkpoints-20261012.md#service-install-08a-reconciliation-001). Current status: [CURRENT_STATE](../../../CURRENT_STATE.md).

## Exact SI08-A closure boundary (2026-09-26)

Recorded evidence: [historical checkpoint](evidence/documentation-checkpoints-20261012.md#service-install-08a-reconciliation-002). Current status: [CURRENT_STATE](../../../CURRENT_STATE.md).

The architecture §9 defines A as owner decisions, a pinned verified artifact,
checked contract gaps and closed manifest/settings/secret contracts. It does
not define A as a Vault deployment or completion of every B–E implementation.
The storage/codec foundation above is progress, not proof of those entire gates.

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

Input/secret integration contract: [typed contract freeze](service-install-08a-secret-contracts.md).

## Initial implementation DIFF result — BLOCK (2026-09-26)

Recorded evidence: [historical checkpoint](evidence/documentation-checkpoints-20261012.md#service-install-08a-reconciliation-003). Current status: [CURRENT_STATE](../../../CURRENT_STATE.md).

## Owner-approved correction and closure (2026-09-26)

Recorded evidence: [historical checkpoint](evidence/documentation-checkpoints-20261012.md#service-install-08a-reconciliation-004). Current status: [CURRENT_STATE](../../../CURRENT_STATE.md).

Canonical deployment grammar is now identical in output schema and Go,
with a 128-character bound. Python schema/publish/Fetch and Go tests cover
hyphen, dot, underscore, max length and rejected identifiers. Exact metadata
keys are checked before Go struct decode; changed-case aliases fail closed.
