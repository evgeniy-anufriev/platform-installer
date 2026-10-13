# Independent FULL DIFF review

2026-10-12. Reviewer: /root/plan_review, independent read-only architecture reviewer.
Verdict: **BLOCK**. Automatic implementation/publication stopped.

Base bb32857280ba0238a1fc5a744b3226d8d3105f75; frozen diff
`.runtime/qa/schema-registry-20261012/implementation-review.diff`, independently
checked SHA256 1b44a9170ccd5eadde276ce27b35cb7fd3baf7fc8eea024fd0a77a6698ad6e54.
Review covers broker-bound Registry, settings, conditional artifacts, member
configuration, PKI/secrets, Apply/Verify/clear, schema/catalog and documentation.

## SR-D01 — BLOCKING, OPEN

Log-directory ownership is not proven before mutation/removal.
schema_registry_validate.yml checks directory type and absence of symlinks for
guard paths, but checks the ownership marker only for config_directory.
schema_registry_member.yml changes ownership/mode for all managed_paths, including
logs; schema_registry_clear.yml recursively removes these paths.

A foreign ordinary directory at the deterministic log path, with config/unit
absent, passes preflight. Apply can change its access; Clear can delete its files.
A separate config marker does not prove ownership of the log directory.

Smallest correction: independently prove ownership of every mutated/deleted
member root, including logs. Existing unmarked roots must block before mutation.
New roots receive ownership markers; Clear consumes those proofs.

Required tests: foreign logs with absent and owned config/unit, unchanged contents
and permissions, owned positive clear, symlink refusal and neighboring deployment
preservation. No secret contents in evidence. Unsafe filesystem mutation cannot
be closed merely by accepting risk.

Subsequent owner-authorized production-task reproduction confirmed the issue on
RED OS for absent config/unit and matching owned config with absent unit. Directory
ownership/mode changed and the harmless foreign file was deleted; neighbor survived.
See [the journal](test-journal.md#sr-d01-reproduction--2026-10-12). This adds evidence,
does not correct the implementation or constitute another review.

## SR-D02 — NON_BLOCKING, OPEN

The manifest declares x-memberRole: broker, but artifact planning does not consume
the declaration. Actual broker restriction resides in role conditions. Remove the
unused declaration or explicitly document it as nonoperational; prove controller-only
hosts perform no Registry source probes/delivery/install.

## Architecture and evidence

No blocking overengineering mechanism found. Shared pure projection, conditional
artifact activation and memberInputOnly reuse existing boundaries. Package plays
provide the Kafka-to-Registry barrier; production execution_controller.py:469 uses
the package playbook. No new desired-state store or orchestration layer introduced.

Reviewer directly inspected instructions, frozen identity, Core boundaries, role,
manifest/playbooks, tests/documents, dispatcher and existing PKI resolver. Skill
ansible-core-review applied. Parent-reported tests were not rerun by reviewer:
15+25+33 and 5+9+4 suites, native functional tests and final Verify changed=0.
Bundle publication, broader native cases, clear/cleanup and real Wails remain open.

Review remains CURRENT for the frozen diff. One owner-authorized TARGETED_RECHECK
of SR-D01 is available under docs/agent-procedures/review.md. No automatic rerun.

Subsequent [owner-authorized targeted recheck](sr-d01-targeted-review.md) resolved
SR-D01. The original FULL verdict above is preserved as historical evidence.
