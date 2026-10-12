# UI-01E3 — Shared runtime session credentials architecture

Status: **OWNER-APPROVED PLAN; ADDITIONAL REVIEW WAIVED (2026-09-14)**. This
milestone adds one write-only, runtime-only technical credential for all target
servers in the currently open project. It does not contact targets, prepare an
Execution Node, change project files or implement execution-time secret
transport.

## 1. Goal

Provide the credential input already represented by the Servers mockup without
turning credentials into portable desired state:

```text
Servers session credential form
        ↓
generated Wails binding
        ↓
Go RuntimeSecretBroker (one project-bound lease)
        ├── SSH password OR private-key bytes
        └── optional sudo password

portable project / snapshot / EditSession / review / journal
        → no secret value, local key path or session credential reference
```

One technical username and one authentication choice apply to every target
server in the project. Per-host credentials are not introduced.

## 2. Accepted inputs and discrepancies

This plan was checked against `docs/design/ui-design-01-mockups.html`,
`docs/design/ui-design-01.md`, `docs/work/ui-01/ui-01.md`,
`docs/work/ui-01/ui-01a-contract-freeze.md`, the completed E1/E2 architecture and the
current implementation.

The relevant mockup element is the compact **Session credentials — for all
servers** control above the independently scrolling server list. The Execution
Node panel, readiness checks, connection checks and discovered facts remain
E4/E5 scope.

The UX document says a server record may contain an opaque `SecretRef`. That
does not apply to the shared E3 session credential. The accepted UI-01A freeze
is authoritative for E3: credential material is held only by a runtime broker
and never enters the portable project. The broker may create an opaque internal
`runtime:ssh-session-<32-hex>` reference for a future trusted Go consumer, but
E3 never exposes it through Wails/React and never writes it to `project.yml`,
inventory, `group_vars`, `host_vars` or generated state.

The current repository has no application runtime-secret broker. Existing
`executionnode.IdentityResolver` resolves the separately configured trusted
Execution Node identity and is not a target-session credential store. E3 must
not overload that resolver or the current desktop command-line flags.

After the initial approved review cycle, the owner made two binding
corrections: E5 is independent of the E3 target lease until UI-02 transport
exists, and the internal broker reference is not part of Wails/React status.
The owner explicitly waived an additional architecture review of this revised
plan.

## 3. Scope and non-goals

E3 includes:

- one project-bound technical username;
- exactly one SSH authentication mode: `SSH_PASSWORD` or `SSH_PRIVATE_KEY`;
- an optional, separate sudo password;
- explicit replacement and clearing;
- one-hour expiry from credential set/replacement and lifecycle cleanup;
- status-only Wails queries and Servers-page rendering;
- safe, bounded ingestion of a user-selected private-key file;
- negative tests proving non-disclosure and zero project mutation.

E3 excludes:

- per-host usernames, passwords, keys or credential references;
- target SSH probes, host-key trust, facts or preparation;
- Execution Node selection, bottom panel and auto-selection — E4;
- readiness and preparation — E5;
- sending target secrets to the Execution Node;
- `PutRuntimeSecretLease/v1alpha1`, Ansible connection-variable
  materialization and terminal/cancel recovery — UI-02;
- Windows Credential Manager, keychain, SQLite, preferences, local files or any
  other durable secret storage;
- project edit commands, review-plan fields or Core contract changes;
- encrypted-private-key passphrase support until an execution consumer and its
  cleanup contract are implemented.

No E3 action is an edit-session action. Setting or clearing credentials neither
starts nor invalidates an `EditSession` and never enables a blocked project
commit.

## 4. Credential boundaries

E3 distinguishes two trust boundaries:

| Credential | Purpose | Owner | E3 behavior |
| --- | --- | --- | --- |
| Target session credential | SSH/elevation for all desired target servers | RuntimeSecretBroker | Capture and hold locally only |
| Execution Node credential | Trusted workstation-to-Execution-Node transport | Existing application binding / IdentityResolver | Unchanged |

The two credentials may happen to have equal values in a particular
environment, but the application never aliases, copies or reuses one as the
other implicitly. Selecting a target server as the future Execution Node does
not merge these leases.

The optional sudo password is distinct from the SSH password. The UI may offer
an explicit **same as SSH password** choice in password mode, but unchecked or
absent input never implies equality. The broker records the resulting secret
bytes in separate fields inside the same lease.

E4/E5 do not consume the E3 target credential. E5 checks and prepares only the
selected Execution Node through its separate trusted application binding. Any
`sudo -n` probe or elevation requirement in E5 therefore belongs to that
Execution Node binding and cannot use E3 password/key material or derive a
blocker from E3 availability. Target-host credential transfer, elevation checks
and preparation remain blocked until UI-02 implements the approved remote
secret-lease transport.

## 5. Contract

The existing accepted contract name remains `SessionCredential/v1alpha1`.
UI-01A accepted its architecture name, but no external client or production
implementation has published that runtime contract. The owner-approved sudo
field therefore becomes part of its first implementation rather than creating
an additive `v1alpha2`. Core and portable-project contracts are unchanged.
There is one model and one broker; password and private-key modes do not create
parallel credential DTOs or stores.

Conceptual write request:

```text
SessionCredentialInput/v1alpha1
  username                 required
  ssh.mode                 SSH_PASSWORD | SSH_PRIVATE_KEY
  ssh.password             write-only; password mode only
  ssh.privateKeyPath       one-shot local input; key mode only
  elevation.mode           NONE | SUDO_PASSWORD
  elevation.password       write-only; sudo mode only
```

`privateKeyPath` is not credential state. It is a path explicitly selected by
the operator and consumed synchronously by Go. Go opens one bounded regular
file, reads its bytes into the broker and immediately drops the path. The path
is never returned, retained in application state, copied into a project or
included in errors. E3 does not create a second private-key file.

Conceptual status response:

```text
SessionCredentialStatus/v1alpha1
  status                   MISSING | PRESENT | EXPIRED
  username                 safe metadata, when PRESENT
  sshMode                  safe metadata, when PRESENT
  sudoPasswordStatus       NOT_PROVIDED | PRESENT
  expiresAt                when PRESENT
```

The response contains no password, key bytes, key path, internal reference,
hash, length, preview or value-derived diagnostic. The opaque reference remains
private to the Go broker and a future trusted UI-02 consumer; React cannot read
or interpret it.

Wails application operations are:

```text
SetSessionCredential(input) -> SessionCredentialStatus
GetSessionCredentialStatus() -> SessionCredentialStatus
ClearSessionCredential() -> SessionCredentialStatus(MISSING)
```

All operations require an open project. The broker binding uses both canonical
project root and project identity so that copied projects with equal IDs cannot
share a credential accidentally.

Stable safe errors include:

```text
PROJECT_NOT_OPEN
SESSION_CREDENTIAL_INPUT_INVALID
SESSION_CREDENTIAL_MODE_INVALID
SESSION_CREDENTIAL_TOO_LARGE
SESSION_PRIVATE_KEY_UNREADABLE
SESSION_PRIVATE_KEY_NOT_REGULAR
SESSION_PRIVATE_KEY_INVALID
SESSION_PRIVATE_KEY_ENCRYPTED_UNSUPPORTED
SESSION_CREDENTIAL_UNAVAILABLE
```

Errors never interpolate username, path, secret text or parser output.

## 6. Validation and bounds

Go is authoritative for application-level input shape:

- username is non-empty after surrounding-space normalization, valid UTF-8 and
  bounded to 255 bytes; it is not parsed as a shell fragment;
- exactly one SSH mode is selected;
- password mode requires a non-empty password and rejects a private-key path;
- private-key mode requires one non-empty absolute path and rejects an SSH
  password;
- sudo mode `SUDO_PASSWORD` requires a non-empty separate value;
- mode `NONE` rejects supplied sudo-password bytes;
- passwords are bounded to 4 KiB each;
- private-key input is one regular file bounded to 1 MiB;
- files, directories, devices and reparse/symlink targets that cannot be proven
  to be one readable regular file are rejected safely.

E3 does not authenticate the credential or infer target capability. Every
private key is parsed before publication with the Go standard-library parser;
the first implementation accepts unencrypted regular PEM RSA/ECDSA private
keys and deliberately rejects other encodings rather than expanding the
vendored dependency graph for a UI-only session cache. Invalid input returns
`SESSION_PRIVATE_KEY_INVALID`; encrypted input returns
`SESSION_PRIVATE_KEY_ENCRYPTED_UNSUPPORTED`. Parser messages and key-derived
details are never returned. Encrypted-key passphrases are not requested,
persisted or guessed until that mode has an approved execution contract.

## 7. RuntimeSecretBroker lifecycle

The broker is an application-scoped Go object with one active lease because the
desktop application has one current project context. It is not a map of durable
projects and not a generic secret manager.

The lease contains only:

```text
project binding
opaque reference
username
SSH mode and secret bytes
optional sudo secret bytes
last trusted use time
expiry time
generation
```

Concurrency is bounded by the existing `App.editMu`, one broker mutex and one
replaceable expiry timer. All `SetSessionCredential`,
`GetSessionCredentialStatus`, `ClearSessionCredential`, `CreateProject`,
`OpenProject` and `CloseProject` operations are serialized by `App.editMu`.
Bounded synchronous private-key ingestion and publication happen within that
application operation, so a completed project switch cannot be followed by a
late publication for the previous project. The fixed lock order is
`App.editMu` then broker mutex. The timer callback acquires only the broker
mutex and never calls App or acquires `App.editMu`.

Setting a new credential validates and fully constructs the replacement before
swapping it under the broker lock; the previous lease is then cleared. A failed
replacement leaves the previous valid lease intact. No new coordinator,
project-context transaction or generation subsystem is added above App.

The lease expires one hour after credential set/replacement. Credential reads,
status polling, page rendering and navigation do not extend this fixed deadline.
The timer validates the lease generation before clearing it so an old callback
cannot erase a replacement.

Expiry overwrites and drops all secret byte slices and the opaque reference,
then retains only a non-secret in-memory marker containing the same project
binding and expiry time. Status returns `EXPIRED` from that marker. Explicit
clear, successful project close/switch and replacement remove the marker;
`MISSING` means neither a live lease nor a matching expiry marker exists. The
marker is never persisted or included in project state.

The lease is cleared on:

- explicit `ClearSessionCredential`;
- successful replacement;
- expiry (secret bytes and reference; a non-secret marker remains);
- successful project close;
- successful switch to a different project root/identity;
- application shutdown.

A failed open/create/switch attempt leaves the current project and its lease
unchanged. Project navigation within the same project does not clear it.

Go can overwrite broker-owned byte slices on clear as best effort, but the
architecture does not promise impossible complete memory erasure across Go,
WebView and OS copies. The enforceable guarantees are bounded lifetime, no
durable write, no value-return API and no logging.

## 8. UI behavior

The Servers page receives a compact credential panel above the server-list
scroll area:

```text
Credentials for this session — used for all servers
Technical user       [ platform-automation ]
SSH authentication   [ Password | Private key ]
Password              [ ******** ]
or private key        [ Select file ]
Sudo                  [ No password supplied | Requires password ]
Sudo password         [ ******** ]
                      [ Save in session ] [ Clear ]
Status                Available until … | Missing | Expired
```

The exact label is **Save in session**, not project **Save**. Help text states
that values apply to every server, exist only in the current application
session and are not written to the project.

After a successful set, password fields and the transient selected path are
cleared from React state immediately. Cancel, modal close, project switch and
component unmount also clear unsent values. The UI never repopulates a secret
from status.

`MISSING` and `EXPIRED` are informational in E3. They do not block server CRUD,
Review, Core validation or Commit. The panel does not display fake connection,
sudo or readiness PASS states.

The server Add/Edit dialogs remain credential-free. There is no per-row
credential icon that could imply different credentials per host.

## 9. App and project lifecycle integration

`App` receives one broker during construction. It exposes only the three fixed
Wails operations and status DTO. There is no generic secret CRUD API.

Each credential operation acquires the existing `App.editMu` before reading
current project context or entering the broker. Private-key validation/read is
completed while that lock still binds the operation to the current project.
Project lifecycle operations already use the same lock and clear the broker in
the same critical section after a successful context replacement. Broker timer
callbacks never acquire or wait for `App.editMu`, preventing reverse-order
deadlock.

Project lifecycle integration is explicit:

- after a successful `CreateProject` or `OpenProject` that replaces the current
  project, clear the previous binding before publishing the new context;
- `CloseProject` clears only after the close operation is accepted;
- failed project operations preserve the current binding;
- application shutdown always calls broker close/clear;
- `CurrentProject`, snapshots and application diagnostics do not embed
  credential status; the Servers page requests it from the separate secrets
  facade.

The Wails application adds an `OnShutdown` hook for deterministic cleanup. No
background service, worker queue or persistence layer is introduced.

## 10. Security and failure behavior

- Write requests and broker methods must never use general-purpose structured
  logging of the request object.
- Panic/error formatting must not include input DTOs.
- Secret values must never appear in returned errors, diagnostics, plans,
  snapshots, execution events, local mirrors or test failure messages.
- Password/key material is never passed through argv, environment variables or
  command interpolation.
- Private-key reads are local and synchronous; no target or Execution Node is
  contacted.
- Replacement is all-or-nothing. Invalid SSH or sudo input does not partially
  replace one field.
- Clear is idempotent and returns `MISSING`.
- Expired status cannot be used to resolve a secret internally.
- A stale expiry callback cannot clear a newer generation.
- Project save and credential replacement are independent; neither is rolled
  back because the other fails.

The future UI-02 trusted Go transport may resolve the internal opaque reference
directly from the broker and must implement `PutRuntimeSecretLease/v1alpha1`
before target execution. Neither Wails nor React participates in that
resolution. E3 deliberately provides no export method returning a reference or
raw bytes to React or a generic caller.

## 11. Implementation slices

1. Add one bounded `internal/runtimesecret` broker with deterministic clock and
   expiry-timer seams; add focused lifecycle, replacement and concurrency tests.
2. Add the fixed input/status DTOs and three Wails application operations;
   integrate successful project replacement, close and application shutdown.
3. Add private-key file ingestion through the same setter and broker, with
   regular-file/size/error-sanitization tests.
4. Add the Servers session panel, password/key/sudo modes, status-only rendering
   and immediate clearing of transient form state.
5. Add Go/App/frontend tests for project binding, expiry, failed replacement,
   navigation, accessibility and no effect on E2 edit sessions.
6. Recheck the mockup and execute E3 acceptance and regression gates before
   updating milestone state.

## 12. Acceptance

Automated and native Windows tests must prove:

- one password credential is held as one broker lease for all projected
  targets, without per-host records or a Wails-visible reference;
- private-key mode reads the selected file once and retains bytes, not path;
- optional sudo password is independent and status exposes presence only;
- explicit same-as-SSH choice works only when selected;
- invalid/oversized/unreadable input is rejected without replacing a valid
  lease;
- replacement invalidates the previous internal broker reference;
- clear, expiry, project close, successful project switch and process shutdown
  remove availability;
- failed project switch preserves the current lease;
- status polling and navigation do not extend expiry;
- old timer callbacks cannot erase a replacement;
- concurrent Set versus successful Close/Open/Create cannot publish a lease
  after project replacement, while a failed switch preserves the current
  lease;
- after a Set/project-lifecycle race, no credential for the previous project
  becomes available by reopening that project;
- server CRUD, Review and Commit work with missing or expired target
  credentials;
- project file digests are unchanged across set, replace, expire and clear;
- snapshots, plans, frontend state after submit, errors and logs contain no
  secret, private-key path or value-derived material;
- target and Execution Node transports receive zero calls from E3 operations;
- E4/E5 behavior and Execution Node readiness do not depend on E3 availability;
- no credential values or references are added to portable project files.

Required gates:

```text
focused broker and App tests
frontend session-credential component tests
go test ./...
go vet ./...
go test -race for affected Go packages
frontend test / lint / production build
wails build -nopackage -clean
changed-file secret audit
git diff --check
```

Core, service and RED OS target tests are not required unless implementation
changes those boundaries. UI-01E3 performs no remote acceptance because it has
no approved remote secret transport or target operation; E6 owns combined
Windows/RED OS acceptance after E4/E5.

## 13. Overengineering guard

E3 introduces one small broker because secret lifetime and non-disclosure
cannot be owned safely by React state or the portable project. It reuses one
accepted `SessionCredential/v1alpha1` concept and creates no generic vault,
provider registry, per-host map, database, encrypted local store, secret-event
bus or background worker.

The existing App mutex plus the single broker mutex/timer are required for
project replacement and expiry safety. A poll-only lazy expiry would leave
expired bytes resident indefinitely when status is not queried. A separate
coordinator, project-context generation transaction, scheduler subsystem or one
goroutine per consumer is unnecessary and excluded.

Private-key selection uses the same setter and broker rather than a pending
selection token, staging store or second credential lifecycle. The Go
standard-library PEM parser gives deterministic structural validation without a
custom key model or new dependency. Durable OS credential-store integration and encrypted-key
passphrases remain separate owner decisions backed by a concrete consumer.
