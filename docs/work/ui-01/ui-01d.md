# UI-01D — first write and edit/review session

Document scope: the original milestone contract/design. Historical status, review
and QA checkpoints are collected separately; current status and authorization
are recorded only in [CURRENT_STATE](../../../CURRENT_STATE.md).

Recorded status and review scope: [historical checkpoint](evidence/documentation-checkpoints-20261012.md#ui-01d-checkpoint-003).

UI-01D adds the shared Go-owned transient edit/review/commit lifecycle and the
narrow first-save UI required to turn a metadata-only managed project into a
complete minimal Ansible project. It does not add the full server, topology,
PKI or service editors and does not start an installation.

## Accepted boundary

- React renders form/session/plan/result state and calls generated Wails
  bindings; it does not parse or write YAML.
- Go owns the bounded in-memory session, candidate assembly, revision-bound
  plan, guarded transaction, rollback/recovery and explicit discard.
- the selected READY Execution Node runs the fixed candidate
  `BuildProjectSnapshot` operation; Core remains authoritative for the
  target-free project snapshot and infrastructure semantics;
- the candidate request is the closed nested
  `platform.installer/project-snapshot-request/v1alpha1` contract and is used
  only after capability negotiation. Older nodes fail without candidate
  staging or silent downgrade;
- the first commit creates only `ansible.cfg`, `inventory/hosts.yml` and
  `inventory/group_vars/all/platform-installer.yml`. `project.yml` and unknown
  files are byte-preserved. No credentials, implicit localhost or empty
  `platform_targets` project is committed.

## Real acceptance

See [historical checkpoint](evidence/documentation-checkpoints-20261012.md#ui-01d-checkpoint-001). Current status: [CURRENT_STATE](../../../CURRENT_STATE.md).

## Regression evidence

See [historical checkpoint](evidence/documentation-checkpoints-20261012.md#ui-01d-checkpoint-002). Current status: [CURRENT_STATE](../../../CURRENT_STATE.md).

## Deferred scope

UI-01E owns the full server editor, session credentials and Execution Node
selection/preparation panel. UI-01F–H own topology, PKI and service forms.
UI-02 owns installation planning/execution/progress/result composition. No
later milestone was started by UI-01D.

## Additive server-type foundation

The later `OWNER-APP-CONFIG-01/02` decision preserves this milestone's
published v1alpha2 evidence and payload compatibility. Current new Installer
sessions now emit additive `project-edit/v1alpha3`; its first-save
`CreateServer` requires a grammar-valid type; the normal selector is populated
from Go-loaded application config and writes only the stable ID to
`platform_host.type`. A type absent from the local list is warning-only. The existing narrow form
adds that one selector so the accepted first-save path remains usable. This is
not general add/edit/remove server UI and does not start UI-01E.
