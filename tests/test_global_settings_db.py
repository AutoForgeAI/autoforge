import json
from pathlib import Path

from autocoder.core.global_settings_db import get_global_setting_json
from autocoder.server.settings_store import AdvancedSettings, load_advanced_settings, save_advanced_settings


def test_advanced_settings_roundtrip_sqlite(tmp_path, monkeypatch):
    db_path = tmp_path / "settings.db"
    monkeypatch.setenv("AUTOCODER_SETTINGS_DB_PATH", str(db_path))

    s = AdvancedSettings(
        review_enabled=True,
        review_mode="gate",
        api_port_range_start=6000,
        api_port_range_end=6010,
    )
    save_advanced_settings(s)

    loaded = load_advanced_settings()
    assert loaded.review_enabled is True
    assert loaded.review_mode == "gate"
    assert loaded.api_port_range_start == 6000
    assert loaded.api_port_range_end == 6010


def test_advanced_settings_migrates_from_legacy_json_once(tmp_path, monkeypatch):
    # Ensure Path.home() points to a temp directory for the legacy file.
    home = tmp_path / "home"
    (home / ".autocoder").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))

    db_path = tmp_path / "settings.db"
    monkeypatch.setenv("AUTOCODER_SETTINGS_DB_PATH", str(db_path))

    legacy_path = home / ".autocoder" / "ui_settings.json"
    legacy_payload = {
        "review_enabled": True,
        "review_mode": "advisory",
        "logs_keep_days": 9,
    }
    legacy_path.write_text(json.dumps(legacy_payload), encoding="utf-8")

    s1 = load_advanced_settings()
    assert s1.review_enabled is True
    assert s1.review_mode == "advisory"
    assert s1.logs_keep_days == 9

    # Confirm migrated to DB.
    data = get_global_setting_json("advanced_settings_v1")
    assert isinstance(data, dict)
    assert data.get("review_mode") == "advisory"

    # Delete legacy file; DB should still be authoritative.
    legacy_path.unlink()
    s2 = load_advanced_settings()
    assert s2.review_enabled is True
    assert s2.review_mode == "advisory"
    assert s2.logs_keep_days == 9

