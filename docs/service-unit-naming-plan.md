# Service systemd unit naming plan

## Status and identity

- Milestone: `SERVICE-UNIT-NAMING-01`
- Status: implementation and focused QA complete; naming acceptance remains in the S11 full-service test
- Plan base revision: `82dc77b8b4123c549d9f82de02796d26fb716c34`
- Scope: deterministic names for service-role units in a fresh S11-00 QA baseline
- Non-goal: changing live servers in this planning/review step

## Owner decisions

The owner rejects hashes in operator-visible service unit names and requests a
consistent rule for service instances:

```text
platform-<service>@<deployment-id>-<numeric-instance-id>.service
```

Example: member `vault-1` in deployment `qa-vault-consumer` becomes
`platform-vault@qa-vault-consumer-1.service`.

The numeric instance ID is the terminal decimal suffix of the canonical member
ID (`vault-1` -> `1`, `clickhouse-3` -> `3`). It is not an ordinal derived
from sorted/list position and is not a hash. Missing suffixes, invalid unit
components, overlong names, or collisions on one host must fail closed before
service mutation. Separate process kinds use separate `<service>` components
(for example `clickhouse-server` and `clickhouse-keeper`; Kafka broker and
controller units are distinct only when they are distinct processes).

The accepted input grammar is deliberately strict and does not use systemd
escaping: deployment IDs used in unit names must match
`[a-z0-9][a-z0-9-]*`. The instance number is parsed only from the canonical
member ID's final `-<positive-decimal>` suffix; leading zeroes are rejected.
There is no ordinal, hash, or fallback derivation. Any value outside this
grammar blocks before mutation. Validate the complete assembled unit name,
including `@` and `.service`, against systemd's 255-character limit. Since the
accepted characters are ASCII, character and byte lengths are identical.

Before mutation, check the exact final unit names on each target host for
duplicates/collisions, using the service/process component as part of the
identity. In particular, distinct process units such as ClickHouse server and
keeper must not collide with one another or with another member's final name.

The requested service policy is:

| Service | Unit naming policy |
| --- | --- |
| HAProxy, BIND, DNS client, Keepalived | Keep the selected OS/package-provided singleton unit names |
| Docker rootless daemon | Keep `docker.service` in each Linux user's separate user systemd manager |
| Redis, ClickHouse, Vault, Kafka, PostgreSQL | Use the deployment/member instance naming rule above |

Docker's system-level bridge helper is a separate Installer-owned helper,
currently named by Linux account (`platform-docker-rootless-<user>.service`).
It is not the rootless daemon. The user accepted retaining this distinction;
the shared `platform-docker-lxc-ready.target` also remains unchanged. HAProxy
appeared twice in the original list and is treated once.

## Cause and current evidence

Vault currently computes the complete SHA-256 of `deployment-id + newline +
member-id` and uses it in `instance_name`. ClickHouse computes the same digest,
uses its first 16 hex characters in unit filenames, and stores the complete
identity digest in its member ownership marker. These are role-authored names,
not names synthesized by systemd. They were selected to distinguish multiple
deployment/member pairs but are not readable. Redis already uses template units
with a readable member ID. Other roles use package singleton names or their own
custom forms.

## Implementation boundaries

- Keep infrastructure behavior, deployment/member projection, and standalone
  Ansible execution in the roles/Core contracts. Do not implement naming in Go
  or React.
- Put the fixed naming policy with the service package/role, not in project
  input or a user-editable application setting. The policy is a product
  invariant, not per-project configuration.
- Keep hashes, where useful, only as internal ownership/fingerprint data; do
  not expose them in active unit names.
- Keep package-owned singleton units unchanged. Do not create one BIND,
  HAProxy, Keepalived, or DNS-client daemon per deployment.
- Keep Docker's per-user `docker.service` and its account-scoped bridge helper
  separate; this role currently supports one daemon per Linux account.

## Fresh-install behavior and test boundary

Automatic migration of old hash-named or other legacy units is explicitly out
of scope. The owner states that the naming check will happen during the next
full-service S11 run on the QA nodes after the bounded S11-00 cleanup.

S11-00 means the recorded Installer-free QA baseline in
[`service-install-11-cleanup.md`](service-install-11-cleanup.md), not a
pristine operating system image. It removes only the enumerated prior
Installer/QA service runtime and preserves OS-owned and other shared resources.
That cleanup is the precondition for this naming acceptance; it is not
implemented as an automatic service-role migration.

Before installing a per-instance unit, the role must validate the proposed
name and check for a conflicting prior unit. If a legacy hash unit or any
unowned/mismatched unit remains after S11-00, Apply must fail before service
mutation with a safe diagnostic. It must not rename, stop, delete or adopt that
unit automatically. The explicit S11-00 cleanup procedure remains responsible
for the bounded test reset.

On the fresh baseline, Apply installs and starts the new unit; the existing
service Verify checks it. The full-service run records the exact active unit
names for all requested per-instance services and confirms the obsolete
hash-form names are absent. No service plan is started as part of this code
change; naming acceptance occurs only in the separately approved S11 full
service run.

## Verification matrix

- Unit/name derivation: exact examples; accepted deployment-ID grammar;
  terminal positive-number extraction; missing/malformed suffixes and leading
  zeroes; rejected characters; exact 255-character boundary; and same-host
  collisions across members and process kinds.
- Multi-instance examples: two ClickHouse members on one host, multiple Vault
  members on one host, Kafka split controller/broker roles, and distinct
  deployments with the same numeric member ID.
- Role contracts: Apply/Verify/Clear and cross-unit dependencies reference the
  exact new name; package singleton services remain unchanged; Docker daemon
  and account-scoped bridge remain distinct.
- Fresh baseline: document S11-00 completion; verify no prior Installer/QA
  runtime remains, without claiming a pristine OS.
- Naming acceptance: assert exact new unit names, service health, absence of
  legacy hash-form units, and that any unexpected/foreign unit blocks before
  service mutation and is preserved.
- Run focused service role and Core contract tests, standalone syntax checks,
  then the required real React/Wails/Core flow before claiming service-level
  acceptance. RED OS remains the primary Core QA target.

## Known acceptance gap

Roles now derive deterministic member-scoped units for Vault, ClickHouse,
Redis/Sentinel, Kafka and PostgreSQL. Their apply, verify and clear paths use
the resolved names; validation rejects invalid member suffixes, overlong names
and host-local collisions before Kafka artifact delivery. Existing final unit
paths are checked for regular-file type and an exact role ownership marker;
symlinks and foreign files are rejected before they can be overwritten.
Legacy role-generated units are not migrated or adopted: the role fails closed
with a safe diagnostic and leaves them intact.
Package-owned singleton services and Docker naming were not changed.

Focused QA on the RED OS test VM passed: 97 existing/new Python contract tests,
syntax checks for the Apply/Verify/Clear playbooks in scope, and the ClickHouse
standalone/three-member topology contract (including exact expected unit names).
The source tree was synchronized from this working copy into a temporary QA
workspace; no target service hosts were changed. `S11-00` cleanup and the
real React/Wails full-service naming acceptance have not been run. The prior
SI11 installation result does not prove the new unit names. The next naming
acceptance remains a separately approved full-service S11 run on the recorded
S11-00 baseline; no automatic unit-name migration is part of acceptance.
