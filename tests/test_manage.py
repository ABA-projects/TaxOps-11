"""Tests for manage.py CLI — does not require a live DB."""
import subprocess
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent


def test_manage_help_exits_zero():
    result = subprocess.run(
        [sys.executable, "manage.py", "--help"],
        capture_output=True, text=True,
        cwd=_PROJECT_ROOT
    )
    assert result.returncode == 0
    assert "init-db" in result.stdout
    assert "create-org" in result.stdout


def test_manage_unknown_command_exits_nonzero():
    result = subprocess.run(
        [sys.executable, "manage.py", "unknown-command"],
        capture_output=True, text=True,
        cwd=_PROJECT_ROOT
    )
    assert result.returncode != 0
