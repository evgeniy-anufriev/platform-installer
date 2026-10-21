# SZI stage 1 — независимый FULL DIFF и решение владельца

Независимый вердикт 2026-10-21: **BLOCK**, один пункт SZI-D04. Проверен base
`7f044699f5b66ccbad4603978472275ce2010235` и незакоммиченный текстовый
diff с fingerprint
`138774EC001D313D6CA929AAD249A609FED146EBDA7CDA5ADF5C72736023C015`.
Ignored binary assets не входили в этот fingerprint.

**SZI-D04 — требование reviewer, отклонено владельцем.** В публичном
DeploymentPlan есть общее действие `applications:apply`, а декларация
`restore_on_create` и её digest входят в semantic fingerprint. Reviewer
предложил показать в действии отдельный несекретный restore descriptor
(resource/provider/database/digest, only-on-create), поскольку прежняя
формулировка плана обещала видимую операцию восстановления. Остальные
обнаруженные в ходе FULL DIFF замечания D01–D03 были исправлены до итогового
заключения: пароль для `kcadm` не передаётся в argv; временный CLI-контейнер
rootless Docker использует корректное отображение UID; `start_priority`
запускает Keycloak раньше зависимых приложений. Generic runner не содержит
веток для СЗИ, Keycloak, Docker или Compose.

**Решение владельца 2026-10-21:** не вводить restore-only детализацию плана.
Публичный план ранее не показывал подробности каждого действия; изменение
только ради `restore_on_create` было бы непоследовательным. Единый подробный
показ действий всех типов не входит в первый этап СЗИ. Формулировка
[технического плана](../szi-stage1-technical-plan.md) исправлена: декларация
restore участвует в fingerprint общего Apply, отдельный публичный descriptor
не требуется. SZI-D04 снят решением владельца **по объёму этапа**, не
техническим исправлением и не новым одобрением reviewer. Исторический
вердикт FULL DIFF остаётся `BLOCK`; targeted recheck по отвергнутому пункту
не проводится.

Границы доказательств: RED OS application suite 145 PASS/1 skip, SZI5,
native generic runner1 и Apply syntax PASS, focused Go и frontend267/build/lint
PASS по проверкам исполнителя. Содержимое ignored dump/theme/JAR reviewer не
проверял. Восстановление PostgreSQL, bootstrap точного образа Keycloak,
реальный React/Wails flow и повторный Apply остаются приёмочными проверками.
