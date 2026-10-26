# FULL-STACK-CLEAN-INSTALL: Docker account review

## FULL DIFF

Independent architecture-reviewer,2026-10-26. Base
2a8ce14fbb06c53599cb1088d43a4cf1b251fe58.32-file scope fingerprint
b0cbc9bca0942a655c87d11f182d57ddea3d889bdbc54d7a0211203352172b95;
additional Docker contract89244066a0ef1cdca1a29d99ae00d2e4f09e8f431a9566ca45c9ffc228876044.
Hashes independently confirmed. Initial service-capacity failure produced no
verdict; the same initial review resumed and completed. No second FULL review.

Verdict: BLOCK; one blocking finding.

- **FSCI-D01 BLOCKING OPEN:** getent absence before Ansible user-task does not
  prove this invocation created the account. A concurrent creator can cause
  the subsequent chpasswd to replace an existing password. Smallest correction:
  standard atomic useradd, stop on failure; password initialization only after
  successful exclusive creation. Native race test must preserve the competing
  account's password. No new locks or owner markers required.
- **FSCI-N01 NON_BLOCKING OPEN:** source selection is local UI state while
  a prior plan can be restored. The displayed source can differ from the
  fingerprint-bound request. No authorization bypass found. Distinguish next
  plan settings from restored plan parameters, or project the stored source.
- **FSCI-N02 NON_BLOCKING OPEN:** verifier internal failure returns2 but is
  presented as PASSWORD_MISMATCH. A distinct safe unavailable code is useful.

Overengineering: no blocking finding. Existing request type is reused; the
account task sequence and system libcrypt were justified. Review did not run
tests, contact targets or establish React/Wails acceptance.

## Owner response and correction

Owner requested detail, then explicitly authorized fixing FSCI-D01 through
useradd, native Ansible race coverage and one TARGETED_RECHECK. Creation now
uses useradd; password derivation/initialization requires its successful result.
The test injects a competing creator between production getent and production
useradd and checks that its password remains unchanged. Recheck pending;
FULL_PROJECT run has not started.

## TARGETED_RECHECK FSCI-D01

Owner-approved single recheck: APPROVE, FSCI-D01 RESOLVED, blocking0.
Exact two-file manifest
d7644b3934190846e66a6987610fc1090a463a65baa4670fb26ba1a3c67ffe99
independently confirmed. Standard useradd failure stops execution; hash and
chpasswd depend on its successful rc0. Native test uses the production YAML
sequence and proves rejection, password preservation and protected output.
No added lock/marker/DTO infrastructure. N01/N02 remain nonblocking open;
they were not part of this recheck. Reviewer did not execute tests or access
targets; native3tests/25.753s were run by the parent. Full installation pending.
