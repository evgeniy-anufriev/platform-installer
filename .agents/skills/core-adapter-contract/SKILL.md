---
name: core-adapter-contract
description: Add or review the structured Go-to-Python/Ansible Core adapter boundary.
---

# Core adapter contract

Use when a Go backend operation needs a new or changed answer from Core.

1. Decide the owner first: Go owns application lifecycle; Core owns
   infrastructure semantics.
2. Define versioned structured intent from Go, a thin controller bridge, and a
   structured versioned Core result. `coreadapter.CommandAdapter` must consume
   the result, not human Ansible stdout.
3. Keep payload separate from bounded diagnostics. Define stable status/error
   behavior, deterministic serialization, timeout and context cancellation.
4. Exclude secret values. For pure resolve/snapshot/validate operations prove
   no target contact and offline operation.
5. Add compatibility tests through the real standalone Ansible entrypoint.

Stop if Go would reproduce a Core result, or if a Python adapter would become
an EditPlan, session or process-lifecycle manager.

For a new operation, identify the playbook/action entrypoint, request/response
schema, version, safe diagnostics, cancellation behavior, target-contact
contract and offline test before writing code.
