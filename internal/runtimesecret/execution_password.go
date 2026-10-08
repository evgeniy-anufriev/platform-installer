package runtimesecret

import "errors"

// HasExecutionSudoPassword returns only live credential metadata.
func (b *Broker) HasExecutionSudoPassword(binding Binding, identity ExecutionIdentity) bool {
	b.mu.Lock()
	defer b.mu.Unlock()
	if b.lease == nil || b.lease.binding != binding || !b.now().Before(b.lease.expiresAt) {
		return false
	}
	current, err := executionIdentityFromLease(b.lease)
	return err == nil && sameExecutionIdentity(current, identity) && len(b.lease.sudoSecret) != 0
}

// WithExecutionSudoPassword shares the existing exact-operation hold and wipe rules.
func (b *Broker) WithExecutionSudoPassword(binding Binding, identity ExecutionIdentity, planID, runID string, use func([]byte) error) error {
	if use == nil {
		return errors.New("SESSION_CREDENTIAL_UNAVAILABLE")
	}
	b.mu.Lock()
	var password []byte
	if b.lease != nil && b.lease.binding == binding && b.now().Before(b.lease.expiresAt) {
		current, err := executionIdentityFromLease(b.lease)
		if err == nil && sameExecutionIdentity(current, identity) {
			password = append([]byte(nil), b.lease.sudoSecret...)
		}
	} else if b.operationHoldLocked(binding, planID, runID) && sameExecutionIdentity(b.runHold.identity, identity) {
		password = append([]byte(nil), b.runHold.sudoPassword...)
	}
	b.mu.Unlock()
	if len(password) == 0 {
		return errors.New("SESSION_CREDENTIAL_UNAVAILABLE")
	}
	defer zero(password)
	return use(password)
}

// CurrentExecutionIdentityForOperation permits an expired password only for
// the exact already-reserved Start or confirmed run. Empty scope is live-only.
func (b *Broker) CurrentExecutionIdentityForOperation(binding Binding, planID, runID string) (ExecutionIdentity, error) {
	b.mu.Lock()
	defer b.mu.Unlock()
	if b.lease != nil && b.lease.binding == binding && b.now().Before(b.lease.expiresAt) {
		return executionIdentityFromLease(b.lease)
	}
	if b.operationHoldLocked(binding, planID, runID) {
		return b.runHold.identity, nil
	}
	return ExecutionIdentity{}, errors.New("SESSION_CREDENTIAL_UNAVAILABLE")
}

func (b *Broker) operationHoldLocked(binding Binding, planID, runID string) bool {
	h := b.runHold
	if h == nil || h.binding != binding {
		return false
	}
	return (h.state == "STARTING" && planID != "" && runID == "" && h.planID == planID) || (h.state == "RUNNING" && runID != "" && planID == "" && h.runID == runID)
}

// WithExecutionPassword never exposes other secrets or a password for another
// generation. The synchronous caller cannot retain the cleared byte slice.
func (b *Broker) WithExecutionPassword(binding Binding, identity ExecutionIdentity, planID, runID string, use func([]byte) error) error {
	if use == nil || identity.Mode != SSHPassword {
		return errors.New("SESSION_CREDENTIAL_UNAVAILABLE")
	}
	b.mu.Lock()
	var password []byte
	if b.lease != nil && b.lease.binding == binding && b.now().Before(b.lease.expiresAt) {
		current, err := executionIdentityFromLease(b.lease)
		if err == nil && sameExecutionIdentity(current, identity) {
			password = append([]byte(nil), b.lease.sshSecret...)
		}
	} else if b.operationHoldLocked(binding, planID, runID) && sameExecutionIdentity(b.runHold.identity, identity) {
		password = append([]byte(nil), b.runHold.password...)
	}
	b.mu.Unlock()
	if len(password) == 0 {
		return errors.New("SESSION_CREDENTIAL_UNAVAILABLE")
	}
	defer zero(password)
	return use(password)
}
