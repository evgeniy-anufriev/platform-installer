# platform.docker

Standalone Ansible role for rootless Docker Engine and the Docker Compose CLI
plugin. It requires a pre-existing Core PKI materialization plan or the
documented `platform_docker_tls_directory` for manual inventory use.
Create-user mode obtains its password only from the controller-local runtime
file mapping `platform_docker_secret_files[passwordSecretRef]`. No password
belongs in project, inventory, extra-vars or playbook output.
