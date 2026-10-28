"""Initial SCRAM record for Kafka's native storage formatter, never process argv."""
import base64
import hashlib
import os


def storage_scram(password, salt=None):
    if not isinstance(password, str) or not password:
        raise ValueError('KAFKA_ADMIN_RUNTIME_SECRET_INVALID')
    salt = os.urandom(16) if salt is None else salt
    salted = hashlib.pbkdf2_hmac('sha512', password.encode('utf-8'), salt, 8192)
    return 'SCRAM-SHA-512=[name=admin,iterations=8192,salt=%s,saltedpassword=%s]' % (
        base64.b64encode(salt).decode('ascii'), base64.b64encode(salted).decode('ascii'))


class FilterModule:
    def filters(self):
        return {'storage_scram': storage_scram}
