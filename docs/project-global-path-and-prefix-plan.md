# Project data root and managed resource prefix

## Owner request

Add two portable project settings to the Settings screen and Ansible Core:

- `platform_data_root_directory`: default `/var/lib`; base for default data
  directories of services. An explicit service/member path
  remains authoritative.
- `platform_name_prefix`: empty project value adds no prefix; a nonempty value is prepended to
  service-owned target resource names, using the existing `-` or `_`
  separator for that resource.

The owner confirmed that both values belong to the portable project, even
though the current UI design describes Settings as application-local.

## Ownership and flow

Store project settings as ordinary Ansible variables in the existing
Installer-owned `inventory/group_vars/all/platform-installer.yml`. A standalone
Ansible project may provide them through normal inventory precedence. The
Go managed writer edits only these two validated fields in the existing
document and exposes them in its existing project view. React renders and
submits project edit commands through the existing Review/Save lifecycle.
No local application-config copy or new settings persistence is introduced.

The effective prefix is empty if `platform_name_prefix` is absent or empty;
otherwise it is the supplied token. A nonempty token must match
`^[a-z][a-z0-9_]{0,23}$`; the product adds `-` or `_` between that token
and the resource suffix according to the existing spelling of that resource.
Core validates the token for standalone projects and Go validates it before
Save. Each derived target name and path is also checked for its own length
and collision before target mutation. Internal API names, variable
names, collection/FQCN names, schema keys, catalog IDs, portable managed
document names and generated-state document names do not change. They are
contract identifiers rather than target resource names.

## Target resource inventory

The prefix sweep covers service-owned systemd units, users and groups,
configuration directories and files, persistent ownership markers, runtime
locks, DNS/HAProxy integration files, rootless Docker helper units and
service-specific logs. Installer PKI paths, trust anchors and application
runtime paths retain their existing names. A path/name must use the same
effective prefix in Apply, Verify, Clear, preflight, recovery, diagnostics and
standalone role defaults. Runtime-only Installer execution workspaces and
artifact cache names require a separate explicit decision because they are
Installer infrastructure rather than service/application resources.

The data-root sweep covers Kafka, Redis, ClickHouse, PostgreSQL and Vault
defaults. The owner deferred application data directories, which remain under
their current application account homes. It excludes Installer execution
runtime, workspace, cache and bootstrap locations by owner decision. The current `managed_data_path_guard`
allows only `/var/lib` under `/var`; a custom root requires the same guarded
absolute-path policy before any mutation. Kafka discovery/plan projection must
consume the same project variable and effective path as Apply/Verify.

The Services screen gets the effective directory from the target-free Core
configuration preview. Service packages declare which deployment/member
settings describe their data paths; Core projects the path from the selected
hosts' saved `platform_data_root_directory` and resolved placement. This is a
read-only presentation value: it does not alter desired state or Apply/Verify
precedence. The preview is for the last saved revision, so a project-setting
draft appears after Save. While a project-setting value is staged, the
Settings page highlights it, shows the staged value and states that Save in the
project header is still required. Explicit service and member paths remain
visible and authoritative.

Implementation correction (2026-10-11): the Wails-facing
`App.AppendEditCommand` allowlist must include `SetProjectSetting`, in addition
to the Installer writer's command validation. A rejected first command used to
discard the new edit session and clear its error, leaving Settings without
feedback. The operation is now accepted and first-command failures are shown
on Settings; focused Go and React regression tests cover both paths.

Implementation correction (2026-10-11, service-path preview): Ansible exposes
`hostvars` as a mapping proxy. The target-free Services preview had accepted
only a built-in `dict`, so it discarded `platform_data_root_directory` and left
both deployment and member paths deferred even when Core preview succeeded.
The preview now consumes the `Mapping` interface for hostvars and per-host
values. A regression test exercises nested mapping proxies and confirms the
`/data/qa-clickhouse` output. Bundle `si11-full-service-20261011-22` contains
the fix; UI acceptance after normal bundle rebind remains pending.

## Safety and acceptance

Changing a prefix after installation changes resource identity. The owner
will remove old deployments before rolling out this mechanism; the Installer
does not stop or migrate them automatically. A subsequent changed prefix
creates new prefixed resources without blocking solely because old resources
exist. Existing ownership and port checks for the new deployment remain.
The UI states that this setting changes resource names and does not migrate
old resources.
The existing owner-accepted risk of changing data-directory paths without
automatic data migration remains distinct and must be visible in the UI.

Check defaults against the current project, then a fresh project with custom
root/prefix, explicit service/member overrides, co-located members, standalone
Ansible inventory, Go Review/Save/reopen/Verify, real Wails handlers and
read-only RED OS projection. Do not mark installation acceptance from source
tests alone. Build/publish a new bundle only after the code and required gates
pass; do not activate it on a running installation implicitly.
