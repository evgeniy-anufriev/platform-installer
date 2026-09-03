// Package artifactsource selects where one compatible install requirement is
// satisfied. Repository checks are supplied by the actual install node.
package artifactsource

import (
	"context"
	"strings"
)

type Source string

const (
	Repository    Source = "REPOSITORY"
	OfflineBundle Source = "OFFLINE_BUNDLE"
	Blocked       Source = "BLOCKED"
)

type Requirement struct {
	ID           string `json:"id"`
	Name         string `json:"name"`
	Version      string `json:"version"`
	OS           string `json:"os"`
	Architecture string `json:"architecture"`
}

type Candidate struct {
	ID           string     `json:"id"`
	Name         string     `json:"name"`
	Version      string     `json:"version"`
	OS           string     `json:"os"`
	Architecture string     `json:"architecture"`
	Artifacts    []Artifact `json:"artifacts,omitempty"`
}

type Artifact struct {
	Ref    string `json:"ref"`
	SHA256 string `json:"sha256"`
	Size   int64  `json:"size"`
	Type   string `json:"type"`
}

type Result struct {
	APIVersion  string      `json:"apiVersion"`
	Kind        string      `json:"kind"`
	Requirement Requirement `json:"requirement"`
	TargetNode  string      `json:"targetNode"`
	Source      Source      `json:"source"`
	Version     string      `json:"version,omitempty"`
	ArtifactRef string      `json:"artifactRef,omitempty"`
	Artifacts   []Artifact  `json:"artifacts,omitempty"`
	Reason      string      `json:"reason"`
}

type Provider interface {
	FindCompatible(Requirement) (Candidate, bool, error)
}

// CandidatesProvider is a data-only bundle provider. It contains candidates
// already verified by the bundle importer; it does not select a source or
// inspect the target node.
type CandidatesProvider []Candidate

func (p CandidatesProvider) FindCompatible(requirement Requirement) (Candidate, bool, error) {
	for _, candidate := range p {
		if compatible(requirement, candidate) {
			return candidate, true, nil
		}
	}
	return Candidate{}, false, nil
}

type ProbeStatus string

const (
	AvailableCompatible   ProbeStatus = "AVAILABLE_COMPATIBLE"
	AvailableIncompatible ProbeStatus = "AVAILABLE_INCOMPATIBLE"
	NotFound              ProbeStatus = "NOT_FOUND"
	RepositoryUnavailable ProbeStatus = "REPOSITORY_UNAVAILABLE"
	ProbeFailed           ProbeStatus = "PROBE_FAILED"
)

type RepositoryProbeResult struct {
	TargetNode  string      `json:"targetNode"`
	Requirement Requirement `json:"requirement"`
	Status      ProbeStatus `json:"status"`
	Candidates  []Candidate `json:"candidates,omitempty"`
	Reason      string      `json:"reason"`
}

type RepositoryProbe interface {
	ProbeRepository(context.Context, Requirement) (RepositoryProbeResult, error)
}

// RuntimeProjection converts resolved decisions into the derived Ansible
// variable consumed by the shared service gate. It never writes project state.
func RuntimeProjection(targetNode string, results []Result) map[string]Result {
	projection := make(map[string]Result, len(results))
	for _, result := range results {
		if result.TargetNode != targetNode {
			continue
		}
		projection[result.Requirement.ID] = result
	}
	return projection
}

// Resolve applies the same policy to execution-node and target-node
// requirements. Each provider must query only the node it represents.
func Resolve(requirement Requirement, repository, bundle Provider) (Result, error) {
	return ResolveForNode("", requirement, repository, bundle)
}

// ResolveForNode returns the versioned contract consumed by Core service
// roles. Providers remain scoped to the target node supplied by the caller.
func ResolveForNode(targetNode string, requirement Requirement, repository, bundle Provider) (Result, error) {
	base := func(source Source, candidate Candidate, reason string) Result {
		return Result{APIVersion: "platform.installer/artifact-source/v1alpha1", Kind: "ResolvedArtifactSource", Requirement: requirement, TargetNode: targetNode, Source: source, Version: candidate.Version, ArtifactRef: candidate.ID, Artifacts: candidate.Artifacts, Reason: reason}
	}
	if candidate, ok, err := repository.FindCompatible(requirement); err != nil {
		if candidate, bundleOK, bundleErr := bundle.FindCompatible(requirement); bundleErr != nil {
			return Result{}, bundleErr
		} else if bundleOK {
			return base(OfflineBundle, candidate, "REPOSITORY_UNAVAILABLE"), nil
		}
		return base(Blocked, Candidate{}, "REPOSITORY_UNAVAILABLE"), err
	} else if ok && compatible(requirement, candidate) {
		return base(Repository, candidate, "REPOSITORY_COMPATIBLE"), nil
	}
	if candidate, ok, err := bundle.FindCompatible(requirement); err != nil {
		return Result{}, err
	} else if ok && compatible(requirement, candidate) {
		return base(OfflineBundle, candidate, "BUNDLE_COMPATIBLE"), nil
	}
	return base(Blocked, Candidate{}, "BUNDLE_MISSING_OR_INCOMPATIBLE"), nil
}

func compatible(requirement Requirement, candidate Candidate) bool {
	if candidate.Name != requirement.Name || candidate.OS != requirement.OS || candidate.Architecture != requirement.Architecture {
		return false
	}
	return versionMatches(requirement.Version, candidate.Version)
}

func versionMatches(required, actual string) bool {
	if required == "" {
		return true
	}
	requiredParts, actualParts := strings.Split(required, "."), strings.Split(actual, ".")
	if len(requiredParts) != len(actualParts) {
		return false
	}
	for i, part := range requiredParts {
		if part != "x" && part != "X" && part != actualParts[i] {
			return false
		}
	}
	return true
}
