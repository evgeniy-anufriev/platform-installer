//go:build browser

package main

import (
	"bytes"
	"encoding/json"
	"errors"
	"io"
	"net/http"

	"platform-installer/internal/executionnode"
	"platform-installer/internal/installer"
)

type browserOperation func(*App, []byte) (any, error)

func noBrowserArgs[R any](fn func(*App) R) browserOperation {
	return func(app *App, body []byte) (any, error) {
		if err := decodeBrowserArgs(body); err != nil {
			return nil, err
		}
		return fn(app), nil
	}
}

func noBrowserArgsError[R any](fn func(*App) (R, error)) browserOperation {
	return func(app *App, body []byte) (any, error) {
		if err := decodeBrowserArgs(body); err != nil {
			return nil, err
		}
		return fn(app)
	}
}

func oneBrowserArg[A, R any](fn func(*App, A) R) browserOperation {
	return func(app *App, body []byte) (any, error) {
		var arg A
		if err := decodeBrowserArgs(body, &arg); err != nil {
			return nil, err
		}
		return fn(app, arg), nil
	}
}

func oneBrowserArgError[A, R any](fn func(*App, A) (R, error)) browserOperation {
	return func(app *App, body []byte) (any, error) {
		var arg A
		if err := decodeBrowserArgs(body, &arg); err != nil {
			return nil, err
		}
		return fn(app, arg)
	}
}

func twoBrowserArgs[A, B, R any](fn func(*App, A, B) R) browserOperation {
	return func(app *App, body []byte) (any, error) {
		var first A
		var second B
		if err := decodeBrowserArgs(body, &first, &second); err != nil {
			return nil, err
		}
		return fn(app, first, second), nil
	}
}

func twoBrowserArgsError[A, B, R any](fn func(*App, A, B) (R, error)) browserOperation {
	return func(app *App, body []byte) (any, error) {
		var first A
		var second B
		if err := decodeBrowserArgs(body, &first, &second); err != nil {
			return nil, err
		}
		return fn(app, first, second)
	}
}

func oneBrowserError[A any](fn func(*App, A) error) browserOperation {
	return func(app *App, body []byte) (any, error) {
		var arg A
		if err := decodeBrowserArgs(body, &arg); err != nil {
			return nil, err
		}
		return struct{}{}, fn(app, arg)
	}
}

func decodeBrowserArgs(body []byte, outputs ...any) error {
	var args []json.RawMessage
	decoder := json.NewDecoder(bytes.NewReader(body))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&args); err != nil {
		return errors.New("REQUEST_ARGUMENTS_INVALID")
	}
	var trailing any
	if err := decoder.Decode(&trailing); err != io.EOF || len(args) != len(outputs) {
		return errors.New("REQUEST_ARGUMENTS_INVALID")
	}
	for i, raw := range args {
		argDecoder := json.NewDecoder(bytes.NewReader(raw))
		argDecoder.DisallowUnknownFields()
		if err := argDecoder.Decode(outputs[i]); err != nil {
			return errors.New("REQUEST_ARGUMENTS_INVALID")
		}
	}
	return nil
}

func browserOperations() map[string]browserOperation {
	return map[string]browserOperation{
		"chooseRuntimeBundleUpdate":  noBrowserArgs((*App).ChooseRuntimeBundleUpdate),
		"confirmRuntimeBundleUpdate": oneBrowserArg((*App).ConfirmRuntimeBundleUpdate),
		"inspectOrphanRun":           noBrowserArgs((*App).InspectOrphanRun),
		"cancelOrphanRun":            oneBrowserArg((*App).CancelOrphanRun),
		"getApplicationConfig":       noBrowserArgs((*App).GetApplicationConfig),
		"currentProject":             noBrowserArgs((*App).CurrentProject),
		"openProject":                oneBrowserArg((*App).OpenProject),
		"createProject":              oneBrowserArg((*App).CreateProject),
		"closeProject":               noBrowserArgs((*App).CloseProject),
		"startEditSession":           noBrowserArgs((*App).StartEditSession),
		"appendEditCommand": twoBrowserArgs(func(app *App, sessionID string, command installer.EditCommand) EditOperationResult {
			return app.AppendEditCommand(sessionID, command)
		}),
		"amendServiceConfigurationDraft":          browserAmendConfiguration(),
		"reviewEditSession":                       oneBrowserArg((*App).ReviewStructuralEditSession),
		"commitEditPlan":                          twoBrowserArgs((*App).CommitStructuralEditPlan),
		"discardEditSession":                      oneBrowserArg((*App).DiscardEditSession),
		"getSessionCredentialStatus":              noBrowserArgsError((*App).GetSessionCredentialStatus),
		"setSessionCredential":                    oneBrowserArgError((*App).SetSessionCredential),
		"setPKIStorePassword":                     oneBrowserArgError((*App).SetPKIStorePassword),
		"getRuntimeSecretDescriptors":             noBrowserArgs((*App).GetRuntimeSecretDescriptors),
		"setDeploymentRuntimeSecretValues":        oneBrowserError((*App).SetDeploymentRuntimeSecretValues),
		"getPendingRuntimeSecretDescriptors":      oneBrowserArg((*App).GetPendingRuntimeSecretDescriptors),
		"setPendingDeploymentRuntimeSecretValues": oneBrowserError((*App).SetPendingDeploymentRuntimeSecretValues),
		"choosePendingDeploymentRuntimeSecretFile": twoBrowserArgsError(func(app *App, input PendingRuntimeSecretFileInput, fileBytes []byte) (string, error) {
			defer clear(fileBytes)
			return app.importPendingDeploymentRuntimeSecretFile(input, fileBytes)
		}),
		"listPendingSecretOutputs": oneBrowserArg(func(app *App, cursor *string) SecretOutputPackagesOperation {
			return app.ListPendingSecretOutputs(cursor)
		}),
		"setSecretOutputEncryptionPassword": oneBrowserError((*App).SetSecretOutputEncryptionPassword),
		"deliverPendingSecretOutput":        oneBrowserArg((*App).DeliverPendingSecretOutput),
		"clearSessionCredential":            noBrowserArgsError((*App).ClearSessionCredential),
		"getExecutionNodeContext":           noBrowserArgsError((*App).GetExecutionNodeContext),
		"getServiceConfigurationPreview": noBrowserArgsError(func(app *App) (executionnode.ServiceConfigurationPreview, error) {
			return app.GetServiceConfigurationPreview()
		}),
		"probeExecutionNodeHostKey":   noBrowserArgs((*App).ProbeExecutionNodeHostKey),
		"approveExecutionNodeHostKey": oneBrowserArg((*App).ApproveExecutionNodeHostKey),
		"declineExecutionNodeHostKey": noBrowserArgs((*App).DeclineExecutionNodeHostKey),
		"probeTargetHostKey":          oneBrowserArg((*App).ProbeTargetHostKey),
		"approveTargetHostKey":        oneBrowserArg((*App).ApproveTargetHostKey),
		"declineTargetHostKey":        noBrowserArgs((*App).DeclineTargetHostKey),
		"getInstallationState":        noBrowserArgs((*App).GetInstallationState),
		"createInstallationPlan":      oneBrowserArg((*App).CreateInstallationPlan),
		"getInstallationPlan":         oneBrowserArg((*App).GetInstallationPlan),
		"approveInstallationPlan":     twoBrowserArgs((*App).ApproveInstallationPlan),
		"startApprovedInstallation":   oneBrowserArg((*App).StartApprovedInstallation),
		"getInstallationRun":          oneBrowserArg((*App).GetInstallationRun),
		"subscribeInstallationRun": twoBrowserArgs(func(app *App, runID string, afterSequence int) InstallationSubscriptionResult {
			return app.SubscribeInstallationRun(runID, afterSequence)
		}),
		"unsubscribeInstallationRun": oneBrowserArg(func(app *App, subscriptionID string) struct{} {
			app.UnsubscribeInstallationRun(subscriptionID)
			return struct{}{}
		}),
		"cancelInstallationRun":        oneBrowserArg((*App).CancelInstallationRun),
		"getEndpointPreview":           noBrowserArgs((*App).GetEndpointPreview),
		"getVerifiedPKIView":           noBrowserArgs((*App).GetVerifiedPKIView),
		"selectExecutionNode":          oneBrowserArgError((*App).SelectExecutionNode),
		"checkExecutionNode":           noBrowserArgs((*App).CheckExecutionNode),
		"planExecutionNodePreparation": noBrowserArgs((*App).PlanExecutionNodePreparation),
		"prepareExecutionNode":         oneBrowserArg((*App).PrepareExecutionNode),
		"verifyProject":                noBrowserArgs((*App).VerifyProject),
		"planProjectExport":            twoBrowserArgs((*App).PlanProjectExport),
		"commitProjectExport":          oneBrowserArg((*App).CommitProjectExport),
	}
}

func browserAmendConfiguration() browserOperation {
	type args struct {
		SessionID   string
		Index       int
		Expected    installer.EditCommand
		Replacement *installer.EditCommand `json:"replacement"`
	}
	return func(app *App, body []byte) (any, error) {
		var input args
		if err := decodeBrowserArgs(body, &input.SessionID, &input.Index, &input.Expected, &input.Replacement); err != nil {
			return nil, errors.New("REQUEST_ARGUMENTS_INVALID")
		}
		return app.AmendServiceConfigurationDraft(input.SessionID, input.Index, input.Expected, input.Replacement), nil
	}
}

type browserAPIError struct {
	Code    string `json:"code"`
	Message string `json:"message"`
}

func writeBrowserError(w http.ResponseWriter, status int, err error) {
	code := projectErrorCode(err)
	if code == "" {
		code = "BROWSER_API_REQUEST_FAILED"
	}
	message := projectErrorMessage(code)
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(map[string]browserAPIError{"error": {Code: code, Message: message}})
}
