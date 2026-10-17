package coreadapter

import (
	"encoding/json"
	"errors"
	"regexp"
)

// These are Core-resolved presentation values, never editable desired state.
type ApplicationLibraries struct {
	APIVersion string                        `json:"apiVersion"`
	Status     string                        `json:"status"`
	Libraries  map[string]ApplicationLibrary `json:"libraries"`
	Findings   []map[string]any              `json:"findings"`
}

type ApplicationLibrary struct {
	Topics                   map[string]json.RawMessage     `json:"topics"`
	RuntimeDirectory         string                         `json:"runtimeDirectory"`
	Connections              map[string]json.RawMessage     `json:"connections"`
	LibraryRef               string                         `json:"libraryRef"`
	Packages                 map[string]json.RawMessage     `json:"packages"`
	Instances                map[string]ApplicationInstance `json:"instances"`
	Resources                map[string]json.RawMessage     `json:"resources"`
	SharedSecretRequirements map[string]json.RawMessage     `json:"sharedSecretRequirements"`
}

type ApplicationInstance struct {
	Topics                    map[string]json.RawMessage      `json:"topics"`
	ApplicationName           string                          `json:"applicationName"`
	SlotID                    string                          `json:"slotId"`
	Placements                map[string]ApplicationPlacement `json:"placements"`
	Connections               map[string]json.RawMessage      `json:"connections"`
	CredentialRequirements    map[string]json.RawMessage      `json:"credentialRequirements"`
	RuntimeSecretRequirements []string                        `json:"runtimeSecretRequirements"`
	SecretBindings            map[string]json.RawMessage      `json:"secretBindings"`
	AgentRequired             bool                            `json:"agentRequired"`
	ExecutionPrerequisites    []string                        `json:"executionPrerequisites"`
	IdentityEnvironment       map[string]string               `json:"identityEnvironment"`
	ImageRequirement          json.RawMessage                 `json:"imageRequirement"`
	AppRole                   json.RawMessage                 `json:"approle"`
}

type ApplicationPlacement struct {
	TopicBindings    map[string][]string        `json:"topicBindings"`
	RuntimeDirectory string                     `json:"runtimeDirectory"`
	CommonDefaults   map[string]json.RawMessage `json:"commonDefaults,omitempty"`
	Inherited        map[string]json.RawMessage `json:"inherited,omitempty"`
	ServerID         string                     `json:"SERVER_ID"`
	RuntimeRef       string                     `json:"runtimeRef"`
	Command          []string                   `json:"command"`
	ImageRequirement json.RawMessage            `json:"imageRequirement"`
	Origin           ApplicationOrigin          `json:"origin"`
	Parameters       map[string]json.RawMessage `json:"parameters"`
	Environment      map[string]any             `json:"environment"`
	Ports            map[string]json.RawMessage `json:"ports"`
	Endpoint         json.RawMessage            `json:"endpoint"`
	ContainerName    string                     `json:"containerName"`
	ComposeProject   string                     `json:"composeProject"`
	RuntimePath      string                     `json:"runtimePath"`
	LibraryEnvPath   string                     `json:"libraryEnvPath"`
}

type ApplicationOrigin struct {
	Resolution         string `json:"resolution"`
	Precision          string `json:"precision"`
	ApplicationPackage string `json:"applicationPackage"`
	LibraryPackage     string `json:"libraryPackage"`
	Host               string `json:"host"`
}

var applicationID = regexp.MustCompile(`^[a-z][a-z0-9]*(?:[-_.][a-z0-9]+)*$`)

func (s *Snapshot) validateApplications() error {
	if s.ApplicationLibraries == nil {
		return nil
	}
	a := s.ApplicationLibraries
	invalid := errors.New("APPLICATION_SNAPSHOT_RESPONSE_INVALID")
	if s.APIVersion != "platform.installer/project-snapshot/v2alpha1" || a.APIVersion != "platform.installer/application-libraries/v1alpha1" || (a.Status != "PASS" && a.Status != "BLOCKED") || a.Libraries == nil || len(a.Libraries) > 256 || len(a.Findings) > 1024 {
		return invalid
	}
	for id, library := range a.Libraries {
		if !validApplicationID(id) || library.LibraryRef == "" || len(library.LibraryRef) > 256 || library.Instances == nil || len(library.Instances) > 256 {
			return invalid
		}
		for id, instance := range library.Instances {
			if !validApplicationID(id) || !validApplicationID(instance.ApplicationName) || !validApplicationID(instance.SlotID) || instance.Placements == nil || len(instance.Placements) > 256 || len(instance.RuntimeSecretRequirements) > 256 {
				return invalid
			}
			for host, placement := range instance.Placements {
				if !validApplicationID(host) || placement.ServerID != host || !validApplicationID(placement.RuntimeRef) || placement.Origin.Host != host || placement.Origin.Resolution != "ANSIBLE" || placement.Origin.Precision != "RESOLUTION_SCOPE" {
					return invalid
				}
			}
		}
	}
	return nil
}

func validApplicationID(id string) bool { return len(id) <= 128 && applicationID.MatchString(id) }
