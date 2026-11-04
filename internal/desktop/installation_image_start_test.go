package desktop

import (
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"platform-installer/internal/executionnode"
	"platform-installer/internal/runtimesecret"
)

type startImageIdentity struct{}

func (startImageIdentity) IdentityFile(string) (string, error) { return "synthetic-key", nil }

// Exercise the production OpenSSH planning/credential callback without a host
// connection. Stop after image preparation, before any execution dispatch.
type startImageRunner struct {
	t        *testing.T
	scope    executionnode.ImagePreparationScope
	prepared bool
}

func (r *startImageRunner) Run(ctx context.Context, name string, args []string, input []byte) ([]byte, error) {
	return r.RunBounded(ctx, name, args, input, 65536)
}

func (r *startImageRunner) RunBounded(_ context.Context, _ string, args []string, input []byte, _ int) ([]byte, error) {
	command := strings.Join(args, " ")
	if strings.Contains(command, "readlink") {
		return []byte("/var/lib/platform-installer/runtime/releases/synthetic"), nil
	}
	if len(input) == 0 && strings.Contains(command, "/state/active") {
		return []byte("BUNDLE_DIGEST=sha256:" + strings.Repeat("b", 64)), nil
	}
	var request map[string]any
	if json.Unmarshal(input, &request) != nil {
		return []byte("HIT"), nil
	}
	switch request["operation"] {
	case "GetCapabilities":
		return json.Marshal(map[string]any{"apiVersion": "platform.installer/execution-capabilities/v1alpha10", "supportedOperations": []string{"BuildDeploymentPlan", "PrepareApplicationImages"}, "deploymentPlanRequestVersions": []string{"platform.installer/execution-runtime/v1alpha6"}, "applicationImages": map[string]any{"protocol": "PrepareApplicationImages/v1alpha1", "leaseProtocol": "platform.installer/application-image-preparation-lease/v1alpha1"}})
	case "PrepareApplicationImages":
		if request["phase"] == "DESCRIBE" {
			return json.Marshal(map[string]any{"status": "INPUTS_READY", "inputsDigest": "sha256:" + strings.Repeat("a", 64), "inputs": r.scope, "leaseBinding": map[string]any{}})
		}
		lease, _ := request["preparationLease"].(map[string]any)
		payload, _ := lease["payload"].(map[string]any)
		values, _ := payload["runtimeSecretValues"].(map[string]any)
		approvals, _ := lease["approvals"].([]any)
		if payload["username"] != "operator" || payload["password"] != "synthetic-ssh" || len(values) != 2 || values["application-secret-"+strings.Repeat("a", 32)] != "synthetic-registry-user" || values["application-secret-"+strings.Repeat("b", 32)] != "synthetic-registry-password" || len(approvals) != 1 {
			r.t.Fatal("Start preparation lost scoped session credentials or SSH approvals")
		}
		r.prepared = true
		return json.Marshal(map[string]any{"status": "READY", "preparationDigest": "sha256:" + strings.Repeat("c", 64)})
	case "BuildDeploymentPlan":
		return []byte(`{"error":"QA_PLAN_STOP_AFTER_PREPARATION"}`), nil
	default:
		r.t.Fatal("unexpected protocol operation")
		return nil, nil
	}
}

type startImageBuilder struct {
	base          *installationPlanBuilder
	transport     executionnode.OpenSSHTransport
	rebuild       bool
	beforeRebuild func()
}

func (b *startImageBuilder) BuildDeploymentPlan(ctx context.Context, node executionnode.Node, root string, release map[string]any, order []string) (executionnode.DeploymentPlan, error) {
	if !b.rebuild {
		return b.base.BuildDeploymentPlan(ctx, node, root, release, order)
	}
	if b.beforeRebuild != nil {
		b.beforeRebuild()
	}
	return b.transport.BuildDeploymentPlan(ctx, node, root, release, order)
}

func TestStartRebuildProvidesImagePreparationSessionCredentials(t *testing.T) {
	for _, scenario := range []string{"retained-inputs", "changed-context", "foreign-revision", "foreign-library", "missing-session", "missing-trust"} {
		t.Run(scenario, func(t *testing.T) {
			app, base, client := installationPlanApp(t, false)
			defer app.secrets.Close()
			app.execution.context.SelectedHostID = "node-1"
			if err := os.Mkdir(filepath.Join(app.current.Root, "inventory"), 0700); err != nil {
				t.Fatal(err)
			}
			revision, err := app.projectRevision(app.current.Root)
			if err != nil {
				t.Fatal(err)
			}
			app.current.Managed.ProjectRevision = revision
			pin := app.approvedTargetHostKeys["node1"]
			pin.revision = revision
			app.approvedTargetHostKeys["node1"] = pin
			inputs := []executionnode.ApplicationSecretDescriptor{}
			for i, purpose := range []string{"APPLICATION_REGISTRY_USERNAME", "APPLICATION_REGISTRY_PASSWORD"} {
				ref := []string{"registry-user", "registry-password"}[i]
				inputs = append(inputs, executionnode.ApplicationSecretDescriptor{RequirementRef: "application-secret-" + strings.Repeat(string(rune('a'+i)), 32), SourceRef: ref, Purpose: purpose, DisplayLabel: purpose, Hosts: []string{"node1"}, ApplicationLibraries: []string{"sdku"}, Operations: []string{"APPLICATION_LIBRARIES_APPLY", "APPLICATION_LIBRARIES_VERIFY"}})
			}
			app.binding.reader.transport = applicationDescriptorTransport{inputs: inputs}
			binding, _ := app.credentialBindingLocked()
			if _, err := app.secrets.Set(binding, runtimesecret.Input{Username: "operator", SSHMode: runtimesecret.SSHPassword, SSHPassword: "synthetic-ssh"}); err != nil {
				t.Fatal(err)
			}
			if err := app.secrets.SetPendingApplicationSecretValues(binding, map[string]string{"registry-user": "synthetic-registry-user", "registry-password": "synthetic-registry-password"}); err != nil {
				t.Fatal(err)
			}
			runner := &startImageRunner{t: t, scope: executionnode.ImagePreparationScope{ProjectIdentity: app.current.Project.ID, ProjectRevision: revision, TargetConnections: map[string]executionnode.ImageTargetConnection{"node1": {Address: "192.0.2.10", Port: 22}}}}
			data, _ := json.Marshal(inputs)
			if err := json.Unmarshal(data, &runner.scope.Requirements); err != nil {
				t.Fatal(err)
			}
			builder := &startImageBuilder{base: base, transport: executionnode.OpenSSHTransport{Identity: startImageIdentity{}, Runner: runner}}
			app.binding.plans = executionnode.NewExecutionService(builder, client)
			created := app.CreateInstallationPlan([]string{})
			if created.Plan == nil {
				t.Fatal("plan not created")
			}
			approved := app.ApproveInstallationPlan(created.Plan.ID, []string{"ACK_RISK"})
			if approved.Error != nil {
				t.Fatal("plan not approved")
			}
			builder.rebuild = true
			builder.beforeRebuild = func() {
				app.editMu.Lock()
				defer app.editMu.Unlock()
				switch scenario {
				case "changed-context":
					app.installationGeneration++
				case "foreign-revision":
					runner.scope.ProjectRevision = "sha256:" + strings.Repeat("f", 64)
				case "foreign-library":
					runner.scope.Requirements[0].ApplicationLibraries = []string{"foreign"}
				case "missing-session":
					app.secrets.Clear()
				case "missing-trust":
					clear(app.approvedTargetHostKeys)
				}
			}
			result := app.StartApprovedInstallation(created.Plan.ID)
			if result.Error == nil || client.starts != 0 {
				t.Fatal("test must stop before execution dispatch")
			}
			if scenario == "retained-inputs" {
				if !runner.prepared || result.Error.Code != "QA_PLAN_STOP_AFTER_PREPARATION" {
					t.Fatalf("Start did not complete image preparation: %s", result.Error.Code)
				}
			} else if runner.prepared || result.Error.Code == "TARGET_CREDENTIAL_REQUIRED" {
				t.Fatalf("unsafe preparation or missing callback: %s", result.Error.Code)
			}
		})
	}
}

func TestTargetCredentialRequiredMessageDescribesStart(t *testing.T) {
	message := projectErrorMessage("TARGET_CREDENTIAL_REQUIRED")
	if !strings.Contains(message, "SSH") || strings.Contains(message, "открыть проект") {
		t.Fatal("incorrect fallback message for Start")
	}
}
