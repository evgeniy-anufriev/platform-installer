# `platform.core.pki_deploy`

Атомарно развёртывает target-owned files из уже разрешённых PKI plans; это target
часть `pki-apply.yml`. Устанавливает CA каждого используемого authority в системное
хранилище доверия (`/etc/pki/ca-trust/source/anchors`) и запускает
`update-ca-trust`. Якоря именуются хэшами проекта и authority: разные проекты
сосуществуют. Установленные якоря намеренно сохраняются. Обновление хранилища
запускается при каждом PKI-развёртывании, поэтому повтор после ошибки
`update-ca-trust` восстанавливает системное состояние.
PKI настраивается через
desired state/materialization, а не ручной подменой destination files.

Публичные integration inputs — project identity, selected plan list и owner/group
потребителя. Plans, persistent PKI state, fingerprints, certificates, keys и
stores — managed artifacts; их нельзя изменять вручную.
