//go:build browser

package desktop

import (
	"bytes"
	"context"
	"crypto/rand"
	"crypto/subtle"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"io/fs"
	"net"
	"net/http"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"
)

const (
	browserCookieName = "platform-installer-local"
	browserIdleLimit  = 15 * time.Minute
	browserMaxRequest = 4 << 20
	browserMaxCalls   = 32
)

type browserHost struct {
	app            *App
	static         fs.FS
	operations     map[string]browserOperation
	hub            *browserEventHub
	listener       net.Listener
	server         *http.Server
	authority      string
	origin         string
	allowedHosts   map[string]struct{}
	allowedOrigins map[string]struct{}
	bootstrap      [32]byte
	session        [32]byte
	mu             sync.Mutex
	bootstrapped   bool
	leaseID        string
	lastActive     time.Time
	activeCalls    int
	exitPending    bool
	stopping       bool
	localOnly      bool
	ctx            context.Context
	cancel         context.CancelFunc
}

func newBrowserHost(app *App, static fs.FS, hub *browserEventHub) (*browserHost, error) {
	if hub == nil {
		return nil, errors.New("BROWSER_EVENT_CHANNEL_UNAVAILABLE")
	}
	host := &browserHost{app: app, static: static, operations: browserOperations(), hub: hub, lastActive: time.Now()}
	if _, err := rand.Read(host.bootstrap[:]); err != nil {
		return nil, errors.New("BROWSER_BOOTSTRAP_UNAVAILABLE")
	}
	if _, err := rand.Read(host.session[:]); err != nil {
		return nil, errors.New("BROWSER_SESSION_UNAVAILABLE")
	}
	return host, nil
}

func runBrowserHost(parent context.Context, app *App, static fs.FS, hub *browserEventHub) error {
	return runConfiguredBrowserHost(parent, app, static, hub, "127.0.0.1:0", "", true, true)
}

func runRemoteBrowserHost(parent context.Context, app *App, static fs.FS, hub *browserEventHub, listenAddress, expectedHost string) error {
	if listenAddress == "" || expectedHost == "" {
		return errors.New("BROWSER_LISTENER_CONFIGURATION_INVALID")
	}
	return runConfiguredBrowserHost(parent, app, static, hub, listenAddress, expectedHost, false, false)
}

func runConfiguredBrowserHost(parent context.Context, app *App, static fs.FS, hub *browserEventHub, listenAddress, expectedHost string, localOnly, launchLocalBrowser bool) error {
	host, err := newBrowserHost(app, static, hub)
	if err != nil {
		return err
	}
	host.listener, err = net.Listen("tcp", listenAddress)
	if err != nil {
		return errors.New("BROWSER_LISTENER_UNAVAILABLE")
	}
	host.localOnly = localOnly
	if localOnly {
		host.authority = host.listener.Addr().String()
		host.setAuthorities(host.authority, false)
	} else {
		host.authority = expectedHost
		host.setAuthorities(expectedHost, true)
	}
	host.server = &http.Server{Handler: host, ReadHeaderTimeout: 5 * time.Second, IdleTimeout: 90 * time.Second}
	host.ctx, host.cancel = context.WithCancel(parent)
	app.startup(host.ctx)
	serveResult := make(chan error, 1)
	go func() { serveResult <- host.server.Serve(host.listener) }()
	go host.monitor()
	if launchLocalBrowser {
		launchURL := host.origin + "/?mode=browser#bootstrap=" + hex.EncodeToString(host.bootstrap[:])
		if err := openBrowser(launchURL); err != nil {
			host.cancel()
			_ = host.server.Close()
			app.shutdown(context.Background())
			return err
		}
	} else {
		_, _ = fmt.Fprintf(os.Stdout, "Browser UI: %s\n", host.origin)
	}
	select {
	case <-host.ctx.Done():
	case err := <-serveResult:
		if !errors.Is(err, http.ErrServerClosed) {
			host.cancel()
			app.shutdown(context.Background())
			return errors.New("BROWSER_SERVER_FAILED")
		}
	}
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	_ = host.server.Shutdown(shutdownCtx)
	app.shutdown(context.Background())
	return nil
}

func (h *browserHost) setAuthorities(primary string, includeLocalhost bool) {
	h.origin = "http://" + primary
	h.allowedHosts = map[string]struct{}{primary: {}}
	h.allowedOrigins = map[string]struct{}{h.origin: {}}
	if !includeLocalhost {
		return
	}
	_, port, err := net.SplitHostPort(primary)
	if err != nil {
		return
	}
	for _, host := range []string{"localhost", "127.0.0.1", "[::1]"} {
		authority := net.JoinHostPort(strings.Trim(host, "[]"), port)
		h.allowedHosts[authority] = struct{}{}
		h.allowedOrigins["http://"+authority] = struct{}{}
	}
}

func (h *browserHost) monitor() {
	ticker := time.NewTicker(15 * time.Second)
	defer ticker.Stop()
	for {
		select {
		case <-h.ctx.Done():
			return
		case now := <-ticker.C:
			h.mu.Lock()
			shouldExit := (h.exitPending || now.Sub(h.lastActive) >= browserIdleLimit) && h.activeCalls == 0 && !h.stopping
			h.mu.Unlock()
			if !shouldExit || h.hasActiveRun() {
				continue
			}
			h.mu.Lock()
			shouldStop := !h.stopping && h.activeCalls == 0 && (h.exitPending || now.Sub(h.lastActive) >= browserIdleLimit)
			if shouldStop {
				h.stopping = true
			}
			h.mu.Unlock()
			if !shouldStop {
				continue
			}
			if h.hasActiveRun() {
				h.mu.Lock()
				h.stopping = false
				if !h.exitPending {
					h.lastActive = time.Now()
				}
				h.mu.Unlock()
				continue
			}
			h.mu.Lock()
			shouldCancel := h.stopping && h.activeCalls == 0
			if !shouldCancel {
				h.stopping = false
			}
			h.mu.Unlock()
			if !shouldCancel {
				continue
			}
			h.cancel()
			return
		}
	}
}

func (h *browserHost) hasActiveRun() bool {
	h.app.editMu.Lock()
	defer h.app.editMu.Unlock()
	if h.app.startInFlight || h.app.startOutcomeUnknown {
		return true
	}
	if h.app.current.Status != "OPEN" || h.app.current.Project == nil {
		return len(h.app.installationRuns.runIDs()) > 0
	}
	return !h.app.knownRunsTerminalLocked()
}

func (h *browserHost) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("X-Content-Type-Options", "nosniff")
	w.Header().Set("Referrer-Policy", "no-referrer")
	w.Header().Set("X-Frame-Options", "DENY")
	w.Header().Set("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'")
	if !h.requestAllowed(r) {
		http.NotFound(w, r)
		return
	}
	if strings.HasPrefix(r.URL.Path, "/api/") {
		h.serveAPI(w, r)
		return
	}
	h.serveStatic(w, r)
}

func (h *browserHost) requestAllowed(r *http.Request) bool {
	if _, ok := h.allowedHosts[r.Host]; !ok {
		return false
	}
	if !h.localOnly {
		return true
	}
	host, _, err := net.SplitHostPort(r.RemoteAddr)
	if err != nil {
		return false
	}
	ip := net.ParseIP(host)
	return ip != nil && ip.IsLoopback()
}

func (h *browserHost) serveAPI(w http.ResponseWriter, r *http.Request) {
	origin := r.Header.Get("Origin")
	_, originAllowed := h.allowedOrigins[origin]
	if !originAllowed && !(origin == "" && r.Method == http.MethodGet && r.URL.Path == "/api/events" && r.Header.Get("Sec-Fetch-Site") == "same-origin") {
		http.Error(w, "origin rejected", http.StatusForbidden)
		return
	}
	w.Header().Set("Cache-Control", "no-store")
	switch r.URL.Path {
	case "/api/bootstrap":
		if !h.localOnly {
			http.NotFound(w, r)
			return
		}
		h.handleBootstrap(w, r)
	case "/api/lease/acquire":
		h.handleLease(w, r)
	case "/api/events":
		h.handleEvents(w, r)
	case "/api/heartbeat":
		h.handleHeartbeat(w, r)
	case "/api/exit":
		h.handleExit(w, r)
	default:
		if strings.HasPrefix(r.URL.Path, "/api/call/") {
			h.handleCall(w, r)
			return
		}
		http.NotFound(w, r)
	}
}

func (h *browserHost) handleBootstrap(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method rejected", http.StatusMethodNotAllowed)
		return
	}
	var request struct {
		Token string `json:"token"`
	}
	if err := decodeBrowserJSON(w, r, &request, 2048); err != nil {
		writeBrowserError(w, http.StatusBadRequest, err)
		return
	}
	supplied, err := hex.DecodeString(request.Token)
	if err != nil || len(supplied) != len(h.bootstrap) {
		http.Error(w, "bootstrap rejected", http.StatusUnauthorized)
		return
	}
	h.mu.Lock()
	defer h.mu.Unlock()
	if h.bootstrapped || subtle.ConstantTimeCompare(supplied, h.bootstrap[:]) != 1 {
		http.Error(w, "bootstrap rejected", http.StatusUnauthorized)
		return
	}
	h.bootstrapped = true
	h.lastActive = time.Now()
	http.SetCookie(w, &http.Cookie{Name: browserCookieName, Value: hex.EncodeToString(h.session[:]), Path: "/", HttpOnly: true, SameSite: http.SameSiteStrictMode})
	writeBrowserJSON(w, http.StatusOK, map[string]string{"status": "READY"})
}

func (h *browserHost) handleLease(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method rejected", http.StatusMethodNotAllowed)
		return
	}
	if !h.validSession(r) {
		http.Error(w, "session rejected", http.StatusUnauthorized)
		return
	}
	var request struct {
		LeaseID string `json:"leaseId"`
	}
	if err := decodeBrowserJSON(w, r, &request, 1024); err != nil || !validBrowserLeaseID(request.LeaseID) {
		writeBrowserError(w, http.StatusBadRequest, errors.New("BROWSER_LEASE_INVALID"))
		return
	}
	h.mu.Lock()
	defer h.mu.Unlock()
	if h.stopping {
		http.Error(w, "browser host is shutting down", http.StatusServiceUnavailable)
		return
	}
	if h.leaseID != "" && subtle.ConstantTimeCompare([]byte(h.leaseID), []byte(request.LeaseID)) != 1 {
		http.Error(w, "another browser tab is active", http.StatusConflict)
		return
	}
	h.leaseID = request.LeaseID
	h.lastActive = time.Now()
	writeBrowserJSON(w, http.StatusOK, map[string]string{"status": "ACTIVE"})
}

func validBrowserLeaseID(value string) bool {
	if len(value) < 32 || len(value) > 128 {
		return false
	}
	for _, r := range value {
		if !(r >= 'a' && r <= 'z' || r >= 'A' && r <= 'Z' || r >= '0' && r <= '9' || r == '-' || r == '_') {
			return false
		}
	}
	return true
}

func (h *browserHost) validSession(r *http.Request) bool {
	if !h.localOnly {
		return true
	}
	cookie, err := r.Cookie(browserCookieName)
	if err != nil {
		return false
	}
	supplied, err := hex.DecodeString(cookie.Value)
	return err == nil && len(supplied) == len(h.session) && subtle.ConstantTimeCompare(supplied, h.session[:]) == 1
}

func (h *browserHost) authorized(w http.ResponseWriter, r *http.Request) bool {
	return h.authorizeRequest(w, r, false)
}

func (h *browserHost) authorizeCall(w http.ResponseWriter, r *http.Request) bool {
	return h.authorizeRequest(w, r, true)
}

func (h *browserHost) authorizeRequest(w http.ResponseWriter, r *http.Request, countCall bool) bool {
	if !h.validSession(r) {
		http.Error(w, "session rejected", http.StatusUnauthorized)
		return false
	}
	h.mu.Lock()
	if h.stopping {
		h.mu.Unlock()
		http.Error(w, "browser host is shutting down", http.StatusServiceUnavailable)
		return false
	}
	lease := h.leaseID
	if lease == "" || subtle.ConstantTimeCompare([]byte(lease), []byte(r.Header.Get("X-Platform-UI-Lease"))) != 1 {
		h.mu.Unlock()
		http.Error(w, "tab lease rejected", http.StatusForbidden)
		return false
	}
	if countCall && h.activeCalls >= browserMaxCalls {
		h.mu.Unlock()
		http.Error(w, "application busy", http.StatusTooManyRequests)
		return false
	}
	h.lastActive = time.Now()
	if countCall {
		h.activeCalls++
	}
	h.mu.Unlock()
	return true
}

func (h *browserHost) finishCall() {
	h.mu.Lock()
	h.activeCalls--
	h.mu.Unlock()
}

func (h *browserHost) handleCall(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method rejected", http.StatusMethodNotAllowed)
		return
	}
	if !h.authorizeCall(w, r) {
		return
	}
	defer h.finishCall()
	if r.Header.Get("Content-Type") != "application/json" {
		http.Error(w, "content type rejected", http.StatusUnsupportedMediaType)
		return
	}
	operationName := strings.TrimPrefix(r.URL.Path, "/api/call/")
	operation, ok := h.operations[operationName]
	if !ok || strings.Contains(operationName, "/") {
		http.NotFound(w, r)
		return
	}
	body, err := io.ReadAll(http.MaxBytesReader(w, r.Body, browserMaxRequest))
	if err != nil {
		writeBrowserError(w, http.StatusBadRequest, errors.New("REQUEST_BODY_INVALID"))
		return
	}
	defer clear(body)
	result, err := operation(h.app, body)
	if err != nil {
		writeBrowserError(w, http.StatusBadRequest, err)
		return
	}
	writeBrowserJSON(w, http.StatusOK, map[string]any{"result": result})
}

func (h *browserHost) handleHeartbeat(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method rejected", http.StatusMethodNotAllowed)
		return
	}
	if !h.authorized(w, r) {
		return
	}
	w.WriteHeader(http.StatusNoContent)
}

func (h *browserHost) handleExit(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method rejected", http.StatusMethodNotAllowed)
		return
	}
	if !h.authorized(w, r) {
		return
	}
	h.mu.Lock()
	h.exitPending = true
	h.mu.Unlock()
	status := "EXITING"
	if h.hasActiveRun() {
		status = "EXIT_AFTER_RUN"
	}
	writeBrowserJSON(w, http.StatusAccepted, map[string]string{"status": status})
}

func (h *browserHost) serveStatic(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet && r.Method != http.MethodHead {
		http.Error(w, "method rejected", http.StatusMethodNotAllowed)
		return
	}
	path := strings.TrimPrefix(r.URL.Path, "/")
	if path == "" || path == "index.html" {
		path = "browser.html"
	}
	if path == "browser.html" {
		data, err := fs.ReadFile(h.static, path)
		if err != nil {
			http.NotFound(w, r)
			return
		}
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		w.Header().Set("Cache-Control", "no-store")
		if !h.localOnly {
			data = bytes.Replace(data, []byte(`<script src="/browser-bootstrap.js"></script>`), []byte(`<script src="/browser-mode.js"></script><script src="/browser-bootstrap.js"></script>`), 1)
		}
		_, _ = w.Write(data)
		return
	}
	if path == "browser-mode.js" && !h.localOnly {
		w.Header().Set("Content-Type", "text/javascript; charset=utf-8")
		w.Header().Set("Cache-Control", "no-store")
		_, _ = io.WriteString(w, `window.__PI_BROWSER_REMOTE__ = true;`)
		return
	}
	if !fs.ValidPath(path) {
		http.NotFound(w, r)
		return
	}
	fileServer := http.FileServer(http.FS(h.static))
	cloned := r.Clone(r.Context())
	cloned.URL.Path = "/" + path
	fileServer.ServeHTTP(w, cloned)
}

func (h *browserHost) handleEvents(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "method rejected", http.StatusMethodNotAllowed)
		return
	}
	if !h.authorized(w, r) {
		return
	}
	flusher, ok := w.(http.Flusher)
	if !ok {
		http.Error(w, "stream unavailable", http.StatusInternalServerError)
		return
	}
	after, _ := strconv.ParseUint(r.Header.Get("Last-Event-ID"), 10, 64)
	backlog, events, remove, gap := h.hub.subscribe(after)
	defer remove()
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-store")
	w.Header().Set("Connection", "keep-alive")
	w.Header().Set("X-Accel-Buffering", "no")
	if gap {
		frame, _ := json.Marshal(map[string]any{"name": installationEventName, "payload": InstallationSubscriptionEvent{ErrorCode: "OBSERVER_HISTORY_GAP"}})
		_, _ = fmt.Fprintf(w, "data: %s\n\n", frame)
	}
	for _, item := range backlog {
		if !writeBrowserSSE(w, item) {
			return
		}
	}
	flusher.Flush()
	heartbeat := time.NewTicker(20 * time.Second)
	defer heartbeat.Stop()
	for {
		select {
		case <-r.Context().Done():
			return
		case item, open := <-events:
			if !open {
				return
			}
			if !writeBrowserSSE(w, item) {
				return
			}
			flusher.Flush()
		case <-heartbeat.C:
			if _, err := io.WriteString(w, ": ping\n\n"); err != nil {
				return
			}
			flusher.Flush()
		}
	}
}

func writeBrowserSSE(w io.Writer, event browserEvent) bool {
	_, err := fmt.Fprintf(w, "id: %d\ndata: %s\n\n", event.ID, event.Data)
	return err == nil
}

func decodeBrowserJSON(w http.ResponseWriter, r *http.Request, target any, limit int64) error {
	decoder := json.NewDecoder(http.MaxBytesReader(w, r.Body, limit))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(target); err != nil {
		return errors.New("REQUEST_BODY_INVALID")
	}
	var trailing any
	if err := decoder.Decode(&trailing); err != io.EOF {
		return errors.New("REQUEST_BODY_INVALID")
	}
	return nil
}

func writeBrowserJSON(w http.ResponseWriter, status int, payload any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(payload)
}

type browserEvent struct {
	ID   uint64
	Data []byte
}

type browserEventHub struct {
	mu          sync.Mutex
	nextID      uint64
	history     []browserEvent
	subscribers map[uint64]chan browserEvent
	nextSubID   uint64
}

func newBrowserEventHub() *browserEventHub {
	return &browserEventHub{subscribers: map[uint64]chan browserEvent{}}
}

func (h *browserEventHub) Publish(ctx context.Context, name string, payload any) {
	if ctx != nil && ctx.Err() != nil {
		return
	}
	data, err := json.Marshal(map[string]any{"name": name, "payload": payload})
	if err != nil {
		return
	}
	h.mu.Lock()
	h.nextID++
	event := browserEvent{ID: h.nextID, Data: data}
	h.history = append(h.history, event)
	if len(h.history) > 4096 {
		h.history = append([]browserEvent(nil), h.history[len(h.history)-4096:]...)
	}
	for id, channel := range h.subscribers {
		select {
		case channel <- event:
		default:
			delete(h.subscribers, id)
			close(channel)
		}
	}
	h.mu.Unlock()
}

func (h *browserEventHub) subscribe(after uint64) ([]browserEvent, <-chan browserEvent, func(), bool) {
	h.mu.Lock()
	defer h.mu.Unlock()
	gap := len(h.history) > 0 && after+1 < h.history[0].ID
	backlog := make([]browserEvent, 0, len(h.history))
	for _, event := range h.history {
		if event.ID > after {
			backlog = append(backlog, event)
		}
	}
	h.nextSubID++
	id := h.nextSubID
	channel := make(chan browserEvent, 256)
	h.subscribers[id] = channel
	remove := func() {
		h.mu.Lock()
		if current, ok := h.subscribers[id]; ok {
			delete(h.subscribers, id)
			close(current)
		}
		h.mu.Unlock()
	}
	return backlog, channel, remove, gap
}
