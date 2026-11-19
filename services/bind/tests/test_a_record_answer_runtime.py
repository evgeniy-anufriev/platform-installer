import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ansible_collections/platform/bind/plugins/modules'))
from a_record_observations import checked_records, observations


def record(name):
    return dict(owner=f'{name}.example.test.', zone='example.test', ttl=60, addresses=['192.0.2.1'])


def answer(owner, lines='', status='NOERROR', flags='qr aa'):
    return (f';; ->>HEADER<<- opcode: QUERY, status: {status}, id: 1\n'
            f';; flags: {flags}; QUERY: 1\n;{owner}\tIN\tA\n{lines}\n')


class ARecordAnswerRuntimeTests(unittest.TestCase):
    def test_matches_questions_and_preserves_exact_ttl_and_nxdomain(self):
        a, b = record('a'), record('b')
        rows = observations(checked_records([b, a]), answer(b['owner'], status='NXDOMAIN') +
                           answer(a['owner'], f"  ; comment\n{a['owner']} 60 IN A 192.0.2.1"))
        self.assertEqual([False, True], [row['changed'] for row in rows])
        self.assertEqual([False, True], [row['absentOwner'] for row in rows])
        self.assertTrue(observations([a], answer(a['owner'], f"{a['owner']} 50 IN A 192.0.2.1"))[0]['changed'])

    def test_missing_duplicate_or_nonauthoritative_response_is_rejected(self):
        a, b = record('a'), record('b')
        for output in (answer(a['owner']), answer(a['owner']) * 2,
                       answer(a['owner']) + answer(b['owner'], flags='qr ra')):
            with self.subTest(output=output), self.assertRaisesRegex(ValueError, 'BIND_DNS_A_RECORD_READ_FAILED'):
                observations([a, b], output)

    def test_cname_and_foreign_owner_are_rejected(self):
        a = record('a')
        for line in (f"{a['owner']} 60 IN CNAME other.example.test.",
                     'other.example.test. 60 IN A 192.0.2.1'):
            with self.subTest(line=line), self.assertRaisesRegex(ValueError, 'BIND_DNS_A_RECORD_EXISTING_RECORD_CONFLICT'):
                observations([a], answer(a['owner'], line))
