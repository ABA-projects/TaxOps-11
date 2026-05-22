"""Tests for Home.py login gate logic.

We test the pure helper functions extracted from Home.py,
not the Streamlit rendering itself (which requires a running app).
"""
import importlib
import sys


# ---------------------------------------------------------------------------
# Helper: reload db.database with / without DATABASE_URL set
# ---------------------------------------------------------------------------

def _reload_db(monkeypatch, url=None):
    monkeypatch.setenv("DATABASE_URL", url) if url else monkeypatch.delenv("DATABASE_URL", raising=False)
    sys.modules.pop("db.database", None)
    return importlib.import_module("db.database")


# ---------------------------------------------------------------------------
# Task 5 — login gate helpers in Home.py
# ---------------------------------------------------------------------------

class TestLoginGateHelpers:
    """login_required() and get_auth_session() must work without a live DB."""

    def test_login_required_false_without_database_url(self, monkeypatch):
        """When DATABASE_URL is not set, login_required() must return False."""
        _reload_db(monkeypatch, url=None)
        # Import helpers directly from the module-level functions we'll add
        from home_gate import login_required
        assert login_required() is False

    def test_login_required_true_with_database_url(self, monkeypatch):
        """When DATABASE_URL is set, login_required() must return True."""
        _reload_db(monkeypatch, url="postgresql://x:x@localhost/x")
        from home_gate import login_required
        assert login_required() is True

    def test_get_auth_session_returns_none_when_no_session(self):
        """get_auth_session() must return None when no 'auth' key in session_state."""
        from home_gate import get_auth_session
        # Simulate empty session_state by using a plain dict
        result = get_auth_session({})
        assert result is None

    def test_get_auth_session_returns_dict_when_present(self):
        """get_auth_session() returns the auth dict when present and valid."""
        from home_gate import get_auth_session
        fake_state = {"auth": {"user_id": "u1", "org_id": "o1", "role": "owner", "email": "a@b.com"}}
        result = get_auth_session(fake_state)
        assert result is not None
        assert result["org_id"] == "o1"

    def test_get_auth_session_returns_none_for_incomplete_auth(self):
        """get_auth_session() returns None if required keys are missing."""
        from home_gate import get_auth_session
        # Missing 'org_id'
        fake_state = {"auth": {"user_id": "u1", "role": "owner", "email": "a@b.com"}}
        result = get_auth_session(fake_state)
        assert result is None
