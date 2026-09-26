package secretoutputwire

import (
	"bytes"
	"encoding/json"
	"errors"
	"unicode/utf8"
)

const Protocol = "SecretOutputDelivery/v1alpha1"
const MaxRequestBytes = 8192

var ErrRequest = errors.New("OUTPUT_REQUEST_INVALID")

// Request contains only non-secret protocol control fields. It is not a
// credential payload, a filesystem location or an authorization decision.
type Request struct {
	Protocol           string            `json:"protocol"`
	Operation          string            `json:"operation"`
	ProjectID          string            `json:"projectId"`
	Limit              int               `json:"limit,omitempty"`
	Cursor             string            `json:"cursor,omitempty"`
	PackageID          string            `json:"packageId,omitempty"`
	ExpectedGeneration int               `json:"expectedGeneration,omitempty"`
	ReceiptID          string            `json:"receiptId,omitempty"`
	CiphertextDigests  map[string]string `json:"ciphertextDigests,omitempty"`
}

// DecodeRequest admits exactly the closed request contract. Field presence is
// checked separately so omitted, zero and null cannot silently collapse.
func DecodeRequest(data []byte) (Request, error) {
	var r Request
	if len(data) == 0 || len(data) > MaxRequestBytes || !utf8.Valid(data) || !uniqueFlatObject(data) {
		return r, ErrRequest
	}
	var fields map[string]json.RawMessage
	if json.Unmarshal(data, &fields) != nil {
		return r, ErrRequest
	}
	d := json.NewDecoder(bytes.NewReader(data))
	d.DisallowUnknownFields()
	if d.Decode(&r) != nil || r.Protocol != Protocol || !project.MatchString(r.ProjectID) {
		return Request{}, ErrRequest
	}
	required := []string{"protocol", "operation", "projectId"}
	optional := []string{}
	switch r.Operation {
	case "GetCapabilities":
	case "ListPending":
		required = append(required, "limit")
		optional = append(optional, "cursor")
		if r.Limit < 1 || r.Limit > 32 {
			return Request{}, ErrRequest
		}
		if _, exists := fields["cursor"]; exists && !opaque.MatchString(r.Cursor) {
			return Request{}, ErrRequest
		}
	case "Fetch", "Acknowledge":
		required = append(required, "packageId", "expectedGeneration")
		if !opaque.MatchString(r.PackageID) || r.ExpectedGeneration < 1 || r.ExpectedGeneration > 2147483647 {
			return Request{}, ErrRequest
		}
		if r.Operation == "Acknowledge" {
			required = append(required, "receiptId", "ciphertextDigests")
			if !opaque.MatchString(r.ReceiptID) || !uniqueFlatObject(fields["ciphertextDigests"]) || len(r.CiphertextDigests) != 2 ||
				!digest.MatchString(r.CiphertextDigests["admin-token"]) || !digest.MatchString(r.CiphertextDigests["unseal-shares"]) {
				return Request{}, ErrRequest
			}
		}
	default:
		return Request{}, ErrRequest
	}
	allowed := make(map[string]bool, len(required)+len(optional))
	for _, key := range required {
		value, exists := fields[key]
		if !exists || bytes.Equal(bytes.TrimSpace(value), []byte("null")) {
			return Request{}, ErrRequest
		}
		allowed[key] = true
	}
	for _, key := range optional {
		allowed[key] = true
	}
	for key := range fields {
		if !allowed[key] {
			return Request{}, ErrRequest
		}
	}
	return r, nil
}
