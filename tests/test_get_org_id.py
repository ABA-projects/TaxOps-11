"""Tests for _get_org_id() helper used in pages/1_Procesar.py and pages/6_Exogenas.py.

We extract _get_org_id into utils/org_id.py so it can be tested without Streamlit.
"""
from __future__ import annotations

import os


class TestGetOrgId:
    """_get_org_id(session_state) must resolve org_id in priority order."""

    def _fn(self, session_state):
        from utils.org_id import get_org_id
        return get_org_id(session_state)

    def test_returns_org_id_from_auth_session(self):
        """When 'auth' has org_id, that value takes priority."""
        state = {"auth": {"user_id": "u1", "org_id": "org-from-auth", "role": "owner", "email": "a@b.com"}}
        assert self._fn(state) == "org-from-auth"

    def test_falls_back_to_env_var_when_no_auth(self, monkeypatch):
        """When no auth session, falls back to TAXOPS_ORG_ID env var."""
        monkeypatch.setenv("TAXOPS_ORG_ID", "org-from-env")
        state = {}
        assert self._fn(state) == "org-from-env"

    def test_returns_none_when_no_auth_and_no_env(self, monkeypatch):
        """When neither auth session nor env var, returns None."""
        monkeypatch.delenv("TAXOPS_ORG_ID", raising=False)
        state = {}
        assert self._fn(state) is None

    def test_auth_takes_priority_over_env(self, monkeypatch):
        """Auth session org_id overrides TAXOPS_ORG_ID env var."""
        monkeypatch.setenv("TAXOPS_ORG_ID", "org-from-env")
        state = {"auth": {"user_id": "u1", "org_id": "org-from-auth", "role": "owner", "email": "a@b.com"}}
        assert self._fn(state) == "org-from-auth"

    def test_incomplete_auth_falls_back_to_env(self, monkeypatch):
        """If auth dict is missing org_id, fall back to env var."""
        monkeypatch.setenv("TAXOPS_ORG_ID", "org-from-env")
        # Missing org_id key
        state = {"auth": {"user_id": "u1", "role": "owner", "email": "a@b.com"}}
        assert self._fn(state) == "org-from-env"
