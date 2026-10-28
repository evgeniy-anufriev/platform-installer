# QA execution procedure

Read before Core/service QA, real WebView acceptance, or stopping the exact build output for a rebuild.
These are mandatory procedures routed by [AGENTS.md](../../AGENTS.md).
They do not authorize a new milestone or target mutation.

## Test Execution Environment

For every service and affected application flow, acceptance MUST include
nonvisual React/Wails integration: invoke the actual React handlers/bindings
against real Wails Go methods and, where relevant, the supported Execution Node
Core/Ansible path. Use the existing bounded automation seam; do not add a
production bypass, arbitrary command bridge or test-only save/start path.
Direct Go harnesses and frontend tests with mocked bindings are supplementary,
not substitutes for this gate. Record the invoked flow, saved revision, run IDs,
terminal results and safe event/output evidence. Visual/manual UI inspection is
separate and is not required by this nonvisual gate; never report it as PASS
without performing it. If the real bridge cannot be exercised, report the gate
as unavailable/blocking rather than substituting mocks or marking it passed.

For owner-authorized EXECUTION-NODE-PASSWORD-AUTH-01 password QA, use a valid
password session entered through the UI; do not require or silently substitute
a PEM key. Do not ask for the password in chat or log/read the form value.
Record account metadata and exact packaged SSH/SCP/helper versions. This does
not authorize account/password changes, sudo policy changes or a new install.
The established EXEC-01 automation identity and sudo policy below stay intact.

Before every real WebView test session that uses PEM SSH credentials, prepare a
private key in an unencrypted PEM encoding accepted by the current
`internal/runtimesecret` validator. If no compatible key is available, create
one before starting the WebView test and ensure its public key is already
authorized on the intended QA hosts. OpenSSH `BEGIN OPENSSH PRIVATE KEY`
format is not accepted by this credential field; the current validator accepts
RSA/EC keys parsed as PKCS#8, RSA PKCS#1 or EC SEC1 PEM, and rejects encrypted
keys. Keep private keys only in `.runtime/secrets/`; never display, print or
copy their contents into project data, logs or documentation. Before testing,
confirm the credential session has not expired. After expiry, renew credentials
through the UI and repeat the host-key probe, independent fingerprint
comparison and explicit UI approval before checking or preparing the node. Do
not bypass host-key trust. If a compatible authorized PEM key or valid session
is unavailable, stop before launching the WebView acceptance flow and record
the prerequisite as blocked.

The Windows development workstation is not the canonical runtime for Python/Ansible Core tests.

- Prefer the configured RED OS test VM when Python or Ansible is unavailable locally.
- A fresh install target must not build the bundle that bootstraps its own Python/Core. DEV acquisition/build runs on a trusted acquisition environment with an existing Python/Core runtime; the selected install Execution Node only receives and activates the verified result.
- Missing `python`, `py`, `pytest` or `ansible-playbook` on Windows is not by itself a reason to mark tests `NOT TESTED` when the RED OS QA environment is available.
- Execute Python/Ansible tests on the RED OS VM through the existing test connection.
- Use local Windows execution only for checks supported there, such as Git, diff and static-file checks.
- Do not install Python/Ansible on Windows merely to run Core QA unless explicitly requested.
- Test commands must use the current working-tree version, not a stale remote copy.
- Transfer only required repository content to a temporary remote test workspace.
- Clean temporary remote test workspaces after QA unless preservation is explicitly required for debugging.
- Use `scripts/qa-sync.ps1` for Windows to RED OS source transfer. It uses
  `scp -r` to copy only `ansible-core`, `services`, `examples`, `contracts` and
  the repository application `config`
  into a unique `/var/tmp/platform-installer-qa-*` workspace, verifies the
  source tree, and must be cleaned with the same helper after QA. Do not use
  tar streaming, `tar | ssh tar`, or ad-hoc archive pipelines. Transfer
  failures are QA infrastructure failures, not product failures.
- Never modify target hosts during read-only Core tests.
- RED OS is the primary current Core QA environment.
- ALT Linux validation is required only for ALT-specific milestone behavior or when explicitly requested.

### Established RED OS EXEC-01 connection

For the configured RED OS QA target at `192.168.56.101`, always connect as
`platform-automation` using the persistent execution identity
`.runtime/secrets/qa-existing-execution-identity.pem` with `IdentitiesOnly=yes`.
This existing identity was verified on 2026-10-27 with strict host-key checking,
the `platform-automation` account and `sudo -n`. The former
`.runtime/platform-exec-key-20260901` path is absent; do not use it for new QA.
SSH key login
is the established transport. The target policy grants
`platform-automation ALL=(ALL) NOPASSWD: ALL`; use `sudo -n`/Ansible
`become: true` and do not use password-based sudo or the `admin` login for
EXEC-01 QA. Do not add or persist any credential values here. If the policy
is absent, diagnose or restore it only through the existing EXEC-01 bootstrap
mechanism.

## Desktop build process cleanup

When a required Wails rebuild is blocked because the repository's own
`build/bin/platform-installer-ui.exe` is still running, first identify the
exact process image path. If it is that exact build output, Codex MAY stop only
that process to release the binary lock and continue the requested rebuild.
Never use this rule to stop another application, a differently located binary,
or an uncertain process.
