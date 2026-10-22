"""
Existing Codebase Onboarding Tests
==================================

Tests for detecting code already present in a project folder and scaffolding
the existing-codebase mode (marker file + dedicated initializer prompt).

Run with: python -m pytest test_existing_codebase.py
"""

from pathlib import Path

import pytest

from prompts import (
    TEMPLATES_DIR,
    detect_existing_codebase,
    is_existing_codebase_project,
    scaffold_project_prompts,
)


def _write(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class TestDetectExistingCodebase:
    def test_empty_directory(self, tmp_path):
        assert detect_existing_codebase(tmp_path) is False

    def test_missing_directory(self, tmp_path):
        assert detect_existing_codebase(tmp_path / "nope") is False

    @pytest.mark.parametrize("manifest", ["package.json", "pyproject.toml", "go.mod", "Cargo.toml"])
    def test_root_manifest(self, tmp_path, manifest):
        _write(tmp_path / manifest, "{}")
        assert detect_existing_codebase(tmp_path) is True

    def test_nested_manifest_alone_is_not_enough(self, tmp_path):
        _write(tmp_path / "docs" / "package.json", "{}")
        assert detect_existing_codebase(tmp_path) is False

    def test_source_files(self, tmp_path):
        for name in ("a.py", "b.py", "pkg/c.py"):
            _write(tmp_path / "src" / name)
        assert detect_existing_codebase(tmp_path) is True

    def test_too_few_source_files(self, tmp_path):
        _write(tmp_path / "script.sh")
        _write(tmp_path / "notes.md")
        assert detect_existing_codebase(tmp_path) is False

    def test_ignores_dependency_and_vcs_dirs(self, tmp_path):
        for i in range(5):
            _write(tmp_path / "node_modules" / "lib" / f"m{i}.js")
            _write(tmp_path / ".git" / "hooks" / f"h{i}.sh")
            _write(tmp_path / "venv" / "lib" / f"p{i}.py")
        assert detect_existing_codebase(tmp_path) is False

    def test_fresh_scaffold_is_not_existing_code(self, tmp_path):
        scaffold_project_prompts(tmp_path)
        assert detect_existing_codebase(tmp_path) is False


class TestScaffoldExistingCodebase:
    def _initializer(self, project_dir: Path) -> str:
        return (project_dir / ".autoforge" / "prompts" / "initializer_prompt.md").read_text(encoding="utf-8")

    def test_existing_template_exists(self):
        template = TEMPLATES_DIR / "initializer_prompt_existing.template.md"
        assert template.exists()
        assert "[FEATURE_COUNT]" in template.read_text(encoding="utf-8")

    def test_greenfield_scaffold(self, tmp_path):
        scaffold_project_prompts(tmp_path)
        assert not is_existing_codebase_project(tmp_path)
        expected = (TEMPLATES_DIR / "initializer_prompt.template.md").read_text(encoding="utf-8")
        assert self._initializer(tmp_path) == expected

    def test_existing_scaffold(self, tmp_path):
        _write(tmp_path / "package.json", "{}")
        scaffold_project_prompts(tmp_path, existing_codebase=True)
        assert is_existing_codebase_project(tmp_path)
        expected = (TEMPLATES_DIR / "initializer_prompt_existing.template.md").read_text(encoding="utf-8")
        assert self._initializer(tmp_path) == expected
        # The user's files are untouched
        assert (tmp_path / "package.json").read_text(encoding="utf-8") == "{}"

    def test_existing_scaffold_replaces_untouched_default_initializer(self, tmp_path):
        scaffold_project_prompts(tmp_path)
        scaffold_project_prompts(tmp_path, existing_codebase=True)
        assert "EXISTING CODEBASE" in self._initializer(tmp_path)

    def test_existing_scaffold_keeps_customized_initializer(self, tmp_path):
        scaffold_project_prompts(tmp_path)
        initializer = tmp_path / ".autoforge" / "prompts" / "initializer_prompt.md"
        initializer.write_text("my custom prompt", encoding="utf-8")
        scaffold_project_prompts(tmp_path, existing_codebase=True)
        assert self._initializer(tmp_path) == "my custom prompt"


class TestClaudeMdGuard:
    """Chat sessions must never destroy a CLAUDE.md the user already had."""

    def test_backup_and_restore(self, tmp_path):
        from server.services.claude_md_guard import (
            get_claude_md_backup_path,
            release_session_claude_md,
            write_session_claude_md,
        )

        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("# my repo rules", encoding="utf-8")

        write_session_claude_md(tmp_path, "session prompt")
        assert claude_md.read_text(encoding="utf-8") == "session prompt"
        assert get_claude_md_backup_path(tmp_path).read_text(encoding="utf-8") == "# my repo rules"

        release_session_claude_md(tmp_path)
        assert claude_md.read_text(encoding="utf-8") == "# my repo rules"
        assert not get_claude_md_backup_path(tmp_path).exists()

    def test_overlapping_sessions_restore_after_last_release(self, tmp_path):
        from server.services.claude_md_guard import release_session_claude_md, write_session_claude_md

        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("# my repo rules", encoding="utf-8")

        write_session_claude_md(tmp_path, "spec prompt")
        write_session_claude_md(tmp_path, "assistant prompt")
        release_session_claude_md(tmp_path)
        assert claude_md.read_text(encoding="utf-8") == "assistant prompt"
        release_session_claude_md(tmp_path)
        assert claude_md.read_text(encoding="utf-8") == "# my repo rules"

    def test_no_user_file_leaves_no_backup(self, tmp_path):
        from server.services.claude_md_guard import (
            get_claude_md_backup_path,
            release_session_claude_md,
            write_session_claude_md,
        )

        write_session_claude_md(tmp_path, "session prompt")
        release_session_claude_md(tmp_path)
        assert not get_claude_md_backup_path(tmp_path).exists()
        # Unmatched release is a no-op
        release_session_claude_md(tmp_path)

    def test_leftover_backup_from_crash_is_not_clobbered(self, tmp_path):
        from server.services.claude_md_guard import (
            get_claude_md_backup_path,
            release_session_claude_md,
            write_session_claude_md,
        )

        backup = get_claude_md_backup_path(tmp_path)
        backup.parent.mkdir(parents=True)
        backup.write_text("# my repo rules", encoding="utf-8")
        # CLAUDE.md still holds a prompt from a session that crashed
        (tmp_path / "CLAUDE.md").write_text("stale prompt", encoding="utf-8")

        write_session_claude_md(tmp_path, "new prompt")
        assert backup.read_text(encoding="utf-8") == "# my repo rules"
        release_session_claude_md(tmp_path)
        assert (tmp_path / "CLAUDE.md").read_text(encoding="utf-8") == "# my repo rules"


class _FakeClaudeClient:
    """Stand-in for ClaudeSDKClient that records the CLAUDE.md it would load."""

    seen_claude_md: list[str] = []

    def __init__(self, options=None):
        self.options = options

    async def __aenter__(self):
        cwd = Path(self.options.cwd)
        _FakeClaudeClient.seen_claude_md.append((cwd / "CLAUDE.md").read_text(encoding="utf-8"))
        return self

    async def __aexit__(self, *args):
        return None


@pytest.fixture
def stub_sdk(monkeypatch):
    import registry

    monkeypatch.setattr(registry, "get_effective_sdk_env", lambda: {})
    monkeypatch.setattr(registry, "get_effort_setting", lambda: "high")
    _FakeClaudeClient.seen_claude_md = []
    return _FakeClaudeClient


def _drain(agen):
    import asyncio

    async def run():
        return [chunk async for chunk in agen]

    return asyncio.run(run())


class TestChatSessionsPreserveClaudeMd:
    def test_spec_session_restores_user_claude_md(self, tmp_path, monkeypatch, stub_sdk):
        import asyncio

        from server.services import spec_chat_session

        monkeypatch.setattr(spec_chat_session, "ClaudeSDKClient", stub_sdk)

        async def fake_query(self, message, attachments=None):
            self.kickoff = message
            if False:
                yield {}

        monkeypatch.setattr(spec_chat_session.SpecChatSession, "_query_claude", fake_query)

        _write(tmp_path / "package.json", "{}")
        (tmp_path / "CLAUDE.md").write_text("# my repo rules", encoding="utf-8")
        scaffold_project_prompts(tmp_path, existing_codebase=True)

        session = spec_chat_session.SpecChatSession("myapp", tmp_path)
        _drain(session.start())

        # During the session the CLI sees the create-spec prompt
        assert "Spec Creation Assistant" in stub_sdk.seen_claude_md[0]
        assert "EXISTING CODEBASE MODE" in session.kickoff

        asyncio.run(session.close())
        assert (tmp_path / "CLAUDE.md").read_text(encoding="utf-8") == "# my repo rules"

    def test_spec_session_restores_on_client_init_failure(self, tmp_path, monkeypatch, stub_sdk):
        from server.services import spec_chat_session

        class FailingClient(stub_sdk):
            async def __aenter__(self):
                raise RuntimeError("boom")

        monkeypatch.setattr(spec_chat_session, "ClaudeSDKClient", FailingClient)
        (tmp_path / "CLAUDE.md").write_text("# my repo rules", encoding="utf-8")
        scaffold_project_prompts(tmp_path, existing_codebase=True)

        session = spec_chat_session.SpecChatSession("myapp", tmp_path)
        chunks = _drain(session.start())
        assert chunks and chunks[-1]["type"] == "error"
        assert (tmp_path / "CLAUDE.md").read_text(encoding="utf-8") == "# my repo rules"

    def test_assistant_session_restores_user_claude_md(self, tmp_path, monkeypatch, stub_sdk):
        import asyncio

        from server.services import assistant_chat_session

        monkeypatch.setattr(assistant_chat_session, "ClaudeSDKClient", stub_sdk)
        (tmp_path / "CLAUDE.md").write_text("# my repo rules", encoding="utf-8")
        scaffold_project_prompts(tmp_path, existing_codebase=True)

        session = assistant_chat_session.AssistantChatSession("myapp", tmp_path)
        _drain(session.start())
        assert stub_sdk.seen_claude_md and stub_sdk.seen_claude_md[0] != "# my repo rules"

        asyncio.run(session.close())
        assert (tmp_path / "CLAUDE.md").read_text(encoding="utf-8") == "# my repo rules"


class AssistantMessage:
    """Shaped like the SDK message the spec session parses (matched by class name)."""

    def __init__(self, content):
        self.content = content


class TextBlock:
    def __init__(self, text):
        self.text = text


class _FakeStreamingClient(_FakeClaudeClient):
    """Fake client that also answers queries, recording CLAUDE.md at each one."""

    seen_at_query: list[str] = []

    async def query(self, message):
        cwd = Path(self.options.cwd)
        _FakeStreamingClient.seen_at_query.append((cwd / "CLAUDE.md").read_text(encoding="utf-8"))

    async def receive_response(self):
        yield AssistantMessage([TextBlock("Hi! Let's plan the new work.")])


@pytest.fixture
def isolated_server(tmp_path, monkeypatch, stub_sdk):
    """The real FastAPI app with an isolated ~/.autoforge and a stubbed Claude client."""
    import registry
    import temp_cleanup
    from server.services import spec_chat_session

    # Don't sweep the machine's real temp dir on lifespan startup
    monkeypatch.setattr(
        temp_cleanup, "cleanup_stale_temp", lambda: {"dirs_deleted": 0, "files_deleted": 0, "bytes_freed": 0}
    )
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setattr(registry, "_engine", None)
    monkeypatch.setattr(registry, "_SessionLocal", None)
    monkeypatch.setattr(spec_chat_session, "ClaudeSDKClient", _FakeStreamingClient)
    _FakeStreamingClient.seen_at_query = []

    from server.main import app

    yield app
    monkeypatch.setattr(registry, "_engine", None)


class TestSpecChatEndToEnd:
    """Go through the real /api/spec/ws route and app lifespan, never calling close()."""

    def test_user_claude_md_restored_after_disconnect_and_shutdown(self, tmp_path, isolated_server):
        from fastapi.testclient import TestClient

        repo = tmp_path / "qarepo"
        _write(repo / "package.json", "{}")
        (repo / "CLAUDE.md").write_text("# my repo rules", encoding="utf-8")
        claude_md = repo / "CLAUDE.md"

        with TestClient(isolated_server, client=("127.0.0.1", 50000)) as client:
            resp = client.post("/api/projects", json={"name": "qarepo", "path": repo.as_posix()})
            assert resp.status_code == 200, resp.text
            assert is_existing_codebase_project(repo)

            with client.websocket_connect("/api/spec/ws/qarepo") as ws:
                ws.send_json({"type": "start"})
                types = []
                while "response_done" not in types:
                    types.append(ws.receive_json()["type"])
                assert "text" in types
                # Between turns the user's file is back in place
                assert claude_md.read_text(encoding="utf-8") == "# my repo rules"

                ws.send_json({"type": "message", "content": "Add dark mode"})
                types = []
                while "response_done" not in types:
                    types.append(ws.receive_json()["type"])

            # The CLI saw the create-spec prompt during both turns
            assert len(_FakeStreamingClient.seen_at_query) == 2
            assert all("Spec Creation Assistant" in seen for seen in _FakeStreamingClient.seen_at_query)

            # WebSocket disconnected, session kept for resume: the user's file is intact
            assert claude_md.read_text(encoding="utf-8") == "# my repo rules"

        # After lifespan shutdown
        assert claude_md.read_text(encoding="utf-8") == "# my repo rules"
        assert not (repo / ".autoforge" / "CLAUDE.md.user-backup").exists()


class TestLeftoverBackup:
    def test_restore_leftover_claude_md(self, tmp_path):
        from server.services.claude_md_guard import get_claude_md_backup_path, restore_leftover_claude_md

        backup = get_claude_md_backup_path(tmp_path)
        backup.parent.mkdir(parents=True)
        backup.write_text("# my repo rules", encoding="utf-8")
        (tmp_path / "CLAUDE.md").write_text("stale spec prompt", encoding="utf-8")

        assert restore_leftover_claude_md(tmp_path) is True
        assert (tmp_path / "CLAUDE.md").read_text(encoding="utf-8") == "# my repo rules"
        assert not backup.exists()
        assert restore_leftover_claude_md(tmp_path) is False

    def test_leftover_kept_while_session_mid_turn(self, tmp_path):
        from server.services.claude_md_guard import (
            release_session_claude_md,
            restore_leftover_claude_md,
            write_session_claude_md,
        )

        (tmp_path / "CLAUDE.md").write_text("# my repo rules", encoding="utf-8")
        write_session_claude_md(tmp_path, "spec prompt")
        assert restore_leftover_claude_md(tmp_path) is False
        assert (tmp_path / "CLAUDE.md").read_text(encoding="utf-8") == "spec prompt"
        release_session_claude_md(tmp_path)
        assert (tmp_path / "CLAUDE.md").read_text(encoding="utf-8") == "# my repo rules"

    def test_agent_start_restores_leftover_backup(self, tmp_path, monkeypatch):
        import asyncio

        from server.services import process_manager
        from server.services.claude_md_guard import get_claude_md_backup_path

        backup = get_claude_md_backup_path(tmp_path)
        backup.parent.mkdir(parents=True)
        backup.write_text("# my repo rules", encoding="utf-8")
        (tmp_path / "CLAUDE.md").write_text("stale spec prompt", encoding="utf-8")

        def no_popen(*args, **kwargs):
            raise OSError("not starting a real agent in tests")

        monkeypatch.setattr(process_manager.subprocess, "Popen", no_popen)
        manager = process_manager.AgentProcessManager("myapp", tmp_path, Path(__file__).parent)
        asyncio.run(manager.start())
        assert (tmp_path / "CLAUDE.md").read_text(encoding="utf-8") == "# my repo rules"
