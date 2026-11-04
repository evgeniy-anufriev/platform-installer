# PKI-01 — Certificate and Java-store materialization

PKI-01 provides a standalone Ansible certificate foundation. It does not
enable Kafka TLS, change any Kafka role, or introduce a generic service
listener runtime model.

## Desired and runtime boundaries

`project.yml.desiredState` may declare managed `certificateAuthorities`,
`certificateProfiles`, and `tlsProfiles`. A deployment or inventory member
opts in through the ordinary `configuration.tlsProfile` reference. The default
scope is `HOST`; `MEMBER`, `DEPLOYMENT` and `PROJECT` are explicit alternatives.
A single TLS profile can use `PROJECT`. Its bound services and applications
share one leaf certificate and private key across their placements. The
certificate profile's SAN switches govern the combined host DNS and IP,
service and HTTPS application endpoint DNS, wildcard DNS and endpoint VIPs.

Normal managed users do not provide key algorithm, key size, validity, usages,
or SAN lists. `platform.core.pki_materialize` role defaults are the sole
canonical source for policy: HOST scope, RSA-3072, 3650-day CA, 365-day leaf,
`serverAuth`, and placed-host DNS/IP SANs. These are ordinary role defaults,
so `group_vars`, `host_vars`, play vars and extra vars retain normal Ansible
precedence. Platform Installer's required `ansible.cfg` sets
`hash_behaviour = merge`, so a partial policy map in `group_vars` or
`host_vars` recursively overlays the role baseline. Schema values are
descriptive only; the resolver receives the effective role-variable mapping
explicitly and has no competing product defaults. C/ST/L/O/OU are optional advanced leaf-subject fields and
default to empty; the derived common name remains the only default DN value.
Profile fields are optional advanced policy overrides. Explicit certificate
scopes remain a contract-level advanced input; manual standalone callers may
provide resolved request/plan data directly.

The resolver returns only `certificateRequestFingerprint` and
`materializationFingerprint` plus identity, path and secret *references*.
Private keys, certificate bytes, passwords and password-file contents are
never part of desired state, plans, fingerprints, facts or diagnostics.

## Materialization lifecycle

`pki-apply.yml` resolves managed topology bindings unless callers supplied the
public manual `platform_pki_requests` and
`platform_pki_materialization_plans` inputs. The Execution Node creates the
managed CA, leaf PEM and dedicated PKCS12 key/trust stores below its persistent
execution state. Target deployment copies only request-owned material with
atomic Ansible copy operations and restrictive permissions.

Store passwords are identified persistently only by the TLS profile's stable
`storePasswordSecretRef` (for example, a provider reference). At invocation,
the provider maps that reference through `platform_pki_secret_files[secretRef]`
to a pre-existing `0600` runtime file. This file is materialization transport,
not password state: deleting it does not change a generated PKCS12 store, and
a later consumer such as SERVICE-02A must resolve the same SecretRef again.
Values never enter project data, inventory, plans, fingerprints, logs or argv.
Sensitive OpenSSL/keytool/copy tasks use `no_log`.

Ordinary reconcile preserves a valid initialized certificate identity. A changed
certificate or authority fingerprint returns `CERTIFICATE_REISSUE_REQUIRED`.
Owner decision 2026-11-03: if managed leaf key/certificate material is missing,
cannot be decoded, has an invalid certificate signature/issuer chain, or the
key does not match the saved certificate,
the same running `PKI_APPLY` selects the existing request-scoped reissue path.
This repairs generated state without a new plan or separate `PKI_REISSUE`
operation. It applies only when the saved request fingerprint still equals the
current desired fingerprint, no interrupted-reissue marker exists, and the
existing authority guards pass. Existing available leaf/store files are backed
up before replacement; missing files are skipped during backup. CA key,
certificate and policy are preserved. Missing or corrupt CA is NOT recovered
automatically; the existing CA state/policy guards remain. Symlinks, unknown
partial state and technical comparison failures still block. Failure
of the one reissue stops Apply; there is no retry loop or rollback claim.

CSR is derived runtime state. If a leaf certificate must be created, its CSR
is regenerated from the current private key even if an old CSR exists.
An existing certificate suppresses CSR creation; a valid repeat keeps identity
and returns no changes. Previously damaged pairs are repaired by the above
reissue path, not by silently signing another certificate outside Apply.

The runtime password for derived PKCS12 stores may be changed independently:
when valid persistent PEM key/certificate material still matches the request
and CA identity, Core rebuilds only the keystore/truststore pair with the newly
provided runtime password. If the stores already validate against that
password and expected PEM identity, they remain unchanged. Missing or invalid
authoritative certificate PEM uses full leaf-request recovery as described
above; valid leaf PEM uses password-only store recovery. Password-only recovery
does not issue a new certificate or bypass explicit reissue authorization.
The MANAGED CA private key and marker are persistent Execution Node state under
`platform_execution_state_root` (default
`/var/lib/platform-installer/execution/pki`), never the ephemeral private
workspace. A missing previously-created CA key is partial state and blocks;
the role never regenerates it. Other partial authority/request state returns a
blocking diagnostic. Automatic renewal and CA rotation remain outside PKI-01.
An explicit leaf-certificate reissue is available only through
`ansible-core/playbooks/pki-reissue.yml` with a non-empty runtime
`platform_pki_reissue_request_ids` list. It records a recovery marker,
preserves old request material in protected Execution Node state, rekeys and
reissues only the selected request, even when its desired certificate identity
is unchanged, then clears the marker after materialization and store repair. This allows
an operator-authorized certificate/key reissue without inventing a
CN/SAN/profile change. Password-only PKCS12 rebuilding is separate and
preserves leaf identity. Ordinary `pki-apply.yml` still blocks changed request
identities and preserves valid initialized material; automatic lost-leaf-key
recovery is the owner-approved exception described above. The certificate profile
`usages` collection already supports
`serverAuth`, `clientAuth`, or both; the current product default is both
`serverAuth` and `clientAuth`. Explicit profile `usages` override this default.

`pki-verify.yml` only resolves the plan, checks target-owned files,
fingerprints and certificate chains, and reports `changed=0`.

## Контракт service apply

Каждый playbook TLS-capable сервиса импортирует `pki-apply.yml` до изменения
конфигурации или запуска роли сервиса. PKI-резолвер строит requests и планы
для TLS-потребителей из canonical project. Само объявление
`certificateProfile` или `tlsProfile` ничего не материализует: deployment или
member сервиса должен явно выбрать `tlsProfile`.

Повторное использование одного TLS-профиля несколькими deployment не делает
их сертификатные запросы взаимозаменяемыми. Перед изменением сервиса роль
находит запрос по его `consumers` (deployment, host, member и TLS-профиль),
затем выбирает materialization plan по `requestId` и host. В управляемом
исполнении точный deployment передаётся из текущей операции плана. В обычном
Ansible запуске без этого контекста разрешён только единственный подходящий
план; неоднозначность блокирует запуск до изменения сервиса. Нельзя выбирать
первый план по паре host/TLS-профиль.

Если у выбранного сервиса нет TLS-потребителей, PKI-резолвер возвращает пустой
plan и не создаёт PKI-каталоги Execution Node или файлы на targets. Отдельный
Core `pki-apply.yml` остаётся без фильтра и намеренно reconcile’ит всех
TLS-потребителей проекта.

## CSR and leaf recovery validation, 2026-11-03

Owner's isolated-system evidence: the saved CSR dated November 1 matches the
certificate written November 3, while the newly written private key differs.
The root cause of the older private key's disappearance remains unproven.
The role's CSR `creates` guard previously accepted that stale runtime CSR;
it now guards on the authoritative leaf certificate instead, so an issuance
always uses the current private key.

Final owner scope: automatic recovery of missing/corrupt **leaf** key/certificate
inside the same Apply; no automatic CA recovery, no container changes, no new
Ansible files, no review. Intermediate CA recovery work was removed. The original
CA state/policy assertions and CA-generation task block match the baseline.
Only the existing request/stores task files and read-only planning state guard
changed. The latter admits missing leaf PEM for a known request so planning does
not prevent the current Apply from performing the authorized recovery.

Native validation used current working-tree sources on RED OS101 in verified
qa-sync workspace `/var/tmp/platform-installer-qa-a5867b091ec94ab586247c22c44a51f8`.
All PKI roots, generated identities, password files and trust-boundary fixtures
were isolated; no installed services or production PKI were changed.

- Final focused state/resolution/contracts/controller-lock/dispatch and native
  completed-reissue guard selection: 40 PASS (2.905s).
- Native stale-CSR issuance and unchanged repeat passed in its 22-case selection
  (133.062s): new key, CSR and certificate match; repeat `changed=0`.
- Native missing-key and different-key recovery plus comparison-tool failure:
  2 PASS (520.591s). Exactly the damaged request is reissued; another resolved
  request and CA bytes remain unchanged; available source material is backed up;
  recovery marker is cleared and repeat `changed=0`.
- Final missing/invalid/signature-corrupt leaf certificate selection: 35 PASS
  (205.121s, includes repeated unit cases), with clean repeat.
- Existing changed-authority refusal test PASS; it retained prior CA/request
  material. Initial test assertions incorrectly counted skipped task headings as
  executed reissues; corrected assertions count changed outcomes. A missing YAML
  import in the added test was corrected before the final PASS.

These selections cover 45 distinct tests; they are focused checks, not full Core
regression or installation acceptance. Temporary QA workspace was cleaned with
the standard helper. No runtime bundle build/publication/rebind, real
React/Wails flow, installation or Start was performed. The isolated installation
requires an updated runtime bundle; existing failed-run history is unchanged.

## Deferred integration

PKI-01 supports only `MANAGED` authorities, PEM, dedicated PKCS12 stores and
server-auth certificates. Imported/external CA, JKS, mTLS, global JVM cacerts,
renewal and rotation are deferred. Kafka becomes a PKI consumer only in the
separate SERVICE-02A listener/SSL milestone.

### TODO: imported or external CA material

Add a versioned `IMPORTED` authority/certificate contract for certificates
issued by an external CA. Desired state must contain only stable references:
the external trust bundle, leaf certificate, private key, PKCS12 stores and
their passwords must arrive through runtime-only SecretRefs, never inventory
or project files. PKI materialization must validate and deploy those inputs as
consumer-owned PKCS12 material; a Kafka deployment then selects one
`configuration.tlsProfile`, which every SSL listener on that service/member
uses. This work must preserve the existing `MANAGED` authority contract and
must not add plaintext secrets to plans, fingerprints or logs.
