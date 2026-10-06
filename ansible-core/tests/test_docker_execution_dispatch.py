import importlib.util
import sys
import unittest
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import execution_controller

source_path = Path(__file__).resolve().parents[1] / "collections" / "ansible_collections" / "platform" / "core" / "plugins" / "filter" / "artifact_source.py"
source_spec = importlib.util.spec_from_file_location("docker_artifact_source", source_path)
source_module = importlib.util.module_from_spec(source_spec)
source_spec.loader.exec_module(source_module)
resolve_artifact_source = source_module.resolve_artifact_source


class DockerExecutionDispatchTests(unittest.TestCase):
    def test_closed_service_dispatch_admits_docker_only(self):
        self.assertTrue(execution_controller._safe_service("docker"))
        self.assertFalse(execution_controller._safe_service("docker-extra"))

    def test_rootless_package_uses_repository_noarch_identity(self):
        manifest = yaml.safe_load((Path(__file__).resolve().parents[2] / "services" / "docker" / "service.yml").read_text(encoding="utf-8"))
        requirement = next(item for item in manifest["runtimeRequirements"] if item["id"] == "docker-rootless")
        self.assertEqual("noarch", requirement["architecture"])
        authority = {
            "apiVersion": "platform.installer/artifact-source-authority/v1alpha1",
            "kind": "ArtifactSourceAuthority",
            "sourcePolicy": "REPOSITORY_THEN_OFFLINE",
            "requirement": {"requirementId": requirement["id"], **requirement},
        }
        result = resolve_artifact_source(
            authority, {"id": requirement["id"], "name": requirement["name"]},
            "node1", "redos", "docker-ce-rootless-extras\t29.7.2\tnoarch\n", 0,
        )
        self.assertEqual("REPOSITORY", result["source"])
        wrong_architecture = resolve_artifact_source(
            authority, {"id": requirement["id"], "name": requirement["name"]},
            "node1", "redos", "docker-ce-rootless-extras\t29.7.2\tx86_64\n", 0,
        )
        self.assertEqual("BLOCKED", wrong_architecture["source"])


if __name__ == "__main__":
    unittest.main()
