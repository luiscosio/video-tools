"""Fingerprint the episode content for the check command."""

import hashlib
import json

import yaml


def script_hash(path):
    data = yaml.safe_load(path.read_text())
    data.pop("approval", None)
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
