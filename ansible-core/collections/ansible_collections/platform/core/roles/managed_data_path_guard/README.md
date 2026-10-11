# `platform.core.managed_data_path_guard`

Read-only preflight for a managed service data directory. The caller supplies
`platform_managed_data_path` and `platform_managed_data_owner` before package or
filesystem mutation. The path must be an absolute directory below a non-system
parent. Existing components must be directories without symlinks, owned by root
or the service account, and not writable by group or others. The guard does not
move existing data or create directories.
