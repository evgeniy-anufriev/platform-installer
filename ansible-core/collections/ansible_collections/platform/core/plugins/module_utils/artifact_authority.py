"""Shared authority construction; callers validate their typed requirements."""
import copy


def assemble_authority(requirement, offline=None, repository=None, image=False):
    return {
        "apiVersion": "platform.installer/artifact-source-authority/" + ("v1alpha2" if image else "v1alpha1"),
        "kind": "ArtifactSourceAuthority",
        "requirement": copy.deepcopy(requirement),
        "sourcePolicy": "REPOSITORY_THEN_OFFLINE",
        "repository": copy.deepcopy(repository or {"kind": "REPOSITORY"}),
        "offlineBundle": copy.deepcopy(offline),
    }
