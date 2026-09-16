package installer

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestReadManagedProjectViewProjectsOnlyOwnedTopologyFields(t *testing.T) {
	root := managedReadProject(t)
	view, err := ReadManagedProjectView(root)
	if err != nil {
		t.Fatal(err)
	}
	if view.ProjectRevision == "" || len(view.Servers) != 1 || view.Deployments["kafka-main"].ServiceType != "kafka" || view.EndpointGroups["edge"].Domain == "" {
		t.Fatalf("view=%#v", view)
	}
	if len(view.MemberPlacements) == 0 || len(view.HostPlacements) == 0 {
		t.Fatalf("placements were not projected: %#v", view)
	}
	for _, placement := range view.MemberPlacements {
		if placement.MemberID == "" || placement.HostID == "" {
			t.Fatalf("invalid member placement: %#v", placement)
		}
	}
}

func TestReadManagedProjectViewProjectsProviderStatesWithoutLoss(t *testing.T) {
	cases := map[string]struct {
		provider  string
		wantState string
	}{
		"editable":              {"      endpointGroupRef: edge\n      virtualRouterId: 42\n      virtualAddresses:\n        - {address: 192.0.2.42, interface: eth0}\n", "EDITABLE"},
		"incomplete":            {"      endpointGroupRef: edge\n", "INCOMPLETE"},
		"unsupported interface": {"      endpointGroupRef: edge\n      virtualRouterId: 42\n      virtualAddresses:\n        - {address: 192.0.2.42, interface: " + strings.Repeat("e", 129) + "}\n", "UNSUPPORTED"},
	}
	for name, testCase := range cases {
		t.Run(name, func(t *testing.T) {
			root := managedReadProject(t)
			desired := string(managedHeader) + "platform_desired_state:\n  endpointGroups:\n    edge:\n      address: {domain: edge.example.test, wildcard: true}\n  serviceDeployments:\n    provider:\n      serviceType: keepalived\n      mode: vrrp\n" + testCase.provider
			path := filepath.Join(root, "inventory", "group_vars", "all", "platform-installer.yml")
			if err := os.WriteFile(path, []byte(desired), 0o600); err != nil {
				t.Fatal(err)
			}
			view, err := ReadManagedProjectView(root)
			if err != nil {
				t.Fatal(err)
			}
			got := view.Deployments["provider"]
			if got.ProviderEditState != testCase.wantState {
				t.Fatalf("provider state = %q, want %q", got.ProviderEditState, testCase.wantState)
			}
			if name == "incomplete" && got.EndpointGroupRef != "edge" {
				t.Fatalf("incomplete reference was lost: %#v", got)
			}
			if name == "unsupported interface" && (len(got.VirtualAddresses) != 1 || len(got.VirtualAddresses[0].Interface) != 129) {
				t.Fatalf("unsupported value was truncated: %#v", got)
			}
		})
	}
}

func TestReadManagedProjectViewProjectsLegacyProviderAddressListReadOnly(t *testing.T) {
	root := managedReadProject(t)
	var addresses strings.Builder
	for index := 0; index < 65; index++ {
		addresses.WriteString(fmt.Sprintf("        - {address: 192.0.2.%d, interface: eth0}\n", index+1))
	}
	desired := string(managedHeader) + "platform_desired_state:\n  endpointGroups:\n    edge:\n      address: {domain: edge.example.test, wildcard: true}\n  serviceDeployments:\n    provider:\n      serviceType: keepalived\n      mode: vrrp\n      endpointGroupRef: edge\n      virtualRouterId: 42\n      virtualAddresses:\n" + addresses.String()
	path := filepath.Join(root, "inventory", "group_vars", "all", "platform-installer.yml")
	if err := os.WriteFile(path, []byte(desired), 0o600); err != nil {
		t.Fatal(err)
	}
	view, err := ReadManagedProjectView(root)
	if err != nil {
		t.Fatal(err)
	}
	provider := view.Deployments["provider"]
	if provider.ProviderEditState != "UNSUPPORTED" || len(provider.VirtualAddresses) != 65 {
		t.Fatalf("provider=%#v", provider)
	}
}

func TestReadManagedProjectViewRejectsSymlinkAndDuplicateKnownFields(t *testing.T) {
	root := managedReadProject(t)
	desired := filepath.Join(root, "inventory", "group_vars", "all", "platform-installer.yml")
	if err := os.Remove(desired); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink(filepath.Join(root, "inventory", "hosts.yml"), desired); err != nil {
		t.Skipf("symlink creation is unavailable: %v", err)
	}
	if _, err := ReadManagedProjectView(root); err == nil || err.Error() != "MANAGED_DOCUMENT_INVALID" {
		t.Fatalf("symlink err=%v", err)
	}

	root = managedReadProject(t)
	duplicate := string(managedHeader) + "platform_desired_state:\n  serviceDeployments: {}\n  serviceDeployments: {}\n  endpointGroups: {}\n"
	if err := os.WriteFile(filepath.Join(root, "inventory", "group_vars", "all", "platform-installer.yml"), []byte(duplicate), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := ReadManagedProjectView(root); err == nil || err.Error() != "MANAGED_DOCUMENT_INVALID" {
		t.Fatalf("duplicate err=%v", err)
	}
}

func TestReadManagedProjectViewEnforcesPerFileAndAggregateLimitsWithoutPartialView(t *testing.T) {
	root := managedReadProject(t)
	path := filepath.Join(root, "inventory", "group_vars", "all", "platform-installer.yml")
	if err := os.WriteFile(path, append([]byte(string(managedHeader)+"platform_desired_state:\n  serviceDeployments: {}\n  endpointGroups: {}\n# "), []byte(strings.Repeat("x", int(maxManagedDocumentBytes)))...), 0o600); err != nil {
		t.Fatal(err)
	}
	if view, err := ReadManagedProjectView(root); err == nil || view != nil {
		t.Fatalf("per-file view=%#v err=%v", view, err)
	}

	root = managedReadProject(t)
	var hosts strings.Builder
	hosts.WriteString(string(managedHeader) + "all:\n  hosts:\n")
	for i := 0; i < 17; i++ {
		hosts.WriteString("    node" + string(rune('a'+i)) + ":\n      ansible_host: 192.0.2.10\n      platform_host: {type: infra}\n")
	}
	hosts.WriteString("  children:\n    platform_targets:\n      hosts:\n")
	large := string(managedHeader) + "platform_deployments: {}\n# " + strings.Repeat("x", int(maxManagedDocumentBytes)-128)
	for i := 0; i < 17; i++ {
		id := "node" + string(rune('a'+i))
		hosts.WriteString("        " + id + ": {}\n")
		dir := filepath.Join(root, "inventory", "host_vars", id)
		if err := os.MkdirAll(dir, 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(filepath.Join(dir, "platform-installer.yml"), []byte(large), 0o600); err != nil {
			t.Fatal(err)
		}
	}
	if err := os.WriteFile(filepath.Join(root, "inventory", "hosts.yml"), []byte(hosts.String()), 0o600); err != nil {
		t.Fatal(err)
	}
	if view, err := ReadManagedProjectView(root); err == nil || view != nil {
		t.Fatalf("aggregate view=%#v err=%v", view, err)
	}
}

func TestReadManagedProjectViewEnforcesCollectionLimits(t *testing.T) {
	t.Run("servers", func(t *testing.T) {
		root := managedReadProject(t)
		var inventory strings.Builder
		inventory.WriteString(string(managedHeader) + "all:\n  hosts:\n")
		for index := 0; index <= maxManagedEntities; index++ {
			id := fmt.Sprintf("node-%04d", index)
			inventory.WriteString("    " + id + ": {ansible_host: 192.0.2.10, platform_host: {type: infra}}\n")
		}
		inventory.WriteString("  children:\n    platform_targets:\n      hosts:\n")
		for index := 0; index <= maxManagedEntities; index++ {
			inventory.WriteString(fmt.Sprintf("        node-%04d: {}\n", index))
		}
		if err := os.WriteFile(filepath.Join(root, "inventory", "hosts.yml"), []byte(inventory.String()), 0o600); err != nil {
			t.Fatal(err)
		}
		assertManagedReadBlocked(t, root)
	})
	for name, content := range map[string]string{
		"deployments":     oversizedDesiredState("serviceDeployments", maxManagedEntities+1),
		"endpoint groups": oversizedDesiredState("endpointGroups", maxManagedEntities+1),
	} {
		t.Run(name, func(t *testing.T) {
			root := managedReadProject(t)
			if err := os.WriteFile(filepath.Join(root, "inventory", "group_vars", "all", "platform-installer.yml"), []byte(content), 0o600); err != nil {
				t.Fatal(err)
			}
			assertManagedReadBlocked(t, root)
		})
	}
	t.Run("placements", func(t *testing.T) {
		root := managedReadProject(t)
		var host strings.Builder
		host.WriteString(string(managedHeader) + "platform_deployments:\n  deploy-main:\n    members:\n")
		for index := 0; index <= maxManagedPlacements; index++ {
			host.WriteString(fmt.Sprintf("      member-%05d: {roles: [role]}\n", index))
		}
		if err := os.WriteFile(filepath.Join(root, "inventory", "host_vars", "node1", "platform-installer.yml"), []byte(host.String()), 0o600); err != nil {
			t.Fatal(err)
		}
		assertManagedReadBlocked(t, root)
	})
	t.Run("roles", func(t *testing.T) {
		root := managedReadProject(t)
		roles := make([]string, 0, maxManagedRoles+1)
		for index := 0; index <= maxManagedRoles; index++ {
			roles = append(roles, fmt.Sprintf("role-%03d", index))
		}
		content := string(managedHeader) + "platform_deployments:\n  deploy-main:\n    roles: [" + strings.Join(roles, ", ") + "]\n"
		if err := os.WriteFile(filepath.Join(root, "inventory", "host_vars", "node1", "platform-installer.yml"), []byte(content), 0o600); err != nil {
			t.Fatal(err)
		}
		assertManagedReadBlocked(t, root)
	})
}

func oversizedDesiredState(kind string, count int) string {
	var result strings.Builder
	result.WriteString(string(managedHeader) + "platform_desired_state:\n")
	if kind == "serviceDeployments" {
		result.WriteString("  endpointGroups: {}\n")
	} else {
		result.WriteString("  serviceDeployments: {}\n")
	}
	result.WriteString("  " + kind + ":\n")
	for index := 0; index < count; index++ {
		if kind == "serviceDeployments" {
			result.WriteString(fmt.Sprintf("    deploy-%04d: {serviceType: kafka, mode: single}\n", index))
		} else {
			result.WriteString(fmt.Sprintf("    group-%04d: {address: {domain: edge.example.test, wildcard: false}}\n", index))
		}
	}
	return result.String()
}

func assertManagedReadBlocked(t *testing.T, root string) {
	t.Helper()
	if view, err := ReadManagedProjectView(root); err == nil || view != nil {
		t.Fatalf("view=%#v err=%v", view, err)
	}
}

func TestReadManagedProjectViewRejectsAmbiguousPlacementSyntax(t *testing.T) {
	root := managedReadProject(t)
	path := filepath.Join(root, "inventory", "host_vars", "node1", "platform-installer.yml")
	content := string(managedHeader) + "platform_deployments:\n  kafka-main:\n    members: {}\n    roles: [broker]\n"
	if err := os.WriteFile(path, []byte(content), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := ReadManagedProjectView(root); err == nil || err.Error() != "MANAGED_DOCUMENT_INVALID" {
		t.Fatalf("err=%v", err)
	}
}

func managedReadProject(t *testing.T) string {
	t.Helper()
	root := t.TempDir()
	for _, directory := range []string{"inventory/group_vars/all", "inventory/host_vars/node1"} {
		if err := os.MkdirAll(filepath.Join(root, directory), 0o755); err != nil {
			t.Fatal(err)
		}
	}
	inventory := string(managedHeader) + "all:\n  hosts:\n    node1:\n      ansible_host: 192.0.2.10\n      platform_host:\n        type: infra\n  children:\n    platform_targets:\n      hosts:\n        node1: {}\n"
	desired := string(managedHeader) + "platform_desired_state:\n  endpointGroups:\n    edge:\n      address:\n        domain: edge.example.test\n        wildcard: true\n  serviceDeployments:\n    kafka-main:\n      serviceType: kafka\n      mode: kraft-standalone\n      endpointGroup: edge\n"
	host := string(managedHeader) + "platform_deployments:\n  kafka-main:\n    members:\n      kafka-1:\n        roles: [broker, controller]\n  dns-main:\n    roles: [primary]\n"
	for path, content := range map[string]string{
		"inventory/hosts.yml":                              inventory,
		"inventory/group_vars/all/platform-installer.yml":  desired,
		"inventory/host_vars/node1/platform-installer.yml": host,
	} {
		if err := os.WriteFile(filepath.Join(root, filepath.FromSlash(path)), []byte(content), 0o600); err != nil {
			t.Fatal(err)
		}
	}
	return root
}
