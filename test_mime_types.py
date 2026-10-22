"""
Tests for web asset MIME type registration (issue #37).

Simulates a Windows registry that maps .css/.js to text/plain and checks that
register_web_mime_types() restores the correct types and that StaticFiles
serves the UI assets with them.
"""

import mimetypes

import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient

from server.utils.mime_types import WEB_MIME_TYPES, register_web_mime_types


@pytest.fixture
def poisoned_mimetypes():
    """Mimic a Windows registry that serves stylesheets/scripts as plain text."""
    mimetypes.init()
    mimetypes.add_type("text/plain", ".css", strict=True)
    mimetypes.add_type("text/plain", ".js", strict=True)
    assert mimetypes.guess_type("index.css")[0] == "text/plain"
    yield
    mimetypes.init()
    register_web_mime_types()


def test_register_overrides_poisoned_types(poisoned_mimetypes):
    register_web_mime_types()
    for ext, mime in WEB_MIME_TYPES.items():
        assert mimetypes.guess_type(f"file{ext}")[0] == mime


def test_static_files_served_with_correct_content_type(poisoned_mimetypes, tmp_path):
    (tmp_path / "index-abc.css").write_text("body{color:red}")
    (tmp_path / "index-abc.js").write_text("console.log(1)")
    register_web_mime_types()

    app = FastAPI()
    app.mount("/assets", StaticFiles(directory=tmp_path), name="assets")
    client = TestClient(app)

    css = client.get("/assets/index-abc.css")
    assert css.status_code == 200
    assert css.headers["content-type"].startswith("text/css")

    js = client.get("/assets/index-abc.js")
    assert js.status_code == 200
    assert js.headers["content-type"].startswith("text/javascript")
