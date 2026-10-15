import os
import socket
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import execution_ssh


class ExecutionSshTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='')
        self.addCleanup(self.tmp.cleanup)
        self.root = str(Path(self.tmp.name) / 'c')
        self.patch = mock.patch.object(execution_ssh, '_root', return_value=self.root)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.journal = SimpleNamespace(root='/execution', run_id='installer-one')
        self.operation = {'operationId': 'applications:apply'}

    def test_operation_and_run_isolation_and_private_directory(self):
        first = execution_ssh.control_path(self.journal, self.operation)
        self.assertLess(len(first) - 2 + 40 + 17, 108)
        self.assertEqual(0o700, os.stat(os.path.dirname(first)).st_mode & 0o777)
        other = execution_ssh.control_path(self.journal, {'operationId': 'applications:verify'})
        self.assertNotEqual(first, other)
        third = execution_ssh.control_path(SimpleNamespace(root='/execution', run_id='installer-two'), self.operation)
        self.assertNotEqual(first, third)
        execution_ssh.cleanup(self.journal, self.operation)
        self.assertTrue(os.path.isdir(os.path.dirname(other)))
        self.assertTrue(os.path.isdir(os.path.dirname(third)))
        execution_ssh.cleanup(self.journal)

    def test_foreign_or_symlink_control_directory_rejected(self):
        os.symlink(self.tmp.name, self.root)
        with self.assertRaisesRegex(ValueError, 'DIRECTORY_INVALID'):
            execution_ssh.control_path(self.journal, self.operation)

    def test_stale_socket_from_confirmed_stopped_group_is_removed(self):
        path = execution_ssh.control_path(self.journal, self.operation).replace('%C', 'a' * 40)
        sock = socket.socket(socket.AF_UNIX)
        sock.bind(path)
        sock.close()
        with mock.patch.object(execution_ssh.subprocess, 'run', return_value=SimpleNamespace(returncode=255)) as run:
            execution_ssh.cleanup(self.journal)
            self.assertEqual(['ssh', '-F', 'none', '-S', path, '-O', 'exit', '127.0.0.1'], run.call_args.args[0])
        self.assertFalse(os.path.exists(path))

    def test_live_socket_cannot_be_silently_unlinked(self):
        path = execution_ssh.control_path(self.journal, self.operation).replace('%C', 'b' * 40)
        sock = socket.socket(socket.AF_UNIX)
        self.addCleanup(sock.close)
        sock.bind(path)
        sock.listen()
        with mock.patch.object(execution_ssh.subprocess, 'run', return_value=SimpleNamespace(returncode=255)):
            with self.assertRaisesRegex(ValueError, 'CLEANUP_FAILED'):
                execution_ssh.cleanup(self.journal)
        self.assertTrue(os.path.exists(path))

    def test_file_instead_of_socket_is_never_removed(self):
        path = execution_ssh.control_path(self.journal, self.operation).replace('%C', 'c' * 40)
        Path(path).write_text('foreign')
        with self.assertRaisesRegex(ValueError, 'SOCKET_INVALID'):
            execution_ssh.cleanup(self.journal)
        self.assertEqual('foreign', Path(path).read_text())

    def test_acknowledged_exit_waits_for_socket_unlink(self):
        path = execution_ssh.control_path(self.journal, self.operation).replace('%C', 'd' * 40)
        sock = socket.socket(socket.AF_UNIX)
        sock.bind(path)
        sock.close()
        with mock.patch.object(execution_ssh.subprocess, 'run', return_value=SimpleNamespace(returncode=0)), \
                mock.patch.object(execution_ssh.time, 'sleep', side_effect=lambda _: os.unlink(path)) as sleep:
            execution_ssh.cleanup(self.journal)
        sleep.assert_called_once_with(0.02)
        self.assertFalse(os.path.exists(os.path.dirname(path)))

    def test_acknowledged_exit_without_unlink_fails_bounded(self):
        path = execution_ssh.control_path(self.journal, self.operation).replace('%C', 'e' * 40)
        sock = socket.socket(socket.AF_UNIX)
        self.addCleanup(sock.close)
        sock.bind(path)
        sock.listen()
        with mock.patch.object(execution_ssh.subprocess, 'run', return_value=SimpleNamespace(returncode=0)), \
                mock.patch.object(execution_ssh.time, 'monotonic', side_effect=[0, 4]):
            with self.assertRaisesRegex(ValueError, 'CLEANUP_FAILED'):
                execution_ssh.cleanup(self.journal)
        self.assertTrue(os.path.exists(path))
