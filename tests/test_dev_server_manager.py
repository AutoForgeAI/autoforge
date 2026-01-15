from __future__ import annotations

import json
from pathlib import Path

from autocoder.server.services.dev_server_manager import detect_dev_command, extract_url


def _write_pkg(tmp_path: Path, scripts: dict[str, str]) -> None:
    (tmp_path / "package.json").write_text(
        json.dumps({"name": "x", "private": True, "scripts": scripts}),
        encoding="utf-8",
    )


def test_extract_url() -> None:
    assert extract_url("ready on http://localhost:5173/") == "http://localhost:5173/"
    assert extract_url("visit https://127.0.0.1:3000") == "https://127.0.0.1:3000"
    assert extract_url("no url here") is None


def test_detect_dev_command_from_autocoder_yaml(tmp_path: Path) -> None:
    (tmp_path / "autocoder.yaml").write_text(
        "commands:\n  dev:\n    command: pnpm dev\n",
        encoding="utf-8",
    )
    _write_pkg(tmp_path, {"dev": "vite"})
    assert detect_dev_command(tmp_path) == "pnpm dev"


def test_detect_dev_command_from_package_json(tmp_path: Path) -> None:
    _write_pkg(tmp_path, {"dev": "vite"})
    assert detect_dev_command(tmp_path) == "npm run dev"

    tmp2 = tmp_path / "p2"
    tmp2.mkdir()
    _write_pkg(tmp2, {"start": "node server.js"})
    assert detect_dev_command(tmp2) == "npm start"

