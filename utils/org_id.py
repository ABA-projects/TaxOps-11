"""utils/org_id.py — Helper for resolving the current organization ID.

Priority order:
  1. st.session_state["auth"]["org_id"]  (set after login when DATABASE_URL present)
  2. TAXOPS_ORG_ID environment variable   (set in docker-compose / Railway for single-org deploys)
  3. None                                 (local/demo mode — no DB persistence)

Testable without Streamlit by accepting a plain dict as session_state.
"""
from __future__ import annotations

import os


def get_org_id(session_state: dict) -> str | None:
    """Resolve the org_id for the current request.

    Args:
        session_state: A dict-like object (e.g. ``st.session_state`` or a plain dict).

    Returns:
        The org UUID string, or ``None`` if neither source is available.
    """
    # 1. Auth session (post-login in SaaS mode)
    auth = session_state.get("auth")
    if auth and isinstance(auth, dict):
        org = auth.get("org_id")
        if org:
            return str(org)

    # 2. Environment variable (single-org / self-hosted deploy)
    env_org = os.environ.get("TAXOPS_ORG_ID")
    if env_org:
        return env_org

    return None
