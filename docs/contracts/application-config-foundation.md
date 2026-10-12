# Application configuration and server type foundation

Version scope: `application-config/v1alpha1` and the original
`project-edit/v1alpha2` → `project-edit/v1alpha3` foundation. The sections below
retain the accepted foundation wording. Statements about emitted session versions
and the then-future UI-01E describe that scope; they do not override later command
versions or the [current project contract](../project-contract.md).
The original heading Planned contract is retained for traceability.
Current status: [CURRENT_STATE](../../CURRENT_STATE.md).

## Owner decision

`OWNER-APP-CONFIG-01`: Installer uses one versioned application configuration
contract for application/product behavior that is not portable infrastructure
desired state. Each server newly created by Installer requires one stable
`type` identifier; the normal UI selector is populated by that configuration.
Portable projects and the command boundary validate identifier grammar, not the
workstation's configured list. Grammar-valid unknown types are preserved and
produce only an Installer warning. Type is descriptive metadata and a
future template-matching input only; it does not select services, topology,
placement, an Execution Node, packages or sources.

`OWNER-APP-CONFIG-02`: `project-edit/v1alpha2` remains immutable.
`project-edit/v1alpha3` is an additive command-contract version in which
`CreateServer.type` is required. Both versions normalize into the same internal
Go `EditCommand`/server model; new Installer edit sessions emit v1alpha3 only.
A grammar-valid existing type absent from local application configuration
produces only a nonblocking Installer presentation diagnostic and cannot alter
Core snapshot semantics, status or fingerprint.

## Planned contract

The repository development source is `config/application.yml`, validated by
`contracts/application-config/v1alpha1/schema.json` and a strict typed Go
loader under `internal/appconfig`. Version 1 contains only a non-empty bounded
`serverTypes` list. Initial stable IDs are `infra`, `app` and `db`, with Russian
display labels. IDs use lowercase ASCII grammar
`^[a-z0-9][a-z0-9_-]{0,62}$`; labels and list size are bounded, and IDs are
unique (including case-insensitive collision checks).

Go exposes the typed application projection through the existing Wails backend;
React does not parse YAML. The development executable prefers the fixed
`build/bin`-relative repository file and accepts a working-tree fallback only
from a root marked by this repository's Go module. Config files and path
components must be regular and must not traverse symlinks/reparse points. Packaging,
override and distribution policy is deliberately deferred and documented as a
separate product decision.

If this file is missing, malformed or unsupported, the application does not
invent defaults. Read-only opening and Core snapshot retrieval remain
available, while the type selector and new v1alpha3 `CreateServer` fail closed
with a bounded safe application diagnostic and no canonical writes.

Canonical project representation is the optional read-compatible value:

```yaml
all:
  hosts:
    node-a:
      ansible_host: 192.0.2.10
      platform_host:
        type: infra
```

`platform_host.type` extends the existing host desired-variable schema and is
not part of host identity. Its schema validates grammar only and keeps the
field optional for legacy reads. Core copies the canonical ID into the existing
`ProjectSnapshot.hosts[node-a].type`; no localized label and no AppConfig data
enters Core or the portable project.

## Write and compatibility behavior

- `project-edit/v1alpha2` remains byte- and semantics-compatible and continues
  to accept its historical `CreateServer(hostId,address,sshPort?)` payload.
  `project-edit/v1alpha3` adds `type` and requires it for `CreateServer`.
  Both versions decode into the same Go `EditCommand`; no parallel Server DTO
  or lifecycle is introduced. New Installer edit sessions emit v1alpha3 only.
- For a v1alpha3 `CreateServer`, Go command validation and first-save
  serialization require a grammar-valid type. The normal UI offers the current
  AppConfig list, but absence from that local list is a nonblocking Installer
  diagnostic and never changes Core command or snapshot semantics.
- This foundation does not make general server CRUD available before UI-01E.
  When UI-01E implements managed-project create/update, it must reuse the same
  command and validation path. Update will preserve type unless an explicit
  typed replacement is supplied.
- Existing known types load normally. Existing grammar-valid types absent from
  current AppConfig remain readable and unchanged. Go computes a separate
  nonblocking Installer presentation diagnostic
  `UNKNOWN_CONFIGURED_SERVER_TYPE` by comparing the already returned snapshot
  host types with AppConfig. It is not a Core finding or portable validation,
  does not mutate the Core snapshot and does not change snapshot/validation
  status or `snapshotFingerprint`. Existing legacy
  hosts without type remain readable/incomplete and receive no default. They
  must be assigned explicitly before a future UI-01E rewrite of that server.
- Loading AppConfig or changing its list never writes project files. Display
  labels are never serialized into inventory. No migration or automatic
  backfill is introduced.


[Source scope](../work/application-config/application-config-server-types.md).
