package executionnode

import (
	"fmt"
	"strings"
	"testing"
)

func TestSecretValuesAreBoundedByBytesInsteadOfQuantity(t *testing.T) {
	values := map[string]string{}
	for i := 0; i < 80; i++ {
		values[fmt.Sprintf("secret-%d", i)] = "synthetic"
	}
	if !validRuntimeSecretValues(values) {
		t.Fatal("valid large set rejected")
	}
	values["secret-0"] = strings.Repeat("x", 4097)
	if validRuntimeSecretValues(values) {
		t.Fatal("per-value limit bypassed")
	}
	for k := range values {
		values[k] = strings.Repeat("x", 1024)
	}
	if validRuntimeSecretValues(values) {
		t.Fatal("aggregate limit bypassed")
	}
}
