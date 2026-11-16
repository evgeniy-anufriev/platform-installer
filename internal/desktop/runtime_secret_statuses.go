package desktop

type RuntimeSecretStatuses struct {
	ProjectRevision string                     `json:"projectRevision,omitempty"`
	Services        map[string]bool            `json:"services,omitempty"`
	Applications    map[string]map[string]bool `json:"applications,omitempty"`
}

// GetRuntimeSecretStatuses projects the same session presence as the editors.
// Only scopes with at least one session input appear in the result. The
// projection uses the loaded saved view and does not reread project files.
func (a *App) GetRuntimeSecretStatuses(section string) RuntimeSecretStatuses {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	managed := a.current.Managed
	if a.current.Status != "OPEN" || managed == nil {
		return RuntimeSecretStatuses{}
	}
	binding, err := a.credentialBindingLocked()
	if err != nil {
		return RuntimeSecretStatuses{}
	}
	result := RuntimeSecretStatuses{ProjectRevision: managed.ProjectRevision}
	switch section {
	case "services":
		result.Services = make(map[string]bool)
		for deployment := range managed.Deployments {
			descriptors, err := a.pendingRuntimeSecretDescriptorsLocked(deployment)
			if err == nil && len(descriptors) > 0 {
				result.Services[deployment] = a.serviceSecretsPresent(binding, descriptors)
			}
		}
	case "applications":
		result.Applications = make(map[string]map[string]bool)
		for library, definition := range managed.ApplicationLibraries {
			slots := []string{""} // Library-level provided connection credentials.
			for slot := range secretObject(definition["applications"]) {
				slots = append(slots, slot)
			}
			for _, slot := range slots {
				items, err := a.savedApplicationSecretsLocked(PendingApplicationSecretContext{
					ApplicationLibrary: library, ApplicationSlot: slot,
				})
				if err != nil || len(items) == 0 {
					continue
				}
				keys := make([]string, 0, len(items))
				for _, item := range items {
					keys = append(keys, item.key)
				}
				presence := a.secrets.PendingApplicationSecretPresence(binding, keys)
				installed := true
				for _, key := range keys {
					installed = installed && presence[key]
				}
				if result.Applications[library] == nil {
					result.Applications[library] = make(map[string]bool)
				}
				result.Applications[library][slot] = installed
			}
		}
	}
	return result
}
