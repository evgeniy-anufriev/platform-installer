# SDKU: HTTP port ENV in application defaults

Date: 2026-10-19. Owner authorized moving `WEB_SERVER_PORT`, `SERVER_PORT` and
`server.port` from Compose-specific substitutions to application defaults,
bound to effective `port-1`. No application installation/restart authorized.

## Implementation

17 application packages with these HTTP variables updated. Each defaults file
has one expression merging package ports, slot, instance and host overrides;
required ENV aliases share its `port-1.container` value. Static `SERVER_PORT`
values removed. `published` remains independent. Compose uses its existing
generic ENV loop; special exclusions/substitutions removed. Existing
alarm-view-service `TNT_DEMO_CLIENT_PORT` binding preserved through the same
alias. The pre-existing removal of alarm-service's explicit
`TNT_DEMO_CLIENT_PORT` was preserved. Frontends and evo-manager's distinct
configuration were not changed. Import catalog package digests refreshed.

No production Core/Go/UI changes, new Python scripts, runtime publication or
new configuration layer. Explicit ENV overrides remain supported; resetting
them restores the calculated defaults.

## Validation

- Current-tree transfer to trusted RED OS102 through `scripts/qa-sync.ps1`:
  `/var/tmp/platform-installer-qa-37a245dd0ec34c318fb6858ae184d455`.
- Real unchanged `resolve_application_libraries` role and builtin Ansible
  template/from_yaml/assert: 17 packages x3 hosts, 51 resolved/rendered rows,
  566 tasks, changed=0, failed=0. Covers package defaults, KNP instance
  container18281/published28281, host2 container18002/published28002 overriding
  instance settings, and explicit DM SERVER_PORT19999 preserved independently.
- Reset: removed instance port/ENV overrides and host port overrides for DM
  and KNP; 2 apps x3 hosts, 71 tasks, changed=0, failed=0. All aliases and the
  rendered Compose returned to package `port-1.container` defaults.
- Real React handlers/Wails Go on an isolated copy of the accepted KNP project:
  OpenProject, credential/trust setup, Project Verify VERIFIED and fresh plan
  EXECUTABLE. Saved revision
  `sha256:eaaedf93828002ac6d60521bc96ec8e90b782f7e10cc0ce2c788ab8840b498a2`;
  plan `plan-e5e342ef1a7ccc65f487b5e3`; existing runtime40
  `sha256:687d7e459a719222889025ede43b6ad0c3eb1501e60706d561e54c6a28256e25`.
  Exactly Library Apply/Verify actions, skipInfrastructureVerify=true.
  No Approve/Start, no execution run and no infrastructure Verify. Existing
  project-specific Sentinel/account bindings retained; only the port refactor
  applied to this representative UI fixture. No visual acceptance claim.

Initial QA-only failures retained in `.runtime/qa`: copied dynamic URL defaults
in group_vars caused recursion; synthetic application entries lacked endpoint
metadata; the template check initially retained the previous application
identity. Corrected fixture/context, reran the unchanged Core. An initial UI
fixture copied unrelated raw packages and lost its accepted project-specific
files/account connections; corrected by retaining those and applying only the
port refactor. No production bypass, binding/security change or hidden failure.

Evidence: `.runtime/qa/sdku-web-port-native-overrides.log`,
`.runtime/qa/sdku-web-port-native-reset.log`,
`.runtime/qa/application-design/sdku-web-port-ui-plan.json`,
`.runtime/qa/sdku-web-port-ui-plan.log`,
`.runtime/qa/sdku-web-port-sync-verify.log`.

Catalog digest consistency and diff whitespace checks PASS. QA-sync source
verification PASS; temporary remote workspace cleaned with the same helper.
Existing application containers/configuration were not changed or restarted.
