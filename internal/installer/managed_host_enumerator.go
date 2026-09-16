package installer

import "sort"

// enumerateManagedHostDocuments discovers only fixed managed host-var
// candidates. Content and ownership are verified later from the exact opened
// file object by managedReadBudget.ownedDocumentOptional.
func enumerateManagedHostDocuments(root string) ([]string, error) {
	names, err := enumerateManagedHostDirectories(root, maxManagedHostDocuments)
	if err != nil {
		return nil, managedReadError("Managed host document collection is unsafe or exceeds its limit", "inventory/host_vars")
	}
	paths := make([]string, 0, len(names))
	for _, name := range names {
		if !identifierPattern.MatchString(name) {
			return nil, managedReadError("Managed host document identifier is invalid", "inventory/host_vars")
		}
		paths = append(paths, managedHostDocument(name))
	}
	sort.Strings(paths)
	return paths, nil
}
