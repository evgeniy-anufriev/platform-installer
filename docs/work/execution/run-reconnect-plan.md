# Previous run reconnection

Owner scope: restore the locally recorded previous run after reopening the same
project. No remote history or run-list operation. The owner explicitly requires
the ordinary execution controls, including Cancel, after Attach; observation-only
restrictions from the initial proposal are superseded.

## Existing contracts and implementation

The durable local run record identifies the project directory, stable project ID,
original revision, run ID and original SSH node/account/fingerprint. The remote
Core journal remains authoritative. Project desired state is unchanged.

Servers / Execution Node exposes **Проверить прежний запуск**. A successful
inspection shows one run ID, its original project revision, current remote state
and **Подключиться**. Go revalidates the short-lived recovery token, record,
project and trusted original node before attaching. A newer saved revision does
not prevent reading the run's original revision.

Attach calls the existing `ExecutionService.Reconnect`, registers the validated
run in the existing application registry and starts the existing app-owned
monitor. React opens Installation / Execution and uses the existing subscription
from sequence zero. GetInstallationRun, RunObserver and the existing Result view
remain the observation path. No plan approval is reconstructed and Start is
never repeated. If the run finishes between inspection and Attach, Result opens.

Recovered run reads and Cancel use the exact captured trusted connection; they
do not require a new bundle preparation or current-revision deployment plan.
CancelInstallationRun retains its existing `ExecutionService.Cancel` path.
Before cancelling a recovered run it refreshes and validates remote run/project
identity and current trusted connection. A cancellation error keeps the run guard
and permits retry through the same Cancel method, even if the journal already
says CANCELLED before the unit stop was confirmed.

Credential renewal stops old local observers and permits renewal only for the
original account, SSH endpoint and host fingerprint. The recovered active-run
record keeps the second-Start and node-switch guards while observation is paused.
Normal Start credential/trust guards are unchanged. Application shutdown stops
local observers and does not issue remote Cancel.

## UI design check

The existing UI design places previous-run inspection on Servers and execution
on Installation. Its previous single-button description did not include the
result row or Attach action. The owner directly authorized this bounded addition
and retaining normal Cancel. No separate recovery page or status list is added.

## Verification and acceptance

Focused Go cases cover attach without prepared bundle, identity/token changes,
terminal race, credential renewal and cancellation-error retry. React handler
tests cover the inspection row, Attach, existing subscription and existing Cancel
without Start. Full Go tests/vet and frontend typecheck/lint/build are required.

Acceptance requires the real React/Wails flow: start, close the application,
reopen the same project, restore credentials/trust, inspect, attach, receive events
and use Cancel or reach Result for the same run ID. The owner requested rebuilt
application and bundle and will perform this acceptance personally. Automated
real-bridge acceptance is not claimed.

## Boundaries

Recovery requires the existing local record and same project directory. Moving
the project or losing that record is outside this scope. No remote listing,
new persistence, Core/service-role change, or arbitrary command bridge is added.
