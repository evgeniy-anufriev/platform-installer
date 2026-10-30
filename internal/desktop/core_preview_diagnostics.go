package desktop

import (
	"context"
	"errors"
	"platform-installer/internal/executionnode"
)

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
