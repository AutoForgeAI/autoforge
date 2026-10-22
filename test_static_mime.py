"""
Static Asset MIME Type Tests
============================

Regression tests for issue #49: on Windows, the registry can map ``.js`` to
``text/plain``, which makes browsers refuse to run the UI's module scripts
(blank page). The server must override such mappings at import time.

Run with: python -m pytest test_static_mime.py
"""

import importlib
import mimetypes
import sys

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient


def _import_server_with_poisoned_registry():
    """Simulate a Windows registry that maps .js/.css to text/plain, then import the server."""
    mimetypes.add_type("text/plain", ".js")
    mimetypes.add_type("text/plain", ".css")
    sys.modules.pop("server.main", None)
    importlib.import_module("server.main")


def test_guess_type_overrides_bad_registry_mappings():
    _import_server_with_poisoned_registry()

    assert mimetypes.guess_type("index-abc123.js")[0] == "text/javascript"
    assert mimetypes.guess_type("chunk.mjs")[0] == "text/javascript"
    assert mimetypes.guess_type("index-abc123.css")[0] == "text/css"
    assert mimetypes.guess_type("vite.svg")[0] == "image/svg+xml"


def test_static_files_serve_javascript_content_type(tmp_path):
    _import_server_with_poisoned_registry()

    (tmp_path / "index-abc123.js").write_text("export default 1;\n")
    (tmp_path / "index-abc123.css").write_text("body{}\n")

    app = FastAPI()
    app.mount("/assets", StaticFiles(directory=tmp_path), name="assets")
    client = TestClient(app)

    js = client.get("/assets/index-abc123.js")
    assert js.status_code == 200
    assert js.headers["content-type"].startswith("text/javascript")

    css = client.get("/assets/index-abc123.css")
    assert css.status_code == 200
    assert css.headers["content-type"].startswith("text/css")
