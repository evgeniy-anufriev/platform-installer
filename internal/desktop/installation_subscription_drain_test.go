package desktop

import (
	"context"
	"testing"
	"time"

	"platform-installer/internal/executionnode"
)

type subscriptionDrainPublisher struct {
	values []InstallationSubscriptionEvent
}

func (p *subscriptionDrainPublisher) Publish(_ context.Context, _ string, value any) {
	p.values = append(p.values, value.(InstallationSubscriptionEvent))
}

func TestInstallationSubscriptionDrainsClosedChannels(t *testing.T) {
	for attempt := 0; attempt < 100; attempt++ {
		events := make(chan executionnode.ExecutionEvent, 3)
		diagnostics := make(chan error, 1)
		for sequence := 10363; sequence <= 10365; sequence++ {
			events <- executionnode.ExecutionEvent{RunID: "installer-final", Sequence: sequence, Status: "SUCCESS"}
		}
		diagnostics <- &executionnode.ObserverError{Code: executionnode.ObserverTransportFailure}
		close(events)
		close(diagnostics)
		publisher := &subscriptionDrainPublisher{}
		app := &App{ctx: context.Background(), events: publisher, installationRuns: newInstallationRunRegistry()}
		app.forwardInstallationSubscription(context.Background(), "final", installationRunSubscription{
			sub: &executionnode.ObserverSubscription{Events: events, Errors: diagnostics},
		})
		var sequences []int
		errorCount := 0
		for _, value := range publisher.values {
			if value.Event != nil {
				sequences = append(sequences, value.Event.Sequence)
			} else if value.ErrorCode != "" {
				errorCount++
			}
		}
		if len(sequences) != 3 || sequences[0] != 10363 || sequences[1] != 10364 || sequences[2] != 10365 || errorCount != 1 {
			t.Fatalf("attempt %d: lost tail or diagnostic: %v, errors=%d", attempt, sequences, errorCount)
		}
	}
}

func TestInstallationSubscriptionCancellationWithOpenChannels(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	app := &App{ctx: ctx, events: &subscriptionDrainPublisher{}, installationRuns: newInstallationRunRegistry()}
	done := make(chan struct{})
	go func() {
		app.forwardInstallationSubscription(ctx, "cancel", installationRunSubscription{
			sub: &executionnode.ObserverSubscription{Events: make(chan executionnode.ExecutionEvent), Errors: make(chan error)},
		})
		close(done)
	}()
	cancel()
	select {
	case <-done:
	case <-time.After(time.Second):
		t.Fatal("forwarder did not stop after cancellation")
	}
}
