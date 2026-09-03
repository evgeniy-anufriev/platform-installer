# Ansible Core rules

Core owns infrastructure/domain semantics. Standard Ansible inventory,
`group_vars`, `host_vars` and role defaults remain authoritative; do not add an
independent precedence resolver.

- Keep service/catalog/schema semantics in their existing Core and service
  layers. `ProjectSnapshot` is derived and read-only.
- Controller operations consumed by Go must be structured, deterministic,
  machine-readable and secret-safe. Human stdout is not an API.
- A pure resolve, snapshot or validation operation must remain target-contact
  free when its contract promises that and must preserve offline execution.
- Do not move EditPlan storage, application sessions, project writer
  transactions, Wails transport, UI state or execution-session lifecycle into
  Python. Thin adapter/controller actions are allowed.
