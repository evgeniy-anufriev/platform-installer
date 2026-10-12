# Application configuration foundation checkpoints

Historical audit and acceptance from [the foundation plan](../application-config-server-types.md).
These statements refer to its original version/scope. Current implementation and
owner decisions are recorded in [CURRENT_STATE](../../../../CURRENT_STATE.md).

## Recorded review and acceptance status


Status: accepted. PLAN review returned `APPROVE_WITH_CHANGES` with zero
blocking findings. The FULL DIFF review found one v1alpha3 parity blocker;
the single permitted TARGETED_RECHECK verified it `RESOLVED` and returned
`APPROVE`. Core-contract and safety rechecks returned `PASS`; all final reviews
have zero unresolved blocking findings. This work does not start UI-01E or
UI-01H.

## Current contract audit

- Canonical server identity is the inventory host ID. Connection data is held
  by normal inventory variables such as `ansible_host` and `ansible_port`.
- `project-edit/v1alpha2` already owns one typed `CreateServer`, `UpdateServer`
  and `DeleteServer` command family. `EditCommand` is the corresponding Go
  type; no parallel Server command or DTO will be introduced.
- UI-01D currently implements only first-save `CreateServer`; general managed
  project CRUD remains UI-01E work.
- The first-save writer owns and deterministically serializes
  `inventory/hosts.yml`. Core reads host variables and projects each host into
  the existing `ProjectSnapshot.hosts[hostId]` object. Service and topology
  references continue to use host ID and are independent of type.
- Historical fixtures and projects have no server type. Making the field
  structurally required on read would invalidate accepted portable projects.

## Implemented acceptance evidence

Implemented acceptance evidence:

- local `go test ./...` and `go vet ./...` pass;
- frontend tests (7), lint and production build pass;
- `wails build -nopackage -clean` produces the Windows executable;
- RED OS contract tests (8), target-free snapshot acceptance (`changed=0`) and
  full Core suite (241, 4 skipped) pass;
- fixture catalog and configuration schemas are reproducible;
- network-isolated `validate.yml` passes on localhost with `changed=0` and no
  target contact.
- architecture TARGETED_RECHECK, Core-contract review and safety review each
  report zero unresolved blocking findings; mandatory overengineering review
  reports zero findings.


[Source scope](../application-config-server-types.md).
