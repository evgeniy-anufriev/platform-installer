# SI11 S06 — inherited service settings before and after READY

Document scope: the original milestone contract/design. Historical status, review
and QA checkpoints are collected separately; current status and authorization
are recorded only in [CURRENT_STATE](../../../CURRENT_STATE.md).

Recorded status and review scope: [historical checkpoint](evidence/documentation-checkpoints-20261012.md#si11-s06-inherited-settings-plan-checkpoint-001).



## User-visible behavior

The Services deployment and member editors show saved override presence even
without an Execution Node. When the project's exact immutable bundle is
available and verified locally, they also show a safe, literal role default
for a supported setting. An inherited value is never copied into an edit
command merely because it is displayed. A dynamic default is labelled
«Вычисляется при выполнении»; an unavailable exact bundle is labelled
«Значение по умолчанию пока недоступно». The editing field itself displays a
safe known effective value when available (saved override, current Core value,
or literal bundle default), while the adjacent source label distinguishes its
origin. An inherited display value is not a saved override: `Применить` stays
disabled until the operator explicitly changes the field. Unresolved or
unsafe values leave the field empty with an honest source/status label.

When the selected Execution Node becomes READY, the Installer requests a
bounded, target-free Core service-configuration projection for the current
saved project revision and exact runtime. This does not call Project Verify,
does not update verification status, and cannot authorize installation. It
may run on READY transition and after a semantic Save, with one in-flight
request per project/runtime identity. A subsequent draft shows its explicit
local inputs separately; old Core results must not be labelled current.

## Authority and contracts

Role defaults remain authored in the service package. The bundle builder may
derive one immutable, digest-covered, **presentation-only** static-default
component from those role defaults and manifest mappings. This component is
not desired state, not a second source of service semantics, and cannot
override Core. It carries only closed primitive values admitted by trusted
catalog descriptors; never raw roles, Jinja expressions, arbitrary objects,
credentials or opaque variables. Unknown/nonliteral/sensitive settings carry
only a state marker. Bundle publication is immutable; older bundles without
the component remain readable with the unavailable fallback. A successful
local projection requires exact artifact/catalog lock verification and safe
handle-bound component reading. No local Ansible precedence implementation:
Go joins a fixed default by service type/setting ID with already saved,
direct-owned deployment/member override presence for display only.

The owner requires values for **all supported ordinary settings**, not only
numbers and enums. A value may cross the UI presentation boundary only for a
trusted, `MANAGED` descriptor whose closed editor shape is `BOOLEAN`,
`INTEGER`, `NUMBER`, `ENUM`, `BOUNDED_STRING`, `DNS_DOMAIN`, `TLS_PROFILE` or
`SERVICE_DEPLOYMENT`, and only when the concrete literal passes that
descriptor's existing type, length, range and choice bounds. This admits
ordinary strings and references such as account names and TLS-profile IDs.
The current `RUNTIME_SECRET_REFERENCE_OBJECT` shape is **never** a display
value; it exposes only configured/present state and its dedicated Secrets UI.
`UNSUPPORTED`, `ADVANCED`, arbitrary objects/arrays, opaque settings,
unbounded strings, Jinja expressions and over-limit values also expose state
only. Do not infer confidentiality from setting IDs or labels. Never ship raw
role maps or the raw Core configuration projection to React. Positive and
negative tests cover each admitted shape and credential/expression/object/
oversize rejection. Display is not an edit command: inherited values are not
saved until the user explicitly applies an override.

Core owns actual resolution. Reuse its existing
`resolve_service_configuration` logic. A new closed, versioned read-only
operation returns only supported managed settings keyed by deployment ID and
canonical `(deploymentId, memberId)` identity, with state, safe value where
resolved, source and bounded origin metadata. No raw effectiveConfiguration
map or expression is sent to React. Define a fixed request and bounded
response contract, explicit capability advertisement on a **new** capabilities
version, strict identity/revision/runtime binding, response size and
collection limits, safe diagnostics, timeout/cancellation and no target
contact. Existing published capability and snapshot contracts stay immutable.
The operation runs on the Execution Node, not the workstation. If an older
READY runtime lacks the operation, retain the local presentation with a clear
«Core-проекция недоступна» state; never downgrade to running Python locally.

Projection freshness key: saved canonical project revision plus exact bundle
and catalog digests and selected READY node/runtime identity. Invalidate on
Save, project close/reopen to another revision, node/runtime switch or loss of
READY. A failed/slow Core query does not turn a valid saved project INVALID
and does not block Save. It also does not change Verify evidence. Caching is
memory-only; no new persistent state.

## UX and safety

Show one source label per supported setting: «По умолчанию»,
«Переопределено для сервиса», «Переопределено для ноды» or
«Вычисляется при выполнении». An explicit override at a member scope wins
only for that exact member; multiple members on one host remain independent.
Unknown or unsupported settings retain the existing read-only/presence-only
behavior. Runtime-secret or credential-shaped values are never displayed as
plaintext by either projection. No Core query occurs merely because a user
opens a page repeatedly, and neither this query nor Verify contacts targets.

## Acceptance

- Before READY: saved override and literal safe default are visible with
  source; nonliteral/default-unavailable states are honest; no Core call.
- After READY: one bounded Core operation provides current deployment/member
  source/value without triggering Verify, planning, target contact or Save.
- Save/revision/node/runtime changes invalidate old evidence; drafts cannot
  masquerade as saved effective state.
- 3/1 member overrides remain distinct on one host; no secrets or unsupported
  raw values reach Wails/React.
- Existing bundles and capability versions remain compatible; new release
  publication and activation use the supported immutable path.
- Focused Core, Go and React tests, standalone Ansible entrypoint, real Wails
  bridge acceptance, RED OS target-free proof, reproducibility and diff check.

No UI-wide redesign, new desired-state store, generic Ansible-variable
evaluator, Project Verify shortcut or installation gate change belongs here.
