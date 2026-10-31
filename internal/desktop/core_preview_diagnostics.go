package desktop

import (
	"context"
	"errors"
	"platform-installer/internal/executionnode"
	"strings"
	"unicode"
)

// Presentation only: Core codes and validation severity remain authoritative.
var projectFindingMessagesRU = map[string]string{
	"ROLE_DEFAULT_TYPE_INVALID":                               "Тип значения роли по умолчанию не соответствует описанию настройки.",
	"ROLE_DEFAULT_VALIDATION_INVALID":                         "Значение роли по умолчанию нарушает ограничения настройки.",
	"SERVICE_CONFIGURATION_ADVANCED_TYPE_INVALID":             "Расширенные настройки сервиса должны иметь допустимый объектный тип.",
	"SERVICE_CONFIGURATION_CONTRACT_CONFLICT":                 "В пакете сервиса одновременно заданы конфликтующие форматы описания настроек.",
	"SERVICE_CONFIGURATION_KIND_INVALID":                      "Недопустим вид настройки сервиса.",
	"SERVICE_CONFIGURATION_LOGICAL_ID_INVALID":                "Некорректен логический идентификатор настройки сервиса.",
	"SERVICE_CONFIGURATION_ROLE_VARIABLE_DUPLICATE":           "Несколько настроек сервиса ссылаются на одну переменную роли.",
	"SERVICE_CONFIGURATION_ROLE_VARIABLE_INVALID":             "Некорректно имя переменной роли в описании настройки.",
	"SERVICE_CONFIGURATION_SCOPES_INVALID":                    "Недопустима область применения настройки сервиса.",
	"SERVICE_CONFIGURATION_SETTINGS_INVALID":                  "Описание настроек сервиса должно быть объектом.",
	"SERVICE_CONFIGURATION_SETTING_INVALID":                   "Некорректна структура описания настройки сервиса.",
	"SERVICE_CONFIGURATION_VALIDATION_INVALID":                "Некорректно описание ограничений настройки сервиса.",
	"SERVICE_CONFIGURATION_VALIDATION_TYPE_INVALID":           "Тип ограничения настройки не соответствует типу её значения.",
	"ADVANCED_SETTING_RESERVED":                               "Расширенная настройка использует зарезервированное имя.",
	"APPLICATION_BOOTSTRAP_PROVIDER_INVALID":                  "Для начальной настройки приложения выбран недопустимый поставщик секретов.",
	"APPLICATION_INFRASTRUCTURE_BARRIER_REQUIRED":             "Перед приложениями требуется проверка готовности инфраструктуры.",
	"APPLICATION_PROVIDER_INPUT_INVALID":                      "Некорректны входные параметры поставщика ресурсов приложения.",
	"APPLICATION_SCRIPT_EXECUTION_FAILED":                     "Сценарий приложения завершился ошибкой.",
	"ARTIFACT_SOURCE_AMBIGUOUS":                               "Для артефакта найдено несколько подходящих источников; выбор неоднозначен.",
	"ARTIFACT_SOURCE_OFFLINE_REQUIRED":                        "В наборе установки отсутствует обязательный артефакт для автономной установки.",
	"CERTIFICATE_AUTHORITIES_INVALID":                         "Некорректно описание центров сертификации.",
	"CERTIFICATE_AUTHORITY_NOT_FOUND":                         "Указанный центр сертификации не найден.",
	"CERTIFICATE_AUTHORITY_UNSUPPORTED":                       "Выбранный режим центра сертификации не поддерживается.",
	"CERTIFICATE_CONSUMER_HOST_REQUIRED":                      "Для потребителя сертификата необходимо указать сервер.",
	"CERTIFICATE_IDENTITY_VALUE_INVALID":                      "Некорректно DNS-имя или IP-адрес в идентификаторах сертификата.",
	"CERTIFICATE_PROFILES_INVALID":                            "Некорректно описание профилей сертификатов.",
	"CERTIFICATE_PROFILE_NOT_FOUND":                           "Указанный профиль сертификата не найден.",
	"CERTIFICATE_SCOPE_INVALID":                               "Недопустима область действия сертификата.",
	"CONTROLLER_LISTENER_REQUIRED":                            "Для контроллера Kafka необходимо настроить слушатель соединений.",
	"DNS_CLIENT_SERVER_NOT_FOUND":                             "DNS-клиент должен ссылаться на существующее развёртывание авторитетного DNS-сервера.",
	"DNS_CLIENT_SERVER_RESOLUTION_BLOCKED":                    "Параметры DNS-сервера, выбранного для клиента, не удалось разрешить из-за ошибок конфигурации.",
	"DNS_CLIENT_SERVER_TYPE_INVALID":                          "Для DNS-клиента выбран сервис неподходящего типа.",
	"DNS_DEFAULT_TTL_INVALID":                                 "Некорректно время жизни DNS-записей по умолчанию.",
	"DNS_ENDPOINT_ADDRESS_UNRESOLVED":                         "Не удалось определить адрес конечной точки для DNS-записи.",
	"DNS_ENDPOINT_GROUP_OUTSIDE_ZONE":                         "Домен группы конечных точек находится за пределами управляемой DNS-зоны.",
	"DNS_ENDPOINT_MODE_INVALID":                               "Выбран недопустимый режим публикации конечных точек в DNS.",
	"DNS_ENDPOINT_PROVIDER_AMBIGUOUS":                         "Для конечной точки найдено несколько DNS-поставщиков; выбор неоднозначен.",
	"DNS_HOST_ADDRESS_UNRESOLVED":                             "Не удалось определить адрес сервера для DNS-записи.",
	"DNS_HOST_ID_INVALID":                                     "Идентификатор сервера недопустим для формирования DNS-имени.",
	"DNS_PARTICIPANT_ROLE_INVALID":                            "Участнику DNS назначена недопустимая роль.",
	"DNS_PRIMARY_COUNT_INVALID":                               "В DNS-развёртывании должно быть допустимое число основных серверов.",
	"DNS_PROVIDER_ADDRESS_INVALID":                            "Некорректен адрес поставщика DNS.",
	"DNS_RECORD_COLLISION":                                    "Несколько настроек создают конфликтующие DNS-записи.",
	"DNS_SOURCE_DEPLOYMENT_SELECTION_INVALID":                 "Некорректно выбрано исходное развёртывание для публикации DNS-записей.",
	"DNS_WILDCARD_MODE_INVALID":                               "Недопустим режим использования подстановочных DNS-записей.",
	"DNS_ZONE_INVALID":                                        "Управляемая DNS-зона должна быть полным доменным именем в нижнем регистре.",
	"ENDPOINT_BACKEND_NAME_COLLISION":                         "Имена целевых групп конечных точек совпадают.",
	"ENDPOINT_DEPLOYMENT_ID_NOT_DNS_LABEL":                    "Идентификатор развёртывания недопустим как часть DNS-имени конечной точки.",
	"ENDPOINT_FQDN_COLLISION":                                 "Несколько конечных точек используют одинаковое полное доменное имя.",
	"ENDPOINT_GROUPS_INVALID":                                 "Некорректно описание групп конечных точек.",
	"ENDPOINT_GROUP_DOMAIN_DUPLICATE":                         "Домен группы конечных точек указан повторно.",
	"ENDPOINT_GROUP_DOMAIN_INVALID":                           "Некорректен домен группы конечных точек.",
	"ENDPOINT_GROUP_NOT_FOUND":                                "Указанная группа конечных точек не найдена.",
	"ENDPOINT_PROVIDER_FIELD_REQUIRED":                        "У поставщика конечных точек не заполнен обязательный параметр.",
	"ENDPOINT_PROVIDER_UNSUPPORTED":                           "Сервис не поддерживает выбранную роль поставщика конечных точек.",
	"ENDPOINT_SERVICE_UNSUPPORTED":                            "Сервис не поддерживает требуемый тип конечной точки.",
	"ENDPOINT_SOURCE_ID_COLLISION":                            "Идентификаторы источников конечных точек совпадают.",
	"ENDPOINT_SOURCE_INVALID":                                 "Некорректно описание источника конечной точки.",
	"EXECUTION_CANDIDATE_INELIGIBLE":                          "Выбранный сервер не подходит для выполнения операций проекта.",
	"EXECUTION_NODE_NO_ELIGIBLE_CANDIDATE":                    "В проекте нет подходящего узла выполнения.",
	"EXECUTION_ORDER_DEPENDENCY_CONFLICT":                     "Порядок выполнения противоречит зависимостям сервисов.",
	"HAPROXY_BACKEND_BALANCE_INVALID":                         "Недопустим алгоритм балансировки; разрешены roundrobin, leastconn и source.",
	"HAPROXY_BACKEND_CHECK_INVALID":                           "Признак проверки работоспособности должен быть логическим значением.",
	"HAPROXY_BACKEND_SSL_INVALID":                             "Признак TLS для целевых серверов должен быть логическим значением.",
	"HAPROXY_BACKEND_FALL_REQUIRED":                           "Для проверки работоспособности укажите число неудач fall от 1 до 20.",
	"HAPROXY_BACKEND_RISE_REQUIRED":                           "Для проверки работоспособности укажите число успешных проверок rise от 1 до 20.",
	"HAPROXY_BACKEND_CHECK_DEPENDENCY_FORBIDDEN":              "Параметры fall и rise допустимы только при включённой проверке работоспособности.",
	"HAPROXY_BACKEND_DEFAULTS_INVALID":                        "Настройки целевых серверов по умолчанию должны быть объектом.",
	"HAPROXY_BACKEND_DURATION_INVALID":                        "Некорректно значение длительности в настройках целевых серверов.",
	"HAPROXY_BACKEND_HTTP_CHECK_INVALID":                      "Некорректно описание HTTP-проверки работоспособности.",
	"HAPROXY_BACKEND_MAXCONN_INVALID":                         "Некорректно ограничение числа соединений maxconn.",
	"HAPROXY_BACKEND_PORT_COLLISION":                          "Порты целевых серверов конфликтуют.",
	"HAPROXY_BACKEND_PORT_UNRESOLVED":                         "Не удалось определить порт целевого сервера.",
	"HAPROXY_BACKEND_PROPERTY_UNKNOWN":                        "В настройках целевых серверов указан неподдерживаемый параметр.",
	"HAPROXY_BACKEND_SSL_VERIFY_FORBIDDEN":                    "Проверка сертификата sslVerify допустима только при включённом TLS.",
	"HAPROXY_BACKEND_SSL_VERIFY_REQUIRED":                     "Для TLS-соединения с целевым сервером необходимо задать sslVerify.",
	"HAPROXY_BACKEND_TARGETS_UNRESOLVED":                      "Не удалось определить целевые серверы HAProxy.",
	"HAPROXY_BACKEND_TLS_IDENTITY_UNRESOLVED":                 "В запросе сертификата целевого сервера отсутствует DNS-имя конечной точки.",
	"HAPROXY_CLIENT_LISTENER_DESCRIPTOR_INVALID":              "Некорректно описание клиентского слушателя HAProxy.",
	"HAPROXY_HEALTH_TRACKING_DEPLOYMENT_NOT_FOUND":            "Развёртывание для отслеживания работоспособности HAProxy не найдено.",
	"HAPROXY_HEALTH_TRACKING_DEPLOYMENT_TYPE_INVALID":         "Для отслеживания работоспособности HAProxy выбран сервис неподходящего типа.",
	"HAPROXY_HEALTH_TRACKING_ENDPOINT_GROUP_MISMATCH":         "Группа конечных точек отслеживаемого сервиса не совпадает с группой HAProxy.",
	"HAPROXY_HEALTH_TRACKING_PARTICIPANT_MISSING":             "Отсутствует обязательный участник отслеживания работоспособности HAProxy.",
	"HAPROXY_INTEGRATION_INVALID":                             "Некорректно описание интеграции HAProxy.",
	"HAPROXY_TARGET_ENDPOINT_UNSUPPORTED":                     "HAProxy не поддерживает выбранную целевую конечную точку.",
	"HOST_ENDPOINT_FQDN_COLLISION":                            "Конечные точки серверов используют одинаковое полное доменное имя.",
	"HOST_ENDPOINT_HOST_ID_NOT_DNS_LABEL":                     "Идентификатор сервера недопустим как часть DNS-имени конечной точки.",
	"HOST_ENDPOINT_INVALID":                                   "Некорректно описание конечной точки сервера.",
	"HOST_ENDPOINT_WILDCARD_REQUIRED":                         "Для конечной точки сервера требуется подстановочное DNS-имя.",
	"HOST_SCOPED_MEMBERS_FORBIDDEN":                           "Для размещения сервиса на уровне сервера нельзя задавать отдельных участников.",
	"HOST_SCOPED_PLACEMENT_INVALID":                           "Некорректно размещение сервиса на уровне сервера.",
	"HOST_SCOPED_PLACEMENT_UNSUPPORTED":                       "Сервис не поддерживает размещение на уровне сервера.",
	"HOST_TRANSPORT_PORT_INVALID":                             "Некорректен порт подключения к серверу.",
	"INTER_BROKER_LISTENER_REQUIRED":                          "Необходимо настроить слушатель для соединений между брокерами Kafka.",
	"INVALID_MEMBER_CONFIGURATION":                            "Некорректна конфигурация участника сервиса.",
	"INVENTORY_DEPLOYMENT_NOT_FOUND":                          "Развёртывание, указанное в инвентаре, не найдено.",
	"KAFKA_CLUSTER_ID_DISCOVERY_CONFLICT":                     "На узлах обнаружены противоречащие друг другу идентификаторы кластера Kafka.",
	"KAFKA_CLUSTER_ID_METADATA_MISMATCH":                      "Идентификатор кластера Kafka не совпадает с метаданными на диске.",
	"KAFKA_DIRECTORY_ID_METADATA_MISMATCH":                    "Идентификатор каталога Kafka не совпадает с метаданными на диске.",
	"KAFKA_IDENTITY_DISCOVERY_DUPLICATE":                      "При обнаружении Kafka получены повторяющиеся идентификаторы.",
	"KAFKA_IDENTITY_DISCOVERY_INCOMPLETE":                     "Не удалось получить все идентификаторы существующей установки Kafka.",
	"KAFKA_IDENTITY_DISCOVERY_REQUIRED":                       "Перед продолжением необходимо обнаружить идентификаторы существующей установки Kafka.",
	"KAFKA_IDENTITY_DISCOVERY_UNKNOWN":                        "Состояние идентификаторов существующей установки Kafka не определено.",
	"KAFKA_IDENTITY_DISCOVERY_UNKNOWN_MEMBER":                 "Обнаруженные идентификаторы Kafka относятся к неизвестному участнику.",
	"LEGACY_MEMBER_HOST_CONFLICT":                             "Устаревшая привязка участника противоречит размещению по серверам.",
	"LISTENERS_INVALID":                                       "Некорректно описание слушателей соединений.",
	"LISTENERS_REQUIRED":                                      "Необходимо настроить слушатели соединений.",
	"LISTENER_INVALID":                                        "Некорректно описание слушателя соединений.",
	"LISTENER_NAME_INVALID":                                   "Недопустимо имя слушателя соединений.",
	"LISTENER_PORT_COLLISION":                                 "Слушатели соединений используют конфликтующие порты.",
	"LISTENER_PORT_INVALID":                                   "Недопустим порт слушателя соединений.",
	"LISTENER_PROTOCOL_INVALID":                               "Слушатель использует неподдерживаемый протокол.",
	"LISTENER_PURPOSE_INVALID":                                "Недопустимо назначение слушателя соединений.",
	"LISTENER_ROLE_PROJECTION_EMPTY":                          "Для роли участника не найден подходящий слушатель соединений.",
	"MANAGED_VARIABLE_SOURCE_CONFLICT":                        "Для управляемой переменной заданы противоречащие источники.",
	"MEMBER_HOST_NOT_FOUND":                                   "Сервер, назначенный участнику сервиса, не найден.",
	"MEMBER_PLACEMENT_UNASSIGNED":                             "Участнику сервиса не назначен сервер.",
	"MEMBER_ROLES_INVALID":                                    "Некорректно заданы роли участника сервиса.",
	"MEMBER_ROLE_UNSUPPORTED":                                 "Сервис не поддерживает назначенную участнику роль.",
	"MEMBER_SCOPE_SETTING_NOT_ALLOWED":                        "Параметр нельзя переопределять на уровне участника сервиса.",
	"PERSISTED_MEMBERS_NOT_ALLOWED":                           "Список разрешённых участников не должен сохраняться в желаемом состоянии проекта.",
	"PKI_DEFAULTS_INVALID":                                    "Некорректны настройки PKI по умолчанию.",
	"PKI_STORE_PASSWORD_REFERENCE_UNSUPPORTED":                "Ссылка на пароль хранилища PKI не поддерживается.",
	"PLACEMENT_DEPLOYMENT_NOT_FOUND":                          "В размещении указан неизвестный экземпляр сервиса.",
	"PLACEMENT_DISTINCT_HOSTS_REQUIRED":                       "Участники этого сервиса должны размещаться на разных серверах.",
	"PLACEMENT_MEMBER_NOT_FOUND":                              "В размещении указан неизвестный участник сервиса.",
	"PLAINTEXT_SECRET_FIELD_FORBIDDEN":                        "В конфигурации проекта нельзя хранить секрет открытым текстом; используйте раздел «Секреты».",
	"PROJECT_API_VERSION_UNSUPPORTED":                         "Версия формата проекта не поддерживается.",
	"PROJECT_ARTIFACT_DIGEST_INVALID":                         "Некорректна контрольная сумма набора установки проекта.",
	"PROJECT_ARTIFACT_LOCK_INVALID":                           "Некорректна привязка проекта к набору установки.",
	"PROJECT_CATALOG_API_VERSION_UNSUPPORTED":                 "Версия формата каталога проекта не поддерживается.",
	"PROJECT_CATALOG_DIGEST_INVALID":                          "Некорректна контрольная сумма каталога проекта.",
	"PROJECT_CATALOG_DIGEST_MISMATCH":                         "Контрольная сумма каталога не совпадает с привязкой проекта.",
	"PROJECT_CATALOG_INVALID":                                 "Некорректно описание каталога проекта.",
	"PROJECT_CATALOG_SERVICES_INVALID":                        "Некорректно описание сервисов в каталоге проекта.",
	"PROJECT_DESIRED_STATE_CONTRACT_UNSUPPORTED":              "Версия контракта желаемого состояния проекта не поддерживается.",
	"PROJECT_IDENTITY_REQUIRED":                               "Для выполнения необходим явно заданный идентификатор проекта.",
	"PROJECT_ID_REQUIRED":                                     "Не задан обязательный идентификатор проекта.",
	"PROJECT_KIND_INVALID":                                    "Неверно указан тип документа проекта.",
	"PROJECT_SERVICE_DEFINITION_DIGEST_MISMATCH":              "Контрольная сумма определения сервиса не совпадает с привязкой проекта.",
	"PROJECT_SNAPSHOT_INPUT_INVALID":                          "Не удалось построить снимок проекта из сохранённых входных данных.",
	"PROJECT_VALIDATION_BLOCKED":                              "Проверка конфигурации проекта выявила блокирующие ошибки.",
	"ROLE_DEFAULTS_INVALID":                                   "Некорректны настройки роли по умолчанию.",
	"ROLE_DEFAULT_NOT_DECLARED":                               "Для параметра не объявлено значение по умолчанию в роли.",
	"RUNTIME_SECRET_REFERENCE_INVALID":                        "Некорректна настройка секрета; задайте пароль через раздел «Секреты».",
	"RUNTIME_SECRET_REFERENCE_REQUIRED":                       "Не задан обязательный пароль сервиса; используйте раздел «Секреты».",
	"RUNTIME_SECRET_REQUIREMENT_DUPLICATE":                    "Требование к секрету объявлено повторно.",
	"RUNTIME_SECRET_REQUIREMENT_INVALID":                      "Некорректно описание требования к секрету сервиса.",
	"RUNTIME_SECRET_REQUIREMENT_SCHEMA_INVALID":               "Схема параметра секрета несовместима с объявленным требованием.",
	"SCHEMA_REGISTRY_ENABLED_INVALID":                         "Признак включения реестра схем должен быть логическим значением.",
	"SCHEMA_REGISTRY_OFFSETS_TOPIC_REPLICATION_UNSATISFIABLE": "Для заданной репликации служебного топика реестра схем недостаточно брокеров.",
	"SCHEMA_REGISTRY_PORT_COLLISION":                          "Порт реестра схем конфликтует с другим слушателем.",
	"SCHEMA_VALIDATION_ENGINE_ERROR":                          "Не удалось выполнить проверку проекта по опубликованным схемам.",
	"SCHEMA_VALIDATION_FAILED":                                "Значение параметра не соответствует схеме проекта.",
	"SERVICE_CATALOG_DIGEST_MISMATCH":                         "Контрольная сумма каталога сервисов не совпадает с ожидаемой.",
	"SERVICE_CATALOG_INVALID":                                 "Каталог сервисов имеет некорректную структуру.",
	"SERVICE_CATALOG_LOCK_NOT_FOUND":                          "Не найдена привязка к каталогу сервисов.",
	"SERVICE_CONFIGURATION_ENUM_INVALID":                      "Выбрано значение, отсутствующее в списке разрешённых для параметра.",
	"SERVICE_CONFIGURATION_INVALID":                           "Конфигурация сервиса имеет некорректную структуру.",
	"SERVICE_CONFIGURATION_MAPPING_INVALID":                   "Некорректно сопоставление настроек сервиса с переменными роли.",
	"SERVICE_CONFIGURATION_MAPPING_REQUIRED":                  "Не задано обязательное сопоставление настройки с переменной роли.",
	"SERVICE_CONFIGURATION_MAXIMUM_INVALID":                   "Значение параметра сервиса превышает допустимый максимум.",
	"SERVICE_CONFIGURATION_MINIMUM_INVALID":                   "Значение параметра сервиса меньше допустимого минимума.",
	"SERVICE_CONFIGURATION_MIN_LENGTH_INVALID":                "Длина значения параметра сервиса меньше допустимой.",
	"SERVICE_CONFIGURATION_PROPERTY_UNKNOWN":                  "Параметр конфигурации не объявлен схемой сервиса.",
	"SERVICE_CONFIGURATION_SETTINGS_REQUIRED":                 "Не объявлены обязательные настройки сервиса.",
	"SERVICE_CONFIGURATION_TYPE_INVALID":                      "Тип значения параметра сервиса не соответствует схеме.",
	"SERVICE_DEFINITION_DIGEST_MISMATCH":                      "Контрольная сумма определения сервиса не совпадает с ожидаемой.",
	"SERVICE_DEFINITION_NOT_FOUND":                            "Определение сервиса не найдено в каталоге.",
	"SERVICE_DEFINITION_VERSION_MISMATCH":                     "Версия определения сервиса не совпадает с привязкой проекта.",
	"SERVICE_DEPLOYMENTS_INVALID":                             "Некорректно описание развёртываний сервисов.",
	"SERVICE_DEPLOYMENT_INVALID":                              "Некорректно описание экземпляра сервиса.",
	"SERVICE_INTEGRATION_SOURCE_NOT_FOUND":                    "Не найден источник, указанный в интеграции сервиса.",
	"SERVICE_MEMBERS_INVALID":                                 "Некорректно описание участников сервиса.",
	"SERVICE_MEMBER_COUNT_ABOVE_MAXIMUM":                      "Число участников сервиса превышает допустимый максимум.",
	"SERVICE_MEMBER_COUNT_BELOW_MINIMUM":                      "Число участников сервиса меньше необходимого минимума.",
	"SERVICE_MODE_UNSUPPORTED":                                "Выбранный режим работы сервиса не поддерживается.",
	"SERVICE_ROLE_COUNT_ABOVE_MAXIMUM":                        "Слишком много участников сервиса с указанной ролью.",
	"SERVICE_ROLE_COUNT_BELOW_MINIMUM":                        "Недостаточно участников сервиса с указанной ролью.",
	"SERVICE_SECRET_INPUT_DUPLICATE":                          "Входные данные секрета сервиса указаны повторно.",
	"SERVICE_SECRET_INPUT_METADATA_INVALID":                   "Некорректно описание входных данных секрета сервиса.",
	"SERVICE_SECRET_INPUT_PLACEMENT_INVALID":                  "Некорректно размещение потребителя секрета сервиса.",
	"SERVICE_TARGETS_UNAVAILABLE":                             "Для сервиса не найдены доступные целевые серверы.",
	"SERVICE_TYPE_REQUIRED":                                   "Не указан обязательный тип сервиса.",
	"STATIC_REFERENCE_NOT_FOUND":                              "Не найдена переменная, на которую ссылается настройка.",
	"TLS_PROFILES_INVALID":                                    "Некорректно описание профилей TLS.",
	"TLS_PROFILE_NOT_FOUND":                                   "Указанный профиль TLS не найден.",
	"TLS_PROFILE_REQUIRED":                                    "Не выбран TLS-профиль сервиса. Создайте профиль TLS и сохраните проект; первый доступный профиль будет выбран автоматически.",
	"VARIABLE_DOCUMENT_BINDING_INVALID":                       "Некорректна привязка переменной к документу проекта.",
	"VARIABLE_DOCUMENT_ORIGIN_INVALID":                        "Некорректно указан источник документа с переменными.",
	"VIRTUAL_ADDRESS_DUPLICATE":                               "Виртуальный адрес указан повторно.",
}

func projectFindingMessageRU(code, message string) string {
	for _, r := range strings.TrimSpace(message) {
		if unicode.IsLetter(r) {
			if unicode.In(r, unicode.Cyrillic) {
				return message // Preserve bounded Russian stage/cause diagnostics.
			}
			break
		}
	}
	if translated, ok := projectFindingMessagesRU[code]; ok {
		if code == "HAPROXY_BACKEND_TLS_IDENTITY_UNRESOLVED" && message == "Backend TLS identity is unavailable" {
			return "Не удалось определить DNS-имя конечной точки целевого сервиса для проверки TLS. Проверьте привязку группы конечных точек."
		}
		return translated
	}
	return "Проверка проекта обнаружила замечание для указанной настройки. Подробное описание этого кода отсутствует в текущей версии Installer."
}

func servicePreviewFailureFinding(err error) executionnode.Finding {
	reasons := map[string]string{
		"SERVICE_CONFIGURATION_PREVIEW_UNAVAILABLE":      "Сохранённый проект и готовая привязка узла недоступны для запроса Core.",
		"SERVICE_CONFIGURATION_PREVIEW_UNSUPPORTED":      "Runtime не подтвердил поддерживаемую версию capabilities и операцию BuildServiceConfigurationPreview.",
		"SERVICE_CONFIGURATION_PREVIEW_INPUT_INVALID":    "Запрос Core-проекции содержит некорректные входные данные.",
		"SERVICE_CONFIGURATION_PREVIEW_RESPONSE_INVALID": "Ответ Core-проекции не соответствует контракту.",
		"SERVICE_CONFIGURATION_PREVIEW_STALE":            "Проект, runtime или привязка узла изменились во время получения Core-проекции.",
		"PROJECT_SNAPSHOT_INPUT_INVALID":                 "Core не смог построить снимок входных данных проекта.",
		"PROJECT_SNAPSHOT_FAILED":                        "Core завершил построение снимка проекта с ошибкой.",
		"CORE_OPERATION_FAILED":                          "Операция Core завершилась ошибкой до публикации результата.",
		"PROJECT_REVISION_CHANGED":                       "Сохранённая ревизия проекта изменилась.",
		"EXECUTION_RUNTIME_IDENTITY_UNCONFIRMED":         "Ответ Core не содержит подтверждённую идентичность текущего runtime.",
		"EXECUTION_NODE_UNAVAILABLE":                     "Не выполнен SSH-запрос к Execution Node.",
		"BINDING_REQUIRED":                               "Отсутствует действующая привязка Execution Node к текущему сеансу.",
		"SERVICE_CONFIGURATION_PREVIEW_TIMEOUT":          "Истёк тайм-аут получения Core-проекции.",
	}
	code := projectErrorCode(err)
	var executionError *executionnode.ExecutionError
	if errors.As(err, &executionError) {
		code = executionError.Code
	}
	if errors.Is(err, context.DeadlineExceeded) {
		code = "SERVICE_CONFIGURATION_PREVIEW_TIMEOUT"
	}
	message, known := reasons[code]
	if !known {
		code, message = "SERVICE_CONFIGURATION_PREVIEW_UNAVAILABLE", "Не удалось получить Core-проекцию; безопасный код причины не предоставлен."
	}
	if known && executionError != nil {
		for _, finding := range executionError.Findings {
			if finding.Code == code {
				if safe := boundedFindingString(finding.SafeMessage, 512); safe != "" {
					message = safe
					break
				}
			}
		}
	}
	return executionnode.Finding{Code: code, SafeMessage: message}
}
