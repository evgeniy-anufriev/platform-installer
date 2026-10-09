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

func redis(ctx context.Context, pool *x509.CertPool, identity tls.Certificate, prefix string) error {
	host, port, user, password := prefix+"_HOST", prefix+"_PORT", prefix+"_USER", prefix+"_PASSWORD"
	if err := require(host, port, user, password); err != nil {
		return err
	}
	dialer := &tls.Dialer{NetDialer: &net.Dialer{Timeout: 4 * time.Second},
		Config: &tls.Config{MinVersion: tls.VersionTLS12, RootCAs: pool, ServerName: os.Getenv(host), Certificates: []tls.Certificate{identity}}}
	conn, err := dialer.DialContext(ctx, "tcp", net.JoinHostPort(os.Getenv(host), os.Getenv(port)))
	if err != nil {
		return err
	}
	defer conn.Close()
	_ = conn.SetDeadline(time.Now().Add(4 * time.Second))
	if err = respWrite(conn, "AUTH", os.Getenv(user), os.Getenv(password)); err != nil {
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
	return nil
}

func kafka(ctx context.Context, pool *x509.CertPool) error {
	if err := require("KAFKA_HOST", "KAFKA_PORT"); err != nil {
		return err
	}
	dialer := &tls.Dialer{NetDialer: &net.Dialer{Timeout: 4 * time.Second},
		Config: &tls.Config{MinVersion: tls.VersionTLS12, RootCAs: pool, ServerName: os.Getenv("KAFKA_HOST")}}
	conn, err := dialer.DialContext(ctx, "tcp", net.JoinHostPort(os.Getenv("KAFKA_HOST"), os.Getenv("KAFKA_PORT")))
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
	request, err := http.NewRequestWithContext(ctx, http.MethodPost, target+"/", strings.NewReader("SELECT 1 FORMAT TabSeparated"))
	if err != nil {
		return err
	}
	request.SetBasicAuth(os.Getenv("CLICKHOUSE_USER"), os.Getenv("CLICKHOUSE_PASSWORD"))
	transport := &http.Transport{TLSClientConfig: &tls.Config{MinVersion: tls.VersionTLS12, RootCAs: pool, Certificates: []tls.Certificate{identity}}}
	defer transport.CloseIdleConnections()
	client := &http.Client{Timeout: 5 * time.Second, Transport: transport}
	response, err := client.Do(request)
	if err != nil {
		return err
	}
	defer response.Body.Close()
	body, err := io.ReadAll(io.LimitReader(response.Body, 128))
	if err != nil || response.StatusCode != http.StatusOK || strings.TrimSpace(string(body)) != "1" {
		return errors.New("CLICKHOUSE_QUERY_FAILED")
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
