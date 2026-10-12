# UI-01A — mockup reconciliation

Status: COMPLETE, 2026-09-05. The static HTML is a UX reference, not evidence
that a backend contract or infrastructure state exists.

## Pre-start walkthrough

Reviewed flow:

```text
Projects/Create
  → Servers
  → Topology
  → Certificates
  → Services
  → Review
```

Also reviewed Topology → selected deployment → shared Service editor → return,
and Installation Summary → Plan → Execution → Result.

| Mockup behavior | Contract reconciliation |
| --- | --- |
| Create asks for name/path | Add verified bundle selection implicitly or as advanced choice; backend generates ID and locks |
| Empty project claims no inventory/vars | Accepted; only `project.yml` exists after create |
| Forms survive page navigation | Backend transient edit session owns review intents; frontend state alone is insufficient |
| Server form includes host/address | Canonical server command excludes shared technical username/credential |
| Topology precedes PKI and Services | Accepted navigation and handoff order |
| Topology has “Add instance” | Uses catalog-driven deployment creation; no implicit deployment on catalog browse |
| Certificates example edits profile | Requires typed PKI CRUD; SAN/material state stays Core/runtime-derived |
| Service selects PKI profile | Reuses catalog-declared configuration command; no duplicate relation model |
| Topology opens Service settings | Same deployment/session/editor; return context is page-local operational state |
| Review mentions native files | Backend `EditPlan`, not frontend-generated diff, supplies actual affected paths/digests |
| Mock “save” works without Core | Prototype-only divergence; production review/commit blocks without authoritative candidate snapshot |
| Installation Plan/Result | UI-02 over existing DeploymentPlan/run contracts, not UI-01 editor behavior |
| Demo PASS/status/timings | Examples only; never map to actual readiness without backend evidence |

## Required implementation states

Every applicable UI-01B+ screen must have loading, empty, ready, partial,
blocked/read-only and transport-unavailable presentation. Unsaved draft, saved
desired state, execution readiness and observed runtime result are independent.

Specific corrections for production:

- persistent project context displays project name, root and edit state;
- validation binding status is separate from target session credentials;
- unavailable Core keeps safe local project navigation/draft, but disables
  authoritative refresh/review/commit;
- review shows backend semantic changes and affected documents; it never claims
  that save applies infrastructure;
- Certificates distinguishes desired profiles, derived SAN/consumers and
  materialization result;
- active execution warning names its run/revision; project edits cannot affect it;
- Plan shows targets and dependencies; Result shows observed outcomes for one
  run and does not rerun verify when opened.

## Accepted visual/navigation decisions

- Global order: Projects, Servers, Topology, Certificates, Services,
  Installation, Logs, then Help/About/Settings.
- Recommended editing order is not a wizard; non-TLS services may skip PKI.
- Services is a global page and the shared detail destination from Topology.
- Main editor uses two columns where useful; diagnostics/details expand on
  demand. Execution task detail remains collapsed by default.
- One session-scoped technical identity/credential applies to all target
  servers. The value never appears in project state.

## Acceptance recheck

UI-01A changed no production UI. The current mockup already demonstrates the
accepted order, shared Service editor, preserved form draft, PKI reference,
review, and collapsed Plan/Execution/Result details. No additional mockup edit
is needed for the contract freeze. Each later milestone must repeat its focused
walkthrough before coding and at acceptance as required by AGENTS.md.
