package coreadapter

import (
	"strings"
	"testing"
)

const applicationSnapshot = `{"apiVersion":"platform.installer/project-snapshot/v2alpha1","applicationLibraries":{"apiVersion":"platform.installer/application-libraries/v1alpha1","status":"PASS","libraries":{"sdku":{"libraryRef":"sdku@1.0.0","instances":{"gateway-sdku":{"applicationName":"gateway","slotId":"gateway","runtimeSecretRequirements":["db-password"],"placements":{"node1":{"SERVER_ID":"node1","runtimeRef":"docker-main","origin":{"host":"node1","resolution":"ANSIBLE","precision":"RESOLUTION_SCOPE"}}}}}}},"findings":[]}}`

func TestApplicationSnapshotTypedProjection(t *testing.T) {
	s, err := DecodeSnapshot([]byte(applicationSnapshot))
	if err != nil {
		t.Fatal(err)
	}
	i := s.ApplicationLibraries.Libraries["sdku"].Instances["gateway-sdku"]
	if i.Placements["node1"].RuntimeRef != "docker-main" || i.RuntimeSecretRequirements[0] != "db-password" {
		t.Fatal("Core projection lost")
	}
}

func TestApplicationSnapshotPreservesScalarEnvironment(t *testing.T) {
	data := strings.Replace(applicationSnapshot, `"SERVER_ID":"node1"`, `"environment":{"TEXT":"001","COUNT":2000,"ENABLED":false},"SERVER_ID":"node1"`, 1)
	s, err := DecodeSnapshot([]byte(data))
	if err != nil {
		t.Fatal(err)
	}
	env := s.ApplicationLibraries.Libraries["sdku"].Instances["gateway-sdku"].Placements["node1"].Environment
	if env["TEXT"] != "001" || env["COUNT"] != float64(2000) || env["ENABLED"] != false {
		t.Fatalf("environment scalar types changed: %v", env)
	}
}

func TestApplicationSnapshotRejectsUnsupportedAndInvalidIdentity(t *testing.T) {
	for _, data := range []string{
		strings.Replace(applicationSnapshot, "project-snapshot/v2alpha1", "project-snapshot/v99", 1),
		strings.Replace(applicationSnapshot, "application-libraries/v1alpha1", "application-libraries/v99", 1),
		strings.Replace(applicationSnapshot, `"sdku":`, `"../sdku":`, 1),
		strings.Replace(applicationSnapshot, `"SERVER_ID":"node1"`, `"SERVER_ID":"node2"`, 1),
		strings.Repeat(" ", 2*1024*1024+1),
	} {
		if _, err := DecodeSnapshot([]byte(data)); err == nil {
			t.Fatal("invalid application snapshot accepted")
		}
	}
}
