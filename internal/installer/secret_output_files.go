package installer

import (
	"bytes"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"io"
	"path/filepath"
	"regexp"
)

var (
	secretOutputProjectID    = regexp.MustCompile(`^[a-z0-9][a-z0-9-]{0,127}$`)
	secretOutputDeploymentID = regexp.MustCompile(`^[a-z][a-z0-9]*(?:[-_.][a-z0-9]+)*$`)
	secretOutputPackageID    = regexp.MustCompile(`^[0-9a-f]{32}$`)
	secretOutputRunID        = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$`)
	secretOutputDigest       = regexp.MustCompile(`^sha256:[0-9a-f]{64}$`)
)

var ErrSecretOutputFiles = errors.New("SECRET_OUTPUT_FILES_UNAVAILABLE")

type SecretOutputStagingRetainedError struct{ Path string }

func (*SecretOutputStagingRetainedError) Error() string { return "EXPORT_STAGING_RETAINED" }

type SecretOutputFileReceipt struct {
	ReceiptID     string            `json:"receiptId"`
	Directory     string            `json:"directory"`
	Digests       map[string]string `json:"ciphertextDigests"`
	ProjectID     string            `json:"projectId"`
	DeploymentID  string            `json:"deploymentId"`
	PackageID     string            `json:"packageId"`
	SourceRunID   string            `json:"sourceRunId"`
	Generation    int               `json:"generation"`
	RuntimeDigest string            `json:"runtimeDigest"`
}

type secretOutputLocalReceipt struct {
	SchemaVersion int               `json:"schemaVersion"`
	ProjectID     string            `json:"projectId"`
	DeploymentID  string            `json:"deploymentId"`
	PackageID     string            `json:"packageId"`
	SourceRunID   string            `json:"sourceRunId"`
	Generation    int               `json:"generation"`
	RuntimeDigest string            `json:"runtimeDigest"`
	ReceiptID     string            `json:"receiptId"`
	Entries       []string          `json:"entries"`
	Digests       map[string]string `json:"ciphertextDigests"`
}

// PublishSecretOutputFiles writes only the two encrypted, fixed-name output
// entries and their completion receipt. It uses the existing platform-safe
// directory-handle writer, never overwrites a package, and publishes by one
// no-replace directory rename. On failure it does not guess that pathname
// cleanup is identity-safe.
func PublishSecretOutputFiles(parent, projectID, deploymentID, packageID, sourceRunID string, generation int, runtimeDigest string, adminTokenAge, unsealSharesAge []byte) (SecretOutputFileReceipt, error) {
	return publishSecretOutputFiles(parent, projectID, deploymentID, packageID, sourceRunID, generation, runtimeDigest, adminTokenAge, unsealSharesAge, nil)
}

// Fault injection stays local to this publication operation; production has
// no global hooks or alternate writer.
func publishSecretOutputFiles(parent, projectID, deploymentID, packageID, sourceRunID string, generation int, runtimeDigest string, adminTokenAge, unsealSharesAge []byte, before func(string) error) (SecretOutputFileReceipt, error) {
	check := func(stage string) error {
		if before != nil {
			return before(stage)
		}
		return nil
	}
	if parent == "" || !secretOutputProjectID.MatchString(projectID) || !secretOutputDeploymentID.MatchString(deploymentID) || !secretOutputPackageID.MatchString(packageID) || !secretOutputRunID.MatchString(sourceRunID) || generation < 1 || !secretOutputDigest.MatchString(runtimeDigest) || len(adminTokenAge) == 0 || len(adminTokenAge) > 131072 || len(unsealSharesAge) == 0 || len(unsealSharesAge) > 131072 {
		return SecretOutputFileReceipt{}, ErrSecretOutputFiles
	}
	var random [16]byte
	if _, err := rand.Read(random[:]); err != nil {
		return SecretOutputFileReceipt{}, ErrSecretOutputFiles
	}
	receiptID := hex.EncodeToString(random[:])
	digests := map[string]string{"admin-token": ciphertextDigest(adminTokenAge), "unseal-shares": ciphertextDigest(unsealSharesAge)}
	name := deploymentID
	receipt := secretOutputLocalReceipt{SchemaVersion: 1, ProjectID: projectID, DeploymentID: deploymentID, PackageID: packageID, SourceRunID: sourceRunID, Generation: generation, RuntimeDigest: runtimeDigest, ReceiptID: receiptID, Entries: []string{"admin-token", "unseal-shares"}, Digests: digests}
	encodedReceipt, err := json.Marshal(receipt)
	if err != nil {
		return SecretOutputFileReceipt{}, ErrSecretOutputFiles
	}
	root, err := openExportDestinationDirectory(parent)
	if err != nil {
		return SecretOutputFileReceipt{}, ErrSecretOutputFiles
	}
	defer root.close()
	projectRoot := root
	secrets, err := root.createDirectory("secrets")
	if err != nil {
		secrets, err = openSecretOutputDirectory(root, []string{"secrets"})
	}
	if err != nil {
		return SecretOutputFileReceipt{}, ErrSecretOutputFiles
	}
	defer secrets.close()
	if check("project-flush") != nil || syncSecretOutputDirectory(projectRoot) != nil {
		return SecretOutputFileReceipt{}, ErrSecretOutputFiles
	}
	root = secrets
	parent = filepath.Join(parent, "secrets")
	staging, stagingName, err := root.createStaging(name)
	if err != nil {
		return SecretOutputFileReceipt{}, ErrSecretOutputFiles
	}
	defer staging.close()
	retained := func() error {
		path := filepath.Join(parent, stagingName)
		if len(path) > 4096 {
			path = ""
		}
		return &SecretOutputStagingRetainedError{Path: path}
	}
	entries := []struct {
		name string
		data []byte
	}{{"admin-token.age", adminTokenAge}, {"unseal-shares.age", unsealSharesAge}}
	for _, entry := range entries {
		if err := staging.writeFile(entry.name, entry.data); err != nil {
			return SecretOutputFileReceipt{}, retained()
		}
		readBack, _, err := staging.readFile([]string{entry.name}, 131072)
		if err != nil || len(readBack) != len(entry.data) || ciphertextDigest(readBack) != ciphertextDigest(entry.data) {
			return SecretOutputFileReceipt{}, retained()
		}
	}
	if err := staging.writeFile("complete", encodedReceipt); err != nil {
		return SecretOutputFileReceipt{}, retained()
	}
	readBack, _, err := staging.readFile([]string{"complete"}, 8192)
	if err != nil || string(readBack) != string(encodedReceipt) {
		return SecretOutputFileReceipt{}, retained()
	}
	if check("staging-flush") != nil || syncSecretOutputDirectory(staging) != nil {
		return SecretOutputFileReceipt{}, retained()
	}
	if check("publish") != nil {
		return SecretOutputFileReceipt{}, retained()
	}
	if err := root.publish(staging, stagingName, name); err != nil {
		return SecretOutputFileReceipt{}, retained()
	}
	if check("published-flush") != nil {
		return SecretOutputFileReceipt{}, ErrSecretOutputFiles
	}
	published, err := root.openDirectory([]string{name})
	if err != nil {
		return SecretOutputFileReceipt{}, ErrSecretOutputFiles
	}
	defer published.close()
	if published.identity() != staging.identity() || syncSecretOutputDirectory(staging) != nil || syncSecretOutputDirectory(root) != nil {
		return SecretOutputFileReceipt{}, ErrSecretOutputFiles
	}
	for _, entry := range append(entries, struct {
		name string
		data []byte
	}{"complete", encodedReceipt}) {
		data, _, readErr := published.readFile([]string{entry.name}, 131072)
		if readErr != nil || !bytes.Equal(data, entry.data) {
			return SecretOutputFileReceipt{}, ErrSecretOutputFiles
		}
	}
	if check("binding-readback") != nil {
		return SecretOutputFileReceipt{}, ErrSecretOutputFiles
	}
	currentRoot, err := openExportDestinationDirectory(filepath.Dir(parent))
	if err != nil {
		return SecretOutputFileReceipt{}, ErrSecretOutputFiles
	}
	defer currentRoot.close()
	currentSecrets, err := currentRoot.openDirectory([]string{"secrets"})
	if err != nil {
		return SecretOutputFileReceipt{}, ErrSecretOutputFiles
	}
	defer currentSecrets.close()
	if currentRoot.identity() != projectRoot.identity() || currentSecrets.identity() != root.identity() {
		return SecretOutputFileReceipt{}, ErrSecretOutputFiles
	}
	return SecretOutputFileReceipt{ReceiptID: receiptID, Directory: filepath.Join(parent, name), Digests: digests, ProjectID: projectID, DeploymentID: deploymentID, PackageID: packageID, SourceRunID: sourceRunID, Generation: generation, RuntimeDigest: runtimeDigest}, nil
}

// ReadSecretOutputFiles verifies a previously published package through the
// same safe opened-directory primitives. It returns only encrypted bytes and
// never follows a substituted package/file path.
func ReadSecretOutputFiles(parent, projectID, deploymentID, packageID, sourceRunID string, generation int, runtimeDigest string) (SecretOutputFileReceipt, map[string][]byte, error) {
	if parent == "" || !secretOutputProjectID.MatchString(projectID) || !secretOutputDeploymentID.MatchString(deploymentID) || !secretOutputPackageID.MatchString(packageID) || !secretOutputRunID.MatchString(sourceRunID) || generation < 1 || !secretOutputDigest.MatchString(runtimeDigest) {
		return SecretOutputFileReceipt{}, nil, ErrSecretOutputFiles
	}
	root, err := openExportDestinationDirectory(parent)
	if err != nil {
		return SecretOutputFileReceipt{}, nil, ErrSecretOutputFiles
	}
	defer root.close()
	name := deploymentID
	projectRoot := root
	secrets, err := openSecretOutputDirectory(root, []string{"secrets"})
	if err != nil {
		return SecretOutputFileReceipt{}, nil, ErrSecretOutputFiles
	}
	defer secrets.close()
	root = secrets
	parent = filepath.Join(parent, "secrets")
	directory, err := openSecretOutputDirectory(root, []string{name})
	if err != nil {
		return SecretOutputFileReceipt{}, nil, ErrSecretOutputFiles
	}
	defer directory.close()
	encoded, _, err := directory.readFile([]string{"complete"}, 8192)
	var receipt secretOutputLocalReceipt
	decoder := json.NewDecoder(bytes.NewReader(encoded))
	decoder.DisallowUnknownFields()
	if err != nil || decoder.Decode(&receipt) != nil || receipt.SchemaVersion != 1 || receipt.ProjectID != projectID || receipt.DeploymentID != deploymentID || receipt.PackageID != packageID || receipt.SourceRunID != sourceRunID || receipt.Generation != generation || receipt.RuntimeDigest != runtimeDigest || !secretOutputPackageID.MatchString(receipt.ReceiptID) || len(receipt.Entries) != 2 || receipt.Entries[0] != "admin-token" || receipt.Entries[1] != "unseal-shares" || len(receipt.Digests) != 2 {
		return SecretOutputFileReceipt{}, nil, ErrSecretOutputFiles
	}
	var trailing any
	if decoder.Decode(&trailing) != io.EOF {
		return SecretOutputFileReceipt{}, nil, ErrSecretOutputFiles
	}
	ciphertexts := make(map[string][]byte, 2)
	for _, entry := range []struct{ id, file string }{{"admin-token", "admin-token.age"}, {"unseal-shares", "unseal-shares.age"}} {
		data, _, readErr := directory.readFile([]string{entry.file}, 131072)
		if readErr != nil || !secretOutputDigest.MatchString(receipt.Digests[entry.id]) || ciphertextDigest(data) != receipt.Digests[entry.id] {
			for _, value := range ciphertexts {
				clear(value)
			}
			clear(data)
			return SecretOutputFileReceipt{}, nil, ErrSecretOutputFiles
		}
		ciphertexts[entry.id] = data
	}
	if syncSecretOutputDirectory(directory) != nil || syncSecretOutputDirectory(root) != nil || syncSecretOutputDirectory(projectRoot) != nil {
		for _, data := range ciphertexts {
			clear(data)
		}
		return SecretOutputFileReceipt{}, nil, ErrSecretOutputFiles
	}
	return SecretOutputFileReceipt{ReceiptID: receipt.ReceiptID, Directory: filepath.Join(parent, name), Digests: receipt.Digests, ProjectID: projectID, DeploymentID: deploymentID, PackageID: packageID, SourceRunID: sourceRunID, Generation: generation, RuntimeDigest: runtimeDigest}, ciphertexts, nil
}

func ciphertextDigest(data []byte) string {
	digest := sha256.Sum256(data)
	return "sha256:" + hex.EncodeToString(digest[:])
}

// ReadSecretOutputReceipt discovers binding only at one canonical deployment
// path supplied by the managed projection, never by directory scanning.
func ReadSecretOutputReceipt(rootPath, projectID, deploymentID, runtimeDigest string) (SecretOutputFileReceipt, map[string][]byte, error) {
	if !secretOutputDeploymentID.MatchString(deploymentID) {
		return SecretOutputFileReceipt{}, nil, ErrSecretOutputFiles
	}
	root, err := openExportSourceDirectory(rootPath)
	if err != nil {
		return SecretOutputFileReceipt{}, nil, ErrSecretOutputFiles
	}
	defer root.close()
	dir, err := root.openDirectory([]string{"secrets", deploymentID})
	if err != nil {
		return SecretOutputFileReceipt{}, nil, ErrSecretOutputFiles
	}
	defer dir.close()
	data, _, err := dir.readFile([]string{"complete"}, 8192)
	var receipt secretOutputLocalReceipt
	if err != nil || json.Unmarshal(data, &receipt) != nil {
		return SecretOutputFileReceipt{}, nil, ErrSecretOutputFiles
	}
	return ReadSecretOutputFiles(rootPath, projectID, deploymentID, receipt.PackageID, receipt.SourceRunID, receipt.Generation, runtimeDigest)
}
