from pathlib import Path
from datetime import date
import yaml

from plaibox.metadata import read_metadata, write_metadata

METADATA_FILENAME = ".plaibox.yaml"


def test_write_metadata_creates_file(tmp_path):
    meta = {
        "name": "test-project",
        "description": "A test project",
        "status": "sandbox",
        "created": "2026-04-10",
        "tags": [],
        "tech": [],
    }
    write_metadata(tmp_path, meta)

    written = yaml.safe_load((tmp_path / METADATA_FILENAME).read_text())
    assert written["name"] == "test-project"
    assert written["status"] == "sandbox"


def test_read_metadata_returns_dict(tmp_path):
    meta = {
        "name": "test-project",
        "description": "A test project",
        "status": "sandbox",
        "created": "2026-04-10",
        "tags": [],
        "tech": [],
    }
    (tmp_path / METADATA_FILENAME).write_text(yaml.dump(meta))

    result = read_metadata(tmp_path)
    assert result["name"] == "test-project"
    assert result["description"] == "A test project"


def test_read_metadata_returns_none_when_missing(tmp_path):
    result = read_metadata(tmp_path)
    assert result is None


def test_write_metadata_overwrites_existing(tmp_path):
    meta_v1 = {"name": "old", "description": "Old", "status": "sandbox",
                "created": "2026-04-10", "tags": [], "tech": []}
    meta_v2 = {"name": "new", "description": "New", "status": "project",
                "created": "2026-04-10", "tags": [], "tech": []}

    write_metadata(tmp_path, meta_v1)
    write_metadata(tmp_path, meta_v2)

    result = read_metadata(tmp_path)
    assert result["name"] == "new"
    assert result["status"] == "project"
