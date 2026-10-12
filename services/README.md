# Service packages

Each directory is a versioned service capability package containing its
manifest, configuration schema, compatibility and artifact metadata, examples,
tests, and independently usable Ansible collection. The future Installer reads
these packages; it does not own a parallel service catalog.

Команды оператора и разграничение редактируемого inventory от generated/runtime
файлов приведены в [общем guide playbooks](../docs/guides/ansible-playbooks/README.md).
