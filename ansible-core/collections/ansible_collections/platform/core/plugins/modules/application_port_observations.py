"""Read-only checks for the unique TCP ports required by placements."""
import socket

from ansible.module_utils.basic import AnsibleModule


def main():
    module = AnsibleModule(
        argument_spec=dict(ports=dict(type='dict', required=True)),
        supports_check_mode=True,
    )
    for port, placements in module.params['ports'].items():
        try:
            number = int(port)
            if not 1 <= number <= 65535:
                raise ValueError()
        except ValueError:
            module.fail_json(msg='APPLICATION_PUBLISHED_PORT_INVALID', placements=placements)
        with socket.socket() as probe:
            probe.settimeout(1)
            try:
                occupied = probe.connect_ex(('127.0.0.1', number)) == 0
            except TimeoutError:
                occupied = False
        if occupied:
            module.fail_json(msg='APPLICATION_PUBLISHED_PORT_OCCUPIED', port=number, placements=placements)
    module.exit_json(changed=False)


if __name__ == '__main__':
    main()
