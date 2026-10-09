package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

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
