// Package runtimesecret holds short-lived, application-local target session
// credentials. It deliberately has no persistence or transport capability.
package runtimesecret

import (
	"crypto/ecdsa"
	"crypto/rand"
	"crypto/rsa"
	"crypto/x509"
	"encoding/pem"
	"errors"
	"io"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"
	"unicode/utf8"
)

const (
	StatusMissing = "MISSING"
	StatusPresent = "PRESENT"
	StatusExpired = "EXPIRED"

	SSHPassword   = "SSH_PASSWORD"
	SSHPrivateKey = "SSH_PRIVATE_KEY"
	ElevationNone = "NONE"
	ElevationSudo = "SUDO_PASSWORD"

	SudoNotProvided             = "NOT_PROVIDED"
	SudoPresent                 = "PRESENT"
	PKIStorePasswordNotRequired = "NOT_REQUIRED"
	PKIStorePasswordMissing     = "MISSING"
	PKIStorePasswordPresent     = "PRESENT"
)

const (
	maxUsernameBytes         = 255
	maxPasswordBytes         = 4 << 10
	maxPKIStorePasswordBytes = 4096
	maxKeyBytes              = 1 << 20
)

// Binding prevents a lease for one open project being observed by another.
type Binding struct {
	Root string
	ID   string
}

type Input struct {
	Username          string `json:"username"`
	SSHMode           string `json:"sshMode"`
	SSHPassword       string `json:"sshPassword"`
	PrivateKeyPath    string `json:"privateKeyPath"`
	ElevationMode     string `json:"elevationMode"`
	ElevationPassword string `json:"elevationPassword"`
}

// Status intentionally includes safe metadata only.
type Status struct {
	Status                 string `json:"status"`
	Username               string `json:"username,omitempty"`
	SSHMode                string `json:"sshMode,omitempty"`
	SudoPasswordStatus     string `json:"sudoPasswordStatus"`
	PKIStorePasswordStatus string `json:"pkiStorePasswordStatus"`
	ExpiresAt              string `json:"expiresAt,omitempty"`
}

// TargetCredential is a short-lived copy supplied only to a synchronous
// execution transport callback. It is intentionally not JSON serializable and
// has no persistence or Wails-facing representation.
type TargetCredential struct {
	Username         string
	SSHMode          string
	SSHSecret        []byte
	SudoSecret       []byte
	PKIStorePassword []byte
}

type lease struct {
	binding          Binding
	reference        []byte
	username         string
	sshMode          string
	sshSecret        []byte
	sudoSecret       []byte
	pkiStorePassword []byte
	expiresAt        time.Time
	generation       uint64
}

// SetPKIStorePassword updates only the optional in-memory PKI password on the
// current project-bound lease. It neither extends its TTL nor contacts a node.
func (b *Broker) SetPKIStorePassword(binding Binding, value string) (Status, error) {
	if !utf8.ValidString(value) || len([]byte(value)) < 1 || len([]byte(value)) > maxPKIStorePasswordBytes {
		return Status{}, errors.New("PKI_STORE_PASSWORD_INPUT_INVALID")
	}
	b.mu.Lock()
	defer b.mu.Unlock()
	if b.lease == nil || b.lease.binding != binding || !b.now().Before(b.lease.expiresAt) {
		if b.lease != nil && !b.now().Before(b.lease.expiresAt) {
			b.expireLocked(b.lease.generation)
		}
		return Status{}, errors.New("SESSION_CREDENTIAL_UNAVAILABLE")
	}
	next := append([]byte(nil), value...)
	zero(b.lease.pkiStorePassword)
	b.lease.pkiStorePassword = next
	return statusFromLease(b.lease), nil
}

type expiredMarker struct {
	binding   Binding
	expiresAt time.Time
}

type Broker struct {
	mu      sync.Mutex
	ttl     time.Duration
	now     func() time.Time
	lease   *lease
	expired *expiredMarker
	timer   *time.Timer
	nextGen uint64
}

type Option func(*Broker)

func WithTTL(ttl time.Duration) Option      { return func(b *Broker) { b.ttl = ttl } }
func WithClock(now func() time.Time) Option { return func(b *Broker) { b.now = now } }

func NewBroker(options ...Option) *Broker {
	b := &Broker{ttl: 30 * time.Minute, now: time.Now}
	for _, option := range options {
		option(b)
	}
	return b
}

// Set atomically replaces the lease after constructing and validating all
// input. A failed replacement leaves the prior lease untouched.
func (b *Broker) Set(binding Binding, input Input) (Status, error) {
	if binding.Root == "" || binding.ID == "" {
		return Status{}, errors.New("SESSION_CREDENTIAL_UNAVAILABLE")
	}
	candidate, err := b.buildLease(binding, input)
	if err != nil {
		return Status{}, err
	}
	b.mu.Lock()
	defer b.mu.Unlock()
	b.clearLeaseLocked(false)
	b.expired = nil
	b.nextGen++
	candidate.generation = b.nextGen
	candidate.expiresAt = b.now().Add(b.ttl)
	b.lease = candidate
	b.armExpiryLocked(candidate.generation, candidate.expiresAt)
	return statusFromLease(candidate), nil
}

func (b *Broker) Status(binding Binding) Status {
	b.mu.Lock()
	defer b.mu.Unlock()
	if b.lease != nil && b.lease.binding == binding {
		if !b.now().Before(b.lease.expiresAt) {
			b.expireLocked(b.lease.generation)
		} else {
			return statusFromLease(b.lease)
		}
	}
	if b.expired != nil && b.expired.binding == binding {
		return Status{Status: StatusExpired, SudoPasswordStatus: SudoNotProvided, PKIStorePasswordStatus: PKIStorePasswordMissing}
	}
	return missingStatus()
}

func (b *Broker) Clear() {
	b.mu.Lock()
	defer b.mu.Unlock()
	b.clearLeaseLocked(true)
}

func (b *Broker) Close() { b.Clear() }

// WithTargetCredential exposes one in-memory credential to a synchronous
// caller while the broker lease remains valid. The callback must not retain
// the slices; they are zeroed immediately after it returns.
func (b *Broker) WithTargetCredential(binding Binding, use func(TargetCredential) error) error {
	if use == nil {
		return errors.New("SESSION_CREDENTIAL_UNAVAILABLE")
	}
	b.mu.Lock()
	if b.lease == nil || b.lease.binding != binding || !b.now().Before(b.lease.expiresAt) {
		if b.lease != nil && !b.now().Before(b.lease.expiresAt) {
			b.expireLocked(b.lease.generation)
		}
		b.mu.Unlock()
		return errors.New("SESSION_CREDENTIAL_UNAVAILABLE")
	}
	value := TargetCredential{Username: b.lease.username, SSHMode: b.lease.sshMode, SSHSecret: append([]byte(nil), b.lease.sshSecret...), SudoSecret: append([]byte(nil), b.lease.sudoSecret...), PKIStorePassword: append([]byte(nil), b.lease.pkiStorePassword...)}
	b.mu.Unlock()
	defer zero(value.SSHSecret)
	defer zero(value.SudoSecret)
	defer zero(value.PKIStorePassword)
	return use(value)
}

func (b *Broker) buildLease(binding Binding, input Input) (*lease, error) {
	username := stringTrimSpace(input.Username)
	if username == "" || !utf8.ValidString(username) || len(username) > maxUsernameBytes {
		return nil, errors.New("SESSION_CREDENTIAL_INPUT_INVALID")
	}
	if input.ElevationMode == "" {
		input.ElevationMode = ElevationNone
	}
	var sshSecret []byte
	switch input.SSHMode {
	case SSHPassword:
		if len(input.SSHPassword) > maxPasswordBytes {
			return nil, errors.New("SESSION_CREDENTIAL_TOO_LARGE")
		}
		if input.PrivateKeyPath != "" || input.SSHPassword == "" {
			return nil, errors.New("SESSION_CREDENTIAL_MODE_INVALID")
		}
		sshSecret = []byte(input.SSHPassword)
	case SSHPrivateKey:
		if input.SSHPassword != "" || input.PrivateKeyPath == "" || !filepath.IsAbs(input.PrivateKeyPath) {
			return nil, errors.New("SESSION_CREDENTIAL_MODE_INVALID")
		}
		key, err := readPrivateKey(input.PrivateKeyPath)
		if err != nil {
			return nil, err
		}
		sshSecret = key
	default:
		return nil, errors.New("SESSION_CREDENTIAL_MODE_INVALID")
	}
	var sudoSecret []byte
	switch input.ElevationMode {
	case ElevationNone:
		if input.ElevationPassword != "" {
			zero(sshSecret)
			return nil, errors.New("SESSION_CREDENTIAL_MODE_INVALID")
		}
	case ElevationSudo:
		if len(input.ElevationPassword) > maxPasswordBytes {
			zero(sshSecret)
			return nil, errors.New("SESSION_CREDENTIAL_TOO_LARGE")
		}
		if input.ElevationPassword == "" {
			zero(sshSecret)
			return nil, errors.New("SESSION_CREDENTIAL_MODE_INVALID")
		}
		sudoSecret = []byte(input.ElevationPassword)
	default:
		zero(sshSecret)
		return nil, errors.New("SESSION_CREDENTIAL_MODE_INVALID")
	}
	reference := make([]byte, 16)
	if _, err := rand.Read(reference); err != nil {
		zero(sshSecret)
		zero(sudoSecret)
		return nil, errors.New("SESSION_CREDENTIAL_UNAVAILABLE")
	}
	return &lease{binding: binding, reference: reference, username: username, sshMode: input.SSHMode, sshSecret: sshSecret, sudoSecret: sudoSecret}, nil
}

func readPrivateKey(path string) ([]byte, error) {
	info, err := os.Lstat(path)
	if err != nil {
		return nil, errors.New("SESSION_PRIVATE_KEY_UNREADABLE")
	}
	if !info.Mode().IsRegular() || info.Mode()&os.ModeSymlink != 0 {
		return nil, errors.New("SESSION_PRIVATE_KEY_NOT_REGULAR")
	}
	file, err := os.Open(path)
	if err != nil {
		return nil, errors.New("SESSION_PRIVATE_KEY_UNREADABLE")
	}
	defer file.Close()
	opened, err := file.Stat()
	if err != nil || !opened.Mode().IsRegular() || opened.Mode()&os.ModeSymlink != 0 {
		return nil, errors.New("SESSION_PRIVATE_KEY_NOT_REGULAR")
	}
	contents, err := io.ReadAll(io.LimitReader(file, maxKeyBytes+1))
	if err != nil {
		return nil, errors.New("SESSION_PRIVATE_KEY_UNREADABLE")
	}
	if len(contents) > maxKeyBytes {
		zero(contents)
		return nil, errors.New("SESSION_CREDENTIAL_TOO_LARGE")
	}
	if err := validatePrivateKey(contents); err != nil {
		zero(contents)
		if errors.Is(err, errEncryptedPrivateKey) {
			return nil, errors.New("SESSION_PRIVATE_KEY_ENCRYPTED_UNSUPPORTED")
		}
		return nil, errors.New("SESSION_PRIVATE_KEY_INVALID")
	}
	return contents, nil
}

var errEncryptedPrivateKey = errors.New("encrypted private key")

// validatePrivateKey accepts the portable unencrypted PEM key forms supported
// by Go's standard library. It intentionally does not invoke an external
// parser or leave parser diagnostics available to callers.
func validatePrivateKey(contents []byte) error {
	block, rest := pem.Decode(contents)
	if block == nil || len(strings.TrimSpace(string(rest))) != 0 {
		return errors.New("invalid private key")
	}
	if x509.IsEncryptedPEMBlock(block) || strings.Contains(block.Type, "ENCRYPTED") {
		return errEncryptedPrivateKey
	}
	if key, err := x509.ParsePKCS8PrivateKey(block.Bytes); err == nil {
		switch key.(type) {
		case *rsa.PrivateKey, *ecdsa.PrivateKey:
			return nil
		default:
			return errors.New("unsupported private key")
		}
	}
	if _, err := x509.ParsePKCS1PrivateKey(block.Bytes); err == nil {
		return nil
	}
	if _, err := x509.ParseECPrivateKey(block.Bytes); err == nil {
		return nil
	}
	return errors.New("invalid private key")
}

func (b *Broker) armExpiryLocked(generation uint64, expiresAt time.Time) {
	if b.timer != nil {
		b.timer.Stop()
	}
	b.timer = time.AfterFunc(b.ttl, func() {
		b.mu.Lock()
		defer b.mu.Unlock()
		b.expireLocked(generation)
	})
}

func (b *Broker) expireLocked(generation uint64) {
	if b.lease == nil || b.lease.generation != generation {
		return
	}
	binding, expiresAt := b.lease.binding, b.lease.expiresAt
	b.clearLeaseLocked(false)
	b.expired = &expiredMarker{binding: binding, expiresAt: expiresAt}
}

func (b *Broker) clearLeaseLocked(clearExpired bool) {
	if b.timer != nil {
		b.timer.Stop()
		b.timer = nil
	}
	if b.lease != nil {
		zero(b.lease.reference)
		zero(b.lease.sshSecret)
		zero(b.lease.sudoSecret)
		zero(b.lease.pkiStorePassword)
		b.lease = nil
	}
	if clearExpired {
		b.expired = nil
	}
}

func statusFromLease(value *lease) Status {
	sudo := SudoNotProvided
	if len(value.sudoSecret) != 0 {
		sudo = SudoPresent
	}
	pki := PKIStorePasswordMissing
	if len(value.pkiStorePassword) != 0 {
		pki = PKIStorePasswordPresent
	}
	return Status{Status: StatusPresent, Username: value.username, SSHMode: value.sshMode, SudoPasswordStatus: sudo, PKIStorePasswordStatus: pki, ExpiresAt: value.expiresAt.UTC().Format(time.RFC3339)}
}

func missingStatus() Status {
	return Status{Status: StatusMissing, SudoPasswordStatus: SudoNotProvided, PKIStorePasswordStatus: PKIStorePasswordMissing}
}
func zero(value []byte) {
	for i := range value {
		value[i] = 0
	}
}
func stringTrimSpace(value string) string { return strings.TrimSpace(value) }
