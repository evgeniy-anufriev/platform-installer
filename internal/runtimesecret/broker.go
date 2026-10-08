// Package runtimesecret holds short-lived, application-local target session
// credentials. It deliberately has no persistence or transport capability.
package runtimesecret

import (
	"crypto/ecdsa"
	"crypto/rand"
	"crypto/rsa"
	"crypto/sha256"
	"crypto/x509"
	"encoding/pem"
	"errors"
	"io"
	"os"
	"path/filepath"
	"regexp"
	"sort"
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
	Username            string
	SSHMode             string
	SSHSecret           []byte
	SudoSecret          []byte
	PKIStorePassword    []byte
	RuntimeSecretValues map[string][]byte
	RuntimeSecretInputs []RuntimeSecretInput
}

// RuntimeSecretInput is a typed, short-lived payload for the private v1alpha4
// lease. Values are borrowed by one synchronous execution callback and cleared
// immediately afterwards.
type RuntimeSecretInput struct {
	RequirementRef, Purpose, ServiceDeployment string
	Operations                                 []string
	Value                                      []byte
	Shares                                     [][]byte
}

type lease struct {
	binding             Binding
	reference           []byte
	username            string
	sshMode             string
	sshSecret           []byte
	privateKeyPath      string
	privateKeyInfo      os.FileInfo
	sudoSecret          []byte
	pkiStorePassword    []byte
	runtimeSecretValues map[string][]byte
	runtimeSecretInputs []RuntimeSecretInput
	expiresAt           time.Time
	generation          uint64
}

// runExecutionIdentityHold retains the approved identity during one Start/run.
// PEM bytes are never copied; the original file stays verified. Password mode
// retains a private, wiped-on-release copy for that exact operation only.
type runExecutionIdentityHold struct {
	state        string
	planID       string
	runID        string
	binding      Binding
	identity     ExecutionIdentity
	password     []byte
	sudoPassword []byte
}

// pendingRuntimeSecrets holds service-password values entered before a target
// credential is available.  It is project-bound, short-lived and deliberately
// separate from a transport credential: it cannot be used for SSH or exposed
// through Status.
type pendingRuntimeSecrets struct {
	binding    Binding
	values     map[string][]byte
	typed      map[string]RuntimeSecretInput
	expiresAt  time.Time
	generation uint64
}

// SetPendingServiceSecretInput stores a locally catalog-authorized typed
// secret without requiring a target credential or Execution Node readiness.
// Core later supplies the opaque exact requirementRef and allowed operations.
func (b *Broker) SetPendingServiceSecretInput(binding Binding, deployment, purpose string, value []byte, shares [][]byte) error {
	if binding.Root == "" || binding.ID == "" || deployment == "" || len(deployment) > 128 {
		return errors.New("RUNTIME_SECRET_INPUT_INVALID")
	}
	input := RuntimeSecretInput{Purpose: purpose, ServiceDeployment: deployment}
	switch purpose {
	case "SERVICE_ADMIN_TOKEN":
		if len(value) == 0 || len(value) > 4096 || len(shares) != 0 || !utf8.Valid(value) {
			return errors.New("RUNTIME_SECRET_INPUT_INVALID")
		}
		input.Value = append([]byte(nil), value...)
	case "SERVICE_UNSEAL_SHARES":
		if len(shares) == 0 || len(shares) > 255 || len(value) != 0 {
			return errors.New("RUNTIME_SECRET_INPUT_INVALID")
		}
		seen := map[string]bool{}
		total := 0
		for _, share := range shares {
			if len(share) == 0 || len(share) > 128 || !utf8.Valid(share) || seen[string(share)] {
				return errors.New("RUNTIME_SECRET_INPUT_INVALID")
			}
			seen[string(share)] = true
			total += len(share)
		}
		if total > 32768 {
			return errors.New("RUNTIME_SECRET_INPUT_INVALID")
		}
		input.Shares = cloneSecretSlices(shares)
	default:
		return errors.New("RUNTIME_SECRET_INPUT_INVALID")
	}
	key := typedSecretKey(deployment, purpose)
	b.mu.Lock()
	defer b.mu.Unlock()
	if b.pending == nil || b.pending.binding != binding || !b.now().Before(b.pending.expiresAt) {
		if b.pending != nil && !b.now().Before(b.pending.expiresAt) {
			b.clearPendingLocked()
		}
		b.nextGen++
		b.pending = &pendingRuntimeSecrets{binding: binding, values: map[string][]byte{}, typed: map[string]RuntimeSecretInput{}, expiresAt: b.now().Add(b.ttl), generation: b.nextGen}
		b.armPendingExpiryLocked(b.pending.generation, b.pending.expiresAt)
	}
	if b.pending.typed == nil {
		b.pending.typed = map[string]RuntimeSecretInput{}
	}
	if previous, ok := b.pending.typed[key]; ok {
		zeroRuntimeSecretInput(previous)
	}
	b.pending.typed[key] = input
	return nil
}

// BindPendingServiceSecretInputs maps local deployment/purpose values onto
// the exact current Core descriptors before target credential serialization.
func (b *Broker) BindPendingServiceSecretInputs(binding Binding, descriptors []RuntimeSecretInput) error {
	b.mu.Lock()
	defer b.mu.Unlock()
	if b.pending == nil || b.pending.binding != binding || !b.now().Before(b.pending.expiresAt) || b.lease == nil || b.lease.binding != binding || !b.now().Before(b.lease.expiresAt) {
		return nil
	}
	allowed := make(map[string]RuntimeSecretInput, len(descriptors))
	for _, descriptor := range descriptors {
		if !validTypedDescriptor(descriptor) {
			return errors.New("RUNTIME_SECRET_DESCRIPTORS_STALE")
		}
		key := typedSecretKey(descriptor.ServiceDeployment, descriptor.Purpose)
		if _, exists := allowed[key]; exists {
			return errors.New("RUNTIME_SECRET_DESCRIPTORS_STALE")
		}
		allowed[key] = descriptor
	}
	attached := make([]RuntimeSecretInput, 0, len(b.pending.typed))
	for key, pending := range b.pending.typed {
		descriptor, ok := allowed[key]
		if !ok {
			return errors.New("RUNTIME_SECRET_DESCRIPTORS_STALE")
		}
		descriptor.Value = append([]byte(nil), pending.Value...)
		descriptor.Shares = cloneSecretSlices(pending.Shares)
		attached = append(attached, descriptor)
	}
	sort.Slice(attached, func(i, j int) bool { return attached[i].RequirementRef < attached[j].RequirementRef })
	for _, old := range b.lease.runtimeSecretInputs {
		zeroRuntimeSecretInput(old)
	}
	b.lease.runtimeSecretInputs = attached
	return nil
}

func validTypedDescriptor(value RuntimeSecretInput) bool {
	if !runtimeSecretID(value.RequirementRef) || value.ServiceDeployment == "" || len(value.ServiceDeployment) > 128 {
		return false
	}
	switch value.Purpose {
	case "SERVICE_ADMIN_TOKEN":
		return len(value.Operations) == 2 && value.Operations[0] == "SERVICE_APPLY" && value.Operations[1] == "SERVICE_VERIFY"
	case "SERVICE_UNSEAL_SHARES":
		return len(value.Operations) == 1 && value.Operations[0] == "SERVICE_APPLY"
	default:
		return false
	}
}

func typedSecretKey(deployment, purpose string) string { return deployment + "\x00" + purpose }

func zeroRuntimeSecretInput(value RuntimeSecretInput) {
	zero(value.Value)
	zeroByteSlices(value.Shares)
}

func zeroTypedSecretMap(values map[string]RuntimeSecretInput) {
	for _, value := range values {
		zeroRuntimeSecretInput(value)
	}
}

func zeroByteSlices(values [][]byte) {
	for _, value := range values {
		zero(value)
	}
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

// SetRuntimeSecretValues replaces the session-only service-secret set.  The
// caller supplies only safe requirement IDs; values never enter Status or a
// serializable DTO.
func (b *Broker) SetRuntimeSecretValues(binding Binding, values map[string]string) error {
	if len(values) == 0 || len(values) > 16 {
		return errors.New("RUNTIME_SECRET_INPUT_INVALID")
	}
	next, total := make(map[string][]byte, len(values)), 0
	for reference, value := range values {
		if !runtimeSecretID(reference) || !utf8.ValidString(value) || len([]byte(value)) < 1 || len([]byte(value)) > 4096 {
			zeroSecretMap(next)
			return errors.New("RUNTIME_SECRET_INPUT_INVALID")
		}
		total += len([]byte(value))
		if total > 65536 {
			zeroSecretMap(next)
			return errors.New("RUNTIME_SECRET_INPUT_INVALID")
		}
		next[reference] = []byte(value)
	}
	b.mu.Lock()
	defer b.mu.Unlock()
	if b.lease == nil || b.lease.binding != binding || !b.now().Before(b.lease.expiresAt) {
		zeroSecretMap(next)
		return errors.New("SESSION_CREDENTIAL_UNAVAILABLE")
	}
	zeroSecretMap(b.lease.runtimeSecretValues)
	b.lease.runtimeSecretValues = next
	return nil
}

// SetRuntimeSecretValuesForRequirements replaces only one descriptor-bound
// subset. Other acknowledged service values remain in the same short-lived
// lease, so separate service dialogs cannot erase each other.
func (b *Broker) SetRuntimeSecretValuesForRequirements(binding Binding, requirements []string, values map[string]string) error {
	if !sameRuntimeSecretRequirements(requirements, values) {
		return errors.New("RUNTIME_SECRET_INPUT_INVALID")
	}
	b.mu.Lock()
	defer b.mu.Unlock()
	if b.lease == nil || b.lease.binding != binding || !b.now().Before(b.lease.expiresAt) {
		return errors.New("SESSION_CREDENTIAL_UNAVAILABLE")
	}
	next := cloneSecretMap(b.lease.runtimeSecretValues)
	for _, reference := range requirements {
		zero(next[reference])
		delete(next, reference)
	}
	for reference, value := range values {
		next[reference] = []byte(value)
	}
	if !validRuntimeSecretMap(next) {
		zeroSecretMap(next)
		return errors.New("RUNTIME_SECRET_INPUT_INVALID")
	}
	zeroSecretMap(b.lease.runtimeSecretValues)
	b.lease.runtimeSecretValues = next
	return nil
}

// SetPendingRuntimeSecretValuesForRequirements accepts a locally
// catalog-authorized service-secret subset before a READY Execution Node or a
// target credential exists. Values are kept only in Broker memory and expire
// on the same bounded TTL as session credentials.
func (b *Broker) SetPendingRuntimeSecretValuesForRequirements(binding Binding, requirements []string, values map[string]string) error {
	if binding.Root == "" || binding.ID == "" || !sameRuntimeSecretRequirements(requirements, values) {
		return errors.New("RUNTIME_SECRET_INPUT_INVALID")
	}
	next := make(map[string][]byte, len(values))
	for reference, value := range values {
		next[reference] = []byte(value)
	}
	b.mu.Lock()
	defer b.mu.Unlock()
	if b.pending != nil && b.pending.binding == binding && b.now().Before(b.pending.expiresAt) {
		merged := cloneSecretMap(b.pending.values)
		typed := cloneTypedSecretMap(b.pending.typed)
		for _, reference := range requirements {
			zero(merged[reference])
			delete(merged, reference)
		}
		for reference, value := range next {
			merged[reference] = value
		}
		next = merged
		b.clearPendingLocked()
		b.pending = &pendingRuntimeSecrets{binding: binding, values: next, typed: typed, expiresAt: b.now().Add(b.ttl)}
		b.nextGen++
		b.pending.generation = b.nextGen
		b.armPendingExpiryLocked(b.pending.generation, b.pending.expiresAt)
		return nil
	}
	if !validRuntimeSecretMap(next) {
		zeroSecretMap(next)
		return errors.New("RUNTIME_SECRET_INPUT_INVALID")
	}
	b.clearPendingLocked()
	b.nextGen++
	b.pending = &pendingRuntimeSecrets{binding: binding, values: next, expiresAt: b.now().Add(b.ttl), generation: b.nextGen}
	b.armPendingExpiryLocked(b.pending.generation, b.pending.expiresAt)
	return nil
}

// PromotePendingRuntimeSecretValues moves values into the target credential
// only after Core has produced the current descriptor set. Every pending key
// must be in that set; stale or superseded local requirements fail closed.
func (b *Broker) PromotePendingRuntimeSecretValues(binding Binding, requirements []string) error {
	b.mu.Lock()
	defer b.mu.Unlock()
	if b.pending == nil || b.pending.binding != binding {
		return nil
	}
	if !b.now().Before(b.pending.expiresAt) {
		b.clearPendingLocked()
		return errors.New("RUNTIME_SECRET_INPUT_EXPIRED")
	}
	if b.lease == nil || b.lease.binding != binding || !b.now().Before(b.lease.expiresAt) {
		return nil
	}
	allowed := make(map[string]struct{}, len(requirements))
	for _, reference := range requirements {
		if !runtimeSecretID(reference) {
			return errors.New("RUNTIME_SECRET_DESCRIPTORS_STALE")
		}
		allowed[reference] = struct{}{}
	}
	for reference := range b.pending.values {
		if _, ok := allowed[reference]; !ok {
			return errors.New("RUNTIME_SECRET_DESCRIPTORS_STALE")
		}
	}
	// Typed inputs share this pending bucket but are authorized and bound by
	// BindPendingServiceSecretInputs, not by password-map promotion.
	if len(b.pending.values) == 0 {
		return nil
	}
	next := cloneSecretMap(b.lease.runtimeSecretValues)
	for reference, value := range b.pending.values {
		zero(next[reference])
		next[reference] = append([]byte(nil), value...)
	}
	if !validRuntimeSecretMap(next) {
		zeroSecretMap(next)
		return errors.New("RUNTIME_SECRET_INPUT_INVALID")
	}
	zeroSecretMap(b.lease.runtimeSecretValues)
	b.lease.runtimeSecretValues = next
	zeroSecretMap(b.pending.values)
	b.pending.values = nil
	if len(b.pending.typed) == 0 {
		b.clearPendingLocked()
	}
	return nil
}

// ClearRuntimeSecretValues leaves the target credential and optional PKI
// password intact while invalidating descriptor-bound service values.
func (b *Broker) ClearRuntimeSecretValues(binding Binding) {
	b.mu.Lock()
	defer b.mu.Unlock()
	if b.lease != nil && b.lease.binding == binding {
		zeroSecretMap(b.lease.runtimeSecretValues)
		b.lease.runtimeSecretValues = nil
		zeroTypedSecretSlice(b.lease.runtimeSecretInputs)
		b.lease.runtimeSecretInputs = nil
	}
	if b.pending != nil && b.pending.binding == binding {
		b.clearPendingLocked()
	}
}

// ClearAttachedRuntimeSecretValues removes only values already attached to a
// target credential. Pending locally entered values remain available for the
// immediately following Core-attested promotion step.
func (b *Broker) ClearAttachedRuntimeSecretValues(binding Binding) {
	b.mu.Lock()
	defer b.mu.Unlock()
	if b.lease != nil && b.lease.binding == binding {
		zeroSecretMap(b.lease.runtimeSecretValues)
		b.lease.runtimeSecretValues = nil
		zeroTypedSecretSlice(b.lease.runtimeSecretInputs)
		b.lease.runtimeSecretInputs = nil
	}
}

type expiredMarker struct {
	binding    Binding
	expiresAt  time.Time
	generation uint64
}

type Broker struct {
	mu              sync.Mutex
	ttl             time.Duration
	now             func() time.Time
	lease           *lease
	runHold         *runExecutionIdentityHold
	pending         *pendingRuntimeSecrets
	outputPassword  []byte
	outputBinding   Binding
	outputExpiresAt time.Time
	expired         *expiredMarker
	timer           *time.Timer
	nextGen         uint64
}

// SetOutputEncryptionPassword keeps the workstation-only age password in the
// same bounded in-memory broker as other session secrets. It is never part of
// TargetCredential or any transport payload.
func (b *Broker) SetOutputEncryptionPassword(binding Binding, password []byte) error {
	if binding.Root == "" || binding.ID == "" || len(password) == 0 || len(password) > maxPKIStorePasswordBytes || !utf8.Valid(password) {
		return errors.New("SECRET_OUTPUT_PASSWORD_INVALID")
	}
	b.mu.Lock()
	defer b.mu.Unlock()
	if b.outputBinding != binding {
		zero(b.outputPassword)
	}
	b.outputPassword = append(b.outputPassword[:0], password...)
	b.outputBinding = binding
	b.outputExpiresAt = b.now().Add(b.ttl)
	return nil
}

// WithOutputEncryptionPassword lends a short-lived copy synchronously and
// zeroes it after callback completion. It is not exposed in status or DTOs.
func (b *Broker) WithOutputEncryptionPassword(binding Binding, use func([]byte) error) error {
	if use == nil {
		return errors.New("SECRET_OUTPUT_PASSWORD_MISSING")
	}
	b.mu.Lock()
	if b.outputBinding != binding || len(b.outputPassword) == 0 || !b.now().Before(b.outputExpiresAt) {
		if len(b.outputPassword) > 0 && !b.now().Before(b.outputExpiresAt) {
			zero(b.outputPassword)
			b.outputPassword = nil
		}
		b.mu.Unlock()
		return errors.New("SECRET_OUTPUT_PASSWORD_MISSING")
	}
	copyValue := append([]byte(nil), b.outputPassword...)
	b.mu.Unlock()
	defer zero(copyValue)
	return use(copyValue)
}

func (b *Broker) ClearOutputEncryptionPassword(binding Binding) {
	b.mu.Lock()
	defer b.mu.Unlock()
	if b.outputBinding == binding {
		zero(b.outputPassword)
		b.outputPassword = nil
		b.outputBinding = Binding{}
		b.outputExpiresAt = time.Time{}
	}
}

func (b *Broker) HasOutputEncryptionPassword(binding Binding) bool {
	b.mu.Lock()
	defer b.mu.Unlock()
	if b.outputBinding != binding || len(b.outputPassword) == 0 {
		return false
	}
	if !b.now().Before(b.outputExpiresAt) {
		zero(b.outputPassword)
		b.outputPassword = nil
		b.outputBinding = Binding{}
		b.outputExpiresAt = time.Time{}
		return false
	}
	return true
}

type Option func(*Broker)

func WithTTL(ttl time.Duration) Option      { return func(b *Broker) { b.ttl = ttl } }
func WithClock(now func() time.Time) Option { return func(b *Broker) { b.now = now } }

func NewBroker(options ...Option) *Broker {
	b := &Broker{ttl: 2 * time.Hour, now: time.Now}
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
	if b.runHold != nil {
		zero(candidate.sshSecret)
		zero(candidate.sudoSecret)
		zero(candidate.pkiStorePassword)
		zeroSecretMap(candidate.runtimeSecretValues)
		zeroTypedSecretSlice(candidate.runtimeSecretInputs)
		return Status{}, errors.New("INSTALLATION_RUN_ACTIVE")
	}
	if b.outputBinding != binding {
		zero(b.outputPassword)
		b.outputPassword = nil
		b.outputBinding = Binding{}
		b.outputExpiresAt = time.Time{}
	}
	b.clearLeaseLocked(false)
	if b.pending != nil && b.pending.binding != binding {
		b.clearPendingLocked()
	}
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
	b.clearPendingLocked()
	b.clearRunHoldsLocked()
	zero(b.outputPassword)
	b.outputPassword = nil
	b.outputBinding = Binding{}
	b.outputExpiresAt = time.Time{}
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
	value := TargetCredential{Username: b.lease.username, SSHMode: b.lease.sshMode, SSHSecret: append([]byte(nil), b.lease.sshSecret...), SudoSecret: append([]byte(nil), b.lease.sudoSecret...), PKIStorePassword: append([]byte(nil), b.lease.pkiStorePassword...), RuntimeSecretValues: cloneSecretMap(b.lease.runtimeSecretValues), RuntimeSecretInputs: cloneTypedSecretSlice(b.lease.runtimeSecretInputs)}
	b.mu.Unlock()
	defer zero(value.SSHSecret)
	defer zero(value.SudoSecret)
	defer zero(value.PKIStorePassword)
	defer zeroSecretMap(value.RuntimeSecretValues)
	defer zeroTypedSecretSlice(value.RuntimeSecretInputs)
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
	var keyInfo os.FileInfo
	switch input.SSHMode {
	case SSHPassword:
		if len(input.SSHPassword) > maxPasswordBytes {
			return nil, errors.New("SESSION_CREDENTIAL_TOO_LARGE")
		}
		if strings.ContainsAny(input.SSHPassword, "\r\n\x00") {
			return nil, errors.New("SESSION_CREDENTIAL_PASSWORD_FORMAT_UNSUPPORTED")
		}
		if input.PrivateKeyPath != "" || input.SSHPassword == "" {
			return nil, errors.New("SESSION_CREDENTIAL_MODE_INVALID")
		}
		sshSecret = []byte(input.SSHPassword)
	case SSHPrivateKey:
		if input.SSHPassword != "" || input.PrivateKeyPath == "" || !filepath.IsAbs(input.PrivateKeyPath) {
			return nil, errors.New("SESSION_CREDENTIAL_MODE_INVALID")
		}
		key, info, err := readPrivateKeyWithInfo(input.PrivateKeyPath)
		if err != nil {
			return nil, err
		}
		sshSecret = key
		keyInfo = info
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
		if strings.ContainsAny(input.ElevationPassword, "\r\n\x00") {
			zero(sshSecret)
			return nil, errors.New("SESSION_CREDENTIAL_PASSWORD_FORMAT_UNSUPPORTED")
		}
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
	keyPath := ""
	if input.SSHMode == SSHPrivateKey {
		keyPath = filepath.Clean(input.PrivateKeyPath)
	}
	return &lease{binding: binding, reference: reference, username: username, sshMode: input.SSHMode, sshSecret: sshSecret, privateKeyPath: keyPath, privateKeyInfo: keyInfo, sudoSecret: sudoSecret}, nil
}

// ExecutionIdentity is private application transport metadata. It must never
// cross Wails, logs or the portable project boundary.
type ExecutionIdentity struct {
	Mode       string
	Path       string
	Username   string
	Digest     [sha256.Size]byte
	Generation uint64
	FileInfo   os.FileInfo
}

func (b *Broker) CurrentExecutionIdentity(binding Binding) (ExecutionIdentity, error) {
	b.mu.Lock()
	defer b.mu.Unlock()
	if b.lease != nil && b.lease.binding == binding && b.now().Before(b.lease.expiresAt) {
		return executionIdentityFromLease(b.lease)
	}
	if b.lease != nil && !b.now().Before(b.lease.expiresAt) {
		b.expireLocked(b.lease.generation)
	}
	if identity, ok := b.heldExecutionIdentityLocked(binding); ok && identity.Mode != SSHPassword {
		return identity, nil
	}
	return ExecutionIdentity{}, errors.New("EXECUTION_NODE_PEM_REQUIRED")
}

// ReserveExecutionIdentityForStart retains only approved identity metadata
// before dispatch. The reservation is idempotent for a retry of the same plan.
func (b *Broker) ReserveExecutionIdentityForStart(binding Binding, planID string, identity ExecutionIdentity) error {
	if binding.Root == "" || binding.ID == "" || planID == "" || len(planID) > 128 ||
		identity.Username == "" || identity.Generation == 0 ||
		(identity.Mode != SSHPassword && (identity.Path == "" || identity.FileInfo == nil || identity.Digest == [sha256.Size]byte{})) {
		return errors.New("EXECUTION_RUN_IDENTITY_INVALID")
	}
	b.mu.Lock()
	defer b.mu.Unlock()
	if hold := b.runHold; hold != nil {
		if hold.state == "STARTING" && hold.binding == binding && hold.planID == planID && sameExecutionIdentity(hold.identity, identity) {
			return nil
		}
		return errors.New("INSTALLATION_RUN_ACTIVE")
	}
	if b.lease != nil && b.lease.binding == binding && b.lease.generation == identity.Generation {
		if !b.now().Before(b.lease.expiresAt) {
			b.expireLocked(b.lease.generation)
		}
	}
	if b.lease != nil && b.lease.binding == binding && b.now().Before(b.lease.expiresAt) {
		current, err := executionIdentityFromLease(b.lease)
		if err != nil || !sameExecutionIdentity(current, identity) {
			return errors.New("EXECUTION_RUN_IDENTITY_STALE")
		}
	} else if b.expired == nil || b.expired.binding != binding || b.expired.generation != identity.Generation {
		return errors.New("EXECUTION_RUN_IDENTITY_STALE")
	}
	if identity.Mode == SSHPassword && (b.lease == nil || !b.now().Before(b.lease.expiresAt)) {
		return errors.New("EXECUTION_RUN_IDENTITY_STALE")
	}
	b.runHold = &runExecutionIdentityHold{state: "STARTING", planID: planID, binding: binding, identity: identity}
	if identity.Mode == SSHPassword {
		b.runHold.password = append([]byte(nil), b.lease.sshSecret...)
	}
	if b.lease != nil && b.now().Before(b.lease.expiresAt) {
		b.runHold.sudoPassword = append([]byte(nil), b.lease.sudoSecret...)
	}
	return nil
}

// ConfirmExecutionIdentityRun binds the reserved slot to the authoritative
// run ID returned by Start. It remains usable after ordinary lease expiry.
func (b *Broker) ConfirmExecutionIdentityRun(binding Binding, planID, runID string) error {
	if runID == "" || len(runID) > 128 {
		return errors.New("EXECUTION_RUN_IDENTITY_INVALID")
	}
	b.mu.Lock()
	defer b.mu.Unlock()
	hold := b.runHold
	if hold == nil || hold.state != "STARTING" || hold.binding != binding || hold.planID != planID {
		return errors.New("EXECUTION_RUN_IDENTITY_STALE")
	}
	hold.state, hold.runID = "RUNNING", runID
	return nil
}

// ReleaseStartingExecutionIdentity releases only a reservation whose Start
// was authoritatively not dispatched.
func (b *Broker) ReleaseStartingExecutionIdentity(binding Binding, planID string) {
	b.mu.Lock()
	defer b.mu.Unlock()
	if hold := b.runHold; hold != nil && hold.state == "STARTING" && hold.binding == binding && hold.planID == planID {
		zero(hold.password)
		zero(hold.sudoPassword)
		clearExecutionIdentity(&hold.identity)
		b.runHold = nil
	}
}

// ReleaseExecutionIdentityForRun releases one run's retained metadata after
// its authoritative terminal state has been observed.
func (b *Broker) ReleaseExecutionIdentityForRun(runID string) {
	b.mu.Lock()
	defer b.mu.Unlock()
	if hold := b.runHold; hold != nil && hold.state == "RUNNING" && hold.runID == runID {
		zero(hold.password)
		zero(hold.sudoPassword)
		clearExecutionIdentity(&hold.identity)
		b.runHold = nil
	}
}

// ClearRunExecutionIdentityHolds is used when the owning project or trusted
// Execution Node context is replaced. It does not alter any ordinary lease.
func (b *Broker) ClearRunExecutionIdentityHolds() {
	b.mu.Lock()
	defer b.mu.Unlock()
	b.clearRunHoldsLocked()
}

func (b *Broker) HasRunExecutionIdentityHold(binding Binding) bool {
	b.mu.Lock()
	defer b.mu.Unlock()
	return b.hasRunHoldLocked(binding)
}

func (b *Broker) HasAnyRunExecutionIdentityHold() bool {
	b.mu.Lock()
	defer b.mu.Unlock()
	return b.runHold != nil
}

func (b *Broker) HasStartingExecutionIdentity(binding Binding, planID string) bool {
	b.mu.Lock()
	defer b.mu.Unlock()
	return b.runHold != nil && b.runHold.state == "STARTING" && b.runHold.binding == binding && b.runHold.planID == planID
}

func executionIdentityFromLease(value *lease) (ExecutionIdentity, error) {
	if value != nil && value.sshMode == SSHPassword && len(value.sshSecret) > 0 {
		return ExecutionIdentity{Mode: SSHPassword, Username: value.username, Generation: value.generation}, nil
	}
	if value == nil || value.sshMode != SSHPrivateKey || value.privateKeyPath == "" {
		return ExecutionIdentity{}, errors.New("EXECUTION_NODE_PEM_REQUIRED")
	}
	return ExecutionIdentity{Mode: SSHPrivateKey, Path: value.privateKeyPath, Username: value.username, Digest: sha256.Sum256(value.sshSecret), Generation: value.generation, FileInfo: value.privateKeyInfo}, nil
}

func sameExecutionIdentity(left, right ExecutionIdentity) bool {
	if left.Mode == SSHPassword || right.Mode == SSHPassword {
		return left.Mode == right.Mode && left.Username == right.Username && left.Generation == right.Generation && left.Generation != 0
	}
	return left.Path == right.Path && left.Username == right.Username && left.Digest == right.Digest && left.Generation == right.Generation && left.FileInfo != nil && right.FileInfo != nil && os.SameFile(left.FileInfo, right.FileInfo)
}

func (b *Broker) heldExecutionIdentityLocked(binding Binding) (ExecutionIdentity, bool) {
	hold := b.runHold
	if hold == nil || hold.binding != binding || hold.identity.Username == "" || hold.identity.Generation == 0 || (hold.identity.Mode != SSHPassword && (hold.identity.Path == "" || hold.identity.FileInfo == nil)) {
		return ExecutionIdentity{}, false
	}
	return hold.identity, true
}

func (b *Broker) hasRunHoldLocked(binding Binding) bool {
	return b.runHold != nil && b.runHold.binding == binding
}

func (b *Broker) clearRunHoldsLocked() {
	if b.runHold != nil {
		zero(b.runHold.password)
		zero(b.runHold.sudoPassword)
		clearExecutionIdentity(&b.runHold.identity)
		b.runHold = nil
	}
}

func clearExecutionIdentity(identity *ExecutionIdentity) {
	if identity == nil {
		return
	}
	identity.Path = ""
	identity.Mode = ""
	identity.Username = ""
	identity.Digest = [sha256.Size]byte{}
	identity.Generation = 0
	identity.FileInfo = nil
}

func readPrivateKey(path string) ([]byte, error) {
	value, _, err := readPrivateKeyWithInfo(path)
	return value, err
}

func readPrivateKeyWithInfo(path string) ([]byte, os.FileInfo, error) {
	info, err := os.Lstat(path)
	if err != nil {
		return nil, nil, errors.New("SESSION_PRIVATE_KEY_UNREADABLE")
	}
	if !info.Mode().IsRegular() || info.Mode()&os.ModeSymlink != 0 {
		return nil, nil, errors.New("SESSION_PRIVATE_KEY_NOT_REGULAR")
	}
	file, err := openPrivateKey(path)
	if err != nil {
		return nil, nil, errors.New("SESSION_PRIVATE_KEY_UNREADABLE")
	}
	defer file.Close()
	opened, err := file.Stat()
	if err != nil || !opened.Mode().IsRegular() || opened.Mode()&os.ModeSymlink != 0 || !os.SameFile(info, opened) {
		return nil, nil, errors.New("SESSION_PRIVATE_KEY_NOT_REGULAR")
	}
	contents, err := io.ReadAll(io.LimitReader(file, maxKeyBytes+1))
	if err != nil {
		return nil, nil, errors.New("SESSION_PRIVATE_KEY_UNREADABLE")
	}
	if len(contents) > maxKeyBytes {
		zero(contents)
		return nil, nil, errors.New("SESSION_CREDENTIAL_TOO_LARGE")
	}
	if err := validatePrivateKey(contents); err != nil {
		zero(contents)
		if errors.Is(err, errEncryptedPrivateKey) {
			return nil, nil, errors.New("SESSION_PRIVATE_KEY_ENCRYPTED_UNSUPPORTED")
		}
		return nil, nil, errors.New("SESSION_PRIVATE_KEY_INVALID")
	}
	return contents, opened, nil
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

func (b *Broker) armPendingExpiryLocked(generation uint64, expiresAt time.Time) {
	time.AfterFunc(time.Until(expiresAt), func() {
		b.mu.Lock()
		defer b.mu.Unlock()
		if b.pending != nil && b.pending.generation == generation && !b.now().Before(b.pending.expiresAt) {
			b.clearPendingLocked()
		}
	})
}

func (b *Broker) expireLocked(generation uint64) {
	if b.lease == nil || b.lease.generation != generation {
		return
	}
	binding, expiresAt := b.lease.binding, b.lease.expiresAt
	b.clearLeaseLocked(false)
	b.expired = &expiredMarker{binding: binding, expiresAt: expiresAt, generation: generation}
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
		zeroSecretMap(b.lease.runtimeSecretValues)
		zeroTypedSecretSlice(b.lease.runtimeSecretInputs)
		zeroTypedSecretSlice(b.lease.runtimeSecretInputs)
		b.lease = nil
	}
	if clearExpired {
		b.expired = nil
	}
}

func (b *Broker) clearPendingLocked() {
	if b.pending == nil {
		return
	}
	zeroSecretMap(b.pending.values)
	zeroTypedSecretMap(b.pending.typed)
	b.pending = nil
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

var runtimeSecretRequirementPattern = regexp.MustCompile(`^[a-z][a-z0-9-]{0,63}$`)

func runtimeSecretID(value string) bool { return runtimeSecretRequirementPattern.MatchString(value) }

func sameRuntimeSecretRequirements(requirements []string, values map[string]string) bool {
	if len(requirements) == 0 || len(requirements) != len(values) || len(requirements) > 16 {
		return false
	}
	seen := make(map[string]struct{}, len(requirements))
	for _, reference := range requirements {
		if !runtimeSecretID(reference) {
			return false
		}
		if _, duplicate := seen[reference]; duplicate {
			return false
		}
		seen[reference] = struct{}{}
		if _, present := values[reference]; !present {
			return false
		}
	}
	return validRuntimeSecretMapFromStrings(values)
}

func validRuntimeSecretMap(values map[string][]byte) bool {
	if len(values) == 0 || len(values) > 16 {
		return false
	}
	total := 0
	for reference, value := range values {
		if !runtimeSecretID(reference) || !utf8.Valid(value) || len(value) < 1 || len(value) > 4096 {
			return false
		}
		total += len(value)
		if total > 65536 {
			return false
		}
	}
	return true
}

func validRuntimeSecretMapFromStrings(values map[string]string) bool {
	if len(values) == 0 || len(values) > 16 {
		return false
	}
	total := 0
	for reference, value := range values {
		if !runtimeSecretID(reference) || !utf8.ValidString(value) || len([]byte(value)) < 1 || len([]byte(value)) > 4096 {
			return false
		}
		total += len([]byte(value))
		if total > 65536 {
			return false
		}
	}
	return true
}
func cloneSecretMap(value map[string][]byte) map[string][]byte {
	result := make(map[string][]byte, len(value))
	for key, item := range value {
		result[key] = append([]byte(nil), item...)
	}
	return result
}
func zeroSecretMap(value map[string][]byte) {
	for _, item := range value {
		zero(item)
	}
}

func cloneTypedSecretInput(value RuntimeSecretInput) RuntimeSecretInput {
	return RuntimeSecretInput{RequirementRef: value.RequirementRef, Purpose: value.Purpose, ServiceDeployment: value.ServiceDeployment,
		Operations: append([]string(nil), value.Operations...), Value: append([]byte(nil), value.Value...), Shares: cloneSecretSlices(value.Shares)}
}

func cloneSecretSlices(values [][]byte) [][]byte {
	result := make([][]byte, len(values))
	for i, value := range values {
		result[i] = append([]byte(nil), value...)
	}
	return result
}

func cloneTypedSecretSlice(values []RuntimeSecretInput) []RuntimeSecretInput {
	result := make([]RuntimeSecretInput, len(values))
	for i, value := range values {
		result[i] = cloneTypedSecretInput(value)
	}
	return result
}

func cloneTypedSecretMap(values map[string]RuntimeSecretInput) map[string]RuntimeSecretInput {
	if values == nil {
		return nil
	}
	result := make(map[string]RuntimeSecretInput, len(values))
	for key, value := range values {
		result[key] = cloneTypedSecretInput(value)
	}
	return result
}

func zeroTypedSecretSlice(values []RuntimeSecretInput) {
	for _, value := range values {
		zeroRuntimeSecretInput(value)
	}
}
func stringTrimSpace(value string) string { return strings.TrimSpace(value) }
