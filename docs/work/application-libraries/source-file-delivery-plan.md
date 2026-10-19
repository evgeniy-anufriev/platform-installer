# Application source file delivery

Owner approved binary-safe source delivery and an 8 MiB package-file limit on
2026-10-19. The existing application Files editor and `config_files` descriptors
remain the only configuration surface; no new desired-state model or script.

1. Preserve allowlisted package-relative source/template paths, unique relative
   destinations, symlink rejection and read-only Compose mount validation.
   Raise the existing per-file limit consistently in Core and Go to 8 MiB.
   Owner amendment: remove file-extension checks entirely within existing
   package assets/configuration/template paths, including files with no suffix.
   These are application inputs; hooks/tasks/plugins paths remain forbidden.
   Apply the same package-only 8 MiB allowance to the protected candidate
   archive sender/receiver. Keep generic 4 MiB and aggregate bounds unchanged.
2. Render templates as before. For source files use standard Ansible stat SHA256,
   slurp for bounded nonsecret validation, and copy(src) for exact bytes. Keep
   template text secret checks; scan decoded source bytes for the same forbidden
   private-key and credential-assignment patterns. No archive-content secret
   inspection is claimed: packages remain trusted code, as existing templates.
   Bind the config fingerprint to the source bytes and relative destination.
3. Keep the existing private materialization directories, ownership checks,
   config-digest label and Compose activation/retry behavior. No new lock.
4. For Evo QA use an explicitly named mock user-script JAR which logs a fixed
   startup marker through Evo's real script loader and does not access Kafka
   objects. Preserve original source inputs; do not substitute the Evo image.
   Configure/mount the JAR through Files and the approved library plan, not
   manually prepared host directories. Do not include source production CSV or
   user scripts in the mock package.
5. Validate Core on current-tree RED OS, Go package import/export bytes and
   bounds, native Ansible binary copy/digest/repeat and secret rejection.
   Exercise actual React Files Save/reopen and fresh approved Library Apply/
   Verify with explicit infrastructure skip; verify all three hosts' mounted
   bytes and real mock execution logs. Preserve safe diagnostics and own-account
   provisioning through the plan. No infrastructure installation or full-suite
   acceptance claim.

Independent FULL PLAN review precedes implementation; FULL DIFF review precedes
runtime publication/execution because package-file trust/transport is affected.
Review budgets and owner disposition follow the repository review procedure.
