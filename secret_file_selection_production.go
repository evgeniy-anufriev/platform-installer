//go:build !dev

package main

// Production never reads QA file selections or installs a replacement picker.
func configureQASecretFileSelection(*App) error { return nil }
