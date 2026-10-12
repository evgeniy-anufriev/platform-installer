# UI-01H2 — Services navigation and supported managed forms

Document scope: the original milestone contract/design. Historical status, review
and QA checkpoints are collected separately; current status and authorization
are recorded only in [CURRENT_STATE](../../../CURRENT_STATE.md).

Recorded status and review scope: [historical checkpoint](evidence/documentation-checkpoints-20261012.md#ui-01h2-architecture-checkpoint-002).

## Goal and scope

H2 adds the single global **Services** page and the one Topology hand-off into
it. It renders only the H1 `ProjectCatalogView.configurationSettings` closed
descriptor set and appends only H1 v1alpha8 configuration intents into the
existing shared EditSession. It has no Go, Core, schema, catalog, writer,
Execution Node, PKI or target changes.

The mockup/design reconciliation is exact: global navigation order remains
Project → Servers → Topology → Certificates → Services → Installation; a
Topology **Configure service** action opens the same Services page with that
deployment selected. There is no topology-specific editor, second route or
service-local Save. Mockup default values and status examples are not shown as
Core facts.

## Existing seams reused

- `App` already owns one `page`, one EditSession, `appendStructuralIntent`,
  Review, Save, Discard and the shared 16-command limit.
- `TopologyPage` already owns the selected deployment through App callbacks.
  H2 adds `onConfigureDeployment(deploymentId)`; App sets the Services
  selection and the page together.
- `ManagedProjectView` provides saved direct overrides; the exact READY
  `ProjectCatalogView` provides safe descriptor metadata. React never receives
  raw catalog/schema maps or unsupported configuration values.
- H1 commands are the only mutation transport:
  `SetServiceConfigurationValue` and `RemoveServiceConfigurationOverride`.

## Page model and navigation

`Page` gains the real `services` page. It is enabled for an open managed or
empty Installer project, independently of Execution Node readiness. If no
deployment exists, it shows an empty state with a link to Topology; it does not
create a deployment. The Services list is derived from saved deployments plus
the known current-session Create/Delete deployment intents, exactly as the
existing Topology list does. A draft-deleted deployment is unavailable for new
configuration commands. Selection is application-local, reset on close/open
or committed-refresh failure, and cleared if the selected deployment vanishes
from the final draft.

The one `services` route has two mutually exclusive local views. The list view
shows deployments; opening one shows the selected-deployment detail view with
an explicit **Back to services** action. Topology enters that same detail view,
not a second destination. Both views retain the App-owned selected deployment,
shared session and Review/Save/Discard state. Detail displays only immutable
deployment ID/service/mode plus grouped safe descriptors. H2 supports
deployment scope only; member scope and TLS selector/Certificates return flow
are explicitly H3. A descriptor that offers only member scope is displayed
read-only in H2. After either entry path, focus moves to the detail heading;
return moves focus to the Services list heading.

## Supported controls and local form state

H2 implements only descriptor shapes admitted by H1:

- `BOOLEAN`: checkbox;
- `INTEGER` and `NUMBER`: bounded textual numeric input, parsed locally only
  for UI feedback and sent as JSON primitive;
- `ENUM`: select from the copied closed literals;
- `BOUNDED_STRING`: text input with the copied length bounds.

`TLS_PROFILE` is rendered read-only/deferred in H2. Edit controls require all
of: exact READY catalog, `kind === MANAGED`, deployment scope and one of the
four H2 primitive shapes. `UNSUPPORTED`, `ADVANCED`, `PROTECTED`, unknown,
member-only and no-READY-catalog rows are non-editable. React makes no
name/service/label/object-shape inference and never renders raw unsupported
payloads.

The existing frontend adapter is extended only with H1's bounded
`ManagedConfigurationOverride` projection (`setting`, override presence, state
and, only where H1 permits it, a copied primitive value). It does not add a
frontend DTO or expose a raw configuration map.

Each field has ephemeral local form state. The first **Apply** appends one Set
intent; **Reset to inherited** appends Remove for a saved override. The S11
owner amendment allows explicit re-edit before Save: a guarded session
operation replaces or withdraws only the already acknowledged command for
that exact `(deploymentId, DEPLOYMENT, setting)` target. Reset of an unsaved
Set without a saved override withdraws that command. Other commands and their
order stay intact, canonical files are not changed before Commit, and the
shared session limit remains 16. This is not a separate save path.

On an Append failure, no local acknowledged overlay is created. On success,
the page derives a draft overlay solely from acknowledged intents for display;
the backend reducer remains authoritative. Save/Discard/reopen use the
existing App behavior. `COMMITTED_REFRESH_FAILED` hides editable state and
offers only existing read-only refresh.

## Safety and acceptance

H2 must prove:

- sidebar and Topology action reach the same Services detail view/selection;
  explicit return restores the list view without creating a session;
- no second deployment, session or save path exists;
- initial no-catalog, catalog-unavailable, unsupported and empty-project
  states are read-only/safe;
- supported deployment fields append exact v1alpha8 intents, lock after
  acknowledgement and respect the shared limit;
- Reset is explicit Remove; false, zero and empty string remain values;
- direct saved override vs inherited state and final draft display are clear;
- no raw YAML/catalog maps/unsupported values/secret input reach React;
- existing Topology, Certificates, App navigation and H1 Go behavior remain
  unchanged.

Component tests cover keyboard list selection, both entry paths, focus on the
detail heading and list heading after return, disabled controls, and alert
errors with semantic roles.

Tests are frontend unit/component tests plus affected App tests, frontend
lint/test/build and Wails build. H2 does not require RED OS service or target
acceptance because it adds no Core/Ansible/runtime behavior.

## Non-goals

No member override editor, TLS selector, certificate navigation, secret input,
complex object editor, service-specific rich panel, generic JSON Schema engine,
catalog fallback, Core Verify change, execution lifecycle or H3/H4 work.

## Implementation evidence

See [historical checkpoint](evidence/documentation-checkpoints-20261012.md#ui-01h2-architecture-checkpoint-001). Current status: [CURRENT_STATE](../../../CURRENT_STATE.md).
