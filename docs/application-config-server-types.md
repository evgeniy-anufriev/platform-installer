# Application config and required server type foundation

Status: accepted. PLAN review returned `APPROVE_WITH_CHANGES` with zero
blocking findings. The FULL DIFF review found one v1alpha3 parity blocker;
the single permitted TARGETED_RECHECK verified it `RESOLVED` and returned
`APPROVE`. Core-contract and safety rechecks returned `PASS`; all final reviews
have zero unresolved blocking findings. This work does not start UI-01E or
UI-01H.

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

## Implementation and verification

1. Add the minimal schema, repository config and strict Go loader/error model.
2. Add additive `project-edit/v1alpha3`, retain v1alpha2 unchanged, and extend
   the shared edit command, backend validation and first-save writer. The
   existing UI-01D first-save form receives only the minimal AppConfig-backed
   type selector needed to keep that already shipped flow functional with new
   v1alpha3 sessions; full server CRUD remains UI-01E.
3. Extend the existing host desired schema and snapshot projection only.
4. Expose AppConfig through the current App/Wails service and add bounded
   unknown/missing-type presentation warnings without adding UI-01E forms.
5. Add loader, command, compatibility, snapshot and no-mutation tests. Update
   contracts and durable architecture/UI documentation.
6. Run Go test/vet, affected frontend checks if generated bindings change,
   contract/schema checks, focused Core snapshot tests on RED OS when required,
   secret audit and `git diff --check`.

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

Future template export may derive display slots such as `infra-1`, `infra-2`
and `app-1`, but a slot is never canonical host identity and import assignment
will remain explicit. No template generation or matching is implemented here.

## Non-goals and overengineering guard

No settings database, arbitrary map, remote config service, feature framework,
migration engine, template subsystem, automatic placement, service defaults,
topology/PKI rules, credentials, target addresses or Execution Node policy is
added. One YAML document, one schema, one small loader and extensions to the
existing command/snapshot paths are sufficient.
