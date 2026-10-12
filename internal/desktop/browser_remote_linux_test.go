//go:build browser && linux

package desktop

import (
	"net/http/httptest"
	"net/url"
	"strings"
	"testing"
	"testing/fstest"
)

func TestValidBrowserAuthority(t *testing.T) {
	for _, value := range []string{"installer.example:8765", "192.0.2.20:8765", "[2001:db8::20]:8765", "localhost:8765"} {
		if !validBrowserAuthority(value) {
			t.Errorf("validBrowserAuthority(%q) = false", value)
		}
	}
	for _, value := range []string{"", ":8765", "installer.example", "installer.example:0", "installer.example:65536", "bad host:8765", "evil\r\nX-Test: yes:8765"} {
		if validBrowserAuthority(value) {
			t.Errorf("validBrowserAuthority(%q) = true", value)
		}
	}
}

func TestBrowserListenerMustMatchAdvertisedPort(t *testing.T) {
	for _, pair := range [][2]string{{"127.0.0.1:8765", "installer.example:8765"}, {":8765", "localhost:8765"}} {
		if !browserListenerMatchesHost(pair[0], pair[1]) {
			t.Errorf("browserListenerMatchesHost(%q, %q) = false", pair[0], pair[1])
		}
	}
	for _, pair := range [][2]string{{":8765", "installer.example:8080"}, {":0", "localhost:8765"}, {"8765", "localhost:8765"}} {
		if browserListenerMatchesHost(pair[0], pair[1]) {
			t.Errorf("browserListenerMatchesHost(%q, %q) = true", pair[0], pair[1])
		}
	}
}

func TestRemoteBrowserHostChecksAdvertisedHostsAndLocalhostAliases(t *testing.T) {
	host := &browserHost{}
	host.setAuthorities("installer.example:8765", true)
	for _, authority := range []string{"installer.example:8765", "localhost:8765", "127.0.0.1:8765", "[::1]:8765"} {
		request := httptest.NewRequest("GET", "http://"+authority+"/", nil)
		request.RemoteAddr = "198.51.100.8:4000"
		if !host.requestAllowed(request) {
			t.Errorf("requestAllowed(%q) = false", authority)
		}
	}
	request := httptest.NewRequest("GET", "http://unconfigured.example:8765/", nil)
	request.RemoteAddr = "198.51.100.8:4000"
	if host.requestAllowed(request) {
		t.Fatal("unconfigured Host was accepted")
	}
	host.localOnly = true
	request = httptest.NewRequest("GET", "http://installer.example:8765/", nil)
	request.RemoteAddr = "198.51.100.8:4000"
	if host.requestAllowed(request) {
		t.Fatal("non-loopback client was accepted by local mode")
	}
}

func TestRemoteBrowserServesRemoteBootstrapAndAllowsSameOriginLocalhost(t *testing.T) {
	host := &browserHost{
		static:     fstest.MapFS{"browser.html": &fstest.MapFile{Data: []byte(`<script src="/browser-bootstrap.js"></script>`)}},
		operations: map[string]browserOperation{},
	}
	host.setAuthorities("installer.example:8765", true)
	page := httptest.NewRequest("GET", "http://installer.example:8765/", nil)
	page.RemoteAddr = "198.51.100.8:4000"
	pageRecorder := httptest.NewRecorder()
	host.ServeHTTP(pageRecorder, page)
	if pageRecorder.Code != 200 || !strings.Contains(pageRecorder.Body.String(), `<script src="/browser-mode.js"></script>`) {
		t.Fatalf("remote browser bootstrap was not served: status=%d body=%q", pageRecorder.Code, pageRecorder.Body.String())
	}

	lease := "0123456789abcdef0123456789abcdef"
	host.leaseID = lease
	request := httptest.NewRequest("POST", "http://localhost:8765/api/lease/acquire", strings.NewReader(`{"leaseId":"`+lease+`"}`))
	request.Host = "localhost:8765"
	request.RemoteAddr = "127.0.0.1:4000"
	request.Header.Set("Origin", "http://localhost:8765")
	request.Header.Set("Content-Type", "application/json")
	recorder := httptest.NewRecorder()
	host.ServeHTTP(recorder, request)
	if recorder.Code != 200 {
		t.Fatalf("localhost lease request status = %d, want 200", recorder.Code)
	}

	request = httptest.NewRequest("POST", "http://installer.example:8765/api/lease/acquire", strings.NewReader(`{"leaseId":"`+lease+`"}`))
	request.RemoteAddr = "198.51.100.8:4000"
	request.Header.Set("Origin", "http://attacker.example")
	request.Header.Set("Content-Type", "application/json")
	recorder = httptest.NewRecorder()
	host.ServeHTTP(recorder, request)
	if recorder.Code != 403 {
		t.Fatalf("cross-origin API request status = %d, want 403", recorder.Code)
	}
}

func TestRemoteBrowserOriginsMatchConfiguredAuthority(t *testing.T) {
	host := &browserHost{}
	host.setAuthorities("[2001:db8::20]:8765", true)
	for origin := range host.allowedOrigins {
		parsed, err := url.Parse(origin)
		if err != nil || parsed.Host == "" {
			t.Fatalf("invalid configured origin %q: %v", origin, err)
		}
	}
}
