# A1 target-free application library fixture

No project.yml required. Inventory addresses are documentation-only TEST-NET.
The package closure is trusted operator input: defaults/templates are executable
Ansible/Jinja and must be reviewed before use. A1 does not render templates or
connect to hosts, registry, Vault or Docker. The image tag is a QA requirement,
not evidence of immutable delivery; image locking/loading belongs to A2.1.

Use ansible-core/playbooks/project-snapshot.yml or validate.yml on an Execution
Node with inventory/hosts.yml, platform_project_root and a published catalog.
Select desired-state v3alpha1 explicitly; library output uses snapshot v2alpha1.
The current execution planner rejects this snapshot until A7.
