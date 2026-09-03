package installer

import (
	"crypto/rand"
	"encoding/hex"
	"sync"
	"time"
)

type storedDocument struct {
	LogicalPath string
	Before      []byte
	After       []byte
	Existed     bool
}

type storedPlan struct {
	Created     time.Time
	ProjectRoot string
	Public      EditPlan
	Documents   []storedDocument
}

type PlanStore interface {
	Put(plan storedPlan) (string, error)
	Get(id string) (storedPlan, bool)
	Discard(id string) bool
}

type MemoryPlanStore struct {
	mu    sync.Mutex
	ttl   time.Duration
	now   func() time.Time
	plans map[string]storedPlan
}

func NewMemoryPlanStore(ttl time.Duration) *MemoryPlanStore {
	return &MemoryPlanStore{ttl: ttl, now: time.Now, plans: make(map[string]storedPlan)}
}

func cloneStoredPlan(plan storedPlan) storedPlan {
	copyPlan := plan
	copyPlan.Public.AffectedDocuments = append([]DocumentChange(nil), plan.Public.AffectedDocuments...)
	copyPlan.Public.SemanticChanges = append([]SemanticChange(nil), plan.Public.SemanticChanges...)
	copyPlan.Documents = make([]storedDocument, len(plan.Documents))
	for index, document := range plan.Documents {
		copyPlan.Documents[index] = document
		copyPlan.Documents[index].Before = append([]byte(nil), document.Before...)
		copyPlan.Documents[index].After = append([]byte(nil), document.After...)
	}
	return copyPlan
}

func (s *MemoryPlanStore) Put(plan storedPlan) (string, error) {
	identifier := make([]byte, 16)
	if _, err := rand.Read(identifier); err != nil {
		return "", err
	}
	id := hex.EncodeToString(identifier)
	s.mu.Lock()
	defer s.mu.Unlock()
	s.plans[id] = cloneStoredPlan(plan)
	return id, nil
}

func (s *MemoryPlanStore) Get(id string) (storedPlan, bool) {
	s.mu.Lock()
	defer s.mu.Unlock()
	plan, found := s.plans[id]
	if !found {
		return storedPlan{}, false
	}
	if s.ttl > 0 && s.now().Sub(plan.Created) > s.ttl {
		delete(s.plans, id)
		return storedPlan{}, false
	}
	return cloneStoredPlan(plan), true
}

func (s *MemoryPlanStore) Discard(id string) bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	_, found := s.plans[id]
	delete(s.plans, id)
	return found
}
