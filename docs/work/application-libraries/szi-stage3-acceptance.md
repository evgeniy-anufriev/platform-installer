# SZI Stage3 stand acceptance

Owner-authorized on 2026-10-24. Continue in codex/szi-stage3.

## Ordered gates

1. Direct preparation without Ansible: materialize the authored files, invoke the
   provider scripts directly on Execution Node, and start the six containers.
   Correct packages/defaults/configuration against observed failures.
2. Only after direct success, exercise the same inputs through native Ansible,
   including repeated integration calls and unchanged state.
3. Only after both gates pass, use the actual React/Wails fresh plan, approval,
   Start and terminal flow. No earlier installation plan/run is allowed.

## Placement and shared packages

Use one set of application packages for both library instances sdku and cspa:
data-manager, hmi-backend and hmi-frontend-para. SDKU instances run on node1/101;
CSPA instances run on node2/102. Each has its own applicationId, endpoint and
SSO client. Stop the five SZI containers on102 to release resources; SZI on103
remains the provider through its existing public endpoint. No source107 services
or unrelated target applications are authorized to stop.

Use alarm-view-service as the working defaults/ports/ENV/PKI/Agent reference.
Each application owns one client JSON template shared by both libraries. Its
resources/policies/role catalogue are common; identity and endpoint values vary
per instance. hmi-backend uses the original hmi-backend-cspa configuration as the
reference. Other applications retain their respective original client settings.
Keep redirect URIs https://nginx…/<applicationId>/*.

## Groups and mappings

- SDKU: Администратор СДКУ, Инженер СДКУ, Диспетчер управляющий, Диспетчер неуправляющий.
- CSPA: Администратор ЦСПА, Инженер ЦСПА.

The owner corrected the initial shared administrator list: Администратор ЦСПА
belongs only to CSPA. SDKU client roles bind to SDKU groups, CSPA client roles to
CSPA groups. Source export calls CSPA groups Администратор_ЦСПА and Инженер_ЦСПА;
use their original assignments for the requested space-separated group names.
SDKU Engineer uses the original Инженер group assignments.
Read realm and client roles from the original dump/export, never credentials.
Preserve existing SZI/builtin assignments where declared; do not delete objects
or foreign assignments. Common client role definitions include those required
by either library's original groups.

## Acceptance evidence

On101: data-manager-sdku, hmi-backend-sdku, hmi-frontend-para-sdku.
On102: data-manager-cspa, hmi-backend-cspa, hmi-frontend-para-cspa.
All six must be running and ready. Review logs by severity: startup, TLS,
configuration, authentication and integration failures block acceptance;
business-function errors may be accepted explicitly and retained in evidence.
Read back clients, resources/policies/roles and group assignments independently.
Prove repeat calls preserve object identity and return unchanged when applicable.
Record each gate separately; direct success is not Ansible or real-run success.

Runtime credentials remain in the established private runtime paths and travel
through stdin/protected files. No values in project, logs or public evidence.
QA helpers belong under .runtime/qa/szi-stage3, not repository root.

Package defaults do not select a project endpoint group: endpoint is disabled
by default; project overrides enable it and select the actual group. data-manager
has no Kafka connection/account/bindings; Kafka applies to hmi-backend only.
