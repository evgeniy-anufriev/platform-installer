package executionnode

import (
	"bytes"
	"encoding/json"
	"errors"
	"io"
	"strings"
)

// Image requirements stay separate from RPM selection; Core owns delivery.
type ApplicationImageRequirement struct {
	ID                 string   `json:"id"`
	Name               string   `json:"name"`
	ArtifactType       string   `json:"artifactType"`
	ImageID            string   `json:"imageId"`
	LocalReference     string   `json:"localReference"`
	ApplicationLibrary string   `json:"applicationLibrary"`
	InstanceID         string   `json:"instanceId"`
	Hosts              []string `json:"hosts"`
	SourcePolicy       string   `json:"sourcePolicy"`
	Platform           struct {
		OS           string `json:"os"`
		Architecture string `json:"architecture"`
		Variant      string `json:"variant,omitempty"`
	} `json:"platform"`
}

func decodeApplicationImage(raw any) (ApplicationImageRequirement, error) {
	var image ApplicationImageRequirement
	data, err := json.Marshal(raw)
	if err == nil && len(data) <= 64*1024 {
		d := json.NewDecoder(bytes.NewReader(data))
		d.DisallowUnknownFields()
		if d.Decode(&image) == nil && d.Decode(new(any)) == io.EOF && image.ID != "" && len(image.ID) <= 256 && image.Name != "" && len(image.Name) <= 512 && image.ArtifactType == "container-image" && validSHA256(image.ImageID) && image.LocalReference == "platform-application:sha256-"+strings.TrimPrefix(image.ImageID, "sha256:") && runtimeSecretDeploymentPattern.MatchString(image.ApplicationLibrary) && len(image.ApplicationLibrary) <= 128 && runtimeSecretDeploymentPattern.MatchString(image.InstanceID) && len(image.InstanceID) <= 128 && image.SourcePolicy == "REPOSITORY_THEN_OFFLINE" && image.Platform.OS == "linux" && (image.Platform.Architecture == "amd64" || image.Platform.Architecture == "arm64") && len(image.Platform.Variant) <= 32 {
			if hosts, ok := raw.(map[string]any); ok {
				if _, valid := decodePlanStringList(hosts["hosts"], 256); valid {
					return image, nil
				}
			}
		}
	}
	return ApplicationImageRequirement{}, errors.New("DEPLOYMENT_PLAN_REQUIREMENT_INVALID")
}
