from autocoder.server.services.process_manager import is_auth_error


def test_is_auth_error_matches_common_patterns():
    assert is_auth_error("Error: not logged in (please run claude login)")
    assert is_auth_error("Authentication failed: unauthorized")
    assert is_auth_error("Invalid API key provided")


def test_is_auth_error_ignores_non_auth_lines():
    assert not is_auth_error("")
    assert not is_auth_error("INFO: Started server process")
    assert not is_auth_error("Tests failed: npm error Missing script: \"test\"")

