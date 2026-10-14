"""Vault Clear must accept exactly the data ancestors permitted by Apply."""

from contextlib import ExitStack
import importlib.util
from pathlib import Path
import stat
from types import SimpleNamespace
import unittest
from unittest.mock import patch


SOURCE = (Path(__file__).resolve().parents[1] / "ansible_collections/platform/vault/plugins/modules/clear_member.py")
SPEC = importlib.util.spec_from_file_location("vault_clear_member_paths", SOURCE)
CLEAR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CLEAR)


class VaultClearDataPathTests(unittest.TestCase):
    def inspect(self, owner, mode=0o700, allow_service_ancestors=True, data_root=None):
        entries = [
            SimpleNamespace(st_uid=0, st_mode=stat.S_IFDIR | 0o755),
            SimpleNamespace(st_uid=owner, st_mode=stat.S_IFDIR | mode),
            SimpleNamespace(st_uid=1002, st_mode=stat.S_IFDIR | 0o700),
        ]
        with patch.object(CLEAR.os, "open", side_effect=[10, 11, 12, 13]) as opened, \
             patch.object(CLEAR.os, "fstat", side_effect=entries), \
             patch.object(CLEAR.os, "close"):
            with ExitStack() as stack:
                result = CLEAR.owned_directory(
                    stack, "/data/vault/member", 1002,
                    service_owned_ancestors=allow_service_ancestors,
                    data_root=data_root,
                )
            self.assertEqual(result, 13)
            self.assertTrue(all(call.args[1] & CLEAR.os.O_NOFOLLOW for call in opened.call_args_list))

    def test_service_owned_intermediate_data_directory_is_allowed(self):
        self.inspect(1002)

    def test_foreign_intermediate_directory_is_rejected(self):
        with self.assertRaisesRegex(CLEAR.ClearFailure, "VAULT_CLEAR_PATH_UNSAFE"):
            self.inspect(2000)

    def test_explicit_custom_root_owner_is_allowed_only_at_that_root(self):
        self.inspect(2000, mode=0o755, data_root=('/data/vault', 2000))

    def test_custom_root_owner_does_not_extend_to_other_ancestors(self):
        with self.assertRaisesRegex(CLEAR.ClearFailure, 'VAULT_CLEAR_PATH_UNSAFE'):
            self.inspect(2000, data_root=('/data', 2000))

    def test_custom_root_requires_the_configured_owner(self):
        with self.assertRaisesRegex(CLEAR.ClearFailure, 'VAULT_CLEAR_PATH_UNSAFE'):
            self.inspect(2000, data_root=('/data/vault', 3000))

    def test_custom_root_still_rejects_group_writable_directory(self):
        with self.assertRaisesRegex(CLEAR.ClearFailure, 'VAULT_CLEAR_PATH_UNSAFE'):
            self.inspect(2000, mode=0o775, data_root=('/data/vault', 2000))

    def test_custom_root_must_contain_member_data_path(self):
        with patch.object(CLEAR.os, 'geteuid', return_value=0), \
             patch.object(CLEAR, 'private_mount_namespace'), \
             patch.object(CLEAR.pwd, 'getpwnam', return_value=SimpleNamespace(pw_uid=1002)), \
             patch.object(CLEAR, 'owned_directory') as opened:
            for root in ['/other', '/data/vault/member', '/data/../data', '/data/']:
                with self.subTest(root=root), self.assertRaisesRegex(
                        CLEAR.ClearFailure, 'VAULT_CLEAR_PATH_UNSAFE'):
                    CLEAR.clear_member('qa-vault', 'vault-1', '/data/vault/member',
                                       'qa-vault', inspect_only=True,
                                       data_root_directory=root, data_root_owner='operator')
            opened.assert_not_called()

    def test_writable_intermediate_directory_is_rejected(self):
        with self.assertRaisesRegex(CLEAR.ClearFailure, "VAULT_CLEAR_PATH_UNSAFE"):
            self.inspect(1002, mode=0o722)

    def test_config_and_unit_paths_keep_root_owned_ancestors(self):
        with self.assertRaisesRegex(CLEAR.ClearFailure, "VAULT_CLEAR_PATH_UNSAFE"):
            self.inspect(1002, allow_service_ancestors=False)


if __name__ == "__main__":
    unittest.main()
