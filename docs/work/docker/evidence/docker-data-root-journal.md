# Docker data-root — 2026-10-25

Owner scope: add the Docker daemon data directory setting and expose an
override in the existing service editor. Contract:
[Docker data directory](../../../contracts/docker-rootless.md#docker-data-directory).

## Implementation

- `dataRoot` maps to ordinary role variable `platform_docker_data_root`.
  Default: `/home/{{ platform_docker_account_name }}/.local/share/docker`.
  The service manifest supplies the label, description and deployment scope;
  the existing React editor and guarded writer handle override/reset.
- Rootless configuration is the account's `.config/docker/daemon.json`.
  Apply retains unrelated JSON keys, writes `data-root` privately and notifies
  the existing restart handler. Paths reject traversal, links, unsafe ancestor
  ownership/modes, system paths and other users' homes. Existing data-root
  ownership must match the Docker account. No data migration or deletion.
- Verify reads the directory/configuration and checks the live daemon's
  `DockerRootDir`. Configuration content is processed under `no_log`.
- Generated schema/catalog and all 20 fixture project locks were regenerated
  by the standard generators on RED OS. Catalog digest:
  `sha256:56ab7904b254dea873e29a243f6af6263e5b3f2a4639118f7b2fa2d12fae6e60`.

The UI design, shared catalog/ownership rules, service mockup and existing
Docker plan were checked before implementation and again at editor acceptance.
This extends the existing setting contract without changing architecture or
introducing a Docker-specific React editor. No material design discrepancy.

## Focused verification

Current sources transferred with `scripts/qa-sync.ps1` to RED OS node1 as
`platform-automation`, using the existing runtime identity copy under
`.runtime/secrets/qa-existing-execution-identity.pem`, `IdentitiesOnly=yes`,
strict host-key validation and `sudo -n`. The procedure's older key path was
absent; the owner directed lookup under `.runtime/secrets/` and the existing
identity authenticated successfully. No password/admin fallback.

Source workspace: `/var/tmp/platform-installer-qa-456f5934994040b3af144fbd5bb33727`.
Source equality confirmed by the helper after generated outputs were retrieved.

| Check | Result |
| --- | --- |
| `services/docker/tests/test_data_root_runtime.py` | 5 PASS, 152.819s; real Ansible tasks in private temporary directories: missing config, JSON retention, repeat `changed=0`, read-only Verify, mismatch refusal, override without migration, invalid paths, symlink/writable ancestors, invalid JSON shape and linked configuration refusal |
| `test_service_configuration_*.py` | 39 PASS |
| `test_docker_execution_dispatch.py` | 2 PASS |
| Docker TLS-resolution native test | 1 PASS |
| Apply/Verify playbook syntax | 2 PASS |
| Schema and fixture catalog reproducibility | PASS |
| Go `internal/projectlifecycle`, `internal/installer` | PASS; initial combined invocation also named two nonexistent packages and returned setup failures for those names only |
| Go `internal/desktop -run 'Test.*(Catalog\|ServiceConfiguration\|Structural)' -count=1` | PASS |
| Frontend `npm ci --no-audit --no-fund`, `npm run build` | PASS; existing Vite large-chunk warning |
| `git diff --check` | PASS; generated frontend build noise removed |

## Actual React/Wails editor

An empty-runtime-input QA bundle was built on the trusted existing-runtime
acquisition node2, from the current sources transferred into
`/var/tmp/platform-installer-qa-f86d0a3eee65491094cdb15a0c8d1249`.
Version: `docker-data-root-qa-20261025`; bundle digest:
`sha256:cb32762a025d8905652007af1afc0b63275e12628e6d7103ce00080c86851513`.
It was verified/published through the standard publisher before Wails launch.
This editor-only bundle is not a production runtime closure.

The isolated project `Docker data-root QA` was created through React; its
Docker deployment/inventory were then seeded as a local fixture before the
affected editor flow. Only the native chooser was substituted with the known
fixture path. Actual handlers called real Go `AppendEditCommand`,
`ReviewStructuralEditSession` and `CommitStructuralEditPlan`; no writer or
save/start bypass was added.

- Default expression remains deferred without Core; the help states the
  account-based default. Reset is initially disabled.
- Editing `/data/docker-qa` and applying it to the draft did not change disk.
- Review returned READY; Save returned COMMITTED. Reopen showed the override.
  Saved revision:
  `sha256:761abd8980ae72c2b56a3f5515b711f19b530303ab9288ccdbc4a327e7b6fed0`.
- Reset used `RemoveServiceConfigurationOverride`; Review/Save/reopen removed
  only `dataRoot` and retained `accountName: platform-docker`.
  Final revision:
  `sha256:1dab180963581eaf0186cc3e28a3b33d71cd3f17c100d113f4f85de8c96ae687`.
- Screenshots at 1440×1000 and 1024×900 inspected: label, help, input and
  Apply/Reset controls visible; no overlapping controls. PASS.

Untracked reproducible evidence is under `.runtime/qa/docker-data-root-ui.cjs`,
`docker-data-root-ui-evidence.json`, `docker-data-root-ui1440.png` and
`docker-data-root-ui1024.png`. Early fixture/setup attempts exposed missing
inventory ownership/canonical host records, an old button selector and an
OpenProject navigation race; those QA setup issues were corrected. The final
full editor cycle passed. No production code was changed for automation.

## Cleanup and acceptance limits

No installation plan, approval, Start or target Docker restart was performed.
The live daemon has not been tested with the overridden directory. Full
production runtime closure publication/rebind and actual daemon Apply/Verify
remain separate acceptance gates.

The prior immutable bundle was preserved with filesystem hardlinks and fully
validated before temporary publication. After QA it was restored by the
standard publisher as the active cache:
`sha256:07ee125e7d274bb5434936378cb04f975aca009f46358e0f784821b52be8f25b`.
The isolated Wails/Vite processes were stopped by their verified identities.
Both temporary remote source workspaces were removed with `qa-sync.ps1`.
The local QA project, bundle and evidence remain available under `.runtime/qa/`.
