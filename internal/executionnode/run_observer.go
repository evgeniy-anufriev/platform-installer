package executionnode

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"
)

const (
	ObserverIntegrityFailure = "EXECUTION_OBSERVER_INTEGRITY_FAILURE"
	ObserverTransportFailure = "EXECUTION_OBSERVER_TRANSPORT_FAILURE"
	ObserverMirrorFailure    = "EXECUTION_OBSERVER_MIRROR_FAILURE"
	ObserverSubscriberSlow   = "EXECUTION_OBSERVER_SUBSCRIBER_OVERFLOW"
	ObserverHistoryTruncated = "EXECUTION_OBSERVER_HISTORY_TRUNCATED"
	ObserverCapacityExceeded = "EXECUTION_OBSERVER_CAPACITY_EXCEEDED"

	maxObservedRuns             = 32
	maxSubscribersPerRun        = 16
	maxAggregateSubscriberSlots = 16 * 1024
)

type ObserverError struct{ Code string }

func (e *ObserverError) Error() string { return e.Code }

type ObserverSubscription struct {
	NodeID       string
	RunID        string
	MirrorPath   string
	Events       <-chan ExecutionEvent
	Errors       <-chan error
	events       chan ExecutionEvent
	errors       chan error
	done         chan struct{}
	closeRequest sync.Once
	finishOnce   sync.Once
	remove       func()
	checkpoint   int
}

func (s *ObserverSubscription) Close() {
	if s != nil {
		s.closeRequest.Do(s.remove)
	}
}

func (s *ObserverSubscription) finish(err error) {
	s.finishOnce.Do(func() {
		if err != nil {
			for {
				select {
				case s.errors <- err:
					goto delivered
				default:
				}
				select {
				case <-s.errors:
				default:
					goto delivered
				}
			}
		}
	delivered:
		close(s.events)
		close(s.errors)
		close(s.done)
	})
}

type observedRun struct {
	stateMu          sync.Mutex
	key              observerRunKey
	node             Node
	runID            string
	ctx              context.Context
	cancel           context.CancelFunc
	mirror           *EventMirror
	last             int
	seen             map[int][]byte
	subs             map[uint64]*ObserverSubscription
	nextSub          uint64
	mirrorErr        error
	mirrorCheckpoint int
	mirrorVerified   bool
	earliestSequence int
	historyTruncated bool
}

type RunObserver struct {
	client       ExecutionClient
	runtimeRoot  string
	pollInterval time.Duration
	minBackoff   time.Duration
	maxBackoff   time.Duration
	mu           sync.Mutex
	runs         map[observerRunKey]*observedRun
}

type observerRunKey struct {
	nodeID        string
	address       string
	user          string
	port          uint16
	credentialRef string
	runID         string
}

func NewRunObserver(client ExecutionClient, runtimeRoot string) (*RunObserver, error) {
	if client == nil || runtimeRoot == "" {
		return nil, errors.New("EXECUTION_OBSERVER_INPUT_INVALID")
	}
	absolute, err := filepath.Abs(runtimeRoot)
	if err != nil {
		return nil, errors.New("EXECUTION_OBSERVER_INPUT_INVALID")
	}
	return &RunObserver{client: client, runtimeRoot: absolute, pollInterval: 500 * time.Millisecond, minBackoff: 250 * time.Millisecond, maxBackoff: 5 * time.Second, runs: map[observerRunKey]*observedRun{}}, nil
}

func (o *RunObserver) Observe(ctx context.Context, node Node, runID string) (*ObserverSubscription, error) {
	return o.SubscribeAfter(ctx, node, runID, 0, 256)
}

func (o *RunObserver) Subscribe(ctx context.Context, node Node, runID string, capacity int) (*ObserverSubscription, error) {
	return o.SubscribeAfter(ctx, node, runID, 0, capacity)
}

func (o *RunObserver) SubscribeAfter(ctx context.Context, node Node, runID string, after, capacity int) (*ObserverSubscription, error) {
	if ctx == nil || !validRuntimeToken(runID) || after < 0 || capacity < 1 || capacity > 4096 {
		return nil, errors.New("EXECUTION_OBSERVER_INPUT_INVALID")
	}
	key := observerKey(node, runID)
	o.mu.Lock()
	current := o.runs[key]
	startPoller := false
	if current == nil {
		if len(o.runs) >= maxObservedRuns {
			o.mu.Unlock()
			return nil, &ObserverError{Code: ObserverCapacityExceeded}
		}
		mirror, mirrorErr := OpenEventMirror(o.runtimeRoot, runID, nodeMirrorFingerprint(node))
		runContext, cancel := context.WithCancel(context.Background())
		current = &observedRun{key: key, node: node, runID: runID, ctx: runContext, cancel: cancel, mirror: mirror, seen: map[int][]byte{}, subs: map[uint64]*ObserverSubscription{}, mirrorErr: mirrorErr, mirrorVerified: true}
		if mirror != nil {
			current.last = mirror.LastSequence()
			current.seen = mirror.knownEvents()
			current.mirrorCheckpoint = current.last
			current.mirrorVerified = current.last == 0
		}
		o.runs[key] = current
		startPoller = true
	}
	if len(current.subs) >= maxSubscribersPerRun {
		o.mu.Unlock()
		return nil, &ObserverError{Code: ObserverCapacityExceeded}
	}
	current.stateMu.Lock()
	replayCount := 0
	for sequence := range current.seen {
		if sequence > after {
			replayCount++
		}
	}
	requestedSlots := replayCount + capacity
	if requestedSlots > 4096 {
		current.stateMu.Unlock()
		o.mu.Unlock()
		if startPoller {
			o.finish(current, nil)
		}
		return nil, errors.New("EXECUTION_OBSERVER_REPLAY_LIMIT")
	}
	if o.aggregateSubscriberSlotsLocked()+requestedSlots > maxAggregateSubscriberSlots {
		current.stateMu.Unlock()
		o.mu.Unlock()
		if startPoller {
			o.finish(current, nil)
		}
		return nil, &ObserverError{Code: ObserverCapacityExceeded}
	}
	events := make(chan ExecutionEvent, replayCount+capacity)
	errorsChannel := make(chan error, 4)
	mirrorPath := ""
	if current.mirrorErr == nil {
		mirrorPath, _ = EventMirrorPath(o.runtimeRoot, runID)
	}
	sub := &ObserverSubscription{NodeID: node.ID, RunID: runID, MirrorPath: mirrorPath, Events: events, Errors: errorsChannel, events: events, errors: errorsChannel, done: make(chan struct{}), checkpoint: after}
	id := current.nextSub
	current.nextSub++
	sub.remove = func() { o.removeSubscriber(key, current, id, sub) }
	if current.mirrorErr != nil {
		sub.errors <- &ObserverError{Code: ObserverMirrorFailure}
	}
	if current.historyTruncated && after < current.earliestSequence-1 {
		sub.errors <- &ObserverError{Code: ObserverHistoryTruncated}
	}
	if current.mirrorVerified {
		for _, sequence := range orderedSequences(current.seen, after, current.last) {
			encoded, ok := current.seen[sequence]
			if !ok {
				continue
			}
			var event ExecutionEvent
			if decodeCanonicalEvent(encoded, &event) {
				sub.events <- event
				sub.checkpoint = sequence
			}
		}
	}
	current.stateMu.Unlock()
	current.subs[id] = sub
	o.mu.Unlock()
	if startPoller {
		go o.poll(current)
	}
	go func() {
		select {
		case <-ctx.Done():
			sub.Close()
		case <-sub.done:
		}
	}()
	return sub, nil
}

func (o *RunObserver) aggregateSubscriberSlotsLocked() int {
	total := 0
	for _, current := range o.runs {
		for _, sub := range current.subs {
			total += cap(sub.events)
		}
	}
	return total
}

func nodeMirrorFingerprint(node Node) string {
	value := strings.Join([]string{node.ID, node.Address, node.User, strconv.Itoa(int(node.Port)), node.HostKey.Fingerprint}, "\x00")
	digest := sha256.Sum256([]byte(value))
	return "sha256:" + hex.EncodeToString(digest[:])
}

func (o *RunObserver) Replay(ctx context.Context, node Node, runID string, after int) ([]ExecutionEvent, error) {
	if ctx == nil || !validRuntimeToken(runID) || after < 0 {
		return nil, errors.New("EXECUTION_OBSERVER_INPUT_INVALID")
	}
	result := []ExecutionEvent{}
	last := after
	seen := map[int][]byte{}
	historyTruncated := false
	for {
		page, err := o.client.GetEvents(ctx, node, runID, last, ExecutionEventPageLimit)
		if err != nil {
			if errors.Is(err, errExecutionEventsResponseInvalid) || errors.Is(err, errExecutionEventResponseInvalid) {
				return nil, &ObserverError{Code: ObserverIntegrityFailure}
			}
			return nil, err
		}
		accepted, next, err := validateObserverPage(page, runID, last, seen)
		if err != nil {
			return nil, err
		}
		result = append(result, accepted...)
		historyTruncated = historyTruncated || page.HistoryTruncated
		last = next
		if !page.HasMore {
			if historyTruncated {
				return result, &ObserverError{Code: ObserverHistoryTruncated}
			}
			return result, nil
		}
	}
}

func (o *RunObserver) Stop(node Node, runID string) {
	key := observerKey(node, runID)
	o.mu.Lock()
	if current := o.runs[key]; current != nil {
		current.cancel()
	}
	o.mu.Unlock()
}

func (o *RunObserver) removeSubscriber(key observerRunKey, current *observedRun, id uint64, sub *ObserverSubscription) {
	o.mu.Lock()
	if o.runs[key] == current {
		delete(current.subs, id)
		if len(current.subs) == 0 {
			current.cancel()
		}
	}
	o.mu.Unlock()
	sub.finish(nil)
}

func (o *RunObserver) poll(current *observedRun) {
	backoff := o.minBackoff
	for {
		current.stateMu.Lock()
		after := current.last
		if !current.mirrorVerified && current.mirrorCheckpoint > 0 {
			after = current.mirrorCheckpoint - 1
		}
		current.stateMu.Unlock()
		page, err := o.client.GetEvents(current.ctx, current.node, current.runID, after, ExecutionEventPageLimit)
		if err != nil {
			if current.ctx.Err() != nil {
				o.finish(current, nil)
				return
			}
			if errors.Is(err, errExecutionEventsResponseInvalid) || errors.Is(err, errExecutionEventResponseInvalid) {
				o.finish(current, &ObserverError{Code: ObserverIntegrityFailure})
				return
			}
			o.notify(current, &ObserverError{Code: ObserverTransportFailure})
			if !waitObserver(current.ctx, backoff) {
				o.finish(current, nil)
				return
			}
			backoff *= 2
			if backoff > o.maxBackoff {
				backoff = o.maxBackoff
			}
			continue
		}
		backoff = o.minBackoff
		current.stateMu.Lock()
		accepted, next, validationErr := validateObserverPage(page, current.runID, current.last, current.seen)
		if page.HistoryTruncated {
			current.historyTruncated = true
			current.earliestSequence = page.EarliestSequence
		}
		mirrorMismatch := false
		verifiedMirror := false
		if !current.mirrorVerified && current.mirrorCheckpoint > 0 {
			checkpoint := current.mirrorCheckpoint
			remoteCheckpointMatches := len(page.Events) > 0 && page.Events[0].Sequence == checkpoint
			if remoteCheckpointMatches {
				encoded, encodeErr := canonicalEvent(page.Events[0])
				remoteCheckpointMatches = encodeErr == nil && bytes.Equal(current.seen[checkpoint], encoded)
			}
			if validationErr != nil || !remoteCheckpointMatches {
				mirrorMismatch = true
			} else {
				current.mirrorVerified = true
				verifiedMirror = true
			}
		}
		current.stateMu.Unlock()
		if mirrorMismatch {
			o.resetUnverifiedMirror(current)
			continue
		}
		if verifiedMirror {
			o.publishMirroredHistory(current, current.mirrorCheckpoint)
		}
		if validationErr != nil {
			o.finish(current, validationErr)
			return
		}
		if page.HistoryTruncated {
			o.notify(current, &ObserverError{Code: ObserverHistoryTruncated})
		}
		for _, event := range accepted {
			if current.mirror != nil {
				if _, mirrorErr := current.mirror.Append(event); mirrorErr != nil {
					_ = current.mirror.Close()
					current.mirror = nil
					current.stateMu.Lock()
					current.mirrorErr = mirrorErr
					current.stateMu.Unlock()
					o.notify(current, &ObserverError{Code: ObserverMirrorFailure})
				}
			}
			current.stateMu.Lock()
			current.last = event.Sequence
			encoded, _ := canonicalEvent(event)
			current.seen[event.Sequence] = encoded
			current.stateMu.Unlock()
			o.publish(current, event)
		}
		current.stateMu.Lock()
		current.last = next
		current.stateMu.Unlock()
		if page.HasMore {
			continue
		}
		run, runErr := o.client.GetExecution(current.ctx, current.node, current.runID)
		if runErr != nil {
			o.notify(current, &ObserverError{Code: ObserverTransportFailure})
			if !waitObserver(current.ctx, backoff) {
				o.finish(current, nil)
				return
			}
			backoff *= 2
			if backoff > o.maxBackoff {
				backoff = o.maxBackoff
			}
			continue
		}
		backoff = o.minBackoff
		current.stateMu.Lock()
		last := current.last
		current.stateMu.Unlock()
		if run.RunID != "" && run.RunID != current.runID || run.Sequence < last {
			o.finish(current, &ObserverError{Code: ObserverIntegrityFailure})
			return
		}
		if terminalExecutionState(run.State) {
			if run.Sequence > last {
				continue
			}
			o.finish(current, nil)
			return
		}
		if !waitObserver(current.ctx, o.pollInterval) {
			o.finish(current, nil)
			return
		}
	}
}

func validateObserverPage(page ExecutionEventPage, runID string, last int, seen map[int][]byte) ([]ExecutionEvent, int, error) {
	accepted := make([]ExecutionEvent, 0, len(page.Events))
	next := last
	if page.HistoryTruncated {
		if page.EarliestSequence <= last+1 {
			return nil, last, &ObserverError{Code: ObserverIntegrityFailure}
		}
		next = page.EarliestSequence - 1
	}
	for _, event := range page.Events {
		if validateExecutionEvent(event, runID) != nil {
			return nil, last, &ObserverError{Code: ObserverIntegrityFailure}
		}
		encoded, _ := canonicalEvent(event)
		if event.Sequence <= next {
			if prior, ok := seen[event.Sequence]; ok && bytes.Equal(prior, encoded) {
				continue
			}
			return nil, last, &ObserverError{Code: ObserverIntegrityFailure}
		}
		if event.Sequence != next+1 {
			return nil, last, &ObserverError{Code: ObserverIntegrityFailure}
		}
		if len(seen) >= maxObservedExecutionEvents {
			return nil, last, &ObserverError{Code: ObserverIntegrityFailure}
		}
		accepted = append(accepted, event)
		seen[event.Sequence] = encoded
		next = event.Sequence
	}
	if page.NextSequence != next || page.HasMore && len(page.Events) == 0 {
		return nil, last, &ObserverError{Code: ObserverIntegrityFailure}
	}
	return accepted, next, nil
}

func (o *RunObserver) publish(current *observedRun, event ExecutionEvent) {
	o.mu.Lock()
	overflow := []*ObserverSubscription{}
	if o.runs[current.key] == current {
		for id, sub := range current.subs {
			if event.Sequence <= sub.checkpoint {
				continue
			}
			select {
			case sub.events <- event:
				sub.checkpoint = event.Sequence
			default:
				delete(current.subs, id)
				overflow = append(overflow, sub)
			}
		}
		if len(current.subs) == 0 {
			current.cancel()
		}
	}
	o.mu.Unlock()
	for _, sub := range overflow {
		sub.finish(&ObserverError{Code: ObserverSubscriberSlow})
	}
}

func (o *RunObserver) publishMirroredHistory(current *observedRun, through int) {
	current.stateMu.Lock()
	history := make(map[int][]byte, len(current.seen))
	for sequence, encoded := range current.seen {
		if sequence <= through {
			history[sequence] = append([]byte(nil), encoded...)
		}
	}
	current.stateMu.Unlock()
	for _, sequence := range orderedSequences(history, 0, through) {
		encoded, ok := history[sequence]
		if !ok {
			continue
		}
		var event ExecutionEvent
		if decodeCanonicalEvent(encoded, &event) {
			o.publish(current, event)
		}
	}
}

func orderedSequences(events map[int][]byte, after, through int) []int {
	result := make([]int, 0, len(events))
	for sequence := range events {
		if sequence > after && sequence <= through {
			result = append(result, sequence)
		}
	}
	sort.Ints(result)
	return result
}

func (o *RunObserver) resetUnverifiedMirror(current *observedRun) {
	current.stateMu.Lock()
	if current.mirror != nil {
		if err := current.mirror.Reset(); err != nil {
			_ = current.mirror.Close()
			current.mirror = nil
		}
	}
	current.last = 0
	current.seen = map[int][]byte{}
	current.mirrorCheckpoint = 0
	current.mirrorVerified = true
	current.earliestSequence = 0
	current.historyTruncated = false
	current.stateMu.Unlock()
	o.notify(current, &ObserverError{Code: ObserverMirrorFailure})
}

func decodeCanonicalEvent(encoded []byte, event *ExecutionEvent) bool {
	return json.Unmarshal(encoded, event) == nil
}

func (o *RunObserver) notify(current *observedRun, err error) {
	o.mu.Lock()
	if o.runs[current.key] == current {
		for _, sub := range current.subs {
			select {
			case sub.errors <- err:
			default:
			}
		}
	}
	o.mu.Unlock()
}

func (o *RunObserver) finish(current *observedRun, err error) {
	o.mu.Lock()
	if o.runs[current.key] == current {
		delete(o.runs, current.key)
	}
	subs := make([]*ObserverSubscription, 0, len(current.subs))
	for id, sub := range current.subs {
		delete(current.subs, id)
		subs = append(subs, sub)
	}
	o.mu.Unlock()
	current.cancel()
	if current.mirror != nil {
		_ = current.mirror.Close()
	}
	for _, sub := range subs {
		sub.finish(err)
	}
}

func observerKey(node Node, runID string) observerRunKey {
	return observerRunKey{nodeID: node.ID, address: node.Address, user: node.User, port: node.Port, credentialRef: node.CredentialRef, runID: runID}
}

func terminalExecutionState(state string) bool {
	switch state {
	case "SUCCEEDED", "FAILED", "CANCELLED", "INTERRUPTED", "CORRUPT_ORPHANED":
		return true
	default:
		return false
	}
}

func waitObserver(ctx context.Context, duration time.Duration) bool {
	timer := time.NewTimer(duration)
	defer timer.Stop()
	select {
	case <-ctx.Done():
		return false
	case <-timer.C:
		return true
	}
}
