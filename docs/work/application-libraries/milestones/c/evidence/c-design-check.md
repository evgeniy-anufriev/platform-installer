# C1 — HTML design check

2026-10-15. Scope: documentation and static synthetic HTML only.
No production code, runtime bundle, target service or credential operations.

Checked using installed Playwright/Chromium against local
`docs/design/ui-design-01-mockups.html`:

- New Applications navigation and return to Installation: PASS.
- Two library selections × library/slot levels × four tabs =16 content cases: PASS.
- Search/filter and explicit reset demonstration: PASS.
- Browser page errors:0.
- Root horizontal/vertical overflow at1024×720: none.
- Screenshots inspected:1440×900 light,1024×720 light,1024×720 dark.
  Master-detail, visible actions and internal scroll areas confirmed.
- Existing Markdown links from C plan/contract index resolve locally.

Screenshots are local ignored artifacts `.runtime/c-mockup-1440.png`,
`.runtime/c-mockup-1024.png`, `.runtime/c-mockup-dark.png`; not target evidence.
Final post-review changes only clarify placeholder banner and CSPA one-host example;
final syntax/interactions rechecked separately before delivery.

Not exercised/claimed: real create/import/edit-session/disk Save, dirty-navigation
dialog, modal focus trap,200% zoom, long-list stress, React/Wails/Core integration,
target Apply/Verify. Those are explicit C2–C4 gates, not satisfied by this mockup.
Production code and infrastructure remain unchanged. No commit was requested.

Owner refinement: image and host/container port fields added with in-memory explicit
overrides and independent reset. Existing PLAN review predates this bounded detail;
no new independent review claimed.

## Production C acceptance,2026-10-16

Actual React/Wails Applications editor inspected at1440×900,1024×720 and125% zoom.
Scoped sidebar colors and ordinary form-control styles match the existing light
shell. Header/tabs wrap at narrow widths without covering fields. The OS dark
preference was exercised; production continues to render the established light
shell, so no production dark-theme implementation is claimed. Dirty stay/discard
was owner-accepted; per-field staging remains. Actual editor/import/external-revision
and target acceptance are recorded in [C journal](c-test-journal.md), separately
from the static mockup checks above.