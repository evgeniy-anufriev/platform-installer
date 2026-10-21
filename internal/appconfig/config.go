package appconfig

import (
	"errors"
	"io"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"unicode/utf8"

	"gopkg.in/yaml.v3"
)

const (
	SchemaVersion        = 3
	maxConfigBytes       = 64 * 1024
	maxServerTypes       = 64
	maxServicePriorities = 64
	maxLibraryPriorities = 128
	maxDisplayNameLength = 128
)

var ServerTypeIDPattern = regexp.MustCompile(`^[a-z0-9][a-z0-9_-]{0,62}$`)
var libraryNamePattern = regexp.MustCompile(`^[a-z][a-z0-9]*(?:[-_.][a-z0-9]+)*$`)

type ServerType struct {
	ID          string `json:"id" yaml:"id"`
	DisplayName string `json:"displayName" yaml:"displayName"`
}

type ServiceExecutionPriority struct {
	ServiceType string `json:"serviceType" yaml:"serviceType"`
	Priority    *int   `json:"priority" yaml:"priority"`
}

type LibraryExecutionPriority struct {
	LibraryName string `json:"libraryName" yaml:"libraryName"`
	Priority    *int   `json:"priority" yaml:"priority"`
}

type Config struct {
	SchemaVersion              int                        `json:"schemaVersion" yaml:"schemaVersion"`
	ServerTypes                []ServerType               `json:"serverTypes" yaml:"serverTypes"`
	ServiceExecutionPriorities []ServiceExecutionPriority `json:"serviceExecutionPriorities" yaml:"serviceExecutionPriorities"`
	LibraryExecutionPriorities []LibraryExecutionPriority `json:"libraryExecutionPriorities" yaml:"libraryExecutionPriorities"`
}

type Error struct {
	Code string
}

func (e *Error) Error() string { return e.Code }

func Load(path string) (Config, error) {
	file, err := openRegularFile(path)
	if err != nil {
		return Config{}, err
	}
	defer file.Close()
	if info, err := file.Stat(); err != nil {
		return Config{}, &Error{Code: "APPLICATION_CONFIG_UNREADABLE"}
	} else if info.Size() > maxConfigBytes {
		return Config{}, &Error{Code: "APPLICATION_CONFIG_TOO_LARGE"}
	}

	decoder := yaml.NewDecoder(io.LimitReader(file, maxConfigBytes+1))
	decoder.KnownFields(true)
	var config Config
	if err := decoder.Decode(&config); err != nil {
		return Config{}, &Error{Code: "APPLICATION_CONFIG_INVALID"}
	}
	var extra any
	if err := decoder.Decode(&extra); err != io.EOF {
		return Config{}, &Error{Code: "APPLICATION_CONFIG_INVALID"}
	}
	if err := Validate(config); err != nil {
		return Config{}, err
	}
	return config, nil
}

func openRegularFile(path string) (*os.File, error) {
	absolute, err := filepath.Abs(path)
	if err != nil {
		return nil, &Error{Code: "APPLICATION_CONFIG_UNREADABLE"}
	}
	for component := absolute; ; component = filepath.Dir(component) {
		info, err := os.Lstat(component)
		if err != nil {
			if errors.Is(err, os.ErrNotExist) {
				return nil, &Error{Code: "APPLICATION_CONFIG_NOT_FOUND"}
			}
			return nil, &Error{Code: "APPLICATION_CONFIG_UNREADABLE"}
		}
		if info.Mode()&os.ModeSymlink != 0 {
			return nil, &Error{Code: "APPLICATION_CONFIG_UNSAFE_PATH"}
		}
		parent := filepath.Dir(component)
		if parent == component {
			break
		}
	}
	before, err := os.Lstat(absolute)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return nil, &Error{Code: "APPLICATION_CONFIG_NOT_FOUND"}
		}
		return nil, &Error{Code: "APPLICATION_CONFIG_UNREADABLE"}
	}
	if before.Mode()&os.ModeSymlink != 0 || !before.Mode().IsRegular() {
		return nil, &Error{Code: "APPLICATION_CONFIG_UNSAFE_PATH"}
	}
	file, err := os.Open(absolute)
	if err != nil {
		return nil, &Error{Code: "APPLICATION_CONFIG_UNREADABLE"}
	}
	after, err := file.Stat()
	if err != nil || !after.Mode().IsRegular() || !os.SameFile(before, after) {
		file.Close()
		return nil, &Error{Code: "APPLICATION_CONFIG_UNSAFE_PATH"}
	}
	return file, nil
}

func Validate(config Config) error {
	if config.SchemaVersion == 1 || config.SchemaVersion == 2 {
		return &Error{Code: "APPLICATION_CONFIG_UPGRADE_REQUIRED"}
	}
	if config.SchemaVersion != SchemaVersion {
		return &Error{Code: "APPLICATION_CONFIG_VERSION_UNSUPPORTED"}
	}
	if len(config.ServerTypes) == 0 || len(config.ServerTypes) > maxServerTypes {
		return &Error{Code: "APPLICATION_CONFIG_SERVER_TYPES_INVALID"}
	}
	if len(config.ServiceExecutionPriorities) == 0 || len(config.ServiceExecutionPriorities) > maxServicePriorities {
		return &Error{Code: "APPLICATION_CONFIG_SERVICE_PRIORITIES_INVALID"}
	}
	prioritySeen := make(map[string]bool, len(config.ServiceExecutionPriorities))
	for _, entry := range config.ServiceExecutionPriorities {
		if !ServerTypeIDPattern.MatchString(entry.ServiceType) || entry.Priority == nil || *entry.Priority < 0 {
			return &Error{Code: "APPLICATION_CONFIG_SERVICE_PRIORITY_INVALID"}
		}
		if prioritySeen[entry.ServiceType] {
			return &Error{Code: "APPLICATION_CONFIG_SERVICE_PRIORITY_DUPLICATE"}
		}
		prioritySeen[entry.ServiceType] = true
	}
	if len(config.LibraryExecutionPriorities) > maxLibraryPriorities {
		return &Error{Code: "APPLICATION_CONFIG_LIBRARY_PRIORITIES_INVALID"}
	}
	librarySeen := make(map[string]bool, len(config.LibraryExecutionPriorities))
	for _, entry := range config.LibraryExecutionPriorities {
		if !libraryNamePattern.MatchString(entry.LibraryName) || len(entry.LibraryName) > 128 || entry.Priority == nil || *entry.Priority < 0 {
			return &Error{Code: "APPLICATION_CONFIG_LIBRARY_PRIORITY_INVALID"}
		}
		if librarySeen[entry.LibraryName] {
			return &Error{Code: "APPLICATION_CONFIG_LIBRARY_PRIORITY_DUPLICATE"}
		}
		librarySeen[entry.LibraryName] = true
	}
	seen := make(map[string]bool, len(config.ServerTypes))
	for _, serverType := range config.ServerTypes {
		if !ServerTypeIDPattern.MatchString(serverType.ID) {
			return &Error{Code: "APPLICATION_CONFIG_SERVER_TYPE_ID_INVALID"}
		}
		name := strings.TrimSpace(serverType.DisplayName)
		if name == "" || !utf8.ValidString(name) || utf8.RuneCountInString(name) > maxDisplayNameLength {
			return &Error{Code: "APPLICATION_CONFIG_SERVER_TYPE_NAME_INVALID"}
		}
		key := strings.ToLower(serverType.ID)
		if seen[key] {
			return &Error{Code: "APPLICATION_CONFIG_SERVER_TYPE_DUPLICATE"}
		}
		seen[key] = true
	}
	return nil
}

func (c Config) HasServerType(id string) bool {
	for _, serverType := range c.ServerTypes {
		if serverType.ID == id {
			return true
		}
	}
	return false
}

func ResolveDevelopmentPath(workingDirectory, executable string) (string, error) {
	candidates := []string{}
	if executable != "" {
		candidates = append(candidates, filepath.Clean(filepath.Join(filepath.Dir(executable), "..", "..", "config", "application.yml")))
	}
	if isRepositoryDevelopmentRoot(workingDirectory) {
		candidates = append(candidates, filepath.Join(workingDirectory, "config", "application.yml"))
	}
	for _, candidate := range candidates {
		file, err := openRegularFile(candidate)
		if err == nil {
			file.Close()
			return candidate, nil
		}
		var typed *Error
		if errors.As(err, &typed) && typed.Code != "APPLICATION_CONFIG_NOT_FOUND" {
			return "", err
		}
	}
	return "", &Error{Code: "APPLICATION_CONFIG_NOT_FOUND"}
}

func isRepositoryDevelopmentRoot(root string) bool {
	file, err := openRegularFile(filepath.Join(root, "go.mod"))
	if err != nil {
		return false
	}
	defer file.Close()
	content, err := io.ReadAll(io.LimitReader(file, 4097))
	if err != nil || len(content) > 4096 {
		return false
	}
	for _, line := range strings.Split(string(content), "\n") {
		if strings.TrimSpace(line) == "module platform-installer" {
			return true
		}
	}
	return false
}
