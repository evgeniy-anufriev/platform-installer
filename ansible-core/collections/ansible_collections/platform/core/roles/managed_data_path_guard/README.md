# `platform.core.managed_data_path_guard`

Preflight for a managed service data directory. The caller supplies
`platform_managed_data_path` and `platform_managed_data_owner` before package or
filesystem mutation. The path must be an absolute directory below a non-system
parent. Existing components must be directories without symlinks, owned by root
or the service account, and not writable by group or others.

When the data path is below a custom `platform_data_root_directory`, the caller
also supplies that root, its `ansible_user` owner, and the service's Verify-only
flag. Apply safely reconciles only the custom root to that SSH technical user
with mode `0755`; descendant data directories retain service ownership. Verify
checks the same owner and mode without changing them. The standard `/var/lib`
root is excluded from ownership changes and remains system-owned. No existing
service data is moved or recursively chowned. Explicit service paths outside the
project root keep their existing ownership behavior and do not cause the
project root to be created or changed.
