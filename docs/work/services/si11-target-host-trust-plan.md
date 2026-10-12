# SI11 — target SSH host trust handoff (plan)

## Scope and observed gap

The S11 full-plan run reaches PKI target contact but fails because the detached
Execution Node controller uses strict `UserKnownHostsFile` and has no approved
target host keys. The existing Wails approval covers the workstation →
Execution Node hop only. Target trust is a separate operator decision. This
change supplies that missing input through the normal UI/Go/Execution Node
path; it does not disable strict verification or add a QA-only file copy.

The Servers mockup has server rows and a persistent Execution Node panel but no
target-trust action. Add a per-saved-server `Проверить SSH-ключ` action and a
bounded approval dialog showing host/port, key type and SHA256 fingerprint.
The installation screen may report missing/stale approvals, but cannot approve
keys implicitly. No new portable project field is added.

## Authority and binding

- Probe the saved server's address and configured SSH port from the selected
  trusted Execution Node through its bounded read-only `ssh-keyscan` transport;
  parse the bounded response with the existing keyscan parser. The workstation
  never contacts the target directly. Probing alone is never approval. The operator
  must compare and explicitly approve the fingerprint through Wails. A scan
  result expires in two minutes.
- Runtime-only approval binds project identity and exact saved revision,
  server ID, address, port, key type and public key. Invalidate on project
  close/reopen, semantic Save, server edit/delete, or a changed probe/key.
  Never persist it in project files, browser storage, logs or diagnostics.
- The target-free Core snapshot already resolves `ansible_host` and
  `ansible_port` through Ansible hostvars. Its action also passes private
  Core-to-plan inputs without widening the public ProjectSnapshot. Use that
  existing private seam to pass a closed per-target connection description:
  target host ID, exact effective address, integer port and connection mode.
  Admit only absent/default SSH or explicit `ssh` mode; reject `local`, other
  connection plugins, nonliteral/ambiguous endpoints and host-scoped SSH
  option overrides that can alter host-key sources or effective destination.
  Specifically reject `ansible_ssh_host` and `ansible_ssh_port`: the SSH
  connection plugin treats them as aliases for its effective destination and
  port, so they cannot be ignored after resolving `ansible_host` and
  `ansible_port`.
  The description is included in the digest-bound private ExecutionManifest,
  not the public DeploymentPlan or portable project. Public snapshot fields
  and published schemas remain unchanged.
- At Start, after the authoritative fresh plan rebuild and fingerprint check,
  collect the union of target host IDs from the fresh Core plan. Require a
  matching approval and saved typed server address/port for every target.
  The node-side stage compares each approved ID/address/port against the
  matching Core-resolved private manifest connection, including mode. Exact
  mismatch (including inventory/group_vars override or alias), missing ID,
  unsupported mode/options, duplicate/conflicting endpoint or stale approval
  blocks Start before lease attachment or target contact. No DNS alias
  equivalence is guessed. Core's plan determines scope; React and Go do not
  infer topology or Ansible precedence. The private manifest's
  `targetConnections` is restricted to the union of `targets` from every
  action in that exact fresh plan. The approved set must exactly cover this
  plan-scoped connection set, including PKI operations, without requiring
  trust for unrelated inventory hosts.
- A keyscan is unauthenticated evidence. The dialog must say to verify the
  fingerprint through an independent trusted source. An approval confirms
  only that key, not readiness or target credentials.

## Execution handoff

- Before any durable Start commit, transmit a bounded canonical known_hosts
  document over the existing trusted workstation → Execution Node transport.
  A narrow private staging operation validates the exact fresh plan staging
  ID, project identity/revision, plan fingerprint, runtime release and
  manifest digest; checks its parsed lines against the approved target set
  and the manifest's Core-resolved connection descriptions; and atomically
  places a root-owned 0600 file plus a plan-bound SHA-256 trust digest marker
  in that plan's staging directory. It rejects unsafe paths/links and an
  existing conflicting marker. Neither file is global mutable trust state.
- Start reopens the staged trust file and marker through safe file handles,
  checks type/mode/size, recomputes the digest from the exact read bytes and
  matches the marker and current private manifest binding before moving the
  staging directory or committing the run. A leftover marker without the
  exact approved file never authorizes Start. On idempotent retry after commit,
  the authoritative mapping/run-local trust wins; a new staging file cannot
  replace the committed run's trust. The detached controller repeats this
  validation immediately before each target-contacting operation so a later
  path replacement fails closed. This is private Start validation, not a
  public StartExecution/v1alpha2 schema change.
- The existing Start transaction moves that staging directory to the
  authoritative run directory. For target-contacting v1alpha2 runs, the
  controller uses only the run-local approved known_hosts with strict host-key
  checking. It constructs a fixed SSH option set (`-F none`,
  `UserKnownHostsFile=<run>/known_hosts`, `GlobalKnownHostsFile=none`,
  `KnownHostsCommand=none`, `UpdateHostKeys=no`,
  `StrictHostKeyChecking=yes`, `IdentitiesOnly=yes`) and forces Ansible's
  host-key-checking setting on. It strips inherited SSH option environment
  variables and rejects inventory/host/group SSH argument or executable
  overrides rather than letting later options add another trust source or
  change the destination. Verify the effective SSH option boundary with
  focused tests, including conflicting options. Missing/unsafe file fails
  before target contact. A failed stage
  leaves no authoritative run; no Start or lease attachment occurs. Retry of
  an already committed startAttemptId keeps the same run identity and trust.
- Host-key mismatch at SSH time fails normally. No `StrictHostKeyChecking=no`,
  `accept-new`, global host-key fallback, target SSH from the workstation,
  public Start schema change, or direct Ansible/Go test bypass.
- Preserve standalone Ansible's existing inventory/SSH configuration. Do not
  change service or PKI semantics. Localhost-only operations need no target
  approval.

## Acceptance and safety

Positive: approve every target in real Wails, build/approve fresh plan, Start
through the existing React handler/Go method, observe one terminal run and
target SSH with strict run-local trust. Repeat and multi-host acceptance remain
under S11; no DONE claim from unit tests alone.

Negative: unapproved/stale/changed-key target, revision change, different
effective inventory/group-vars host or port, `ansible_ssh_host` or
`ansible_ssh_port` alias, local connection,
conflicting SSH options, conflicting address/key, malformed or oversized input,
unsafe staging object/path, file replacement after staging, digest mismatch,
failed stage, missing run-local file, and concurrent plans cannot silently
authorize target contact. Verify no keys or secrets enter portable files,
public plan, events or diagnostics. Exercise precommit rollback, committed
idempotent retry, and no-target-contact cases.

Run focused Go/Python/React tests, full Go test/vet, affected RED OS tests,
frontend lint/test/build, Wails build, security audit and `git diff --check`.
This is a high-risk trust/process boundary: one FULL PLAN and one FULL DIFF
independent review, with at most one owner-approved targeted recheck per gate.
