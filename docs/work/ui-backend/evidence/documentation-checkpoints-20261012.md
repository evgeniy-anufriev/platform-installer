# Historical documentation checkpoints

Extracted on 2026-10-12 from the original milestone documents. Recorded statuses,
versions, review verdicts and test outcomes describe their source scope and dates.
They do not override [CURRENT_STATE](../../../../CURRENT_STATE.md), authorize new
work or prove later acceptance. Requirements and planned QA remain in the source
documents. A moved evidence section retains its original wording and title.

## ui-be-01.md

Source document: [ui-be-01.md](../ui-be-01.md).

<a id="ui-be-01-checkpoint-001"></a>

Status: **DONE**. This milestone defines architecture and semantic contracts
only. It does not implement a Go backend, Wails transport, React pages, project
mutation, execution streaming, or another desired-state store.


## ui-be-02.md

Source document: [ui-be-02.md](../ui-be-02.md).

<a id="ui-be-02-checkpoint-001"></a>

## Acceptance evidence

The representative `examples/valid/ui-project-snapshot` project has three
unreachable-by-design inventory hosts and exercises Kafka, PostgreSQL HA,
Keepalived, BIND, dns-client, HAProxy, endpoint publication, provider
relations, and shared host-scoped PKI identities.

On RED OS:

- 168 Core unit tests passed;
- catalog and configuration-schema reproducibility checks passed;
- two repeated queries were logically identical and all snapshot assertions
  passed with `changed=0` and only `localhost` in the play recap;
- the same acceptance play passed under `sudo -n unshare -n`;
- one standalone query, including Ansible startup and serialization, took
  0.87 seconds and produced a 70,853-byte JSON snapshot.

No service runtime acceptance is required by this milestone.



<a id="ui-be-02-checkpoint-002"></a>

Status: **DONE**. This milestone implements the first real Installer read path.
It adds no writer, Wails/React application, SQLite desired-state copy, runtime
observation, apply, or verify behavior.


## ui-be-04.md

Source document: [ui-be-04.md](../ui-be-04.md).

<a id="ui-be-04-checkpoint-001"></a>

### UI-BE-04E completion evidence

The production-shaped UI lifecycle test completed two serial Kafka runs with
terminal `SUCCEEDED` under an explicit 30-minute test timeout. PKI apply,
Kafka apply and Kafka verify passed in both runs; the direct Kafka regression
proved repeat apply `changed=0, failed=0`. The deployment-scoped shared TLS
certificate carries `serverAuth` and `clientAuth` with SANs for all three
members. RED OS Core/service/race, local Go, catalog/schema and safety gates
passed.

UI-BE-04 overall is DONE. UI-01 remains a separately gated future milestone.
