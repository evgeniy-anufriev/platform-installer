package executionnode

import (
	"context"
	"errors"
	"strings"
)

// RuntimePreparationError contains a closed diagnostic, never remote output.
type RuntimePreparationError struct {
	Phase   string
	Finding Finding
	cause   error
}

func (e *RuntimePreparationError) Error() string { return e.Finding.Code }
func (e *RuntimePreparationError) Unwrap() error { return e.cause }

var preparationReasons = map[string]string{
	"EXECUTION_RUNTIME_ARGUMENTS_INVALID":              "Нарушено число аргументов подготовки runtime.",
	"EXECUTION_BOOTSTRAP_NOT_ROOT":                     "Команда подготовки запущена без root.",
	"EXECUTION_BOOTSTRAP_OS_RELEASE_MISSING":           "Недоступен /etc/os-release.",
	"EXECUTION_BOOTSTRAP_PLATFORM_INVALID":             "Некорректные OS, VERSION_ID или архитектура узла.",
	"EXECUTION_BOOTSTRAP_OS_UNSUPPORTED":               "ОС узла не поддерживается bootstrap.",
	"EXECUTION_BOOTSTRAP_PLATFORM_MISMATCH":            "Платформа узла отсутствует в наборе установки.",
	"EXECUTION_BOOTSTRAP_PACKAGE_TOOL_MISSING":         "Не найдены rpm/dnf.",
	"EXECUTION_BOOTSTRAP_INSTALLED_PACKAGE_BROKEN":     "Установленный runtime-пакет не предоставляет требуемую команду.",
	"EXECUTION_BOOTSTRAP_RPM_UNSAFE":                   "RPM набора не является обычным файлом.",
	"EXECUTION_BOOTSTRAP_RPM_INVALID":                  "Не удалось прочитать метаданные RPM набора.",
	"EXECUTION_BOOTSTRAP_RPM_AMBIGUOUS":                "В наборе несколько RPM одного пакета.",
	"EXECUTION_BOOTSTRAP_OFFLINE_INSTALL_FAILED":       "DNF завершил установку из offline-набора с ошибкой.",
	"EXECUTION_BOOTSTRAP_REPOSITORY_INSTALL_FAILED":    "DNF завершил установку runtime-пакетов из репозиториев с ошибкой.",
	"EXECUTION_BOOTSTRAP_PACKAGE_UNAVAILABLE":          "DNF не нашёл требуемый runtime-пакет.",
	"EXECUTION_BOOTSTRAP_DEPENDENCY_RESOLUTION_FAILED": "DNF не разрешил зависимости runtime-пакетов.",
	"EXECUTION_BOOTSTRAP_REPOSITORY_DOWNLOAD_FAILED":   "DNF не смог загрузить данные из настроенного репозитория.",
	"EXECUTION_BOOTSTRAP_PACKAGE_SIGNATURE_FAILED":     "DNF отклонил подпись пакета.",
	"EXECUTION_BOOTSTRAP_DISK_FULL":                    "DNF остановлен: недостаточно места на диске.",
	"EXECUTION_BOOTSTRAP_PACKAGE_MANAGER_BUSY":         "DNF не получил блокировку пакетного менеджера.",
	"EXECUTION_BOOTSTRAP_PACKAGE_NOT_INSTALLED":        "После DNF требуемый runtime-пакет не установлен.",
	"EXECUTION_BOOTSTRAP_LEGACY_PREREQUISITES_MISSING": "В бандле нет скрипта автоматического bootstrap; Python/Ansible отсутствуют. Перевыпустите бандл с bootstrap_execution_runtime.sh.",
	"EXECUTION_BOOTSTRAP_LOCK_TOOL_MISSING":            "Не найдена команда flock.",
	"EXECUTION_BUNDLE_STAGE_INVALID":                   "Некорректный staging-каталог набора.",
	"EXECUTION_BUNDLE_DIGEST_INVALID":                  "Некорректный digest набора.",
	"EXECUTION_RUNTIME_DIRECTORY_UNSAFE":               "Небезопасные владелец, тип или права каталога runtime.",
	"EXECUTION_RUNTIME_LOCK_UNSAFE":                    "Небезопасный файл блокировки runtime.",
	"EXECUTION_RUNTIME_PREPARATION_BUSY":               "Подготовка runtime уже выполняется: блокировка занята.",
	"EXECUTION_RUNTIME_CANDIDATE_EXISTS":               "Каталог кандидата runtime уже существует.",
	"EXECUTION_RUNTIME_CANDIDATE_UNSAFE":               "Кандидат runtime содержит недопустимые файлы.",
	"EXECUTION_RUNTIME_CANDIDATE_INVALID":              "Не пройдена проверка файлов, прав или checksum кандидата runtime.",
	"EXECUTION_RUNTIME_BACKUP_EXISTS":                  "Каталог резервного состояния runtime уже существует.",
	"EXECUTION_RUNTIME_CURRENT_UNSAFE":                 "Некорректная ссылка current у runtime.",
	"EXECUTION_RUNTIME_ACTIVE_UNSAFE":                  "Небезопасный файл активного состояния runtime.",
	"EXECUTION_RUNTIME_EXISTING_RELEASE_INVALID":       "Существующий runtime release не прошёл проверку целостности.",
	"EXECUTION_RUNTIME_CANDIDATE_COPY_FAILED":          "Не удалось скопировать и подготовить root-owned runtime-кандидат.",
	"EXECUTION_RUNTIME_STATE_INITIALIZATION_FAILED":    "Не удалось подготовить состояние активации runtime.",
	"EXECUTION_RUNTIME_PYTHON_INITIALIZATION_FAILED":   "Python не смог инициализировать защищённое состояние runtime.",
	"EXECUTION_RUNTIME_CAPABILITY_CHECK_FAILED":        "Ansible-проверка execution-capabilities.yml завершилась ошибкой.",
	"EXECUTION_RUNTIME_SWITCH_FAILED":                  "Не удалось переключить current/active на новый runtime.",
	"EXECUTION_BOOTSTRAP_COMMAND_FAILED":               "Команда bootstrap завершилась ошибкой.",
	"EXECUTION_RUNTIME_ACTIVATION_COMMAND_FAILED":      "Команда активации runtime завершилась ошибкой.",
	"EXECUTION_RUNTIME_PREPARATION_TIMEOUT":            "Истёк тайм-аут подготовки runtime.",
}

func runtimePreparationFailure(phase string, output []byte, cause error) error {
	code := "EXECUTION_BOOTSTRAP_COMMAND_FAILED"
	if phase == "activation" {
		code = "EXECUTION_RUNTIME_ACTIVATION_COMMAND_FAILED"
	}
	for _, line := range strings.Split(string(output), "\n") {
		candidate := strings.TrimSpace(line)
		if _, exists := preparationReasons[candidate]; exists {
			code = candidate
			break
		}
	}
	if errors.Is(cause, context.DeadlineExceeded) {
		code = "EXECUTION_RUNTIME_PREPARATION_TIMEOUT"
	}
	return &RuntimePreparationError{Phase: phase, Finding: Finding{Code: code, SafeMessage: preparationReasons[code]}, cause: cause}
}

func serviceConfigurationPreviewSupported(capabilities map[string]any) bool {
	switch capabilities["apiVersion"] {
	case "platform.installer/execution-capabilities/v1alpha5", "platform.installer/execution-capabilities/v1alpha6",
		"platform.installer/execution-capabilities/v1alpha7", "platform.installer/execution-capabilities/v1alpha8",
		"platform.installer/execution-capabilities/v1alpha9", "platform.installer/execution-capabilities/v1alpha10",
		"platform.installer/execution-capabilities/v1alpha11":
		return validServiceConfigurationPreviewCapability(capabilities["serviceConfigurationPreview"], capabilities["supportedOperations"])
	default:
		return false
	}
}
