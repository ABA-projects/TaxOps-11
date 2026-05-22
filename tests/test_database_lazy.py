"""Tests for lazy DB engine initialization."""
import sys


def test_import_without_database_url_does_not_raise(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    sys.modules.pop("db.database", None)
    import db.database
    assert db.database.db_available() is False


def test_db_available_returns_false_without_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    sys.modules.pop("db.database", None)
    import db.database
    assert db.database.db_available() is False
