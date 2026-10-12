# UI-01I — portable export and reopening

Document scope: the original milestone contract/design. Historical status, review
and QA checkpoints are collected separately; current status and authorization
are recorded only in [CURRENT_STATE](../../../CURRENT_STATE.md).

Recorded status and review scope: [historical checkpoint](evidence/documentation-checkpoints-20261012.md#ui-01i-checkpoint-002).

UI-01I publishes only a saved full Installer-managed configuration into a new,
empty native directory. It has no archive/template/import mode and never
overwrites or adopts an existing destination. The in-memory export capability
retains the opened source and destination authorities from Preview through the
single Commit attempt; it exposes document metadata but never document content.

The portable allow-list copies `project.yml`, optional `ansible.cfg`,
`inventory/hosts.yml`, and owned `inventory/group_vars` / `inventory/host_vars`
documents. Runtime credentials, drafts, generated state, execution workspaces,
plans, facts, journals, results and verification evidence are excluded. The
output is then opened only through the normal read-only `OpenProject` path.

## Final security correction

The implementation review found and the owner authorized exact corrections for
three export-boundary defects. The one permitted targeted recheck approved all
three with zero blocking and zero overengineering findings:

- `UI01I-DIFF-001`: source and destination roots now open from a trusted
  platform anchor and are traversed component-by-component through no-follow,
  handle-relative operations. No pre-open ancestor check authorizes a later
  pathname open.
- `UI01I-DIFF-002`: Linux does not perform pathname-based recursive staging
  cleanup when it cannot prove a final unlink remains bound to its owned open
  object. It fails closed and retains staging rather than risk deleting a
  swapped sibling. A Linux race test exchanges staging with a marker-bearing
  sibling and proves that marker survives.
- `UI01I-DIFF-003`: after successful export the dialog explicitly offers
  **Открыть экспортированный проект**. A successful normal open becomes the
  current project; an open failure keeps the completed export intact and shows
  only a safe error.

The targeted verdict applies to HEAD `17a3472` plus correction fingerprint
`031953fc08f5812cfd103d5555d558d58fbc4fd0a31895bec0b3ae1efe966b1f` before
this evidence-only update.

## Acceptance evidence

See [historical checkpoint](evidence/documentation-checkpoints-20261012.md#ui-01i-checkpoint-001). Current status: [CURRENT_STATE](../../../CURRENT_STATE.md).
