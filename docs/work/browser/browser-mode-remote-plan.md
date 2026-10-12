# BROWSER-REMOTE — Linux backend with browser workstation

Document scope: the original milestone contract/design. Historical status, review
and QA checkpoints are collected separately; current status and authorization
are recorded only in [CURRENT_STATE](../../../CURRENT_STATE.md).

Security boundary: DEV-ONLY over HTTP; production/security acceptance deferred until v1.0
HTTPS. Linux remote startup requires the explicit
`-browser-allow-insecure-dev-http` flag. The source-IP restriction does not
provide confidentiality or integrity for credentials and runtime-secret
uploads in transit. Do not use this mode with production systems or data.
Local Windows Browser mode and native Wails mode are unaffected.

## Goal

Run the existing Go application backend on a Linux Execution Node and present
the same React UI through an ordinary browser on the operator workstation.
Wails remains an optional desktop wrapper over the same Go application
services. Feature components use one transport-neutral `ProjectBackend`;
they do not branch on Wails or browser mode.

## Owner decisions and deployment boundary

- The backend is reachable at an operator-configured `host:port` over HTTP.
- Owner decision: HTTP remote is allowed only in a development environment
  with explicit startup opt-in. Credentials and encrypted runtime-secret file
  bytes are visible to network observers and can be altered in transit. Do not
  use production systems/data. HTTPS and security acceptance are deferred to
  v1.0.
- The deployment environment MUST allow connections to the backend port only
  from the operator workstation running the browser and from localhost on the
  Linux host. All other machines and network sources must be denied.
- The environment team owns and supplies evidence for that source restriction.
  The Installer does not configure the firewall, authentication, TLS, load
  balancer or Keycloak in this milestone. The future deployment is expected to
  use a 443/TLS load balancer and Keycloak.
- The initial remote mode is one interactive browser tab and one operator
  workstation. It is not a multi-user service.
- Project paths entered in the browser are paths on the Linux Execution Node.
- A runtime-secret file is chosen from the browser user's computer and its
  bytes are sent only to the one typed operation that imports it.

The owner-approved network rule and the exact plan reviewed are recorded by
the targeted `BROWSER-REMOTE-01` recheck (plan SHA-256
`B5DBF8465901E0A755E94E7679D35A103BAD6495014F88C39754E38A6594D8D5`). The
review resolved the blocking finding; it did not verify a deployed firewall.
The owner subsequently clarified that localhost on the Linux host is also an
allowed source. This additional allowance is narrower than allowing any
network client and is included in the implementation; the environment must
still deny all other network sources.

## Implementation boundary

- Build the browser host on Linux without starting Wails. It serves the
  production React assets and a closed set of typed API operations over the
  same `App` methods.
- Bind address and advertised host are explicit startup settings. The safe
  default is loopback; remote access requires deliberate listener settings and
  the environment's source restriction before the process is exposed. The
  listener and advertised host must use the same port; accepted Host values
  are the advertised authority and localhost aliases for that port.
- Require the configured Host and same-origin API requests. Use bounded JSON
  bodies, a fixed operation allow-list, request concurrency limits and
  graceful process shutdown. These checks are input/transport constraints;
  they are not presented as user authentication.
- Preserve the existing local Windows browser mode and native Wails mode.
  Wails retains its native file and directory dialogs.
- In remote browser mode, open/create/export project flows request explicit
  absolute server-side paths. No generic server filesystem browser or listing
  endpoint is introduced; existing backend path and transaction guards remain
  authoritative.
- The browser file picker reads one encrypted runtime-secret file in memory.
  Only its bytes and the existing typed operation inputs are submitted. Do not
  submit the filename or persist the upload in browser storage, project files,
  logs or diagnostics. Go enforces `secretfiles.MaxEncryptedBytes`, runs the
  existing parser, clears temporary byte buffers and stores decrypted values
  only in the existing runtime-only secret broker.
- Progress continues through the existing Go event projection and browser SSE
  adapter. It does not change run IDs, sequence handling, Core execution
  authority or cancellation semantics.

## Out of scope

- Installer-managed authentication, authorization, TLS, reverse proxy,
  Keycloak and firewall rules.
- Access from arbitrary network sources or multiple workstations/users.
- Generic filesystem, shell, Core or arbitrary RPC endpoints.
- A second project store, session database or Ansible/Core semantic path.
- Moving Wails, Go application semantics or Core execution to the browser.

## Startup

The Linux `-tags browser` entry point refuses to start unless the explicit
`-browser-allow-insecure-dev-http` flag is supplied. The default listener is
loopback; remote access additionally requires explicit listener/host
configuration. HTTP is a development-only exception, not an accepted
production deployment. HTTPS, external HTTPS origin handling, and security
acceptance remain required for v1.0.

The process prints the UI URL and remains in the foreground until explicit
Exit, bounded idle shutdown or a process stop signal. No browser is launched on
the Linux host.

## Acceptance gates

- Without `-browser-allow-insecure-dev-http`, Linux browser build exits before
  opening a listener and emits `BROWSER_REMOTE_HTTP_REQUIRES_DEV_OPT_IN`.
- Dev-only HTTP startup is explicitly not production acceptance.
- At v1.0, acceptance must prove HTTPS transport for credentials and secret
  uploads, valid external HTTPS origins, and rejected untrusted origins.
- Deployment evidence confirms the browser workstation and localhost can
  connect, while a second machine cannot reach the backend port.
- Real browser acceptance covers open/create/save/export using Linux-side
  paths; session credentials; host-key trust; fresh plan, approval, Start,
  progress, cancellation and result; event reconnect; and runtime encrypted
  file upload from the browser workstation.
- Negative checks cover unlisted operations, wrong Host/Origin/method/content
  type, oversized body/file, invalid server paths and malformed encrypted
  input. Secret bytes and passwords must not appear in logs/events/diagnostics.
- Wails build and affected native-dialog/UI flows remain functional.
- Recheck the UI mockup and design flows at acceptance. Do not claim the
  network boundary passed until environment evidence is available.
