package executionnode

import (
	"context"
	"errors"
	"strconv"
	"strings"
	"time"
)

// ServerInformation is an observation, never installation readiness or inventory.
type ServerInformation struct {
	Hostname     string `json:"hostname"`
	OS           string `json:"os"`
	OSVersion    string `json:"osVersion"`
	Architecture string `json:"architecture"`
	CPUCount     int    `json:"cpuCount"`
	MemoryBytes  int64  `json:"memoryBytes"`
	ServerTime   string `json:"serverTime"`
	CheckedAt    string `json:"checkedAt"`
}

const serverInformationScript = `set -eu
export LC_ALL=C
printf 'HOSTNAME=%s\n' "$(hostname)"
awk -F= '$1 == "NAME" {print "OS=" substr($0,6)} $1 == "VERSION_ID" {print "VERSION=" substr($0,12)}' /etc/os-release
printf 'ARCH=%s\nCPU=%s\n' "$(uname -m)" "$(getconf _NPROCESSORS_ONLN)"
awk '$1 == "MemTotal:" {print "MEMORY_KIB=" $2}' /proc/meminfo
printf 'TIME=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
`

func (t OpenSSHTransport) ReadServerInformation(ctx context.Context, node Node) (ServerInformation, error) {
	ctx, cancel := context.WithTimeout(ctx, 20*time.Second)
	defer cancel()
	output, err := t.sshSeparatedBounded(ctx, node, "sh", []string{"-s"}, []byte(serverInformationScript), 16384, 1024)
	if err != nil {
		return ServerInformation{}, errors.New("SERVER_INFORMATION_CONNECTION_FAILED")
	}
	return parseServerInformation(output)
}

func parseServerInformation(output []byte) (ServerInformation, error) {
	invalid := errors.New("SERVER_INFORMATION_INVALID")
	if len(output) == 0 || len(output) > 16384 {
		return ServerInformation{}, invalid
	}
	values := map[string]string{}
	for _, line := range strings.Split(strings.TrimSpace(string(output)), "\n") {
		key, value, ok := strings.Cut(line, "=")
		if !ok || len(value) > 256 || strings.ContainsAny(value, "\x00\r\t") {
			return ServerInformation{}, invalid
		}
		switch key {
		case "HOSTNAME", "OS", "VERSION", "ARCH", "CPU", "MEMORY_KIB", "TIME":
		default:
			return ServerInformation{}, invalid
		}
		if _, exists := values[key]; exists {
			return ServerInformation{}, invalid
		}
		values[key] = strings.Trim(value, "\"")
	}
	if len(values) != 7 {
		return ServerInformation{}, invalid
	}
	for _, value := range values {
		if value == "" {
			return ServerInformation{}, invalid
		}
	}
	cpu, err := strconv.Atoi(values["CPU"])
	if err != nil || cpu < 1 || cpu > 1048576 {
		return ServerInformation{}, invalid
	}
	memory, err := strconv.ParseInt(values["MEMORY_KIB"], 10, 64)
	if err != nil || memory < 1 || memory > 1<<50 {
		return ServerInformation{}, invalid
	}
	if _, err := time.Parse(time.RFC3339, values["TIME"]); err != nil {
		return ServerInformation{}, invalid
	}
	return ServerInformation{Hostname: values["HOSTNAME"], OS: values["OS"], OSVersion: values["VERSION"], Architecture: values["ARCH"], CPUCount: cpu, MemoryBytes: memory * 1024, ServerTime: values["TIME"], CheckedAt: time.Now().UTC().Format(time.RFC3339)}, nil
}
