# Historical documentation checkpoints

Extracted on 2026-10-12 from the original milestone documents. Recorded statuses,
versions, review verdicts and test outcomes describe their source scope and dates.
They do not override [CURRENT_STATE](../../../../CURRENT_STATE.md), authorize new
work or prove later acceptance. Requirements and planned QA remain in the source
documents. A moved evidence section retains its original wording and title.

## core-06.md

Source document: [core-06.md](../core-06.md).

<a id="core-06-checkpoint-001"></a>

Status: DONE.


## core-01.md

Source document: [core-01.md](../core-01.md).

<a id="core-01-checkpoint-001"></a>

## Kafka role status

The package contains the independently usable collection namespace and
`platform.kafka.kafka_kraft` role skeleton. It deliberately has no
`tasks/main.yml`: production work starts in SERVICE-01A only after Core
contracts are stable.



<a id="core-01-checkpoint-002"></a>

## Validation evidence

The read-only Core smoke was executed on RED OS as an Ansible controller:

- Python 3.11.15;
- ansible-core 2.18.15;
- contract schema-document tests: 4/4 passed;
- Core, catalog and Draft 2020-12 engine tests: 23/23 passed;
- derived catalog reproducibility check passed;
- syntax check passed;
- all six valid root fixtures passed with `changed=0`;
- all three invalid fixtures returned non-zero with the exact expected
  structured finding code and field.

No target host was contacted or modified. Temporary controller files were
removed after the test.



<a id="core-01-checkpoint-003"></a>

## CORE-01 status

CORE-01 is **DONE**. Draft 2020-12 validation is provided by the vendored
`jsonschema` 4.17.3 engine behind `SchemaValidator`. The local registry and
network-denying handlers are covered by positive/negative tests, including
`$defs`/`$ref`, `if`/`then`, `const`, `enum` and `unevaluatedProperties`.
The RED OS controller ran the complete schema, Core, catalog and fixture
validation suite successfully without installing dependencies or contacting
target hosts.
