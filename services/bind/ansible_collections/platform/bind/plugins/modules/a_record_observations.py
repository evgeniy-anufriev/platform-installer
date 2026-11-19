"""Observe the exact A-record sets of a single local authoritative zone."""
import ipaddress
import re

from ansible.module_utils.basic import AnsibleModule


LABEL = r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?'
DOMAIN = rf'(?:{LABEL}\.)+[a-z]{{2,63}}'
HEADER = re.compile(r'^;; ->>HEADER<<- .*?status: ([A-Z]+),.*$', re.M)


def ipv4(value):
    return isinstance(value, str) and str(ipaddress.IPv4Address(value)) == value


def checked_records(records):
    if not records:
        raise ValueError('BIND_DNS_A_RECORD_UPDATE_INPUT_INVALID')
    zones, owners = set(), set()
    for record in records:
        zone, owner = record.get('zone'), record.get('owner')
        addresses, ttl = record.get('addresses'), record.get('ttl')
        if (not isinstance(zone, str) or len(zone) > 253 or not re.fullmatch(DOMAIN, zone) or
                not isinstance(owner, str) or len(owner) > 254 or
                not re.fullmatch(rf'(?:\*\.)?{DOMAIN}\.', owner) or
                not owner.endswith('.' + zone + '.') or owner in owners or
                not isinstance(addresses, list) or not addresses or
                type(ttl) not in (int, str) or not re.fullmatch(r'[0-9]{1,10}', str(ttl)) or
                not 1 <= int(ttl) <= 2147483647):
            raise ValueError('BIND_DNS_A_RECORD_UPDATE_INPUT_INVALID')
        try:
            valid = all(ipv4(address) for address in addresses)
        except ValueError:
            valid = False
        if not valid:
            raise ValueError('BIND_DNS_A_RECORD_UPDATE_ADDRESS_INVALID')
        if len(set(addresses)) != len(addresses):
            raise ValueError('BIND_DNS_A_RECORD_UPDATE_INPUT_INVALID')
        owners.add(owner)
        zones.add(zone)
    if len(zones) != 1:
        raise ValueError('BIND_DNS_A_RECORD_UPDATE_INPUT_INVALID')
    return sorted(records, key=lambda record: record['owner'])


def observations(records, output, force=False):
    blocks = HEADER.split(output)
    expected = {record['owner']: record for record in records}
    results = {}
    for status, block in zip(blocks[1::2], blocks[2::2]):
        flags = re.search(r'^;; flags: ([^;]+);', block, re.M)
        question = re.findall(r'^;([^;\s]+)\s+IN\s+A\s*$', block, re.M)
        if (status not in ('NOERROR', 'NXDOMAIN') or not flags or
                not {'qr', 'aa'} <= set(flags[1].split()) or
                'tc' in flags[1].split() or
                len(question) != 1 or question[0].lower() not in expected or
                question[0].lower() in results):
            raise ValueError('BIND_DNS_A_RECORD_READ_FAILED')
        owner = question[0].lower()
        record = expected[owner]
        current = []
        for line in block.splitlines():
            if not line.strip() or line.lstrip().startswith(';'):
                continue
            fields = line.split()
            if (len(fields) != 5 or fields[0].lower() != owner or
                    fields[2:4] != ['IN', 'A'] or not fields[1].isdigit() or
                    not ipv4(fields[4]) or status != 'NOERROR'):
                raise ValueError('BIND_DNS_A_RECORD_EXISTING_RECORD_CONFLICT')
            current.append((int(fields[1]), fields[4]))
        desired = [(int(record['ttl']), address) for address in record['addresses']]
        results[owner] = dict(record=record, currentAddresses=sorted(address for _, address in current),
                              absentOwner=status == 'NXDOMAIN',
                              changed=force or sorted(current) != sorted(desired))
    if results.keys() != expected.keys():
        raise ValueError('BIND_DNS_A_RECORD_READ_FAILED')
    return [results[record['owner']] for record in records]


def main():
    module = AnsibleModule(argument_spec=dict(records=dict(type='list', elements='dict', required=True),
                                             force=dict(type='bool', default=False),
                                             verify=dict(type='bool', default=False)),
                           supports_check_mode=True)
    try:
        records = checked_records(module.params['records'])
        rc, output, _ = module.run_command(
            ['dig', '@127.0.0.1', '+norecurse', '+noall', '+comments', '+question', '+answer', '-f', '/dev/stdin'],
            data=''.join(record['owner'] + ' A\n' for record in records), binary_data=True,
            environ_update={'LC_ALL': 'C'})
        if rc:
            raise ValueError('BIND_DNS_A_RECORD_READ_FAILED')
        rows = observations(records, output, module.params['force'])
        if module.params['verify'] and any(row['changed'] for row in rows):
            raise ValueError('BIND_DNS_A_RECORD_UPDATE_VERIFY_FAILED')
    except ValueError as error:
        code = str(error)
        module.fail_json(msg=code if code.startswith('BIND_DNS_') else 'BIND_DNS_A_RECORD_READ_FAILED')
    module.exit_json(changed=False, observations=rows)


if __name__ == '__main__':
    main()
