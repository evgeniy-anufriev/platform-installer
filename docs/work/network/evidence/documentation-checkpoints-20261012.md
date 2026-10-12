# Historical documentation checkpoints

Extracted on 2026-10-12 from the original milestone documents. Recorded statuses,
versions, review verdicts and test outcomes describe their source scope and dates.
They do not override [CURRENT_STATE](../../../../CURRENT_STATE.md), authorize new
work or prove later acceptance. Requirements and planned QA remain in the source
documents. A moved evidence section retains its original wording and title.

## net-04.md

Source document: [net-04.md](../net-04.md).

<a id="net-04-checkpoint-001"></a>

## Accepted runtime evidence

The three-node RED OS acceptance completed with Barrier A and Barrier B passing
on every node, with each active graph equal to its candidate graph and native
`haproxy -c` passing. The deployment endpoint and every enabled host endpoint
passed TLS hostname verification and returned the expected stats route. Host
normalization treated `Host` values with and without `:443` identically, while
an unknown Host returned `503`.

Runtime socket counters confirmed that bounded deployment-endpoint requests
used all three healthy HAProxy backend participants. The configured VIP owner
was determined semantically; stopping HAProxy only on a non-owner made only
that host endpoint return `503`, without migrating the VIP or affecting the
pooled and remaining host endpoints. Restoring the service recovered every
endpoint. Separate verify, repeat apply, post-recovery verify and
post-recovery repeat apply all returned `changed=0 failed=0` for localhost and
all three targets.

The deployment-scoped TLS identity covers the deployment, configured host
endpoint names and `*.asutp.scada.local` on every HAProxy participant. The
wildcard SAN was added using the explicit selected PKI reissue lifecycle; it
is never an implicit ordinary NET-04 reconcile.



<a id="net-04-checkpoint-002"></a>

Status: DONE.


## net-04-2.md

Source document: [net-04-2.md](../net-04-2.md).

<a id="net-04-2-checkpoint-001"></a>

## Runtime evidence

- source PostgreSQL `changed=0` вызвал BIND и HAProxy;
- bounded HAProxy drift repaired full-model reconcile, затем verify `changed=0`;
- QA add/remove изменял только canonical desired state: exact record/backend
  появились и исчезли, DNS serial `4 → 5`, unchanged repeat — `0`;
- final BIND/HAProxy/PostgreSQL verifies — `changed=0`;
- Keepalived `.111`/`.112` отдельно reconciled normal lifecycle: один owner,
  helper PASS, BACKUP + nopreempt. Keepalived не NET-04.2 provider.
