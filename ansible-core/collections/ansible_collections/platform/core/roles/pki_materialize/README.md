# `platform.core.pki_materialize`

Разрешает authorities, certificate/TLS profiles и SAN policy в derived
materialization plans, затем создаёт или явно переиздаёт managed material на
Execution Node. Используйте `pki-apply.yml`, read-only `pki-verify.yml` или
явный `pki-reissue.yml` с request IDs. Выбранный существующий request явно
переиздаётся и при неизменной certificate identity; обычный `pki-apply.yml`
сохраняет fail-closed поведение и не переиздаёт material автоматически.

Пользователь задаёт PKI в `platform_desired_state`; policy defaults находятся в
`defaults/main.yml`. Plans, runtime roots и generated identities редактировать
нельзя. `platform_pki_secret_files` содержит только mapping SecretRef →
runtime-only file, а не значения секретов.
