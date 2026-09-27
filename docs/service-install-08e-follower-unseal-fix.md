# SI08-E follower unseal correction

Owner authorized the narrow correction on 2026-09-28. The follower include
previously passed `vault_member: "{{ vault_member }}"`, shadowing the outer
loop variable with a recursive template. Remove only this redundant override;
the existing `vault_member` loop remains the authority for the current follower.
No protocol, TLS, bootstrap custody, reset or standalone behavior was redesigned.

## Regression evidence

Fresh RED OS source transfer used `scripts/qa-sync.ps1`; its temporary workspace
was removed afterward. `python3 -m unittest discover -s services/vault/tests -v`:
21 PASS in 2.535s. The new focused test validates the outer loop variable and
uses real Ansible Templar to resolve follower identity and TLS API endpoints
for colocated and distributed members without a recursive override.
Catalog/configuration-schema reproducibility, verifier syntax-check,
`go test ./...`, `go vet ./...` and `git diff --check`: PASS.

## Real HA 3/1 recovery

Immutable release `qa-si08-vault-20260928-15`:
`sha256:c6a54fca6cede1c53b935f828accb75bf5413e97c167e083674603efc7fc4f03`.
Catalog unchanged. Supported QA promotion verified/published/activated the
new release and advanced project locks through guarded CAS.

The preceding failed run's bootstrap package was delivered and acknowledged
through actual React/Wails into encrypted files under `secrets/vault-qa-ha31/`.
The actual React secret-file handlers imported both files into the session.
No token/shares were logged and no initialized seed was reset or reinitialized.

Fresh plan `plan-c0ccd228d15b7c1481d0b0f1`, saved revision
`sha256:ddf3f1e2c8248810ae69c30b08a963f3b00a7061f71a72d89fa434a9004f70e4`.
Actual React/Wails approval/Start/observe/result:
`installer-1fc2dacbcb428c7ebf2375f981086e12` SUCCEEDED in 2160s (36m),
terminal sequence 942. PKI/apply/verify SUCCESS at sequences 149/761/941.
Task stream: 367 SUCCESS, 98 SKIPPED, 1 CHANGED, 0 FAILED; no sequence gaps
or degraded task observability. The single changed task started the previously
unstarted second follower. This is recovery/installation PASS, NOT a
changed=0 repeat claim. Result output list READY/NO_NEW_PACKAGE.

All three HA units active. TLS-validated health on ports 8300/8302/8304:
all initialized/unsealed, one leader and two standbys, same cluster identity
`dfcf9c15-cf74-5efd-8af4-bf81b04af50d`. Accepted standalone remains ACTIVE.
The existing role's separate verify passed; visual UI acceptance is not claimed.

## Remaining acceptance

Strict repeat changed=0, HA 3/3, failover/restart and final SI08-E gates remain
pending. Reversible current-boot swap masks remain on QA hosts; reboot removes
them. Do not interpret this correction as overall SI08-E DONE.
