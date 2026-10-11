// application-connection-probe is a QA-only application started by Vault Agent.
// It never prints credential values or persists them in project files.
package main

import (
	"context"
	"crypto/tls"
	"crypto/x509"
	"encoding/binary"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"time"
)

type check struct {
	State  string `json:"state"`
	Reason string `json:"reason,omitempty"`
}

type status struct {
	Overall   string           `json:"overall"`
	Checks    map[string]check `json:"checks"`
	CheckedAt string           `json:"checkedAt"`
}

func env(name, fallback string) string {
	if value := strings.TrimSpace(os.Getenv(name)); value != "" {
		return value
	}
	return fallback
}

func result(err error) check {
	if err == nil {
		return check{State: "ok"}
	}
	// Errors may contain addresses, DSNs or fragments of server output. Expose only a code.
	return check{State: "failed", Reason: "CONNECTION_CHECK_FAILED"}
}

func require(names ...string) error {
	for _, name := range names {
		if os.Getenv(name) == "" {
			return errors.New("missing input")
		}
	}
	return nil
}

func trustedPool(ctx context.Context) (*x509.CertPool, string, error) {
	path := os.Getenv("PROBE_TRUSTSTORE_PKCS12")
	if path == "" {
		return nil, "", errors.New("missing truststore")
	}
	if err := require("PROBE_KEYSTORE_PASSWORD"); err != nil {
		return nil, "", err
	}
	cmd := exec.CommandContext(ctx, "/usr/bin/openssl", "pkcs12", "-in", path,
		"-nokeys", "-passin", "env:PROBE_KEYSTORE_PASSWORD")
	pem, err := cmd.Output()
	if err != nil {
		return nil, "", errors.New("PKCS12_READ_FAILED")
	}
	pool := x509.NewCertPool()
	if !pool.AppendCertsFromPEM(pem) {
		return nil, "", errors.New("PKCS12_CERTS_MISSING")
	}
	// psql needs a file; /run/probe must be a container tmpfs, never a project mount.
	if err := os.MkdirAll("/run/probe", 0700); err != nil {
		return nil, "", err
	}
	path = filepath.Join("/run/probe", "ca.pem")
	if err := os.WriteFile(path, pem, 0600); err != nil {
		return nil, "", err
	}
	return pool, path, nil
}

func clientIdentity(ctx context.Context) (tls.Certificate, string, string, error) {
	path := os.Getenv("PROBE_KEYSTORE_PKCS12")
	if path == "" || os.Getenv("PROBE_KEYSTORE_PASSWORD") == "" {
		return tls.Certificate{}, "", "", errors.New("missing client keystore")
	}
	extract := func(args ...string) ([]byte, error) {
		cmd := exec.CommandContext(ctx, "/usr/bin/openssl", append([]string{
			"pkcs12", "-in", path, "-passin", "env:PROBE_KEYSTORE_PASSWORD"}, args...)...)
		output, err := cmd.Output()
		if err != nil {
			return nil, errors.New("PKCS12_CLIENT_READ_FAILED")
		}
		return output, nil
	}
	certPEM, err := extract("-clcerts", "-nokeys")
	if err != nil {
		return tls.Certificate{}, "", "", err
	}
	keyPEM, err := extract("-nocerts", "-nodes")
	if err != nil {
		return tls.Certificate{}, "", "", err
	}
	identity, err := tls.X509KeyPair(certPEM, keyPEM)
	if err != nil {
		return tls.Certificate{}, "", "", errors.New("PKCS12_CLIENT_INVALID")
	}
	if err := os.MkdirAll("/run/probe", 0700); err != nil {
		return tls.Certificate{}, "", "", err
	}
	certPath, keyPath := "/run/probe/client-cert.pem", "/run/probe/client-key.pem"
	if err := os.WriteFile(certPath, certPEM, 0600); err != nil {
		return tls.Certificate{}, "", "", err
	}
	if err := os.WriteFile(keyPath, keyPEM, 0600); err != nil {
		return tls.Certificate{}, "", "", err
	}
	return identity, certPath, keyPath, nil
}

func postgres(ctx context.Context, caPath, certPath, keyPath string) error {
	if err := require("PGHOST", "PGPORT", "PGDATABASE", "PGUSER", "PGPASSWORD"); err != nil {
		return err
	}
	cmd := exec.CommandContext(ctx, "/usr/bin/psql", "-X", "-A", "-t", "-q", "-c", "SELECT 1")
	cmd.Env = append(os.Environ(), "PGSSLMODE=verify-full", "PGSSLROOTCERT="+caPath,
		"PGSSLCERT="+certPath, "PGSSLKEY="+keyPath,
		"PGCONNECT_TIMEOUT=4", "PGOPTIONS=-c statement_timeout=3000")
	output, err := cmd.Output()
	if err != nil || strings.TrimSpace(string(output)) != "1" {
		return errors.New("POSTGRES_QUERY_FAILED")
	}
	return nil
}

func respWrite(conn net.Conn, args ...string) error {
	var builder strings.Builder
	fmt.Fprintf(&builder, "*%d\r\n", len(args))
	for _, arg := range args {
		fmt.Fprintf(&builder, "$%d\r\n%s\r\n", len(arg), arg)
	}
	_, err := io.WriteString(conn, builder.String())
	return err
}

func respLine(conn net.Conn) (string, error) {
	var bytes []byte
	for len(bytes) < 4096 {
		one := make([]byte, 1)
		if _, err := io.ReadFull(conn, one); err != nil {
			return "", err
		}
		bytes = append(bytes, one[0])
		if len(bytes) >= 2 && bytes[len(bytes)-2] == '\r' && bytes[len(bytes)-1] == '\n' {
			return string(bytes[:len(bytes)-2]), nil
		}
	}
	return "", errors.New("RESP_TOO_LONG")
}

func respBulk(conn net.Conn) (string, error) {
	line, err := respLine(conn)
	if err != nil || !strings.HasPrefix(line, "$") {
		return "", errors.New("RESP_BULK_INVALID")
	}
	size, err := strconv.Atoi(line[1:])
	if err != nil || size < 0 || size > 4096 {
		return "", errors.New("RESP_BULK_INVALID")
	}
	value := make([]byte, size+2)
	if _, err = io.ReadFull(conn, value); err != nil || string(value[size:]) != "\r\n" {
		return "", errors.New("RESP_BULK_INVALID")
	}
	return string(value[:size]), nil
}

func redis(ctx context.Context, pool *x509.CertPool, identity tls.Certificate, prefix string) error {
	host, port, user, password := prefix+"_HOST", prefix+"_PORT", prefix+"_USER", prefix+"_PASSWORD"
	if err := require(host, port, user, password); err != nil {
		return err
	}
	return redisAt(ctx, pool, identity, os.Getenv(host), os.Getenv(port), os.Getenv(user), os.Getenv(password), prefix)
}

func redisAt(ctx context.Context, pool *x509.CertPool, identity tls.Certificate, host, port, user, password, prefix string) error {
	dialer := &tls.Dialer{NetDialer: &net.Dialer{Timeout: 4 * time.Second},
		Config: &tls.Config{MinVersion: tls.VersionTLS12, RootCAs: pool, ServerName: host, Certificates: []tls.Certificate{identity}}}
	conn, err := dialer.DialContext(ctx, "tcp", net.JoinHostPort(host, port))
	if err != nil {
		return err
	}
	defer conn.Close()
	_ = conn.SetDeadline(time.Now().Add(4 * time.Second))
	if err = respWrite(conn, "AUTH", user, password); err != nil {
		return err
	}
	line, err := respLine(conn)
	if err != nil || line != "+OK" {
		return errors.New("REDIS_AUTH_FAILED")
	}
	if err = respWrite(conn, "PING"); err != nil {
		return err
	}
	line, err = respLine(conn)
	if err != nil || line != "+PONG" {
		return errors.New("REDIS_PING_FAILED")
	}
	if prefix == "SENTINEL" {
		if err = require("SENTINEL_MASTER_NAME", "REDIS_TARGETS", "REDIS_USER", "REDIS_PASSWORD"); err != nil {
			return err
		}
		if err = respWrite(conn, "SENTINEL", "get-master-addr-by-name", os.Getenv("SENTINEL_MASTER_NAME")); err != nil {
			return err
		}
		line, err = respLine(conn)
		if err != nil || line != "*2" {
			return errors.New("SENTINEL_DISCOVERY_FAILED")
		}
		master, err := respBulk(conn)
		if err != nil {
			return err
		}
		masterPort, err := respBulk(conn)
		if err != nil {
			return err
		}
		address := net.JoinHostPort(master, masterPort)
		for _, target := range strings.Split(os.Getenv("REDIS_TARGETS"), ",") {
			if strings.TrimSpace(target) == address {
				return redisAt(ctx, pool, identity, master, masterPort, os.Getenv("REDIS_USER"), os.Getenv("REDIS_PASSWORD"), "MASTER")
			}
		}
		return errors.New("SENTINEL_MASTER_UNEXPECTED")
	}
	// Only this QA application may write, and only with an explicit fixture namespace.
	if prefix == "REDIS" && os.Getenv("PROBE_REDIS_KEY_PREFIX") != "" {
		key := os.Getenv("PROBE_REDIS_KEY_PREFIX") + "probe-" + strconv.FormatInt(time.Now().UnixNano(), 10)
		if err = respWrite(conn, "SET", key, "1", "EX", "30"); err != nil {
			return err
		}
		if line, err = respLine(conn); err != nil || line != "+OK" {
			return errors.New("REDIS_WRITE_FAILED")
		}
		defer respWrite(conn, "DEL", key)
		if err = respWrite(conn, "GET", key); err != nil {
			return err
		}
		if value, err := respBulk(conn); err != nil || value != "1" {
			return errors.New("REDIS_READ_FAILED")
		}
		if err = respWrite(conn, "DEL", key); err != nil {
			return err
		}
		if line, err = respLine(conn); err != nil || line != ":1" {
			return errors.New("REDIS_DELETE_FAILED")
		}
		if err = respWrite(conn, "GET", "__platform_forbidden_namespace__:probe"); err != nil {
			return err
		}
		if line, err = respLine(conn); err != nil || !strings.HasPrefix(line, "-NOPERM") {
			return errors.New("REDIS_NAMESPACE_UNRESTRICTED")
		}
	}
	return nil
}

func kafka(ctx context.Context, pool *x509.CertPool) error {
	if os.Getenv("KAFKA_TARGETS") != "" {
		for _, target := range strings.Split(os.Getenv("KAFKA_TARGETS"), ",") {
			host, port, err := net.SplitHostPort(strings.TrimSpace(target))
			if err != nil {
				return err
			}
			if err = kafkaAt(ctx, pool, host, port); err != nil {
				return err
			}
		}
		return nil
	}
	if err := require("KAFKA_HOST", "KAFKA_PORT"); err != nil {
		return err
	}
	return kafkaAt(ctx, pool, os.Getenv("KAFKA_HOST"), os.Getenv("KAFKA_PORT"))
}

func kafkaAt(ctx context.Context, pool *x509.CertPool, host, port string) error {
	dialer := &tls.Dialer{NetDialer: &net.Dialer{Timeout: 4 * time.Second},
		Config: &tls.Config{MinVersion: tls.VersionTLS12, RootCAs: pool, ServerName: host}}
	conn, err := dialer.DialContext(ctx, "tcp", net.JoinHostPort(host, port))
	if err != nil {
		return err
	}
	defer conn.Close()
	_ = conn.SetDeadline(time.Now().Add(4 * time.Second))
	// ApiVersions v0: request header only, no SASL identity or topic operation.
	request := []byte{0, 0, 0, 10, 0, 18, 0, 0, 0, 0, 0, 1, 0, 0}
	if _, err = conn.Write(request); err != nil {
		return err
	}
	var header [8]byte
	if _, err = io.ReadFull(conn, header[:]); err != nil {
		return err
	}
	if size := binary.BigEndian.Uint32(header[:4]); size < 4 || size > 1<<20 || binary.BigEndian.Uint32(header[4:]) != 1 {
		return errors.New("KAFKA_PROTOCOL_RESPONSE_INVALID")
	}
	body := make([]byte, binary.BigEndian.Uint32(header[:4])-4)
	if _, err = io.ReadFull(conn, body); err != nil || len(body) < 6 || binary.BigEndian.Uint16(body[:2]) != 0 || binary.BigEndian.Uint32(body[2:6]) == 0 {
		return errors.New("KAFKA_API_VERSIONS_FAILED")
	}
	return nil
}

func clickhouse(ctx context.Context, pool *x509.CertPool, identity tls.Certificate) error {
	if err := require("CLICKHOUSE_URL", "CLICKHOUSE_USER", "CLICKHOUSE_PASSWORD"); err != nil {
		return err
	}
	target := strings.TrimRight(os.Getenv("CLICKHOUSE_URL"), "/")
	if !strings.HasPrefix(target, "https://") {
		return errors.New("CLICKHOUSE_HTTPS_REQUIRED")
	}
	transport := &http.Transport{TLSClientConfig: &tls.Config{MinVersion: tls.VersionTLS12, RootCAs: pool, Certificates: []tls.Certificate{identity}}}
	defer transport.CloseIdleConnections()
	client := &http.Client{Timeout: 5 * time.Second, Transport: transport}
	query := func(sql string) (int, string, error) {
		request, err := http.NewRequestWithContext(ctx, http.MethodPost, target+"/", strings.NewReader(sql))
		if err != nil {
			return 0, "", err
		}
		request.SetBasicAuth(os.Getenv("CLICKHOUSE_USER"), os.Getenv("CLICKHOUSE_PASSWORD"))
		response, err := client.Do(request)
		if err != nil {
			return 0, "", err
		}
		defer response.Body.Close()
		body, err := io.ReadAll(io.LimitReader(response.Body, 1024))
		return response.StatusCode, strings.TrimSpace(string(body)), err
	}
	code, body, err := query("SELECT 1 FORMAT TabSeparated")
	if err != nil || code != http.StatusOK || body != "1" {
		return errors.New("CLICKHOUSE_QUERY_FAILED")
	}
	if os.Getenv("PROBE_CLICKHOUSE_TABLE") != "" {
		database, table := os.Getenv("PROBE_CLICKHOUSE_DATABASE"), os.Getenv("PROBE_CLICKHOUSE_TABLE")
		deniedDatabase, deniedTable := os.Getenv("PROBE_CLICKHOUSE_DENIED_DATABASE"), os.Getenv("PROBE_CLICKHOUSE_DENIED_TABLE")
		for _, value := range []string{database, table, deniedDatabase, deniedTable} {
			if value == "" || len(value) > 63 || strings.IndexFunc(value, func(char rune) bool {
				return !(char >= 'a' && char <= 'z' || char >= '0' && char <= '9' || char == '_' || char == '-')
			}) >= 0 {
				return errors.New("CLICKHOUSE_FIXTURE_INVALID")
			}
		}
		code, body, err = query("SELECT count() FROM `" + database + "`.`" + table + "` FORMAT TabSeparated")
		if _, numberErr := strconv.ParseUint(body, 10, 64); err != nil || numberErr != nil || code != http.StatusOK {
			return errors.New("CLICKHOUSE_FIXTURE_SELECT_FAILED")
		}
		code, body, err = query("SELECT count() FROM `" + deniedDatabase + "`.`" + deniedTable + "` FORMAT TabSeparated")
		if err != nil || code == http.StatusOK || !strings.Contains(body, "Code: 497") {
			return errors.New("CLICKHOUSE_SCOPE_UNRESTRICTED")
		}
	}
	return nil
}

func vaultAgent() error {
	// Agent env_template must populate this from an allowed Vault KV path.
	// The value is never included in the status response.
	if os.Getenv("PROBE_VAULT_MARKER") == "" {
		return errors.New("VAULT_TEMPLATE_MISSING")
	}
	return nil
}

func collect(ctx context.Context) status {
	report := status{Overall: "ok", Checks: map[string]check{}, CheckedAt: time.Now().UTC().Format(time.RFC3339)}
	pool, caPath, err := trustedPool(ctx)
	report.Checks["pkcs12"] = result(err)
	var identity tls.Certificate
	var certPath, keyPath string
	if err == nil {
		identity, certPath, keyPath, err = clientIdentity(ctx)
	}
	report.Checks["pkcs12Client"] = result(err)
	if err == nil {
		report.Checks["postgresql"] = result(postgres(ctx, caPath, certPath, keyPath))
		report.Checks["redis"] = result(redis(ctx, pool, identity, "REDIS"))
		report.Checks["sentinel"] = result(redis(ctx, pool, identity, "SENTINEL"))
		report.Checks["kafka"] = result(kafka(ctx, pool))
		report.Checks["clickhouse"] = result(clickhouse(ctx, pool, identity))
	} else {
		for _, name := range []string{"postgresql", "redis", "sentinel", "kafka", "clickhouse"} {
			report.Checks[name] = check{State: "blocked", Reason: "PKCS12_UNAVAILABLE"}
		}
	}
	report.Checks["vaultAgent"] = result(vaultAgent())
	for _, name := range []string{"pkcs12", "pkcs12Client", "postgresql", "redis", "sentinel", "kafka", "clickhouse", "vaultAgent"} {
		if report.Checks[name].State != "ok" {
			report.Overall = "failed"
		}
	}
	return report
}

func handler(writer http.ResponseWriter, request *http.Request) {
	if request.URL.Path != "/status" {
		http.NotFound(writer, request)
		return
	}
	if request.Method != http.MethodGet {
		writer.WriteHeader(http.StatusMethodNotAllowed)
		return
	}
	ctx, cancel := context.WithTimeout(request.Context(), 20*time.Second)
	defer cancel()
	report := collect(ctx)
	writer.Header().Set("Content-Type", "application/json")
	writer.Header().Set("Cache-Control", "no-store")
	if report.Overall != "ok" {
		writer.WriteHeader(http.StatusServiceUnavailable)
	}
	_ = json.NewEncoder(writer).Encode(report)
}

func main() {
	port := env("PROBE_PORT", "8080")
	if _, err := strconv.Atoi(port); err != nil {
		fmt.Fprintln(os.Stderr, "INVALID_PORT")
		os.Exit(2)
	}
	server := &http.Server{Addr: "0.0.0.0:" + port, Handler: http.HandlerFunc(handler),
		ReadHeaderTimeout: 5 * time.Second}
	if err := server.ListenAndServe(); !errors.Is(err, http.ErrServerClosed) {
		fmt.Fprintln(os.Stderr, "PROBE_SERVER_FAILED")
		os.Exit(1)
	}
}
