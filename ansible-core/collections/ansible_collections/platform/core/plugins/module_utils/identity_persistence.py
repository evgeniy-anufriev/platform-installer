from __future__ import absolute_import, division, print_function

__metaclass__ = type

import hashlib
import json
import os
import tempfile

try:
    import yaml
except ImportError:
    yaml = None


def _hash(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _read_bytes(path):
    with open(path, "rb") as source:
        return source.read()


def _dump(document):
    if yaml is None:
        raise RuntimeError("PyYAML is required for identity persistence")
    return yaml.safe_dump(document, allow_unicode=True, default_flow_style=False, sort_keys=False, width=100).encode("utf-8")


def persist_identity_documents(project_path, inventory_path, project, inventory, transaction_dir=None, before_commit=None):
    """Persist a complete project/inventory pair with optimistic locking.

    Inputs must be parsed candidate documents. This function never edits
    group_vars/host_vars and never performs identity decisions.
    """
    paths = [os.path.abspath(project_path), os.path.abspath(inventory_path)]
    originals = [_read_bytes(path) for path in paths]
    if yaml is not None:
        try:
            if yaml.safe_load(originals[0]) == project and yaml.safe_load(originals[1]) == inventory:
                return {"status": "PASS", "changed": False, "candidateHashes": [_hash(v) for v in originals]}
        except (TypeError, ValueError, yaml.YAMLError):
            pass
    candidates = [_dump(project), _dump(inventory)]
    if all(_hash(value) == _hash(original) for value, original in zip(candidates, originals)):
        return {"status": "PASS", "changed": False, "candidateHashes": [_hash(v) for v in candidates]}
    if transaction_dir is None:
        transaction_dir = os.path.dirname(paths[0])
    os.makedirs(transaction_dir, exist_ok=True)
    txid = next(tempfile._get_candidate_names())
    marker_path = os.path.join(transaction_dir, ".identity-materialization-%s.json" % txid)
    temp_paths = []
    rollback_paths = []
    for path, original in zip(paths, originals):
        rollback_path = os.path.join(transaction_dir, ".%s.%s.rollback" % (txid, os.path.basename(path)))
        with open(rollback_path, "wb") as backup:
            backup.write(original)
            backup.flush()
            os.fsync(backup.fileno())
        rollback_paths.append(rollback_path)
    marker = {"transactionId": txid, "targets": paths, "rollbackPaths": rollback_paths, "originalHashes": [_hash(v) for v in originals], "candidateHashes": [_hash(v) for v in candidates], "state": "PREPARED"}
    with open(marker_path, "w", encoding="utf-8") as marker_file:
        json.dump(marker, marker_file, sort_keys=True)
        marker_file.flush()
        os.fsync(marker_file.fileno())
    try:
        for path, content in zip(paths, candidates):
            fd, temp_path = tempfile.mkstemp(prefix=".%s." % os.path.basename(path), dir=os.path.dirname(path))
            temp_paths.append(temp_path)
            with os.fdopen(fd, "wb") as output:
                output.write(content)
                output.flush()
                os.fsync(output.fileno())
        if before_commit is not None:
            before_commit(paths)
        current = [_read_bytes(path) for path in paths]
        if [_hash(v) for v in current] != marker["originalHashes"]:
            raise RuntimeError("MATERIALIZATION_CONCURRENT_EDIT")
        for temp_path, path in zip(temp_paths, paths):
            os.replace(temp_path, path)
        marker["state"] = "COMMITTED"
        with open(marker_path, "w", encoding="utf-8") as marker_file:
            json.dump(marker, marker_file, sort_keys=True)
            marker_file.flush()
            os.fsync(marker_file.fileno())
        os.unlink(marker_path)
        for rollback_path in rollback_paths:
            if os.path.exists(rollback_path):
                os.unlink(rollback_path)
        return {"status": "PASS", "changed": originals != candidates, "candidateHashes": marker["candidateHashes"]}
    except Exception:
        for temp_path in temp_paths:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
        for path, original in zip(paths, originals):
            if os.path.exists(path) and _hash(_read_bytes(path)) != _hash(original):
                fd, rollback = tempfile.mkstemp(prefix=".rollback.", dir=os.path.dirname(path))
                with os.fdopen(fd, "wb") as output:
                    output.write(original)
                    output.flush()
                    os.fsync(output.fileno())
                os.replace(rollback, path)
        if os.path.exists(marker_path):
            os.unlink(marker_path)
        for rollback_path in rollback_paths:
            if os.path.exists(rollback_path):
                os.unlink(rollback_path)
        raise


def recover_identity_transaction(marker_path):
    """Recover an interrupted transaction before a new managed apply."""
    with open(marker_path, "r", encoding="utf-8") as source:
        marker = json.load(source)
    current = [_hash(_read_bytes(path)) for path in marker["targets"]]
    if current == marker["candidateHashes"]:
        os.unlink(marker_path)
        for path in marker.get("rollbackPaths", []):
            if os.path.exists(path):
                os.unlink(path)
        return {"status": "COMMITTED", "changed": False}
    if current == marker["originalHashes"]:
        os.unlink(marker_path)
        for path in marker.get("rollbackPaths", []):
            if os.path.exists(path):
                os.unlink(path)
        return {"status": "ROLLED_BACK", "changed": False}
    for target, rollback in zip(marker["targets"], marker["rollbackPaths"]):
        with open(rollback, "rb") as source, tempfile.NamedTemporaryFile(delete=False, dir=os.path.dirname(target)) as output:
            output.write(source.read())
            output.flush()
            os.fsync(output.fileno())
            temporary = output.name
        os.replace(temporary, target)
    os.unlink(marker_path)
    for path in marker.get("rollbackPaths", []):
        if os.path.exists(path):
            os.unlink(path)
    return {"status": "ROLLED_BACK", "changed": True}
