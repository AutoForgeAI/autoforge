"""
Regression tests for static asset MIME types (issue #49).

On some Windows machines the registry maps .js to "text/plain", which Python's
mimetypes module picks up. The UI's module scripts are then rejected by the
browser and the page renders blank. server.main must override such mappings.
"""

import importlib
import mimetypes

import server.main


def test_js_mime_type_overrides_bad_registry_mapping():
    # Simulate a broken Windows registry entry, then re-run the module setup.
    mimetypes.add_type("text/plain", ".js")
    mimetypes.add_type("text/plain", ".css")
    assert mimetypes.guess_type("index.js")[0] == "text/plain"

    importlib.reload(server.main)

    assert mimetypes.guess_type("assets/index-abc123.js")[0] == "text/javascript"
    assert mimetypes.guess_type("assets/worker.mjs")[0] == "text/javascript"
    assert mimetypes.guess_type("assets/index-abc123.css")[0] == "text/css"
    assert mimetypes.guess_type("vite.svg")[0] == "image/svg+xml"
