# Kafka ACL на вкладке «Секреты» — 2026-10-21

Owner request: show Kafka topic/consumer-group rights immediately, using Core
projection with explicit overrides. Bounded UI extension of the existing
Kafka SCRAM account/grants contract; no Core/Go/schema or execution changes.
The existing design/mockups covered Redis and database access, but had no Kafka
ACL table. Owner request resolves this discrepancy; the UI design now records
the added table. No architecture boundary changes; no independent FULL gate
triggered under the review procedure's bounded existing-contract fix rule.

`ApplicationKafkaAccess` shows current `credentialRequirements.<account>.grants`
and Core resource names supplied by the existing freshSecrets/revision guards.
Without current evidence it labels source declarations as unresolved. Opening
the table never saves. Explicit override retains authored source expressions or
copies the current Core baseline intentionally, then replaces the existing list
through SetApplicationLibrarySlot/draft/Review/Save. Reset removes only grants;
mode/credentials and unrelated ACL rows remain unchanged. Empty list is distinct
from reset. Core validates resources/operations and owns provisioning. The
table does not represent observed ACL inventory; declaration removal does not
revoke existing rights. Account mode follows the existing explicit-mode editing
gate shared with other account forms.

Focused frontend: Kafka ACL7 + neighboring account/connection14 =21 PASS.
Includes immediate projection display, stale projection removal, edit retention
after freshness invalidation, source template preservation, empty list/reset,
failed-save/cancel, and real parent account-writer payload preservation.
Neighboring ApplicationsPage18 PASS; total focused39 PASS. Final typecheck/Vite
build, lint and git diff --check PASS. Visual1440/1024 PASS for the real-project
read-only ACL table; both screenshots inspected. The first visual check exposed
the shared fieldset two-column layout at1024; an explicit block layout fixed it.

Real React/Wails/Go/RED OS Core flow PASS on an isolated copy of full-services,
library cspa / alarm-view-service, existing runtime53 without bundle changes.
Actual React Open, credential submission, independent known_hosts fingerprint
comparison and trust confirmation, node1 READY, Verify VERIFIED. Nine Core ACL
rows appeared immediately: topics, consumer groups and cluster permissions.
The existing explicit-mode gate was exercised first (managed). Then actual
Override → draft → Review → Save → Verify VERIFIED, preserving topicRef and the
explicit copied Core list. This real override exercise copies the effective
list; changed operations and adding a group are additionally covered by the
focused parent-writer tests. Actual Reset → Review → Save → Verify VERIFIED
restored the inherited list exactly. Initial revision:
`sha256:be3c233e9156e3040fbe69ca917b223dd54bcb9c1a45a9cfc6eb4875b18d395f`.
Explicit-mode/restored-grants revision:
`sha256:b085304ae92b1017958ec1cbce4922acce0bf763237fc323d22d2eebb107a2cb`.
Explicit-grants revision:
`sha256:525c5d4b6c2d002ac1284bacb846f0a1635e630aba9accad33c9786c9fb0e0e9`.

Evidence `.runtime/qa/inline-secret-input/kafka-acl-acceptance.json`
PASS/complete; driver `kafka-acceptance.cjs`, screenshots `kafka-acl-1440.png`
and `kafka-acl-1024.png` in the same directory. An earlier driver was interrupted
after a concurrent diagnostic browser opened the same isolated bridge; the
possible context invalidation was not independently proven. Final single-page
flow above completed without that diagnostic browser.

No Approve/Start/Apply, application password entry or broker mutation occurred;
no execution run ID. Reopen, visual editing-form and service execution acceptance
are not claimed. The credential session was cleared through actual React.
Exact isolated child/Wails/Vite processes were stopped; original user process
18372 preserved. Local isolated sources/projects/evidence retained. No commit
or push performed; pre-existing dirty changes preserved.
