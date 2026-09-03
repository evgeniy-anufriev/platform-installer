# `platform.core.pki_deploy`

Атомарно развёртывает target-owned files из уже разрешённых PKI plans; это target
часть `pki-apply.yml`. PKI настраивается через desired state/materialization,
а не ручной подменой destination files.

Публичные integration inputs — project identity, selected plan list и owner/group
потребителя. Plans, persistent PKI state, fingerprints, certificates, keys и
stores — managed artifacts; их нельзя изменять вручную.
