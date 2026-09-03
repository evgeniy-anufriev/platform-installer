# `platform.core.pki_verify`

Read-only проверка target-owned PKI material: files, certificate chain и
materialization fingerprint. Используйте `pki-verify.yml`, который сам
восстанавливает derived plans на controller.

Единственный вход — derived plan list. Нельзя сохранять/подделывать plans или
fingerprints для прохождения verify: role не выпускает сертификаты, не пишет
generated state и не меняет target material.
