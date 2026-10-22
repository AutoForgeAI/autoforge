"""
Tests for SQLite journal mode selection and WAL fallback (issue #79).

Run with: python -m pytest test_database_journal.py
"""

import sqlite3
from pathlib import Path

import pytest

import api.database as database
from api.database import (
    _force_rollback_journal,
    _fs_type_for_path,
    _has_wal_header,
    _is_unsafe_wal_fs_type,
    _probe_wal_support,
    create_database,
    dispose_engine,
    get_database_path,
)

MOUNTS = "\n".join([
    "/dev/sda1 / ext4 rw,relatime 0 0",
    "tmpfs /tmp tmpfs rw 0 0",
    "C:\\134 /mnt/c 9p rw,dirsync,aname=drvfs 0 0",
    "server:/export /mnt/code nfs4 rw 0 0",
    "/dev/sdb1 /mnt/code/local ext4 rw 0 0",
    "user@host:/ /home/me/My\\040Share fuse.sshfs rw 0 0",
])


@pytest.fixture(autouse=True)
def _clear_wal_cache():
    database._wal_support_cache.clear()
    yield
    database._wal_support_cache.clear()


def _make_wal_db(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE t (x INTEGER)")
    conn.execute("INSERT INTO t VALUES (1)")
    conn.commit()
    conn.close()


def _add_and_count_feature(session_maker) -> int:
    session = session_maker()
    try:
        session.add(database.Feature(priority=1, category="c", name="n", description="d", steps=[]))
        session.commit()
        return int(session.query(database.Feature).count())
    finally:
        session.close()


def _journal_mode(db_path: Path) -> str:
    conn = sqlite3.connect(str(db_path))
    try:
        return str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower()
    finally:
        conn.close()


class TestFsTypeForPath:
    def test_root_fallback(self):
        assert _fs_type_for_path("/home/me/project", MOUNTS) == "ext4"

    def test_wsl_drive(self):
        assert _fs_type_for_path("/mnt/c/Users/me/project", MOUNTS) == "9p"

    def test_component_boundary(self):
        # /mnt/c must not match /mnt/code
        assert _fs_type_for_path("/mnt/code/app", MOUNTS) == "nfs4"

    def test_longest_mount_wins(self):
        assert _fs_type_for_path("/mnt/code/local/app", MOUNTS) == "ext4"

    def test_exact_mount_point(self):
        assert _fs_type_for_path("/mnt/c", MOUNTS) == "9p"

    def test_octal_escaped_mount_point(self):
        assert _fs_type_for_path("/home/me/My Share/app", MOUNTS) == "fuse.sshfs"

    def test_no_mounts(self):
        assert _fs_type_for_path("/anything", "") is None


class TestUnsafeWalFsType:
    @pytest.mark.parametrize("fs_type", ["nfs", "nfs4", "cifs", "smb3", "9p", "drvfs", "vboxsf",
                                         "virtiofs", "fuse.sshfs", "fuse.rclone", "fuse"])
    def test_unsafe(self, fs_type):
        assert _is_unsafe_wal_fs_type(fs_type)

    @pytest.mark.parametrize("fs_type", ["ext4", "xfs", "btrfs", "apfs", "tmpfs", "zfs", "fuseblk"])
    def test_safe(self, fs_type):
        assert not _is_unsafe_wal_fs_type(fs_type)


class TestWalFallback:
    def test_local_dir_uses_wal(self, tmp_path):
        create_database(tmp_path)
        try:
            assert _journal_mode(get_database_path(tmp_path)) == "wal"
        finally:
            dispose_engine(tmp_path)

    def test_disk_io_error_falls_back_to_delete(self, tmp_path, monkeypatch):
        real_apply = database._apply_journal_mode
        calls = []

        def flaky_apply(engine, journal_mode):
            calls.append(journal_mode)
            if journal_mode == "WAL":
                raise sqlite3.OperationalError("disk I/O error")
            real_apply(engine, journal_mode)

        monkeypatch.setattr(database, "_apply_journal_mode", flaky_apply)

        engine, session_maker = create_database(tmp_path)
        try:
            assert calls == ["WAL", "DELETE"]
            assert _journal_mode(get_database_path(tmp_path)) == "delete"
            # Schema was created and the database is usable
            session = session_maker()
            try:
                session.add(database.Feature(priority=1, category="c", name="n", description="d", steps=[]))
                session.commit()
                assert session.query(database.Feature).count() == 1
            finally:
                session.close()
        finally:
            dispose_engine(tmp_path)

    def test_other_errors_are_not_swallowed(self, tmp_path, monkeypatch):
        def broken_apply(engine, journal_mode):
            raise sqlite3.OperationalError("database is locked")

        monkeypatch.setattr(database, "_apply_journal_mode", broken_apply)
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            create_database(tmp_path)

    def test_force_rollback_journal_converts_wal_database(self, tmp_path):
        db_path = tmp_path / "features.db"
        _make_wal_db(db_path)
        assert _journal_mode(db_path) == "wal"

        _force_rollback_journal(db_path)

        assert _journal_mode(db_path) == "delete"
        conn = sqlite3.connect(str(db_path))
        try:
            assert conn.execute("SELECT x FROM t").fetchall() == [(1,)]
        finally:
            conn.close()

    def test_force_rollback_journal_missing_file(self, tmp_path):
        _force_rollback_journal(tmp_path / "missing.db")
        assert not (tmp_path / "missing.db").exists()


class TestUnsafeFsExistingWalDatabase:
    """A features.db left in WAL mode on a filesystem detected as unsafe (e.g. WSL /mnt/c)."""

    def test_converted_before_opening(self, tmp_path, monkeypatch):
        db_path = get_database_path(tmp_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        _make_wal_db(db_path)
        monkeypatch.setattr(database, "_is_network_path", lambda path: True)

        engine, session_maker = create_database(tmp_path)
        try:
            assert _journal_mode(db_path) == "delete"
            assert _add_and_count_feature(session_maker) == 1
        finally:
            dispose_engine(tmp_path)

    def test_delete_apply_failure_recovers(self, tmp_path, monkeypatch):
        db_path = get_database_path(tmp_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        _make_wal_db(db_path)
        monkeypatch.setattr(database, "_is_network_path", lambda path: True)
        # Simulate the up-front conversion not happening (e.g. file was busy)
        monkeypatch.setattr(database, "_has_wal_header", lambda path: False)

        real_apply = database._apply_journal_mode
        calls = []

        def flaky_apply(engine, journal_mode):
            calls.append(journal_mode)
            if len(calls) == 1:
                raise sqlite3.OperationalError("disk I/O error")
            real_apply(engine, journal_mode)

        monkeypatch.setattr(database, "_apply_journal_mode", flaky_apply)

        engine, session_maker = create_database(tmp_path)
        try:
            assert calls == ["DELETE", "DELETE"]
            assert _journal_mode(db_path) == "delete"
            assert _add_and_count_feature(session_maker) == 1
        finally:
            dispose_engine(tmp_path)


class TestWalProbe:
    def test_probe_succeeds_locally_and_cleans_up(self, tmp_path):
        assert _probe_wal_support(tmp_path) is True
        assert list(tmp_path.iterdir()) == []

    def test_probe_failure_returns_false_and_cleans_up(self, tmp_path, monkeypatch):
        real_connect = sqlite3.connect

        class FailingConn:
            def __init__(self, conn):
                self._conn = conn

            def execute(self, sql, *args):
                if sql.startswith("SELECT"):
                    raise sqlite3.OperationalError("disk I/O error")
                return self._conn.execute(sql, *args)

            def close(self):
                self._conn.close()

        monkeypatch.setattr(database.sqlite3, "connect", lambda *a, **kw: FailingConn(real_connect(*a, **kw)))
        assert _probe_wal_support(tmp_path) is False
        assert list(tmp_path.iterdir()) == []

    def test_probe_result_is_cached(self, tmp_path, monkeypatch):
        probes = []

        def fake_probe(db_dir):
            probes.append(db_dir)
            return True

        monkeypatch.setattr(database, "_probe_wal_support", fake_probe)
        assert database._wal_supported(tmp_path)
        assert database._wal_supported(tmp_path)
        assert len(probes) == 1

    @pytest.mark.parametrize("existing_wal", [False, True])
    def test_failed_probe_never_sets_wal_on_features_db(self, tmp_path, monkeypatch, existing_wal):
        db_path = get_database_path(tmp_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        if existing_wal:
            _make_wal_db(db_path)
        monkeypatch.setattr(database, "_is_network_path", lambda path: False)
        monkeypatch.setattr(database, "_probe_wal_support", lambda db_dir: False)

        # Trace every SQL statement SQLAlchemy connections issue against features.db
        statements: list[str] = []
        real_create_engine = database.create_engine

        def tracing_create_engine(*args, **kwargs):
            engine = real_create_engine(*args, **kwargs)

            @database.event.listens_for(engine, "connect")
            def _trace(dbapi_connection, connection_record):
                dbapi_connection.set_trace_callback(statements.append)

            return engine

        monkeypatch.setattr(database, "create_engine", tracing_create_engine)

        engine, session_maker = create_database(tmp_path)
        try:
            assert _add_and_count_feature(session_maker) == 1
            assert _journal_mode(db_path) == "delete"
            assert not _has_wal_header(db_path)
            assert any("journal_mode=DELETE" in s for s in statements)
            assert not any("journal_mode=wal" in s.lower() for s in statements)
        finally:
            dispose_engine(tmp_path)
