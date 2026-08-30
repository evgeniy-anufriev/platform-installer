---
name: ansible-core-review
description: Review Platform Installer V2 Ansible Core changes for architecture, security and portability risks.
---

# Ansible Core review

Use for review of Ansible Core, collection, playbook, validation or related
contract changes. Order findings by severity and keep the review scoped.

Check that:

- standalone `ansible-playbook` usage remains possible;
- Core has no Installer dependency leak;
- contracts stay versioned and behavior deterministic;
- offline and local `$ref` validation remains safe;
- plaintext secrets are rejected and findings are safe;
- read-only validation does not contact targets;
- vendor is not unnecessarily inspected or modified;
- RED OS/ALT assumptions are explicit where relevant;
- no unnecessary abstraction or duplicated contract is introduced.

Report severity, evidence path/symbol, impact and a concise recommendation.
