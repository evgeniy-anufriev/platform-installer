#!/usr/bin/python
"""Read-only application authentication using installed libpq SQLSTATE output."""
import ctypes
import ctypes.util
import re
import select
import time

from ansible.module_utils.basic import AnsibleModule


def main():
    module = AnsibleModule(argument_spec=dict(
        host=dict(required=True), port=dict(type='int', required=True),
        username=dict(required=True), password=dict(required=True, no_log=True),
        ca_file=dict(type='path', required=True), timeout=dict(type='int', default=10),
    ), supports_check_mode=True)
    args = module.params
    if not 1 <= args['timeout'] <= 60 or not 1 <= args['port'] <= 65535:
        module.fail_json(msg='APPLICATION_POSTGRESQL_PROBE_INPUT_INVALID')
    connection = None
    result = dict(changed=False, authenticated=False, sqlstate='')
    try:
        pq = ctypes.CDLL(ctypes.util.find_library('pq') or 'libpq.so.5')
        signatures = (
            ('PQconnectStartParams', ctypes.c_void_p, [ctypes.POINTER(ctypes.c_char_p), ctypes.POINTER(ctypes.c_char_p), ctypes.c_int]),
            ('PQsetErrorVerbosity', ctypes.c_int, [ctypes.c_void_p, ctypes.c_int]),
            ('PQconnectPoll', ctypes.c_int, [ctypes.c_void_p]),
            ('PQsocket', ctypes.c_int, [ctypes.c_void_p]),
            ('PQerrorMessage', ctypes.c_char_p, [ctypes.c_void_p]),
            ('PQfinish', None, [ctypes.c_void_p]),
        )
        for name, restype, argtypes in signatures:
            function = getattr(pq, name)
            function.restype, function.argtypes = restype, argtypes
        parameters = dict(host=args['host'], port=str(args['port']), dbname='postgres',
                          user=args['username'], password=args['password'], sslmode='verify-full',
                          sslrootcert=args['ca_file'], passfile='/dev/null',
                          connect_timeout=str(args['timeout']))
        array = ctypes.c_char_p * (len(parameters) + 1)
        keys = array(*(key.encode() for key in parameters), None)
        values = array(*(value.encode() for value in parameters.values()), None)
        deadline = time.monotonic() + args['timeout']
        connection = pq.PQconnectStartParams(keys, values, 0)
        if not connection:
            raise ValueError()
        # Set before authentication: psql applies verbosity after initial connect.
        # SQLSTATE mode retains the server code without localized message text.
        pq.PQsetErrorVerbosity(connection, 3)  # PQERRORS_SQLSTATE
        while time.monotonic() < deadline:
            state = pq.PQconnectPoll(connection)
            if state == 3:  # PGRES_POLLING_OK
                result['authenticated'] = True
                break
            if state == 0:  # PGRES_POLLING_FAILED
                error = pq.PQerrorMessage(connection) or b''
                code = re.search(rb':\s+([0-9A-Z]{5})\s*$', error)
                if code:
                    result['sqlstate'] = code.group(1).decode('ascii')
                break
            if state not in (1, 2, 4):
                raise ValueError()
            descriptor = pq.PQsocket(connection)
            if descriptor < 0:
                raise ValueError()
            remaining = max(0, deadline - time.monotonic())
            select.select([descriptor] if state == 1 else [],
                          [descriptor] if state == 2 else [], [], min(remaining, 0.25))
    except Exception:
        # No connection strings, credentials, or libpq messages enter diagnostics.
        result = dict(changed=False, authenticated=False, sqlstate='')
    finally:
        if connection:
            pq.PQfinish(connection)
    module.exit_json(**result)


if __name__ == '__main__':
    main()
