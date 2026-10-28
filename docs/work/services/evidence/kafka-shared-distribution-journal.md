# Kafka shared distribution

Owner-authorized scope, 2026-10-27: a default-false
`platform_kafka_schema_registry_use_kafka_distribution` flag; retain all current
separate-distribution defaults. The earlier authorized
`platform_kafka_script_extension` change is part of the same change scope.
Source base: `3116c99b`; `master` and `origin/master` matched after fetch.

## Implementation

- Kafka command names concatenate their base name with the configured suffix;
  the default remains `.sh` and an empty suffix is supported.
- Shared mode reuses `/opt/<platform_kafka_archive_directory>` for Registry;
  it skips separate Registry source resolution, package installation,
  delivery, extraction and its separate marker.
- Actual shared Kafka extraction records `.platform-kafka-approved-sha256`.
  Existing unmarked or differently marked directories are rejected rather than
  adopted. Shared Apply verifies the approved Kafka archive checksum, including
  Registry-only phase; Verify requires the approved checksum and checks the
  installation marker, regular executable launcher and regular versioned JAR
  without archive delivery or extraction. The root must be a real directory.
- Registry users, configuration, PKI, systemd and member flow are unchanged.
- Current `service.yml`, `artifacts.yml` and compatibility pins remain unchanged.
  A combined distribution package must explicitly bind both logical artifact
  requirements to its approved common payload and correct component versions;
  inventory does not rewrite bundle metadata. No artifact was acquired and no
  Confluent 7.8.0 compatibility is asserted.

## Validation and acceptance

Focused RED OS QA, 2026-10-27, current working-tree sources:

| Check | Result |
| --- | --- |
| Kafka service tests | 42 PASS, including 7 shared-distribution tests |
| Core `test_kafka*.py` | 35 PASS |
| Native application accounts | 13 PASS, including extensionless CLI |
| Native application batch | 9 PASS initially; 1 stale-path assertion corrected and rerun PASS; 10 unique cases PASS |
| Native service repair regressions | 12 PASS |
| Kafka Apply/Verify syntax | 2 PASS |
| `git diff --check`, no hardcoded Kafka `.sh` names in role tasks/templates | PASS |

Total: 112 unique test methods PASS. The first service run exposed a fixture
that called normalization tasks without role defaults; it now loads the real
defaults and sets the expected name prefix. The batch fixture still asserted
pre-relocation `applications/stages/...` imports from a playbook already inside
`applications/`; its relative assertions now use `stages/...`. Production
normalization and application playbooks were not changed.

The new native shared scenario runs real extraction, link, marker and Registry
distribution-preparation tasks with synthetic archive contents inside a private
mount namespace. A temporary directory is bound over `/opt` only in that
namespace; installed host distributions, service accounts, systemd and Kafka
data are not touched. Fresh extraction PASS; repeat and Registry-only Apply
PASS with changed=0; read-only Verify PASS with changed=0 and a nonexistent
archive path; missing-marker interruption is rejected. This is preparation
evidence, not real Kafka/Registry process or React/Wails acceptance.

The established EXEC-01 identity was located at
`.runtime/secrets/qa-existing-execution-identity.pem` and verified with strict
host-key checking, `platform-automation`, `sudo -n`, Python 3.11.15 and Ansible
2.18.15. Updated `docs/agent-procedures/qa.md`; private-key contents were not
printed or copied into QA sources.

Source transfers used `qa-sync.ps1`. Initial workspaces
`/var/tmp/platform-installer-qa-ca588a96327c45efaff07eb3797b84a0` and
`/var/tmp/platform-installer-qa-db904c17ac5f4825bf81a532e7f7e806` disappeared
during execution; interrupted results were discarded and rerun. Completed
service/repair/syntax runs used
`/var/tmp/platform-installer-qa-281c695a16694a339c6b79194a4ef776`; the corrected
batch assertion ran from the final synchronized sources at
`/var/tmp/platform-installer-qa-06becd55ae64467a9cd084c1e36d978c`.
The earlier completed 35 Core and 13 accounts tests ran before the disappearance;
their tested production sources remained unchanged. Both remaining owned
workspaces were removed with `qa-sync.ps1 -Cleanup` after validation (exit code 0).

## Independent review and owner decision

One FULL DIFF review returned BLOCK on base
`3116c99b3ff661543d55878f4a196cfe6112e5eb`, source fingerprint
`d87fa0d437819cb9b680eed400b1ce702775b27f30847758ce77f2d5bc186e7c`.

- KSH-D01 (blocking): shared mode resolves Kafka authority and does not compare
  the separate Registry requirement. After discussion the owner explicitly
  rejected this finding and resumed execution. The additional comparison was
  not implemented; historical review remains BLOCK, not APPROVE. No automatic
  TARGETED_RECHECK or second FULL review was performed.
- KSH-D02 (nonblocking): interruption between extraction and marker can leave an
  unmarked distribution. README now describes recovery without adopting an
  unverified directory, and the native repeat test confirms rejection.
- KSH-D03 (nonblocking): initial tests only checked synthetic Verify assertions.
  Added the isolated production-task fresh/repeat/Registry-only/Verify sequence
  described above; real service/runtime acceptance remains open.

No artifact acquisition, bundle publication/rebind, real Confluent installation,
React/Wails/visual acceptance was performed. Current separate
package versions and artifact pins remain unchanged.


## Git publication

The owner subsequently authorized a scoped commit of Kafka changes and the
related documentation, followed by a normal push to origin/master. Only the
explicit Kafka/documentation staging allowlist is included; exact commit and
push evidence is reported in the chat after publication.
