package main

import (
	"context"
	"crypto/tls"
	"crypto/x509"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"strconv"
	"strings"
	"testing"
	"time"
)

func nativeTLS(t *testing.T, handler func(net.Conn)) (string, *x509.CertPool) {
	t.Helper()
	fixture := httptest.NewTLSServer(http.NotFoundHandler())
	identity := fixture.TLS.Certificates[0]
	pool := x509.NewCertPool()
	pool.AddCert(fixture.Certificate())
	fixture.Close()
	listener, err := tls.Listen("tcp", "127.0.0.1:0", &tls.Config{Certificates: []tls.Certificate{identity}})
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { listener.Close() })
	go func() {
		for {
			conn, err := listener.Accept()
			if err != nil {
				return
			}
			go func() {
				defer conn.Close()
				conn.SetDeadline(time.Now().Add(3 * time.Second))
				handler(conn)
			}()
		}
	}()
	return listener.Addr().String(), pool
}

func TestKafkaChecksCompleteApiVersionsAcrossAllTargets(t *testing.T) {
	good, pool := nativeTLS(t, func(conn net.Conn) {
		request := make([]byte, 14)
		if _, err := io.ReadFull(conn, request); err != nil {
			return
		}
		// correlation id, no error, one ApiVersions entry.
		conn.Write([]byte{0, 0, 0, 16, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1, 0, 18, 0, 0, 0, 0})
	})
	bad, _ := nativeTLS(t, func(conn net.Conn) {
		request := make([]byte, 14)
		io.ReadFull(conn, request)
		response := make([]byte, 14)
		binary.BigEndian.PutUint32(response[:4], 10)
		binary.BigEndian.PutUint32(response[4:8], 1)
		binary.BigEndian.PutUint16(response[8:10], 35)
		conn.Write(response)
	})
	t.Setenv("KAFKA_TARGETS", good)
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	if err := kafka(ctx, pool); err != nil {
		t.Fatal(err)
	}
	t.Setenv("KAFKA_TARGETS", good+","+bad)
	if err := kafka(ctx, pool); err == nil {
		t.Fatal("a broker protocol failure was accepted")
	}
}

func TestSentinelDiscoversOnlyDeclaredMasterAndAuthenticatesRedis(t *testing.T) {
	readCommand := func(conn net.Conn) []string {
		line, err := respLine(conn)
		if err != nil || !strings.HasPrefix(line, "*") {
			return nil
		}
		count, err := strconv.Atoi(line[1:])
		if err != nil || count < 1 || count > 8 {
			return nil
		}
		var command []string
		for index := 0; index < count; index++ {
			value, err := respBulk(conn)
			if err != nil {
				return nil
			}
			command = append(command, value)
		}
		return command
	}
	master, pool := nativeTLS(t, func(conn net.Conn) {
		if command := readCommand(conn); len(command) != 3 || command[0] != "AUTH" || command[1] != "redis-fixture" {
			return
		}
		io.WriteString(conn, "+OK\r\n")
		if command := readCommand(conn); len(command) == 1 && command[0] == "PING" {
			io.WriteString(conn, "+PONG\r\n")
		}
	})
	masterHost, masterPort, _ := net.SplitHostPort(master)
	sentinel, _ := nativeTLS(t, func(conn net.Conn) {
		if command := readCommand(conn); len(command) != 3 || command[0] != "AUTH" {
			return
		}
		io.WriteString(conn, "+OK\r\n")
		if command := readCommand(conn); len(command) != 1 || command[0] != "PING" {
			return
		}
		io.WriteString(conn, "+PONG\r\n")
		if command := readCommand(conn); len(command) != 3 || command[0] != "SENTINEL" || command[2] != "redis-1" {
			return
		}
		fmt.Fprintf(conn, "*2\r\n$%d\r\n%s\r\n$%d\r\n%s\r\n", len(masterHost), masterHost, len(masterPort), masterPort)
	})
	host, port, _ := net.SplitHostPort(sentinel)
	for key, value := range map[string]string{"SENTINEL_HOST": host, "SENTINEL_PORT": port,
		"SENTINEL_USER": "sentinel-fixture", "SENTINEL_PASSWORD": "fixture", "SENTINEL_MASTER_NAME": "redis-1",
		"REDIS_TARGETS": master, "REDIS_USER": "redis-fixture", "REDIS_PASSWORD": "fixture"} {
		t.Setenv(key, value)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	if err := redis(ctx, pool, tls.Certificate{}, "SENTINEL"); err != nil {
		t.Fatal(err)
	}
	t.Setenv("REDIS_TARGETS", "127.0.0.1:1")
	if err := redis(ctx, pool, tls.Certificate{}, "SENTINEL"); err == nil {
		t.Fatal("undeclared discovered master was accepted")
	}
}

func TestStatusRedactsFailuresAndBlocksChecksWithoutPKCS(t *testing.T) {
	t.Setenv("PROBE_TRUSTSTORE_PKCS12", "")
	request := httptest.NewRequest(http.MethodGet, "/status", nil)
	response := httptest.NewRecorder()
	handler(response, request)
	if response.Code != http.StatusServiceUnavailable {
		t.Fatalf("code = %d", response.Code)
	}
	var body status
	if err := json.Unmarshal(response.Body.Bytes(), &body); err != nil {
		t.Fatal(err)
	}
	if body.Checks["kafka"].State != "blocked" || body.Checks["sentinel"].State != "blocked" || body.Checks["pkcs12"].State != "failed" {
		t.Fatalf("unexpected status: %+v", body.Checks)
	}
	if strings.Contains(response.Body.String(), "PROBE_TRUSTSTORE_PKCS12") {
		t.Fatal("input name leaked")
	}
}

func TestUnknownPathDoesNotRunChecks(t *testing.T) {
	response := httptest.NewRecorder()
	handler(response, httptest.NewRequest(http.MethodGet, "/unknown", nil))
	if response.Code != http.StatusNotFound {
		t.Fatalf("code = %d", response.Code)
	}
}
