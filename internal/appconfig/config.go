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
	SchemaVersion        = 1
	maxConfigBytes       = 64 * 1024
	maxServerTypes       = 64
	maxDisplayNameLength = 128
)

var ServerTypeIDPattern = regexp.MustCompile(`^[a-z0-9][a-z0-9_-]{0,62}$`)

type ServerType struct {
	ID          string `json:"id" yaml:"id"`
	DisplayName string `json:"displayName" yaml:"displayName"`
}

type Config struct {
	SchemaVersion int          `json:"schemaVersion" yaml:"schemaVersion"`
	ServerTypes   []ServerType `json:"serverTypes" yaml:"serverTypes"`
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
	if config.SchemaVersion != SchemaVersion {
		return &Error{Code: "APPLICATION_CONFIG_VERSION_UNSUPPORTED"}
	}
	if len(config.ServerTypes) == 0 || len(config.ServerTypes) > maxServerTypes {
		return &Error{Code: "APPLICATION_CONFIG_SERVER_TYPES_INVALID"}
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
