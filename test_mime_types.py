"""
Tests for static asset MIME type registration (issue #37).

Simulates a Windows registry that maps .css/.js/.svg to the wrong types and
verifies register_static_mime_types() restores what browsers require.
"""

import mimetypes
import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient

from server.utils.mime_types import STATIC_MIME_TYPES, register_static_mime_types


def _corrupt_registry() -> None:
    """Mimic broken HKEY_CLASSES_ROOT entries seen on Windows machines."""
    mimetypes.add_type("text/plain", ".css", strict=True)
    mimetypes.add_type("text/plain", ".js", strict=True)
    mimetypes.add_type("application/octet-stream", ".svg", strict=True)


class TestRegisterStaticMimeTypes(unittest.TestCase):
    def tearDown(self):
        register_static_mime_types()

    def test_overrides_wrong_os_mappings(self):
        _corrupt_registry()
        assert mimetypes.guess_type("index.css")[0] == "text/plain"

        register_static_mime_types()

        assert mimetypes.guess_type("index-abc123.css")[0] == "text/css"
        assert mimetypes.guess_type("index-abc123.js")[0] == "text/javascript"
        assert mimetypes.guess_type("vite.svg")[0] == "image/svg+xml"

    def test_all_registered_types_resolve(self):
        register_static_mime_types()
        for ext, mime in STATIC_MIME_TYPES.items():
            assert mimetypes.guess_type(f"file{ext}")[0] == mime, ext

    def test_static_files_served_with_correct_content_type(self):
        _corrupt_registry()
        register_static_mime_types()

        with tempfile.TemporaryDirectory() as tmp:
            assets = Path(tmp)
            (assets / "index.css").write_text("body{color:red}")
            (assets / "index.js").write_text("export {}")
            (assets / "icon.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'/>")

            app = FastAPI()
            app.mount("/assets", StaticFiles(directory=assets), name="assets")
            client = TestClient(app)

            assert client.get("/assets/index.css").headers["content-type"].startswith("text/css")
            assert client.get("/assets/index.js").headers["content-type"].startswith("text/javascript")
            assert client.get("/assets/icon.svg").headers["content-type"].startswith("image/svg+xml")


if __name__ == "__main__":
    unittest.main()
