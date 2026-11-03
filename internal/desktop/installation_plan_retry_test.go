package desktop

import (
	"context"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"platform-installer/internal/executionnode"
	"platform-installer/internal/runtimesecret"
)

type failingNodeOperation struct {
	executionLifecycleStub
	operation string
}

func (service *failingNodeOperation) InspectExecutionNode(ctx context.Context, node executionnode.Node) (executionnode.Inspection, error) {
	if service.operation == "check" || service.operation == "verify" || service.operation == "post-prepare-check" {
		return executionnode.Inspection{}, errors.New("EXECUTION_NODE_UNAVAILABLE")
	}
	return service.executionLifecycleStub.InspectExecutionNode(ctx, node)
}

func (service *failingNodeOperation) PlanExecutionNodePreparation(ctx context.Context, node executionnode.Node, root string) (executionnode.Plan, error) {
	return executionnode.Plan{}, errors.New("EXECUTION_NODE_UNAVAILABLE")
}

func (service *failingNodeOperation) Prepare(ctx context.Context, node executionnode.Node, root, plan string) (executionnode.Result, error) {
	if service.operation == "prepare" {
		return executionnode.Result{}, errors.New("EXECUTION_NODE_UNAVAILABLE")
	}
	return executionnode.Result{State: executionnode.Ready}, nil
}

func TestNodeOperationErrorsRetainSSHTrustAndSessionSecrets(t *testing.T) {
	for _, operation := range []string{"check", "preparation-plan", "prepare", "post-prepare-check", "verify"} {
		t.Run(operation, func(t *testing.T) {
			app, secretBinding, serviceInputs := reapprovalFixture(t)
			bundle := v02TestBundle(t)
			app.availableBundleRoot = bundle.Root
			app.current.Project.Source.BundleDigest = bundle.Digest
			app.current.Project.Source.CatalogDigest = bundle.Manifest.CatalogDigest
			binding := app.binding
			binding.bundleRoot = bundle.Root
			binding.reader.runtimeRelease = map[string]any{"bundleDigest": bundle.Digest, "catalogDigest": bundle.Manifest.CatalogDigest}
			writeInstallationProject(t, app.current.Root)
			if err := os.Mkdir(filepath.Join(app.current.Root, "inventory"), 0700); err != nil {
				t.Fatal(err)
			}
			revision, err := app.projectRevision(app.current.Root)
			if err != nil {
				t.Fatal(err)
			}
			binding.service = &failingNodeOperation{operation: operation}
			app.execution.setStatus("READY")
			before, err := app.secrets.CurrentExecutionIdentity(secretBinding)
			if err != nil {
				t.Fatal(err)
			}
			pin := binding.hostKeyPin
			switch operation {
			case "check":
				if app.CheckExecutionNode().Error == nil {
					t.Fatal("expected inspection error")
				}
			case "preparation-plan":
				if app.PlanExecutionNodePreparation().Error == nil {
					t.Fatal("expected planning error")
				}
			case "prepare", "post-prepare-check":
				app.continuation = &verificationContinuation{root: app.current.Root, projectID: app.current.Project.ID, revision: revision, bindingID: binding.node.ID, planID: "preparation", planDigest: "synthetic", expiresAt: time.Now().Add(time.Minute)}
				if app.PrepareExecutionNode("preparation").Error == nil {
					t.Fatal("expected preparation error")
				}
			case "verify":
				if result := app.verifyProjectWithBindingLocked(binding, revision, true); result.Error == nil {
					t.Fatal("expected verification error")
				}
			}
			after, err := app.secrets.CurrentExecutionIdentity(secretBinding)
			if err != nil || before.Generation != after.Generation || app.binding != binding || binding.hostKeyPin != pin {
				t.Fatal("operation error reset SSH identity or trusted connection")
			}
			if _, err := os.Stat(pin.knownHosts); err != nil {
				t.Fatal("operation error removed approved SSH key")
			}
			if !app.secrets.ServiceSecretsPresent(secretBinding, serviceInputs) || app.secrets.Status(secretBinding).PKIStorePasswordStatus != runtimesecret.PKIStorePasswordPresent {
				t.Fatal("operation error erased session secrets")
			}
			binding.service = &executionLifecycleStub{inspection: executionnode.Inspection{State: executionnode.Ready, Runtime: executionnode.Runtime{BundleDigest: bundle.Digest}}}
			if result := app.CheckExecutionNode(); result.Status != "READY" {
				t.Fatalf("retry required SSH reentry or reapproval: %s", result.Status)
			}
		})
	}
}

type retryRegistryDescriptors struct{ applicationDescriptorTransport }

func (transport retryRegistryDescriptors) BuildRuntimeSecretDescriptors(ctx context.Context, node executionnode.Node, root string, release map[string]any, request executionnode.RuntimeSecretDescriptorRequest) (executionnode.RuntimeSecretDescriptorResult, error) {
	result, err := transport.applicationDescriptorTransport.BuildRuntimeSecretDescriptors(ctx, node, root, release, request)
	result.Runtime.BundleDigest, _ = release["bundleDigest"].(string)
	result.Runtime.CatalogDigest, _ = release["catalogDigest"].(string)
	for i := range result.Descriptors {
		result.Descriptors[i].ServiceDeployment = "vault-one"
	}
	return result, err
}

type retryRegistryPlanBuilder struct {
	app           *App
	scope         executionnode.ImagePreparationScope
	base          installationPlanBuilder
	t             *testing.T
	beforeFailure func()
}

func (builder *retryRegistryPlanBuilder) BuildDeploymentPlan(ctx context.Context, node executionnode.Node, root string, release map[string]any, order []string) (executionnode.DeploymentPlan, error) {
	credentials, err := builder.app.imagePreparationCredentialsLocked(builder.scope)
	if err != nil {
		if builder.beforeFailure != nil {
			builder.beforeFailure()
		}
		return executionnode.DeploymentPlan{}, err
	}
	ref := "application-secret-" + strings.Repeat("a", 32)
	if len(credentials.Payload.RuntimeSecretValues) != 1 || credentials.Payload.RuntimeSecretValues[ref] != "synthetic-registry" {
		builder.t.Fatal("registry input lost or unrelated secrets exposed")
	}
	plan, err := builder.base.BuildDeploymentPlan(ctx, node, root, release, order)
	plan.ProjectIdentity = builder.app.current.Project.ID
	return plan, err
}

func TestMissingRegistryPasswordDoesNotInvalidatePreparedNodeOrOtherSecrets(t *testing.T) {
	for _, scenario := range []string{"retry", "recheck", "changed-endpoint", "tampered-pin", "expired-session"} {
		t.Run(scenario, func(t *testing.T) {
			app, secretBinding, serviceInputs := reapprovalFixture(t)
			bundle := v02TestBundle(t)
			app.availableBundleRoot = bundle.Root
			app.current.Project.Source.BundleDigest = bundle.Digest
			app.current.Project.Source.CatalogDigest = bundle.Manifest.CatalogDigest
			app.binding.bundleRoot = bundle.Root
			app.binding.reader.runtimeRelease = map[string]any{"bundleDigest": bundle.Digest, "catalogDigest": bundle.Manifest.CatalogDigest, "coreVersion": "test-core", "planningProtocol": "platform.installer/execution-runtime/v1alpha1"}
			writeInstallationProject(t, app.current.Root)
			if err := os.Mkdir(filepath.Join(app.current.Root, "inventory"), 0700); err != nil {
				t.Fatal(err)
			}
			revision, err := app.projectRevision(app.current.Root)
			if err != nil {
				t.Fatal(err)
			}
			app.current.Managed.ProjectRevision = revision
			ref := "application-secret-" + strings.Repeat("a", 32)
			inputs := []executionnode.ApplicationSecretDescriptor{{RequirementRef: ref, Purpose: "APPLICATION_REGISTRY_PASSWORD", SourceRef: "registry-password", DisplayLabel: "Registry password", Hosts: []string{"node1"}, ApplicationLibraries: []string{"szi"}, Operations: []string{"APPLICATION_LIBRARIES_APPLY", "APPLICATION_LIBRARIES_VERIFY"}}}
			otherRef := "application-secret-" + strings.Repeat("b", 32)
			inputs = append(inputs, executionnode.ApplicationSecretDescriptor{RequirementRef: otherRef, Purpose: "APPLICATION_SECRET", SourceRef: "app-password", DisplayLabel: "Application password", Hosts: []string{"node1"}, ApplicationLibraries: []string{"szi"}, Operations: []string{"APPLICATION_LIBRARIES_APPLY", "APPLICATION_LIBRARIES_VERIFY"}})
			if err := app.secrets.SetPendingApplicationSecretValues(secretBinding, map[string]string{"app-password": "synthetic-application"}); err != nil {
				t.Fatal(err)
			}
			app.binding.reader.transport = retryRegistryDescriptors{applicationDescriptorTransport{inputs: inputs}}
			app.approvedTargetHostKeys = map[string]approvedTargetHostKey{"node1": {root: app.current.Root, projectID: app.current.Project.ID, revision: revision, address: "192.0.2.10", port: 22, keyType: "ssh-ed25519", publicKey: "confirmed"}}
			app.current.Managed.ApplicationLibraries = map[string]map[string]any{"szi": {"registry_credentials": map[string]any{"registry.example": map[string]any{"password": map[string]any{"source": map[string]any{"kind": "runtime_secret_ref", "ref": "registry-password"}}}}}}
			builder := &retryRegistryPlanBuilder{app: app, t: t, scope: executionnode.ImagePreparationScope{ProjectIdentity: app.current.Project.ID, ProjectRevision: revision, TargetConnections: map[string]executionnode.ImageTargetConnection{"node1": {Address: "192.0.2.10", Port: 22}}}}
			data, _ := json.Marshal(inputs[:1])
			if err := json.Unmarshal(data, &builder.scope.Requirements); err != nil {
				t.Fatal(err)
			}
			app.binding.plans = executionnode.NewExecutionService(builder, &installationPlanClient{})
			app.binding.service = &executionLifecycleStub{inspection: executionnode.Inspection{State: executionnode.Ready, Runtime: executionnode.Runtime{BundleDigest: bundle.Digest}}}
			app.execution.setStatus("READY")
			binding := app.binding
			builder.beforeFailure = func() {
				switch scenario {
				case "changed-endpoint":
					server := app.current.Managed.Servers["node1"]
					server.Address = "192.0.2.11"
					app.current.Managed.Servers["node1"] = server
				case "tampered-pin":
					if err := os.WriteFile(binding.hostKeyPin.knownHosts, []byte("tampered\n"), 0600); err != nil {
						t.Fatal(err)
					}
				case "expired-session":
					app.secrets.Clear()
				}
			}
			first := app.CreateInstallationPlan([]string{})
			if scenario != "retry" && scenario != "recheck" {
				if first.Error == nil || app.binding != nil || app.execution.context.Status == "READY" {
					t.Fatal("changed trust/session retained prepared binding")
				}
				return
			}
			if first.Error == nil || first.Error.Code != "APPLICATION_REGISTRY_RUNTIME_SECRET_REQUIRED" {
				t.Fatalf("missing registry input error: %+v", first.Error)
			}
			if app.binding != binding || app.execution.context.Status != "READY" || !app.secrets.ServiceSecretsPresent(secretBinding, serviceInputs) || app.secrets.Status(secretBinding).PKIStorePasswordStatus != runtimesecret.PKIStorePasswordPresent {
				t.Fatal("missing registry input revoked node or unrelated secrets")
			}
			if len(app.secrets.MissingRequiredSecrets(secretBinding, []string{otherRef}, false, false)) != 0 {
				t.Fatal("missing registry input erased unrelated application password")
			}
			if err := app.SetDeploymentRuntimeSecretValues(RuntimeSecretValuesInput{ProjectRevision: revision, ApplicationLibrary: "szi", ApplicationSourceValues: map[string]string{"registry-password": "synthetic-registry"}}); err != nil {
				t.Fatal(err)
			}
			if scenario == "recheck" {
				setReapprovalProbe(t, app, false)
				if result := app.ApproveExecutionNodeHostKey("reapproval"); result.Status != "APPROVED" {
					t.Fatal("same key reapproval failed")
				}
				if result := app.CheckExecutionNode(); result.Status != "READY" {
					t.Fatalf("recheck: %s", result.Status)
				}
			}
			second := app.CreateInstallationPlan([]string{})
			if second.Error != nil || second.Plan == nil {
				t.Fatalf("retry did not build plan: %+v", second.Error)
			}
			if !app.secrets.ServiceSecretsPresent(secretBinding, serviceInputs) || app.secrets.Status(secretBinding).PKIStorePasswordStatus != runtimesecret.PKIStorePasswordPresent {
				t.Fatal("retry/recheck lost other secrets")
			}
			if len(app.secrets.MissingRequiredSecrets(secretBinding, []string{otherRef}, false, false)) != 0 {
				t.Fatal("retry/recheck erased unrelated application password")
			}
		})
	}
}
