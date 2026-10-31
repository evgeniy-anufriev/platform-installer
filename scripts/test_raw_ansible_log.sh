sudo find /var/lib/platform-installer/execution \
  -type f -path '*/raw-ansible-diagnostics/ansible-output-*.log' \
  -printf '%T@ %p\n' | sort -nr | head -5
