//go:build !dev

package desktop

// Production never reads QA file selections or installs a replacement picker.
func configureQASecretFileSelection(*App) error { return nil }
