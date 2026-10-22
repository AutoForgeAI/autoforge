"""
Tests for SQLite journal mode selection in api/database.py.

Covers the fallback from WAL to DELETE mode on filesystems where WAL's
shared-memory index doesn't work (issue #79: "disk I/O error" on
PRAGMA table_info when starting the orchestrator).
"""

import sqlite3
from pathlib import Path
from unittest import mock

import pytest

from api import database
from api.database import (
    JOURNAL_MODE_ENV_VAR,
    Feature,
    _get_mount_fs_type,
    _is_network_path,
    _is_wal_database,
    _probe_wal_support,
    create_database,
    dispose_engine,
)

FAKE_MOUNTS = """\
/dev/sda1 / ext4 rw,relatime 0 0
C:\\134 /mnt/c 9p rw,noatime 0 0
server:/export /mnt/nfs nfs4 rw 0 0
/dev/sdb1 /mnt/c/local\\040disk ext4 rw 0 0
sshfs#host: /home/me/remote fuse.sshfs rw 0 0
/dev/sdc1 /media/usb fuseblk rw 0 0
"""


@pytest.fixture(autouse=True)
def _clean_state(monkeypatch):
    monkeypatch.delenv(JOURNAL_MODE_ENV_VAR, raising=False)
    database._wal_support_cache.clear()
    yield
    database._wal_support_cache.clear()


def _journal_mode(engine) -> str:
    with engine.connect() as conn:
        raw = conn.connection.dbapi_connection
        assert raw is not None
        return str(raw.execute("PRAGMA journal_mode").fetchone()[0]).lower()


def _patch_mounts(content: str):
    return mock.patch("builtins.open", mock.mock_open(read_data=content))


class TestMountDetection:
    def test_longest_mount_point_wins(self):
        with _patch_mounts(FAKE_MOUNTS):
            assert _get_mount_fs_type("/mnt/c/Users/me/project") == "9p"
            assert _get_mount_fs_type("/mnt/c/local disk/project") == "ext4"
            assert _get_mount_fs_type("/home/me/project") == "ext4"

    def test_prefix_must_match_whole_component(self):
        with _patch_mounts(FAKE_MOUNTS):
            # /mnt/nfs-local is not under /mnt/nfs
            assert _get_mount_fs_type("/mnt/nfs-local/project") == "ext4"

    @pytest.mark.parametrize(
        "path,expected",
        [
            ("/mnt/c/Users/me/project", True),  # WSL Windows drive (9p)
            ("/mnt/nfs/project", True),
            ("/home/me/remote/project", True),  # fuse.sshfs
            ("/media/usb/project", False),  # fuseblk (local ntfs-3g)
            ("/home/me/project", False),
            ("/mnt/c/local disk/project", False),
        ],
    )
    def test_is_network_path(self, path, expected):
        if database.sys.platform == "win32":
            pytest.skip("Unix mount detection")
        with mock.patch.object(Path, "resolve", lambda self: self), _patch_mounts(FAKE_MOUNTS):
            assert _is_network_path(Path(path)) is expected


class TestWalProbe:
    def test_probe_succeeds_on_local_disk_and_cleans_up(self, tmp_path):
        assert _probe_wal_support(tmp_path) is True
        assert list(tmp_path.iterdir()) == []

    def test_probe_fails_when_sqlite_errors(self, tmp_path):
        real_connect = sqlite3.connect
        calls = {"n": 0}

        def flaky_connect(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 2:
                raise sqlite3.OperationalError("disk I/O error")
            return real_connect(*args, **kwargs)

        with mock.patch.object(database.sqlite3, "connect", flaky_connect):
            assert _probe_wal_support(tmp_path) is False
        assert list(tmp_path.iterdir()) == []

    def test_probe_result_is_cached(self, tmp_path):
        assert _probe_wal_support(tmp_path) is True
        with mock.patch.object(database.sqlite3, "connect", side_effect=AssertionError("not cached")):
            assert _probe_wal_support(tmp_path) is True


class TestCreateDatabaseJournalMode:
    def test_uses_wal_on_local_disk(self, tmp_path):
        engine, _ = create_database(tmp_path)
        try:
            assert _journal_mode(engine) == "wal"
        finally:
            dispose_engine(tmp_path)

    def test_falls_back_to_delete_when_wal_unsupported(self, tmp_path):
        with mock.patch.object(database, "_probe_wal_support", return_value=False):
            engine, _ = create_database(tmp_path)
        try:
            assert _journal_mode(engine) == "delete"
        finally:
            dispose_engine(tmp_path)

    def test_env_override(self, tmp_path, monkeypatch):
        monkeypatch.setenv(JOURNAL_MODE_ENV_VAR, "delete")
        with mock.patch.object(database, "_probe_wal_support", side_effect=AssertionError("probe skipped")):
            engine, _ = create_database(tmp_path)
        try:
            assert _journal_mode(engine) == "delete"
        finally:
            dispose_engine(tmp_path)

    def test_invalid_env_override_is_ignored(self, tmp_path, monkeypatch):
        monkeypatch.setenv(JOURNAL_MODE_ENV_VAR, "bogus; DROP TABLE features")
        engine, _ = create_database(tmp_path)
        try:
            assert _journal_mode(engine) == "wal"
        finally:
            dispose_engine(tmp_path)

    def test_existing_wal_database_is_converted_and_keeps_data(self, tmp_path):
        # First run on a filesystem where WAL "works" leaves the DB in WAL mode
        _, session_maker = create_database(tmp_path)
        with session_maker() as session:
            session.add(Feature(priority=1, category="c", name="kept", description="d", steps=[]))
            session.commit()
        dispose_engine(tmp_path)

        db_path = database.get_database_path(tmp_path)
        assert _is_wal_database(db_path)

        # Next run detects that WAL is unusable and must switch the file over
        with mock.patch.object(database, "_probe_wal_support", return_value=False):
            engine, session_maker = create_database(tmp_path)
        try:
            assert _journal_mode(engine) == "delete"
            assert not _is_wal_database(db_path)
            with session_maker() as session:
                assert [f.name for f in session.query(Feature).all()] == ["kept"]
        finally:
            dispose_engine(tmp_path)
