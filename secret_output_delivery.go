package main

import (
	"bytes"
	"context"
	"errors"
	"time"

	"platform-installer/internal/executionnode"
	"platform-installer/internal/installer"
	"platform-installer/internal/runtimesecret"
	"platform-installer/internal/secretfiles"
	"platform-installer/internal/secretoutputwire"
)

type SecretOutputDeliveryInput struct {
	PackageID string `json:"packageId"`
}

type SecretOutputDeliveryOperation struct {
	Status      string                             `json:"status"`
	Package     *executionnode.SecretOutputPackage `json:"package,omitempty"`
	Directory   string                             `json:"directory,omitempty"`
	StagingPath string                             `json:"stagingPath,omitempty"`
	Error       *ProjectOpenError                  `json:"error,omitempty"`
}

type secretOutputDeliveryClient interface {
	GetSecretOutputCapabilities(context.Context, executionnode.Node, string, string) (executionnode.SecretOutputCapabilities, error)
	ListPendingSecretOutputs(context.Context, executionnode.Node, string, string, int, *string) (executionnode.SecretOutputList, error)
	FetchSecretOutput(context.Context, executionnode.Node, string, string, string, int) ([]byte, error)
	AcknowledgeSecretOutput(context.Context, executionnode.Node, string, executionnode.SecretOutputRequest) (executionnode.SecretOutputAck, error)
}

// DeliverPendingSecretOutput fetches one freshly listed package, validates the
// confidential frame against that trusted listing, publishes encrypted files
// and a complete local receipt, then sends the idempotent remote ACK.
func (a *App) DeliverPendingSecretOutput(input SecretOutputDeliveryInput) SecretOutputDeliveryOperation {
	a.editMu.Lock()
	if a.current.Status != "OPEN" || a.current.Project == nil || a.execution.context.Status != "READY" {
		a.editMu.Unlock()
		return secretOutputDeliveryFailure("SECRET_OUTPUT_PREREQUISITE_REQUIRED", "Выберите локальную папку и убедитесь, что Execution Node готов.")
	}
	binding, err := a.resolveSelectedExecutionNodeBindingLocked()
	if err != nil {
		a.editMu.Unlock()
		return secretOutputDeliveryFailure("SECRET_OUTPUT_UNAVAILABLE", "Защищённая доставка выходных файлов недоступна.")
	}
	client, ok := binding.reader.transport.(secretOutputDeliveryClient)
	if !ok {
		a.editMu.Unlock()
		return secretOutputDeliveryFailure("SECRET_OUTPUT_UNSUPPORTED", "Выбранный Execution Node не поддерживает защищённую доставку файлов.")
	}
	runtime, runtimeOK := installationRuntimeBinding(binding.reader.runtimeRelease)
	credentialBinding, bindingErr := a.credentialBindingLocked()
	if !runtimeOK || bindingErr != nil || !a.secrets.HasOutputEncryptionPassword(credentialBinding) {
		a.editMu.Unlock()
		return secretOutputDeliveryFailure("SECRET_OUTPUT_PASSWORD_REQUIRED", "Введите пароль шифрования выходных файлов.")
	}
	root, projectID, node := a.current.Root, a.current.Project.ID, binding.node
	deployments := []string{}
	if a.current.Managed != nil {
		for id := range a.current.Managed.Deployments {
			deployments = append(deployments, id)
		}
	}
	generation, projectRoot := a.installationGeneration, a.current.Root
	ctx, cancel := a.operationContext(3 * time.Minute)
	a.editMu.Unlock()
	defer cancel()

	if _, err := client.GetSecretOutputCapabilities(ctx, node, runtime.BundleDigest, projectID); err != nil {
		return secretOutputDeliveryFailure("SECRET_OUTPUT_UNAVAILABLE", "Возможности безопасной доставки не подтверждены.")
	}
	var selected *executionnode.SecretOutputPackage
	var receipt installer.SecretOutputFileReceipt
	for _, deployment := range deployments {
		local, encrypted, localErr := installer.ReadSecretOutputReceipt(root, projectID, deployment, runtime.BundleDigest)
		if localErr != nil {
			continue
		}
		if local.PackageID != input.PackageID {
			for _, data := range encrypted {
				clear(data)
			}
			continue
		}
		localErr = a.secrets.WithOutputEncryptionPassword(credentialBinding, func(password []byte) error {
			for _, entry := range []struct {
				id, purpose string
				bound       int
			}{{"admin-token", secretfiles.PurposeAdminToken, 4096}, {"unseal-shares", secretfiles.PurposeUnsealShares, 32768}} {
				plain, err := secretfiles.Decrypt(password, encrypted[entry.id], entry.bound)
				if err != nil {
					return err
				}
				parsed, err := secretfiles.ReadVaultInput(entry.purpose, plain, nil)
				clear(plain)
				clear(parsed.Token)
				for _, share := range parsed.Shares {
					clear(share)
				}
				if err != nil {
					return err
				}
			}
			return nil
		})
		for _, data := range encrypted {
			clear(data)
		}
		if localErr != nil {
			return secretOutputDeliveryFailure("SECRET_OUTPUT_LOCAL_RECEIPT_INVALID", "Локальный пакет не подтверждён; удалённая копия сохранена.")
		}
		receipt = local
		selected = &executionnode.SecretOutputPackage{Protocol: "SecretOutputDelivery/v1alpha1", ProjectID: local.ProjectID, DeploymentID: local.DeploymentID, PackageID: local.PackageID, SourceRunID: local.SourceRunID, Generation: local.Generation, RuntimeDigest: local.RuntimeDigest, State: "ACKED_CLEANUP_PENDING", Entries: []string{"admin-token", "unseal-shares"}}
		break
	}
	var cursor *string
	seenCursors := map[string]struct{}{}
	for page := 0; selected == nil && page < 128; page++ {
		listed, err := client.ListPendingSecretOutputs(ctx, node, runtime.BundleDigest, projectID, 32, cursor)
		if err != nil {
			return secretOutputDeliveryFailure("SECRET_OUTPUT_UNAVAILABLE", "Ожидающие выходные файлы получить не удалось.")
		}
		for index := range listed.Packages {
			if listed.Packages[index].PackageID == input.PackageID {
				item := listed.Packages[index]
				selected = &item
				break
			}
		}
		if selected != nil || listed.NextCursor == nil {
			break
		}
		next := *listed.NextCursor
		if next == "" || (cursor != nil && next == *cursor) {
			return secretOutputDeliveryFailure("SECRET_OUTPUT_UNAVAILABLE", "Страница списка выходных файлов некорректна.")
		}
		if _, exists := seenCursors[next]; exists {
			return secretOutputDeliveryFailure("SECRET_OUTPUT_UNAVAILABLE", "Страница списка выходных файлов повторилась.")
		}
		seenCursors[next] = struct{}{}
		cursor = &next
	}
	if selected == nil {
		return secretOutputDeliveryFailure("SECRET_OUTPUT_NOT_FOUND", "Выходной пакет больше не доступен для доставки.")
	}
	if receipt.ReceiptID == "" {
		frame, err := client.FetchSecretOutput(ctx, node, runtime.BundleDigest, projectID, selected.PackageID, selected.Generation)
		if err != nil {
			return secretOutputDeliveryFailure("SECRET_OUTPUT_TRANSFER_FAILED", "Передача прервана; локальные файлы не подтверждены.")
		}
		defer clear(frame)
		expected := secretoutputwire.Binding{ProjectID: selected.ProjectID, DeploymentID: selected.DeploymentID, PackageID: selected.PackageID, SourceRunID: selected.SourceRunID, RuntimeDigest: selected.RuntimeDigest, Generation: selected.Generation}
		var localStorageErr error
		transferErr := secretoutputwire.Consume(bytes.NewReader(frame), expected, func(token, shares []byte) error {
			parsedToken, tokenErr := secretfiles.ReadVaultInput(secretfiles.PurposeAdminToken, token, nil)
			if tokenErr != nil {
				return secretfiles.ErrFile
			}
			defer clear(parsedToken.Token)
			parsedShares, sharesErr := secretfiles.ReadVaultInput(secretfiles.PurposeUnsealShares, shares, nil)
			if sharesErr != nil {
				return secretfiles.ErrFile
			}
			for _, value := range parsedShares.Shares {
				defer clear(value)
			}
			credentialBinding, err := a.credentialBindingLockedForOutput(projectRoot, projectID)
			if err != nil {
				return err
			}
			return a.secrets.WithOutputEncryptionPassword(credentialBinding, func(password []byte) error {
				if existing, encrypted, readErr := installer.ReadSecretOutputFiles(root, projectID, selected.DeploymentID, selected.PackageID, selected.SourceRunID, selected.Generation, selected.RuntimeDigest); readErr == nil {
					defer func() {
						for _, data := range encrypted {
							clear(data)
						}
					}()
					admin, adminErr := secretfiles.Decrypt(password, encrypted["admin-token"], 4096)
					sharesPlain, sharesErr := secretfiles.Decrypt(password, encrypted["unseal-shares"], 32768)
					if adminErr != nil || sharesErr != nil || !bytes.Equal(admin, token) || !bytes.Equal(sharesPlain, shares) {
						clear(admin)
						clear(sharesPlain)
						return errors.New("SECRET_OUTPUT_LOCAL_RECEIPT_INVALID")
					}
					clear(admin)
					clear(sharesPlain)
					receipt = existing
					return nil
				}
				adminAge, err := secretfiles.Encrypt(password, token)
				if err != nil {
					return err
				}
				defer clear(adminAge)
				sharesAge, err := secretfiles.Encrypt(password, shares)
				if err != nil {
					return err
				}
				defer clear(sharesAge)
				adminCheck, err := secretfiles.Decrypt(password, adminAge, 4096)
				if err != nil {
					return err
				}
				sharesCheck, err := secretfiles.Decrypt(password, sharesAge, 32768)
				if err != nil {
					clear(adminCheck)
					return err
				}
				if !bytes.Equal(adminCheck, token) || !bytes.Equal(sharesCheck, shares) {
					clear(adminCheck)
					clear(sharesCheck)
					return errors.New("SECRET_OUTPUT_CIPHER_VERIFY_FAILED")
				}
				clear(adminCheck)
				clear(sharesCheck)
				receipt, err = installer.PublishSecretOutputFiles(root, projectID, selected.DeploymentID, selected.PackageID, selected.SourceRunID, selected.Generation, selected.RuntimeDigest, adminAge, sharesAge)
				localStorageErr = err
				return err
			})
		})
		if transferErr != nil {
			var retained *installer.SecretOutputStagingRetainedError
			if errors.As(localStorageErr, &retained) {
				return SecretOutputDeliveryOperation{Status: "STAGING_RETAINED", Package: selected, StagingPath: retained.Path, Error: &ProjectOpenError{Code: "EXPORT_STAGING_RETAINED", Message: "Публикация не завершена. Зашифрованный временный каталог сохранён, потому что безопасное удаление не удалось доказать."}}
			}
			return secretOutputDeliveryFailure("SECRET_OUTPUT_TRANSFER_FAILED", "Проверка или безопасное сохранение выходных файлов не завершились; удалённый пакет сохранён.")
		}
	}
	if receipt.ReceiptID == "" || len(receipt.Digests) != 2 {
		return secretOutputDeliveryFailure("SECRET_OUTPUT_RECEIPT_INVALID", "Локальная запись о сохранении не подтверждена; удалённый пакет сохранён.")
	}
	a.editMu.Lock()
	currentBinding, currentErr := a.resolveSelectedExecutionNodeBindingLocked()
	current := currentErr == nil && a.installationGeneration == generation && a.current.Root == projectRoot && a.current.Project != nil && a.current.Project.ID == projectID && currentBinding.node.ID == node.ID
	a.editMu.Unlock()
	if !current {
		return secretOutputDeliveryFailure("PROJECT_CHANGED", "Проект или Execution Node изменился; удалённый пакет не подтверждён.")
	}
	ack, err := client.AcknowledgeSecretOutput(ctx, node, runtime.BundleDigest, executionnode.SecretOutputRequest{Operation: "Acknowledge", ProjectID: projectID, PackageID: receipt.PackageID, Generation: receipt.Generation, ReceiptID: receipt.ReceiptID, CiphertextDigests: receipt.Digests})
	if err != nil {
		return SecretOutputDeliveryOperation{Status: "ACK_PENDING", Package: selected, Directory: receipt.Directory, Error: &ProjectOpenError{Code: "SECRET_OUTPUT_ACK_PENDING", Message: "Файлы сохранены, но подтверждение Execution Node не получено. Повторите доставку того же пакета."}}
	}
	if ack.State == "ACKED_CLEANUP_PENDING" {
		return SecretOutputDeliveryOperation{Status: "ACK_PENDING", Package: selected, Directory: receipt.Directory, Error: &ProjectOpenError{Code: ack.State, Message: "Файлы сохранены; Execution Node ещё не завершил очистку временной копии."}}
	}
	return SecretOutputDeliveryOperation{Status: "DELIVERED", Package: selected, Directory: receipt.Directory}
}

func (a *App) credentialBindingLockedForOutput(root, projectID string) (runtimesecret.Binding, error) {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	if a.current.Status != "OPEN" || a.current.Root != root || a.current.Project == nil || a.current.Project.ID != projectID {
		return runtimesecret.Binding{}, errors.New("PROJECT_CHANGED")
	}
	return runtimesecret.Binding{Root: root, ID: projectID}, nil
}

func secretOutputDeliveryFailure(code, message string) SecretOutputDeliveryOperation {
	return SecretOutputDeliveryOperation{Status: "UNAVAILABLE", Error: &ProjectOpenError{Code: code, Message: message}}
}
