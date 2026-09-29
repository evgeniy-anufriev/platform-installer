package executionnode

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"runtime"
	"strconv"
	"sync"
	"testing"
	"time"
)

type observerClient struct {
	mu             sync.Mutex
	events         []ExecutionEvent
	pageSize       int
	failures       int
	getEventsCalls int
	afters         []int
	activeCalls    int
	maxActiveCalls int
	blockFirst     chan struct{}
	blocked        bool
	state          string
}

func (c *observerClient) StartExecution(context.Context, Node, ExecutionStartRequest) (ExecutionRun, error) {
	return ExecutionRun{}, nil
}

func (c *observerClient) CancelExecution(context.Context, Node, string) (ExecutionRun, error) {
	return ExecutionRun{}, nil
}

func (c *observerClient) GetExecution(_ context.Context, _ Node, runID string) (ExecutionRun, error) {
	c.mu.Lock()
	defer c.mu.Unlock()
	return ExecutionRun{RunID: runID, State: c.state, Sequence: len(c.events)}, nil
}

func (c *observerClient) GetEvents(ctx context.Context, _ Node, _ string, after, limit int) (ExecutionEventPage, error) {
	c.mu.Lock()
	c.getEventsCalls++
	c.afters = append(c.afters, after)
	c.activeCalls++
	if c.activeCalls > c.maxActiveCalls {
		c.maxActiveCalls = c.activeCalls
	}
	if c.failures > 0 {
		c.failures--
		c.activeCalls--
		c.mu.Unlock()
		return ExecutionEventPage{}, errors.New("transport unavailable")
	}
	block := c.blockFirst
	if block != nil && !c.blocked {
		c.blocked = true
	} else {
		block = nil
	}
	c.mu.Unlock()
	if block != nil {
		select {
		case <-block:
		case <-ctx.Done():
		}
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	c.activeCalls--
	pageSize := c.pageSize
	if pageSize < 1 || pageSize > limit {
		pageSize = limit
	}
	selected := []ExecutionEvent{}
	for _, event := range c.events {
		if event.Sequence > after && len(selected) < pageSize {
			selected = append(selected, event)
		}
	}
	next := after
	if len(selected) > 0 {
		next = selected[len(selected)-1].Sequence
	}
	return ExecutionEventPage{Events: selected, NextSequence: next, HasMore: next < len(c.events)}, nil
}

func eventSeries(runID string, count int) []ExecutionEvent {
	result := make([]ExecutionEvent, count)
	for index := range result {
		result[index] = validEvent(runID, index+1)
	}
	return result
}

func observerForTest(t *testing.T, client ExecutionClient, root string) *RunObserver {
	t.Helper()
	observer, err := NewRunObserver(client, root)
	if err != nil {
		t.Fatal(err)
	}
	observer.pollInterval = time.Millisecond
	observer.minBackoff = time.Millisecond
	observer.maxBackoff = 4 * time.Millisecond
	return observer
}

func TestRunObserverBoundsActiveRunsAndSubscribers(t *testing.T) {
	client := &observerClient{}
	observer := observerForTest(t, client, t.TempDir())
	subscriptions := make([]*ObserverSubscription, 0, maxObservedRuns)
	for index := 0; index < maxObservedRuns; index++ {
		sub, err := observer.Observe(context.Background(), Node{ID: "node"}, "installer-"+strconv.Itoa(1000+index))
		if err != nil {
			t.Fatalf("observe run %d: %v", index, err)
		}
		subscriptions = append(subscriptions, sub)
	}
	if _, err := observer.Observe(context.Background(), Node{ID: "node"}, "installer-9999"); observerErrorCode(err) != ObserverCapacityExceeded {
		t.Fatalf("active run limit error=%v", err)
	}
	for _, sub := range subscriptions {
		sub.Close()
	}

	observer = observerForTest(t, client, t.TempDir())
	subscriptions = subscriptions[:0]
	for index := 0; index < maxSubscribersPerRun; index++ {
		sub, err := observer.Subscribe(context.Background(), Node{ID: "node"}, "installer-2000", 1)
		if err != nil {
			t.Fatalf("subscribe %d: %v", index, err)
		}
		subscriptions = append(subscriptions, sub)
	}
	if _, err := observer.Subscribe(context.Background(), Node{ID: "node"}, "installer-2000", 1); observerErrorCode(err) != ObserverCapacityExceeded {
		t.Fatalf("subscriber limit error=%v", err)
	}
	for _, sub := range subscriptions {
		sub.Close()
	}
}

func TestRunObserverBoundsAggregateSubscriberBuffers(t *testing.T) {
	observer := observerForTest(t, &observerClient{}, t.TempDir())
	subscriptions := make([]*ObserverSubscription, 0, maxAggregateSubscriberSlots/4096)
	for index := 0; index < maxAggregateSubscriberSlots/4096; index++ {
		sub, err := observer.Subscribe(context.Background(), Node{ID: "node"}, "installer-"+strconv.Itoa(3000+index), 4096)
		if err != nil {
			t.Fatalf("subscribe %d: %v", index, err)
		}
		subscriptions = append(subscriptions, sub)
	}
	if _, err := observer.Subscribe(context.Background(), Node{ID: "node"}, "installer-3999", 1); observerErrorCode(err) != ObserverCapacityExceeded {
		t.Fatalf("aggregate limit error=%v", err)
	}
	for _, sub := range subscriptions {
		sub.Close()
	}
}

func observerErrorCode(err error) string {
	var observerErr *ObserverError
	if errors.As(err, &observerErr) {
		return observerErr.Code
	}
	return ""
}

func collectSubscription(t *testing.T, sub *ObserverSubscription) ([]ExecutionEvent, []error) {
	t.Helper()
	events, reported := []ExecutionEvent{}, []error{}
	timeout := time.After(3 * time.Second)
	for sub.Events != nil || sub.Errors != nil {
		select {
		case event, ok := <-sub.Events:
			if !ok {
				sub.Events = nil
			} else {
				events = append(events, event)
			}
		case err, ok := <-sub.Errors:
			if !ok {
				sub.Errors = nil
			} else {
				reported = append(reported, err)
			}
		case <-timeout:
			t.Fatal("observer did not terminate")
		}
	}
	return events, reported
}

func TestRunObserverUsesOnePollerDrainsPagesAndMirrors(t *testing.T) {
	runID := "installer-200"
	block := make(chan struct{})
	client := &observerClient{events: eventSeries(runID, 5), pageSize: 2, blockFirst: block, state: "SUCCEEDED"}
	root := t.TempDir()
	observer := observerForTest(t, client, root)
	first, err := observer.Subscribe(context.Background(), Node{ID: "execution", Address: "192.0.2.1"}, runID, 16)
	if err != nil {
		t.Fatal(err)
	}
	second, err := observer.Subscribe(context.Background(), Node{ID: "execution", Address: "192.0.2.1"}, runID, 16)
	if err != nil {
		t.Fatal(err)
	}
	if first.RunID != runID || first.NodeID != "execution" || first.MirrorPath != filepath.Join(root, "executions", runID, "events.jsonl") {
		t.Fatalf("subscription identity=%+v", first)
	}
	close(block)
	firstEvents, firstErrors := collectSubscription(t, first)
	secondEvents, secondErrors := collectSubscription(t, second)
	if len(firstEvents) != 5 || len(secondEvents) != 5 || len(firstErrors) != 0 || len(secondErrors) != 0 {
		t.Fatalf("first=%d/%v second=%d/%v", len(firstEvents), firstErrors, len(secondEvents), secondErrors)
	}
	client.mu.Lock()
	if client.maxActiveCalls != 1 || client.getEventsCalls != 3 {
		t.Fatalf("active=%d calls=%d", client.maxActiveCalls, client.getEventsCalls)
	}
	client.mu.Unlock()
	mirror, err := OpenEventMirror(root, runID, nodeMirrorFingerprint(Node{ID: "execution", Address: "192.0.2.1"}))
	if err != nil {
		t.Fatal(err)
	}
	defer mirror.Close()
	if mirror.LastSequence() != 5 || len(mirror.Events(0)) != 5 {
		t.Fatalf("mirror last=%d events=%d", mirror.LastSequence(), len(mirror.Events(0)))
	}
}

func TestRunObserverReconnectsAfterTransportFailure(t *testing.T) {
	runID := "installer-201"
	client := &observerClient{events: eventSeries(runID, 2), pageSize: 1, failures: 1, state: "SUCCEEDED"}
	observer := observerForTest(t, client, t.TempDir())
	sub, err := observer.Observe(context.Background(), Node{ID: "node"}, runID)
	if err != nil {
		t.Fatal(err)
	}
	events, reported := collectSubscription(t, sub)
	if len(events) != 2 || len(reported) == 0 || reported[0].Error() != ObserverTransportFailure {
		t.Fatalf("events=%d errors=%v", len(events), reported)
	}
}

func TestRunObserverRestartResumesFromLastMirroredSequence(t *testing.T) {
	runID := "installer-205"
	root := t.TempDir()
	firstClient := &observerClient{events: eventSeries(runID, 2), pageSize: 2, state: "SUCCEEDED"}
	firstObserver := observerForTest(t, firstClient, root)
	first, _ := firstObserver.Observe(context.Background(), Node{ID: "node"}, runID)
	firstEvents, firstErrors := collectSubscription(t, first)
	if len(firstEvents) != 2 || len(firstErrors) != 0 {
		t.Fatalf("first events=%d errors=%v", len(firstEvents), firstErrors)
	}

	secondClient := &observerClient{events: eventSeries(runID, 4), pageSize: 2, state: "SUCCEEDED"}
	secondObserver := observerForTest(t, secondClient, root)
	second, _ := secondObserver.SubscribeAfter(context.Background(), Node{ID: "node"}, runID, 2, 256)
	secondEvents, secondErrors := collectSubscription(t, second)
	if len(secondEvents) != 2 || secondEvents[0].Sequence != 3 || secondEvents[1].Sequence != 4 || len(secondErrors) != 0 {
		t.Fatalf("second events=%v errors=%v", secondEvents, secondErrors)
	}
	secondClient.mu.Lock()
	defer secondClient.mu.Unlock()
	if len(secondClient.afters) == 0 || secondClient.afters[0] != 1 {
		t.Fatalf("resume after=%v", secondClient.afters)
	}
}

type fixedPageClient struct {
	page ExecutionEventPage
	run  ExecutionRun
}

func (c *fixedPageClient) StartExecution(context.Context, Node, ExecutionStartRequest) (ExecutionRun, error) {
	return ExecutionRun{}, nil
}
func (c *fixedPageClient) CancelExecution(context.Context, Node, string) (ExecutionRun, error) {
	return ExecutionRun{}, nil
}
func (c *fixedPageClient) GetExecution(context.Context, Node, string) (ExecutionRun, error) {
	return c.run, nil
}
func (c *fixedPageClient) GetEvents(context.Context, Node, string, int, int) (ExecutionEventPage, error) {
	return c.page, nil
}

func TestRunObserverRejectsGapAndConflictingDuplicate(t *testing.T) {
	runID := "installer-202"
	gap := &fixedPageClient{page: ExecutionEventPage{Events: []ExecutionEvent{validEvent(runID, 2)}, NextSequence: 2}, run: ExecutionRun{RunID: runID, State: "SUCCEEDED", Sequence: 2}}
	observer := observerForTest(t, gap, t.TempDir())
	sub, _ := observer.Observe(context.Background(), Node{ID: "node"}, runID)
	_, reported := collectSubscription(t, sub)
	if len(reported) != 1 || reported[0].Error() != ObserverIntegrityFailure {
		t.Fatalf("gap errors=%v", reported)
	}

	seen := map[int][]byte{}
	first := validEvent(runID, 1)
	encoded, _ := canonicalEvent(first)
	seen[1] = encoded
	conflict := first
	conflict.Status = "FAILED"
	if _, _, err := validateObserverPage(ExecutionEventPage{Events: []ExecutionEvent{conflict}, NextSequence: 1}, runID, 1, seen); err == nil || err.Error() != ObserverIntegrityFailure {
		t.Fatalf("duplicate err=%v", err)
	}
	accepted, next, err := validateObserverPage(ExecutionEventPage{Events: []ExecutionEvent{first}, NextSequence: 1}, runID, 1, seen)
	if err != nil || len(accepted) != 0 || next != 1 {
		t.Fatalf("identical duplicate accepted=%v next=%d err=%v", accepted, next, err)
	}
}

func TestRunObserverReplayDrainsAllPages(t *testing.T) {
	runID := "installer-206"
	client := &observerClient{events: eventSeries(runID, 5), pageSize: 2, state: "RUNNING"}
	observer := observerForTest(t, client, t.TempDir())
	events, err := observer.Replay(context.Background(), Node{ID: "node"}, runID, 0)
	if err != nil || len(events) != 5 || events[4].Sequence != 5 {
		t.Fatalf("events=%v err=%v", events, err)
	}
}

func TestRunObserverStopsWhenLastConsumerCloses(t *testing.T) {
	runID := "installer-207"
	client := &observerClient{events: nil, state: "RUNNING"}
	observer := observerForTest(t, client, t.TempDir())
	sub, err := observer.Observe(context.Background(), Node{ID: "node"}, runID)
	if err != nil {
		t.Fatal(err)
	}
	sub.Close()
	deadline := time.Now().Add(time.Second)
	for time.Now().Before(deadline) {
		observer.mu.Lock()
		count := len(observer.runs)
		observer.mu.Unlock()
		if count == 0 {
			return
		}
		time.Sleep(time.Millisecond)
	}
	t.Fatal("poller remained after last consumer closed")
}

func TestRunObserverDropsSlowSubscriberWithoutStoppingPolling(t *testing.T) {
	runID := "installer-203"
	client := &observerClient{events: eventSeries(runID, 4), pageSize: 4, state: "SUCCEEDED"}
	observer := observerForTest(t, client, t.TempDir())
	sub, _ := observer.Subscribe(context.Background(), Node{ID: "node"}, runID, 1)
	time.Sleep(30 * time.Millisecond)
	var overflow error
	for err := range sub.Errors {
		overflow = err
	}
	if overflow == nil || overflow.Error() != ObserverSubscriberSlow {
		t.Fatalf("overflow=%v", overflow)
	}
	client.mu.Lock()
	calls := client.getEventsCalls
	client.mu.Unlock()
	if calls == 0 {
		t.Fatal("poller did not run")
	}
}

func TestRunObserverMirrorFailureStillDeliversTypedEvents(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("symlink creation is environment-dependent on Windows")
	}
	parent := t.TempDir()
	root := filepath.Join(parent, "runtime-link")
	if err := os.Symlink(t.TempDir(), root); err != nil {
		t.Fatal(err)
	}
	runID := "installer-204"
	client := &observerClient{events: eventSeries(runID, 1), pageSize: 1, state: "SUCCEEDED"}
	observer := observerForTest(t, client, root)
	sub, _ := observer.Observe(context.Background(), Node{ID: "node"}, runID)
	events, reported := collectSubscription(t, sub)
	if len(events) != 1 || len(reported) == 0 || reported[0].Error() != ObserverMirrorFailure {
		t.Fatalf("events=%d errors=%v", len(events), reported)
	}
}

func TestObserverTerminalErrorReplacesBufferedTransientError(t *testing.T) {
	events := make(chan ExecutionEvent)
	reported := make(chan error, 1)
	reported <- &ObserverError{Code: ObserverTransportFailure}
	sub := &ObserverSubscription{Events: events, Errors: reported, events: events, errors: reported, done: make(chan struct{})}
	sub.finish(&ObserverError{Code: ObserverIntegrityFailure})
	values := []error{}
	for err := range sub.Errors {
		values = append(values, err)
	}
	if len(values) != 1 || values[0].Error() != ObserverIntegrityFailure {
		t.Fatalf("terminal error was lost: %v", values)
	}
}

func TestRunObserverValidatesLocalCheckpointAgainstRemoteAuthority(t *testing.T) {
	runID := "installer-208"
	root := t.TempDir()
	mirror, err := OpenEventMirror(root, runID, nodeMirrorFingerprint(Node{ID: "node"}))
	if err != nil {
		t.Fatal(err)
	}
	local := validEvent(runID, 1)
	if _, err := mirror.Append(local); err != nil {
		t.Fatal(err)
	}
	if err := mirror.Close(); err != nil {
		t.Fatal(err)
	}
	remote := local
	remote.Status = "FAILED"
	client := &observerClient{events: []ExecutionEvent{remote}, pageSize: 1, state: "SUCCEEDED"}
	observer := observerForTest(t, client, root)
	sub, err := observer.Observe(context.Background(), Node{ID: "node"}, runID)
	if err != nil {
		t.Fatal(err)
	}
	events, reported := collectSubscription(t, sub)
	if len(events) != 1 || events[0].Status != "FAILED" {
		t.Fatalf("remote authority was not replayed: %+v", events)
	}
	foundMirrorError := false
	for _, observerErr := range reported {
		foundMirrorError = foundMirrorError || observerErr.Error() == ObserverMirrorFailure
	}
	if !foundMirrorError {
		t.Fatalf("mirror mismatch was not reported: %v", reported)
	}
	recovered, err := OpenEventMirror(root, runID, nodeMirrorFingerprint(Node{ID: "node"}))
	if err != nil {
		t.Fatal(err)
	}
	defer recovered.Close()
	if values := recovered.Events(0); len(values) != 1 || values[0].Status != "FAILED" {
		t.Fatalf("mirror was not rebuilt from remote: %+v", values)
	}
}

func TestSubscribeAfterAtomicallyReplaysCacheThenLiveEvents(t *testing.T) {
	runID := "installer-209"
	client := &observerClient{events: eventSeries(runID, 3), pageSize: 3, state: "RUNNING"}
	observer := observerForTest(t, client, t.TempDir())
	first, err := observer.Observe(context.Background(), Node{ID: "node"}, runID)
	if err != nil {
		t.Fatal(err)
	}
	defer first.Close()
	deadline := time.Now().Add(time.Second)
	for {
		observer.mu.Lock()
		current := observer.runs[observerKey(Node{ID: "node"}, runID)]
		observer.mu.Unlock()
		last := 0
		if current != nil {
			current.stateMu.Lock()
			last = current.last
			current.stateMu.Unlock()
		}
		if last == 3 {
			break
		}
		if time.Now().After(deadline) {
			t.Fatal("observer did not cache initial events")
		}
		time.Sleep(time.Millisecond)
	}
	second, err := observer.SubscribeAfter(context.Background(), Node{ID: "node"}, runID, 1, 8)
	if err != nil {
		t.Fatal(err)
	}
	client.mu.Lock()
	client.events = eventSeries(runID, 4)
	client.state = "SUCCEEDED"
	client.mu.Unlock()
	events, reported := collectSubscription(t, second)
	if len(reported) != 0 || len(events) != 3 || events[0].Sequence != 2 || events[1].Sequence != 3 || events[2].Sequence != 4 {
		t.Fatalf("events=%v errors=%v", events, reported)
	}
}

func TestObserverAcceptsExplicitlyTruncatedHistory(t *testing.T) {
	runID := "installer-210"
	page := ExecutionEventPage{Events: []ExecutionEvent{validEvent(runID, 5)}, NextSequence: 5, EarliestSequence: 5, HistoryTruncated: true}
	accepted, next, err := validateObserverPage(page, runID, 0, map[int][]byte{})
	if err != nil || len(accepted) != 1 || next != 5 {
		t.Fatalf("accepted=%v next=%d err=%v", accepted, next, err)
	}
}

func TestReplayReturnsExplicitHistoryTruncationWithAvailableEvents(t *testing.T) {
	runID := "installer-211"
	client := &fixedPageClient{page: ExecutionEventPage{Events: []ExecutionEvent{validEvent(runID, 5)}, NextSequence: 5, EarliestSequence: 5, HistoryTruncated: true}}
	observer := observerForTest(t, client, t.TempDir())
	events, err := observer.Replay(context.Background(), Node{ID: "node"}, runID, 0)
	if len(events) != 1 || events[0].Sequence != 5 || err == nil || err.Error() != ObserverHistoryTruncated {
		t.Fatalf("events=%v err=%v", events, err)
	}
}

func TestLateSubscriberReceivesCachedHistoryTruncationDiagnostic(t *testing.T) {
	runID := "installer-212"
	event := validEvent(runID, 5)
	encoded, _ := canonicalEvent(event)
	ctx, cancel := context.WithCancel(context.Background())
	current := &observedRun{key: observerKey(Node{ID: "node"}, runID), node: Node{ID: "node"}, runID: runID, ctx: ctx, cancel: cancel, seen: map[int][]byte{5: encoded}, subs: map[uint64]*ObserverSubscription{}, last: 5, mirrorVerified: true, earliestSequence: 5, historyTruncated: true}
	observer := observerForTest(t, &observerClient{}, t.TempDir())
	observer.runs[current.key] = current
	sub, err := observer.SubscribeAfter(context.Background(), current.node, runID, 0, 8)
	if err != nil {
		t.Fatal(err)
	}
	defer sub.Close()
	select {
	case observerErr := <-sub.Errors:
		if observerErr == nil || observerErr.Error() != ObserverHistoryTruncated {
			t.Fatalf("error=%v", observerErr)
		}
	case <-time.After(time.Second):
		t.Fatal("history truncation was not reported")
	}
	select {
	case replayed := <-sub.Events:
		if replayed.Sequence != 5 {
			t.Fatalf("event=%+v", replayed)
		}
	case <-time.After(time.Second):
		t.Fatal("available history was not replayed")
	}
}

func TestObserverRejectsMoreThanRemoteJournalCapacity(t *testing.T) {
	runID := "installer-213"
	seen := make(map[int][]byte, maxObservedExecutionEvents)
	for sequence := 1; sequence <= maxObservedExecutionEvents; sequence++ {
		encoded, _ := canonicalEvent(validEvent(runID, sequence))
		seen[sequence] = encoded
	}
	page := ExecutionEventPage{Events: []ExecutionEvent{validEvent(runID, maxObservedExecutionEvents+1)}, NextSequence: maxObservedExecutionEvents + 1}
	if _, _, err := validateObserverPage(page, runID, maxObservedExecutionEvents, seen); err == nil || err.Error() != ObserverIntegrityFailure {
		t.Fatalf("capacity err=%v", err)
	}
}

func TestObserverAcceptsEventsPastPreviousInstallerLimit(t *testing.T) {
	runID := "installer-214"
	const previousInstallerLimit = 2048
	seen := make(map[int][]byte, previousInstallerLimit)
	for sequence := 1; sequence <= previousInstallerLimit; sequence++ {
		encoded, _ := canonicalEvent(validEvent(runID, sequence))
		seen[sequence] = encoded
	}
	page := ExecutionEventPage{Events: []ExecutionEvent{validEvent(runID, previousInstallerLimit+1)}, NextSequence: previousInstallerLimit + 1}
	accepted, next, err := validateObserverPage(page, runID, previousInstallerLimit, seen)
	if err != nil || len(accepted) != 1 || accepted[0].Sequence != previousInstallerLimit+1 || next != previousInstallerLimit+1 {
		t.Fatalf("accepted=%d next=%d err=%v", len(accepted), next, err)
	}
}
