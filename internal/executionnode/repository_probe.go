package executionnode

import (
	"context"
	"errors"
	"regexp"
	"strings"

	"platform-installer/internal/artifactsource"
)

var packageIdentity = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9_.+:-]{0,127}$`)

// ProbeRepository performs a read-only query against the target node's
// configured DNF repositories. It does not install, refresh or modify repos.
func (t OpenSSHTransport) ProbeRepository(ctx context.Context, node Node, requirement artifactsource.Requirement) (artifactsource.RepositoryProbeResult, error) {
	result := artifactsource.RepositoryProbeResult{TargetNode: node.ID, Requirement: requirement}
	if !packageIdentity.MatchString(requirement.Name) || requirement.OS == "" || requirement.Architecture == "" {
		result.Status = artifactsource.ProbeFailed
		result.Reason = "REQUIREMENT_INVALID"
		return result, errors.New("REPOSITORY_PROBE_REQUIREMENT_INVALID")
	}
	const probeScript = "set -eu\ncase \"$1\" in *[!A-Za-z0-9_.+:-]*) exit 64;; esac\nsudo -n dnf -q repoquery --available --qf '%{NAME}|%{VERSION}|%{ARCH}' -- \"$1\"\n"
	output, err := t.ssh(ctx, node, "sh", []string{"-s", "--", requirement.Name}, []byte(probeScript))
	if err != nil {
		result.Status = artifactsource.RepositoryUnavailable
		result.Reason = "REPOSITORY_UNAVAILABLE"
		return result, nil
	}
	for _, line := range strings.Split(strings.TrimSpace(string(output)), "\n") {
		parts := strings.Split(line, "|")
		if len(parts) != 3 || !packageIdentity.MatchString(parts[0]) || !packageIdentity.MatchString(parts[1]) || !packageIdentity.MatchString(parts[2]) {
			continue
		}
		result.Candidates = append(result.Candidates, artifactsource.Candidate{Name: parts[0], Version: parts[1], OS: requirement.OS, Architecture: parts[2], ID: parts[0] + "-" + parts[1] + "." + parts[2]})
	}
	if len(result.Candidates) == 0 {
		result.Status = artifactsource.NotFound
		result.Reason = "REPOSITORY_NOT_FOUND"
		return result, nil
	}
	for _, candidate := range result.Candidates {
		if candidate.Name == requirement.Name && candidate.Architecture == requirement.Architecture && versionMatches(requirement.Version, candidate.Version) {
			result.Status = artifactsource.AvailableCompatible
			result.Reason = "REPOSITORY_COMPATIBLE"
			return result, nil
		}
	}
	result.Status = artifactsource.AvailableIncompatible
	result.Reason = "REPOSITORY_INCOMPATIBLE"
	return result, nil
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

type repositoryProbeProvider struct {
	result artifactsource.RepositoryProbeResult
}

func (p repositoryProbeProvider) FindCompatible(requirement artifactsource.Requirement) (artifactsource.Candidate, bool, error) {
	if p.result.Status == artifactsource.RepositoryUnavailable || p.result.Status == artifactsource.ProbeFailed {
		return artifactsource.Candidate{}, false, errors.New(p.result.Reason)
	}
	for _, candidate := range p.result.Candidates {
		if candidate.Name == requirement.Name && candidate.OS == requirement.OS && candidate.Architecture == requirement.Architecture && versionMatches(requirement.Version, candidate.Version) {
			return candidate, true, nil
		}
	}
	return artifactsource.Candidate{}, false, nil
}

// ResolveWithTargetProbe keeps repository probing target-scoped while the
// existing artifactsource.Resolve remains the only source-selection authority.
func ResolveWithTargetProbe(ctx context.Context, targetNode Node, requirement artifactsource.Requirement, probe artifactsource.RepositoryProbe, bundle artifactsource.Provider) (artifactsource.Result, artifactsource.RepositoryProbeResult, error) {
	probeResult, err := probe.ProbeRepository(ctx, requirement)
	if err != nil {
		return artifactsource.Result{}, probeResult, err
	}
	result, err := artifactsource.ResolveForNode(targetNode.ID, requirement, repositoryProbeProvider{result: probeResult}, bundle)
	return result, probeResult, err
}

// ResolveRequirementsWithTargetProbe performs one read-only probe per
// requirement and returns the target-filtered projection consumed by the
// Ansible service gate. Source selection remains exclusively in the existing
// artifactsource resolver.
func ResolveRequirementsWithTargetProbe(ctx context.Context, targetNode Node, requirements []artifactsource.Requirement, probe artifactsource.RepositoryProbe, bundle artifactsource.Provider) (map[string]artifactsource.Result, []artifactsource.RepositoryProbeResult, error) {
	results := make([]artifactsource.Result, 0, len(requirements))
	probes := make([]artifactsource.RepositoryProbeResult, 0, len(requirements))
	for _, requirement := range requirements {
		result, probeResult, err := ResolveWithTargetProbe(ctx, targetNode, requirement, probe, bundle)
		if err != nil {
			return nil, probes, err
		}
		results = append(results, result)
		probes = append(probes, probeResult)
	}
	return artifactsource.RuntimeProjection(targetNode.ID, results), probes, nil
}
