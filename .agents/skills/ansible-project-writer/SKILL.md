---
name: ansible-project-writer
description: Safely evolve the UI-BE-03 Ansible-native writer without weakening its staged Core proof or transaction guards.
---

# Ansible project writer

Use only for changes to the UI-BE-03 writer contract or implementation.

Follow the actual flow: `EditCommand` -> `installer.Backend.PlanEdit` -> staged
project -> authoritative `ProjectSnapshot` through `coreadapter.Adapter` ->
opaque `PlanStore` review -> revision/digest-guarded transaction -> post-commit
snapshot.

- Mutate only fixed Installer-owned documents with the managed header. Planning
  writes zero canonical bytes and never rewrites user-owned files.
- Preserve deterministic YAML, stale-plan protection, document/project
  revision guards and `EDIT_SHADOWED` proof through staged Core resolution.
- Keep `safeProjectPath`, symlink/reparse checks, writer lock, journaled
  rollback/recovery, atomic replace and post-commit refresh intact.
- Reject plaintext secrets; plans, journals and diagnostics may contain only
  safe metadata or secret references.
- Keep the machine snapshot target-contact free. Add focused tests for every
  changed guard or transaction failure path and run the authoritative adapter
  acceptance when the Go/Core boundary changes.

Do not add generic YAML adoption, service semantics, apply/runtime execution or
a persistent desired-state model as part of writer work.
