import os
import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ansible-core" / "tools"))
sys.path.insert(0, str(ROOT / "ansible-core" / "collections" / "ansible_collections" / "platform" / "core" / "plugins" / "module_utils"))
from schema_validation import SchemaValidator
import execution_secret_output as storage
from secret_output_wire import OutputWireError


class SecretOutputStorageTests(unittest.TestCase):
    def test_preparation_creates_private_storage_and_preserves_existing_bytes(self):
        with tempfile.TemporaryDirectory() as parent:
            root = Path(parent) / "execution"
            with storage._directory(str(root), create=True):
                pass
            self.assertEqual(0o700, stat.S_IMODE(root.stat().st_mode))
            self.assertEqual(os.geteuid(), root.stat().st_uid)
            sentinel = root / "existing-journal"
            sentinel.write_bytes(b"unchanged")
            with storage._directory(str(root), create=True):
                pass
            self.assertEqual(b"unchanged", sentinel.read_bytes())
            with patch.object(storage.os, "geteuid", return_value=os.geteuid() + 1):
                with self.assertRaisesRegex(OutputWireError, "OUTPUT_ACCESS_DENIED"):
                    with storage._directory(str(root), create=True):
                        pass
            self.assertEqual(b"unchanged", sentinel.read_bytes())

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.schemas = ROOT / "contracts" / "secret-output-delivery" / "v1alpha1"
        self.validator = SchemaValidator(self.schemas)
        self.schema = self.schemas / "metadata.schema.json"
        self.meta = {"protocol": "SecretOutputDelivery/v1alpha1", "packageId": "a" * 32,
                     "projectId": "qa", "deploymentId": "vault-ha",
                     "sourceRunId": "installer-test", "runtimeDigest": "sha256:" + "b" * 64,
                     "generation": 1, "state": "READY", "entries": ["admin-token", "unseal-shares"]}
        self.package = self.root / "secret-outputs" / self.meta["packageId"]

    def publish(self, meta=None, token=b"test-token"):
        value = self.meta if meta is None else meta
        result = storage.publish(str(self.root), value, token,
                                 b'{"keys":["test-share"]}', self.validator, self.schema)
        storage.mark_producer_completed(str(self.root), value["packageId"], value["sourceRunId"],
                                        "SUCCEEDED", "sha256:" + "b" * 64)
        return result

    def fetch(self, project="qa", generation=1):
        return storage.fetch(str(self.root), self.meta["packageId"], project, generation, self.validator, self.schema)

    def test_durable_publish_fetch_and_idempotent_retry(self):
        self.assertEqual(self.publish(), self.meta)
        original = self.fetch()
        self.publish()
        self.assertEqual(self.fetch(), original)
        self.assertEqual(original[:4], b"SOD1")
        self.assertEqual(stat.S_IMODE(self.package.stat().st_mode), 0o700)
        for name in ("admin-token", "unseal-shares", "metadata.json", ".binding.json", ".lock"):
            self.assertEqual(stat.S_IMODE((self.package / name).stat().st_mode), 0o600)
        self.assertFalse((self.root / "runs").exists())

    def test_identity_and_content_cannot_be_overwritten(self):
        self.publish()
        before = self.fetch()
        for meta in (dict(self.meta, projectId="other"), dict(self.meta, deploymentId="vault-other"), dict(self.meta, generation=2)):
            with self.assertRaisesRegex(OutputWireError, "OUTPUT_IDENTITY_MISMATCH"):
                self.publish(meta)
        with self.assertRaisesRegex(OutputWireError, "OUTPUT_IDENTITY_MISMATCH"):
            self.publish(token=b"replacement")
        for project, generation in (("other", 1), ("qa", 2)):
            with self.assertRaisesRegex(OutputWireError, "OUTPUT_IDENTITY_MISMATCH"):
                self.fetch(project, generation)
        self.assertEqual(self.fetch(), before)

    def test_canonical_deployment_ids_schema_publish_fetch(self):
        accepted = ("vault-ha", "vault.ha", "vault_ha", "a" * 128)
        rejected = ("1vault", "vault--ha", "vault/ha", "vault-", "a" * 129)
        for index, deployment in enumerate(accepted + rejected):
            with self.subTest(deployment=deployment):
                meta = dict(self.meta, deploymentId=deployment, packageId=format(index + 1, "032x"))
                if deployment in accepted:
                    self.assertEqual(self.publish(meta), meta)
                    frame = storage.fetch(str(self.root), meta["packageId"], "qa", 1, self.validator, self.schema)
                    self.assertEqual(frame[:4], b"SOD1")
                    self.assertIn(deployment.encode("ascii"), frame)
                else:
                    with self.assertRaises(OutputWireError):
                        self.publish(meta)
                    self.assertFalse((self.root / "secret-outputs" / meta["packageId"]).exists())

    def test_partial_failure_preserves_material_and_same_identity_can_retry(self):
        write = storage._exclusive
        def fault(package, name, data):
            if name == "unseal-shares":
                raise OSError("sensitive-test-canary")
            return write(package, name, data)
        with patch.object(storage, "_exclusive", side_effect=fault):
            with self.assertRaisesRegex(OutputWireError, "^OUTPUT_RECOVERY_REQUIRED$"):
                self.publish()
        self.assertTrue((self.package / "admin-token").exists())
        self.assertFalse((self.package / "metadata.json").exists())
        with self.assertRaises(OutputWireError):
            self.fetch()
        with self.assertRaisesRegex(OutputWireError, "OUTPUT_IDENTITY_MISMATCH"):
            self.publish(dict(self.meta, projectId="other"))
        self.publish()
        self.assertEqual(self.fetch()[:4], b"SOD1")

    def test_symlink_hardlink_and_opened_permissions_fail_closed(self):
        self.publish()
        token = self.package / "admin-token"
        foreign = self.root / "foreign"
        foreign.write_bytes(b"foreign-token")
        foreign.chmod(0o600)
        token.unlink()
        token.symlink_to(foreign)
        with self.assertRaises(OutputWireError): self.fetch()
        self.assertEqual(foreign.read_bytes(), b"foreign-token")
        token.unlink()
        os.link(foreign, token)
        with self.assertRaises(OutputWireError): self.fetch()
        token.unlink()
        token.write_bytes(b"test-token")
        token.chmod(0o644)
        with self.assertRaisesRegex(OutputWireError, "OUTPUT_ACCESS_DENIED"): self.fetch()

    def test_substituted_package_directory_never_followed(self):
        self.publish()
        moved = self.root / "original"
        self.package.rename(moved)
        self.package.symlink_to(moved, target_is_directory=True)
        with self.assertRaises(OutputWireError): self.fetch()
        self.assertTrue((moved / "admin-token").exists())

    def test_read_uses_held_directory_not_later_path_replacement(self):
        self.publish()
        before = self.fetch()
        read = storage._read
        moved = self.root / "held-original"
        swapped = []
        def replace_path(package, name, bound):
            if not swapped:
                self.package.rename(moved)
                self.package.mkdir(mode=0o700)
                (self.package / "admin-token").write_bytes(b"foreign-token")
                swapped.append(True)
            return read(package, name, bound)
        with patch.object(storage, "_read", side_effect=replace_path):
            self.assertEqual(self.fetch(), before)
        self.assertEqual((self.package / "admin-token").read_bytes(), b"foreign-token")
        self.assertTrue((moved / "unseal-shares").exists())

    def test_ready_metadata_not_published_when_atomic_link_fails(self):
        with patch.object(storage.os, "link", side_effect=OSError("sensitive-test-canary")):
            with self.assertRaisesRegex(OutputWireError, "^OUTPUT_RECOVERY_REQUIRED$"):
                self.publish()
        self.assertFalse((self.package / "metadata.json").exists())
        self.assertTrue((self.package / "admin-token").exists())
        self.assertTrue((self.package / "unseal-shares").exists())
        self.publish()
        self.assertEqual(self.fetch()[:4], b"SOD1")

    def test_fifo_and_oversized_entry_rejected_before_unbounded_read(self):
        self.publish()
        token = self.package / "admin-token"
        token.unlink()
        os.mkfifo(token, mode=0o600)
        with self.assertRaisesRegex(OutputWireError, "OUTPUT_ACCESS_DENIED"):
            self.fetch()
        token.unlink()
        token.write_bytes(b"x" * 4097)
        token.chmod(0o600)
        with self.assertRaisesRegex(OutputWireError, "OUTPUT_TRANSFER_FAILED"):
            self.fetch()

    def test_boolean_generation_is_not_integer_identity(self):
        self.publish()
        with self.assertRaisesRegex(OutputWireError, "OUTPUT_REQUEST_INVALID"):
            self.fetch(generation=True)

    def test_invalid_metadata_never_materializes_storage(self):
        with self.assertRaises(OutputWireError): self.publish(dict(self.meta, packageId="../foreign"))
        self.assertFalse((self.root / "secret-outputs").exists())

    def test_project_output_capture_uses_common_entry_names_and_identity_binding(self):
        project = self.root / "project"
        output = project / "secrets" / "vault-ha"
        output.mkdir(parents=True, mode=0o700)
        (project / "secrets").chmod(0o700)
        (output / "admin-token").write_bytes(b"project-token")
        (output / "admin-token").chmod(0o600)
        (output / "unseal-shares").write_bytes(b'{"keys":["share"]}')
        (output / "unseal-shares").chmod(0o600)
        journal = self.root / "journal"
        journal.mkdir(mode=0o700)
        package_id = storage.publish_project_outputs(
            str(self.root), str(project), "qa", "vault-ha", "installer-test",
            self.meta["runtimeDigest"], str(journal), self.validator, self.schema)
        self.assertRegex(package_id, r"^[0-9a-f]{32}$")
        storage.mark_producer_completed(str(self.root), package_id, "installer-test", "SUCCEEDED",
                                        "sha256:" + "c" * 64)
        frame = storage.fetch(str(self.root), package_id, "qa", 1, self.validator, self.schema)
        self.assertEqual(frame[:4], b"SOD1")
        self.assertIn(b'"deploymentId":"vault-ha"', frame)
        self.assertIn(b"project-token", frame)

    def test_project_output_capture_does_not_advertise_absent_or_partial_pair(self):
        project = self.root / "project"
        output = project / "secrets" / "vault-ha"
        output.mkdir(parents=True, mode=0o700)
        (project / "secrets").chmod(0o700)
        journal = self.root / "journal"
        journal.mkdir(mode=0o700)
        self.assertIsNone(storage.publish_project_outputs(
            str(self.root), str(project), "qa", "vault-ha", "installer-test",
            self.meta["runtimeDigest"], str(journal), self.validator, self.schema))
        (output / "admin-token").write_bytes(b"partial")
        (output / "admin-token").chmod(0o600)
        with self.assertRaisesRegex(OutputWireError, "OUTPUT_RECOVERY_REQUIRED"):
            storage.publish_project_outputs(
                str(self.root), str(project), "qa", "vault-ha", "installer-test",
                self.meta["runtimeDigest"], str(journal), self.validator, self.schema)
        self.assertFalse((self.root / "secret-outputs").exists())

    def test_producer_completion_is_durable_exact_and_idempotent(self):
        self.publish()
        terminal_digest = "sha256:" + "b" * 64
        evidence = storage.mark_producer_completed(
            str(self.root), self.meta["packageId"], "installer-test", "SUCCEEDED", terminal_digest)
        self.assertTrue(storage.producer_completed(str(self.root), self.meta["packageId"], "installer-test"))
        self.assertEqual(evidence, storage.mark_producer_completed(
            str(self.root), self.meta["packageId"], "installer-test", "SUCCEEDED", terminal_digest))
        with self.assertRaisesRegex(OutputWireError, "OUTPUT_IDENTITY_MISMATCH"):
            storage.mark_producer_completed(
                str(self.root), self.meta["packageId"], "installer-test", "FAILED", terminal_digest)
        self.assertFalse(storage.producer_completed(str(self.root), self.meta["packageId"], "other-run"))

    def test_list_ack_cleanup_retry_and_generation_binding(self):
        self.publish()
        response_schema = self.schemas / "response.schema.json"
        listed = storage.list_pending(str(self.root), "qa", 32, None, self.validator, response_schema)
        self.assertEqual([self.meta["packageId"]], [item["packageId"] for item in listed["packages"]])
        digests = {"admin-token": "sha256:" + "c" * 64,
                   "unseal-shares": "sha256:" + "d" * 64}
        with patch.object(storage, "_remove_entry", side_effect=OSError("safe-test-fault")):
            pending = storage.acknowledge(str(self.root), "qa", self.meta["packageId"], 1,
                                          "e" * 32, digests)
        self.assertEqual("ACKED_CLEANUP_PENDING", pending["state"])
        self.assertTrue((self.package / "admin-token").exists())
        delivered = storage.acknowledge(str(self.root), "qa", self.meta["packageId"], 1,
                                       "e" * 32, digests)
        self.assertEqual("DELIVERED", delivered["state"])
        self.assertFalse((self.package / "admin-token").exists())
        self.assertEqual(delivered, storage.acknowledge(
            str(self.root), "qa", self.meta["packageId"], 1, "e" * 32, digests))
        self.assertEqual([], storage.list_pending(
            str(self.root), "qa", 32, None, self.validator, response_schema)["packages"])
        with self.assertRaisesRegex(OutputWireError, "OUTPUT_IDENTITY_MISMATCH"):
            storage.acknowledge(str(self.root), "qa", self.meta["packageId"], 1,
                                "f" * 32, digests)

        project = self.root / "project"
        output = project / "secrets" / "vault-ha"
        output.mkdir(parents=True, mode=0o700)
        (project / "secrets").chmod(0o700)
        (output / "admin-token").write_bytes(b"next-token")
        (output / "admin-token").chmod(0o600)
        (output / "unseal-shares").write_bytes(b'{"keys":["next-share"]}')
        (output / "unseal-shares").chmod(0o600)
        journal = self.root / "journal-next"
        journal.mkdir(mode=0o700)
        next_package = storage.publish_project_outputs(
            str(self.root), str(project), "qa", "vault-ha", "installer-next",
            self.meta["runtimeDigest"], str(journal), self.validator, self.schema)
        self.assertNotEqual(self.meta["packageId"], next_package)
        self.assertEqual(2, json.loads((self.root / "secret-outputs" / next_package / "metadata.json").read_text())["generation"])

    def reserve(self, run="installer-reserved", project="qa", deployment="vault-ha"):
        journal = self.root / run
        journal.mkdir(mode=0o700)
        directory = Path(storage.prepare_retained_output_directory(
            str(self.root), str(journal), project, deployment, run, self.meta["runtimeDigest"]))
        return journal, directory

    def finish_reserved(self, journal, project="qa", deployment="vault-ha", state="FAILED"):
        return storage.complete_retained_outputs(str(self.root), str(journal), project, deployment,
            journal.name, self.meta["runtimeDigest"], state, "sha256:"+"f"*64, self.validator, self.schema)

    def write_reserved_entry(self, directory, name, data):
        (directory/name).write_bytes(data)
        (directory/name).chmod(0o600)

    def test_empty_reservation_failure_cancel_allows_next_generation(self):
        for index, terminal in enumerate(("FAILED", "CANCELLED")):
            deployment = "vault-empty-"+str(index)
            journal, directory = self.reserve("installer-empty-"+str(index), deployment=deployment)
            self.assertEqual([], storage.list_pending(str(self.root), "qa", 32, None,
                self.validator, self.schemas/"response.schema.json")["packages"])
            self.finish_reserved(journal, deployment=deployment, state=terminal)
            self.assertTrue(storage.producer_completed(str(self.root), directory.name, journal.name))
            next_journal, next_directory = self.reserve("installer-next-"+str(index), deployment=deployment)
            _, generation = storage.load_package_identity(str(next_journal), "qa", deployment, next_journal.name)
            self.assertEqual(2, generation)
            self.assertNotEqual(directory.name, next_directory.name)
            with self.assertRaises(OutputWireError):
                storage.acknowledge(str(self.root),"qa",directory.name,1,"e"*32,
                    {"admin-token":"sha256:"+"c"*64,"unseal-shares":"sha256:"+"d"*64})

    def test_partial_and_init_only_retained_with_explicit_recovery_status(self):
        for index, name in enumerate(("admin-token", "unseal-shares", "init-response.json")):
            deployment = "vault-partial-"+str(index)
            journal, directory = self.reserve("installer-partial-"+str(index), deployment=deployment)
            content = b"synthetic-partial-material"
            self.write_reserved_entry(directory,name,content)
            with self.assertRaisesRegex(OutputWireError,"OUTPUT_RECOVERY_REQUIRED"):
                self.finish_reserved(journal,deployment=deployment)
            self.assertEqual(content,(directory/name).read_bytes())
            self.assertFalse(storage.producer_completed(str(self.root),directory.name,journal.name))
            self.assertEqual("OUTPUT_RECOVERY_REQUIRED",json.loads((directory/"recovery-status.json").read_text())["code"])
            with self.assertRaisesRegex(OutputWireError,"OUTPUT_RECOVERY_REQUIRED"):
                storage.list_pending(str(self.root),"qa",32,None,self.validator,self.schemas/"response.schema.json")
            with self.assertRaises(OutputWireError):
                storage.fetch(str(self.root),directory.name,"qa",1,self.validator,self.schema)
            with self.assertRaises(OutputWireError):
                storage.acknowledge(str(self.root),"qa",directory.name,1,"e"*32,
                    {"admin-token":"sha256:"+"c"*64,"unseal-shares":"sha256:"+"d"*64})
            self.assertEqual(content,(directory/name).read_bytes())

    def test_other_project_listing_and_admission_unaffected_by_reservation(self):
        journal,directory = self.reserve(project="other-project")
        self.write_reserved_entry(directory,"init-response.json",b"synthetic-recovery")
        with self.assertRaises(OutputWireError): self.finish_reserved(journal,project="other-project")
        self.publish()
        listed=storage.list_pending(str(self.root),"qa",32,None,self.validator,self.schemas/"response.schema.json")
        self.assertEqual([self.meta["packageId"]],[item["packageId"] for item in listed["packages"]])
        next_journal,next_dir = self.reserve("installer-unrelated",project="third-project")
        self.assertTrue(next_dir.exists())

    def test_reservation_before_directory_creation_is_recoverable(self):
        journal=self.root/"installer-before-directory"
        journal.mkdir(mode=0o700)
        package,generation=storage.prepare_package_identity(str(self.root),str(journal),"qa","vault-ha",journal.name,self.meta["runtimeDigest"])
        self.assertFalse((self.root/"secret-outputs"/package).exists())
        self.assertEqual([],storage.list_pending(str(self.root),"qa",32,None,self.validator,self.schemas/"response.schema.json")["packages"])
        self.finish_reserved(journal)
        self.assertTrue(storage.producer_completed(str(self.root),package,journal.name))

    def test_missing_metadata_without_valid_reservation_is_not_ignored(self):
        unknown=self.root/"secret-outputs"/("f"*32)
        unknown.mkdir(parents=True,mode=0o700)
        unknown.parent.chmod(0o700)
        with self.assertRaisesRegex(OutputWireError,"OUTPUT_RECOVERY_REQUIRED"):
            storage.list_pending(str(self.root),"qa",32,None,self.validator,self.schemas/"response.schema.json")

    def test_full_pair_terminal_finalization_publishes_same_package_once(self):
        journal,directory=self.reserve()
        self.write_reserved_entry(directory,"admin-token",b"synthetic-token")
        self.write_reserved_entry(directory,"unseal-shares",b'{"keys":["synthetic-share"]}')
        package=self.finish_reserved(journal,state="INTERRUPTED")
        self.assertEqual(package,self.finish_reserved(journal,state="INTERRUPTED"))
        self.assertTrue(storage.fetch(str(self.root),package,"qa",1,self.validator,self.schema))
        self.assertEqual("READY",json.loads((directory/"metadata.json").read_text())["state"])

    def test_reserved_full_pair_publication_fault_preserves_last_copy_for_retry(self):
        journal,directory=self.reserve()
        self.write_reserved_entry(directory,"admin-token",b"synthetic-token")
        self.write_reserved_entry(directory,"unseal-shares",b'{"keys":["synthetic-share"]}')
        with patch.object(storage,"publish",side_effect=OutputWireError("OUTPUT_RECOVERY_REQUIRED")):
            with self.assertRaisesRegex(OutputWireError,"OUTPUT_RECOVERY_REQUIRED"):
                self.finish_reserved(journal)
        self.assertTrue((directory/"admin-token").exists())
        self.assertFalse((directory/"metadata.json").exists())
        self.assertTrue((directory/"recovery-status.json").exists())
        package=self.finish_reserved(journal)
        self.assertTrue(storage.fetch(str(self.root),package,"qa",1,self.validator,self.schema))

    def test_invalid_reservation_is_not_treated_as_empty_output(self):
        journal,directory=self.reserve()
        reservation=self.root/"secret-outputs"/(".reservation-"+directory.name+".json")
        reservation.write_text('{"packageId":"'+directory.name+'","packageId":"'+directory.name+'"}')
        reservation.chmod(0o600)
        with self.assertRaisesRegex(OutputWireError,"OUTPUT_RECOVERY_REQUIRED"):
            storage.list_pending(str(self.root),"qa",32,None,self.validator,self.schemas/"response.schema.json")
        self.assertFalse(storage.producer_completed(str(self.root),directory.name,journal.name))

    def test_single_retained_custody_apply_verify_terminal_ack(self):
        journal = self.root / "retained-journal"
        journal.mkdir(mode=0o700)
        directory = Path(storage.prepare_retained_output_directory(
            str(self.root), str(journal), "qa", "vault-ha", "installer-retained", self.meta["runtimeDigest"]))
        for name, content in (("admin-token", b"synthetic-token"), ("unseal-shares", b'{"keys":["synthetic-share"]}'), ("init-response.json", b'{"synthetic":true}')):
            (directory / name).write_bytes(content)
            (directory / name).chmod(0o600)
        package = storage.publish_retained_outputs(str(self.root), str(journal), "qa", "vault-ha",
            "installer-retained", self.meta["runtimeDigest"], self.validator, self.schema)
        self.assertEqual(directory.name, package)
        # Separate Verify reads the same custody token, not a project copy.
        self.assertEqual(b"synthetic-token", (directory / "admin-token").read_bytes())
        self.assertFalse((journal / "project" / "secrets").exists())
        storage.mark_producer_completed(str(self.root), package, "installer-retained", "SUCCEEDED", "sha256:"+"f"*64)
        receipt = storage.acknowledge(str(self.root), "qa", package, 1, "e"*32,
            {"admin-token":"sha256:"+"c"*64,"unseal-shares":"sha256:"+"d"*64})
        self.assertEqual("DELIVERED", receipt["state"])
        self.assertTrue(journal.exists())
        for name in ("admin-token", "unseal-shares", "init-response.json"):
            self.assertFalse((directory / name).exists())


if __name__ == "__main__":
    unittest.main()
