# Historical documentation checkpoints

Extracted on 2026-10-12 from the original milestone documents. Recorded statuses,
versions, review verdicts and test outcomes describe their source scope and dates.
They do not override [CURRENT_STATE](../../../../CURRENT_STATE.md), authorize new
work or prove later acceptance. Requirements and planned QA remain in the source
documents. A moved evidence section retains its original wording and title.

## service-install-09-clickhouse-architecture.md

Source document: [service-install-09-clickhouse-architecture.md](../service-install-09-clickhouse-architecture.md).

<a id="service-install-09-clickhouse-architecture-checkpoint-001"></a>

Status: implementation and isolated service/endpoint QA pass; SI09 NOT DONE.
The pinned RPMs were acquired with signed metadata and SHA-256 proof and
published in immutable runtime releases. Direct Ansible 1/1, 3/1 and 3/3
apply/verify/repeat pass, including cross-host replicated writes and owned
node3 failure/recovery. Direct 3/3 ClickHouse apply/verify and its HTTPS
HAProxy endpoint also pass. The real nonvisual React/Wails cumulative run
`installer-f1c76b8b08a861e5cd10257ddc679809` terminated FAILED at HAProxy
apply, although ClickHouse apply succeeded. The HAProxy TLS-probe timeout was
fixed and verified by a later direct apply, but the owner declined a repeat
full-plan run. Consequently the required real-bridge terminal PASS is absent;
this is partial acceptance only. See `CURRENT_STATE.md` for exact evidence.
The former all-services one-plan final
acceptance moves to SERVICE-INSTALL-10 after this milestone; it is not started.
